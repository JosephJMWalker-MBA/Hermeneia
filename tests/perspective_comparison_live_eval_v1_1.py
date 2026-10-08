"""P7 semantic extraction v1.1 experiment (#215): one bounded live run, compared with the immutable v1 baseline.

Executes live_evaluation_protocol_v1.1.json, which was frozen before any v1.1
call. It reuses the v1 live harness and the frozen §9 scorer, imported
unchanged. Only the v1.1 parser and prompt builder are substituted at
runtime, and the cross-participant metric is added. Same production route,
same local model, same sampling, loopback only, nothing accepted.

    python tests/perspective_comparison_live_eval_v1_1.py --ceiling-only --out research/perspective_comparison_live/v1.1
    python tests/perspective_comparison_live_eval_v1_1.py --out research/perspective_comparison_live/v1.1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
for entry in (str(ROOT), str(TESTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import perspective_comparison_candidate_lab as candidate_lab  # noqa: E402
import perspective_comparison_live_eval as live  # noqa: E402  (v1 harness, unchanged)
import synthetic_study_lab as lab  # noqa: E402
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence  # noqa: E402
from hermeneia.perspective_comparison_candidates import (  # noqa: E402
    EXPERIMENTAL_POLICY_VERSION, V1_1_CLASSIFICATIONS, build_prompt_v1_1, candidate_inputs, parse_output_v1_1,
    unit_texts, view_from_receipts,
)
from hermeneia.web.app import create_app  # noqa: E402
from test_e10_vertical_slice_api import _FakeOllamaClient  # noqa: E402

PROTOCOL_PATH = TESTS / "fixtures" / "perspective_comparison" / "v1" / "live_evaluation_protocol_v1.1.json"
V1_RESULTS = ROOT / "research" / "perspective_comparison_live" / "v1" / "results.json"
INVERSE = {stance: value for value, stance in V1_1_CLASSIFICATIONS.items()}
SPAN = ("asserts", "denies", "unclassifiable")


def _use_v1_1() -> None:
    """Route the unchanged v1 harness through the v1.1 parser and prompt builder."""
    live.parse_output = parse_output_v1_1
    live.build_prompt = build_prompt_v1_1


def to_v1_1_wire(v1_wire: str) -> str:
    """Render a v1 wire output (used only for scripted references) in the v1.1 wire format."""
    value = json.loads(v1_wire)
    return json.dumps({"propositions": [{"id": p["id"], "statement": p["statement"], "classifications": [
        {"participant": x["participant"], "classification": INVERSE[x["stance"]], "quote": x["quote"], "relies_on": x["relies_on"]}
        for x in p["positions"]]} for p in value["propositions"]], "assumptions": value["assumptions"]})


def _post(client, receipt_ids, model):
    return client.post("/api/perspective/comparison/candidates",
                       json={"receipt_ids": receipt_ids, "model": model, "policy_version": EXPERIMENTAL_POLICY_VERSION})


def _rebuilt_prompt(db, receipt_ids):
    conn = lab._read_only(db)
    try:
        inputs = candidate_inputs(conn, read_perspective_achievement_evidence(conn), receipt_ids)
        view = view_from_receipts(inputs["receipts"])
        return view, build_prompt_v1_1(view, unit_texts(conn, view, inputs["receipts"]))
    finally:
        conn.close()


def live_extraction(layer1_corpus: dict, case: dict, model: str, workdir: Path) -> dict:
    with lab.isolated(workdir):
        _FakeOllamaClient.models = list(layer1_corpus["models"])
        built = live.layer1_lab.materialize(layer1_corpus, case, workdir / "ws")
    db, ids, labels = built["db"], built["ids"], built["labels"]
    receipt_ids = [ids[key] for key in case["compare"]]
    before = lab._logical_digest(db)
    with live.fresh_settings(workdir), live.loopback_only():
        client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
        response = _post(client, receipt_ids, model)
    view, prompt = _rebuilt_prompt(db, receipt_ids)
    return {"status": response.status_code, "body": response.get_json() or {}, "labels": labels, "view": view,
            "prompt": prompt, "workspace_unchanged": lab._logical_digest(db) == before, "accepted_rows": live._accepted_rows(db)}


def cross_participant(record: dict, case: dict) -> dict:
    reference = case["reference"]
    applicable = bool(reference["agreement"] or reference["disagreement"])
    if record["refused"]:
        return {"applicable": applicable, "holds": False, "propositions": 0, "multi_participant": 0,
                "reference_relations": len(reference["agreement"]) + len(reference["disagreement"])}
    multi = sum(1 for p in record["structure"]["propositions"] if sum(x["stance"] in SPAN for x in p["positions"]) >= 2)
    return {"applicable": applicable, "holds": multi > 0, "propositions": len(record["structure"]["propositions"]),
            "multi_participant": multi, "reference_relations": len(reference["agreement"]) + len(reference["disagreement"])}


def _record(kind, item_id, base, temptation, live_run, case) -> dict:
    record = {"run_id": f"{kind}:{item_id}", "kind": "faithful" if kind == "F" else "adversarial", "base_case": base,
              "temptation": temptation, **live.analyse(live_run, case), "governance": live.governance_checks(live_run)}
    if kind == "A":
        record["temptation_result"] = live.temptation(item_id, record)
    record["cross_participant"] = cross_participant(record, case)
    return record


def extend_aggregate(records: list[dict], cases: dict, protocol: dict) -> dict:
    result = live.aggregate(records, cases, protocol)
    applicable = [r for r in records if r["cross_participant"]["applicable"]]
    props = sum(r["cross_participant"]["propositions"] for r in records)
    multi = sum(r["cross_participant"]["multi_participant"] for r in records)
    relations = sum(r["cross_participant"]["reference_relations"] for r in records)
    tp = sum(r["score"]["agreement"]["tp"] + r["score"]["disagreement"]["tp"] for r in records if r.get("score"))
    holds = sum(1 for r in applicable if r["cross_participant"]["holds"])
    result["metrics"]["multi_participant_proposition_rate"] = {"multi_participant": multi, "propositions": props,
                                                               "rate": live._ratio(multi, props)}
    result["metrics"]["cross_participant_invariant"] = {"holds": holds, "applicable": len(applicable),
                                                        "rate": live._ratio(holds, len(applicable))}
    result["metrics"]["relation_recall_all_runs"] = {"tp": tp, "reference_relations": relations, "rate": live._ratio(tp, relations)}
    material = (len(applicable) > 0 and holds / len(applicable) >= 0.5 and relations > 0 and tp / relations >= 0.25)
    result["decision_after_phi4_mini"] = "material_change" if material else "model_limited"
    return result


def run(out: Path) -> dict:
    _use_v1_1()
    protocol = json.loads(PROTOCOL_PATH.read_text())
    corpus, cases = candidate_lab.load()
    layer1_corpus = live.layer1_lab.load_corpus(ROOT / corpus["layer1_corpus"])
    plan = [("F", c, c, None) for c in corpus["faithful"]["cases"]]
    plan += [("A", a["case_id"], a["base_case"], a["temptation"]) for a in corpus["adversarial"]]
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for kind, item_id, base, temptation in plan:
        with tempfile.TemporaryDirectory(prefix="p7-live-v1.1-") as tmp:
            live_run = live_extraction(layer1_corpus, cases[base], protocol["model"], Path(tmp))
        record = _record(kind, item_id, base, temptation, live_run, cases[base])
        records.append(record)
        print(f"{record['run_id']}: http {record['http_status']} {record.get('code') or ''} "
              f"multi {record['cross_participant']['multi_participant']}/{record['cross_participant']['propositions']}", flush=True)
    result = {"schema": "hermeneia.perspective-comparison-live-evaluation/v1", "protocol": protocol,
              "aggregate": extend_aggregate(records, cases, protocol), "records": records}
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return result


def scripted_ceiling() -> dict:
    """The frozen faithful references in the v1.1 wire format, through the production route with the fake provider."""
    _use_v1_1()
    protocol = json.loads(PROTOCOL_PATH.read_text())
    corpus, cases = candidate_lab.load()
    layer1_corpus = live.layer1_lab.load_corpus(ROOT / corpus["layer1_corpus"])
    records = []
    for case_id in corpus["faithful"]["cases"]:
        case = cases[case_id]
        with tempfile.TemporaryDirectory(prefix="p7-ceiling-v1.1-") as tmp:
            workdir = Path(tmp)
            context = candidate_lab._isolated(workdir, corpus, layer1_corpus)
            try:
                study = candidate_lab.Study(layer1_corpus, case, workdir / "s")
                before = lab._logical_digest(study.db)
                wire = to_v1_1_wire(study.wire(candidate_lab.faithful_script(case["reference"], case["expected"]["order"])))
                from test_e10_vertical_slice_api import _CapturingProvider
                _CapturingProvider.render_responses = [wire]
                response = _post(study.client, study.receipt_ids, corpus["extraction_model"])
                view, prompt = _rebuilt_prompt(study.db, study.receipt_ids)
                live_run = {"status": response.status_code, "body": response.get_json(), "labels": study.labels, "view": view,
                            "prompt": prompt, "workspace_unchanged": lab._logical_digest(study.db) == before,
                            "accepted_rows": live._accepted_rows(study.db)}
                records.append(_record("F", case_id, case_id, None, live_run, case))
            finally:
                context.__exit__(None, None, None)
    return extend_aggregate(records, cases, protocol)


# ── Descriptive report (recomputes no score, changes no decision) ─────────────

def diagnose_v1_1(record: dict) -> dict:
    out = record["raw_output"]
    fence = re.compile(r"\A\s*```(?:json)?[ \t]*\n(.*)\n[ \t]*```\s*\Z", re.S).match(out)
    body = fence.group(1) if fence else out
    info = {"length": len(out), "fenced": bool(fence), "proposition_ids_emitted": len(re.findall(r'"id"\s*:\s*"p\d+"', out))}
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        info.update(category="invalid JSON", error=f"{exc.msg} at char {exc.pos}", context=body[max(0, exc.pos - 40):exc.pos + 20])
        return info
    case = live.layer1_lab.load_corpus(ROOT / "tests" / "fixtures" / "perspective_comparison" / "v1" / "cases.json")
    case = next(c for c in case["cases"] if c["case_id"] == record["base_case"])
    n = len(case["compare"])
    violations: dict[str, int] = {}

    def note(key):
        violations[key] = violations.get(key, 0) + 1

    if not isinstance(value, dict) or set(value) != {"propositions", "assumptions"}:
        note("top-level keys")
    propositions = value.get("propositions", []) if isinstance(value, dict) else []
    if isinstance(propositions, list) and len(propositions) > 2 * n:
        note(f"more than {2 * n} propositions ({len(propositions)})")
    for p in propositions if isinstance(propositions, list) else []:
        if not isinstance(p, dict) or set(p) != {"id", "statement", "classifications"}:
            note("proposition keys " + ",".join(sorted(p)) if isinstance(p, dict) else "proposition not an object")
            continue
        for x in p["classifications"]:
            missing = {"participant", "classification", "quote", "relies_on"} - set(x)
            for key in sorted(missing):
                note(f"classification missing '{key}'")
            if x.get("classification") not in V1_1_CLASSIFICATIONS:
                note(f"classification value {x.get('classification')!r}")
            if x.get("participant") not in {f"P{i}" for i in range(1, n + 1)}:
                note(f"participant label {x.get('participant')!r}")
    for a in value.get("assumptions", []) if isinstance(value, dict) else []:
        if not (isinstance(a, dict) and set(a) == {"participant", "quote"} and isinstance(a.get("quote"), str) and a["quote"].strip()):
            note("assumption shape or quote")
    info.update(category="contract violation", violations=violations)
    return info


def comparison_markdown(v11: dict, v1: dict, ceiling: dict) -> str:
    a, b = v1["aggregate"]["metrics"], v11["aggregate"]["metrics"]
    _corpus, cases = candidate_lab.load()
    v1_cross = [cross_participant(r, cases[r["base_case"]]) for r in v1["records"]]
    v1_props = sum(x["propositions"] for x in v1_cross)
    v1_multi = sum(x["multi_participant"] for x in v1_cross)
    v1_applicable = [x for x in v1_cross if x["applicable"]]
    v1_tp = sum(r["score"]["agreement"]["tp"] + r["score"]["disagreement"]["tp"] for r in v1["records"] if r.get("score"))
    v1_relations = sum(x["reference_relations"] for x in v1_cross)

    def pr(x, key):
        return f"{x[key]:.2f}"

    rows = [
        ("Structural refusal rate", f"{a['structural_refusal_rate']:.2f}", f"{b['structural_refusal_rate']:.2f}"),
        ("Multi-participant proposition rate", f"{v1_multi}/{v1_props}",
         f"{b['multi_participant_proposition_rate']['multi_participant']}/{b['multi_participant_proposition_rate']['propositions']}"),
        ("Cross-participant invariant (applicable runs)",
         f"{sum(1 for x in v1_applicable if x['holds'])}/{len(v1_applicable)}",
         f"{b['cross_participant_invariant']['holds']}/{b['cross_participant_invariant']['applicable']}"),
        ("Agreement recall", pr(a["agreement"], "recall"), pr(b["agreement"], "recall")),
        ("Disagreement recall", pr(a["disagreement"], "recall"), pr(b["disagreement"], "recall")),
        ("Relation recall, all runs (decision rule)", f"{v1_tp}/{v1_relations}",
         f"{b['relation_recall_all_runs']['tp']}/{b['relation_recall_all_runs']['reference_relations']}"),
        ("Minority preservation (runs)", f"{a['minority_preservation']['preserved']}/{a['minority_preservation']['runs']}",
         f"{b['minority_preservation']['preserved']}/{b['minority_preservation']['runs']}"),
        ("Stance accuracy", f"{a['stance_accuracy']:.2f}", f"{(b['stance_accuracy'] or 0):.2f}"),
        ("Evidence reliance P / R", f"{pr(a['evidence_reliance'], 'precision')} / {pr(a['evidence_reliance'], 'recall')}",
         f"{pr(b['evidence_reliance'], 'precision')} / {pr(b['evidence_reliance'], 'recall')}"),
        ("Assumption recall", pr(a["assumptions"], "recall"), pr(b["assumptions"], "recall")),
        ("Unknown preservation (runs)", f"{a['unknown_preservation']['preserved']}/{a['unknown_preservation']['runs']}",
         f"{b['unknown_preservation']['preserved']}/{b['unknown_preservation']['runs']}"),
        ("Admitted but wrong", f"{a['outcomes']['ADMITTED_BUT_WRONG_items']}/{a['outcomes']['admitted_semantic_items']}",
         f"{b['outcomes']['ADMITTED_BUT_WRONG_items']}/{b['outcomes']['admitted_semantic_items']}"),
        ("Untraceable content rate", f"{a['untraceable_content_rate']:.2f}", f"{(b['untraceable_content_rate'] or 0):.2f}"),
    ]
    lines = ["# P7 semantic extraction v1.1 — `hermeneia-phi4-mini:latest`", "",
             f"**Decision (frozen rule): {v11['aggregate']['decision_after_phi4_mini']}.** "
             f"Verdict (frozen thresholds): {v11['aggregate']['verdict']}. Governance defects: {len(v11['aggregate']['governance_defects'])}.", "",
             "Same production route, same local model, same sampling as the v1 baseline (`92475b1`, immutable); only the "
             "frozen v1.1 policy differs. Nothing accepted. Scripted output is not counted as model accuracy.", "",
             "| Measure | v1 baseline | v1.1 | v1.1 scripted ceiling |", "| --- | --- | --- | --- |"]
    c = ceiling["metrics"]
    ceil = {
        "Structural refusal rate": f"{c['structural_refusal_rate']:.2f}",
        "Multi-participant proposition rate": f"{c['multi_participant_proposition_rate']['multi_participant']}/{c['multi_participant_proposition_rate']['propositions']}",
        "Cross-participant invariant (applicable runs)": f"{c['cross_participant_invariant']['holds']}/{c['cross_participant_invariant']['applicable']}",
        "Agreement recall": pr(c["agreement"], "recall"), "Disagreement recall": pr(c["disagreement"], "recall"),
        "Relation recall, all runs (decision rule)": f"{c['relation_recall_all_runs']['tp']}/{c['relation_recall_all_runs']['reference_relations']}",
        "Minority preservation (runs)": f"{c['minority_preservation']['preserved']}/{c['minority_preservation']['runs']}",
        "Stance accuracy": f"{c['stance_accuracy']:.2f}",
        "Evidence reliance P / R": f"{pr(c['evidence_reliance'], 'precision')} / {pr(c['evidence_reliance'], 'recall')}",
        "Assumption recall": pr(c["assumptions"], "recall"),
        "Unknown preservation (runs)": f"{c['unknown_preservation']['preserved']}/{c['unknown_preservation']['runs']}",
        "Admitted but wrong": f"{c['outcomes']['ADMITTED_BUT_WRONG_items']}/{c['outcomes']['admitted_semantic_items']}",
        "Untraceable content rate": f"{c['untraceable_content_rate']:.2f}",
    }
    lines += [f"| {name} | {old} | {new} | {ceil[name]} |" for name, old, new in rows]
    lines += ["", "## Per run", "", "| Run | HTTP | Result | Multi-participant propositions | Admitted wrong |", "| --- | --- | --- | --- | --- |"]
    for r in v11["records"]:
        if r["refused"]:
            d = r["diagnosis"]
            detail = d.get("error") or ", ".join(f"{k} ×{v}" for k, v in d.get("violations", {}).items())
            lines.append(f"| {r['run_id']} | {r['http_status']} | refused `{r['code']}` ({d['category']}: {detail}) | — | — |")
        else:
            s = r["score"]
            lines.append(f"| {r['run_id']} | 201 | matched {s['propositions']['matched']}/{s['propositions']['reference']}, stance "
                         f"{s['stance']['agree']}/{s['stance']['total']}, agreement tp {s['agreement']['tp']}, disagreement tp "
                         f"{s['disagreement']['tp']}, untraceable {sum(s['untraceable'].values())} | "
                         f"{r['cross_participant']['multi_participant']}/{r['cross_participant']['propositions']} | "
                         f"{r['counts']['admitted_but_wrong']}/{r['counts']['admitted_semantic_items']} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ceiling-only", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.ceiling_only:
        (args.out / "scripted_ceiling.json").write_text(json.dumps(scripted_ceiling(), indent=2, sort_keys=True) + "\n")
        return 0
    result = json.loads((args.out / "results.json").read_text()) if args.report_only else run(args.out)
    for record in result["records"]:
        if record["refused"]:
            record["diagnosis"] = diagnose_v1_1(record)
    ceiling = json.loads((args.out / "scripted_ceiling.json").read_text())
    (args.out / "summary.md").write_text(comparison_markdown(result, json.loads(V1_RESULTS.read_text()), ceiling))
    (args.out / "diagnostics.json").write_text(json.dumps({r["run_id"]: r["diagnosis"] for r in result["records"] if r["refused"]},
                                                          indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["aggregate"]["decision_after_phi4_mini"], "verdict": result["aggregate"]["verdict"],
                      "defects": result["aggregate"]["governance_defects"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
