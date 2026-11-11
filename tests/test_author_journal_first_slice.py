"""Workspace Author Journal first slice: real empty-workspace persistence, no manuscript authority.

No new database tables or canonical content model are introduced. Entries use
the existing immutable corpus Investigation Log and survive a server restart.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hermeneia.web.app import create_app
from hermeneia.workspace import create_workspace


def test_author_reflections_work_before_any_document_exists(tmp_path: Path):
    record = create_workspace(
        "An Unwritten Book",
        workspace_root=tmp_path / "workspaces",
        legacy_db=tmp_path / "missing.db",
    )
    db = record.db_path
    first = create_app(db_path=db).test_client()

    # The Author Journal is available without a document or an attached
    # Publication Compositor work; it is not a disguised source import.
    publication = first.get("/api/authoring/work")
    assert publication.status_code == 200
    assert publication.get_json()["attached"] is False

    saved = first.post("/api/investigation-log", json={
        "lane": "corpus",
        "understanding": "I want the opening to begin with an unanswered question.",
        "pressing_questions": "What would change my mind about the thesis?",
    })
    assert saved.status_code == 201
    entry_id = saved.get_json()["id"]

    second = create_app(db_path=db).test_client()
    entries = second.get("/api/investigation-log?lane=corpus").get_json()["entries"]
    assert len(entries) == 1
    assert entries[0]["id"] == entry_id
    assert entries[0]["source_document_id"] is None
    assert entries[0]["page"] is None
    assert entries[0]["understanding"].startswith("I want the opening")
    assert "change my mind" in entries[0]["pressing_questions"]

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM publication_works").fetchone()[0] == 0
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute(
                "UPDATE investigation_log SET understanding = 'changed' WHERE id = ?",
                (entry_id,),
            )
    finally:
        conn.close()


def test_author_journal_ui_uses_existing_field_notes_and_is_packaged():
    root = Path(__file__).resolve().parents[1]
    html = (root / "hermeneia/web/static/index.html").read_text()
    script = (root / "hermeneia/web/static/author_journal.js").read_text()
    project = (root / "pyproject.toml").read_text()

    assert 'onclick="authorJournalOpen()"' in html
    assert 'id="author-journal-overlay"' in html
    assert 'src="/static/author_journal.js"' in html
    assert 'static/*.js' in project
    assert "/api/investigation-log?lane=corpus" in script
    assert "lane: 'corpus'" in script
    assert "authorJournalSave" in script
    assert "/api/authoring/work/attach" not in script
    assert "publication_works" not in script
