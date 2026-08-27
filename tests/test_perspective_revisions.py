from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from hermeneia.perspective_identity import (
    FRAME_V2_SCHEME,
    frame_v2_row_from_draft,
    perspective_frame_v2_id,
)
from hermeneia.perspective_runs import (
    normalize_transient_perspective_draft,
    transient_perspective_fingerprint,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

from test_e10_vertical_slice_api import (
    _CapturingProvider,
    _install_fake_ollama,
    _ollama_registry,
    _reader_selection_scope,
)


def _make_current_db_v16_shaped(db_path) -> None:
    store = SQLiteStore(db_path)
    store.close()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DROP TRIGGER IF EXISTS perspectives_no_update")
        conn.execute("DROP TRIGGER IF EXISTS perspectives_no_delete")
        conn.execute("DROP INDEX IF EXISTS idx_perspectives_legacy_name")
        conn.execute("DROP INDEX IF EXISTS idx_perspectives_frame_fingerprint")
        conn.execute("DROP TABLE perspectives")
        conn.execute(
            """
            INSERT OR IGNORE INTO source_documents
                (id, original_filename, file_hash, total_pages, registered_at, compiler_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("doc-v16", "legacy.pdf", "hash-v16", 1, "2026-08-22T09:00:00+00:00", "test"),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO source_extractions
                (id, document_id, page, region, raw_text, parser, parser_version,
                 coordinates, source_locator, source_hash, hash, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ext-v16",
                "doc-v16",
                1,
                "block:1",
                "Legacy source text.",
                "test",
                "1",
                "{}",
                "page:1:block:1",
                "source-hash",
                "hash",
                "2026-08-22T09:01:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO observations
                (id, source_document_id, source_extraction_id, raw_text, source_locator,
                 semantic_hash, page, paragraph, sentence, preceding_observation_id,
                 following_observation_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "obs-v16",
                "doc-v16",
                "ext-v16",
                "Legacy source text.",
                "page:1:block:1",
                "semantic-hash",
                1,
                1,
                1,
                None,
                None,
                "2026-08-22T09:02:00+00:00",
            ),
        )
        conn.execute(
            """
            CREATE TABLE perspectives (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO perspectives (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            ("legacy-id", "Legacy", "Legacy description", "2026-08-22T10:00:00+00:00"),
        )
        conn.execute(
            """
            INSERT INTO interpretations
                (id, observation_id, perspective, perspective_id, text, evidential_status,
                 evidence_observation_ids, confidence, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "interp-id",
                "obs-v16",
                "Legacy",
                "legacy-id",
                "Legacy reading.",
                "speculative",
                "[]",
                "human",
                "steward-authored",
                "2026-08-22T10:05:00+00:00",
            ),
        )
        conn.execute("UPDATE schema_version SET version = 16")
        conn.commit()
    finally:
        conn.close()


def _draft(**overrides) -> dict:
    base = {
        "label": "Institutional Trust Reader",
        "purpose": "Examine how institutions gain, lose, or borrow legitimacy.",
        "questions": ["Who is expected to trust whom?"],
        "challenges": ["Challenge unsupported legitimacy claims."],
        "limitations": ["May overemphasize institutions."],
    }
    base.update(overrides)
    return base


def _saved_row(draft: dict | None = None, *, declared_by: str = "Primary Human Steward", predecessor: str | None = None):
    return frame_v2_row_from_draft(
        draft or _draft(),
        declared_by=declared_by,
        declared_date="2026-08-22T12:00:00+00:00",
        predecessor_perspective_id=predecessor,
    )[0]


def test_frame_v2_identity_distinguishes_semantics_declaration_context_and_time() -> None:
    transient = normalize_transient_perspective_draft(_draft()).definition
    row = _saved_row()

    assert row["definition_fingerprint"] == transient_perspective_fingerprint(transient)
    assert row["id"] == perspective_frame_v2_id(
        definition_fingerprint=row["definition_fingerprint"],
        declared_by="Primary Human Steward",
    )
    assert _saved_row(declared_by="Another Steward")["id"] != row["id"]
    assert _saved_row(_draft(purpose="Examine institutional trust differently."))["id"] != row["id"]
    assert frame_v2_row_from_draft(
        _draft(),
        declared_by="Primary Human Steward",
        declared_date="2030-01-01T00:00:00+00:00",
    )[0]["id"] == row["id"]


def test_v16_to_v17_migration_preserves_legacy_perspective_and_fk(tmp_path):
    db_path = tmp_path / "legacy-v16.db"
    _make_current_db_v16_shaped(db_path)

    store = SQLiteStore(db_path)
    try:
        row = store.get_perspective_by_id("legacy-id")
        interp = store._conn.execute(
            "SELECT perspective_id FROM interpretations WHERE id = 'interp-id'"
        ).fetchone()
        version = store._conn.execute("SELECT version FROM schema_version").fetchone()[0]
        violations = store._conn.execute("PRAGMA foreign_key_check").fetchall()
        columns = {r[1] for r in store._conn.execute("PRAGMA table_info(perspectives)")}
    finally:
        store.close()

    assert row is not None
    assert {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"],
    } == {
        "id": "legacy-id",
        "name": "Legacy",
        "description": "Legacy description",
        "created_at": "2026-08-22T10:00:00+00:00",
    }
    assert row["identity_scheme"] == "perspective-label-v1"
    assert interp["perspective_id"] == "legacy-id"
    assert version == 17
    assert violations == []
    assert "definition_fingerprint" in columns

    reopened = SQLiteStore(db_path)
    try:
        assert reopened.perspective_count() == 1
        assert reopened._conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        reopened.close()


def test_perspective_migration_rolls_back_if_post_rebuild_step_fails(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy-fails.db"
    _make_current_db_v16_shaped(db_path)

    def fail_after_rebuild(self):
        raise sqlite3.IntegrityError("forced index failure")

    monkeypatch.setattr(SQLiteStore, "_create_perspective_indexes_and_triggers", fail_after_rebuild)
    with pytest.raises(sqlite3.IntegrityError, match="forced index failure"):
        SQLiteStore(db_path)

    conn = sqlite3.connect(db_path)
    try:
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='perspectives'"
        ).fetchone()[0]
        row = conn.execute(
            "SELECT id, name, description, created_at FROM perspectives"
        ).fetchone()
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        conn.close()
    assert "identity_scheme" not in table_sql
    assert tuple(row) == ("legacy-id", "Legacy", "Legacy description", "2026-08-22T10:00:00+00:00")
    assert version == 16


def test_frame_v2_perspectives_are_immutable_and_same_label_can_coexist(tmp_path):
    store = SQLiteStore(tmp_path / "perspectives.db")
    first = store.insert_frame_perspective(_saved_row())
    second = store.insert_frame_perspective(
        _saved_row(_draft(purpose="A refined institutional standpoint."), declared_by="Another Steward")
    )

    assert first["name"] == second["name"] == "Institutional Trust Reader"
    assert first["id"] != second["id"]
    with pytest.raises(sqlite3.IntegrityError, match="Perspective immutable"):
        store._conn.execute("UPDATE perspectives SET purpose = 'mutated' WHERE id = ?", (first["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="Perspective immutable"):
        store._conn.execute("DELETE FROM perspectives WHERE id = ?", (first["id"],))
    store.close()


def test_revision_appends_successor_supersession_and_retry_is_idempotent(tmp_path):
    store = SQLiteStore(tmp_path / "revisions.db")
    predecessor = store.insert_frame_perspective(_saved_row())
    successor_row = _saved_row(
        _draft(purpose="Trace how institutions ask to be believed."),
        predecessor=predecessor["id"],
    )

    successor = store.insert_perspective_revision(
        predecessor["id"],
        successor_row,
        "Sharper trust language.",
        "2026-08-22T12:30:00+00:00",
    )
    retry = store.insert_perspective_revision(
        predecessor["id"],
        {**successor_row, "declared_date": "2030-01-01T00:00:00+00:00", "created_at": "2030-01-01T00:00:00+00:00"},
        "Sharper trust language.",
        "2030-01-01T00:00:00+00:00",
    )

    assert retry["id"] == successor["id"]
    assert store.get_perspective_by_id(predecessor["id"])["purpose"] == predecessor["purpose"]
    edges = store.supersessions_from(predecessor["id"])
    assert len(edges) == 1
    assert edges[0]["new_id"] == successor["id"]
    assert store.perspective_is_current_leaf(predecessor["id"]) is False
    assert store.perspective_is_current_leaf(successor["id"]) is True
    with pytest.raises(ValueError, match="current Perspective leaf"):
        store.insert_perspective_revision(
            predecessor["id"],
            _saved_row(_draft(purpose="Hidden branch."), predecessor=predecessor["id"]),
            "Branch attempt.",
            "2026-08-22T13:00:00+00:00",
        )
    store.close()


def test_concurrent_different_revisions_create_one_successor(tmp_path):
    db_path = tmp_path / "concurrent.db"
    seed = SQLiteStore(db_path)
    predecessor = seed.insert_frame_perspective(_saved_row())
    seed.close()
    barrier = threading.Barrier(2)
    results: list[tuple[str, str]] = []
    lock = threading.Lock()

    def attempt(label: str, purpose: str) -> None:
        store = SQLiteStore(db_path)
        row = _saved_row(
            _draft(purpose=purpose),
            predecessor=predecessor["id"],
        )
        barrier.wait(timeout=5)
        try:
            saved = store.insert_perspective_revision(
                predecessor["id"],
                row,
                f"{label} reason.",
                f"2026-08-22T12:3{0 if label == 'a' else 1}:00+00:00",
            )
            outcome = ("ok", saved["id"])
        except ValueError as exc:
            outcome = ("error", str(exc))
        finally:
            store.close()
        with lock:
            results.append(outcome)

    threads = [
        threading.Thread(target=attempt, args=("a", "Revision A.")),
        threading.Thread(target=attempt, args=("b", "Revision B.")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(item[0] for item in results) == ["error", "ok"]
    assert any("current Perspective leaf" in message for status, message in results if status == "error")
    store = SQLiteStore(db_path)
    try:
        edges = store.supersessions_from(predecessor["id"])
        assert len(edges) == 1
    finally:
        store.close()


def test_reversion_reuses_fingerprint_with_new_id_and_ancestor_object_reuse_is_rejected(tmp_path):
    store = SQLiteStore(tmp_path / "reversion.db")
    p1 = store.insert_frame_perspective(_saved_row(_draft()))
    p2 = store.insert_perspective_revision(
        p1["id"],
        _saved_row(_draft(purpose="Frame B."), predecessor=p1["id"]),
        "Move to B.",
        "2026-08-22T12:10:00+00:00",
    )
    p3 = store.insert_perspective_revision(
        p2["id"],
        _saved_row(_draft(), predecessor=p2["id"]),
        "Revert to A semantics.",
        "2026-08-22T12:20:00+00:00",
    )
    assert p1["definition_fingerprint"] == p3["definition_fingerprint"]
    assert p1["id"] != p3["id"]
    assert store.supersessions_from(p1["id"])[0]["new_id"] == p2["id"]
    assert store.supersessions_from(p2["id"])[0]["new_id"] == p3["id"]
    with pytest.raises(ValueError, match="declaration context"):
        store.insert_perspective_revision(
            p3["id"],
            dict(p1),
            "Reuse ancestor.",
            "2026-08-22T12:30:00+00:00",
        )
    store.close()


def test_root_and_revision_validate_deterministic_frame_v2_ids(tmp_path):
    store = SQLiteStore(tmp_path / "identity.db")
    bad_root = {**_saved_row(), "id": "perspective-frame-v2:" + "0" * 64}
    with pytest.raises(ValueError, match="declaration context"):
        store.insert_frame_perspective(bad_root)

    root = store.insert_frame_perspective(_saved_row())
    bad_revision = {
        **_saved_row(_draft(purpose="Changed.")),
        "created_at": "2026-08-22T12:30:00+00:00",
        "declared_date": "2026-08-22T12:30:00+00:00",
    }
    with pytest.raises(ValueError, match="declaration context"):
        store.insert_perspective_revision(
            root["id"],
            bad_revision,
            "Wrong context.",
            "2026-08-22T12:30:00+00:00",
        )
    store.close()


def test_saved_perspective_api_and_run_use_canonical_identity(tmp_path, monkeypatch):
    _install_fake_ollama(monkeypatch, ["qwen2.5:0.5b"])
    _CapturingProvider.calls = []
    _CapturingProvider.render_prompts = []
    client = create_app(
        db_path=tmp_path / "saved-run.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    saved = client.post(
        "/api/perspective/saved",
        json={"perspective_draft": _draft(), "declared_by": "Primary Human Steward"},
    )
    assert saved.status_code == 201
    perspective = saved.get_json()
    assert perspective["identity_scheme"] == FRAME_V2_SCHEME
    assert perspective["declared_by"] == "Primary Human Steward"

    listing = client.get("/api/perspective/saved").get_json()
    assert listing["perspectives"][0]["id"] == perspective["id"]

    neither = client.post("/api/perspective/run", json={
        "question": "What matters?",
        "model": "qwen2.5:0.5b",
        "scope": _reader_selection_scope(),
    })
    both = client.post("/api/perspective/run", json={
        "perspective_id": "close-reader",
        "saved_perspective_id": perspective["id"],
        "question": "What matters?",
        "model": "qwen2.5:0.5b",
        "scope": _reader_selection_scope(),
    })
    assert neither.status_code == 400
    assert both.status_code == 400

    run = client.post("/api/perspective/run", json={
        "saved_perspective_id": perspective["id"],
        "question": "Who is asked to trust?",
        "model": "qwen2.5:0.5b",
        "scope": _reader_selection_scope("Only this source passage."),
    })

    assert run.status_code == 201
    receipt = run.get_json()
    assert receipt["canonical_status"] == "not_persisted"
    assert receipt["perspective"]["origin"] == "canonical_saved"
    assert receipt["perspective"]["perspective_id"] == perspective["id"]
    assert receipt["perspective"]["definition_fingerprint"] == perspective["definition_fingerprint"]
    assert receipt["perspective"]["declared_by"] == "Primary Human Steward"
    assert "version" not in receipt["perspective"]
    assert receipt["execution"]["provider_id"] == "ollama-local"
    assert receipt["execution"]["model_id"] == "qwen2.5:0.5b"
    assert "Perspective ID: " + perspective["id"] in _CapturingProvider.render_prompts[-1]
    assert "Perspective version:" not in _CapturingProvider.render_prompts[-1]


def test_saved_perspective_get_routes_are_read_only_for_missing_database(tmp_path):
    db_path = tmp_path / "missing.db"
    client = create_app(db_path=db_path).test_client()

    listing = client.get("/api/perspective/saved")
    missing = client.get("/api/perspective/saved/perspective-frame-v2:missing")

    assert listing.status_code == 200
    assert listing.get_json()["perspectives"] == []
    assert missing.status_code == 404
    assert not db_path.exists()


def test_saved_perspective_get_migrates_existing_v16_workspace_before_read(tmp_path):
    db_path = tmp_path / "legacy-web.db"
    _make_current_db_v16_shaped(db_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get("/api/perspective/saved")

    assert response.status_code == 200
    assert response.get_json()["perspectives"] == []
    store = SQLiteStore(db_path)
    try:
        legacy = store.get_perspective_by_id("legacy-id")
        assert legacy["identity_scheme"] == "perspective-label-v1"
        assert store.perspective_count() == 1
    finally:
        store.close()


def test_saved_perspective_revision_api_rejects_legacy_and_non_leaf(tmp_path):
    store = SQLiteStore(tmp_path / "api-revisions.db")
    store.register_perspective({
        "id": "legacy-id",
        "name": "Legacy",
        "description": "",
        "created_at": "2026-08-22T12:00:00+00:00",
    })
    root = store.insert_frame_perspective(_saved_row())
    store.close()
    client = create_app(db_path=tmp_path / "api-revisions.db").test_client()

    legacy = client.post(
        "/api/perspective/saved/legacy-id/revisions",
        json={"perspective_draft": _draft(), "declared_by": "Primary Human Steward", "reason": "No."},
    )
    assert legacy.status_code == 409
    assert "frame-v2" in legacy.get_json()["error"]

    first = client.post(
        f"/api/perspective/saved/{root['id']}/revisions",
        json={
            "perspective_draft": _draft(purpose="Trace legitimation."),
            "declared_by": "Primary Human Steward",
            "reason": "Refine purpose.",
        },
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/perspective/saved/{root['id']}/revisions",
        json={
            "perspective_draft": _draft(purpose="Hidden branch."),
            "declared_by": "Primary Human Steward",
            "reason": "Branch.",
        },
    )
    assert second.status_code == 409
    assert "current Perspective leaf" in second.get_json()["error"]
