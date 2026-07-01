"""
Inquiry Notes Tests

Invariants:
  - Approved, rejected, and unsure observations can all have inquiry notes.
  - Questions are first-class records: observation_id and review_status preserved.
  - Inquiry notes do not alter canonical observation text.
  - Inquiry notes do not automatically create interpretations.
  - Muted (excluded) corpus documents are excluded from observation queries,
    but inquiry notes on their observations are not auto-deleted.
  - One review record per observation (upsert semantics).
  - Deleting an inquiry note does not affect the review record.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "hermeneia.db"
    store = SQLiteStore(db)
    store.close()
    return db


def _seed_observation(conn: sqlite3.Connection) -> str:
    doc_id = str(uuid.uuid4())
    ext_id = str(uuid.uuid4())
    obs_id = str(uuid.uuid4())
    sem_hash = str(uuid.uuid4())  # unique per call
    conn.execute(
        """INSERT INTO source_documents
           (id, file_hash, original_filename, total_pages, registered_at, compiler_version)
           VALUES (?,?,?,?,?,?)""",
        (doc_id, f"hash-{doc_id[:8]}", "test.pdf", 100,
         "2026-01-01T00:00:00+00:00", "test"),
    )
    conn.execute(
        """INSERT INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ext_id, doc_id, 20, "body", "full text", "test", "0",
         "{}", "p.20", f"sh-{ext_id[:8]}", f"h-{ext_id[:8]}", "2026-01-01T00:00:00+00:00"),
    )
    conn.execute(
        """INSERT INTO observations
           (id, epistemic_class, source_document_id, source_extraction_id,
            raw_text, source_locator, semantic_hash, page, paragraph, sentence, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (obs_id, "Evidence", doc_id, ext_id,
         "The green light burned at the end of Daisy's dock.",
         "p.20", sem_hash, 20, 1, 1, "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()
    return obs_id


@pytest.fixture
def app_client(tmp_path):
    db = _make_db(tmp_path)
    from hermeneia.web.app import create_app
    flask_app = create_app(db_path=str(db))
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client, db


@pytest.fixture
def seeded_client(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    obs_id = _seed_observation(conn)
    conn.close()
    from hermeneia.web.app import create_app
    flask_app = create_app(db_path=str(db))
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client, obs_id, db


# ── Schema ────────────────────────────────────────────────────────────────────

def test_inquiry_tables_created(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "observation_reviews" in tables
    assert "inquiry_notes" in tables
    conn.close()


def test_one_review_per_observation(tmp_path):
    """Upsert semantics: second POST updates rather than duplicates."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    obs_id = _seed_observation(conn)
    conn.close()

    from hermeneia.web.app import create_app
    app = create_app(db_path=str(db))
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post(f"/api/observations/{obs_id}/review",
               json={"review_status": "approved", "reason_for_status": "Looks good"})
        c.post(f"/api/observations/{obs_id}/review",
               json={"review_status": "unsure", "reason_for_status": "Actually unclear"})
        conn2 = sqlite3.connect(str(db))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute(
            "SELECT COUNT(*) as cnt FROM observation_reviews WHERE observation_id=?",
            (obs_id,),
        ).fetchone()
        assert rows[0] == 1
        row = conn2.execute(
            "SELECT review_status, reason_for_status FROM observation_reviews WHERE observation_id=?",
            (obs_id,),
        ).fetchone()
        assert row["review_status"] == "unsure"
        assert row["reason_for_status"] == "Actually unclear"
        conn2.close()


# ── Review status for each judgment ──────────────────────────────────────────

@pytest.mark.parametrize("status", ["approved", "rejected", "unsure"])
def test_review_status_stored(seeded_client, status):
    client, obs_id, _ = seeded_client
    r = client.post(f"/api/observations/{obs_id}/review",
                    json={"review_status": status})
    assert r.status_code == 200
    data = r.get_json()
    assert data["review"]["review_status"] == status
    assert data["review"]["observation_id"] == obs_id


# ── Inquiry notes attach to any status ───────────────────────────────────────

@pytest.mark.parametrize("status", ["approved", "rejected", "unsure"])
def test_inquiry_note_on_any_status(seeded_client, status):
    client, obs_id, _ = seeded_client
    client.post(f"/api/observations/{obs_id}/review",
                json={"review_status": status})
    r = client.post(f"/api/observations/{obs_id}/inquiry",
                    json={"question_text": "What passage supports this?",
                          "question_type": "evidence_needed"})
    assert r.status_code == 201
    note = r.get_json()["inquiry_note"]
    assert note["observation_id"] == obs_id
    assert note["question_type"] == "evidence_needed"


def test_inquiry_note_without_prior_review(seeded_client):
    """Notes can be added before a review status is set."""
    client, obs_id, _ = seeded_client
    r = client.post(f"/api/observations/{obs_id}/inquiry",
                    json={"question_text": "Is this overreach?",
                          "question_type": "overreach_suspected"})
    assert r.status_code == 201


def test_multiple_inquiry_notes(seeded_client):
    client, obs_id, _ = seeded_client
    client.post(f"/api/observations/{obs_id}/review",
                json={"review_status": "unsure"})
    for q in ["First question?", "Second question?", "Third question?"]:
        client.post(f"/api/observations/{obs_id}/inquiry",
                    json={"question_text": q})
    r = client.get(f"/api/observations/{obs_id}/review")
    notes = r.get_json()["inquiry_notes"]
    assert len(notes) == 3


# ── question_text preserved with observation_id and review_status ─────────────

def test_question_records_preserve_fields(seeded_client):
    client, obs_id, db = seeded_client
    client.post(f"/api/observations/{obs_id}/review",
                json={"review_status": "rejected",
                      "reason_for_status": "No textual support"})
    client.post(f"/api/observations/{obs_id}/inquiry",
                json={"question_text": "What passage would prove this?",
                      "question_type": "evidence_needed"})
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    note = conn.execute(
        "SELECT * FROM inquiry_notes WHERE observation_id=?", (obs_id,)
    ).fetchone()
    rev = conn.execute(
        "SELECT * FROM observation_reviews WHERE observation_id=?", (obs_id,)
    ).fetchone()
    conn.close()
    assert note["observation_id"] == obs_id
    assert note["question_text"] == "What passage would prove this?"
    assert rev["review_status"] == "rejected"


# ── Notes do not alter observation text ──────────────────────────────────────

def test_notes_do_not_alter_observation_text(seeded_client):
    client, obs_id, db = seeded_client
    original_text = "The green light burned at the end of Daisy's dock."
    client.post(f"/api/observations/{obs_id}/review",
                json={"review_status": "approved"})
    client.post(f"/api/observations/{obs_id}/inquiry",
                json={"question_text": "Why does the green light matter?"})
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    obs = conn.execute(
        "SELECT raw_text FROM observations WHERE id=?", (obs_id,)
    ).fetchone()
    conn.close()
    assert obs["raw_text"] == original_text


# ── Notes do not create interpretations ──────────────────────────────────────

def test_notes_do_not_create_interpretations(seeded_client):
    client, obs_id, db = seeded_client
    client.post(f"/api/observations/{obs_id}/review",
                json={"review_status": "unsure",
                      "steward_note": "Unclear significance"})
    for q in ["Is this about class?", "Or performance?"]:
        client.post(f"/api/observations/{obs_id}/inquiry",
                    json={"question_text": q})
    conn = sqlite3.connect(str(db))
    count = conn.execute("SELECT COUNT(*) FROM interpretations").fetchone()[0]
    conn.close()
    assert count == 0


# ── Delete inquiry note ───────────────────────────────────────────────────────

def test_delete_inquiry_note(seeded_client):
    client, obs_id, _ = seeded_client
    r = client.post(f"/api/observations/{obs_id}/inquiry",
                    json={"question_text": "To be deleted"})
    note_id = r.get_json()["inquiry_note"]["id"]
    client.delete(f"/api/observations/{obs_id}/inquiry/{note_id}")
    r2 = client.get(f"/api/observations/{obs_id}/review")
    notes = r2.get_json()["inquiry_notes"]
    assert not any(n["id"] == note_id for n in notes)


def test_delete_note_does_not_affect_review(seeded_client):
    client, obs_id, _ = seeded_client
    client.post(f"/api/observations/{obs_id}/review",
                json={"review_status": "approved"})
    r = client.post(f"/api/observations/{obs_id}/inquiry",
                    json={"question_text": "Transient question"})
    note_id = r.get_json()["inquiry_note"]["id"]
    client.delete(f"/api/observations/{obs_id}/inquiry/{note_id}")
    r2 = client.get(f"/api/observations/{obs_id}/review")
    assert r2.get_json()["review"]["review_status"] == "approved"


# ── Invalid inputs ────────────────────────────────────────────────────────────

def test_invalid_review_status_rejected(seeded_client):
    client, obs_id, _ = seeded_client
    r = client.post(f"/api/observations/{obs_id}/review",
                    json={"review_status": "maybe"})
    assert r.status_code == 400


def test_empty_question_text_rejected(seeded_client):
    client, obs_id, _ = seeded_client
    r = client.post(f"/api/observations/{obs_id}/inquiry",
                    json={"question_text": "   "})
    assert r.status_code == 400


def test_unknown_question_type_falls_back_to_unclassified(seeded_client):
    client, obs_id, _ = seeded_client
    r = client.post(f"/api/observations/{obs_id}/inquiry",
                    json={"question_text": "Valid question?",
                          "question_type": "totally_made_up"})
    assert r.status_code == 201
    assert r.get_json()["inquiry_note"]["question_type"] == "unclassified"


# ── Review summary ────────────────────────────────────────────────────────────

def test_review_summary_counts(tmp_path):
    db = _make_db(tmp_path)
    from hermeneia.web.app import create_app
    app = create_app(db_path=str(db))
    app.config["TESTING"] = True
    with app.test_client() as c:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        obs_ids = [_seed_observation(conn) for _ in range(4)]
        conn.close()
        statuses = ["approved", "approved", "rejected", "unsure"]
        for obs_id, status in zip(obs_ids, statuses):
            c.post(f"/api/observations/{obs_id}/review",
                   json={"review_status": status})
        for obs_id in obs_ids[:2]:
            c.post(f"/api/observations/{obs_id}/inquiry",
                   json={"question_text": "Why?", "question_type": "meaning_unclear"})
        r = c.get("/api/observations/reviews/summary")
        d = r.get_json()
        assert d["approved"] == 2
        assert d["rejected"] == 1
        assert d["unsure"] == 1
        assert d["total"] == 4
        assert d["questions"] == 2
        assert d["by_question_type"]["meaning_unclear"] == 2


def test_follow_up_needed_counted_in_summary(seeded_client):
    client, obs_id, _ = seeded_client
    client.post(f"/api/observations/{obs_id}/review",
                json={"review_status": "unsure", "follow_up_needed": True})
    r = client.get("/api/observations/reviews/summary")
    assert r.get_json()["follow_up_needed"] == 1
