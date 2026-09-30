"""Capability evaluation consumes Lineage without inventing study history."""
import copy
import json
import socket
import sqlite3

import pytest

from hermeneia.capabilities import evaluate_capabilities, load_capability_registry
from hermeneia.study_lineage import project_study_lineage, serialize_projection
from test_study_lineage import TIME, _evidence, _model_records, _table


EXERCISED = "already_exercised_under_supported_evidence"
UNSUPPORTED = "unsupported_due_to_missing_history"


def _rows(result):
    return {row["capability_id"]: row for row in result["capabilities"]}


def _stored_refs(row):
    return [ref for ref in row["evidence_refs"] if ref.get("record")]


def _assert_exact_refs(row, projection):
    """A capability can cite a view; it cannot replace its provenance."""
    indexed = {
        (json.dumps(item["record"], sort_keys=True), item["event"]): item
        for item in projection["items"]
    }
    for ref in _stored_refs(row):
        item = indexed[(json.dumps(ref["record"], sort_keys=True), ref["event"])]
        for field in ("record", "event", "authorship", "timestamp", "provenance"):
            assert ref[field] == item[field]


def test_actual_lineage_evaluation_is_read_only_and_provider_free(tmp_path, monkeypatch):
    db = tmp_path / "study.db"
    conn = sqlite3.connect(db)
    _evidence(conn)
    _model_records(conn)
    _table(conn, "inquiry_notes", [{
        "id": "question", "observation_id": "same", "question_text": "What supports this?",
        "created_at": TIME,
    }])
    conn.commit()
    before_dump = tuple(conn.iterdump())
    conn.close()
    before_bytes = db.read_bytes()
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    ro.execute("PRAGMA query_only=ON")
    ro.execute("BEGIN")
    projection = project_study_lineage(ro)
    projection_before = serialize_projection(projection)
    registry = load_capability_registry()
    registry_before = copy.deepcopy(registry)
    current = {"governing_question": "What changed?", "perspective_available": True}
    current_before = copy.deepcopy(current)

    def forbidden(*args, **kwargs):
        raise AssertionError("Capability evaluation must not open a database or network connection")

    with monkeypatch.context() as guard:
        guard.setattr(sqlite3, "connect", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        guard.setattr(socket.socket, "connect", forbidden)
        first = evaluate_capabilities(projection, registry, current_state=current)
        second = evaluate_capabilities(projection, registry, current_state=current)

    assert first == second
    assert serialize_projection(projection) == projection_before
    assert registry == registry_before
    assert current == current_before
    assert tuple(ro.iterdump()) == before_dump
    ro.close()
    assert db.read_bytes() == before_bytes


def test_accepted_model_interpretation_cites_existing_acceptance_provenance():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    conn.execute("DELETE FROM interpretations WHERE id != 'accepted'")
    projection = project_study_lineage(conn)
    row = _rows(evaluate_capabilities(
        projection, current_state={"perspective_available": True},
    ))["form_interpretation"]
    assert row["status"] == EXERCISED
    refs = _stored_refs(row)
    accepted = next(ref for ref in refs if ref["record"] == {
        "table": "interpretations", "key": {"id": "accepted"},
    })
    assert accepted["authorship"] == "accepted_model"
    ai = accepted["provenance"]["records"][0]["record_data"]
    assert ai["generating_model"] == "recorded-model"
    assert ai["model_version"] == "historic-v1"
    assert ai["accepting_steward"] == "steward"
    _assert_exact_refs(row, projection)


def test_unknown_interpretation_origin_does_not_gain_historical_completion():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _table(conn, "interpretations", [{
        "id": "unknown", "observation_id": "same", "text": "An interpretation",
        "source": "ai-accepted", "ai_provenance_id": "missing", "created_at": TIME,
        "evidence_observation_ids": "[]",
    }])
    projection = project_study_lineage(conn)
    row = _rows(evaluate_capabilities(
        projection, current_state={"perspective_available": True},
    ))["form_interpretation"]
    assert row["availability"] == "available"
    assert row["status"] == UNSUPPORTED
    assert row["coverage_or_unknown_notes"]
    for ref in _stored_refs(row):
        if ref["record"]["table"] == "interpretations":
            assert ref["authorship"] == "unknown"
    _assert_exact_refs(row, projection)


def test_individually_identified_inquiry_note_is_supported_without_inventing_authorship():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _table(conn, "inquiry_notes", [{
        "id": "question", "observation_id": "same", "question_text": "What is missing?",
        "created_at": TIME,
    }])
    projection = project_study_lineage(conn)
    row = _rows(evaluate_capabilities(projection))["preserve_question"]
    assert row["status"] == EXERCISED
    note = next(ref for ref in _stored_refs(row)
                if ref["record"]["table"] == "inquiry_notes")
    assert note["record"]["key"] == {"id": "question"}
    assert note["authorship"] == "unknown"
    _assert_exact_refs(row, projection)


def test_reader_snapshot_fields_and_compiler_observations_do_not_prove_exercise():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _table(conn, "reader_highlights", [{
        "id": "mark", "source_document_id": "doc", "selected_text": "Same text",
        "question_text": "A mutable question?", "status": "promoted_to_observation",
        "observation_id": "same", "theme_bucket": "working label", "relevance": "contradicts",
        "created_at": "2000-01-01T00:00:00Z", "updated_at": TIME,
    }])
    _table(conn, "workspace_investigation", [{
        "id": "current", "thesis": "A changed governing question?", "updated_at": TIME,
    }])
    projection = project_study_lineage(conn)
    rows = _rows(evaluate_capabilities(projection))
    for capability in ("governing_question", "mark_evidence", "record_observation",
                       "preserve_question", "organize_evidence", "read_source"):
        assert rows[capability]["availability"] == "available"
        assert rows[capability]["status"] == UNSUPPORTED
        _assert_exact_refs(rows[capability], projection)
    assert not any(row["status"] == EXERCISED for row in rows.values())


def test_equal_ids_across_record_types_remain_distinct_evidence():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _table(conn, "reader_highlights", [{
        "id": "same", "source_document_id": "doc", "selected_text": "Same text",
        "updated_at": TIME,
    }])
    projection = project_study_lineage(conn)
    row = _rows(evaluate_capabilities(projection))["organize_evidence"]
    assert row["availability"] == "available"
    matching = [ref for ref in _stored_refs(row) if ref["record"]["key"] == {"id": "same"}]
    assert {ref["record"]["table"] for ref in matching} == {"observations", "reader_highlights"}
    _assert_exact_refs(row, projection)


def test_excluded_parent_closure_cannot_supply_readiness_or_historical_evidence():
    conn = sqlite3.connect(":memory:")
    _evidence(conn, excluded=True)
    _model_records(conn)
    _table(conn, "reader_highlights", [{
        "id": "hidden-mark", "source_document_id": "doc", "selected_text": "Private",
        "updated_at": TIME,
    }])
    _table(conn, "inquiry_notes", [{
        "id": "hidden-question", "observation_id": "same", "question_text": "Private?",
        "created_at": TIME,
    }])
    _table(conn, "narrative_blueprints", [{
        "id": "hidden-blueprint", "thesis": "Private claim", "created_at": TIME,
        "sections": '[{"supporting_observations":["same"],"supporting_interpretations":["accepted"]}]',
    }])
    projection = project_study_lineage(conn)
    assert projection["items"] == []
    rows = _rows(evaluate_capabilities(projection))
    for capability in ("read_source", "mark_evidence", "record_observation", "preserve_question",
                       "organize_evidence", "form_interpretation", "challenge_interpretation",
                       "review_blueprint", "review_lineage"):
        assert rows[capability]["availability"] != "available"
        assert rows[capability]["status"] != EXERCISED
        assert _stored_refs(rows[capability]) == []


def test_old_missing_schema_refuses_evidence_claims_without_migration():
    conn = sqlite3.connect(":memory:")
    before = tuple(conn.iterdump())
    projection = project_study_lineage(conn)
    rows = _rows(evaluate_capabilities(projection))
    for capability in ("read_source", "mark_evidence", "record_observation", "preserve_question",
                       "organize_evidence", "form_interpretation", "challenge_interpretation",
                       "review_blueprint"):
        assert rows[capability]["status"] == UNSUPPORTED
        assert rows[capability]["coverage_or_unknown_notes"]
    assert tuple(conn.iterdump()) == before


def test_proposal_decision_and_critic_report_do_not_become_canonical_or_human_challenge():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    conn.execute("DROP TABLE interpretations")
    _table(conn, "critic_reports", [{
        "id": "report", "proposal_id": "proposal", "observation_id": "same",
        "policy": "conservative", "overall_verdict": "challenge", "generated_at": TIME,
    }])
    projection = project_study_lineage(conn)
    rows = _rows(evaluate_capabilities(projection, current_state={"perspective_available": True}))
    assert rows["form_interpretation"]["status"] == UNSUPPORTED
    assert rows["challenge_interpretation"]["availability"] == "available"
    assert rows["challenge_interpretation"]["status"] == UNSUPPORTED
    assert not any(ref["record"]["table"] == "interpretations"
                   for row in rows.values() for ref in _stored_refs(row))
    _assert_exact_refs(rows["challenge_interpretation"], projection)


def test_current_frame_and_question_change_readiness_without_creating_history():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    projection = project_study_lineage(conn)
    before = serialize_projection(projection)
    rows = _rows(evaluate_capabilities(projection, current_state={
        "governing_question": "What does the evidence permit?", "perspective_available": True,
    }))
    for capability in ("explore_perspective", "form_interpretation"):
        row = rows[capability]
        assert row["availability"] == "available"
        assert row["status"] == UNSUPPORTED
        assert any(ref.get("basis") == "current_state" for ref in row["evidence_refs"])
        _assert_exact_refs(row, projection)
    assert serialize_projection(projection) == before
    with pytest.raises(ValueError):
        evaluate_capabilities(projection, current_state={"historically_exercised": True})


def test_saved_blueprint_and_lineage_are_review_opportunities_not_review_history():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _table(conn, "narrative_blueprints", [{
        "id": "blueprint", "title": "Saved argument", "thesis": "Claim", "source": "steward-authored",
        "sections": '[{"supporting_observations":["same"],"supporting_interpretations":[]}]',
        "created_at": TIME,
    }])
    projection = project_study_lineage(conn)
    rows = _rows(evaluate_capabilities(projection))
    for capability in ("review_blueprint", "review_lineage"):
        assert rows[capability]["availability"] == "available"
        assert rows[capability]["status"] == UNSUPPORTED
        _assert_exact_refs(rows[capability], projection)


def test_inquiry_table_missing_identity_is_unknown_history_not_known_absence():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _table(conn, "inquiry_notes", [{
        "observation_id": "same", "question_text": "What is missing?", "created_at": TIME,
    }])
    projection = project_study_lineage(conn)
    assert "id" in projection["coverage"]["missing_columns"]["inquiry_notes"]
    assert not any(item["record"]["table"] == "inquiry_notes" for item in projection["items"])
    row = _rows(evaluate_capabilities(projection))["preserve_question"]
    assert row["availability"] == "available"
    assert row["status"] == UNSUPPORTED
    assert any("inquiry_notes: id" in note for note in row["coverage_or_unknown_notes"])


@pytest.mark.parametrize("name", [None, ""])
def test_saved_perspective_without_named_frame_cannot_supply_readiness(name):
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    row = {"id": "frame", "created_at": TIME}
    if name is not None:
        row["name"] = name
    _table(conn, "perspectives", [row])
    projection = project_study_lineage(conn)
    result = _rows(evaluate_capabilities(projection))["form_interpretation"]
    assert result["availability"] != "available"
    assert "perspective_frame" in result["prerequisites_missing"]
    if name is None:
        assert result["availability_reason_code"] == "COVERAGE_UNSUPPORTED"
    else:
        assert result["availability_reason_code"] == "MISSING_PERSPECTIVE"
