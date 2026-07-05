"""Durable workspace identity (issue #83).

A workspace is a named interpretive project; its identity must be stable and
independent of the corpus it currently contains. These tests confirm the id is
generated once and persists, stays stable when the corpus changes, is not a
corpus fingerprint, flows into the exported bundle, and can be named.
"""
from __future__ import annotations

import io
import sqlite3
import zipfile
import json
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import build_workspace_zip


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fresh(tmp_path: Path) -> Path:
    db_path = tmp_path / "workspace.db"
    SQLiteStore(db_path).close()
    return db_path


def _add_doc(db_path: Path, doc_id: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "doc.pdf", doc_id, 1, _now(), "test", "primary", 0),
    )
    conn.commit()
    conn.close()


# ── Persistence + stability ────────────────────────────────────────────────


def test_identity_is_generated_and_persists(tmp_path: Path):
    client = create_app(db_path=_fresh(tmp_path)).test_client()
    first = client.get("/api/workspace/identity").get_json()["identity"]
    second = client.get("/api/workspace/identity").get_json()["identity"]
    assert first["workspace_id"]
    assert first["workspace_id"] == second["workspace_id"]  # stable across calls
    assert first["created_at"] == second["created_at"]


def test_empty_workspace_still_has_identity(tmp_path: Path):
    client = create_app(db_path=_fresh(tmp_path)).test_client()
    identity = client.get("/api/workspace/identity").get_json()["identity"]
    assert identity["workspace_id"]  # independent of any corpus


def test_identity_is_stable_when_the_corpus_changes(tmp_path: Path):
    db_path = _fresh(tmp_path)
    client = create_app(db_path=db_path).test_client()
    before = client.get("/api/workspace/identity").get_json()["identity"]["workspace_id"]

    _add_doc(db_path, "a" * 64)
    _add_doc(db_path, "b" * 64)
    after = client.get("/api/workspace/identity").get_json()["identity"]["workspace_id"]
    assert before == after  # identity != corpus fingerprint


def test_identity_is_not_the_corpus_fingerprint(tmp_path: Path):
    import hashlib

    db_path = _fresh(tmp_path)
    _add_doc(db_path, "a" * 64)
    client = create_app(db_path=db_path).test_client()
    workspace_id = client.get("/api/workspace/identity").get_json()["identity"][
        "workspace_id"
    ]
    corpus_fingerprint = hashlib.sha256(("a" * 64).encode()).hexdigest()[:32]
    assert workspace_id != corpus_fingerprint


# ── Naming ─────────────────────────────────────────────────────────────────


def test_workspace_can_be_named_without_changing_its_id(tmp_path: Path):
    client = create_app(db_path=_fresh(tmp_path)).test_client()
    original = client.get("/api/workspace/identity").get_json()["identity"]
    named = client.put(
        "/api/workspace/identity", json={"workspace_name": "Gatsby Study"}
    ).get_json()["identity"]
    assert named["workspace_name"] == "Gatsby Study"
    assert named["workspace_id"] == original["workspace_id"]
    assert named["created_at"] == original["created_at"]


# ── Flows into the bundle ──────────────────────────────────────────────────


def test_export_bundle_carries_the_persistent_identity(tmp_path: Path):
    db_path = _fresh(tmp_path)
    client = create_app(db_path=db_path).test_client()
    workspace_id = client.get("/api/workspace/identity").get_json()["identity"][
        "workspace_id"
    ]

    zip_bytes = client.get("/api/workspace/export").data
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        manifest = json.loads(zf.read("workspace/manifest.json"))
    assert manifest["workspace_id"] == workspace_id


def test_library_build_workspace_zip_prefers_persistent_id(tmp_path: Path):
    """The exporter default resolves to the persistent identity, not the corpus."""
    db_path = _fresh(tmp_path)
    # Create an identity via the app, then export directly from the library.
    create_app(db_path=db_path).test_client().get("/api/workspace/identity")
    conn = sqlite3.connect(db_path)
    workspace_id = conn.execute(
        "SELECT workspace_id FROM workspace_identity WHERE id='current'"
    ).fetchone()[0]
    conn.close()

    data = build_workspace_zip(db_path, generated_at="2026-07-04T15:00:00+00:00")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        manifest = json.loads(zf.read("workspace/manifest.json"))
    assert manifest["workspace_id"] == workspace_id
