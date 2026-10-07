"""P6 Deterministic Companion Coach evaluation (#215): the frozen P5 trajectories plus negatives.

Each scenario is materialized with the P5 laboratory (production write
boundaries, disposable synthetic workspaces, no network), decided by the
production Lineage → Capability Registry → Guided Study Cycle chain, and then
coached by the production ``hermeneia.companion_coach.coach``. The frozen
expectations are compared afterwards and never reach production.

    python3 tests/companion_coach_lab.py --write research/companion_coach/v1
    python3 tests/companion_coach_lab.py --check research/companion_coach/v1
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
import tempfile

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import synthetic_study_lab as lab  # noqa: E402
from hermeneia.companion_coach import POLICY_VERSION, SCHEMA, coach  # noqa: E402

EXPECTATIONS = TESTS / "fixtures" / "companion_coach" / "v1" / "expectations.json"
RESULT_SCHEMA = "hermeneia.companion-coach-lab-results/v1"
_FACTS = {"governing_question_present", "saved_reader_marks", "grouped_marks", "canonical_observations", "inquiry_questions",
          "saved_frames", "selected_frame", "retained_perspective_executions", "interpretation_material", "blueprints"}
_UNCERTAINTY = {"ABSENCE_NOT_PROOF", "HISTORY_NOT_RECORDED", "COVERAGE_INCOMPLETE", "RECORDS_OMITTED", "AUTHORSHIP_UNKNOWN"}
_WITHHELD = {"PREREQUISITE_MISSING", "COVERAGE_UNSUPPORTED", "LATER_IN_CYCLE", "NOT_RECONSTRUCTED_BY_RESUMPTION",
             "ALREADY_CURRENT_MATERIAL", "NARROW_HISTORY_RETAINED"}


def load_expectations(path: Path = EXPECTATIONS) -> dict:
    contract = json.loads(path.read_text())
    if contract.get("schema") != "hermeneia.companion-coach-expectations/v1" or contract.get("policy_version") != POLICY_VERSION:
        raise ValueError("expectations do not match the production coach policy; re-freeze deliberately")
    return contract


def scenario_trajectory(scenario: dict) -> dict:
    """P5 trajectories are used unchanged; P6 negatives carry their own operations."""
    if scenario["source"] == "p5":
        return next(t for t in lab.load_trajectories() if t["trajectory_id"] == scenario["scenario_id"])
    return {"trajectory_id": scenario["scenario_id"], "documents": scenario["documents"], "operations": scenario["operations"],
            "current_state": scenario["current_state"], "fixture_class": scenario["fixture_class"]}


def validate_result(result: dict) -> list[str]:
    """Structural check of hermeneia.companion-coach/v1 (mirrors coach-result.schema.json)."""
    problems = []
    fields = {"schema", "policy_version", "inputs", "decision", "quiet_reason", "suggestion", "noticed", "why_now",
              "next_action", "uncertainty", "blocked", "withheld", "not_history"}
    if set(result) != fields:
        problems.append(f"fields {sorted(set(result) ^ fields)}")
    if result.get("schema") != SCHEMA or result.get("policy_version") != POLICY_VERSION:
        problems.append("schema/policy")
    if result.get("decision") not in ("suggest", "remain_quiet"):
        problems.append("decision")
    if (result["decision"] == "suggest") != (result["suggestion"] is not None) or (result["decision"] == "suggest") == (result["quiet_reason"] is not None):
        problems.append("decision/suggestion/quiet_reason inconsistent")
    if result["suggestion"] and (result["suggestion"]["readiness"]["availability"] != "available" or result["suggestion"]["readiness"]["prerequisites_missing"]):
        problems.append("suggestion is not available")
    if any(f["fact"] not in _FACTS or f["count"] < 1 or not f["evidence"] for f in result["noticed"]):
        problems.append("noticed")
    if any(u["code"] not in _UNCERTAINTY for u in result["uncertainty"]) or any(w["code"] not in _WITHHELD for w in result["withheld"]):
        problems.append("codes")
    return problems


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in ("evidence", "inputs"):
                yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def normalized(result: dict) -> dict:
    """Decision content without evidence timestamps/IDs, for cross-workspace comparison."""
    value = deepcopy(result)
    for fact in value["noticed"]:
        fact.pop("evidence")
    return value


def _fact_counts(result: dict) -> dict:
    counts: dict = {}
    for fact in result["noticed"]:
        if fact["fact"] == "interpretation_material" or fact["fact"] == "retained_perspective_executions":
            counts.setdefault(fact["fact"], {})[fact["authorship"]] = fact["count"]
        else:
            counts[fact["fact"]] = fact["count"]
    return counts


def evaluate_scenario(scenario: dict, rules: dict, workdir: Path) -> dict:
    trajectory = scenario_trajectory(scenario)
    expected = scenario["expected"]
    current_state = trajectory["current_state"]
    with lab.isolated(workdir):
        db = lab.materialize(trajectory, workdir / "primary")
        before = lab._logical_digest(db)
        lineage = lab.production_lineage(db)
        evaluation, guide = lab.production_decide(lineage, current_state)
        result = coach(evaluation, guide)
        again = coach(*lab.production_decide(lab.production_lineage(db), current_state))
        after = lab._logical_digest(db)
        independent = coach(*lab.production_decide(lab.production_lineage(lab.materialize(trajectory, workdir / "independent")), current_state))
        shuffled = deepcopy(lineage)
        random.Random(scenario["scenario_id"]).shuffle(shuffled["items"])
        reversed_items = deepcopy(lineage)
        reversed_items["items"].reverse()
        item_order = all(lab.canonical(coach(*lab.production_decide(v, current_state))) == lab.canonical(result)
                         for v in (shuffled, reversed_items))
        reversed_db = workdir / "reversed.db"
        lab._reverse_storage_copy(db, reversed_db)
        storage_order = normalized(coach(*lab.production_decide(lab.production_lineage(reversed_db), current_state))) == normalized(result)
        scrambled = lab.scramble(trajectory)
        text_invariant = normalized(coach(*lab.production_decide(lab.production_lineage(lab.materialize(scrambled, workdir / "scrambled")),
                                                                scrambled["current_state"]))) == normalized(result)

    rows = {row["capability_id"]: row for row in evaluation["capabilities"]}
    suggested = result["suggestion"]["capability_id"] if result["suggestion"] else None
    items = {(lab.canonical(item["record"]), item["event"]): item for item in lineage["items"]}
    correspondence = []
    for fact in result["noticed"]:
        records = set()
        for ref in fact["evidence"]:
            if "record" in ref:
                item = items.get((lab.canonical(ref["record"]), ref.get("event")))
                if item is None or item["authorship"] != ref.get("authorship"):
                    correspondence.append(f"{fact['fact']}: unresolved or misattributed evidence")
                records.add(lab.canonical(ref["record"]))
            elif ref.get("basis") != "current_state" or ref.get("input") not in ("governing_question", "perspective_available"):
                correspondence.append(f"{fact['fact']}: undeclared current-state input")
        if records and len(records) != fact["count"]:
            correspondence.append(f"{fact['fact']}: count {fact['count']} != {len(records)} distinct records")
        if fact["authorship"] is not None and any(ref.get("authorship") != fact["authorship"] for ref in fact["evidence"] if "record" in ref):
            correspondence.append(f"{fact['fact']}: mixed authorship under one statement")

    text = [s.lower() for s in _strings(result)]
    wording = rules["wording_rules"]
    unsupported_wording = sorted({p for p in wording["unsupported_as_not_done_forbidden"] if any(p in t for t in text)})
    engagement = sorted({p for p in wording["engagement_forbidden"] if any(p in t for t in text)})
    authorship_problems = sorted(
        {f"{f['fact']}:{f['authorship']}" for f in result["noticed"] if f["authorship"] in ("model", "accepted_model")
         and ("model" not in f["statement"].lower() or any(p in f["statement"].lower() for p in wording["model_authorship_forbidden"]))})
    withheld = {w["capability_id"]: w["code"] for w in result["withheld"]}
    counts = _fact_counts(result)
    facts_by_name = {f["fact"]: f for f in result["noticed"]}
    fragments_ok = all(fragment in facts_by_name.get(name, {}).get("statement", "")
                       for name, fragment in expected.get("required_statement_fragments", {}).items())
    blocked_ok = ("blocked" not in expected
                  or (result["blocked"] is not None and all(result["blocked"][k] == v for k, v in expected["blocked"].items())))
    checks = {
        "schema_valid": not validate_result(result),
        "decision": result["decision"] == expected["decision"] and result["quiet_reason"] == expected["quiet_reason"],
        "suggestion": suggested == expected["suggestion"] and (result["suggestion"] or {}).get("basis") == expected["basis"],
        "forbidden_suggestion": suggested in expected["forbidden_suggestions"],
        "never_suggests_unavailable": suggested is None or rows[suggested]["availability"] == "available",
        "follows_p2_recommendation": suggested in (None, guide["recommended_step_id"]),
        "required_facts": all(counts.get(name) == value for name, value in expected["required_facts"].items()),
        "forbidden_facts_absent": not set(expected["forbidden_facts"]) & set(counts),
        "required_uncertainty": set(expected["required_uncertainty"]) <= {u["code"] for u in result["uncertainty"]},
        "required_withheld": all(withheld.get(c) == code for c, code in expected["required_withheld"].items()),
        "blocked": blocked_ok,
        "statement_fragments": fragments_ok,
        "unsupported_wording_clean": not unsupported_wording,
        "no_engagement_language": not engagement,
        "authorship_distinctions": not authorship_problems,
        "evidence_corresponds": not correspondence,
        "silence_honored": (expected["silence"] not in ("preferred", "required")) or result["decision"] == "remain_quiet",
        "repeatable": lab.canonical(result) == lab.canonical(again) and normalized(independent) == normalized(result),
        "invariant_to_item_order": item_order,
        "invariant_to_storage_order": storage_order,
        "invariant_to_text_and_labels": text_invariant,
        "workspace_unchanged": before == after,
    }
    return {"scenario_id": scenario["scenario_id"], "source": scenario["source"], "expected_silence": expected["silence"],
            "p2_recommended_step_id": guide["recommended_step_id"], "coach": normalized(result),
            "fact_counts": counts, "checks": checks,
            "diagnostics": {"schema": validate_result(result), "unsupported_wording": unsupported_wording, "engagement": engagement,
                            "authorship": authorship_problems, "correspondence": correspondence}}


def run(path: Path = EXPECTATIONS) -> dict:
    rules = load_expectations(path)
    results = []
    for scenario in rules["scenarios"]:
        with tempfile.TemporaryDirectory(prefix="p6-coach-") as tmp:
            results.append(evaluate_scenario(scenario, rules, Path(tmp)))
    names = list(results[0]["checks"])
    aggregate = {name: {"passed": sum(1 for r in results if (not r["checks"][name] if name == "forbidden_suggestion" else r["checks"][name])),
                        "total": len(results)} for name in names}
    aggregate["forbidden_suggestions"] = {"count": sum(1 for r in results if r["checks"]["forbidden_suggestion"]), "total": len(results)}
    aggregate.pop("forbidden_suggestion")
    return {"schema": RESULT_SCHEMA, "coach_schema": SCHEMA, "policy_version": POLICY_VERSION,
            "boundaries": "Synthetic disposable workspaces from the frozen P5 trajectories (unchanged) and two P6 negatives; "
                          "production coach over production P1/P2; no network, provider, persistence or telemetry; evaluation data only.",
            "aggregate": aggregate, "scenarios": results}


def summary_markdown(results: dict) -> str:
    lines = ["# P6 Deterministic Companion Coach v1 — evaluation matrix", "",
             f"Generated by `tests/companion_coach_lab.py`; coach `{results['coach_schema']}` policy `{results['policy_version']}` "
             "over production P1/P2. Evaluation data, not study history.", "",
             "| Scenario | P2 next | Coach decision | Suggestion | Silence expected | Checks passed |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in results["scenarios"]:
        c = r["coach"]
        passed = sum(1 for k, v in r["checks"].items() if (not v if k == "forbidden_suggestion" else v))
        decision = c["decision"] + (f" ({c['quiet_reason']})" if c["quiet_reason"] else "")
        suggestion = f"`{c['suggestion']['capability_id']}` ({c['suggestion']['basis']})" if c["suggestion"] else "—"
        lines.append(f"| `{r['scenario_id']}` | `{r['p2_recommended_step_id']}` | {decision} | {suggestion} | "
                     f"{r['expected_silence']} | {passed}/{len(r['checks'])} |")
    a = results["aggregate"]
    lines += ["", "**Aggregate:** " + "; ".join(
        f"{name.replace('_', ' ')} {a[name]['passed']}/{a[name]['total']}" for name in sorted(a) if name != "forbidden_suggestions")
        + f"; forbidden suggestions {a['forbidden_suggestions']['count']}/{a['forbidden_suggestions']['total']}.", ""]
    failing = [(r["scenario_id"], k) for r in results["scenarios"] for k, v in r["checks"].items()
               if (v if k == "forbidden_suggestion" else not v)]
    lines.append("**Failing checks:** " + ("none." if not failing else ", ".join(f"`{s}`:{k}" for s, k in failing)))
    return "\n".join(lines) + "\n"


def write(results: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    (out / "summary.md").write_text(summary_markdown(results))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    results = run()
    if args.write:
        write(results, args.write)
        return 0
    same = json.loads((args.check / "results.json").read_text()) == json.loads(json.dumps(results, sort_keys=True, ensure_ascii=False))
    print("results match committed dataset" if same else "results differ from committed dataset")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
