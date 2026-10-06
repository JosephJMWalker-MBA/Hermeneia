"""Frozen witnesses for #222, #223, #224 and #239: upload source-artifact binding.

A compiled SourceDocument keeps its own source bytes in uploads/ under a name
the server controls; it records the user's filename as metadata; and the
upload route acts on the document it actually compiled. Synthetic PDFs only.
"""
from __future__ import annotations

import hashlib
import io
import sqlite3
import threading

import fitz
import pytest

from hermeneia.compiler import compiler as compiler_module
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


class SourceBindingFailure(AssertionError):
    """Only the observed source-binding failures are expected here."""


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
    return tmp_path, ws, db, app


def _upload(app, data: bytes, name: str, role: str | None = None):
    form = {"file": (io.BytesIO(data), name), **({"role": role} if role else {})}
    return app.test_client().post("/api/upload", data=form, content_type="multipart/form-data")


def _stored_hashes(ws) -> set[str]:
    return {hashlib.sha256(p.read_bytes()).hexdigest() for p in (ws / "uploads").iterdir() if p.is_file()}


def _roles(db) -> dict[str, str]:
    return dict(sqlite3.connect(db).execute("SELECT id, source_role FROM source_documents"))


@pytest.mark.xfail(strict=True, raises=SourceBindingFailure,
                   reason="#222: a second PDF with an existing filename loses its bytes; repair requires its own packet")
def test_same_filename_different_documents_both_keep_source_bytes(workspace):
    _tmp, ws, _db, app = workspace
    a, b = _pdf("First document text."), _pdf("A different second document.")
    assert _upload(app, a, "chapter.pdf").status_code == 200
    assert _upload(app, b, "chapter.pdf").status_code == 200
    missing = {hashlib.sha256(x).hexdigest() for x in (a, b)} - _stored_hashes(ws)
    if missing:
        raise SourceBindingFailure(f"source bytes missing for {sorted(missing)}")


@pytest.mark.xfail(strict=True, raises=SourceBindingFailure,
                   reason="#222: concurrent same-name uploads overwrite each other; repair requires its own packet")
def test_concurrent_same_filename_uploads_both_keep_source_bytes(workspace):
    _tmp, ws, _db, app = workspace
    a, b = _pdf("First concurrent document."), _pdf("Second concurrent document.")
    start = threading.Barrier(2, timeout=20)
    statuses = []

    def go(data):
        start.wait()
        statuses.append(_upload(app, data, "chapter.pdf").status_code)

    threads = [threading.Thread(target=go, args=(x,)) for x in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    missing = {hashlib.sha256(x).hexdigest() for x in (a, b)} - _stored_hashes(ws)
    if sorted(statuses) != [200, 200] or missing:
        raise SourceBindingFailure(f"statuses={statuses} missing={sorted(missing)}")


@pytest.mark.xfail(strict=True, raises=SourceBindingFailure,
                   reason="#223: original_filename records the temporary name; repair requires its own packet")
def test_original_filename_records_the_uploaded_name(workspace):
    _tmp, _ws, db, app = workspace
    assert _upload(app, _pdf("The lamp burned all night."), "My Study.pdf").status_code == 200
    names = [r[0] for r in sqlite3.connect(db).execute("SELECT original_filename FROM source_documents")]
    if names != ["My Study.pdf"]:
        raise SourceBindingFailure(f"original_filename={names}")


@pytest.mark.xfail(strict=True, raises=SourceBindingFailure,
                   reason="#224: re-upload applies the role to another document; repair requires its own packet")
def test_reupload_applies_role_to_the_uploaded_document(workspace):
    _tmp, _ws, db, app = workspace
    a, b = _pdf("Document A text."), _pdf("Document B text.")
    ida, idb = hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest()
    _upload(app, a, "a.pdf")
    _upload(app, b, "b.pdf")
    body = _upload(app, a, "a-again.pdf", role="reference").get_json()
    roles = _roles(db)
    if body["document_id"] != ida or roles != {ida: "reference", idb: "primary"}:
        raise SourceBindingFailure(f"response={body['document_id'][:12]} roles={roles}")


@pytest.mark.xfail(strict=True, raises=SourceBindingFailure,
                   reason="#224: concurrent uploads misattribute the compiled document; repair requires its own packet")
def test_concurrent_new_uploads_apply_role_to_their_own_documents(workspace, monkeypatch):
    _tmp, _ws, db, app = workspace
    a, b = _pdf("Document A, uploaded as reference."), _pdf("Document B, uploaded as primary.")
    ida, idb = hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest()
    real_compile = compiler_module.Compiler.compile
    armed = {"done": False}

    def compile_then_let_b_finish(self, path, *args, **kwargs):
        result = real_compile(self, path, *args, **kwargs)
        if not armed["done"]:
            armed["done"] = True
            t = threading.Thread(target=lambda: _upload(app, b, "B_primary.pdf"))
            t.start()
            t.join(60)
        return result

    monkeypatch.setattr(compiler_module.Compiler, "compile", compile_then_let_b_finish)
    body = _upload(app, a, "A_ref.pdf", role="reference").get_json()
    roles = _roles(db)
    if body["document_id"] != ida or roles != {ida: "reference", idb: "primary"}:
        raise SourceBindingFailure(f"response={body['document_id'][:12]} roles={roles}")


@pytest.mark.xfail(strict=True, raises=SourceBindingFailure,
                   reason="#239: the raw client filename becomes a storage path; repair requires its own packet")
def test_client_filename_never_becomes_a_storage_path(workspace):
    tmp, ws, db, app = workspace
    outside = tmp / "outside"
    outside.mkdir()
    a, b = _pdf("Traversal one."), _pdf("Traversal two.")
    _upload(app, a, "../escaped.pdf")
    _upload(app, b, str(outside / "absolute.pdf"))
    escaped = [p for p in ((ws / "escaped.pdf"), (outside / "absolute.pdf")) if p.exists()]
    missing = {hashlib.sha256(x).hexdigest() for x in (a, b)} - _stored_hashes(ws)
    names = sorted(r[0] for r in sqlite3.connect(db).execute("SELECT original_filename FROM source_documents"))
    if escaped or missing or names != ["absolute.pdf", "escaped.pdf"]:
        raise SourceBindingFailure(f"escaped={escaped} missing={sorted(missing)} names={names}")


def test_identical_content_uploaded_concurrently_is_one_document_with_bytes(workspace):
    _tmp, ws, db, app = workspace
    data = _pdf("Same bytes twice.")
    start = threading.Barrier(2, timeout=20)
    bodies = []

    def go(name):
        start.wait()
        bodies.append(_upload(app, data, name).get_json())

    threads = [threading.Thread(target=go, args=(n,)) for n in ("one.pdf", "two.pdf")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    digest = hashlib.sha256(data).hexdigest()
    assert {b["document_id"] for b in bodies} == {digest}
    assert digest in _stored_hashes(ws)
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 1
