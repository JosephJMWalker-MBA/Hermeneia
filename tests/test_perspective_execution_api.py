"""Explicit human retention binds server-captured single-Perspective runs."""
from __future__ import annotations

import hashlib
import sqlite3

import pytest

from hermeneia.narrative.provider_registry import ProviderRegistry
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_e10_vertical_slice_api import (
    _CapturingProvider, _install_fake_ollama, _ollama_registry,
    _reader_selection_scope, _seed_perspective_scope_source,
)
from test_study_lineage_api import _rollback_journal, _snapshot


TABLE = "perspective_execution_receipts"
OUTPUT = "  Exact proposed reading — not an accepted Interpretation.\n"


@pytest.fixture
def study(tmp_path, monkeypatch):
    _install_fake_ollama(monkeypatch, ["qwen2.5:0.5b"])
    _CapturingProvider.render_responses = [OUTPUT] * 120
    db = tmp_path / "study.db"
    _seed_perspective_scope_source(db)
    app = create_app(db_path=db, provider_registry=_ollama_registry())
    app.testing = True
    return db, app.test_client()


def _run(client, **overrides):
    payload = {
        "perspective_id": "close-reader", "question": "What remains uncertain?",
        "model": "qwen2.5:0.5b", "scope": _reader_selection_scope(),
    }
    payload.update(overrides)
    result = client.post("/api/perspective/run", json=payload)
    assert result.status_code == 201, result.get_json()
    return result.get_json()


def _retain(client, run):
    return client.post(f"/api/perspective/executions/{run['run_id']}/retain", json={"decision": "retain"})


def _count(db):
    with sqlite3.connect(db) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]


def test_successful_run_is_transient_until_explicit_keep(study):
    db, client = study
    _rollback_journal(db)
    before = _snapshot(db.parent)
    transient = _run(client)
    assert transient["canonical_status"] == "not_persisted"
    assert transient["retention"] == {
        "supported": True, "state": "transient",
        "reason": "Keep explicitly to retain this exact execution in the study.",
    }
    assert transient["run_id"]
    assert _count(db) == 0
    assert _snapshot(db.parent) == before
    retained = _retain(client, transient)
    assert retained.status_code == 201
    receipt = retained.get_json()
    assert _count(db) == 1
    assert receipt["run"]["run_id"] == transient["run_id"]
    assert receipt["retention"]["decision"] == "retain"
    assert receipt["retention"]["actor"] == "local_steward"
    assert receipt["retention"]["actor_identity"] == "unknown"


def test_receipt_preserves_effective_inputs_prompt_output_and_execution(study):
    _db, client = study
    transient = _run(client, question="  What remains uncertain? \n")
    receipt = _retain(client, transient).get_json()
    run = receipt["run"]
    assert run["question"] == transient["question"] == "What remains uncertain?"
    assert run["scope_receipt"] == transient["scope_receipt"]
    assert run["execution"] == transient["execution"]
    assert run["response"] == transient["response"] == OUTPUT
    assert run["prompt"] == _CapturingProvider.render_prompts[-1]
    assert run["prompt_version"] == "perspective-run/v1"
    assert run["perspective"]["id"] == "close-reader"
    assert run["perspective"]["version"] == "1"
    assert run["perspective"]["origin"] == "built_in"
    assert run["perspective"]["definition"]["label"] == "Close Reader"
    assert run["execution"]["model_id"] == "qwen2.5:0.5b"
    assert run["execution"]["selection_source"] == "per_run"
    assert run["created_at"] <= run["completed_at"] <= receipt["retention"]["retained_at"]
    for field in ("question", "prompt", "response"):
        assert run[field + "_sha256"] == "sha256:" + hashlib.sha256(run[field].encode("utf-8")).hexdigest()


def test_adapter_stub_provenance_is_preserved_without_fabricating_a_model_version(study, monkeypatch):
    _db, client = study
    config = {"provider": "deterministic_test_stub", "sdk_version": None,
              "request_schema_version": "test-v1", "deterministic": True}
    monkeypatch.setattr(_CapturingProvider, "execution_config", lambda self: dict(config))
    receipt = _retain(client, _run(client)).get_json()
    execution = receipt["run"]["execution"]
    assert execution["provider"] == "deterministic_test_stub"
    assert execution["deterministic"] is True
    assert execution["sdk_version"] is None
    assert execution["provider_id"] == "ollama-local"  # Requested registry adapter, not invented provider facts.
    assert "model_version" not in execution and "temperature" not in execution


def test_explicit_discard_creates_no_durable_positive_or_negative_history(study):
    db, client = study
    run = _run(client)
    _rollback_journal(db)
    before = _snapshot(db.parent)
    discarded = client.post(f"/api/perspective/executions/{run['run_id']}/discard", json={"decision": "discard"})
    assert discarded.status_code == 200
    assert discarded.get_json()["canonical_status"] == "not_persisted"
    assert _count(db) == 0 and _snapshot(db.parent) == before
    assert _retain(client, run).status_code == 404


def test_repeat_keep_is_idempotent_and_retained_history_cannot_be_discarded(study):
    db, client = study
    run = _run(client)
    first, second = _retain(client, run), _retain(client, run)
    assert first.status_code == 201 and second.status_code == 200
    assert first.get_json() == second.get_json()
    assert _count(db) == 1
    result = client.post(f"/api/perspective/executions/{run['run_id']}/discard", json={"decision": "discard"})
    assert result.status_code == 409 and _count(db) == 1


@pytest.mark.parametrize("body", [None, {}, {"decision": "accept"}, {"decision": "discard"},
                                    {"decision": "retain", "response": "fabricated output"},
                                    {"decision": "retain", "actor": "invented individual"}])
def test_keep_rejects_missing_decision_and_client_execution_reposts(study, body):
    db, client = study
    run = _run(client)
    response = client.post(f"/api/perspective/executions/{run['run_id']}/retain", json=body)
    assert response.status_code == 400 and _count(db) == 0


def test_client_mutation_of_response_cannot_rewrite_server_owned_execution(study):
    _db, client = study
    run = _run(client)
    run["response"] = "A locally edited display must not become the executed output."
    run["question"] = "Later question"
    run["scope_receipt"]["primary"]["text"] = "Later source"
    receipt = _retain(client, run).get_json()
    assert receipt["run"]["response"] == OUTPUT
    assert receipt["run"]["question"] == "What remains uncertain?"
    assert receipt["run"]["scope_receipt"]["primary"]["text"] == "Only this selected passage participates."


def test_saved_revision_and_original_question_survive_later_control_changes(study):
    db, client = study
    draft = {"label": "Trust reader", "purpose": "Examine trust.", "questions": ["Who trusts whom?"]}
    saved = client.post("/api/perspective/saved", json={"perspective_draft": draft, "declared_by": "Local test steward"}).get_json()
    run = _run(client, perspective_id=None, saved_perspective_id=saved["id"], question="Original exact question?")
    revised = client.post(f"/api/perspective/saved/{saved['id']}/revisions", json={
        "perspective_draft": {**draft, "purpose": "Examine trust differently."},
        "declared_by": "Local test steward", "reason": "New frame, same display label.",
    })
    assert revised.status_code == 201
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO workspace_investigation (id, thesis, created_at, updated_at) VALUES ('current', ?, ?, ?)",
                     ("Later governing question", "2026-09-30T12:00:00Z", "2026-09-30T12:00:00Z"))
    receipt = _retain(client, run).get_json()
    assert receipt["run"]["perspective"]["id"] == saved["id"]
    assert receipt["run"]["perspective"]["definition"]["purpose"] == "Examine trust."
    assert receipt["run"]["question"] == "Original exact question?"
    assert receipt["run"]["perspective"]["id"] != revised.get_json()["perspective"]["id"]


def test_unknown_workspace_or_restarted_server_cannot_retain_a_copied_token(study, tmp_path):
    db, client = study
    run = _run(client)
    other = tmp_path / "other.db"
    SQLiteStore(other).close()
    other_client = create_app(db_path=other).test_client()
    restarted_client = create_app(db_path=db).test_client()
    assert _retain(other_client, run).status_code == 404
    assert _retain(restarted_client, run).status_code == 404
    assert _count(db) == _count(other) == 0


def test_failed_retention_is_atomic_and_exact_run_can_be_retried(study):
    db, client = study
    run = _run(client)
    with sqlite3.connect(db) as conn:
        conn.execute(f"CREATE TRIGGER receipt_fail BEFORE INSERT ON {TABLE} BEGIN SELECT RAISE(ABORT, 'simulated receipt write failure'); END")
    failed = _retain(client, run)
    assert failed.status_code == 409 and _count(db) == 0
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER receipt_fail")
    assert _retain(client, run).status_code == 201 and _count(db) == 1


def test_read_only_get_validates_identity_and_calls_no_provider_or_store(study, monkeypatch):
    db, client = study
    receipt = _retain(client, _run(client)).get_json()
    _rollback_journal(db)
    before = _snapshot(db.parent)
    import hermeneia.web.app as web
    def forbidden(*args, **kwargs):
        pytest.fail("Read-only execution retrieval must not invoke providers or open a writable store")
    monkeypatch.setattr(ProviderRegistry, "create", forbidden)
    monkeypatch.setattr(web, "SQLiteStore", forbidden)
    real_connect = sqlite3.connect
    traces = []
    def readonly(database, *args, **kwargs):
        assert "mode=ro" in str(database) and kwargs.get("uri") is True
        conn = real_connect(database, *args, **kwargs)
        trace = []
        traces.append(trace)
        conn.set_trace_callback(trace.append)
        return conn
    monkeypatch.setattr(sqlite3, "connect", readonly)
    first = client.get(f"/api/perspective/executions/{receipt['id']}")
    second = client.get(f"/api/perspective/executions/{receipt['id']}")
    assert first.status_code == second.status_code == 200
    assert first.data == second.data and first.get_json() == receipt
    assert first.headers["Cache-Control"] == "no-store"
    assert all(trace[:2] == ["PRAGMA query_only=ON", "BEGIN"] for trace in traces)
    assert _snapshot(db.parent) == before


def test_excluded_source_refuses_retention_and_retrieval_without_leaking_output(study):
    db, client = study
    kept = _retain(client, _run(client)).get_json()
    pending = _run(client)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE source_documents SET excluded_from_analysis=1 WHERE id='doc-selected'")
    before = _count(db)
    result = _retain(client, pending)
    fetched = client.get(f"/api/perspective/executions/{kept['id']}")
    assert result.status_code == fetched.status_code == 409
    assert OUTPUT.encode() not in fetched.data
    assert _count(db) == before


def test_custom_draft_and_room_do_not_acquire_a_keepable_run(study):
    db, client = study
    custom = _run(client, perspective_id=None, perspective_draft={
        "label": "Transient frame", "purpose": "Examine alternatives.", "questions": ["What is omitted?"],
    })
    assert custom["retention"]["supported"] is False and "run_id" not in custom
    room = client.post("/api/perspective/room", json={
        "question": "What is omitted?", "model": "qwen2.5:0.5b", "scope": _reader_selection_scope(),
    })
    assert room.status_code == 201
    assert room.get_json()["canonical_status"] == "not_persisted" and "run_id" not in room.get_json()
    assert _count(db) == 0


def test_missing_store_reads_and_unknown_token_create_no_workspace(tmp_path):
    db = tmp_path / "missing" / "study.db"
    client = create_app(db_path=db).test_client()
    assert client.get("/api/perspective/executions/unknown").status_code == 404
    assert client.post("/api/perspective/executions/unknown/retain", json={"decision": "retain"}).status_code == 404
    assert not db.exists() and not db.parent.exists()


def test_append_only_api_exposes_no_update_or_delete(study):
    _db, client = study
    receipt = _retain(client, _run(client)).get_json()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(f"/api/perspective/executions/{receipt['id']}", json={"response": "replacement"}).status_code == 405


def _highlight_scope(db, *, observation_id=None):
    with sqlite3.connect(db) as conn:
        conn.execute("""INSERT INTO reader_highlights
            (id, source_document_id, page, selected_text, source_locator,
             created_at, updated_at, observation_id)
            VALUES ('retained-highlight', 'doc-selected', 3, 'Captured highlighted passage',
                    'page:3:block:1', '2026-09-30T10:00:00Z', '2026-09-30T10:00:00Z', ?)""",
            (observation_id,))
    scope = _reader_selection_scope()
    scope["supporting"] = {"highlights": {"include": True, "ids": ["retained-highlight"]}}
    return scope


def test_missing_highlight_ancestor_refuses_keep_atomically_under_lineage_rules(study):
    db, client = study
    scope = _highlight_scope(db, observation_id="missing-observation")
    run = _run(client, scope=scope)
    result = _retain(client, run)
    assert result.status_code == 409 and _count(db) == 0
    assert "not eligible" in result.get_json()["error"]


def test_missing_later_highlight_ancestor_cannot_leak_kept_output_through_get(study):
    db, client = study
    receipt = _retain(client, _run(client, scope=_highlight_scope(db))).get_json()
    assert client.get(f"/api/perspective/executions/{receipt['id']}").status_code == 200
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE reader_highlights SET observation_id='missing-observation' WHERE id='retained-highlight'")
    result = client.get(f"/api/perspective/executions/{receipt['id']}")
    assert result.status_code == 409
    assert OUTPUT.encode() not in result.data


def test_bad_execution_capture_fails_closed_without_a_server_keep_token(study):
    db, client = study
    _CapturingProvider.render_responses = [""]
    response = client.post("/api/perspective/run", json={
        "perspective_id": "close-reader", "question": "What remains uncertain?",
        "model": "qwen2.5:0.5b", "scope": _reader_selection_scope(),
    })
    assert response.status_code == 409 and _count(db) == 0
    assert response.get_json()["canonical_status"] == "not_persisted"
    assert "run_id" not in response.get_json()


def test_workspace_export_refuses_invalid_receipt_instead_of_a_partial_bundle(study, monkeypatch):
    _db, client = study
    from hermeneia.workspace.export import PerspectiveExecutionExportError
    def refused(*args, **kwargs):
        raise PerspectiveExecutionExportError("malformed execution evidence")
    monkeypatch.setattr("hermeneia.workspace.build_workspace_zip", refused)
    response = client.get("/api/workspace/export")
    assert response.status_code == 409
    assert response.get_json() == {"error": "malformed execution evidence", "export_status": "refused"}


def test_api_keep_export_restore_and_read_only_context_preserve_exact_execution(study, tmp_path, monkeypatch):
    source, client = study
    receipt = _retain(client, _run(client, scope=_highlight_scope(source))).get_json()
    exported = client.get("/api/workspace/export")
    assert exported.status_code == 200 and exported.mimetype == "application/zip"
    from hermeneia.workspace import restore_workspace, safe_extract_zip
    bundle = safe_extract_zip(exported.data, tmp_path / "bundle")
    restored = tmp_path / "restored" / "study.db"
    report = restore_workspace(restored, bundle)
    assert report["restored"][TABLE] == 1
    assert report["coverage"][TABLE]["status"] == "covered"
    restored_client = create_app(db_path=restored).test_client()
    _rollback_journal(restored)
    before = _snapshot(restored.parent)
    def forbidden(*args, **kwargs):
        pytest.fail("Opening restored retained contexts must not execute a provider")
    monkeypatch.setattr(ProviderRegistry, "create", forbidden)
    fetched = restored_client.get(f"/api/perspective/executions/{receipt['id']}")
    assert fetched.status_code == 200 and fetched.get_json() == receipt
    views = []
    for active_client in (client, restored_client):
        lineage = active_client.get("/api/study-lineage").get_json()
        items = [item for item in lineage["items"] if item["record"]["table"] == TABLE]
        assert len(items) == 1
        assert items[0]["record"]["key"]["id"] == receipt["id"]
        assert items[0]["authorship"] == "model"
        views.append(items)
    assert views[0] == views[1]
    assert _snapshot(restored.parent) == before
    # Canonical record bytes, not a reconstituted display string, survive portability.
    payloads = []
    for path in (source, restored):
        with sqlite3.connect(path) as conn:
            payloads.append(conn.execute(f"SELECT receipt_json FROM {TABLE} WHERE id=?", (receipt["id"],)).fetchone()[0])
    assert payloads[0] == payloads[1]
    assert hashlib.sha256(payloads[0].encode()).digest() == hashlib.sha256(payloads[1].encode()).digest()


def test_saved_frame_opens_through_read_only_receipt_context_without_store_initialization(study, monkeypatch):
    db, client = study
    saved = client.post("/api/perspective/saved", json={
        "perspective_draft": {"label": "Synthetic frame", "purpose": "Examine uncertainty.", "questions": ["What is unknown?"]},
        "declared_by": "Local synthetic steward",
    }).get_json()
    receipt = _retain(client, _run(client, perspective_id=None, saved_perspective_id=saved["id"])).get_json()
    _rollback_journal(db)
    before = _snapshot(db.parent)

    def forbidden(*args, **kwargs):
        pytest.fail("Retained frame contexts must not initialize storage or execute a provider")

    monkeypatch.setattr(SQLiteStore, "__init__", forbidden)
    monkeypatch.setattr(ProviderRegistry, "create", forbidden)
    lineage = client.get("/api/study-lineage").get_json()
    item, = [i for i in lineage["items"] if i["record"]["table"] == TABLE]
    assert not any(c["kind"] == "perspective" for c in item["contexts"])
    context, = [c for c in item["contexts"] if c["kind"] == "perspective_execution"]
    opened = client.get(f"/api/perspective/executions/{context['receipt_id']}")
    assert opened.status_code == 200
    assert opened.get_json()["run"]["perspective"]["id"] == saved["id"]
    assert opened.get_json()["run"]["perspective"]["definition"]["purpose"] == "Examine uncertainty."
    assert _snapshot(db.parent) == before
