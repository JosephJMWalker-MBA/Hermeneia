"""Voice/Witness Critic — judge an Artist draft against a profile's witness.

Deterministic: preserve/avoid phrase checks parsed from the steward-authored
ExpressionProfile directive, plus the built-in expression checks, plus surfaced
critic_expectations. No LLM, no persistence. This audit runs on a previewed
(unsaved) draft — discernment before persistence.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from hermeneia.compiler.critic.profile_fidelity import (
    check_witness_fidelity,
    parse_witness_constraints,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


DIRECTIVE = (
    "Voice: first-person, testimonial\n"
    "Audience: a reader who was not in the room\n\n"
    "Non-negotiables:\n- Keep it in the witness's own frame.\n\n"
    "Preserve these phrases and moves — do not paraphrase them away:\n"
    "- I only know what I saw\n- the hesitation before naming it\n\n"
    "Avoid — never do this:\n- consultant language\n- leverage stakeholders"
)


def test_parse_witness_constraints():
    c = parse_witness_constraints(DIRECTIVE)
    assert c["preserve"] == ["I only know what I saw", "the hesitation before naming it"]
    assert c["avoid"] == ["consultant language", "leverage stakeholders"]
    # A built-in prose directive has no labeled sections.
    assert parse_witness_constraints("Write in a warm, literary voice.") == {"preserve": [], "avoid": []}


def _profile(**over):
    base = {"slug": "witness", "name": "Witness", "artist_prompt": DIRECTIVE,
            "critic_expectations": "Flag press-release sentences."}
    base.update(over)
    return base


def test_faithful_draft_is_strong():
    draft = ("I only know what I saw. There was the hesitation before naming it, "
             "and I have tried to keep it in that frame.")
    r = check_witness_fidelity(draft, _profile())
    assert r["verdict"] == "strong"
    assert r["missing_preserve"] == []
    assert r["violations"] == []
    assert all(p["present"] for p in r["preserve"])
    assert r["expectations"] == "Flag press-release sentences."


def test_dropped_witness_and_violation_downgrades():
    # Omits both preserve phrases AND uses forbidden consultant language.
    draft = "We should leverage stakeholders and align on key takeaways going forward."
    r = check_witness_fidelity(draft, _profile())
    assert set(r["missing_preserve"]) == {"I only know what I saw", "the hesitation before naming it"}
    assert "leverage stakeholders" in r["violations"]
    assert r["verdict"] == "weak"  # both missing and violating


def test_only_missing_preserve_is_partial():
    draft = "A plain account, but it never uses the witness's own words."
    r = check_witness_fidelity(draft, _profile())
    assert r["missing_preserve"]
    assert r["violations"] == []
    assert r["verdict"] == "partial"


# ── Endpoint ────────────────────────────────────────────────────────────────

def _client(tmp_path):
    db = tmp_path / "witness.db"
    SQLiteStore(db).close()
    return db, create_app(db_path=db).test_client()


def _rn_count(db) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM rendered_narratives").fetchone()[0]
    finally:
        conn.close()


def test_voice_preview_endpoint(tmp_path):
    db, client = _client(tmp_path)
    # Create a steward profile whose directive carries the witness constraints.
    slug = client.post("/api/profiles", json={
        "name": "Witness", "voice": "first-person", "artist_prompt": DIRECTIVE,
        "critic_expectations": "Flag press-release sentences."}).get_json()["slug"]

    before = _rn_count(db)
    r = client.post("/api/critic/voice-preview", json={
        "text": "I only know what I saw; the hesitation before naming it stayed with me.",
        "profile_slug": slug})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["preview"] is True and body["persisted"] is False
    assert body["verdict"] == "strong"
    assert body["violations"] == []
    # Nothing was written.
    assert _rn_count(db) == before


def test_voice_preview_validation(tmp_path):
    _, client = _client(tmp_path)
    assert client.post("/api/critic/voice-preview", json={"profile_slug": "x"}).status_code == 400
    assert client.post("/api/critic/voice-preview", json={"text": "hi"}).status_code == 400
    assert client.post("/api/critic/voice-preview",
                       json={"text": "hi", "profile_slug": "nope"}).status_code == 404
