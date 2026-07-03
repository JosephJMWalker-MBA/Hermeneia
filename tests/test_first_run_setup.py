"""
First-Run Setup Tests (issue #20)

Invariant: a fresh environment must be usable from the UI alone. The
setup endpoints detect first-run state and create the workspace — and
they are strictly additive: init never touches an existing workspace.

Covers:
  - state detection: missing DB / empty DB / populated DB
  - init creates a usable schema on a missing DB; idempotent thereafter
  - init on an existing workspace changes nothing (no data deletion)
  - /api/health behavior is unchanged (still 404 without a DB)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _seed_doc(db: Path, doc_id: str) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT OR IGNORE INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 10,
         datetime.now(timezone.utc).isoformat(), "test", "primary", 0),
    )
    conn.commit()
    conn.close()


def test_state_detects_missing_database(tmp_path):
    db = tmp_path / "nonexistent.db"
    client = create_app(db_path=db).test_client()
    s = client.get("/api/setup/state").get_json()
    assert s["database_exists"] is False
    assert s["document_count"] == 0
    assert s["first_run"] is True
    assert s["db_path"] == str(db)


def test_state_detects_empty_workspace(tmp_path):
    db = tmp_path / "empty.db"
    SQLiteStore(db).close()
    client = create_app(db_path=db).test_client()
    s = client.get("/api/setup/state").get_json()
    assert s["database_exists"] is True
    assert s["document_count"] == 0
    assert s["first_run"] is True


def test_state_detects_existing_workspace(tmp_path):
    db = tmp_path / "existing.db"
    SQLiteStore(db).close()
    _seed_doc(db, "a" * 64)
    client = create_app(db_path=db).test_client()
    s = client.get("/api/setup/state").get_json()
    assert s["first_run"] is False
    assert s["document_count"] == 1


def test_init_creates_usable_workspace_and_is_idempotent(tmp_path):
    db = tmp_path / "fresh" / "workspace.db"
    client = create_app(db_path=db).test_client()

    r = client.post("/api/setup/init")
    assert r.status_code == 200
    body = r.get_json()
    assert body["created"] is True
    assert body["database_exists"] is True

    # The created schema must be immediately usable by the app's own
    # surfaces — e.g. the investigation log accepts an entry.
    r = client.post("/api/investigation-log", json={
        "lane": "instrument",
        "understanding": "The UI created this workspace itself.",
    })
    assert r.status_code == 201

    r2 = client.post("/api/setup/init")
    assert r2.get_json()["created"] is False


def test_init_never_touches_an_existing_workspace(tmp_path):
    db = tmp_path / "existing.db"
    SQLiteStore(db).close()
    _seed_doc(db, "b" * 64)
    client = create_app(db_path=db).test_client()

    # Reader data present before init
    r = client.post("/api/reader/highlights", json={
        "source_document_id": "b" * 64,
        "selected_text": "boats against the current",
    })
    assert r.status_code == 201

    r = client.post("/api/setup/init")
    assert r.get_json()["created"] is False

    conn = sqlite3.connect(db)
    docs = conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
    hls = conn.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    conn.close()
    assert docs == 1 and hls == 1, "init must never alter existing data"


def test_health_contract_unchanged(tmp_path):
    """Other consumers rely on health 404ing without a DB; the fresh-
    environment handling lives in /api/setup/state, not here."""
    db = tmp_path / "missing.db"
    client = create_app(db_path=db).test_client()
    assert client.get("/api/health").status_code == 404
    assert client.get("/api/setup/state").status_code == 200
