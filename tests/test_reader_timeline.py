"""Attention timeline (PR 3).

"What have I discovered so far?" — a reverse-chronological feed of the steward's
captured attention (highlights, notes, questions, field notes) across the
corpus. These tests cover the /api/reader/timeline aggregation (kinds, ordering,
exclusion of dismissed highlights and muted documents) and the panel UI wiring.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
SPAN_PREFIX = "reader-span:v1:"


def _span_locator() -> str:
    payload = {
        "page": 2,
        "start": {
            "block_index": 1,
            "source_locator": "page:2:block:1",
            "source_locators": ["page:2:block:1"],
            "extraction_ids": ["ext-1"],
            "offset": 3,
        },
        "end": {
            "block_index": 3,
            "source_locator": "page:2:block:3",
            "source_locators": ["page:2:block:3"],
            "extraction_ids": ["ext-3"],
            "offset": 9,
        },
        "source_locators": [
            "page:2:block:1",
            "page:2:block:2",
            "page:2:block:3",
        ],
        "extraction_ids": ["ext-1", "ext-2", "ext-3"],
    }
    return SPAN_PREFIX + quote(json.dumps(payload, separators=(",", ":")), safe="")


def _seed(tmp_path: Path) -> Path:
    db_path = tmp_path / "workspace.db"
    SQLiteStore(db_path).close()
    doc_id = "a" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 3, "2026-07-01T00:00:00+00:00",
         "test", "primary", 0),
    )

    def _hl(hid, created, **kw):
        cols = dict(
            id=hid, source_document_id=doc_id, source_role="primary", page=2,
            source_locator="page:2:block:4", selected_text="the green light",
            note_text=None, question_text=None, relevance="unclear", tags="[]",
            status="saved_highlight", rank=None, theme_bucket=None,
            created_at=created, updated_at=created,
        )
        cols.update(kw)
        keys = ",".join(cols)
        conn.execute(
            f"INSERT INTO reader_highlights ({keys}) VALUES ({','.join('?' for _ in cols)})",
            list(cols.values()),
        )

    _hl("hl-plain", "2026-07-01T10:00:00+00:00", rank=5)
    _hl("hl-note", "2026-07-02T10:00:00+00:00", note_text="Aspiration made visible.")
    _hl("hl-q", "2026-07-03T10:00:00+00:00", question_text="Does hope require distance?")
    _hl("hl-dismissed", "2026-07-04T10:00:00+00:00", status="dismissed")
    conn.execute(
        """INSERT INTO investigation_log
           (id, lane, understanding, pressing_questions, source_document_id,
            page, governing_question, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("fn-1", "corpus", "Distance sustains desire.", None, doc_id, 2,
         "How does desire depend on distance?", "2026-07-02T12:00:00+00:00"),
    )
    conn.commit()
    conn.close()
    return db_path


def _timeline(db_path: Path):
    return create_app(db_path=db_path).test_client().get("/api/reader/timeline").get_json()


# ── Aggregation ────────────────────────────────────────────────────────────


def test_timeline_merges_kinds_in_reverse_chronological_order(tmp_path: Path):
    body = _timeline(_seed(tmp_path))
    ids = [e["id"] for e in body["entries"]]
    # dismissed highlight excluded; newest first.
    assert "hl-dismissed" not in ids
    assert ids == ["hl-q", "fn-1", "hl-note", "hl-plain"]


def test_timeline_classifies_kinds(tmp_path: Path):
    entries = {e["id"]: e for e in _timeline(_seed(tmp_path))["entries"]}
    assert entries["hl-plain"]["kind"] == "highlight"
    assert entries["hl-note"]["kind"] == "note"
    assert entries["hl-q"]["kind"] == "question"
    assert entries["fn-1"]["kind"] == "field_note"
    assert entries["hl-plain"]["rank"] == 5


def test_timeline_carries_navigation_target(tmp_path: Path):
    entries = {e["id"]: e for e in _timeline(_seed(tmp_path))["entries"]}
    hl = entries["hl-q"]
    assert hl["document_id"] == "a" * 64
    assert hl["document_name"] == "gatsby.pdf"
    assert hl["page"] == 2


def test_timeline_projects_reader_span_locator_without_rewriting_row(tmp_path: Path):
    db_path = _seed(tmp_path)
    locator = _span_locator()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE reader_highlights SET source_locator = ? WHERE id = ?",
        (locator, "hl-q"),
    )
    conn.commit()
    conn.close()

    entries = {e["id"]: e for e in _timeline(db_path)["entries"]}
    hl = entries["hl-q"]
    assert hl["source_locator"] == "page:2:block:1..page:2:block:3"
    assert hl["reader_span_locator"] == locator

    verify = sqlite3.connect(db_path)
    assert verify.execute(
        "SELECT source_locator FROM reader_highlights WHERE id = 'hl-q'"
    ).fetchone()[0] == locator
    verify.close()


def test_timeline_excludes_muted_documents(tmp_path: Path):
    db_path = _seed(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE source_documents SET excluded_from_analysis = 1")
    conn.commit()
    conn.close()
    body = _timeline(db_path)
    # Highlights on the muted doc are gone; the field note (doc-linked) too.
    assert all(e["kind"] == "field_note" and e["document_id"] is None
               for e in body["entries"]) or body["count"] == 0


def test_timeline_empty_workspace(tmp_path: Path):
    db_path = tmp_path / "empty.db"
    SQLiteStore(db_path).close()
    body = _timeline(db_path)
    assert body["count"] == 0
    assert body["entries"] == []


# ── UI wiring ──────────────────────────────────────────────────────────────


def test_timeline_panel_and_trigger_present():
    index = INDEX.read_text()
    assert 'id="cr-bottom-workstation"' in index
    assert 'id="attn-timeline"' in index
    assert "openTimeline()" in index
    assert "closeTimeline()" in index
    assert "cr-rail-timeline" in index
    assert "/api/reader/timeline" in index
    assert "_attnSetFilter" in index
    assert "Timeline" in index
    # Clicking a card navigates the book, not a page away.
    assert "_attnOpen" in index
    assert "_crGoToPage" in index
