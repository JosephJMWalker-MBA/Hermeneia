"""Strict static definitions and conservative, deterministic capability rules."""
from copy import deepcopy
import json

import pytest

from hermeneia.capabilities import (
    CapabilityRegistryError, EVALUATOR_VERSION, STATUSES,
    evaluate_capabilities, load_capability_registry,
)
from hermeneia.study_lineage import SCHEMA


IDS = {
    "governing_question", "read_source", "mark_evidence", "record_observation",
    "preserve_question", "organize_evidence", "explore_perspective",
    "form_interpretation", "challenge_interpretation", "review_blueprint", "review_lineage",
}
UNSUPPORTED = "unsupported_due_to_missing_history"
EXERCISED = "already_exercised_under_supported_evidence"


def _projection(*items):
    # Unit fixtures describe a complete empty/current projection. Integration
    # tests separately exercise the actual storage eligibility/coverage owner.
    return {"schema": SCHEMA, "workspace": {"id": "study", "name": "Study"},
            "items": list(items), "coverage": {"missing_tables": [],
            "missing_columns": {}, "omitted": {}, "limitations": ["Extant records only."]}}


def _item(table, identifier, *, event="recorded", authorship="unknown", **data):
    return {"record": {"table": table, "key": {"id": identifier}},
            "event": event, "authorship": authorship,
            "timestamp": {"field": "created_at", "value": None, "status": "unknown", "sort_key": None},
            "provenance": {"records": [], "basis": "Synthetic projection fixture"},
            "record_data": {"id": identifier, **data}}


def _rows(projection, **current):
    return {row["capability_id"]: row for row in
            evaluate_capabilities(projection, current_state=current)["capabilities"]}


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")


def test_packaged_registry_is_explicit_complete_and_version_frozen():
    first = load_capability_registry()
    assert first == load_capability_registry()
    definitions = first["capabilities"]
    assert len(definitions) == len(IDS)
    assert {row["capability_id"] for row in definitions} == IDS
    assert first["registry_version"] == EVALUATOR_VERSION == "1.0.0"
    assert {row["definition_version"] for row in definitions} == {"1.0.0"}
    result = evaluate_capabilities(_projection(), first)
    # Changing released definitions requires an explicit version/fixture review.
    assert result["registry_sha256"] == "7ec255a892ed48a6ce42b597cad2e247b6f99d59cb7e6edd41bca15d14074622"
    assert STATUSES == {"available", "not_yet_available", EXERCISED, UNSUPPORTED}


@pytest.mark.parametrize("malformation", [
    "duplicate_id", "missing_field", "extra_field", "missing_version", "invalid_version", "unicode_version",
    "unknown_schema", "unknown_fact", "duplicate_fact", "boolean_minimum", "zero_minimum",
    "unhashable_reason", "unknown_reason", "empty_output", "unknown_related", "duplicate_related",
    "readiness_as_history", "nonfinite",
])
def test_invalid_registry_definitions_fail_closed(tmp_path, malformation):
    registry = load_capability_registry()
    row = next(row for row in registry["capabilities"] if row["capability_id"] == "read_source")
    predicate = row["prerequisites"][0]
    if malformation == "duplicate_id":
        registry["capabilities"].append(deepcopy(row))
    elif malformation == "missing_field":
        del row["purpose"]
    elif malformation == "extra_field":
        row["onboarding_done"] = True
    elif malformation == "missing_version":
        del row["definition_version"]
    elif malformation == "invalid_version":
        row["definition_version"] = "01.0.0"
    elif malformation == "unicode_version":
        row["definition_version"] = "1\u0660.0.0"
    elif malformation == "unknown_schema":
        registry["schema"] = "hermeneia.capability-registry/v2"
    elif malformation == "unknown_fact":
        predicate["fact"] = "localStorage_done"
    elif malformation == "duplicate_fact":
        row["prerequisites"].append(deepcopy(predicate))
    elif malformation == "boolean_minimum":
        predicate["minimum"] = True
    elif malformation == "zero_minimum":
        predicate["minimum"] = 0
    elif malformation == "unhashable_reason":
        predicate["reason_code"] = []
    elif malformation == "unknown_reason":
        predicate["reason_code"] = "COMPLETED"
    elif malformation == "empty_output":
        row["expected_outputs"] = []
    elif malformation == "unknown_related":
        row["related_or_next_capabilities"] = ["award_badge"]
    elif malformation == "duplicate_related":
        row["related_or_next_capabilities"] *= 2
    elif malformation == "readiness_as_history":
        row["positive_evidence"] = [{"fact": "reader_material", "minimum": 1}]
    elif malformation == "nonfinite":
        predicate["minimum"] = float("nan")
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(CapabilityRegistryError):
        load_capability_registry(path)
    with pytest.raises(CapabilityRegistryError):
        evaluate_capabilities(_projection(), registry)


@pytest.mark.parametrize("raw", [b"{", b"\xff", b'{"schema":"one","schema":"two"}',
                                     b'{"schema":NaN}'])
def test_invalid_registry_bytes_are_not_repaired_or_reloaded(tmp_path, raw):
    path = tmp_path / "registry.json"
    path.write_bytes(raw)
    with pytest.raises(CapabilityRegistryError):
        load_capability_registry(path)
    assert path.read_bytes() == raw


def test_same_facts_and_definitions_produce_identical_results_without_input_mutation():
    projection = _projection(_item("observations", "b"), _item("observations", "a"))
    registry = load_capability_registry()
    current = {"governing_question": "Why?", "perspective_available": True}
    before = deepcopy((projection, registry, current))
    result = evaluate_capabilities(projection, registry, current_state=current)
    assert _bytes(result) == _bytes(evaluate_capabilities(projection, registry, current_state=current))
    assert (projection, registry, current) == before
    shuffled = deepcopy(projection)
    shuffled["items"].reverse()
    definitions = deepcopy(registry)
    definitions["capabilities"].reverse()
    assert _bytes(result) == _bytes(evaluate_capabilities(shuffled, definitions, current_state=current))
    result["workspace"]["name"] = "Caller edit"
    result["lineage_coverage"]["limitations"].append("Caller edit")
    next(row for row in result["capabilities"] if row["capability_id"] == "organize_evidence")["evidence_refs"][0]["provenance"]["basis"] = "Caller edit"
    result["capabilities"][0]["evidence_refs"].clear()
    registry["capabilities"][0]["title"] = "Caller edit"
    assert projection == before[0]
    assert load_capability_registry() == before[1]


def test_empty_known_coverage_reports_explicit_missing_prerequisites():
    rows = _rows(_projection(), perspective_available=False, governing_question=None)
    expected = {"read_source": "MISSING_SOURCE", "mark_evidence": "MISSING_SOURCE",
                "record_observation": "INSUFFICIENT_EVIDENCE", "preserve_question": "INSUFFICIENT_EVIDENCE",
                "organize_evidence": "INSUFFICIENT_EVIDENCE", "explore_perspective": "MISSING_INQUIRY_CONTEXT",
                "form_interpretation": "INSUFFICIENT_EVIDENCE", "challenge_interpretation": "NO_INTERPRETATION",
                "review_blueprint": "NO_BLUEPRINT", "review_lineage": "NO_LINEAGE"}
    for capability, reason in expected.items():
        assert rows[capability]["status"] == "not_yet_available"
        assert rows[capability]["reason_code"] == reason
        assert rows[capability]["prerequisites_missing"]
    assert rows["governing_question"]["availability"] == "available"
    assert rows["governing_question"]["status"] == UNSUPPORTED


def test_question_only_is_readiness_input_without_evidence_or_history():
    rows = _rows(_projection(), governing_question="Why?", perspective_available=True)
    explore = rows["explore_perspective"]
    assert explore["prerequisites_satisfied"] == ["inquiry_context"]
    assert explore["prerequisites_missing"] == ["evidence"]
    assert explore["status"] == "not_yet_available"
    assert explore["evidence_refs"] == [{"basis": "current_state", "input": "governing_question"}]
    assert not any(row["status"] == EXERCISED for row in rows.values())


def test_reader_mark_without_canonical_observation_does_not_enable_formation():
    projection = _projection(_item("source_extractions", "source", raw_text="Evidence"),
                             _item("reader_highlights", "mark", event="current_snapshot", selected_text="Evidence"))
    rows = _rows(projection, perspective_available=True)
    assert rows["record_observation"]["availability"] == "available"
    assert rows["preserve_question"]["status"] == "available"
    assert rows["form_interpretation"]["availability"] == "not_yet_available"
    assert rows["organize_evidence"]["availability"] == "not_yet_available"
    assert rows["read_source"]["status"] == rows["mark_evidence"]["status"] == UNSUPPORTED


def test_observations_enable_formation_but_not_challenge_without_interpretation():
    rows = _rows(_projection(_item("observations", "obs")), perspective_available=True)
    assert rows["form_interpretation"]["status"] == "available"
    assert rows["challenge_interpretation"]["reason_code"] == "NO_INTERPRETATION"
    assert rows["review_lineage"]["availability"] == "available"
    assert rows["review_lineage"]["status"] == UNSUPPORTED


def test_human_interpretation_supports_only_narrow_retained_formation_result():
    projection = _projection(_item("observations", "obs"),
                             _item("interpretations", "interpretation", authorship="human", text="Claim", source="steward-authored"))
    rows = _rows(projection, perspective_available=False)
    # A retained outcome does not erase a separately unavailable current frame.
    assert rows["form_interpretation"]["status"] == EXERCISED
    assert rows["form_interpretation"]["availability"] == "not_yet_available"
    assert rows["form_interpretation"]["availability_reason_code"] == "MISSING_PERSPECTIVE"
    assert rows["challenge_interpretation"]["availability"] == "available"
    assert rows["challenge_interpretation"]["status"] == UNSUPPORTED


def test_counterevidence_and_critic_verdict_do_not_prove_human_challenge():
    rows = _rows(_projection(_item("observations", "against", relevance="contradicts"),
                            _item("proposed_interpretations", "proposal", authorship="model", text="Claim"),
                            _item("critic_reports", "critic", overall_verdict="challenge")))
    assert rows["challenge_interpretation"]["availability"] == "available"
    assert rows["challenge_interpretation"]["status"] == UNSUPPORTED
    assert rows["form_interpretation"]["status"] != EXERCISED


def test_saved_perspective_is_not_a_historical_execution():
    rows = _rows(_projection(_item("observations", "obs"), _item("perspectives", "frame", name="Frame")), governing_question="Why?")
    assert rows["form_interpretation"]["availability"] == "available"
    assert rows["explore_perspective"]["availability"] == "available"
    assert rows["explore_perspective"]["status"] == UNSUPPORTED


def test_missing_or_omitted_coverage_is_unknown_not_known_absence():
    projection = _projection()
    projection["coverage"]["missing_tables"] = ["source_extractions", "observations"]
    projection["coverage"]["omitted"] = {"narrative_blueprints": 1}
    rows = _rows(projection, perspective_available=False)
    for capability in ("read_source", "form_interpretation", "review_blueprint", "review_lineage"):
        assert rows[capability]["status"] == UNSUPPORTED
        assert rows[capability]["reason_code"] == "COVERAGE_UNSUPPORTED"
        assert rows[capability]["coverage_or_unknown_notes"]


def test_two_views_of_one_durable_identity_do_not_satisfy_multiple_evidence():
    projection = _projection(_item("observations", "one"),
                             _item("observations", "one", event="current_snapshot"))
    row = _rows(projection)["organize_evidence"]
    assert row["availability"] == "not_yet_available"
    assert row["reason_code"] == "INSUFFICIENT_EVIDENCE"
    assert {ref["event"] for ref in row["evidence_refs"]} == {"recorded", "current_snapshot"}


def test_current_governing_question_uses_only_existing_singleton_identity():
    projection = _projection(_item("observations", "obs"),
                             _item("workspace_investigation", "other", event="current_snapshot", thesis="Not the current row"))
    assert _rows(projection)["explore_perspective"]["availability"] == "not_yet_available"
    projection["items"].append(_item("workspace_investigation", "current", event="current_snapshot", thesis="Why?"))
    result = _rows(projection)["explore_perspective"]
    assert result["availability"] == "available"
    assert result["status"] == UNSUPPORTED
    assert not any(ref.get("record", {}).get("key") == {"id": "other"} for ref in result["evidence_refs"])


def test_claim_without_text_is_not_a_challenge_target():
    projection = _projection(_item("observations", "obs"),
                             _item("proposed_interpretations", "proposal", text=""))
    result = _rows(projection)["challenge_interpretation"]
    assert result["availability"] == "not_yet_available"
    assert result["reason_code"] == "NO_INTERPRETATION"


@pytest.mark.parametrize("malformation", ["schema", "coverage", "missing_item_field", "duplicate_event", "onboarding", "frame_type"])
def test_unsupported_inputs_are_not_silently_coerced(malformation):
    projection = _projection(_item("observations", "obs"))
    current = {}
    if malformation == "schema":
        projection["schema"] = "hermeneia.study-lineage/v2"
    elif malformation == "coverage":
        del projection["coverage"]
    elif malformation == "missing_item_field":
        del projection["items"][0]["provenance"]
    elif malformation == "duplicate_event":
        projection["items"].append(deepcopy(projection["items"][0]))
    elif malformation == "onboarding":
        current["onboarding_done"] = True
    elif malformation == "frame_type":
        current["perspective_available"] = 1
    with pytest.raises(ValueError):
        evaluate_capabilities(projection, current_state=current)
