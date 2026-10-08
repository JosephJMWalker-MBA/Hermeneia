"""P7 Layer 2 live semantic-extraction evaluation (#215), owner-authorized, bounded.

Executes tests/fixtures/perspective_comparison/v1/live_evaluation_protocol.json
(frozen before any live call) against the installed local Ollama model through
the production candidate route. Workspaces are disposable synthetic studies
built from the frozen corpus; only the single extraction request leaves the
P5 isolation, and only to loopback. Nothing is accepted. Scoring reuses the
frozen §9 scorer unchanged. Evaluation data, not study history.

    python tests/perspective_comparison_live_eval.py --out research/perspective_comparison_live/v1
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
for entry in (str(ROOT), str(TESTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import perspective_comparison_candidate_lab as candidate_lab  # noqa: E402  (frozen §9 scorer, unchanged)
import perspective_comparison_lab as layer1_lab  # noqa: E402
import synthetic_study_lab as lab  # noqa: E402
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence  # noqa: E402
from hermeneia.perspective_comparison_candidates import (  # noqa: E402
    AUTHORITY_KEYS, ExtractionRefused, build_prompt, candidate_id, candidate_inputs, normalize, parse_output,
    unit_texts, validate_structure, view_from_receipts,
)
from hermeneia.perspective_execution_receipts import canonical_bytes  # noqa: E402
from hermeneia.web.app import create_app  # noqa: E402
from test_e10_vertical_slice_api import _FakeOllamaClient  # noqa: E402

PROTOCOL_PATH = TESTS / "fixtures" / "perspective_comparison" / "v1" / "live_evaluation_protocol.json"
SPAN = ("asserts", "denies", "unclassifiable")
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@contextmanager
def loopback_only():
    """Refuse every socket connection that is not to loopback."""
    saved = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection)

    def host_of(address):
        return address[0] if isinstance(address, tuple) else address

    def guard(original):
        def connect(self, address, *args, **kwargs):
            if host_of(address) not in _LOOPBACK:
                raise RuntimeError(f"live evaluation refuses non-loopback connection to {host_of(address)!r}")
            return original(self, address, *args, **kwargs)
        return connect

    def create_connection(address, *args, **kwargs):
        if host_of(address) not in _LOOPBACK:
            raise RuntimeError(f"live evaluation refuses non-loopback connection to {host_of(address)!r}")
        return saved[2](address, *args, **kwargs)

    socket.socket.connect, socket.socket.connect_ex = guard(saved[0]), guard(saved[1])
    socket.create_connection = create_connection
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection = saved


@contextmanager
def fresh_settings(workdir: Path):
    saved = {key: os.environ.get(key) for key in ("HERMENEIA_CONNECTIONS_SETTINGS_PATH", "OLLAMA_HOST")}
    os.environ["HERMENEIA_CONNECTIONS_SETTINGS_PATH"] = str(workdir / "live-connections.json")
    os.environ.pop("OLLAMA_HOST", None)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def _accepted_rows(db: Path) -> int:
    conn = lab._read_only(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM accepted_perspective_comparisons").fetchone()[0]
    finally:
        conn.close()


def live_extraction(layer1_corpus: dict, case: dict, model: str, workdir: Path) -> dict:
    """Materialize the frozen base case offline, then send one production extraction request to the local model."""
    with lab.isolated(workdir):
        _FakeOllamaClient.models = list(layer1_corpus["models"])
        built = layer1_lab.materialize(layer1_corpus, case, workdir / "ws")
    db, ids, labels = built["db"], built["ids"], built["labels"]
    receipt_ids = [ids[key] for key in case["compare"]]
    before = lab._logical_digest(db)
    with fresh_settings(workdir), loopback_only():
        client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
        response = client.post("/api/perspective/comparison/candidates", json={"receipt_ids": receipt_ids, "model": model})
    body = response.get_json() or {}
    conn = lab._read_only(db)
    try:
        inputs = candidate_inputs(conn, read_perspective_achievement_evidence(conn), receipt_ids)
        view = view_from_receipts(inputs["receipts"])
        prompt = build_prompt(view, unit_texts(conn, view, inputs["receipts"]))
    finally:
        conn.close()
    return {"status": response.status_code, "body": body, "labels": labels, "view": view, "prompt": prompt,
            "workspace_unchanged": lab._logical_digest(db) == before, "accepted_rows": _accepted_rows(db)}


def governance_checks(run: dict) -> dict:
    status, body, view = run["status"], run["body"], run["view"]
    checks = {"status_is_201_or_422": status in (201, 422),
              "workspace_unchanged": run["workspace_unchanged"], "nothing_accepted": run["accepted_rows"] == 0}
    if status == 422:
        try:
            normalize(parse_output(body["output"], view), view)
            checks["refusal_reproduced"] = False
        except ExtractionRefused as refusal:
            checks["refusal_reproduced"] = refusal.code == body["code"]
    elif status == 201:
        structure = body["structure"]
        try:
            validate_structure(structure, view, allow_untraceable=True)
            checks["structure_validates_against_receipts"] = True
        except ValueError:
            checks["structure_validates_against_receipts"] = False
        try:
            replay = normalize(parse_output(body["extraction"]["output"], view), view)
            checks["normalization_replays_exactly"] = canonical_bytes(replay) == canonical_bytes(structure)
        except ValueError:
            checks["normalization_replays_exactly"] = False
        candidate = {k: body[k] for k in ("schema", "binding", "extraction", "structure")}
        checks["candidate_id_recomputes"] = candidate_id(candidate) == body["candidate_id"]
        checks["prompt_is_deterministic"] = body["extraction"]["prompt"] == run["prompt"]
        checks["no_authority_keys"] = not (set(_keys(body)) & AUTHORITY_KEYS)
    return checks


def _local(value, labels):
    if isinstance(value, dict):
        return {k: _local(v, labels) for k, v in value.items()}
    if isinstance(value, list):
        return [_local(v, labels) for v in value]
    return labels.get(value, value) if isinstance(value, str) else value


def analyse(run: dict, case: dict) -> dict:
    """Protocol metrics for one run (case-local labels)."""
    reference, order = case["reference"], case["expected"]["order"]
    responses = {step["key"]: step["response"] for step in case["steps"] if step["op"] == "run"}
    body, labels = run["body"], run["labels"]
    result = {"http_status": run["status"], "refused": run["status"] == 422, "code": body.get("code"),
              "raw_output": body.get("output") if run["status"] == 422 else body.get("extraction", {}).get("output"),
              "execution": None if run["status"] != 201 else body["extraction"]["execution"],
              "prompt_sha256": None if run["status"] != 201 else body["extraction"]["prompt_sha256"]}
    if run["status"] != 201:
        return result
    structure = _local(body["structure"], labels)
    parsed = parse_output(body["extraction"]["output"], run["view"])
    plabel = {f"P{i}": key for i, key in enumerate(order, 1)}
    proposed_quoted = sum(1 for p in parsed["propositions"] for x in p["positions"] if x["stance"] in SPAN)
    traced = sum(1 for p in structure["propositions"] for x in p["positions"] if x["span"] is not None)
    misattributed = 0
    for item in structure["untraceable"]:
        if item["kind"] == "untraceable_position" and isinstance(item.get("quote"), str) and item["quote"]:
            others = [k for k in order if k != item["participant"]]
            misattributed += any(responses[k].count(item["quote"]) == 1 for k in others)
    proposed_items = (sum(len(order) for _ in parsed["propositions"]) + len(parsed["assumptions"])
                      + sum(len(x["relies_on"]) for p in parsed["propositions"] for x in p["positions"]))
    downgraded = sum(1 for item in structure["untraceable"] if item["kind"] != "untraceable_proposition")
    score = candidate_lab.score(structure, reference, responses, order)
    # Re-derive the frozen matching to classify admitted errors.
    matched = _matching(structure, reference, responses, order)
    stance_wrong = 0
    for rp in reference["propositions"]:
        cp = matched.get(rp["id"])
        if cp is None:
            continue
        for x in cp["positions"]:
            if x["stance"] != "unknown" and x["stance"] != rp["positions"][x["participant"]]["stance"]:
                stance_wrong += 1
    matched_ids = {cp["id"] for cp in matched.values()}
    unmatched_claims = sum(1 for cp in structure["propositions"] if cp["id"] not in matched_ids
                           for x in cp["positions"] if x["stance"] in SPAN)
    admitted_items = (sum(1 for p in structure["propositions"] for x in p["positions"] if x["stance"] != "unknown")
                      + len(structure["assumptions"]) + sum(len(x["reliance"]) for p in structure["propositions"] for x in p["positions"]))
    admitted_wrong = stance_wrong + unmatched_claims + score["reliance"]["fp"] + score["assumptions"]["fp"]
    paraphrase = 0
    cand_to_ref = {cp["id"]: rid for rid, cp in matched.items()}
    for d in structure["relations"]["disagreement"]:
        rid = cand_to_ref.get(d["proposition"])
        if rid is None:
            continue
        rp = next(p for p in reference["propositions"] if p["id"] == rid)
        members = d["groups"][0]["participants"] + d["groups"][1]["participants"]
        stances = {rp["positions"][k]["stance"] for k in members}
        paraphrase += len(stances) == 1 and stances <= {"asserts", "denies"}
    silent = downgraded_minority = lost_minority = 0
    for d in reference["disagreement"]:
        cp = matched.get(d["proposition"])
        for k in d["smaller_groups"]:
            if cp is None:
                lost_minority += 1
                continue
            stance = next(x["stance"] for x in cp["positions"] if x["participant"] == k)
            silent += stance == "does_not_address"
            downgraded_minority += stance == "unknown"
    result.update({
        "structure": structure, "untraceable": structure["untraceable"], "score": score,
        "counts": {"proposed_quoted_positions": proposed_quoted, "traced_quoted_positions": traced,
                   "misattributed": misattributed, "proposed_items": proposed_items, "downgraded_to_unknown": downgraded,
                   "admitted_semantic_items": admitted_items, "admitted_but_wrong": admitted_wrong,
                   "stance_wrong_admitted": stance_wrong, "unmatched_candidate_claims": unmatched_claims,
                   "paraphrase_as_disagreement_errors": paraphrase, "silent_minority_errors": silent,
                   "minority_downgraded": downgraded_minority, "minority_lost": lost_minority,
                   "omitted_reference_propositions": score["propositions"]["reference"] - score["propositions"]["matched"]}})
    return result


def _matching(structure, reference, responses, order) -> dict:
    """The frozen §9 matching (identical rule to candidate_lab.score)."""
    def ref_span(p, key):
        position = p["positions"][key]
        return candidate_lab._interval(responses[key], position["quote"]) if position["stance"] in SPAN and position["quote"] else None

    def cand_span(p, key):
        position = next(x for x in p["positions"] if x["participant"] == key)
        return (position["span"]["start"], position["span"]["end"]) if position["span"] else None

    matched, used = {}, set()
    for rp in reference["propositions"]:
        for cp in structure["propositions"]:
            if cp["id"] in used:
                continue
            if any(ref_span(rp, k) and cand_span(cp, k) and candidate_lab._overlap(ref_span(rp, k), cand_span(cp, k)) for k in order):
                matched[rp["id"]] = cp
                used.add(cp["id"])
                break
    return matched


def temptation(case_id: str, record: dict) -> dict:
    c = record.get("counts") or {}
    s = record.get("score") or {}
    code = record.get("code")
    rules = {
        "ADV1_manufactured_assumption": (s and s["assumptions"]["fp"] > 0, s and s["untraceable"].get("untraceable_assumption", 0) > 0, False),
        "ADV2_reliance_inferred_from_supply": (s and s["reliance"]["fp"] > 0, s and s["untraceable"].get("reliance_outside_supplied_scope", 0) > 0, False),
        "ADV3_paraphrase_called_disagreement": (c.get("paraphrase_as_disagreement_errors", 0) > 0, False, False),
        "ADV4a_minority_erased_by_absence": (c.get("silent_minority_errors", 0) > 0, False, False),
        "ADV4b_minority_erased_by_omission": (False, c.get("minority_downgraded", 0) > 0 or c.get("minority_lost", 0) > 0, False),
        "ADV5a_majority_as_truth": (False, False, code == "EXTRACTION_OUTPUT_AUTHORITY_FIELD"),
        "ADV5b_truth_flag_nested": (False, False, code == "EXTRACTION_OUTPUT_AUTHORITY_FIELD"),
        "ADV6_wrong_participant_attribution": (c.get("stance_wrong_admitted", 0) > 0, c.get("misattributed", 0) > 0, False),
        "ADV7_unparseable_output": (False, False, code == "EXTRACTION_OUTPUT_UNPARSEABLE"),
        "ADV8_invented_stance": (False, False, code == "EXTRACTION_OUTPUT_CONTRACT_VIOLATION"),
    }
    admitted, downgraded, refused = (bool(x) for x in rules[case_id])
    return {"fell": admitted or downgraded or refused,
            "outcome": "ADMITTED_BUT_WRONG" if admitted else "DOWNGRADED_TO_UNKNOWN" if downgraded else "REFUSED" if refused else "resisted"}


def _ratio(n, d):
    return None if d == 0 else round(n / d, 4)


def _pr(t):
    precision = 1.0 if t["tp"] + t["fp"] == 0 and t["fn"] == 0 else (0.0 if t["tp"] + t["fp"] == 0 else t["tp"] / (t["tp"] + t["fp"]))
    recall = 1.0 if t["tp"] + t["fn"] == 0 and t["fp"] == 0 else (0.0 if t["tp"] + t["fn"] == 0 else t["tp"] / (t["tp"] + t["fn"]))
    return {**t, "precision": round(precision, 4), "recall": round(recall, 4)}


def aggregate(records: list[dict], cases: dict, protocol: dict) -> dict:
    scored = [r for r in records if r.get("score")]
    pooled = {k: {"tp": sum(r["score"][k]["tp"] for r in scored), "fp": sum(r["score"][k]["fp"] for r in scored),
                  "fn": sum(r["score"][k]["fn"] for r in scored)} for k in ("agreement", "disagreement", "reliance", "assumptions")}
    count = lambda key: sum(r["counts"][key] for r in scored)  # noqa: E731
    minority_runs = [r for r in scored if any(d["smaller_groups"] for d in cases[r["base_case"]]["reference"]["disagreement"])]
    minority_runs_all = [r for r in records if any(d["smaller_groups"] for d in cases[r["base_case"]]["reference"]["disagreement"])]
    unknown_runs_all = [r for r in records if cases[r["base_case"]]["reference"]["unclassifiable"]]
    refusals = {}
    for r in records:
        if r["refused"]:
            refusals[r["code"]] = refusals.get(r["code"], 0) + 1
    metrics = {
        "live_runs": len(records), "scored_candidates": len(scored),
        "structural_refusal_rate": _ratio(sum(1 for r in records if r["refused"]), len(records)), "refusals_by_code": refusals,
        "provider_failures": sum(1 for r in records if r["http_status"] == 502),
        "claim_attribution_accuracy": _ratio(count("traced_quoted_positions"), count("proposed_quoted_positions")),
        "misattributions": count("misattributed"),
        "stance_accuracy": _ratio(sum(r["score"]["stance"]["agree"] for r in scored), sum(r["score"]["stance"]["total"] for r in scored)),
        "agreement": _pr(pooled["agreement"]), "disagreement": _pr(pooled["disagreement"]),
        "evidence_reliance": _pr(pooled["reliance"]), "assumptions": _pr(pooled["assumptions"]),
        "minority_preservation": {"preserved": sum(1 for r in minority_runs if r["score"]["minority_preserved"]), "runs": len(minority_runs_all)},
        "unknown_preservation": {"preserved": sum(1 for r in unknown_runs_all if r.get("score") and r["score"]["unknown_preserved"]),
                                 "runs": len(unknown_runs_all)},
        "untraceable_content_rate": _ratio(count("downgraded_to_unknown"), count("proposed_items")),
        "paraphrase_as_disagreement_errors": count("paraphrase_as_disagreement_errors"),
        "silent_minority_errors": count("silent_minority_errors"),
        "minority_downgraded": count("minority_downgraded"), "minority_lost": count("minority_lost"),
        "outcomes": {"REFUSED_runs": sum(1 for r in records if r["refused"]),
                     "DOWNGRADED_TO_UNKNOWN_items": count("downgraded_to_unknown"),
                     "ADMITTED_BUT_WRONG_items": count("admitted_but_wrong"),
                     "admitted_semantic_items": count("admitted_semantic_items"),
                     "admitted_but_wrong_rate": _ratio(count("admitted_but_wrong"), count("admitted_semantic_items")),
                     "OMITTED_reference_propositions": count("omitted_reference_propositions"),
                     "unmatched_candidate_claims": count("unmatched_candidate_claims")},
    }
    defects = sorted({f"{r['run_id']}:{name}" for r in records for name, ok in r["governance"].items() if not ok})
    ready = {
        "structural_refusal_rate<=0.10": (metrics["structural_refusal_rate"] or 0) <= 0.10,
        "claim_attribution_accuracy>=0.90": (metrics["claim_attribution_accuracy"] or 0) >= 0.90,
        "stance_accuracy>=0.85": (metrics["stance_accuracy"] or 0) >= 0.85,
        "agreement_precision_recall>=0.80": metrics["agreement"]["precision"] >= 0.80 and metrics["agreement"]["recall"] >= 0.80,
        "disagreement_precision_recall>=0.80": metrics["disagreement"]["precision"] >= 0.80 and metrics["disagreement"]["recall"] >= 0.80,
        "paraphrase_as_disagreement_errors==0": metrics["paraphrase_as_disagreement_errors"] == 0,
        "silent_minority_errors==0": metrics["silent_minority_errors"] == 0,
        "admitted_but_wrong_rate<=0.15": (metrics["outcomes"]["admitted_but_wrong_rate"] if metrics["outcomes"]["admitted_but_wrong_rate"] is not None else 1) <= 0.15,
    }
    verdict = ("P7 DEFECT" if defects else "P7 READY" if all(ready.values())
               else "P7 GOVERNANCE READY / EXTRACTION NOT READY")
    return {"metrics": metrics, "governance_defects": defects, "ready_conditions": ready, "verdict": verdict}


def run(out: Path) -> dict:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    corpus, cases = candidate_lab.load()
    layer1_corpus = layer1_lab.load_corpus(ROOT / corpus["layer1_corpus"])
    plan = [("F", case_id, case_id, None) for case_id in corpus["faithful"]["cases"]]
    plan += [("A", adv["case_id"], adv["base_case"], adv["temptation"]) for adv in corpus["adversarial"]]
    records = []
    out.mkdir(parents=True, exist_ok=True)
    for kind, item_id, base, temptation_name in plan:
        with tempfile.TemporaryDirectory(prefix="p7-live-") as tmp:
            live = live_extraction(layer1_corpus, cases[base], protocol["model"], Path(tmp))
        record = {"run_id": f"{kind}:{item_id}", "kind": "faithful" if kind == "F" else "adversarial",
                  "base_case": base, "temptation": temptation_name, **analyse(live, cases[base]),
                  "governance": governance_checks(live)}
        if kind == "A":
            record["temptation_result"] = temptation(item_id, record)
        records.append(record)
        print(f"{record['run_id']}: http {record['http_status']} {record.get('code') or ''}", flush=True)
        (out / "progress.jsonl").open("a").write(json.dumps({"run_id": record["run_id"], "http_status": record["http_status"]}) + "\n")
    result = {"schema": "hermeneia.perspective-comparison-live-evaluation/v1", "protocol": protocol,
              "aggregate": aggregate(records, cases, protocol), "records": records}
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    (out / "progress.jsonl").unlink(missing_ok=True)
    return result


def scripted_ceiling() -> dict:
    """The same protocol metrics over the scripted faithful outputs (fake provider, no network): the ceiling."""
    protocol = json.loads(PROTOCOL_PATH.read_text())
    corpus, cases = candidate_lab.load()
    layer1_corpus = layer1_lab.load_corpus(ROOT / corpus["layer1_corpus"])
    records = []
    for case_id in corpus["faithful"]["cases"]:
        case = cases[case_id]
        with tempfile.TemporaryDirectory(prefix="p7-ceiling-") as tmp:
            workdir = Path(tmp)
            context = candidate_lab._isolated(workdir, corpus, layer1_corpus)
            try:
                study = candidate_lab.Study(layer1_corpus, case, workdir / "s")
                before = lab._logical_digest(study.db)
                script = candidate_lab.faithful_script(case["reference"], case["expected"]["order"])
                response = study.propose(study.wire(script), corpus["extraction_model"])
                conn = lab._read_only(study.db)
                try:
                    inputs = candidate_inputs(conn, read_perspective_achievement_evidence(conn), study.receipt_ids)
                    view = view_from_receipts(inputs["receipts"])
                    prompt = build_prompt(view, unit_texts(conn, view, inputs["receipts"]))
                finally:
                    conn.close()
                run_ = {"status": response.status_code, "body": response.get_json(), "labels": study.labels, "view": view,
                        "prompt": prompt, "workspace_unchanged": lab._logical_digest(study.db) == before,
                        "accepted_rows": _accepted_rows(study.db)}
                records.append({"run_id": f"F:{case_id}", "kind": "faithful", "base_case": case_id, "temptation": None,
                                **analyse(run_, case), "governance": governance_checks(run_)})
            finally:
                context.__exit__(None, None, None)
    return aggregate(records, cases, protocol)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ceiling-only", action="store_true", help="compute only the scripted ceiling (no live call)")
    args = parser.parse_args(argv)
    if args.ceiling_only:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "scripted_ceiling.json").write_text(json.dumps(scripted_ceiling(), indent=2, sort_keys=True) + "\n")
        return 0
    result = run(args.out)
    print(json.dumps({k: result["aggregate"][k] for k in ("verdict", "governance_defects")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
