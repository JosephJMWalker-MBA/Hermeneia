"""Frozen witness for #237: a failed write request must not keep the workspace locked.

Each listed route opens a read-write connection, executes a write, and commits.
If anything raises after the write (here: the commit itself fails once), the
request's transaction must be rolled back and its connection released before
the next request, so an independent writer can take the lock immediately.
Synthetic workspace only.
"""
from __future__ import annotations

import io
import sqlite3
import types

import fitz
import pytest

import hermeneia.web.app as webapp
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


class WorkspaceLockHeld(AssertionError):
    """Only the observed leaked-transaction failure is expected here."""


class _FailingCommitConnection:
    """Delegates to a real connection; the armed commit fails once."""

    armed = False

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)

    def commit(self):
        if _FailingCommitConnection.armed:
            _FailingCommitConnection.armed = False
            raise sqlite3.OperationalError("injected failure after write")
        return self._real.commit()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    db = tmp_path / "workspace.db"
    SQLiteStore(db).close()
    app = create_app(db_path=db)
    app.config["TESTING"] = False
    client = app.test_client()
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "The lamp burned all night. Nobody asked why it burned.")
    doc_id = client.post("/api/upload", data={"file": (io.BytesIO(doc.tobytes()), "s.pdf")},
                         content_type="multipart/form-data").get_json()["document_id"]
    obs_id = sqlite3.connect(db).execute("SELECT id FROM observations ORDER BY id").fetchone()[0]
    highlight = client.post("/api/reader/highlights", json={
        "source_document_id": doc_id, "page": 1, "source_locator": "page:1:block:0",
        "selected_text": "lamp"}).get_json()
    note = client.post(f"/api/observations/{obs_id}/inquiry", json={"question_text": "Why?"}).get_json()

    shim = types.SimpleNamespace(**{k: getattr(sqlite3, k) for k in dir(sqlite3) if not k.startswith("__")})
    shim.connect = lambda *a, **k: _FailingCommitConnection(sqlite3.connect(*a, **k))
    monkeypatch.setattr(webapp, "sqlite3", shim)
    return db, client, {"doc": doc_id, "obs": obs_id, "hl": highlight["id"],
                        "note": (note.get("inquiry_note") or note)["id"]}


ROUTES = {
    "observation_review": ("POST", "/api/observations/{obs}/review", {"review_status": "approved"}),
    "inquiry_create": ("POST", "/api/observations/{obs}/inquiry", {"question_text": "Another question?"}),
    "inquiry_delete": ("DELETE", "/api/observations/{obs}/inquiry/{note}", None),
    "highlight_create": ("POST", "/api/reader/highlights", {"source_document_id": "{doc}", "page": 1,
                                                            "source_locator": "page:1:block:0", "selected_text": "night"}),
    "highlight_update": ("PATCH", "/api/reader/highlights/{hl}", {"note_text": "edited"}),
    "highlight_dismiss": ("DELETE", "/api/reader/highlights/{hl}", None),
    "reading_progress": ("POST", "/api/reader/progress", {"document_id": "{doc}", "page": 1}),
    "highlight_promote": ("POST", "/api/reader/highlights/{hl}/promote", None),
    "field_note_create": ("POST", "/api/investigation-log", {"lane": "corpus", "understanding": "Noted."}),
    "investigation_update": ("PUT", "/api/investigation", {"thesis": "A governing question?"}),
}


def _fill(value, ids):
    if isinstance(value, str):
        return value.format(**ids)
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


@pytest.mark.xfail(strict=True, raises=WorkspaceLockHeld,
                   reason="#237: write routes leak an open transaction on exceptions; repair requires its own packet")
@pytest.mark.parametrize("route", sorted(ROUTES))
def test_failed_write_request_releases_the_workspace_lock(workspace, route):
    db, client, ids = workspace
    method, url, body = ROUTES[route]
    _FailingCommitConnection.armed = True
    response = client.open(_fill(url, ids), method=method, json=_fill(body, ids))
    assert response.status_code >= 500, (route, response.status_code)
    assert not _FailingCommitConnection.armed, "the injected failure must happen after the route's write"

    probe = sqlite3.connect(db, timeout=0)
    try:
        probe.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        raise WorkspaceLockHeld(f"{route}: {exc}") from exc
    finally:
        probe.close()
