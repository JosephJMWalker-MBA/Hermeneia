"""Frozen witnesses for #244: a provider's null output never becomes "None" in a Blueprint.

`/api/architect/generate` already defines how missing provider output is
handled: a missing thesis (or no sections) is refused ("AI response missing
thesis or sections"), a section without a claim is skipped, no usable section
is refused ("No valid sections could be built from AI response"), and an
absent title takes the route's default "Untitled Blueprint". A null value in
the provider's JSON reply is missing output and gets exactly that handling;
no replacement content is invented. Offline in-process provider.
"""
from __future__ import annotations

import json
import sqlite3
import unittest.mock as mock

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_constitutional_p0 import _seed_full_chain


class NoneCommitted(AssertionError):
    """Only the observed provider-null-to-"None" failures are expected here."""


class ArchitectReply:
    def __init__(self, reply: dict):
        self.reply = reply

    def render(self, prompt: str) -> str:
        return json.dumps(self.reply)


@pytest.fixture
def workspace(tmp_path):
    db = tmp_path / "generate.db"
    store = SQLiteStore(db)
    _seed_full_chain(store)
    store.close()
    return db, create_app(db_path=db).test_client()


def _section(claim):
    return {"claim": claim, "obs_refs": ["OBS-1"], "interp_refs": []}


def _generate(client, reply: dict):
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=ArchitectReply(reply)):
        return client.post("/api/architect/generate", json={"directive": "Build from the evidence.", "provider": "fake"})


def _blueprints(db) -> list[tuple[str, str, list[str]]]:
    rows = sqlite3.connect(db).execute("SELECT title, thesis, sections FROM narrative_blueprints").fetchall()
    return [(title, thesis, [s["claim"] for s in json.loads(sections)]) for title, thesis, sections in rows]


def _fabricated(db) -> list:
    return [b for b in _blueprints(db) if "None" in (b[0], b[1], *b[2])]


@pytest.mark.xfail(strict=True, raises=NoneCommitted,
                   reason="#244: a provider's null thesis is committed as 'None'; repair requires its own packet")
def test_null_thesis_is_refused_as_missing(workspace):
    db, client = workspace
    before = _blueprints(db)
    response = _generate(client, {"title": "AI", "thesis": None, "sections": [_section("A claim.")]})
    if response.status_code != 500 or _blueprints(db) != before or _fabricated(db):
        raise NoneCommitted(f"{response.status_code} fabricated={_fabricated(db)}")
    assert response.get_json()["error"] == "AI response missing thesis or sections"


@pytest.mark.xfail(strict=True, raises=NoneCommitted,
                   reason="#244: a provider's null claim is committed as 'None'; repair requires its own packet")
def test_null_claim_section_is_skipped_as_a_blank_one_is(workspace):
    db, client = workspace
    response = _generate(client, {"title": "AI", "thesis": "AI thesis.", "sections": [_section(None), _section("Kept.")]})
    mine = [claims for title, _thesis, claims in _blueprints(db) if title == "AI"]
    if response.status_code != 201 or mine != [["Kept."]]:
        raise NoneCommitted(f"{response.status_code} claims={mine}")


@pytest.mark.xfail(strict=True, raises=NoneCommitted,
                   reason="#244: provider sections with only null claims are committed as 'None'; repair requires its own packet")
def test_only_null_claims_is_refused_as_no_valid_sections(workspace):
    db, client = workspace
    before = _blueprints(db)
    response = _generate(client, {"title": "AI", "thesis": "AI thesis.", "sections": [_section(None)]})
    if response.status_code != 500 or _blueprints(db) != before:
        raise NoneCommitted(f"{response.status_code} fabricated={_fabricated(db)}")
    assert response.get_json()["error"] == "No valid sections could be built from AI response"


@pytest.mark.xfail(strict=True, raises=NoneCommitted,
                   reason="#244: a provider's null title is committed as 'None'; repair requires its own packet")
def test_null_title_takes_the_absent_title_default(workspace):
    db, client = workspace
    response = _generate(client, {"title": None, "thesis": "AI thesis.", "sections": [_section("A claim.")]})
    titles = [title for title, thesis, _claims in _blueprints(db) if thesis == "AI thesis."]
    if response.status_code != 201 or titles != ["Untitled Blueprint"]:
        raise NoneCommitted(f"{response.status_code} titles={titles}")


def test_absent_and_blank_output_keep_their_existing_handling(workspace):
    db, client = workspace
    assert _generate(client, {"title": "AI", "sections": [_section("c")]}).status_code == 500
    response = _generate(client, {"thesis": "Absent title.", "sections": [_section(""), _section("Kept.")]})
    assert response.status_code == 201
    assert [(t, c) for t, th, c in _blueprints(db) if th == "Absent title."] == [("Untitled Blueprint", ["Kept."])]
