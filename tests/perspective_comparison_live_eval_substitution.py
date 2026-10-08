"""P7 model-substitution experiment (#215): one local model, both frozen extraction policies.

Executes the protocol frozen in
live_evaluation_protocol_qwen2.5-7b-instruct.json, which pins the resolved
model digest before any run. Each policy runs in its own process through the
unchanged v1 and v1.1 harnesses and the frozen scorer, on the same production
route, loopback only, with nothing accepted. The installed model's digest is
verified against the frozen one before and after each policy run. This is a
model substitution (architecture, training and model-file defaults change
with the parameter count), not a pure model-size experiment.

    python tests/perspective_comparison_live_eval_substitution.py --policy 1.0.0 --out research/perspective_comparison_live/qwen2.5-7b-instruct
    python tests/perspective_comparison_live_eval_substitution.py --policy 1.1.0 --out research/perspective_comparison_live/qwen2.5-7b-instruct
    python tests/perspective_comparison_live_eval_substitution.py --report --out research/perspective_comparison_live/qwen2.5-7b-instruct
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
for entry in (str(ROOT), str(TESTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import perspective_comparison_candidate_lab as candidate_lab  # noqa: E402
import perspective_comparison_live_eval as live  # noqa: E402  (v1 harness, unchanged)
import perspective_comparison_live_eval_v1_1 as v11  # noqa: E402  (v1.1 harness, unchanged)

PROTOCOL_PATH = TESTS / "fixtures" / "perspective_comparison" / "v1" / "live_evaluation_protocol_qwen2.5-7b-instruct.json"
LIVE = ROOT / "research" / "perspective_comparison_live"


def _field(item, name):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def installed_identity(model: str) -> dict:
    """The installed model's resolved identity, read from the local Ollama runtime over loopback."""
    import ollama

    with live.loopback_only():
        client = ollama.Client(host="http://127.0.0.1:11434")
        listed = _field(client.list(), "models") or []
        entry = next((m for m in listed if (_field(m, "model") or _field(m, "name")) == model), None)
        if entry is None:
            raise RuntimeError(f"{model} is not installed")
        shown = client.show(model)
    details = _field(entry, "details")
    return {"model": model, "digest": _field(entry, "digest"), "size_bytes": _field(entry, "size"),
            "family": _field(details, "family"), "parameter_size": _field(details, "parameter_size"),
            "quantization_level": _field(details, "quantization_level"), "format": _field(details, "format"),
            "modelfile_parameters": _field(shown, "parameters")}


def verify_identity(protocol: dict) -> dict:
    identity = installed_identity(protocol["model"])
    frozen = protocol["model_identity"]
    if identity["digest"] != frozen["digest"]:
        raise RuntimeError(f"installed digest {identity['digest']} differs from the frozen {frozen['digest']}; refusing to run")
    return identity


def run_policy(policy: str, out: Path) -> dict:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    before = verify_identity(protocol)
    extraction = live.live_extraction
    if policy == "1.1.0":
        v11._use_v1_1()
        extraction = v11.live_extraction
    elif policy != "1.0.0":
        raise ValueError("unsupported policy")
    corpus, cases = candidate_lab.load()
    layer1_corpus = live.layer1_lab.load_corpus(ROOT / corpus["layer1_corpus"])
    plan = [("F", c, c, None) for c in corpus["faithful"]["cases"]]
    plan += [("A", a["case_id"], a["base_case"], a["temptation"]) for a in corpus["adversarial"]]
    target = out / f"policy-{policy}"
    target.mkdir(parents=True, exist_ok=True)
    partial = target / "records.partial.jsonl"
    partial.unlink(missing_ok=True)
    records = []
    for kind, item_id, base, temptation in plan:
        with tempfile.TemporaryDirectory(prefix=f"p7-substitution-{policy}-") as tmp:
            live_run = extraction(layer1_corpus, cases[base], protocol["model"], Path(tmp))
        record = v11._record(kind, item_id, base, temptation, live_run, cases[base])
        records.append(record)
        with partial.open("a") as handle:  # no live output is lost if post-processing fails
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        print(f"{policy} {record['run_id']}: http {record['http_status']} {record.get('code') or ''} "
              f"multi {record['cross_participant']['multi_participant']}/{record['cross_participant']['propositions']}", flush=True)
    after = verify_identity(protocol)
    result = {"schema": "hermeneia.perspective-comparison-live-evaluation/v1", "protocol": protocol, "policy_version": policy,
              "model_identity_before": before, "model_identity_after": after,
              "aggregate": v11.extend_aggregate(records, cases, protocol), "records": records}
    for record in result["records"]:
        if record["refused"]:
            try:  # descriptive only; never allowed to lose the run
                record["diagnosis"] = (v11.diagnose_v1_1(record) if policy == "1.1.0" else
                                       __import__("perspective_comparison_live_report").diagnose(record))
            except Exception as exc:  # noqa: BLE001
                record["diagnosis"] = {"category": "diagnosis unavailable", "error": type(exc).__name__}
    (target / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    partial.unlink()
    return result


def _metrics(result: dict, cases: dict, protocol: dict) -> dict:
    """Frozen metrics plus the cross-participant metric, recomputed from records for configurations run before it existed."""
    records = result["records"]
    for record in records:
        record.setdefault("cross_participant", v11.cross_participant(record, cases[record["base_case"]]))
    return v11.extend_aggregate(records, cases, protocol)


def report(out: Path) -> str:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    _corpus, cases = candidate_lab.load()
    configs = [
        ("phi4-mini · v1", json.loads((LIVE / "v1" / "results.json").read_text())),
        ("phi4-mini · v1.1", json.loads((LIVE / "v1.1" / "results.json").read_text())),
        ("qwen2.5-7b · v1", json.loads((out / "policy-1.0.0" / "results.json").read_text())),
        ("qwen2.5-7b · v1.1", json.loads((out / "policy-1.1.0" / "results.json").read_text())),
    ]
    aggregates = [(name, _metrics(result, cases, protocol)) for name, result in configs]

    def pr(x):
        return f"{x['precision']:.2f} / {x['recall']:.2f}"

    def frac(x, a, b):
        return f"{x[a]}/{x[b]}"

    measures = [
        ("Structural refusal rate", lambda m: f"{m['structural_refusal_rate']:.2f} ({m['outcomes']['REFUSED_runs']}/{m['live_runs']})"),
        ("Multi-participant proposition rate", lambda m: frac(m["multi_participant_proposition_rate"], "multi_participant", "propositions")),
        ("Cross-participant invariant", lambda m: frac(m["cross_participant_invariant"], "holds", "applicable")),
        ("Relation recall, all runs", lambda m: frac(m["relation_recall_all_runs"], "tp", "reference_relations")),
        ("Agreement P / R", lambda m: pr(m["agreement"])),
        ("Disagreement P / R", lambda m: pr(m["disagreement"])),
        ("Minority preservation", lambda m: frac(m["minority_preservation"], "preserved", "runs")),
        ("Unknown preservation", lambda m: frac(m["unknown_preservation"], "preserved", "runs")),
        ("Stance accuracy", lambda m: "n/a" if m["stance_accuracy"] is None else f"{m['stance_accuracy']:.2f}"),
        ("Evidence reliance P / R", lambda m: pr(m["evidence_reliance"])),
        ("Assumption P / R", lambda m: pr(m["assumptions"])),
        ("Claim attribution accuracy", lambda m: "n/a" if m["claim_attribution_accuracy"] is None else f"{m['claim_attribution_accuracy']:.2f}"),
        ("Untraceable content rate", lambda m: "n/a" if m["untraceable_content_rate"] is None else f"{m['untraceable_content_rate']:.2f}"),
        ("Downgraded to unknown (items)", lambda m: str(m["outcomes"]["DOWNGRADED_TO_UNKNOWN_items"])),
        ("Admitted but wrong", lambda m: f"{m['outcomes']['ADMITTED_BUT_WRONG_items']}/{m['outcomes']['admitted_semantic_items']}"),
        ("Paraphrase-as-disagreement / silent-minority errors", lambda m: f"{m['paraphrase_as_disagreement_errors']} / {m['silent_minority_errors']}"),
    ]
    identity = protocol["model_identity"]
    lines = ["# P7 model-substitution experiment — `qwen2.5:7b-instruct` under frozen policies v1 and v1.1", "",
             "A model substitution, not a pure model-size experiment: architecture, training and model-file defaults change with "
             "the parameter count, and the production Ollama path sets no generation options. Fixed: frozen corpus and "
             "references, v1 and v1.1 policies, production route, governance and parser, scoring, stop criteria, loopback-only "
             "execution, no acceptance.", "",
             f"Model: `{identity['model']}` · digest `{identity['digest']}` · {identity['parameter_size']} · "
             f"{identity['quantization_level']} · family {identity['family']} · {identity['size_bytes']} bytes.", "",
             "| Measure | " + " | ".join(name for name, _ in aggregates) + " |", "| --- |" + " --- |" * len(aggregates)]
    for label, fn in measures:
        lines.append(f"| {label} | " + " | ".join(fn(m["metrics"]) for _, m in aggregates) + " |")
    lines.append("| Decision (frozen rule) | " + " | ".join(m["decision_after_phi4_mini"] for _, m in aggregates) + " |")
    lines.append("| Verdict (frozen thresholds) | " + " | ".join(m["verdict"] for _, m in aggregates) + " |")
    lines.append("| Governance defects | " + " | ".join(str(len(m["governance_defects"])) for _, m in aggregates) + " |")
    lines += ["", "`material_change` under the frozen rule means extraction capability is demonstrated for that model and "
              "configuration only; `model_limited` means the cross-participant invariant or relation recall threshold was not met."]
    for name, result in configs[2:]:
        lines += ["", f"## {name} — per run", "", "| Run | HTTP | Result | Multi-participant | Admitted wrong |", "| --- | --- | --- | --- | --- |"]
        for r in result["records"]:
            if r["refused"]:
                d = r.get("diagnosis") or {}
                detail = d.get("error") or ", ".join(f"{k} ×{v}" for k, v in (d.get("violations") or {}).items())
                lines.append(f"| {r['run_id']} | {r['http_status']} | refused `{r['code']}` ({d.get('category', '')}: {detail}) | — | — |")
            else:
                s = r["score"]
                lines.append(f"| {r['run_id']} | 201 | matched {s['propositions']['matched']}/{s['propositions']['reference']}, stance "
                             f"{s['stance']['agree']}/{s['stance']['total']}, agreement tp {s['agreement']['tp']}/fp {s['agreement']['fp']}, "
                             f"disagreement tp {s['disagreement']['tp']}/fp {s['disagreement']['fp']}, untraceable {sum(s['untraceable'].values())} | "
                             f"{r['cross_participant']['multi_participant']}/{r['cross_participant']['propositions']} | "
                             f"{r['counts']['admitted_but_wrong']}/{r['counts']['admitted_semantic_items']} |")
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text)
    (out / "comparison.json").write_text(json.dumps({name: m for name, m in aggregates}, indent=2, sort_keys=True) + "\n")
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--policy", choices=["1.0.0", "1.1.0"])
    group.add_argument("--report", action="store_true")
    group.add_argument("--identity", action="store_true", help="print the installed identity of the protocol model")
    args = parser.parse_args(argv)
    if args.identity:
        print(json.dumps(installed_identity(json.loads(PROTOCOL_PATH.read_text())["model"]), indent=2, sort_keys=True))
        return 0
    if args.report:
        report(args.out)
        return 0
    result = run_policy(args.policy, args.out)
    print(json.dumps({"policy": args.policy, "decision": result["aggregate"]["decision_after_phi4_mini"],
                      "verdict": result["aggregate"]["verdict"], "defects": result["aggregate"]["governance_defects"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
