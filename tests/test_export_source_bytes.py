"""Promoted regressions for #229 and #238: export canonical uploads from SourceDocuments.

Bundle uploads are the source bytes of the exported SourceDocuments, named by
the content hash that is their identity (WBS §4). Files that are not the
source of any exported document are not canonical evidence, a document is
never exported without its bytes because of a concurrent upload, and a
document whose bytes are absent is classified explicitly rather than silently.
Commit 39fcb0b preserves the negative versions; the repair demonstrated strict
unexpected passes before the expected failures were removed.
Synthetic workspaces only.
"""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import threading
import zipfile

import fitz
import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import build_workspace_zip, export_workspace_bundle
from hermeneia.workspace import export as export_module

TIME = "2026-10-06T12:00:00+00:00"


class SourceBytesExportFailure(AssertionError):
    """Only the observed source-bytes export failures are expected here."""


def _pdf(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    db = ws / "workspace.db"
    SQLiteStore(db).close()
    app = create_app(db_path=db)
    app.config["TESTING"] = False
    upload(app, _pdf("Existing document text."), "old.pdf")
    return tmp_path, ws, db, app


def upload(app, data: bytes, name: str):
    return app.test_client().post("/api/upload", data={"file": (io.BytesIO(data), name)},
                                  content_type="multipart/form-data").get_json()


def _bundle_files(directory) -> dict[str, bytes]:
    manifest = json.loads((directory / "manifest.json").read_text())
    return {entry["path"]: (directory / entry["path"]).read_bytes() for entry in manifest["files"]} | {
        "manifest.json": (directory / "manifest.json").read_bytes()}


def _zip_files(data: bytes) -> dict[str, bytes]:
    archive = zipfile.ZipFile(io.BytesIO(data))
    return {name.split("/", 1)[1]: archive.read(name) for name in archive.namelist() if not name.endswith("/")}


def _documents_without_bytes(files: dict[str, bytes]) -> set[str]:
    documents = {d["id"] for d in json.loads(files["corpus/documents.json"])}
    uploads = {hashlib.sha256(data).hexdigest() for path, data in files.items() if path.startswith("corpus/uploads/")}
    return documents - uploads


def _concurrent_upload(app):
    t = threading.Thread(target=lambda: upload(app, _pdf("Document added during export."), "new.pdf"))
    t.start()
    t.join(60)


def test_only_source_bytes_of_exported_documents_are_canonical_uploads(workspace):
    _tmp, ws, db, _app = workspace
    (ws / "uploads" / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
    (ws / "uploads" / "study_k2j3h4g5.pdf").write_bytes(b"%PDF-1.4 orphaned partial upload")
    export_workspace_bundle(db, ws.parent / "bundle", generated_at=TIME, workspace_id="s")
    files = _bundle_files(ws.parent / "bundle")
    documents = {d["id"] for d in json.loads(files["corpus/documents.json"])}
    uploads = {hashlib.sha256(data).hexdigest() for path, data in files.items() if path.startswith("corpus/uploads/")}
    if uploads != documents:
        raise SourceBytesExportFailure(f"unreferenced canonical uploads: {sorted(uploads - documents)}")


def test_library_export_never_exports_a_document_without_its_bytes(workspace, monkeypatch):
    _tmp, ws, db, app = workspace
    real_connect = export_module._connect_ro
    armed = {"done": False}

    def connect_after_concurrent_upload(path):
        if not armed["done"]:
            armed["done"] = True
            _concurrent_upload(app)
        return real_connect(path)

    monkeypatch.setattr(export_module, "_connect_ro", connect_after_concurrent_upload)
    export_workspace_bundle(db, ws.parent / "bundle", generated_at=TIME, workspace_id="s")
    missing = _documents_without_bytes(_bundle_files(ws.parent / "bundle"))
    if missing:
        raise SourceBytesExportFailure(f"documents exported without source bytes: {sorted(missing)}")


def test_zip_export_never_exports_a_document_without_its_bytes(workspace, monkeypatch):
    _tmp, _ws, db, app = workspace
    real_publication = export_module._publication_component
    armed = {"done": False}

    def publication_after_concurrent_upload(conn, path):
        if not armed["done"]:
            armed["done"] = True
            _concurrent_upload(app)
        return real_publication(conn, path)

    monkeypatch.setattr(export_module, "_publication_component", publication_after_concurrent_upload)
    files = _zip_files(build_workspace_zip(db, generated_at=TIME, workspace_id="s"))
    missing = _documents_without_bytes(files)
    if missing:
        raise SourceBytesExportFailure(f"documents exported without source bytes: {sorted(missing)}")


def test_document_with_absent_source_bytes_is_classified_in_the_manifest(workspace):
    _tmp, ws, db, app = workspace
    lost = upload(app, _pdf("A document whose bytes were lost."), "lost.pdf")["document_id"]
    for path in (ws / "uploads").iterdir():
        if hashlib.sha256(path.read_bytes()).hexdigest() == lost:
            path.unlink()
    manifest = export_workspace_bundle(db, ws.parent / "bundle", generated_at=TIME, workspace_id="s")
    classification = manifest.get("source_bytes") or {}
    if classification.get("missing") != [lost]:
        raise SourceBytesExportFailure(f"manifest source_bytes={classification}")
