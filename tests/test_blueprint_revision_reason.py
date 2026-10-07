"""Promoted regression for #241: a Blueprint revision without a reason is refused.

`_persist_blueprint_revision_and_compile` requires a revision reason, and the
reason is the steward's recorded rationale on an append-only, immutable
SupersessionRelation (Constitution Art. X). JSON null means "not given",
exactly as an absent or blank reason does; it never becomes the rationale
"None". Commit 7e645ff preserves the negative version; the repair demonstrated
a strict unexpected pass before the expected failure was removed.
Synthetic workspace; no provider calls.
"""
from __future__ import annotations

import sqlite3

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_constitutional_p0 import _seed_full_chain


class FabricatedRationale(AssertionError):
    """Only the observed null-to-"None" rationale failure is expected here."""


@pytest.fixture
def predecessor(tmp_path):
    db = tmp_path / "revise.db"
    store = SQLiteStore(db)
    _seed_full_chain(store)
    store.close()
    client = create_app(db_path=db).test_client()
    obs = [r[0] for r in sqlite3.connect(db).execute("SELECT id FROM observations")]
    response = client.post("/api/pipeline/ratify-blueprint", json={"candidate": {
        "title": "T", "thesis": "Th", "sections": [{"claim": "c", "supporting_observations": obs[:1]}]}})
    assert response.status_code == 201, response.get_json()
    return db, client, obs, response.get_json()["blueprint_id"]


def _revise(client, obs, predecessor_id, **reason):
    return client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": predecessor_id, **reason,
        "candidate": {"title": "T2", "thesis": "Th", "sections": [{"claim": "c2", "supporting_observations": obs[:1]}]}})


def _state(db) -> tuple[int, list]:
    conn = sqlite3.connect(db)
    try:
        return (conn.execute("SELECT COUNT(*) FROM narrative_blueprints").fetchone()[0],
                conn.execute("SELECT reason FROM supersession_relations").fetchall())
    finally:
        conn.close()


def test_null_reason_is_refused_and_records_nothing(predecessor):
    db, client, obs, predecessor_id = predecessor
    before = _state(db)
    response = _revise(client, obs, predecessor_id, reason=None)
    if response.status_code != 400 or _state(db) != before:
        raise FabricatedRationale(f"{response.status_code} {response.get_json()} state={_state(db)}")
    assert response.get_json()["error"] == "revision reason is required"


@pytest.mark.parametrize("reason", [{}, {"reason": ""}, {"reason": "   "}])
def test_absent_or_blank_reason_is_refused(predecessor, reason):
    db, client, obs, predecessor_id = predecessor
    before = _state(db)
    response = _revise(client, obs, predecessor_id, **reason)
    assert response.status_code == 400 and response.get_json()["error"] == "revision reason is required"
    assert _state(db) == before


def test_stated_reason_is_recorded_verbatim(predecessor):
    db, client, obs, predecessor_id = predecessor
    response = _revise(client, obs, predecessor_id, reason="Sharpen the second claim.")
    assert response.status_code == 201, response.get_json()
    assert _state(db)[1] == [("Sharpen the second claim.",)]
