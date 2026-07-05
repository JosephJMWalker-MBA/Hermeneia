"""Import Workspace UI + endpoints (issues #70/#76/#81).

Inspect before acting: preview a bundle .zip read-only, then restore only on
explicit confirmation. v1 restores into a fresh workspace only; a non-empty
target is surfaced (409), never silently overwritten. A malformed upload is a
400.
"""
from __future__ import annotations

import io
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import build_workspace_zip


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed(db_path: Path) -> None:
    SQLiteStore(db_path).close()
    doc_id = "a" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 3, _now(), "test", "primary", 0),
    )
    conn.execute(
        """INSERT INTO workspace_investigation
           (id, thesis, purpose, lenses, reconsider, created_at, updated_at)
           VALUES ('current', ?, ?, ?, ?, ?, ?)""",
        ("How does desire depend on distance?", None, "[]", None, _now(), _now()),
    )
    conn.commit()
    conn.close()


def _bundle_zip(tmp_path: Path) -> bytes:
    """A real bundle .zip built from a seeded source workspace."""
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True, exist_ok=True)
    _seed(src)
    return build_workspace_zip(
        src, generated_at="2026-07-04T15:00:00+00:00", workspace_id="ws"
    )


# ── Preview ────────────────────────────────────────────────────────────────


def test_preview_reports_summary_into_empty_workspace(tmp_path: Path):
    zip_bytes = _bundle_zip(tmp_path)
    fresh = tmp_path / "fresh.db"
    SQLiteStore(fresh).close()
    client = create_app(db_path=fresh).test_client()

    resp = client.post(
        "/api/workspace/import/preview",
        data={"bundle": (io.BytesIO(zip_bytes), "workspace.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["target_empty"] is True
    assert body["would_create"]["source_documents"] == 1
    assert body["has_investigation"] is True
    assert body["wbs_version"] == "1.0"


def test_preview_flags_nonempty_target(tmp_path: Path):
    zip_bytes = _bundle_zip(tmp_path)
    live = tmp_path / "live.db"
    _seed(live)  # already has work
    client = create_app(db_path=live).test_client()
    body = client.post(
        "/api/workspace/import/preview",
        data={"bundle": (io.BytesIO(zip_bytes), "workspace.zip")},
        content_type="multipart/form-data",
    ).get_json()
    assert body["target_empty"] is False


def test_preview_rejects_a_non_zip(tmp_path: Path):
    fresh = tmp_path / "fresh.db"
    SQLiteStore(fresh).close()
    client = create_app(db_path=fresh).test_client()
    resp = client.post(
        "/api/workspace/import/preview",
        data={"bundle": (io.BytesIO(b"not a zip"), "junk.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_preview_requires_a_bundle(tmp_path: Path):
    fresh = tmp_path / "fresh.db"
    SQLiteStore(fresh).close()
    client = create_app(db_path=fresh).test_client()
    resp = client.post("/api/workspace/import/preview", data={},
                       content_type="multipart/form-data")
    assert resp.status_code == 400


# ── Restore ────────────────────────────────────────────────────────────────


def test_restore_into_empty_workspace_succeeds(tmp_path: Path):
    zip_bytes = _bundle_zip(tmp_path)
    fresh = tmp_path / "fresh.db"
    SQLiteStore(fresh).close()
    client = create_app(db_path=fresh).test_client()

    resp = client.post(
        "/api/workspace/import/restore",
        data={"bundle": (io.BytesIO(zip_bytes), "workspace.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["restored"]["source_documents"] == 1

    verify = sqlite3.connect(fresh)
    n = verify.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
    thesis = verify.execute(
        "SELECT thesis FROM workspace_investigation WHERE id='current'"
    ).fetchone()[0]
    verify.close()
    assert n == 1
    assert thesis == "How does desire depend on distance?"


def test_restore_refuses_nonempty_workspace_with_409(tmp_path: Path):
    zip_bytes = _bundle_zip(tmp_path)
    live = tmp_path / "live.db"
    _seed(live)
    client = create_app(db_path=live).test_client()
    resp = client.post(
        "/api/workspace/import/restore",
        data={"bundle": (io.BytesIO(zip_bytes), "workspace.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 409
    assert "not empty" in resp.get_json()["error"]


def test_restore_rejects_bad_zip_with_400(tmp_path: Path):
    fresh = tmp_path / "fresh.db"
    SQLiteStore(fresh).close()
    client = create_app(db_path=fresh).test_client()
    resp = client.post(
        "/api/workspace/import/restore",
        data={"bundle": (io.BytesIO(b"nope"), "junk.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


# ── UI affordance ──────────────────────────────────────────────────────────


def test_import_ui_affordance_present():
    index = (
        Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
    ).read_text()
    assert "importWorkspace()" in index
    assert "Import workspace" in index
    assert 'id="ws-import-overlay"' in index
    assert "_wsImportPreview" in index
    assert "_wsImportRestore" in index
    assert "/api/workspace/import/preview" in index
    assert "/api/workspace/import/restore" in index
