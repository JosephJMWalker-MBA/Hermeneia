"""Deterministic Companion Coach v1 (#215 P6): one bounded suggestion, or silence.

The coach consumes only the production Capability Registry evaluation (P1)
and Guided Study Cycle projection (P2) for one snapshot. It never reads SQL
or Lineage, never selects a step other than P2's recommendation, never makes
an unavailable capability available, persists nothing and calls no provider.
Its result is a current projection, not study history.
Contract: docs/design/companion-coach-v1.md.
"""
from __future__ import annotations

from copy import deepcopy
import json

SCHEMA = "hermeneia.companion-coach/v1"
POLICY_VERSION = "1.0.0"
_GUIDE_SCHEMA = "hermeneia.guided-study-cycle/v1"
_EVALUATION_SCHEMA = "hermeneia.capability-evaluation/v1"
_GUIDE_VERSIONS = frozenset({"1.0.0"})
_ABSENCE_NOTE = "Absence of an extant record is not proof that an operation never occurred."
_AUTHORSHIP_NOTE = "Canonical interpretation authorship is unknown; formation cannot be attributed."
NOT_HISTORY = ("This is a current coaching projection, not study history. It does not record that a suggestion "
               "was shown, accepted or helpful.")
_OMITTED = ("Some records are omitted from this projection (for example, records from sources excluded from "
            "analysis, or records whose parents are unavailable) and do not inform this coaching result.")
_INTERPRETATION_STATEMENTS = {
    "human": "{n} steward-authored Interpretation(s) are retained.",
    "accepted_model": "{n} accepted model contribution(s) are retained as Interpretations.",
    "model": "{n} model proposal(s) are present; a proposal is not a steward-authored Interpretation.",
}
_INTERPRETATION_UNKNOWN = "{n} Interpretation record(s) have unrecorded authorship."


def _validate(evaluation: dict, guide: dict) -> None:
    if not isinstance(evaluation, dict) or evaluation.get("schema") != _EVALUATION_SCHEMA:
        raise ValueError("Capability Registry evaluation v1 required")
    if not isinstance(guide, dict) or guide.get("schema") != _GUIDE_SCHEMA or guide.get("guide_version") not in _GUIDE_VERSIONS:
        raise ValueError("Supported Guided Study Cycle projection required")
    for key in ("registry_version", "evaluator_version", "registry_sha256"):
        if guide.get(key) != evaluation.get(key):
            raise ValueError("Guide and evaluation must come from the same registry and evaluator")
    rows = {row["capability_id"]: row for row in evaluation["capabilities"]}
    steps = {step["capability_id"]: step for step in guide["steps"]}
    if set(rows) != set(steps) or len(steps) != len(guide["steps"]):
        raise ValueError("Guide and evaluation must cover the same capabilities")
    for capability, step in steps.items():
        if step["availability"] != rows[capability]["availability"] or step["capability_status"] != rows[capability]["status"]:
            raise ValueError("Guide and evaluation must come from the same snapshot")
    if guide.get("recommended_step_id") not in steps:
        raise ValueError("Guide recommendation must name a guide step")


def _distinct(refs: list, tables: set[str]) -> list[dict]:
    """Distinct typed records from production references; decision views add none."""
    found: dict[str, dict] = {}
    for ref in refs:
        record = ref.get("record")
        if isinstance(record, dict) and record.get("table") in tables and ref.get("event") != "decision":
            found.setdefault(json.dumps(record, sort_keys=True), ref)
    return [found[key] for key in sorted(found)]


def _fact(name, count, refs, basis, statement, authorship=None) -> dict:
    return {"fact": name, "count": count, "basis": basis, "authorship": authorship,
            "statement": statement, "evidence": deepcopy(refs)}


def _noticed(rows: dict, steps: dict) -> list[dict]:
    facts = []
    question = steps["governing_question"]
    if question["status"] == "currently_supported" and question["evidence_or_state_basis"]:
        facts.append(_fact("governing_question_present", 1, question["evidence_or_state_basis"], "current_state",
                           "A governing question is present now."))

    def counted(name, capability, tables, basis, template):
        refs = _distinct(rows[capability]["evidence_refs"], tables)
        if refs:
            authors = sorted({ref.get("authorship") for ref in refs})
            facts.append(_fact(name, len(refs), refs, basis, template.format(n=len(refs)),
                               authors[0] if len(authors) == 1 else None))

    counted("saved_reader_marks", "organize_evidence", {"reader_highlights"}, "current_state",
            "{n} saved Reader mark(s) are present as current snapshots; when or by whom they were made is not recorded.")
    organize = steps["organize_evidence"]
    if organize["status"] == "currently_supported":
        grouped = _distinct(organize["evidence_or_state_basis"], {"reader_highlights"})
        if grouped:
            facts.append(_fact("grouped_marks", len(grouped), grouped, "current_state",
                               f"{len(grouped)} saved Reader mark(s) currently carry group labels; labels are not organization history."))
    counted("canonical_observations", "form_interpretation", {"observations"}, "durable_history",
            "{n} canonical Observation(s) are available as compiler-derived source units.")
    counted("inquiry_questions", "preserve_question", {"inquiry_notes"}, "durable_history",
            "{n} inquiry question(s) are retained beside Observations.")
    counted("saved_frames", "form_interpretation", {"perspectives"}, "durable_history",
            "{n} saved Perspective frame(s) are declared; a frame declaration is not a run.")
    selected = [ref for ref in rows["form_interpretation"]["evidence_refs"]
                if ref.get("basis") == "current_state" and ref.get("input") == "perspective_available"]
    if selected:
        facts.append(_fact("selected_frame", 1, selected[:1], "current_state", "A Perspective frame is selected now."))
    counted("retained_perspective_executions", "explore_perspective", {"perspective_execution_receipts"}, "durable_history",
            "{n} retained Perspective execution(s) are model-generated; keeping them is not agreement.")
    # One statement per Lineage authorship: model work is never merged with steward work.
    interpretations = _distinct(rows["challenge_interpretation"]["evidence_refs"], {"interpretations", "proposed_interpretations"})
    for author in sorted({ref.get("authorship") for ref in interpretations}):
        group = [ref for ref in interpretations if ref.get("authorship") == author]
        text = _INTERPRETATION_STATEMENTS.get(author, _INTERPRETATION_UNKNOWN)
        facts.append(_fact("interpretation_material", len(group), group, "durable_history", text.format(n=len(group)), author))
    counted("blueprints", "review_blueprint", {"narrative_blueprints"}, "durable_history",
            "{n} saved Blueprint(s) are retained; review of a Blueprint is not recorded.")
    return facts


def _uncertainty(rows: dict, steps: dict, guide: dict, suggested: str | None) -> list[dict]:
    result = []
    if suggested is not None:
        row, step = rows[suggested], steps[suggested]
        if row["status"] != "already_exercised_under_supported_evidence" and _ABSENCE_NOTE in row["coverage_or_unknown_notes"]:
            result.append({"code": "ABSENCE_NOT_PROOF", "statement": _ABSENCE_NOTE,
                           "source": f"P1 {suggested}.coverage_or_unknown_notes"})
        if step["history_support"]["status"] == "unsupported":
            result.append({"code": "HISTORY_NOT_RECORDED", "statement": step["history_support"]["reason"],
                           "source": f"P2 {suggested}.history_support"})
    coverage = guide["lineage_coverage"]
    missing = list(coverage["missing_tables"]) + [f"{table} ({', '.join(columns)})"
                                                  for table, columns in sorted(coverage["missing_columns"].items())]
    if missing:
        result.append({"code": "COVERAGE_INCOMPLETE", "source": "P2 lineage_coverage",
                       "statement": "This workspace's records do not include: " + "; ".join(missing)
                                    + ". Hermeneia cannot establish what those records would show."})
    if any(coverage["omitted"].values()):
        result.append({"code": "RECORDS_OMITTED", "statement": _OMITTED, "source": "P2 lineage_coverage.omitted"})
    if any(_AUTHORSHIP_NOTE in row["coverage_or_unknown_notes"] for row in rows.values()):
        result.append({"code": "AUTHORSHIP_UNKNOWN", "statement": _AUTHORSHIP_NOTE, "source": "P1 coverage_or_unknown_notes"})
    return result


def _withheld(rows: dict, guide: dict, chosen: str) -> list[dict]:
    order = [step["capability_id"] for step in guide["steps"]]
    position = order.index(chosen)
    result = []
    for index, step in enumerate(guide["steps"]):
        capability = step["capability_id"]
        if capability == chosen:
            continue
        row, state = rows[capability], step["status"]
        if state == "not_ready":
            code, detail = "PREREQUISITE_MISSING", f"{row['availability_reason_code']}: {row['availability_reason']}"
        elif state == "unknown":
            code, detail = "COVERAGE_UNSUPPORTED", row["availability_reason"]
        elif state == "currently_supported":
            code, detail = "ALREADY_CURRENT_MATERIAL", step["status_reason"]
        elif state == "historically_exercised":
            code, detail = "NARROW_HISTORY_RETAINED", step["history_support"]["reason"]
        elif index > position:
            code, detail = "LATER_IN_CYCLE", "The guide suggests the earliest step that is not current material first."
        else:
            code, detail = "NOT_RECONSTRUCTED_BY_RESUMPTION", guide["recommendation_reason"]
        result.append({"capability_id": capability, "code": code, "detail": detail})
    return result


def coach(evaluation: dict, guide: dict) -> dict:
    """Deterministic policy 1.0.0 over one snapshot's P1 evaluation and P2 guide."""
    _validate(evaluation, guide)
    rows = {row["capability_id"]: row for row in evaluation["capabilities"]}
    steps = {step["capability_id"]: step for step in guide["steps"]}
    chosen = guide["recommended_step_id"]
    row, step = rows[chosen], steps[chosen]

    if row["availability"] == "not_yet_available":
        decision, quiet = "remain_quiet", "NEXT_STEP_BLOCKED"
        why = f"The guide's next step, {step['title']}, is not available now: {row['availability_reason']}"
    elif row["availability"] == "unsupported_due_to_missing_history":
        decision, quiet = "remain_quiet", "NEXT_STEP_UNKNOWN"
        why = (f"Readiness for the guide's next step, {step['title']}, cannot be established from this workspace's "
               f"records. {row['availability_reason']}")
    elif chosen == "review_lineage":
        decision, quiet = "remain_quiet", "OPTIONAL_REVIEW_ONLY"
        why = (f"{guide['recommendation_reason']} The remaining guide step is optional review, which is not "
               "recorded, so the coach does not interrupt.")
    else:
        decision, quiet = "suggest", None
        why = " ".join(part for part in (step["why_it_matters"], step["status_reason"], guide["recommendation_reason"]) if part)

    suggestion = None
    if decision == "suggest":
        anchored = (steps["governing_question"]["status"] == "currently_supported"
                    and steps["form_interpretation"]["status"] == "historically_exercised")
        suggestion = {"capability_id": chosen, "definition_version": step["definition_version"], "title": step["title"],
                      "action": step["recommended_action"], "target_surface": step["target_surface"],
                      "basis": "durable_history" if anchored else "current_state",
                      "readiness": {"availability": row["availability"],
                                    "availability_reason_code": row["availability_reason_code"],
                                    "prerequisites_satisfied": list(row["prerequisites_satisfied"]),
                                    "prerequisites_missing": list(row["prerequisites_missing"])}}
    blocked = None
    if quiet in ("NEXT_STEP_BLOCKED", "NEXT_STEP_UNKNOWN"):
        blocked = {"capability_id": chosen, "availability": row["availability"],
                   "reason_code": row["availability_reason_code"], "reason": row["availability_reason"],
                   "prerequisites_missing": list(row["prerequisites_missing"])}
    return {
        "schema": SCHEMA, "policy_version": POLICY_VERSION,
        "inputs": {"guide_schema": guide["schema"], "guide_version": guide["guide_version"],
                   "registry_version": guide["registry_version"], "evaluator_version": guide["evaluator_version"],
                   "registry_sha256": guide["registry_sha256"], "recommended_step_id": chosen},
        "decision": decision, "quiet_reason": quiet, "suggestion": suggestion,
        "noticed": _noticed(rows, steps), "why_now": why,
        "next_action": step["recommended_action"] if decision == "suggest" else None,
        "uncertainty": _uncertainty(rows, steps, guide, chosen if decision == "suggest" else None),
        "blocked": blocked, "withheld": _withheld(rows, guide, chosen), "not_history": NOT_HISTORY,
    }
