"""A deterministic method guide over Capability Registry v1 and Study Lineage.

Current material is a place to resume study, never reconstructed completion.
Only the capability evaluator decides readiness and historical support.
"""
from copy import deepcopy
import json

from .capabilities import evaluate_capabilities, load_capability_registry

SCHEMA = "hermeneia.guided-study-cycle/v1"
GUIDE_VERSION = "1.0.0"

# Ordered presentation metadata. Eligibility and provenance belong to P1.
_CYCLE = (
    ("governing_question", "question", "Set or revisit the governing question"),
    ("read_source", "reader", "Open the source and read a small passage"),
    ("mark_evidence", "capture", "Mark one passage that matters"),
    ("record_observation", "observations", "Inspect source units or an anchored observation candidate"),
    ("preserve_question", "inquiry", "Preserve a question beside an Observation"),
    ("organize_evidence", "evidence", "Compare and group the evidence you retained"),
    ("explore_perspective", "perspective", "Choose a frame and examine the evidence"),
    ("form_interpretation", "interpretation", "Form or inspect a provisional interpretation"),
    ("challenge_interpretation", "search", "Search source passages for counterevidence"),
    ("review_blueprint", "blueprint", "Review the Blueprint against its evidence"),
    ("review_lineage", "lineage", "Inspect the recorded study lineage"),
)


def project_guided_study_cycle(lineage: dict, registry: dict | None = None, *, current_state: dict | None = None) -> dict:
    """Read-only cycle projection; browser preferences are never inputs.

    Material descriptions consult only already-eligible Lineage items referenced
    by P1. They neither change availability nor classify authorship/acceptance.
    """
    registry = load_capability_registry() if registry is None else registry
    current = {} if current_state is None else deepcopy(current_state)
    # P1 validates all inputs and owns every prerequisite/status decision.
    evaluation = evaluate_capabilities(lineage, registry, current_state=current)
    definitions = {row["capability_id"]: row for row in registry["capabilities"]}
    capabilities = {row["capability_id"]: row for row in evaluation["capabilities"]}
    if set(definitions) != {row[0] for row in _CYCLE}:
        raise ValueError("Guided Study Cycle v1 requires the exact initial capability set")

    def identity(record):
        # The real typed key is unchanged; no new identity is minted.
        return json.dumps(record, sort_keys=True, ensure_ascii=False)

    items = {(identity(item["record"]), item["event"]): item for item in lineage["items"]}

    def refs(capability, table=None):
        return [deepcopy(ref) for ref in capabilities[capability]["evidence_refs"]
                if table is None or ref.get("record", {}).get("table") == table]

    def record_rows(capability, table):
        return [(ref, items[(identity(ref["record"]), ref["event"])]["record_data"])
                for ref in refs(capability, table)]

    def nonblank(value):
        return isinstance(value, str) and bool(value.strip())

    question_basis = []
    if "governing_question" in current:
        has_question = nonblank(current["governing_question"])
        if has_question:
            question_basis = [{"basis": "current_state", "input": "governing_question"}]
    else:
        # Inquiry notes are not silently relabeled as the governing question.
        question_basis = [ref for ref, data in record_rows("explore_perspective", "workspace_investigation")
                          if ref["record"]["key"] == {"id": "current"} and nonblank(data.get("thesis"))]
        has_question = bool(question_basis)

    observations = refs("form_interpretation", "observations")
    marks = refs("organize_evidence", "reader_highlights")
    questions = refs("preserve_question", "inquiry_notes")
    sources = refs("read_source", "source_extractions")
    interpretations = [ref for ref in refs("challenge_interpretation")
                       if ref.get("record", {}).get("table") in ("interpretations", "proposed_interpretations")]
    group_refs = [ref for ref, data in record_rows("organize_evidence", "reader_highlights")
                  if nonblank(data.get("theme_bucket")) or nonblank(data.get("evidence_bucket"))]
    frames = [ref for ref in refs("form_interpretation")
              if ref.get("record", {}).get("table") == "perspectives" or ref.get("input") == "perspective_available"]
    blueprints = refs("review_blueprint", "narrative_blueprints")

    # Snapshot support describes material, not an operation performed. It is
    # used only to find a useful resumption point within P1's readiness gates.
    material = {
        "governing_question": (has_question, question_basis,
            "A governing question is present now; its formulation history is not recorded." if has_question else
            "A current governing question is not established by this snapshot. Set a compass, not a conclusion."),
        "read_source": (bool(marks), sources + marks,
            "Readable source material is available. Reading and comprehension are not measured."),
        "mark_evidence": (bool(marks), marks,
            "Saved Reader marks are available; historical marking and authorship remain unknown." if marks else
            "The source supports marking. A saved Reader attention record is not established by this snapshot."),
        "record_observation": (bool(observations), observations,
            "Canonical source units are available for inspection; compiler segmentation is distinct from human attention." if observations else
            "Saved evidence supports observation work. Inspect source units or designate an anchored candidate without rewriting evidence."),
        "preserve_question": (bool(questions), questions,
            "A separately identified inquiry question is retained; authorship and resolution are separate claims." if questions else
            "Keep uncertainty beside its evidence. A separately identified inquiry question is not established by this snapshot."),
        "organize_evidence": (len({identity(ref["record"]) for ref in group_refs}) >= 2, group_refs,
            "At least two saved marks have current group labels. These labels are neither bucket history nor Scope admission." if len({identity(ref["record"]) for ref in group_refs}) >= 2 else
            "Enough distinct evidence is available to begin organizing. Current labels do not establish organization history or Scope admission."),
        "explore_perspective": (bool(frames), frames,
            "A saved or explicitly selected frame is available. A frame is not a recorded Perspective execution." if frames else
            "Choose a frame and examine the admitted evidence. Current receipts do not establish durable Perspective execution history."),
        "form_interpretation": (bool(interpretations), interpretations,
            "An interpretation or proposal is retained. A proposal remains unaccepted unless existing provenance says otherwise." if interpretations else
            "Use the preserved Observation and a frame to develop a provisional interpretation; retain what supports it."),
        "challenge_interpretation": (False, refs("challenge_interpretation"),
            "Examine counterevidence and alternatives. Current records do not establish that human review occurred."),
        "review_blueprint": (bool(blueprints), blueprints,
            "A saved Blueprint is available. Creation or supersession does not establish review or evidence-driven revision."),
        "review_lineage": (False, refs("review_lineage"),
            "Inspect what the study actually preserves, including its unknowns. Review itself is not durably recorded."),
    }
    steps = []
    for ordinal, (capability_id, target, action) in enumerate(_CYCLE, 1):
        definition, capability = definitions[capability_id], capabilities[capability_id]
        supported, basis, material_reason = material[capability_id]
        historical = capability["status"] == "already_exercised_under_supported_evidence"
        if historical:
            status = "historically_exercised"
        elif capability["availability"] == "available":
            status = "currently_supported" if supported else "ready"
        else:
            status = "not_ready" if capability["availability"] == "not_yet_available" else "unknown"
        reason = material_reason if capability["availability"] == "available" or historical else capability["availability_reason"]
        steps.append({
            "step_id": capability_id, "ordinal": ordinal, "capability_id": capability_id,
            "definition_version": definition["definition_version"], "title": definition["title"],
            "why_it_matters": definition["purpose"], "status": status,
            "capability_status": capability["status"], "availability": capability["availability"],
            "status_reason": reason, "reason_code": capability["reason_code"],
            "availability_reason": capability["availability_reason"],
            "recommended_action": action, "target_surface": target,
            "evidence_or_state_basis": basis or refs(capability_id),
            "history_support": {"status": "supported" if historical else "unsupported",
                "reason": capability["reason"] if historical else definition["refusal_or_unknown_conditions"]["reason"]},
            "coverage_or_unknown_notes": deepcopy(capability["coverage_or_unknown_notes"]),
        })

    # A retained attributable Interpretation is a legitimate later resumption
    # point, not proof of the missing earlier method actions. If a Blueprint is
    # also retained, inspect Lineage; no review or complete cycle is inferred.
    start = 0
    recommendation_reason = "Resume at the earliest step whose current material is not supported; missing prerequisites are explained."
    if has_question and capabilities["form_interpretation"]["status"] == "already_exercised_under_supported_evidence":
        start = 10 if blueprints else 8
        recommendation_reason = (
            "An attributable Interpretation and a Blueprint are retained. Inspect their Lineage; earlier actions and review history remain unknown."
            if blueprints else
            "An attributable Interpretation is retained. Check counterevidence next; earlier method actions are not reconstructed as completed."
        )
    recommended = next((step for step in steps[start:] if step["status"] not in ("currently_supported", "historically_exercised")), steps[-1])
    result = {key: deepcopy(evaluation[key]) for key in
              ("workspace", "registry_version", "evaluator_version", "registry_sha256", "lineage_coverage")}
    return {"schema": SCHEMA, "guide_version": GUIDE_VERSION, **result, "steps": steps,
            "recommended_step_id": recommended["step_id"], "recommendation_reason": recommendation_reason}
