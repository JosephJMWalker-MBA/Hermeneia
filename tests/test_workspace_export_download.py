"""Export Workspace download (issues #70/#76/#79).

The browser-facing delivery of the Workspace Bundle: a deterministic .zip. These
tests cover the zip builder's determinism and the /api/workspace/export endpoint
(content type, attachment filename, contents, read-only safety), plus the UI
button wiring.
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


def _seed(tmp_path: Path) -> Path:
    db_path = tmp_path / "workspace.db"
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
    uploads = db_path.parent / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / "gatsby_abc.pdf").write_bytes(b"%PDF-1.7 fake")
    return db_path


# ── Zip builder ────────────────────────────────────────────────────────────


def test_zip_contains_bundle_files():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        db_path = _seed(Path(td))
        data = build_workspace_zip(
            db_path, generated_at="2026-07-04T15:00:00+00:00", workspace_id="ws"
        )
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
        assert "workspace/manifest.json" in names
        assert "workspace/investigation.json" in names
        assert "workspace/corpus/documents.json" in names
        assert any(n.startswith("workspace/corpus/uploads/") for n in names)


def test_zip_is_byte_identical_for_identical_state():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        db_path = _seed(Path(td))
        a = build_workspace_zip(
            db_path, generated_at="2026-07-04T15:00:00+00:00", workspace_id="ws"
        )
        b = build_workspace_zip(
            db_path, generated_at="2026-07-04T15:00:00+00:00", workspace_id="ws"
        )
        assert a == b


# ── Endpoint ───────────────────────────────────────────────────────────────


def test_export_endpoint_returns_a_zip_attachment(tmp_path: Path):
    db_path = _seed(tmp_path)
    resp = create_app(db_path=db_path).test_client().get("/api/workspace/export")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/zip"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert ".zip" in resp.headers["Content-Disposition"]

    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        assert "workspace/manifest.json" in zf.namelist()
        inv = zf.read("workspace/investigation.json").decode()
    assert "How does desire depend on distance?" in inv


def test_export_endpoint_404_without_database(tmp_path: Path):
    resp = create_app(db_path=tmp_path / "missing.db").test_client().get(
        "/api/workspace/export"
    )
    assert resp.status_code == 404


def test_export_endpoint_does_not_mutate_the_database(tmp_path: Path):
    db_path = _seed(tmp_path)
    before = db_path.read_bytes()
    create_app(db_path=db_path).test_client().get("/api/workspace/export")
    assert db_path.read_bytes() == before


# ── UI wiring ──────────────────────────────────────────────────────────────


def test_export_button_present_in_workspace_drawer():
    index = (
        Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
    ).read_text()
    assert "exportWorkspace()" in index
    assert "Export workspace" in index
    assert "/api/workspace/export" in index
