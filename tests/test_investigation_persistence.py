"""Governing question persistence (issue #71).

The governing question is the interpretive root of the workspace. It must be
durable in the database, not merely cached in the browser. These tests exercise
the /api/investigation endpoints and the wiring into the synthesis packet, and
confirm no canonical evidence is touched.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fresh_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "investigation.db"
    SQLiteStore(db_path).close()
    return db_path


def _client(db_path: Path):
    return create_app(db_path=db_path).test_client()


# ── Persistence + retrieval ────────────────────────────────────────────────


def test_saving_the_question_persists_to_the_database(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    client = _client(db_path)

    resp = client.put(
        "/api/investigation",
        json={
            "thesis": "How does desire depend on distance?",
            "purpose": "Trace aspiration across the novel.",
            "lenses": ["aspiration", "class"],
            "created": "2026-07-01T00:00:00+00:00",
        },
    )
    assert resp.status_code == 200

    # It is in the database, in its own durable table — not only localStorage.
    verify = sqlite3.connect(db_path)
    row = verify.execute(
        "SELECT thesis, purpose, lenses FROM workspace_investigation WHERE id = 'current'"
    ).fetchone()
    verify.close()
    assert row is not None
    assert row[0] == "How does desire depend on distance?"
    assert row[1] == "Trace aspiration across the novel."
    assert "aspiration" in row[2]


def test_loading_prefers_the_database_question(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    client = _client(db_path)
    client.put("/api/investigation", json={"thesis": "The durable question."})

    body = client.get("/api/investigation").get_json()
    assert body["investigation"]["thesis"] == "The durable question."
    assert body["investigation"]["lenses"] == []


def test_empty_workspace_returns_no_investigation(tmp_path: Path):
    body = _client(_fresh_db(tmp_path)).get("/api/investigation").get_json()
    assert body["investigation"] is None


def test_thesis_is_required(tmp_path: Path):
    resp = _client(_fresh_db(tmp_path)).put("/api/investigation", json={"thesis": "  "})
    assert resp.status_code == 400


def test_revision_updates_but_preserves_created_at(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    client = _client(db_path)
    first = client.put(
        "/api/investigation",
        json={"thesis": "First question.", "created": "2026-07-01T00:00:00+00:00"},
    ).get_json()["investigation"]
    second = client.put(
        "/api/investigation", json={"thesis": "Revised question."}
    ).get_json()["investigation"]

    assert second["thesis"] == "Revised question."
    assert second["created_at"] == first["created_at"]  # original creation preserved
    assert second["updated_at"] >= first["updated_at"]

    # Still a single row (mutable, not append-only).
    verify = sqlite3.connect(db_path)
    count = verify.execute("SELECT COUNT(*) FROM workspace_investigation").fetchone()[0]
    verify.close()
    assert count == 1


# ── Migration path (legacy browser-only question) ──────────────────────────


def test_legacy_localStorage_question_can_be_migrated_via_put(tmp_path: Path):
    """The client migrates a browser-only question by PUTting it when the DB has
    none; the endpoint accepts that legacy shape and makes it durable."""
    db_path = _fresh_db(tmp_path)
    client = _client(db_path)
    assert client.get("/api/investigation").get_json()["investigation"] is None

    # Simulate _invHydrate's migration call for a legacy value.
    client.put(
        "/api/investigation",
        json={
            "thesis": "A question that only lived in the browser.",
            "lenses": ["memory"],
            "created": "2026-06-01T00:00:00+00:00",
        },
    )
    body = client.get("/api/investigation").get_json()
    assert body["investigation"]["thesis"] == "A question that only lived in the browser."
    assert body["investigation"]["created_at"] == "2026-06-01T00:00:00+00:00"


# ── Wiring: synthesis packet + Field Notes snapshot + canonical safety ─────


def test_synthesis_packet_uses_the_durable_governing_question(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    doc_id = "a" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 10, _now(), "test", "primary", 0),
    )
    conn.commit()
    conn.close()

    client = _client(db_path)
    client.put("/api/investigation", json={"thesis": "The durable compass."})

    packet = client.get(f"/api/study/compile?document_id={doc_id}").get_json()[
        "synthesis_packet"
    ]
    assert packet["governing_question"] == "The durable compass."


def test_field_notes_still_snapshot_the_governing_question(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    doc_id = "b" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 10, _now(), "test", "primary", 0),
    )
    conn.commit()
    conn.close()

    client = _client(db_path)
    assert client.post(
        "/api/investigation-log",
        json={
            "lane": "corpus",
            "understanding": "Distance sustains desire.",
            "source_document_id": doc_id,
            "governing_question": "How does desire depend on distance?",
        },
    ).status_code == 201

    verify = sqlite3.connect(db_path)
    snap = verify.execute(
        "SELECT governing_question FROM investigation_log LIMIT 1"
    ).fetchone()
    verify.close()
    assert snap[0] == "How does desire depend on distance?"


def test_saving_the_question_does_not_touch_canonical_evidence(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    client = _client(db_path)
    client.put("/api/investigation", json={"thesis": "A question."})

    verify = sqlite3.connect(db_path)
    assert verify.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    assert verify.execute("SELECT COUNT(*) FROM source_extractions").fetchone()[0] == 0
    assert verify.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 0
    verify.close()


# ── UI still renders the question (Compass + Your Question form) ────────────


def test_question_compass_and_form_still_present_in_ui():
    index = (
        Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
    ).read_text()
    assert "_crRenderQuestionCompass" in index
    assert 'id="cr-question-compass"' in index
    assert "_crRenderQuestionCard" in index
    assert "Keep this question" in index
    # invSave now also persists to the durable endpoint.
    assert "/api/investigation" in index
    assert "_invHydrate" in index
