"""Promoted regressions for #243: a null Blueprint title, thesis or claim never becomes "None".

Every Blueprint commit route requires a title, a thesis and section claims
("title is required", "thesis is required", "section N claim is required";
the extractor's "missing required keys" / "missing 'claim'"; architect/import
skips a section without a claim). JSON null — from a client or a provider
reply — means "not given", exactly as an absent key does; it never becomes
the literal "None" in an immutable NarrativeBlueprint (Constitution Art. X).
Commit b27b4e8 preserves the negative versions; the repair demonstrated
strict unexpected passes before the expected failures were removed.
Synthetic workspace; offline in-process extractor provider.
"""
from __future__ import annotations

import json
import sqlite3
import unittest.mock as mock
from types import SimpleNamespace

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_constitutional_p0 import _seed_full_chain

FIELDS = ("title", "thesis", "claim")


class NoneCommitted(AssertionError):
    """Only the observed null-to-"None" Blueprint failures are expected here."""


@pytest.fixture
def workspace(tmp_path):
    db = tmp_path / "blueprints.db"
    store = SQLiteStore(db)
    _seed_full_chain(store)
    store.close()
    client = create_app(db_path=db).test_client()
    obs = [r[0] for r in sqlite3.connect(db).execute("SELECT id FROM observations")]
    return db, client, obs


def _candidate(obs, null_field: str | None = None) -> dict:
    candidate = {"title": "T", "thesis": "Th", "sections": [{"claim": "c", "supporting_observations": obs[:1]}]}
    if null_field == "claim":
        candidate["sections"][0]["claim"] = None
    elif null_field:
        candidate[null_field] = None
    return candidate


def _blueprints(db) -> list[tuple[str, str, list[str]]]:
    rows = sqlite3.connect(db).execute("SELECT title, thesis, sections FROM narrative_blueprints").fetchall()
    return [(title, thesis, [s["claim"] for s in json.loads(sections)]) for title, thesis, sections in rows]


def _check(db, before, response, expected_status: int = 400):
    stored = _blueprints(db)
    fabricated = [b for b in stored if "None" in (b[0], b[1], *b[2])]
    if fabricated or response.status_code != expected_status or stored != before:
        raise NoneCommitted(f"{response.status_code} fabricated={fabricated}")


class _ExtractorReply:
    """Anthropic-shaped provider whose Blueprint reply carries one null field."""

    def __init__(self, null_field: str):
        reply = {"title": "Extracted", "thesis": "An extracted thesis.", "sections": [{"claim": "An extracted claim."}]}
        if null_field == "claim":
            reply["sections"][0]["claim"] = None
        else:
            reply[null_field] = None
        content = [SimpleNamespace(text=json.dumps(reply))]
        self._model = "fake-extractor"
        self._client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_k: SimpleNamespace(content=content)))


@pytest.mark.parametrize("field", FIELDS)
def test_ratify_refuses_a_null_required_field(workspace, field):
    db, client, obs = workspace
    before = _blueprints(db)
    response = client.post("/api/pipeline/ratify-blueprint", json={"candidate": _candidate(obs, field)})
    _check(db, before, response)


@pytest.mark.parametrize("field", FIELDS)
def test_revise_refuses_a_null_required_field(workspace, field):
    db, client, obs = workspace
    predecessor = client.post("/api/pipeline/ratify-blueprint", json={"candidate": _candidate(obs)}).get_json()
    before = _blueprints(db)
    candidate = _candidate(obs, field)
    candidate["sections"][0]["supporting_observations"] = obs[:1]
    response = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": predecessor["blueprint_id"], "reason": "Revise.", "candidate": candidate})
    _check(db, before, response)


@pytest.mark.parametrize("field", FIELDS)
def test_extract_and_save_refuses_a_provider_null_required_field(workspace, field):
    db, client, _obs = workspace
    before = _blueprints(db)
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=_ExtractorReply(field)):
        response = client.post("/api/pipeline/extract-blueprint",
                               json={"text": "A document to extract.", "provider": "fake", "save": True})
    _check(db, before, response, expected_status=422)


@pytest.mark.parametrize("field", ("title", "thesis"))
def test_import_refuses_a_null_title_or_thesis(workspace, field):
    db, client, _obs = workspace
    before = _blueprints(db)
    body = {"title": "T", "thesis": "Th", "sections": [{"claim": "c", "obs_refs": ["OBS-1"]}], field: None}
    response = client.post("/api/architect/import", json=body)
    _check(db, before, response)


def test_import_skips_a_section_whose_claim_is_null_as_it_skips_a_blank_one(workspace):
    db, client, _obs = workspace
    response = client.post("/api/architect/import", json={"title": "T", "thesis": "Th", "sections": [
        {"claim": None, "obs_refs": ["OBS-1"]}, {"claim": "Kept claim.", "obs_refs": ["OBS-1"]}]})
    claims = [claims for title, _thesis, claims in _blueprints(db) if title == "T"]
    if response.status_code != 201 or claims != [["Kept claim."]]:
        raise NoneCommitted(f"{response.status_code} claims={claims}")


def test_absent_and_blank_fields_keep_their_existing_refusals(workspace):
    db, client, obs = workspace
    candidate = _candidate(obs)
    del candidate["title"]
    assert client.post("/api/pipeline/ratify-blueprint", json={"candidate": candidate}).get_json()["error"] == "title is required"
    blank = _candidate(obs)
    blank["sections"][0]["claim"] = "  "
    assert client.post("/api/pipeline/ratify-blueprint", json={"candidate": blank}).get_json()["error"] == "section 1 claim is required"
    assert client.post("/api/architect/import", json={"thesis": "Th", "sections": [{"claim": "c"}]}).get_json()["error"] == "title is required"
