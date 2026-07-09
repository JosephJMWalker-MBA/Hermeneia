"""POST /api/profiles — steward-authored ExpressionProfile creation (#93).

The Reader's "Voice" tab captures witness constraints and saves them as a real
ExpressionProfile — the object the Artist/Critic pipeline consumes. These tests
guard the web create path: it persists a steward-authored profile, generates a
unique slug, validates input, and lands in the immutable expression_profiles
table.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "profiles_test.db"
    SQLiteStore(db_path).close()
    return db_path


def test_post_creates_steward_authored_profile(tmp_path):
    client = create_app(db_path=_make_db(tmp_path)).test_client()
    r = client.post("/api/profiles", json={
        "name": "Field-witness",
        "voice": "first-person, testimonial",
        "audience": "a reader who was not in the room",
        "artist_prompt": ("Voice: first-person, testimonial\n\n"
                          "Avoid — never do this:\n- do not turn this into consultant language"),
        "critic_expectations": "Flag any sentence that sounds like a press release.",
    })
    assert r.status_code == 201, r.get_data(as_text=True)
    assert r.get_json()["slug"] == "field-witness"

    listing = client.get("/api/profiles").get_json()["profiles"]
    mine = [p for p in listing if p["slug"] == "field-witness"]
    assert mine, "created profile should appear in GET /api/profiles"
    assert mine[0]["source"] == "steward-authored"
    assert "consultant language" in mine[0]["artist_prompt"]
    assert mine[0]["critic_expectations"] == "Flag any sentence that sounds like a press release."


def test_duplicate_name_gets_a_distinct_slug(tmp_path):
    client = create_app(db_path=_make_db(tmp_path)).test_client()
    payload = {"name": "Plain", "artist_prompt": "Voice: plain and unhurried"}
    a = client.post("/api/profiles", json=payload)
    b = client.post("/api/profiles", json=payload)
    assert a.status_code == 201 and b.status_code == 201
    assert a.get_json()["slug"] == "plain"
    assert a.get_json()["slug"] != b.get_json()["slug"], "second save must not collide"


def test_validation_requires_name_and_directive(tmp_path):
    client = create_app(db_path=_make_db(tmp_path)).test_client()
    assert client.post("/api/profiles", json={"artist_prompt": "x"}).status_code == 400
    assert client.post("/api/profiles", json={"name": "x"}).status_code == 400


def test_saved_profile_is_immutable(tmp_path):
    db = _make_db(tmp_path)
    client = create_app(db_path=db).test_client()
    slug = client.post("/api/profiles", json={
        "name": "Immutable", "artist_prompt": "Voice: fixed"}).get_json()["slug"]

    # The table's no_update trigger forbids mutation — confirms the profile is a
    # provenance-grade, create-once record, not editable in place.
    conn = sqlite3.connect(db)
    try:
        raised = False
        try:
            conn.execute("UPDATE expression_profiles SET name='x' WHERE slug=?", (slug,))
            conn.commit()
        except sqlite3.Error:
            raised = True
        assert raised, "ExpressionProfile must be immutable"
    finally:
        conn.close()
