"""Current study guidance consumes capabilities without manufacturing history."""
from copy import deepcopy
import json
import socket
import sqlite3

import pytest

from hermeneia.capabilities import evaluate_capabilities, load_capability_registry
from hermeneia.guided_study_cycle import project_guided_study_cycle
from hermeneia.study_lineage import project_study_lineage, serialize_projection
from test_study_lineage import TIME, _evidence, _model_records, _table


CYCLE = (
    "governing_question", "read_source", "mark_evidence", "record_observation",
    "preserve_question", "organize_evidence", "explore_perspective",
    "form_interpretation", "challenge_interpretation", "review_blueprint", "review_lineage",
)
EXERCISED = "already_exercised_under_supported_evidence"


def _rows(projection):
    return {row["capability_id"]: row for row in projection["steps"]}


def _question(conn):
    _table(conn, "workspace_investigation", [{
        "id": "current", "thesis": "What does the evidence permit?", "updated_at": TIME,
    }])


def _marks(conn, *, grouped=False):
    _table(conn, "reader_highlights", [{
        "id": identifier, "source_document_id": "doc", "selected_text": "Same text",
        "theme_bucket": "working label" if grouped else None,
        "evidence_bucket": None, "updated_at": TIME,
    } for identifier in ("mark-a", "mark-b")])


def _preserved_question(conn):
    _table(conn, "inquiry_notes", [{
        "id": "question", "observation_id": "same", "question_text": "What argues against it?",
        "created_at": TIME,
    }])


def _frame(conn):
    _table(conn, "perspectives", [{"id": "frame", "name": "A named frame", "created_at": TIME}])


def _blueprint(conn):
    _table(conn, "narrative_blueprints", [{
        "id": "blueprint", "thesis": "A retained claim", "source": "steward-authored",
        "sections": '[{"supporting_observations":["same"],"supporting_interpretations":["accepted"]}]',
        "created_at": TIME,
    }])


def _project(conn, **current):
    return project_guided_study_cycle(project_study_lineage(conn), current_state=current)


def _record_refs(value):
    """Find actual typed references without imposing a presentation wrapper."""
    if isinstance(value, dict):
        if isinstance(value.get("record"), dict) and "table" in value["record"]:
            yield value
        for item in value.values():
            yield from _record_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _record_refs(item)


def test_cycle_has_exact_ordered_registered_capabilities_and_explanations():
    conn = sqlite3.connect(":memory:")
    result = _project(conn)
    assert result["schema"] == "hermeneia.guided-study-cycle/v1"
    assert tuple(row["capability_id"] for row in result["steps"]) == CYCLE
    assert tuple(row["ordinal"] for row in result["steps"]) == tuple(range(1, 12))
    assert len({row["step_id"] for row in result["steps"]}) == 11
    definitions = {row["capability_id"]: row for row in load_capability_registry()["capabilities"]}
    for row in result["steps"]:
        assert row["title"]
        assert row["why_it_matters"]
        assert row["recommended_action"]
        assert row["target_surface"]
        assert row["status"] in {"ready", "not_ready", "currently_supported", "historically_exercised", "unknown"}
        assert row["capability_id"] in definitions
        assert row["history_support"]["status"] in {"supported", "unsupported"}
        assert row["history_support"]["reason"]


def test_cycle_preserves_all_p1_readiness_and_historical_statuses():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    _question(conn)
    _preserved_question(conn)
    lineage = project_study_lineage(conn)
    current = {"perspective_available": True}
    capabilities = {row["capability_id"]: row for row in evaluate_capabilities(
        lineage, current_state=current,
    )["capabilities"]}
    guided = _rows(project_guided_study_cycle(lineage, current_state=current))
    for identifier, capability in capabilities.items():
        assert guided[identifier]["capability_status"] == capability["status"]
        assert guided[identifier]["availability"] == capability["availability"]
        assert guided[identifier]["history_support"]["status"] == (
            "supported" if capability["status"] == EXERCISED else "unsupported"
        )


def test_a_empty_workspace_recommends_governing_question():
    conn = sqlite3.connect(":memory:")
    result = _project(conn)
    assert result["recommended_step_id"] == _rows(result)["governing_question"]["step_id"]
    assert _rows(result)["governing_question"]["availability"] == "available"
    assert "present now" not in _rows(result)["governing_question"]["status_reason"]
    assert _rows(result)["governing_question"]["history_support"]["status"] == "unsupported"


def test_b_current_question_without_source_recommends_source_attention():
    conn = sqlite3.connect(":memory:")
    _question(conn)
    result = _project(conn)
    rows = _rows(result)
    assert rows["governing_question"]["status"] == "currently_supported"
    assert result["recommended_step_id"] == rows["read_source"]["step_id"]
    assert rows["read_source"]["availability"] != "available"
    assert rows["read_source"]["status_reason"]
    assert rows["governing_question"]["history_support"]["status"] == "unsupported"


def test_imported_source_and_compiler_units_do_not_replace_reader_attention():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _question(conn)
    result = _project(conn)
    rows = _rows(result)
    assert result["recommended_step_id"] == rows["read_source"]["step_id"]
    assert rows["read_source"]["availability"] == "available"
    assert rows["read_source"]["status"] == "ready"
    assert rows["mark_evidence"]["status"] == "ready"
    assert rows["read_source"]["history_support"]["status"] == "unsupported"
    assert rows["mark_evidence"]["history_support"]["status"] == "unsupported"
    assert rows["record_observation"]["history_support"]["status"] == "unsupported"


def test_preserved_inquiry_does_not_become_workspace_governing_question():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _preserved_question(conn)
    result = _project(conn)
    assert result["recommended_step_id"] == _rows(result)["governing_question"]["step_id"]
    assert _rows(result)["governing_question"]["status"] != "currently_supported"
    assert _rows(result)["preserve_question"]["history_support"]["status"] == "supported"


def test_explicit_current_question_overrides_snapshot_without_rewriting_it():
    conn = sqlite3.connect(":memory:")
    _question(conn)
    before = tuple(conn.iterdump())
    retained = _project(conn)
    overridden = _project(conn, governing_question=None)
    assert _rows(retained)["governing_question"]["status"] == "currently_supported"
    assert _rows(overridden)["governing_question"]["status"] != "currently_supported"
    assert overridden["recommended_step_id"] == _rows(overridden)["governing_question"]["step_id"]
    assert tuple(conn.iterdump()) == before


def test_c_marks_without_observations_recommend_observation_without_mark_history():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    # Preserve a real schema with known absence rather than fabricate a mark's
    # canonical Observation or inflate missing-table coverage into absence.
    conn.execute("DELETE FROM observations")
    _marks(conn)
    _question(conn)
    result = _project(conn)
    rows = _rows(result)
    assert result["recommended_step_id"] == rows["record_observation"]["step_id"]
    assert rows["record_observation"]["availability"] == "available"
    assert rows["mark_evidence"]["status"] == "currently_supported"
    assert rows["mark_evidence"]["history_support"]["status"] == "unsupported"
    assert rows["read_source"]["history_support"]["status"] == "unsupported"


def test_d_observations_and_retained_question_recommend_organization():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _marks(conn)
    _question(conn)
    _preserved_question(conn)
    result = _project(conn)
    rows = _rows(result)
    assert result["recommended_step_id"] == rows["organize_evidence"]["step_id"]
    assert rows["organize_evidence"]["availability"] == "available"
    assert rows["record_observation"]["history_support"]["status"] == "unsupported"
    assert rows["preserve_question"]["history_support"]["status"] == "supported"


def test_e_current_group_labels_recommend_perspective_but_never_prove_a_run():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _marks(conn, grouped=True)
    _question(conn)
    _preserved_question(conn)
    result = _project(conn)
    rows = _rows(result)
    assert result["recommended_step_id"] == rows["explore_perspective"]["step_id"]
    assert rows["explore_perspective"]["availability"] == "available"
    assert rows["organize_evidence"]["status"] == "currently_supported"
    assert rows["organize_evidence"]["history_support"]["status"] == "unsupported"
    assert rows["explore_perspective"]["history_support"]["status"] == "unsupported"


def test_saved_frame_without_interpretation_surfaces_interpretation_work():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _marks(conn, grouped=True)
    _question(conn)
    _preserved_question(conn)
    _frame(conn)
    result = _project(conn)
    rows = _rows(result)
    assert result["recommended_step_id"] == rows["form_interpretation"]["step_id"]
    assert rows["form_interpretation"]["availability"] == "available"
    assert rows["explore_perspective"]["status"] == "currently_supported"
    assert rows["explore_perspective"]["history_support"]["status"] == "unsupported"


def test_f_retained_supported_interpretation_makes_challenge_appropriate():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    _question(conn)
    # Earlier transient questions/grouping need not be invented to explain
    # the appropriate next method for an existing accepted Interpretation.
    result = _project(conn)
    rows = _rows(result)
    assert result["recommended_step_id"] == rows["challenge_interpretation"]["step_id"]
    assert rows["form_interpretation"]["history_support"]["status"] == "supported"
    assert rows["challenge_interpretation"]["availability"] == "available"
    assert rows["challenge_interpretation"]["history_support"]["status"] == "unsupported"
    assert result["recommendation_reason"]


def test_g_saved_blueprint_does_not_establish_review_or_revision_cause():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    _question(conn)
    _blueprint(conn)
    row = _rows(_project(conn))["review_blueprint"]
    assert row["status"] == "currently_supported"
    assert row["availability"] == "available"
    assert row["history_support"]["status"] == "unsupported"
    assert row["capability_status"] != EXERCISED


def test_h_advanced_current_material_recommends_lineage_without_full_cycle():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    _question(conn)
    _preserved_question(conn)
    _marks(conn, grouped=True)
    _frame(conn)
    _blueprint(conn)
    result = _project(conn)
    rows = _rows(result)
    assert result["recommended_step_id"] == rows["review_lineage"]["step_id"]
    assert rows["review_lineage"]["history_support"]["status"] == "unsupported"
    assert rows["challenge_interpretation"]["history_support"]["status"] == "unsupported"
    assert rows["review_blueprint"]["history_support"]["status"] == "unsupported"
    assert "award" not in result and "achievement" not in result and "completed" not in result


def test_critic_finding_remains_output_not_human_challenge_history():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    _question(conn)
    _table(conn, "critic_reports", [{
        "id": "critic", "proposal_id": "proposal", "observation_id": "same",
        "overall_verdict": "challenge", "generated_at": TIME,
    }])
    row = _rows(_project(conn))["challenge_interpretation"]
    assert row["status"] in {"ready", "currently_supported"}
    assert row["history_support"]["status"] == "unsupported"
    assert row["capability_status"] != EXERCISED


def test_missing_history_is_not_failed_and_does_not_block_ready_perspective():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    result = _project(conn, governing_question="Why?")
    row = _rows(result)["explore_perspective"]
    assert row["availability"] == "available"
    assert row["history_support"]["status"] == "unsupported"
    assert row["status"] in {"ready", "currently_supported"}
    assert all(step["status"] not in {"failed", "fail", "complete", "completed"} for step in result["steps"])


def test_registry_prerequisites_and_prose_remain_authoritative():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _marks(conn)
    _question(conn)
    lineage = project_study_lineage(conn)
    registry = load_capability_registry()
    definition = next(row for row in registry["capabilities"] if row["capability_id"] == "organize_evidence")
    definition["definition_version"] = registry["registry_version"] = "1.0.1"
    definition["prerequisites"][0]["minimum"] = 999
    definition["purpose"] = "Definition-owned explanation."
    direct = {row["capability_id"]: row for row in evaluate_capabilities(lineage, registry)["capabilities"]}
    result = project_guided_study_cycle(lineage, registry)
    row = _rows(result)["organize_evidence"]
    assert row["availability"] == direct["organize_evidence"]["availability"] == "not_yet_available"
    assert row["capability_status"] == direct["organize_evidence"]["status"]
    assert "Definition-owned explanation." in json.dumps(row, ensure_ascii=False)


def test_cycle_retains_typed_identity_and_exact_unknown_provenance():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _question(conn)
    _table(conn, "reader_highlights", [{
        "id": "same", "source_document_id": "doc", "selected_text": "Same text", "updated_at": TIME,
    }])
    lineage = project_study_lineage(conn)
    indexed = {json.dumps(item["record"], sort_keys=True): item for item in lineage["items"]}
    row = _rows(project_guided_study_cycle(lineage))["organize_evidence"]
    refs = list(_record_refs(row["evidence_or_state_basis"]))
    matching = [ref for ref in refs if ref["record"]["key"] == {"id": "same"}]
    assert {ref["record"]["table"] for ref in matching} == {"observations", "reader_highlights"}
    for ref in refs:
        item = indexed[json.dumps(ref["record"], sort_keys=True)]
        for field in ("record", "event", "authorship", "timestamp", "provenance"):
            assert ref[field] == item[field]


def test_excluded_records_cannot_supply_current_support_or_history():
    conn = sqlite3.connect(":memory:")
    _evidence(conn, excluded=True)
    _model_records(conn)
    _marks(conn, grouped=True)
    _preserved_question(conn)
    _blueprint(conn)
    result = _project(conn, governing_question="An explicit current question")
    for identifier in CYCLE[1:]:
        row = _rows(result)[identifier]
        assert row["status"] not in {"currently_supported", "historically_exercised"}
        assert row["history_support"]["status"] == "unsupported"
        assert list(_record_refs(row["evidence_or_state_basis"])) == []


@pytest.mark.parametrize("current", [
    {"completed": {"read_source": True}}, {"finished": True}, {"paused": True},
    {"governing_question": "Why?", "full_cycle": True},
])
def test_presentation_preferences_cannot_enter_study_evaluation(current):
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError):
        _project(conn, **current)


def test_guidance_is_deterministic_read_only_and_provider_free(tmp_path, monkeypatch):
    db = tmp_path / "synthetic-study.db"
    conn = sqlite3.connect(db)
    _evidence(conn)
    _model_records(conn)
    _question(conn)
    _marks(conn, grouped=True)
    conn.commit()
    before_dump = tuple(conn.iterdump())
    conn.close()
    before = db.read_bytes(), db.stat().st_mtime_ns
    ro = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    ro.execute("PRAGMA query_only=ON")
    ro.execute("BEGIN")
    lineage = project_study_lineage(ro)
    registry = load_capability_registry()
    current = {"perspective_available": True}
    input_before = deepcopy((lineage, registry, current))

    def forbidden(*args, **kwargs):
        raise AssertionError("Guidance must not connect to a database or provider")

    with monkeypatch.context() as guard:
        guard.setattr(sqlite3, "connect", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        guard.setattr(socket.socket, "connect", forbidden)
        first = project_guided_study_cycle(lineage, registry, current_state=current)
        second = project_guided_study_cycle(lineage, registry, current_state=current)
    assert first == second
    assert (lineage, registry, current) == input_before
    shuffled = deepcopy(lineage)
    shuffled["items"].reverse()
    assert first == project_guided_study_cycle(shuffled, registry, current_state=current)
    assert tuple(ro.iterdump()) == before_dump
    assert serialize_projection(lineage) == serialize_projection(input_before[0])
    ro.close()
    assert (db.read_bytes(), db.stat().st_mtime_ns) == before
