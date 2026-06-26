"""
Tests for Multi-Profile Artist Rendering.

Proves:
- All built-in profiles are present in the DB after initialization
- render_for_plan succeeds for every built-in profile with null provider
- Each profile produces a distinct RenderedNarrative (different profile_id)
- POST /api/pipeline/run-artist-all-profiles returns one result per profile
- All results have status "created" or "exists" (no errors with null provider)
- Second call for same plan_id returns all "exists" (idempotent)
- Translation profiles (literary-es, literary-fr, literary-sw) are included
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.narrative.profiles import BUILT_IN_PROFILES, list_profiles
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def seeded(tmp_path):
    db_path = tmp_path / "multi.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    app = create_app(db_path=db_path)
    return db_path, ids, app.test_client()


# ── Profile registry ──────────────────────────────────────────────────────────

def test_built_in_profiles_include_translation_slugs():
    slugs = {p["slug"] for p in BUILT_IN_PROFILES}
    assert "literary-es" in slugs, "Spanish profile missing"
    assert "literary-sw" in slugs, "Swahili profile missing"
    assert "literary-fr" in slugs, "French profile missing"


def test_profiles_seeded_into_db(tmp_path):
    from hermeneia.storage.sqlite import ensure_profile_tables
    db_path = tmp_path / "profiles.db"
    store = SQLiteStore(db_path)
    ensure_profile_tables(store._conn)
    profiles = list_profiles(store._conn)
    store.close()
    slugs = {p["slug"] for p in profiles}
    assert "literary-en" in slugs
    assert "literary-es" in slugs
    assert "literary-sw" in slugs
    assert "executive-en" in slugs
    assert len(profiles) >= len(BUILT_IN_PROFILES)


def test_translation_profiles_have_correct_language(tmp_path):
    from hermeneia.storage.sqlite import ensure_profile_tables
    db_path = tmp_path / "profiles.db"
    store = SQLiteStore(db_path)
    ensure_profile_tables(store._conn)
    profiles = {p["slug"]: p for p in list_profiles(store._conn)}
    store.close()
    assert profiles["literary-es"]["language"] == "es"
    assert profiles["literary-sw"]["language"] == "sw"
    assert profiles["literary-fr"]["language"] == "fr"
    assert profiles["literary-en"]["language"] == "en"


# ── render_for_plan per profile ────────────────────────────────────────────────

def test_render_for_plan_each_built_in_profile(tmp_path):
    """null provider renders successfully for every built-in profile."""
    from hermeneia.storage.sqlite import ensure_profile_tables
    db_path = tmp_path / "all_profiles.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    ensure_profile_tables(store._conn)
    conn = store._conn

    from hermeneia.narrative.artist_service import render_for_plan

    profiles = list_profiles(conn)
    assert len(profiles) >= len(BUILT_IN_PROFILES)

    narrative_ids = set()
    for profile in profiles:
        result = render_for_plan(
            ids["plan_id"], conn,
            provider_name="null",
            profile_slug=profile["slug"],
        )
        assert result.row["id"], f"No narrative ID for profile {profile['slug']}"
        narrative_ids.add(result.row["id"])

    # Each profile produces a distinct narrative slot
    assert len(narrative_ids) == len(profiles)
    store.close()


def test_render_all_profiles_idempotent(tmp_path):
    """Rendering twice with null provider returns same narrative IDs."""
    from hermeneia.storage.sqlite import ensure_profile_tables
    db_path = tmp_path / "idempotent.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    ensure_profile_tables(store._conn)
    conn = store._conn

    from hermeneia.narrative.artist_service import render_for_plan

    profiles = list_profiles(conn)
    first_ids = {
        p["slug"]: render_for_plan(ids["plan_id"], conn, provider_name="null",
                                   profile_slug=p["slug"]).row["id"]
        for p in profiles
    }
    second_ids = {
        p["slug"]: render_for_plan(ids["plan_id"], conn, provider_name="null",
                                   profile_slug=p["slug"]).row["id"]
        for p in profiles
    }
    assert first_ids == second_ids
    store.close()


# ── API endpoint ──────────────────────────────────────────────────────────────

def test_run_artist_all_profiles_returns_one_per_profile(seeded):
    db_path, ids, client = seeded

    resp = client.post("/api/pipeline/run-artist-all-profiles", json={
        "plan_id": ids["plan_id"],
        "provider": "null",
    })

    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data
    results = data["results"]

    # One result per built-in profile
    assert len(results) >= len(BUILT_IN_PROFILES)

    slugs = {r["profile_slug"] for r in results}
    assert "literary-en" in slugs
    assert "literary-es" in slugs
    assert "literary-sw" in slugs


def test_run_artist_all_profiles_no_errors_with_null(seeded):
    db_path, ids, client = seeded

    resp = client.post("/api/pipeline/run-artist-all-profiles", json={
        "plan_id": ids["plan_id"],
        "provider": "null",
    })

    assert resp.status_code == 200
    results = resp.get_json()["results"]
    for r in results:
        assert r["status"] in ("created", "exists"), \
            f"Profile {r['profile_slug']} got status {r['status']}: {r.get('error')}"


def test_run_artist_all_profiles_second_call_exists(seeded):
    db_path, ids, client = seeded

    payload = {"plan_id": ids["plan_id"], "provider": "null"}
    client.post("/api/pipeline/run-artist-all-profiles", json=payload)
    resp = client.post("/api/pipeline/run-artist-all-profiles", json=payload)

    assert resp.status_code == 200
    results = resp.get_json()["results"]
    for r in results:
        assert r["status"] == "exists", \
            f"Profile {r['profile_slug']} should be 'exists' on second call, got {r['status']}"


def test_run_artist_all_profiles_missing_plan_id(seeded):
    _, _, client = seeded
    resp = client.post("/api/pipeline/run-artist-all-profiles", json={"provider": "null"})
    assert resp.status_code == 400


def test_run_artist_all_profiles_translation_profiles_present(seeded):
    db_path, ids, client = seeded

    resp = client.post("/api/pipeline/run-artist-all-profiles", json={
        "plan_id": ids["plan_id"],
        "provider": "null",
    })

    assert resp.status_code == 200
    results = {r["profile_slug"]: r for r in resp.get_json()["results"]}
    assert results["literary-es"]["language"] == "es"
    assert results["literary-sw"]["language"] == "sw"
    assert results["literary-fr"]["language"] == "fr"
