"""The method guide is a provider-free read of one eligible study snapshot."""
import json
import socket
import sqlite3

import pytest

from hermeneia.narrative.provider_registry import ProviderRegistry
from hermeneia.perspective_identity import frame_v2_row_from_draft
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_evidence_board_api import _seed_board_db
from test_study_lineage_api import _rollback_journal, _snapshot


ROUTE = "/api/guided-study-cycle"


def _steps(body):
    return {step["step_id"]: step for step in body["steps"]}


def _stored_keys(body):
    return {(ref["record"]["table"], ref["record"]["key"].get("id"))
            for step in body["steps"] for ref in step["evidence_or_state_basis"]
            if ref.get("record")}


def _save_frame(db, name="Saved inquiry frame"):
    row, _ = frame_v2_row_from_draft({
        "label": name, "purpose": "Examine the question against retained evidence.",
        "questions": ["What remains unsupported?"],
        "challenges": ["Keep inference distinct from the passage."],
        "limitations": ["No claim about omitted evidence."],
    }, declared_by="test steward", declared_date="2026-09-01T12:00:00+00:00")
    store = SQLiteStore(db)
    try:
        store.insert_frame_perspective(row)
    finally:
        store.close()
    return row["id"]


def _set_current_question(db):
    connection = sqlite3.connect(db)
    try:
        connection.execute("""INSERT INTO workspace_investigation
            (id, thesis, created_at, updated_at) VALUES ('current', ?, ?, ?)""",
            ("What does the retained passage support?", "2026-09-01T12:00:00+00:00", "2026-09-01T12:00:00+00:00"))
        connection.commit()
    finally:
        connection.close()


def test_guide_get_is_deterministic_read_only_and_provider_free(tmp_path, monkeypatch):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)  # Startup migrations precede the read boundary.
    import hermeneia.web.app as web

    def forbidden(*args, **kwargs):
        pytest.fail("A guide read must not create a store, provider, or network connection")

    monkeypatch.setattr(web, "SQLiteStore", forbidden)
    monkeypatch.setattr(ProviderRegistry, "create", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    real_connect = sqlite3.connect
    traces = []

    def readonly_connect(database, *args, **kwargs):
        assert "mode=ro" in str(database) and kwargs.get("uri") is True
        connection = real_connect(database, *args, **kwargs)
        trace = []
        traces.append(trace)
        connection.set_trace_callback(trace.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", readonly_connect)
    first = client.get(ROUTE)
    second = client.get(ROUTE)
    assert first.status_code == second.status_code == 200
    assert first.data == second.data
    assert first.mimetype == "application/json"
    assert first.headers["Cache-Control"] == "no-store"
    body = first.get_json()
    assert body["schema"] == "hermeneia.guided-study-cycle/v1"
    assert len(body["steps"]) == 11
    assert body["current_frame_selection"] is None
    assert ("reader_highlights", "hl-a") in _stored_keys(body)
    assert ("observations", "obs-a") in _stored_keys(body)
    assert len(traces) == 2
    for trace in traces:
        assert trace[:2] == ["PRAGMA query_only=ON", "BEGIN"]
        assert all(sql.lstrip().upper().startswith(("SELECT", "PRAGMA", "BEGIN")) for sql in trace)
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("existing", [False, True])
def test_empty_or_absent_store_recommends_question_without_creating_history(tmp_path, existing, monkeypatch):
    db = tmp_path / "workspace" / "study.db"
    if existing:
        store = SQLiteStore(db)
        store.close()
    client = create_app(db_path=db).test_client()
    if existing:
        _rollback_journal(db)
    before = _snapshot(tmp_path)
    import hermeneia.web.app as web

    def no_store(*args, **kwargs):
        pytest.fail("Opening an empty guide must not initialize study history")

    monkeypatch.setattr(web, "SQLiteStore", no_store)
    response = client.get(ROUTE)
    repeated = client.get(ROUTE)
    assert response.status_code == repeated.status_code == 200
    assert response.data == repeated.data
    body = response.get_json()
    assert body["recommended_step_id"] == "governing_question"
    assert _steps(body)["governing_question"]["status"] == "ready"
    assert not any(step["status"] == "historically_exercised" for step in body["steps"])
    assert _snapshot(tmp_path) == before
    if not existing:
        assert not db.exists() and not db.parent.exists()


def test_guide_rejects_mutation_methods(tmp_path):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(ROUTE, json={"completed": True}).status_code == 405
    assert _snapshot(tmp_path) == before


def test_guide_reads_only_selected_workspace(tmp_path):
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    _seed_board_db(first)
    _seed_board_db(second)
    connection = sqlite3.connect(second)
    try:
        connection.execute("UPDATE reader_highlights SET id='second-workspace-mark' WHERE id='hl-a'")
        connection.commit()
    finally:
        connection.close()
    first_client = create_app(db_path=first).test_client()
    second_client = create_app(db_path=second).test_client()
    _rollback_journal(first)
    _rollback_journal(second)
    before = _snapshot(tmp_path)
    a, b = first_client.get(ROUTE), second_client.get(ROUTE)
    assert a.status_code == b.status_code == 200
    assert ("reader_highlights", "hl-a") in _stored_keys(a.get_json())
    assert ("reader_highlights", "second-workspace-mark") not in _stored_keys(a.get_json())
    assert ("reader_highlights", "second-workspace-mark") in _stored_keys(b.get_json())
    assert ("reader_highlights", "hl-a") not in _stored_keys(b.get_json())
    assert _snapshot(tmp_path) == before


def test_excluded_parent_and_derived_children_do_not_supply_guide_support(tmp_path):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    connection = sqlite3.connect(db)
    try:
        connection.execute("UPDATE source_documents SET excluded_from_analysis=1 WHERE id='doc-a'")
        connection.execute("""INSERT INTO interpretations
            (id, observation_id, perspective, text, evidential_status, created_at)
            VALUES ('excluded-interpretation', 'obs-a', 'Close Reader', 'Excluded claim',
                    'contested', '2026-09-01T12:00:00+00:00')""")
        sections = json.dumps([{"claim": "Excluded claim", "supporting_observations": ["obs-a"],
                                "supporting_interpretations": ["excluded-interpretation"]}])
        connection.execute("""INSERT INTO narrative_blueprints
            (id, title, thesis, sections, created_at) VALUES (?, ?, ?, ?, ?)""",
            ("excluded-blueprint", "Excluded", "Excluded thesis", sections, "2026-09-01T12:00:00+00:00"))
        connection.commit()
    finally:
        connection.close()
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)
    response = client.get(ROUTE)
    assert response.status_code == 200
    for hidden in (b'"doc-a"', b'"obs-a"', b'"hl-a"', b'"hl-b"',
                   b'"excluded-interpretation"', b'"excluded-blueprint"'):
        assert hidden not in response.data
    assert ("reader_highlights", "hl-c") in _stored_keys(response.get_json())
    steps = _steps(response.get_json())
    assert steps["form_interpretation"]["status"] != "historically_exercised"
    assert steps["review_blueprint"]["status"] not in ("currently_supported", "historically_exercised")
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("query", [
    "completed=true", "governing_question=Invented", "perspective_available=true",
    "perspective_kind=builtin", "perspective_id=close-reader",
    "perspective_kind=unknown&perspective_id=close-reader",
    "perspective_kind=builtin&perspective_id=missing",
    "perspective_kind=saved&perspective_id=' OR 1=1 --",
    "perspective_kind=saved&perspective_id=close-reader",
    "perspective_kind=builtin&perspective_id=",
    "perspective_kind=builtin&perspective_kind=builtin&perspective_id=close-reader",
    "perspective_kind=builtin&perspective_id=close-reader&perspective_id=skeptical-reader",
])
def test_unvalidated_current_or_historical_inputs_are_refused(query, tmp_path):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)
    response = client.get(f"{ROUTE}?{query}")
    assert response.status_code == 400
    assert set(response.get_json()) == {"error"}
    assert _snapshot(tmp_path) == before


def test_builtin_selection_supports_current_frame_without_execution_history(tmp_path):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    _set_current_question(db)
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)
    response = client.get(ROUTE, query_string={"perspective_kind": "builtin", "perspective_id": "close-reader"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["current_frame_selection"] == {"kind": "builtin", "id": "close-reader", "basis": "current_ui_selection"}
    step = _steps(body)["explore_perspective"]
    assert step["status"] == "currently_supported"
    assert step["history_support"]["status"] == "unsupported"
    assert step["evidence_or_state_basis"] == [{"basis": "current_state", "input": "perspective_available"}]
    assert not any(row["status"] == "historically_exercised" for row in body["steps"])
    assert _snapshot(tmp_path) == before


def test_valid_frame_selection_does_not_bypass_missing_question_readiness(tmp_path):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)
    response = client.get(ROUTE, query_string={"perspective_kind": "builtin", "perspective_id": "close-reader"})
    assert response.status_code == 200
    step = _steps(response.get_json())["explore_perspective"]
    assert step["availability"] == "not_yet_available"
    assert step["status"] == "not_ready"
    assert step["history_support"]["status"] == "unsupported"
    assert response.get_json()["recommended_step_id"] == "governing_question"
    assert _snapshot(tmp_path) == before


def test_saved_selection_uses_exact_eligible_durable_frame(tmp_path):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    _set_current_question(db)
    frame_id = _save_frame(db)
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)
    response = client.get(ROUTE, query_string={"perspective_kind": "saved", "perspective_id": frame_id})
    assert response.status_code == 200
    body = response.get_json()
    assert body["current_frame_selection"] == {"kind": "saved", "id": frame_id, "basis": "current_ui_selection"}
    assert _steps(body)["explore_perspective"]["history_support"]["status"] == "unsupported"
    assert _snapshot(tmp_path) == before


def test_legacy_label_is_not_validated_as_current_saved_frame(tmp_path):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    store = SQLiteStore(db)
    try:
        store.register_perspective({"id": "old-label", "name": "Legacy label", "description": "", "created_at": "2026-09-01T12:00:00+00:00"})
    finally:
        store.close()
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)
    response = client.get(ROUTE, query_string={"perspective_kind": "saved", "perspective_id": "old-label"})
    assert response.status_code == 400
    assert set(response.get_json()) == {"error"}
    assert _snapshot(tmp_path) == before


def test_unreadable_store_returns_no_partial_guide_or_inferred_progress(tmp_path):
    db = tmp_path / "study.db"
    _seed_board_db(db)
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    db.write_bytes(b"not a SQLite database")  # Corrupt after existing startup boundary.
    before = _snapshot(tmp_path)
    response = client.get(ROUTE)
    assert response.status_code == 409
    assert set(response.get_json()) == {"error"}
    assert "no progress was inferred" in response.get_json()["error"]
    assert _snapshot(tmp_path) == before
