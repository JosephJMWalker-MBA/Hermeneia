"""
Companion API Tests (issue #10)

Invariant: the Companion is a reading participant, not an authority.
Context is explicit — only the sections the reader checked are gathered
and sent, never silently expanded — and every reply reports exactly what
context was used. Nothing the Companion says enters the record.

Covers:
  - only checked context sections reach the provider prompt
  - no flags -> only the reader's message is sent (no silent expansion)
  - context_used echoes what was gathered, including requested-but-empty
  - observations from excluded documents never enter the context
  - stub provider answers without any AI configured
  - validation: missing message, unknown provider
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import hermeneia.web.app as webapp
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "companion_test.db"
    store = SQLiteStore(db_path)
    store.close()
    return db_path


def _seed(db: Path, doc_id: str, excluded: int = 0) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT OR IGNORE INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 10, _now(), "test", "primary", excluded),
    )
    ext_id = doc_id[:8] + "_ext"
    conn.execute(
        """INSERT OR IGNORE INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ext_id, doc_id, 2, "body", "Then wear the gold hat, if that will move her;",
         "test", "1", "{}", "p.2", doc_id[:32], doc_id[:32], _now()),
    )
    conn.execute(
        """INSERT OR IGNORE INTO observations
           (id, epistemic_class, source_document_id, raw_text, source_locator,
            semantic_hash, page, paragraph, sentence, source_extraction_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (doc_id[:8] + "_obs", "Evidence", doc_id,
         "Then wear the gold hat, if that will move her;", "p.2",
         doc_id[:32], 2, 1, 1, ext_id, _now()),
    )
    conn.commit()
    conn.close()


class _Capture:
    """Stands in for _call_provider; records the prompt it was given."""
    def __init__(self):
        self.system = None
        self.user = None

    def __call__(self, provider, system, user):
        self.system = system
        self.user = user
        return "A grounded reply."


def test_only_checked_context_reaches_the_provider(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    doc_id = "a" * 64
    _seed(db, doc_id)
    cap = _Capture()
    monkeypatch.setattr(webapp, "_call_provider", cap)

    client = create_app(db_path=db).test_client()
    r = client.post("/api/companion/ask", json={
        "provider": "stub",
        "message": "What is this passage doing?",
        "document_id": doc_id,
        "page": 2,
        "context_flags": {"governing_question": True, "selected_passage": True},
        "selected_text": "wear the gold hat",
        "governing_question_text": "What is the green light asking Gatsby to believe?",
    })
    assert r.status_code == 200
    body = r.get_json()

    assert "wear the gold hat" in cap.user
    assert "green light asking Gatsby" in cap.user
    # Unchecked sections must be absent — no silent expansion.
    assert "MACHINE OBSERVATIONS" not in cap.user
    assert "CURRENT PAGE" not in cap.user
    assert "SAVED HIGHLIGHTS" not in cap.user

    used = {c["key"] for c in body["context_used"]}
    assert used == {"governing_question", "selected_passage"}


def test_no_flags_sends_only_the_message(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    doc_id = "b" * 64
    _seed(db, doc_id)
    cap = _Capture()
    monkeypatch.setattr(webapp, "_call_provider", cap)

    client = create_app(db_path=db).test_client()
    r = client.post("/api/companion/ask", json={
        "provider": "stub",
        "message": "Hello.",
        "document_id": doc_id,
        "page": 2,
        "context_flags": {},
        # Data present but unchecked — must not leak into the prompt.
        "selected_text": "should not appear",
        "governing_question_text": "should not appear either",
    })
    assert r.status_code == 200
    assert cap.user.strip() == "READER'S MESSAGE:\nHello."
    assert r.get_json()["context_used"] == []


def test_requested_but_empty_context_is_reported(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    doc_id = "c" * 64
    _seed(db, doc_id)
    monkeypatch.setattr(webapp, "_call_provider", _Capture())

    client = create_app(db_path=db).test_client()
    r = client.post("/api/companion/ask", json={
        "provider": "stub",
        "message": "Anything selected?",
        "document_id": doc_id,
        "page": 2,
        "context_flags": {"selected_passage": True},
        "selected_text": "",
    })
    assert r.status_code == 200
    used = r.get_json()["context_used"]
    assert used and used[0]["key"] == "selected_passage"
    assert "nothing is selected" in used[0]["summary"]


def test_excluded_document_observations_never_enter_context(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    doc_id = "d" * 64
    _seed(db, doc_id, excluded=1)
    cap = _Capture()
    monkeypatch.setattr(webapp, "_call_provider", cap)

    client = create_app(db_path=db).test_client()
    r = client.post("/api/companion/ask", json={
        "provider": "stub",
        "message": "What do the observations say?",
        "document_id": doc_id,
        "page": 2,
        "context_flags": {"page_observations": True, "current_page": True},
    })
    assert r.status_code == 200
    assert "gold hat" not in (cap.user or ""), (
        "Excluded-document content must never reach the Companion"
    )
    summaries = " ".join(c["summary"] for c in r.get_json()["context_used"])
    assert "requested, but" in summaries


def test_stub_provider_answers_without_ai(tmp_path):
    db = _make_db(tmp_path)
    doc_id = "e" * 64
    _seed(db, doc_id)

    client = create_app(db_path=db).test_client()
    r = client.post("/api/companion/ask", json={
        "provider": "stub",
        "message": "Are you there?",
        "context_flags": {},
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["reply"]
    assert body["provider"] == "Stub (no AI)"


def test_validation(tmp_path):
    db = _make_db(tmp_path)
    client = create_app(db_path=db).test_client()
    assert client.post("/api/companion/ask", json={
        "provider": "stub", "message": ""}).status_code == 400
    assert client.post("/api/companion/ask", json={
        "provider": "not-a-provider", "message": "hi"}).status_code == 400
