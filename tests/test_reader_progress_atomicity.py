"""Frozen witnesses for #236 and #226: reading progress must be an atomic upsert.

Two progress posts for one document may overlap. Each accepted page must be
stored, concurrent first posts must not fail, and the post whose page set
reaches 100% must record completion. Synthetic workspace only.
"""
from __future__ import annotations

import io
import sqlite3
import threading
import time
from datetime import datetime as _real_datetime

import fitz
import pytest

import hermeneia.web.app as webapp
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


class LostProgress(AssertionError):
    """Only the observed lost-update / missing-completion failures are expected here."""


def _document(client, pages: int) -> str:
    doc = fitz.open()
    for index in range(pages):
        doc.new_page().insert_text((72, 72), f"Page {index + 1} text.")
    return client.post("/api/upload", data={"file": (io.BytesIO(doc.tobytes()), f"doc{pages}.pdf")},
                       content_type="multipart/form-data").get_json()["document_id"]


@pytest.fixture
def workspace(tmp_path):
    db = tmp_path / "workspace.db"
    SQLiteStore(db).close()
    app = create_app(db_path=db)
    app.config["TESTING"] = False
    return db, app


def _stored(db, doc_id):
    return sqlite3.connect(db).execute(
        "SELECT pages_read, percent_read, completed_at FROM reading_progress WHERE document_id = ?",
        (doc_id,)).fetchone()


def _concurrent_posts(monkeypatch, app, doc_id, pages):
    """Start both posts together; each pauses at its first timestamp, which follows its read."""
    racing = threading.local()

    class SlowFirstTimestamp(_real_datetime):
        @classmethod
        def now(cls, tz=None):
            if getattr(racing, "active", False) and not getattr(racing, "paused", False):
                racing.paused = True
                time.sleep(0.3)
            return _real_datetime.now(tz)

    monkeypatch.setattr(webapp, "datetime", SlowFirstTimestamp)
    start = threading.Barrier(len(pages), timeout=10)
    statuses = {}

    def post(page):
        racing.active = True
        client = app.test_client()
        start.wait()
        statuses[page] = client.post("/api/reader/progress", json={"document_id": doc_id, "page": page}).status_code

    threads = [threading.Thread(target=post, args=(page,)) for page in pages]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    monkeypatch.setattr(webapp, "datetime", _real_datetime)
    return statuses


@pytest.mark.xfail(strict=True, raises=LostProgress,
                   reason="#236: concurrent first posts race on INSERT; repair requires its own packet")
def test_concurrent_first_posts_both_succeed_and_keep_both_pages(workspace, monkeypatch):
    db, app = workspace
    doc_id = _document(app.test_client(), 5)
    statuses = _concurrent_posts(monkeypatch, app, doc_id, [1, 2])
    pages = sorted(__import__("json").loads(_stored(db, doc_id)[0]))
    if statuses != {1: 200, 2: 200} or pages != [1, 2]:
        raise LostProgress(f"statuses={statuses} pages={pages}")


@pytest.mark.xfail(strict=True, raises=LostProgress,
                   reason="#236: progress update is read-modify-write; repair requires its own packet")
def test_concurrent_update_posts_keep_both_pages(workspace, monkeypatch):
    db, app = workspace
    client = app.test_client()
    doc_id = _document(client, 5)
    assert client.post("/api/reader/progress", json={"document_id": doc_id, "page": 1}).status_code == 200
    statuses = _concurrent_posts(monkeypatch, app, doc_id, [2, 3])
    pages = sorted(__import__("json").loads(_stored(db, doc_id)[0]))
    if statuses != {2: 200, 3: 200} or pages != [1, 2, 3]:
        raise LostProgress(f"statuses={statuses} pages={pages}")


@pytest.mark.xfail(strict=True, raises=LostProgress,
                   reason="#226: the first progress row never records completion; repair requires its own packet")
def test_first_post_reaching_completion_sets_completed_at(workspace):
    db, app = workspace
    client = app.test_client()
    doc_id = _document(client, 1)
    response = client.post("/api/reader/progress", json={"document_id": doc_id, "page": 1})
    assert response.status_code == 200 and response.get_json()["percent_read"] == 100.0
    _pages, percent, completed_at = _stored(db, doc_id)
    if percent != 100.0 or not completed_at:
        raise LostProgress(f"percent={percent} completed_at={completed_at!r}")


def test_partial_first_post_does_not_record_completion(workspace):
    db, app = workspace
    client = app.test_client()
    doc_id = _document(client, 3)
    assert client.post("/api/reader/progress", json={"document_id": doc_id, "page": 1}).status_code == 200
    assert _stored(db, doc_id)[2] is None
