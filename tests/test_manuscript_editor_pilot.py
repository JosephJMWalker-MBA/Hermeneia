"""First real-use WYSIWYG pilot: sandboxed editor + versioned working draft.

The working document deliberately does NOT create a Compositor edition,
SourceDocument, Observation, or authoring approval. Tests use an isolated
temporary workspace and never touch a user's Gatsby or real manuscripts.
"""
from __future__ import annotations

import sqlite3
import shutil
import subprocess
from pathlib import Path

import pytest

from hermeneia.web.app import create_app
from hermeneia.workspace import create_workspace

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "hermeneia/web/static"


@pytest.fixture
def client(tmp_path):
    record = create_workspace(
        "An Actual Book",
        workspace_root=tmp_path / "workspaces",
        legacy_db=tmp_path / "no-gatsby.db",
    )
    yield create_app(db_path=record.db_path).test_client(), record.db_path


def test_editor_route_is_separate_from_reader_and_statically_packaged(client):
    browser, _ = client
    response = browser.get("/editor")
    assert response.status_code == 200
    assert b'id="writer-frame"' in response.data
    assert b'id="writer-title"' in response.data
    assert b'contenteditable="true"' not in response.data  # sandboxed in frame
    assert b'id="writer-css"' in response.data
    assert b'id="writer-import"' in response.data
    assert b'id="writer-history"' in response.data

    index = (STATIC / "index.html").read_text()
    assert 'href="/editor"' in index
    assert 'name="herm-start-mode" value="write"' in index
    assert 'name="herm-start-mode" value="journal"' in index

    startup = (STATIC / "start_screen.js").read_text()
    assert "window.location.assign('/editor')" in startup
    css = (STATIC / "manuscript_editor.css").read_text()
    assert ".writer-sheet-wrap" in css
    canvas_css = (STATIC / "manuscript_canvas.css").read_text()
    assert "#writer-document" in canvas_css
    writer = (STATIC / "manuscript_editor.js").read_text()
    assert "contenteditable" in writer
    assert "allow-same-origin" in (STATIC / "manuscript_editor.html").read_text()
    assert 'style-src &apos;self&apos;' in writer
    assert "window.addEventListener('beforeunload'" in writer
    assert "expected_revision:state.revision" in writer
    assert "style_css" in writer
    package = (ROOT / "pyproject.toml").read_text()
    assert '"static/*.html", "static/*.js", "static/*.css"' in package


def test_typing_saves_versions_and_css_without_ever_admitting_source(client):
    browser, db = client
    initial = browser.get("/api/manuscript-draft")
    assert initial.status_code == 200
    assert initial.json["revision"] is None
    assert initial.json["publication_edition"] is False

    first = browser.post("/api/manuscript-draft", json={
        "title": "Toward an Ecology of Intelligence",
        "html": "<h1>Purpose</h1><p>Our first passage.</p>",
        "style_css": "h1 { color: teal; }",
        "expected_revision": None,
    })
    assert first.status_code == 201
    assert first.json["number"] == 1
    assert first.json["publication_edition"] is False
    rev1 = first.json["revision"]

    second = browser.post("/api/manuscript-draft", json={
        "title": "Toward an Ecology of Intelligence",
        "html": "<h1>Purpose</h1><p>Our first <strong>revised</strong> passage.</p>",
        "style_css": "h1 { color: teal; }",
        "expected_revision": rev1,
    })
    assert second.status_code == 201
    assert second.json["number"] == 2
    assert second.json["previous"] == rev1
    rev2 = second.json["revision"]
    assert rev1 != rev2

    # Restart the Flask app; the head must be durable, not an in-memory draft.
    reopened = create_app(db_path=db).test_client()
    fresh = reopened.get("/api/manuscript-draft")
    assert fresh.status_code == 200
    assert fresh.json["revision"] == rev2
    assert "<strong>revised</strong>" in fresh.json["html"]
    assert "color: teal" in fresh.json["style_css"]

    history = reopened.get("/api/manuscript-draft/history")
    assert [r["revision"] for r in history.json["revisions"]] == [rev2, rev1]
    old = reopened.get("/api/manuscript-draft/history/" + rev1)
    assert old.json["html"] == "<h1>Purpose</h1><p>Our first passage.</p>"

    conflict = reopened.post("/api/manuscript-draft", json={
        "title": "Conflicting edit", "html": "<p>Lost update</p>",
        "style_css": "", "expected_revision": rev1
    })
    assert conflict.status_code == 409
    assert conflict.json["code"] == "STALE_MANUSCRIPT_DRAFT"
    assert reopened.get("/api/manuscript-draft").json["revision"] == rev2

    same = reopened.post("/api/manuscript-draft", json={
        "title": "Toward an Ecology of Intelligence",
        "html": "<h1>Purpose</h1><p>Our first <strong>revised</strong> passage.</p>",
        "style_css": "h1 { color: teal; }",
        "expected_revision": rev2,
    })
    assert same.status_code == 200
    assert same.json["revision"] == rev2

    exported = reopened.get("/api/manuscript-draft/export")
    assert exported.status_code == 200
    assert exported.content_type.startswith("text/html")
    assert b"<h1>Purpose</h1>" in exported.data
    assert b"color: teal" in exported.data
    assert b"attachment;" in exported.headers["Content-Disposition"]

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM publication_works").fetchone()[0] == 0

    files = list((db.parent / "manuscript-draft" / "revisions").glob("r*.json"))
    assert len(files) == 2


def test_import_converts_markdown_and_rejects_malicious_markup(client):
    browser, _ = client
    converted = browser.post("/api/manuscript-draft/convert", json={
        "format": "markdown",
        "content": "# Introduction\n\nThe *author* writes **freely**.",
    })
    assert converted.status_code == 200
    assert "<h1>Introduction</h1>" in converted.json["html"]
    assert "<strong>freely</strong>" in converted.json["html"]

    plain = browser.post("/api/manuscript-draft/convert", json={
        "format": "text", "content": "First paragraph.\n\nSecond paragraph.",
    })
    assert plain.status_code == 200
    assert "<p>First paragraph.</p><p>Second paragraph.</p>" == plain.json["html"]

    saved = browser.post("/api/manuscript-draft", json={
        "title": "Test",
        "expected_revision": None,
        "html": '<p onclick="evil()">Safe</p><img src=x onerror=evil()><script>alert(1)</script><p><a href="javascript:evil()">link</a></p>',
        "style_css": "p { font-family: Georgia; }"
    })
    assert saved.status_code == 201
    html = saved.json["html"]
    assert "Safe" in html and "<p>" in html
    assert "<script" not in html
    assert "<img" not in html
    assert "onclick" not in html
    assert "javascript:" not in html
    assert "alert(1)" not in html


def test_invalid_draft_does_not_advance_history(client):
    browser, _ = client
    no_title = browser.post("/api/manuscript-draft", json={
        "title": "", "html": "<p>Draft</p>", "expected_revision": None
    })
    assert no_title.status_code == 400

    no_css = browser.post("/api/manuscript-draft", json={
        "title": "Test", "html": "<p>Draft</p>",
        "style_css": "x" * (64 * 1024 + 1),
        "expected_revision": None,
    })
    assert no_css.status_code == 413
    assert browser.get("/api/manuscript-draft/history").json["revisions"] == []


@pytest.mark.skipif(shutil.which("node") is None, reason="Node not installed")
def test_editor_javascript_parses():
    for name in ("manuscript_editor.js", "start_screen.js"):
        r = subprocess.run(["node", "--check", str(STATIC / name)],
                           text=True, capture_output=True, check=False)
        assert r.returncode == 0, r.stderr
