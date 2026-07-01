"""
Reading Trail Summary Tests

Invariant: The summary is a deterministic map of human attention.
It does not score, grade, or call any AI provider.

Covers:
  1.  Reading progress summary is separate from machine coverage.
  2.  Highlight count does not create observations.
  3.  Observation candidate count only counts explicitly promoted highlights.
  4.  Dismissed highlights are excluded from active trail summary.
  5.  Source role is preserved in summary.
  6.  Non-primary highlights are labelled as non-primary in summary.
  7.  Question counts come from reader_highlights.question_text, not AI interpretations.
  8.  Summary is deterministic — produces same result when called twice.
  9.  Muted/excluded documents do not appear in investigation summary.
  10. Empty reading trail returns a useful empty state.
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
    db = tmp_path / "trail_test.db"
    SQLiteStore(db).close()
    return db


def _insert_doc(conn, doc_id, filename, source_role="primary", excluded=0, total_pages=20):
    conn.execute(
        """INSERT OR IGNORE INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, filename, doc_id, total_pages, _now(), "test", source_role, excluded),
    )


def _insert_obs(conn, obs_id, doc_id, text="obs text", page=1):
    ext_id = obs_id + "_ext"
    locator = f"p.{page}.s.1.§.1"
    conn.execute(
        """INSERT OR IGNORE INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ext_id, doc_id, page, "body", text, "t", "1", "{}", locator,
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


def _save_highlight(client, doc_id, text, **kwargs):
    payload = {"source_document_id": doc_id, "selected_text": text, **kwargs}
    resp = client.post("/api/reader/highlights", json=payload)
    assert resp.status_code == 201
    return resp.get_json()["id"]


# ── 1. Reading progress is separate from machine coverage ─────────────────────

def test_reading_progress_separate_from_machine_coverage(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", total_pages=10)
    for i in range(8):
        _insert_obs(conn, f"obs_{i}", "a" * 64, page=i + 1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get(f"/api/reader/documents/{'a'*64}/summary")
    assert resp.status_code == 200
    s = resp.get_json()

    assert s["reading_progress"]["pages_read"] == 0, "No pages read yet"
    assert s["machine_coverage"]["observation_count"] == 8
    assert s["machine_coverage"]["note"], "Machine coverage note must be present"


# ── 2. Highlight count does not create observations ───────────────────────────

def test_highlight_count_does_not_create_observations(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    for i in range(3):
        _save_highlight(client, "a" * 64, f"Passage {i}")

    s = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    assert s["highlight_trail"]["total_active"] == 3

    conn2 = sqlite3.connect(db)
    obs = conn2.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn2.close()
    assert obs == 0, "Saving highlights must never create observations"


# ── 3. Observation candidate count only counts explicit promotions ─────────────

def test_observation_candidate_count_only_explicit(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    hl1 = _save_highlight(client, "a" * 64, "Passage A")
    hl2 = _save_highlight(client, "a" * 64, "Passage B")
    _save_highlight(client, "a" * 64, "Passage C — not promoted")

    client.post(f"/api/reader/highlights/{hl1}/promote")
    client.post(f"/api/reader/highlights/{hl2}/promote")

    s = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    assert s["observation_candidates"]["count"] == 2
    assert s["highlight_trail"]["total_active"] == 3, "All highlights still active"


# ── 4. Dismissed highlights excluded from active summary ──────────────────────

def test_dismissed_highlights_excluded_from_summary(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    hl_keep = _save_highlight(client, "a" * 64, "Keeper")
    hl_gone = _save_highlight(client, "a" * 64, "Dismissed")

    client.delete(f"/api/reader/highlights/{hl_gone}")

    s = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    assert s["highlight_trail"]["total_active"] == 1
    assert s["highlight_trail"]["dismissed_count"] == 1


# ── 5. Source role is preserved in summary ────────────────────────────────────

def test_source_role_preserved_in_candidate_items(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary")
    _insert_doc(conn, "b" * 64, "essay.pdf",  source_role="commentary")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    hl_a = _save_highlight(client, "a" * 64, "Primary passage")
    hl_b = _save_highlight(client, "b" * 64, "Commentary passage")
    client.post(f"/api/reader/highlights/{hl_a}/promote")
    client.post(f"/api/reader/highlights/{hl_b}/promote")

    sa = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    sb = client.get(f"/api/reader/documents/{'b'*64}/summary").get_json()

    roles_a = {c["source_role"] for c in sa["observation_candidates"]["items"]}
    roles_b = {c["source_role"] for c in sb["observation_candidates"]["items"]}
    assert roles_a == {"primary"}
    assert roles_b == {"commentary"}


# ── 6. Non-primary highlights surfaced in summary ─────────────────────────────

def test_non_primary_highlights_counted_separately(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf",  source_role="primary")
    _insert_doc(conn, "b" * 64, "notes.pdf",   source_role="notes")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    _save_highlight(client, "a" * 64, "Primary highlight")
    _save_highlight(client, "b" * 64, "Notes highlight 1")
    _save_highlight(client, "b" * 64, "Notes highlight 2")

    sa = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    sb = client.get(f"/api/reader/documents/{'b'*64}/summary").get_json()

    assert sa["highlight_trail"]["non_primary_count"] == 0
    assert sb["highlight_trail"]["non_primary_count"] == 2


# ── 7. Question counts come from reader_highlights, not interpretations ────────

def test_question_counts_from_reader_highlights_not_ai(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    _save_highlight(client, "a" * 64, "Passage with question",
                    question_text="What does the green light mean here?")
    _save_highlight(client, "a" * 64, "Passage with question 2",
                    question_text="Is this irony or sincerity?")
    _save_highlight(client, "a" * 64, "Passage without question")

    s = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    assert s["question_trail"]["total_questions"] == 2

    conn2 = sqlite3.connect(db)
    interp_count = conn2.execute(
        "SELECT COUNT(*) FROM proposed_interpretations"
    ).fetchone()[0]
    conn2.close()
    assert interp_count == 0, "Questions must not trigger AI interpretation"


# ── 8. Summary is deterministic ───────────────────────────────────────────────

def test_summary_is_deterministic(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    _save_highlight(client, "a" * 64, "Some passage", question_text="A question")

    s1 = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    s2 = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()

    assert s1["highlight_trail"]["total_active"] == s2["highlight_trail"]["total_active"]
    assert s1["question_trail"]["total_questions"] == s2["question_trail"]["total_questions"]
    assert s1["reading_progress"]["percent_read"] == s2["reading_progress"]["percent_read"]


# ── 9. Excluded documents excluded from investigation summary ─────────────────

def test_excluded_docs_not_in_investigation_summary(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf",  excluded=0)
    _insert_doc(conn, "b" * 64, "muted.pdf",   excluded=1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    s = client.get("/api/reader/summary").get_json()
    doc_ids = [d["id"] for d in s["documents"]]
    assert "a" * 64 in doc_ids
    assert "b" * 64 not in doc_ids, "Excluded document must not appear in investigation summary"


# ── 10. Empty reading trail returns useful empty state ────────────────────────

def test_empty_reading_trail_returns_empty_state(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    s = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    assert s["empty"] is True
    assert s["highlight_trail"]["total_active"] == 0
    assert s["reading_progress"]["pages_read"] == 0
    assert s["question_trail"]["total_questions"] == 0
    assert s["observation_candidates"]["count"] == 0


# ── Bonus: relevance breakdown in summary ─────────────────────────────────────

def test_relevance_breakdown_in_summary(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    _save_highlight(client, "a" * 64, "P1", relevance="supports")
    _save_highlight(client, "a" * 64, "P2", relevance="supports")
    _save_highlight(client, "a" * 64, "P3", relevance="contradicts")
    _save_highlight(client, "a" * 64, "P4", relevance="unclear")

    s = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    rel = s["highlight_trail"]["by_relevance"]
    assert rel.get("supports") == 2
    assert rel.get("contradicts") == 1
    assert rel.get("unclear") == 1


# ── Bonus: attention clusters are page-windowed ────────────────────────────────

def test_attention_clusters_by_page_window(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", total_pages=60)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    # 3 highlights in page 5 window, 2 in page 45 window
    for _ in range(3):
        _save_highlight(client, "a" * 64, "Early passage", page=5)
    for _ in range(2):
        _save_highlight(client, "a" * 64, "Late passage", page=45)

    s = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    clusters = s["attention_clusters"]
    assert len(clusters) == 2

    by_start = {c["start"]: c for c in clusters}
    assert by_start[1]["highlights"] == 3
    assert by_start[41]["highlights"] == 2


# ── Bonus: continue reading points to next unread page ────────────────────────

def test_next_unread_page_in_progress(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", total_pages=10)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    client.post("/api/reader/progress", json={"document_id": "a" * 64, "page": 1})
    client.post("/api/reader/progress", json={"document_id": "a" * 64, "page": 2})

    s = client.get(f"/api/reader/documents/{'a'*64}/summary").get_json()
    assert s["reading_progress"]["next_unread_page"] == 3


def test_summary_get_does_not_create_observations_or_mutate_reader_data(tmp_path):
    """A summary GET is a read-only projection over the existing trail."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", total_pages=10)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    _save_highlight(client, "a" * 64, "Human-selected passage")
    client.post(
        "/api/reader/progress",
        json={"document_id": "a" * 64, "page": 1},
    )

    conn_before = sqlite3.connect(db)
    before = {
        table: conn_before.execute(
            f"SELECT COUNT(*) FROM {table}"  # table names are fixed test data
        ).fetchone()[0]
        for table in ("observations", "reader_highlights", "reading_progress")
    }
    conn_before.close()

    assert client.get(f"/api/reader/documents/{'a'*64}/summary").status_code == 200
    assert client.get("/api/reader/summary").status_code == 200

    conn_after = sqlite3.connect(db)
    after = {
        table: conn_after.execute(
            f"SELECT COUNT(*) FROM {table}"  # table names are fixed test data
        ).fetchone()[0]
        for table in ("observations", "reader_highlights", "reading_progress")
    }
    conn_after.close()
    assert after == before
    assert after["observations"] == 0


def test_summary_never_accesses_provider_registry(tmp_path):
    """Reader summaries must not consult AI/provider infrastructure."""
    class ProviderTrap:
        def __getattr__(self, name):
            raise AssertionError(f"summary attempted provider access: {name}")

    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    client = create_app(
        db_path=db,
        provider_registry=ProviderTrap(),
    ).test_client()
    assert client.get(f"/api/reader/documents/{'a'*64}/summary").status_code == 200
    assert client.get("/api/reader/summary").status_code == 200


def test_investigation_summary_excludes_muted_document_trail_counts(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary")
    _insert_doc(
        conn,
        "b" * 64,
        "muted-notes.pdf",
        source_role="notes",
        excluded=0,
    )
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    _save_highlight(client, "a" * 64, "Primary passage")
    _save_highlight(
        client,
        "b" * 64,
        "Muted question",
        question_text="This must not enter the active summary.",
    )
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_documents SET excluded_from_analysis = 1 WHERE id = ?",
        ("b" * 64,),
    )
    conn.commit(); conn.close()

    summary = client.get("/api/reader/summary").get_json()
    assert summary["highlight_trail"]["total_active"] == 1
    assert summary["question_trail"]["total_questions"] == 0
    assert summary["highlight_trail"]["by_source_role"] == {"primary": 1}


def test_recent_items_label_non_primary_source_role(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "b" * 64, "commentary.pdf", source_role="commentary")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    _save_highlight(
        client,
        "b" * 64,
        "Commentary passage",
        question_text="How does this compare with the primary text?",
    )

    summary = client.get(f"/api/reader/documents/{'b'*64}/summary").get_json()
    recent = summary["recent_highlights"][0]
    question = summary["question_trail"]["recent_questions"][0]
    assert recent["source_role"] == "commentary"
    assert recent["is_primary_source"] is False
    assert question["source_role"] == "commentary"
    assert question["is_primary_source"] is False


def test_summary_contains_no_reader_score_or_grade(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_doc(conn, "a" * 64, "gatsby.pdf")
    conn.commit(); conn.close()

    summary = create_app(db_path=db).test_client().get(
        f"/api/reader/documents/{'a'*64}/summary"
    ).get_json()
    serialized = json.dumps(summary).lower()
    for forbidden in ("reader_score", "grade", "streak", "leaderboard"):
        assert forbidden not in serialized


def test_reader_ui_presents_attention_map_without_gamification():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "/api/reader/documents/${encodeURIComponent(_crDocId)}/summary" in index_html
    assert "A map of attention, not a report card." in index_html
    assert "Attention Clusters" in index_html
    assert "Highlights by Source Role" in index_html
    assert "Recent Questions" in index_html
    assert "Reader Score" not in index_html
    assert "leaderboard" not in index_html.lower()
