"""
Tests for Blueprint Extractor — "Start From Existing Work" onboarding path.

Proves:
- Valid JSON response from LLM is parsed into a normalized Blueprint dict
- Sections get empty obs/interp lists by default
- Malformed JSON raises BlueprintExtractionError
- Missing required fields raise BlueprintExtractionError
- Markdown code fences are stripped before parsing
- NullProvider returns a stub (not an error)
- POST /api/pipeline/extract-blueprint returns a proposed Blueprint without saving
- POST /api/pipeline/extract-blueprint with save=true stores Blueprint and Plan
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hermeneia.compiler.blueprint_extractor import (
    BlueprintExtractionError,
    _parse_and_validate,
    extract_blueprint_from_text,
)
from hermeneia.web.app import create_app


# ── _parse_and_validate ───────────────────────────────────────────────────────

def test_parse_valid_json():
    raw = json.dumps({
        "title": "Test Title",
        "thesis": "A central claim about something.",
        "sections": [
            {"claim": "First supporting claim."},
            {"claim": "Second supporting claim."},
        ],
    })
    result = _parse_and_validate(raw)
    assert result["title"] == "Test Title"
    assert result["thesis"] == "A central claim about something."
    assert len(result["sections"]) == 2


def test_parse_normalizes_sections():
    raw = json.dumps({
        "title": "T",
        "thesis": "Thesis.",
        "sections": [{"claim": "Claim one."}],
    })
    result = _parse_and_validate(raw)
    section = result["sections"][0]
    assert section["supporting_observations"] == []
    assert section["supporting_interpretations"] == []


def test_parse_strips_markdown_fences():
    raw = "```json\n" + json.dumps({
        "title": "T", "thesis": "Th.", "sections": [{"claim": "C."}]
    }) + "\n```"
    result = _parse_and_validate(raw)
    assert result["title"] == "T"


def test_parse_strips_bare_fences():
    raw = "```\n" + json.dumps({
        "title": "T", "thesis": "Th.", "sections": [{"claim": "C."}]
    }) + "\n```"
    result = _parse_and_validate(raw)
    assert result["title"] == "T"


def test_parse_raises_on_bad_json():
    with pytest.raises(BlueprintExtractionError, match="valid JSON"):
        _parse_and_validate("not json at all")


def test_parse_raises_on_missing_title():
    raw = json.dumps({"thesis": "Th.", "sections": [{"claim": "C."}]})
    with pytest.raises(BlueprintExtractionError, match="title"):
        _parse_and_validate(raw)


def test_parse_raises_on_empty_sections():
    raw = json.dumps({"title": "T", "thesis": "Th.", "sections": []})
    with pytest.raises(BlueprintExtractionError, match="section"):
        _parse_and_validate(raw)


def test_parse_raises_on_section_missing_claim():
    raw = json.dumps({"title": "T", "thesis": "Th.", "sections": [{"topic": "no claim"}]})
    with pytest.raises(BlueprintExtractionError, match="claim"):
        _parse_and_validate(raw)


# ── extract_blueprint_from_text ───────────────────────────────────────────────

class _FakeProvider:
    """Returns a minimal valid Blueprint JSON."""
    def __call__(self, prompt: str) -> str:
        return json.dumps({
            "title": "Fake Blueprint",
            "thesis": "The text establishes a claim.",
            "sections": [{"claim": "Supporting claim one."}],
        })


def test_extract_empty_text_raises():
    with pytest.raises(BlueprintExtractionError, match="No text"):
        extract_blueprint_from_text("", _FakeProvider())


def test_extract_whitespace_only_raises():
    with pytest.raises(BlueprintExtractionError, match="No text"):
        extract_blueprint_from_text("   \n  ", _FakeProvider())


def test_extract_null_provider_returns_stub():
    from hermeneia.narrative.artist_providers import get_provider
    null_prov = get_provider("null")
    result = extract_blueprint_from_text("Some document text about things.", null_prov)
    assert "title" in result
    assert "thesis" in result
    assert isinstance(result["sections"], list)
    assert len(result["sections"]) >= 1


# ── API endpoint ──────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    app = create_app(db_path=db_path)
    return app.test_client()


def test_extract_api_missing_text(client):
    resp = client.post("/api/pipeline/extract-blueprint",
                       json={}, content_type="application/json")
    assert resp.status_code == 400
    assert "text" in resp.get_json()["error"]


def test_extract_api_returns_proposed_blueprint(client):
    resp = client.post("/api/pipeline/extract-blueprint", json={
        "text": "A detailed analysis of the topic at hand.",
        "provider": "null",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "proposed_blueprint" in data
    bp = data["proposed_blueprint"]
    assert "title" in bp
    assert "thesis" in bp
    assert isinstance(bp["sections"], list)


def test_extract_api_no_save_does_not_write(client, tmp_path):
    # client fixture uses a non-existent DB path; save=False skips the DB entirely
    resp = client.post("/api/pipeline/extract-blueprint", json={
        "text": "Analysis text here.",
        "provider": "null",
        "save": False,
    })
    assert resp.status_code == 200
    # Confirm no blueprint was written (DB was never created)
    db_path = tmp_path / "test.db"
    assert not db_path.exists()


@pytest.fixture
def seeded_db(tmp_path):
    """Create an initialized DB and return (db_path, app, client)."""
    from hermeneia.storage.sqlite import SQLiteStore
    db_path = tmp_path / "extract.db"
    store = SQLiteStore(db_path)
    store.close()
    app = create_app(db_path=db_path)
    return db_path, app.test_client()


def test_extract_api_save_true_stores_blueprint(seeded_db):
    db_path, c = seeded_db

    resp = c.post("/api/pipeline/extract-blueprint", json={
        "text": "An existing report with claims and evidence.",
        "provider": "null",
        "save": True,
    })

    assert resp.status_code == 201
    data = resp.get_json()
    assert "blueprint_id" in data
    assert "plan_id" in data
    assert "proposed_blueprint" in data

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM narrative_blueprints").fetchone()[0]
    conn.close()
    assert count == 1


def test_extract_api_save_idempotent(seeded_db):
    db_path, c = seeded_db

    payload = {
        "text": "An existing report with claims and evidence.",
        "provider": "null",
        "save": True,
    }
    r1 = c.post("/api/pipeline/extract-blueprint", json=payload)
    r2 = c.post("/api/pipeline/extract-blueprint", json=payload)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.get_json()["blueprint_id"] == r2.get_json()["blueprint_id"]

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM narrative_blueprints").fetchone()[0]
    conn.close()
    assert count == 1
