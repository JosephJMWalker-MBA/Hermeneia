"""
Investigation Log / Field Notes Tests (issue #18)

Invariant: the investigator's evolving understanding is part of the
record. Entries are append-only snapshots — later understanding
supersedes; it never rewrites. Two lanes: 'corpus' (learning about the
text) and 'instrument' (learning about Hermeneia while using it).

Covers:
  - entries round-trip with timestamp, page, document, governing question
  - entries persist across app restart (the requirement: survive reloads)
  - lane filter; lane validation; empty-entry validation
  - questions-only entries are allowed
  - entries are immutable at the database level (trigger)
  - unknown document ids are stored as unattributed, not rejected
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "invlog_test.db"
    store = SQLiteStore(db_path)
    store.close()
    return db_path


def _insert_doc(db: Path, doc_id: str) -> None:
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


def test_entry_round_trip_with_full_metadata(tmp_path):
    db = _make_db(tmp_path)
    doc_id = "a" * 64
    _insert_doc(db, doc_id)
    client = create_app(db_path=db).test_client()

    r = client.post("/api/investigation-log", json={
        "lane": "corpus",
        "understanding": "Gatsby's problem may be aspiration that refuses correction by reality.",
        "pressing_questions": "Where does the text distinguish hope from self-deception?",
        "source_document_id": doc_id,
        "page": 2,
        "governing_question": "What is the green light asking Gatsby to believe?",
    })
    assert r.status_code == 201

    entries = client.get("/api/investigation-log").get_json()["entries"]
    assert len(entries) == 1
    e = entries[0]
    assert e["lane"] == "corpus"
    assert "refuses correction" in e["understanding"]
    assert "hope from self-deception" in e["pressing_questions"]
    assert e["source_document_id"] == doc_id
    assert e["original_filename"] == "gatsby.pdf"
    assert e["page"] == 2
    assert "green light" in e["governing_question"]
    assert e["created_at"]


def test_entries_persist_across_app_restart(tmp_path):
    """The requirement: saved entries must survive reloads and updates."""
    db = _make_db(tmp_path)
    first = create_app(db_path=db).test_client()
    r = first.post("/api/investigation-log", json={
        "lane": "instrument",
        "understanding": "The Reader must become the primary workspace.",
    })
    assert r.status_code == 201

    # Fresh app instance over the same DB — runs the startup migration path.
    second = create_app(db_path=db).test_client()
    entries = second.get("/api/investigation-log").get_json()["entries"]
    assert len(entries) == 1
    assert entries[0]["understanding"].startswith("The Reader must become")


def test_lane_filter_and_distinction(tmp_path):
    db = _make_db(tmp_path)
    client = create_app(db_path=db).test_client()
    client.post("/api/investigation-log", json={
        "lane": "corpus", "understanding": "About the text."})
    client.post("/api/investigation-log", json={
        "lane": "instrument", "understanding": "About the instrument."})

    corpus = client.get("/api/investigation-log?lane=corpus").get_json()["entries"]
    instrument = client.get("/api/investigation-log?lane=instrument").get_json()["entries"]
    assert [e["understanding"] for e in corpus] == ["About the text."]
    assert [e["understanding"] for e in instrument] == ["About the instrument."]


def test_validation(tmp_path):
    db = _make_db(tmp_path)
    client = create_app(db_path=db).test_client()
    assert client.post("/api/investigation-log", json={
        "lane": "nonsense", "understanding": "x"}).status_code == 400
    assert client.post("/api/investigation-log", json={
        "lane": "corpus"}).status_code == 400  # nothing to keep


def test_questions_only_entry_is_allowed(tmp_path):
    """Sometimes all you have is the question — that is still progress."""
    db = _make_db(tmp_path)
    client = create_app(db_path=db).test_client()
    r = client.post("/api/investigation-log", json={
        "lane": "corpus",
        "pressing_questions": "Is Nick a moral judge or a revising witness?",
    })
    assert r.status_code == 201
    e = client.get("/api/investigation-log").get_json()["entries"][0]
    assert e["understanding"] is None
    assert "revising witness" in e["pressing_questions"]


def test_entries_are_immutable_at_db_level(tmp_path):
    """Snapshots of understanding are append-only: later understanding
    supersedes, it never rewrites."""
    db = _make_db(tmp_path)
    client = create_app(db_path=db).test_client()
    client.post("/api/investigation-log", json={
        "lane": "corpus", "understanding": "First reading."})

    conn = sqlite3.connect(db)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE investigation_log SET understanding = 'rewritten'")
    conn.close()


def test_unknown_document_stored_as_unattributed(tmp_path):
    db = _make_db(tmp_path)
    client = create_app(db_path=db).test_client()
    r = client.post("/api/investigation-log", json={
        "lane": "corpus",
        "understanding": "Noted between documents.",
        "source_document_id": "nope" * 16,
    })
    assert r.status_code == 201
    e = client.get("/api/investigation-log").get_json()["entries"][0]
    assert e["source_document_id"] is None
