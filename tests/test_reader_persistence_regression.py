"""
Reader Artifact Persistence Regression Tests (issue #21)

Invariant: reader-created artifacts — highlights, notes, questions,
observation candidates, concept tags — must survive application updates.
App code can change. Investigation data must persist.

These tests simulate the update cycle: seed a workspace through the API,
re-open it the way a freshly deployed app does (create_app runs the
startup migration path), and assert every artifact survives intact.

Covers:
  - highlights with notes, questions, and concept tags round-trip
    through a simulated app restart/migration
  - re-running the migration path is idempotent (no data loss, no dupes)
  - concept tags (tags=["concept:..."]) persist and deserialize
  - observation candidates keep their status across restart
  - dismissed highlights remain recorded (status change, never deletion)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "persistence_test.db"
    store = SQLiteStore(db_path)
    store.close()
    return db_path


def _insert_doc(db: Path, doc_id: str, filename: str = "gatsby.pdf") -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT OR IGNORE INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, filename, doc_id, 10, _now(), "test", "primary", 0),
    )
    conn.commit()
    conn.close()


def _seed_reader_session(client, doc_id: str) -> dict:
    """Create the artifacts a real reading session produces. Returns ids."""
    ids = {}

    r = client.post("/api/reader/highlights", json={
        "source_document_id": doc_id,
        "page": 2,
        "selected_text": "Then wear the gold hat, if that will move her;",
        "note_text": "The novel opens with advice about performing wealth.",
        "question_text": "Is the epigraph telling us Gatsby's whole strategy?",
        "relevance": "supports",
    })
    assert r.status_code == 201
    ids["highlight"] = r.get_json()["id"]

    r = client.post("/api/reader/highlights", json={
        "source_document_id": doc_id,
        "page": 2,
        "selected_text": "aspiration",
        "note_text": "Working definition: longing toward something higher.",
        "tags": ["concept:aspiration"],
    })
    assert r.status_code == 201
    ids["concept"] = r.get_json()["id"]

    r = client.post("/api/reader/highlights", json={
        "source_document_id": doc_id,
        "page": 3,
        "selected_text": "If you can bounce high, bounce for her too,",
        "note_text": "Candidate for observation.",
    })
    assert r.status_code == 201
    ids["candidate"] = r.get_json()["id"]
    r = client.post(f"/api/reader/highlights/{ids['candidate']}/promote")
    assert r.status_code == 200

    r = client.post("/api/reader/highlights", json={
        "source_document_id": doc_id,
        "page": 4,
        "selected_text": "Till she cry Lover, gold-hatted, high-bouncing lover,",
    })
    assert r.status_code == 201
    ids["dismissed"] = r.get_json()["id"]
    r = client.patch(f"/api/reader/highlights/{ids['dismissed']}",
                     json={"status": "dismissed"})
    assert r.status_code == 200

    return ids


def _highlights_by_id(client, doc_id: str) -> dict:
    r = client.get(f"/api/reader/documents/{doc_id}/highlights")
    assert r.status_code == 200
    rows = r.get_json().get("highlights", [])
    return {h["id"]: h for h in rows}


def test_reader_artifacts_survive_app_restart_and_migration(tmp_path):
    """The update cycle: seed → close → re-open via create_app (which runs
    the startup migration path) → every artifact intact."""
    db = _make_db(tmp_path)
    doc_id = "a" * 64
    _insert_doc(db, doc_id)

    first = create_app(db_path=db).test_client()
    ids = _seed_reader_session(first, doc_id)

    # Simulate the app update: a brand-new app instance over the same DB.
    # create_app runs ensure_profile_tables (the migration path) on startup.
    second = create_app(db_path=db).test_client()
    survived = _highlights_by_id(second, doc_id)

    hl = survived[ids["highlight"]]
    assert hl["selected_text"].startswith("Then wear the gold hat")
    assert hl["note_text"] == "The novel opens with advice about performing wealth."
    assert hl["question_text"] == "Is the epigraph telling us Gatsby's whole strategy?"
    assert hl["relevance"] == "supports"
    assert hl["page"] == 2

    concept = survived[ids["concept"]]
    assert concept["tags"] == ["concept:aspiration"], (
        "Concept tags must survive restart and deserialize as a list"
    )

    candidate = survived[ids["candidate"]]
    assert candidate["status"] in ("observation_candidate", "promoted_to_observation")

    # The list API correctly hides dismissed highlights; the record itself
    # must still exist — dismissal is a status, never a deletion.
    assert ids["dismissed"] not in survived
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT status FROM reader_highlights WHERE id = ?",
        (ids["dismissed"],),
    ).fetchone()
    conn.close()
    assert row is not None and row[0] == "dismissed", (
        "Dismissal is a status, never a deletion — the record must remain"
    )


def test_migration_path_is_idempotent_for_reader_data(tmp_path):
    """Running the startup migration repeatedly must neither lose nor
    duplicate reader artifacts."""
    db = _make_db(tmp_path)
    doc_id = "b" * 64
    _insert_doc(db, doc_id)

    client = create_app(db_path=db).test_client()
    _seed_reader_session(client, doc_id)

    conn = sqlite3.connect(db)
    before = conn.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    conn.close()

    for _ in range(3):
        create_app(db_path=db)  # each construction runs the migration path

    conn = sqlite3.connect(db)
    after = conn.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    texts = {r[0] for r in conn.execute(
        "SELECT selected_text FROM reader_highlights").fetchall()}
    conn.close()

    assert after == before, "Migrations must not add or drop reader rows"
    assert any(t.startswith("Then wear the gold hat") for t in texts)


def test_concept_tag_round_trip_through_api(tmp_path):
    """tags=[\"concept:<name>\"] posted by the Reader's Concept action must
    store and return as a parsed list, not a JSON string."""
    db = _make_db(tmp_path)
    doc_id = "c" * 64
    _insert_doc(db, doc_id)

    client = create_app(db_path=db).test_client()
    r = client.post("/api/reader/highlights", json={
        "source_document_id": doc_id,
        "selected_text": "the green light",
        "tags": ["concept:aspiration"],
        "page": 5,
    })
    assert r.status_code == 201

    rows = _highlights_by_id(client, doc_id)
    tags = list(rows.values())[0]["tags"]
    assert isinstance(tags, list) and tags == ["concept:aspiration"]


def test_reader_shell_keeps_return_to_reading_visible():
    """Issue #21 regression guard: Reader must remain the obvious home,
    not a hidden stop inside the pipeline shell."""
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert 'id="reader-home-btn"' in index_html
    assert "Return to Reading" in index_html
    assert "_updateReaderReturnUI(id)" in index_html
    assert "reader-home-btn.active" in index_html


def test_machine_page_brief_is_above_the_page_with_constitutional_copy():
    """Issue #12: machine observations become a pre-reading page brief above
    the reader, with careful copy and stewardship actions — not a buried list."""
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    # The brief exists as an accordion with the required headline and count copy.
    assert 'id="cr-page-brief"' in index_html
    assert "The machine thinks these may matter on this page" in index_html
    assert "· tap to review" in index_html
    assert "_crToggleBrief()" in index_html
    # Constitutional copy, verbatim.
    assert ("Hermeneia noticed these possible points of attention. Read the page "
            "yourself, then approve, edit, question, or reject them.") in index_html
    # Initial stewardship actions.
    assert "_crBriefRule(" in index_html
    assert "'approved'" in index_html and "'rejected'" in index_html and "'unsure'" in index_html
    assert "_crBriefQuestion(" in index_html
    # The brief sits above the page text, not in the side stack.
    assert index_html.index('id="cr-page-brief"') < index_html.index('id="cr-page-view"')
    # The old long list is demoted to a secondary, collapsed disclosure.
    assert "Machine Observations — Full List" in index_html
    assert "_crToggleRelated()" in index_html


def test_reader_capture_ui_is_passage_attached_and_records_attention_metadata():
    """The live loop must support passage selection -> important/tag/note/
    question/candidate capture without depending on a detached side panel."""
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "cr-selection-preview" in index_html
    assert "cr-important-input" in index_html
    assert "cr-tags-input" in index_html
    assert "Capture this passage" in index_html
    assert "_crCaptureBlock" in index_html
    assert "_crParseTypedTags" in index_html
    assert "_crSaveHighlight(true)" in index_html
    assert "Capture is attached to the selected passage" in index_html


def test_reader_saved_highlights_render_inline_after_reload():
    """Saved Reader artifacts must be visible back in the book after the
    highlight list reloads; the persisted view cannot rely only on native
    selection or CSS Custom Highlight state."""
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "cr-inline-highlight" in index_html
    assert "_crRenderTextWithHighlights" in index_html
    assert "_crHighlightTags" in index_html
    assert "_crRenderPage();" in index_html
    assert "CSS.highlights.set('hermeneia-pending'" in index_html
    assert "user-select: none" in index_html
