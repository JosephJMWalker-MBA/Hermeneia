"""Descriptive report over the preserved P7 live-extraction results (#215).

Reads research/perspective_comparison_live/v1/results.json and the scripted
ceiling. It recomputes no score and changes no verdict. It adds descriptive
error categories for refused outputs, plus run-to-run variability across
repeated identical prompts, and writes summary.md.

    python tests/perspective_comparison_live_report.py research/perspective_comparison_live/v1
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

TESTS = Path(__file__).resolve().parent
LAYER1 = json.loads((TESTS / "fixtures" / "perspective_comparison" / "v1" / "cases.json").read_text())
CASES = {case["case_id"]: case for case in LAYER1["cases"]}
_FENCE = re.compile(r"\A\s*```(?:json)?[ \t]*\n(.*)\n[ \t]*```\s*\Z", re.S)


def diagnose(record: dict) -> dict:
    """Why a refused output failed: the JSON error, or every violated contract rule."""
    out = record["raw_output"]
    match = _FENCE.match(out)
    body = match.group(1) if match else out
    info = {"length": len(out), "fenced": bool(match), "proposition_ids_emitted": len(re.findall(r'"id"\s*:\s*"p\d+"', out))}
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        following = body[exc.pos:exc.pos + 1]
        kind = ("unterminated code fence" if exc.pos == 0 and body.lstrip().startswith("```") else
                "trailing comma" if "trailing comma" in exc.msg else
                "unquoted token" if exc.msg.startswith("Expecting value") and re.match(r"[A-Za-z_\[]", following or " ") else
                "missing delimiter or bracket" if "delimiter" in exc.msg else exc.msg)
        info.update(category=f"invalid JSON: {kind}", error=f"{exc.msg} at char {exc.pos}",
                    context=body[max(0, exc.pos - 40):exc.pos + 20], runaway=len(out) > 8000)
        if info["runaway"]:
            info["category"] += f"; runaway output ({len(out)} chars, {info['proposition_ids_emitted']} propositions)"
        return info
    case = CASES[record["base_case"]]
    labels = {f"P{i}" for i in range(1, len(case["compare"]) + 1)}
    units = {f"U{i}" for i in range(1, len(case["expected"]["evidence"]["units"]) + 1)}
    violations = Counter()
    if not isinstance(value, dict) or set(value) != {"propositions", "assumptions"}:
        violations["top-level keys"] += 1
    for p in value.get("propositions", []) if isinstance(value, dict) else []:
        for x in p.get("positions", []) if isinstance(p, dict) else []:
            missing = {"participant", "stance", "quote", "relies_on"} - set(x)
            extra = set(x) - {"participant", "stance", "quote", "relies_on"}
            for key in sorted(missing):
                violations[f"position missing '{key}'"] += 1
            for key in sorted(extra):
                violations[f"position has unknown key '{key}'"] += 1
            if x.get("participant") not in labels:
                violations[f"unknown participant label {x.get('participant')!r}"] += 1
            if x.get("stance") not in ("asserts", "denies", "does_not_address", "unclassifiable"):
                violations[f"stance outside contract {x.get('stance')!r}"] += 1
            if any(item not in units for item in x.get("relies_on") or []):
                violations["relies_on outside unit labels"] += 1
    for a in value.get("assumptions", []) if isinstance(value, dict) else []:
        if not (isinstance(a, dict) and set(a) == {"participant", "quote"}):
            violations["assumption keys"] += 1
        elif not (isinstance(a["quote"], str) and a["quote"].strip()):
            violations["assumption without a quote"] += 1
    info.update(category="contract violation", violations=dict(sorted(violations.items())))
    return info


def variability(records: list[dict]) -> dict:
    groups: dict[str, list] = {}
    for record in records:
        groups.setdefault(record["base_case"], []).append(record)
    result = {}
    for base, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        outputs = {hashlib.sha256((r["raw_output"] or "").encode()).hexdigest() for r in group}
        prompts = {r["prompt_sha256"] for r in group if r["prompt_sha256"]}
        result[base] = {"runs": len(group), "distinct_outputs": len(outputs), "distinct_prompts_among_candidates": len(prompts),
                        "outcomes": [f"{r['run_id']}: {r['http_status']}{' ' + r['code'] if r.get('code') else ''}" for r in group]}
    return result


def comparison_shape(records: list[dict]) -> dict:
    """Does the model relate participants at all, and why do quoted positions fail to trace?"""
    candidates = [r for r in records if not r["refused"]]
    propositions = [p for r in candidates for p in r["structure"]["propositions"]]
    multi = sum(1 for p in propositions if sum(x["stance"] != "unknown" for x in p["positions"]) >= 2)
    reasons = Counter()
    for r in candidates:
        for item in r["structure"]["untraceable"]:
            if item["kind"] == "untraceable_position":
                quote = item.get("quote")
                reasons["missing quote" if quote is None else "empty quote" if quote == "" else
                        "altered or non-exact quote"] += 1
    return {"candidate_propositions": len(propositions), "propositions_classifying_2_or_more_participants": multi,
            "untraced_quoted_position_reasons": dict(sorted(reasons.items())),
            "positions_left_unclassified": sum(r["score"]["untraceable"].get("position_not_classified", 0) for r in candidates)}


def summary(results: dict, ceiling: dict, diagnostics: dict, varied: dict) -> str:
    m, c = results["aggregate"]["metrics"], ceiling["metrics"]
    shape = comparison_shape(results["records"])

    def pr(x):
        return f"P {x['precision']:.2f} / R {x['recall']:.2f} (tp {x['tp']}, fp {x['fp']}, fn {x['fn']})"

    rows = [
        ("Structural refusal rate", f"{m['structural_refusal_rate']:.2f} ({m['outcomes']['REFUSED_runs']}/{m['live_runs']})", f"{c['structural_refusal_rate']:.2f}"),
        ("Claim attribution accuracy", f"{m['claim_attribution_accuracy']:.2f} (misattributions {m['misattributions']})", f"{c['claim_attribution_accuracy']:.2f}"),
        ("Stance accuracy", f"{m['stance_accuracy']:.2f}", f"{c['stance_accuracy']:.2f}"),
        ("Agreement", pr(m["agreement"]), pr(c["agreement"])),
        ("Disagreement", pr(m["disagreement"]), pr(c["disagreement"])),
        ("Evidence reliance", pr(m["evidence_reliance"]), pr(c["evidence_reliance"])),
        ("Assumptions", pr(m["assumptions"]), pr(c["assumptions"])),
        ("Minority preservation (runs)", f"{m['minority_preservation']['preserved']}/{m['minority_preservation']['runs']} (downgraded {m['minority_downgraded']}, lost {m['minority_lost']})",
         f"{c['minority_preservation']['preserved']}/{c['minority_preservation']['runs']}"),
        ("Unknown preservation (runs)", f"{m['unknown_preservation']['preserved']}/{m['unknown_preservation']['runs']}", f"{c['unknown_preservation']['preserved']}/{c['unknown_preservation']['runs']}"),
        ("Untraceable content rate", f"{m['untraceable_content_rate']:.2f}", f"{c['untraceable_content_rate']:.2f}"),
        ("Paraphrase-as-disagreement errors", str(m["paraphrase_as_disagreement_errors"]), str(c["paraphrase_as_disagreement_errors"])),
        ("Silent-minority errors", str(m["silent_minority_errors"]), str(c["silent_minority_errors"])),
        ("Admitted but wrong", f"{m['outcomes']['ADMITTED_BUT_WRONG_items']}/{m['outcomes']['admitted_semantic_items']} = {m['outcomes']['admitted_but_wrong_rate']:.2f}",
         f"{c['outcomes']['ADMITTED_BUT_WRONG_items']}/{c['outcomes']['admitted_semantic_items']} = {c['outcomes']['admitted_but_wrong_rate']:.2f}"),
    ]
    lines = ["# P7 live semantic-extraction evaluation — `hermeneia-phi4-mini:latest`", "",
             f"**Verdict (frozen protocol): {results['aggregate']['verdict']}.** Governance defects: "
             f"{len(results['aggregate']['governance_defects'])}.", "",
             "Owner-authorized, bounded, local-only; production candidate route; frozen corpus, prompt, rules and scorer; "
             "nothing accepted. Temperature 0 is not supported by the production path (Ollama defaults applied). "
             "Steward review is not counted as model accuracy.", "",
             "## Live model against the scripted ceiling", "", "| Measure | Live (23 runs) | Scripted ceiling (13 faithful) |", "| --- | --- | --- |"]
    lines += [f"| {name} | {live} | {ceil} |" for name, live, ceil in rows]
    lines += ["", "Ready conditions: " + "; ".join(f"`{k}` {'met' if v else 'not met'}" for k, v in results["aggregate"]["ready_conditions"].items()), "",
              "## Bad model content by outcome", "",
              f"- **REFUSED:** {m['outcomes']['REFUSED_runs']} runs ({', '.join(f'{k} {v}' for k, v in m['refusals_by_code'].items())})",
              f"- **DOWNGRADED TO UNKNOWN:** {m['outcomes']['DOWNGRADED_TO_UNKNOWN_items']} items",
              f"- **ADMITTED BUT WRONG:** {m['outcomes']['ADMITTED_BUT_WRONG_items']} of {m['outcomes']['admitted_semantic_items']} admitted items "
              f"(including {m['outcomes']['unmatched_candidate_claims']} claims on unmatched propositions)",
              f"- Omitted reference propositions: {m['outcomes']['OMITTED_reference_propositions']}", "",
              "## Comparison shape (descriptive)", "",
              f"- Candidate propositions classifying two or more participants: "
              f"{shape['propositions_classifying_2_or_more_participants']} of {shape['candidate_propositions']}. The model "
              "restated each participant separately and never related participants, so no agreement or disagreement "
              "could be derived. Zero paraphrase-as-disagreement and silent-minority errors therefore reflect the absence "
              "of comparison, not resistance to those errors.",
              f"- Positions left unclassified by the model: {shape['positions_left_unclassified']}.",
              "- Untraced quoted positions: " + ", ".join(f"{k} ×{v}" for k, v in shape["untraced_quoted_position_reasons"].items()) + ".", "",
              "## Per run", "", "| Run | HTTP | Result | Untraceable | Admitted wrong | Temptation (frozen criterion) |", "| --- | --- | --- | --- | --- | --- |"]
    for r in results["records"]:
        if r["refused"]:
            d = diagnostics[r["run_id"]]
            detail = d["category"] + (": " + ", ".join(f"{k} ×{v}" for k, v in d.get("violations", {}).items()) if d.get("violations") else "")
            result = f"refused `{r['code']}` ({detail})"
            untr = wrong = "—"
        else:
            s = r["score"]
            result = (f"propositions {s['propositions']['matched']}/{s['propositions']['reference']} matched, {s['propositions']['candidate']} proposed; "
                      f"stance {s['stance']['agree']}/{s['stance']['total']}; relations agreement {len(r['structure']['relations']['agreement'])}, "
                      f"disagreement {len(r['structure']['relations']['disagreement'])}")
            untr = ", ".join(f"{k} ×{v}" for k, v in r["score"]["untraceable"].items()) or "—"
            wrong = f"{r['counts']['admitted_but_wrong']}/{r['counts']['admitted_semantic_items']}"
        temptation = ""
        if r.get("temptation_result"):
            t = r["temptation_result"]
            temptation = t["outcome"] + (" (no candidate to assess)" if r["refused"] and t["outcome"] == "resisted" else "")
        lines.append(f"| {r['run_id']} | {r['http_status']} | {result} | {untr} | {wrong} | {temptation} |")
    lines += ["", "## Run-to-run variability (identical prompts)", "", "| Base case | Runs | Distinct outputs | Outcomes |", "| --- | --- | --- | --- |"]
    for base, v in varied.items():
        lines.append(f"| {base} | {v['runs']} | {v['distinct_outputs']} | {'; '.join(v['outcomes'])} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    out = Path((argv or sys.argv[1:])[0])
    results = json.loads((out / "results.json").read_text())
    ceiling = json.loads((out / "scripted_ceiling.json").read_text())
    diagnostics = {r["run_id"]: diagnose(r) for r in results["records"] if r["refused"]}
    varied = variability(results["records"])
    (out / "diagnostics.json").write_text(json.dumps({"refusals": diagnostics, "variability": varied,
                                                       "comparison_shape": comparison_shape(results["records"])},
                                                      indent=2, sort_keys=True) + "\n")
    (out / "summary.md").write_text(summary(results, ceiling, diagnostics, varied))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
