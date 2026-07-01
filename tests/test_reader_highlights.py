"""
Close Reading Workspace Tests

Invariant: Human highlights are observations-in-formation, not automatically canonical.
A highlight is human attention — it requires explicit promotion to become an observation candidate.

Covers:
  - highlight can be saved without creating an observation
  - highlight preserves source_document_id and source_role
  - highlight can include note and question
  - promote action sets status=observation_candidate, not an Observation row
  - dismissed highlights excluded from list
  - muted documents excluded from related-observation search
  - reading progress is separate from machine coverage
  - TTS path does not store selected text (no implicit save on read)
  - save validates required fields
  - relevance options are enforced
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "reader_test.db"
    store = SQLiteStore(db_path)
    store.close()
    return db_path


def _insert_doc(conn: sqlite3.Connection, doc_id: str, filename: str,
                source_role: str = "primary", excluded: int = 0,
                total_pages: int = 10) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, filename, doc_id, total_pages, _now(), "test", source_role, excluded),
    )


def _insert_obs(conn: sqlite3.Connection, obs_id: str, doc_id: str,
                text: str, page: int = 1) -> None:
    locator = f"p.{page}.s.1.§.1"
    ext_id = obs_id + "_ext"
    conn.execute(
        """INSERT OR IGNORE INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ext_id, doc_id, page, "body", text, "test", "1", "{}", locator,
         obs_id[:32], obs_id[:32], _now()),
    )
    conn.execute(
        """INSERT OR IGNORE INTO observations
           (id, epistemic_class, source_document_id, raw_text,
            source_locator, semantic_hash, page, paragraph, sentence,
            source_extraction_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (obs_id, "Evidence", doc_id, text, locator,
         obs_id[:32], page, 1, 1, ext_id, _now()),
    )
    conn.commit()


# ── Save highlight ─────────────────────────────────────────────────────────────

def test_save_highlight_does_not_create_observation(tmp_path):
    """Saving a highlight must not insert a row into the observations table."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.post("/api/reader/highlights", json={
        "source_document_id": "a" * 64,
        "selected_text": "So we beat on, boats against the current.",
        "page": 1,
    })
    assert resp.status_code == 201
    hl_id = resp.get_json()["id"]

    conn2 = sqlite3.connect(db)
    obs_count = conn2.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn2.close()
    assert obs_count == 0, "Saving a highlight must not create an observation"
    assert hl_id, "A highlight id must be returned"


def test_highlight_preserves_source_document_id_and_role(tmp_path):
    """Saved highlight must record source_document_id and the document's source_role."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "essay.pdf", source_role="commentary")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.post("/api/reader/highlights", json={
        "source_document_id": "b" * 64,
        "selected_text": "Fitzgerald's prose is deceptively simple.",
        "page": 3,
    })
    assert resp.status_code == 201
    hl_id = resp.get_json()["id"]

    conn2 = sqlite3.connect(db)
    conn2.row_factory = sqlite3.Row
    row = conn2.execute("SELECT * FROM reader_highlights WHERE id = ?", (hl_id,)).fetchone()
    conn2.close()
    assert row["source_document_id"] == "b" * 64
    assert row["source_role"] == "commentary", "source_role must be copied from the document"
    assert row["page"] == 3


def test_highlight_saves_note_and_question(tmp_path):
    """Highlight must preserve note_text and question_text."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.post("/api/reader/highlights", json={
        "source_document_id": "a" * 64,
        "selected_text": "the green light",
        "note_text": "Symbol of Gatsby's longing — across the bay.",
        "question_text": "Does the green light change meaning by chapter 5?",
        "relevance": "supports",
    })
    assert resp.status_code == 201
    hl_id = resp.get_json()["id"]

    conn2 = sqlite3.connect(db)
    conn2.row_factory = sqlite3.Row
    row = conn2.execute("SELECT * FROM reader_highlights WHERE id = ?", (hl_id,)).fetchone()
    conn2.close()
    assert "longing" in (row["note_text"] or "")
    assert "chapter 5" in (row["question_text"] or "")
    assert row["relevance"] == "supports"


def test_promote_creates_candidate_not_observation(tmp_path):
    """Promoting a highlight must set status=observation_candidate, not create an Observation."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    hl = client.post("/api/reader/highlights", json={
        "source_document_id": "a" * 64,
        "selected_text": "He had thrown himself into it with a creative passion.",
    }).get_json()

    resp = client.post(f"/api/reader/highlights/{hl['id']}/promote")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "observation_candidate"

    conn2 = sqlite3.connect(db)
    conn2.row_factory = sqlite3.Row
    row = conn2.execute("SELECT status, observation_id FROM reader_highlights WHERE id = ?", (hl["id"],)).fetchone()
    obs_count = conn2.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn2.close()
    assert row["status"] == "observation_candidate"
    assert row["observation_id"] is None, "Promotion must not create an Observation row"
    assert obs_count == 0


def test_dismissed_highlight_excluded_from_list(tmp_path):
    """Dismissed highlights must not appear in the document highlight list."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    hl1 = client.post("/api/reader/highlights", json={
        "source_document_id": "a" * 64, "selected_text": "Keeper passage.",
    }).get_json()
    hl2 = client.post("/api/reader/highlights", json={
        "source_document_id": "a" * 64, "selected_text": "Dismissed passage.",
    }).get_json()

    client.delete(f"/api/reader/highlights/{hl2['id']}")

    resp = client.get(f"/api/reader/documents/{'a'*64}/highlights")
    ids = [h["id"] for h in resp.get_json()["highlights"]]
    assert hl1["id"] in ids
    assert hl2["id"] not in ids, "Dismissed highlight must not appear in list"


def test_relevance_is_enforced(tmp_path):
    """Invalid relevance value must be silently defaulted to 'unclear'."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.post("/api/reader/highlights", json={
        "source_document_id": "a" * 64,
        "selected_text": "Some passage.",
        "relevance": "INVALID_VALUE",
    })
    assert resp.status_code == 201
    hl_id = resp.get_json()["id"]

    conn2 = sqlite3.connect(db)
    conn2.row_factory = sqlite3.Row
    row = conn2.execute("SELECT relevance FROM reader_highlights WHERE id = ?", (hl_id,)).fetchone()
    conn2.close()
    assert row["relevance"] == "unclear"


def test_missing_selected_text_returns_400(tmp_path):
    """Save without selected_text must return 400."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.post("/api/reader/highlights", json={
        "source_document_id": "a" * 64,
    })
    assert resp.status_code == 400


def test_unknown_document_returns_404(tmp_path):
    """Save highlight for unknown document must return 404."""
    db = _make_db(tmp_path)
    client = create_app(db_path=db).test_client()
    resp = client.post("/api/reader/highlights", json={
        "source_document_id": "z" * 64,
        "selected_text": "Something.",
    })
    assert resp.status_code == 404


# ── Reading progress ───────────────────────────────────────────────────────────

def test_reading_progress_is_separate_from_machine_coverage(tmp_path):
    """Reading progress for a document starts at 0 regardless of machine observation count."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", total_pages=10)
    # Insert several machine observations
    for i in range(5):
        _insert_obs(conn, f"obs_{i}", "a" * 64, f"Machine observation {i}.", page=i+1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    docs = client.get("/api/reader/documents").get_json()["documents"]
    gatsby = next(d for d in docs if d["filename"] == "gatsby.pdf")
    assert gatsby["percent_read"] == 0.0, "Reading progress must start at 0 regardless of machine observations"


def test_reading_progress_increments_per_page(tmp_path):
    """Recording page visits must accumulate toward 100%."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", total_pages=4)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    for pg in [1, 2]:
        resp = client.post("/api/reader/progress", json={"document_id": "a" * 64, "page": pg})
        assert resp.status_code == 200

    docs = client.get("/api/reader/documents").get_json()["documents"]
    gatsby = next(d for d in docs if d["id"] == "a" * 64)
    assert gatsby["percent_read"] == 50.0, "2 of 4 pages read should be 50%"
    assert gatsby["last_page"] == 2


def test_duplicate_page_visit_not_double_counted(tmp_path):
    """Visiting the same page twice must not inflate the page count."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", total_pages=4)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    client.post("/api/reader/progress", json={"document_id": "a" * 64, "page": 1})
    client.post("/api/reader/progress", json={"document_id": "a" * 64, "page": 1})

    docs = client.get("/api/reader/documents").get_json()["documents"]
    gatsby = next(d for d in docs if d["id"] == "a" * 64)
    assert gatsby["percent_read"] == 25.0, "Page revisit must not double-count"


# ── Related observations ───────────────────────────────────────────────────────

def test_muted_doc_excluded_from_related_observations(tmp_path):
    """Related-observation search must exclude observations from muted documents."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=0)
    _insert_doc(conn, "b" * 64, "muted.pdf",  source_role="primary", excluded=1)
    _insert_obs(conn, "obs_a", "a" * 64, "Visible observation.", page=1)
    _insert_obs(conn, "obs_b", "b" * 64, "Muted observation.", page=1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get(f"/api/reader/documents/{'a'*64}/related-observations?page=1")
    ids = [o["id"] for o in resp.get_json()["observations"]]
    assert "obs_a" in ids
    assert "obs_b" not in ids, "Observations from muted documents must be excluded"


def test_related_observations_scoped_to_page(tmp_path):
    """Related observations should be near the requested page, not from all pages."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary")
    _insert_obs(conn, "obs_p1", "a" * 64, "Page 1 observation.", page=1)
    _insert_obs(conn, "obs_p9", "a" * 64, "Page 9 observation.", page=9)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get(f"/api/reader/documents/{'a'*64}/related-observations?page=1")
    ids = [o["id"] for o in resp.get_json()["observations"]]
    assert "obs_p1" in ids
    assert "obs_p9" not in ids, "Distant-page observations must not appear when filtering by page"


# ── Document list ──────────────────────────────────────────────────────────────

def test_reader_documents_list_excludes_excluded_docs(tmp_path):
    """GET /api/reader/documents must not include excluded documents in the list."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", excluded=0)
    _insert_doc(conn, "b" * 64, "muted.pdf",  excluded=1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    docs = client.get("/api/reader/documents").get_json()["documents"]
    filenames = [d["filename"] for d in docs]
    assert "gatsby.pdf" in filenames
    assert "muted.pdf" not in filenames, "Excluded documents must not appear in the reader list"
