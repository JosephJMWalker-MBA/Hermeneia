"""Ratify & Save — persist the EXACT previewed Artist draft as a RenderedNarrative.

Ratification is the moment a generated artifact enters the durable record. The
core requirement: it stores the bytes the steward saw and judged, verbatim, and
never re-renders. These tests guard that — exact text, idempotency, provenance,
and immutability.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from hermeneia.storage.hashing import make_expression_profile_id, make_rendered_narrative_id
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


@pytest.fixture
def seeded(tmp_path):
    db_path = tmp_path / "ratify.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    return db_path, ids, create_app(db_path=db_path).test_client()


def _row_text(db_path, narrative_id):
    conn = sqlite3.connect(db_path)
    try:
        r = conn.execute(
            "SELECT text, architect_plan_id, provider, expression_profile_id, prompt_used "
            "FROM rendered_narratives WHERE id = ?", (narrative_id,)).fetchone()
        return r
    finally:
        conn.close()


def test_ratify_persists_exact_bytes(seeded):
    db_path, ids, client = seeded
    profile_slug = "literary-en"
    exact = "The exact draft the steward saw — verbatim, with a ✦ marker 12345."
    r = client.post("/api/pipeline/ratify-draft", json={
        "plan_id": ids["plan_id"], "provider": "ratify-test",
        "profile_slug": profile_slug, "text": exact})
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["created"] is True and body["status"] == "ratified"

    nid = make_rendered_narrative_id(ids["plan_id"], "ratify-test", make_expression_profile_id(profile_slug))
    assert body["id"] == nid
    row = _row_text(db_path, nid)
    assert row is not None
    assert row[0] == exact                       # exact bytes, verbatim
    assert row[1] == ids["plan_id"]              # plan provenance
    assert row[2] == "ratify-test"               # provider provenance
    assert row[3] == make_expression_profile_id(profile_slug)  # profile provenance
    assert row[4]                                # prompt_used reconstructed


def test_second_ratify_is_idempotent_and_does_not_overwrite(seeded):
    db_path, ids, client = seeded
    payload = {"plan_id": ids["plan_id"], "provider": "ratify-test",
               "profile_slug": "literary-en", "text": "FIRST ratified draft."}
    first = client.post("/api/pipeline/ratify-draft", json=payload)
    assert first.status_code == 201
    nid = first.get_json()["id"]

    # A second ratify with DIFFERENT text must not re-render or overwrite.
    second = client.post("/api/pipeline/ratify-draft", json={**payload, "text": "SECOND, different."})
    assert second.status_code == 200
    assert second.get_json()["status"] == "already_ratified"
    assert _row_text(db_path, nid)[0] == "FIRST ratified draft."  # unchanged


def test_ratified_narrative_is_immutable(seeded):
    db_path, ids, client = seeded
    nid = client.post("/api/pipeline/ratify-draft", json={
        "plan_id": ids["plan_id"], "provider": "null", "text": "immutable draft"}).get_json()["id"]
    conn = sqlite3.connect(db_path)
    try:
        raised = False
        try:
            conn.execute("UPDATE rendered_narratives SET text='x' WHERE id=?", (nid,))
            conn.commit()
        except sqlite3.Error:
            raised = True
        assert raised
    finally:
        conn.close()


def test_ratify_validation(seeded):
    _, ids, client = seeded
    assert client.post("/api/pipeline/ratify-draft", json={"text": "x"}).status_code == 400
    assert client.post("/api/pipeline/ratify-draft", json={"plan_id": ids["plan_id"]}).status_code == 400
    assert client.post("/api/pipeline/ratify-draft",
                       json={"plan_id": ids["plan_id"], "text": "   "}).status_code == 400
