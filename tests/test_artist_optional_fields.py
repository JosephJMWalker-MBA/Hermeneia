"""Frozen witness for #240: JSON null for an optional Artist field means "not given".

The preview and ratify routes document `profile?`, `profile_slug?` and
`provider: "null"?` as optional, and the Reader sends `profile || null` and
`profile_slug: d.profileSlug || null` for its "No Expression Profile" choice.
JSON null therefore means no Expression Profile (or the default provider),
exactly as an absent key does; it never becomes the string "None".
In-process scripted Artist; no network.
"""
from __future__ import annotations

import sqlite3

import pytest

from hermeneia.narrative import artist_service
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_constitutional_p0 import _seed_full_chain
from test_ratify_draft_candidate import ScriptedArtist


class NullFieldCoerced(AssertionError):
    """Only the observed null-to-"None" coercion failures are expected here."""


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    db_path = tmp_path / "optional.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    monkeypatch.setattr(artist_service, "get_provider",
                        lambda name="null", **_k: ScriptedArtist(name, ["An unvoiced draft."]))
    return db_path, ids, create_app(db_path=db_path).test_client()


@pytest.mark.xfail(strict=True, raises=NullFieldCoerced,
                   reason="#240: null profile becomes the slug 'None'; repair requires its own packet")
def test_no_expression_profile_previews_and_ratifies_as_the_reader_sends_it(seeded):
    db, ids, client = seeded
    preview = client.post("/api/pipeline/preview-artist",
                          json={"plan_id": ids["plan_id"], "profile": None, "provider": "ratify-test"})
    if preview.status_code != 200:
        raise NullFieldCoerced(f"preview {preview.status_code} {preview.get_json()}")
    held = preview.get_json()
    assert held["profile_slug"] is None
    ratify = client.post("/api/pipeline/ratify-draft", json={
        "plan_id": ids["plan_id"], "provider": held["provider"], "profile_slug": None,
        "text": held["text"], "candidate_id": held["candidate_id"]})
    if ratify.status_code != 201:
        raise NullFieldCoerced(f"ratify {ratify.status_code} {ratify.get_json()}")
    profile_id = sqlite3.connect(db).execute(
        "SELECT expression_profile_id FROM rendered_narratives WHERE id = ?", (ratify.get_json()["id"],)).fetchone()[0]
    assert profile_id is None


@pytest.mark.xfail(strict=True, raises=NullFieldCoerced,
                   reason="#240: null provider becomes the provider 'None'; repair requires its own packet")
def test_null_provider_previews_with_the_default_provider(seeded):
    _db, ids, client = seeded
    preview = client.post("/api/pipeline/preview-artist",
                          json={"plan_id": ids["plan_id"], "profile": "literary-en", "provider": None})
    if preview.status_code != 200 or preview.get_json()["provider"] != "null":
        raise NullFieldCoerced(f"preview {preview.status_code} {preview.get_json()}")
