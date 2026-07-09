"""Record View — the read path the ledger depends on.

A ratified draft must surface in the record ledger with its provenance, and its
detail must return the exact saved bytes plus a lineage surface back to evidence.
These guard that end-to-end read path (the Record tab is a client-side view over
these existing endpoints).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


@pytest.fixture
def seeded(tmp_path):
    db_path = tmp_path / "record.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    return db_path, ids, create_app(db_path=db_path).test_client()


def test_ratified_draft_appears_in_ledger_with_provenance(seeded):
    _, ids, client = seeded
    exact = "The ratified artifact — exact bytes for the record ledger."
    ratify = client.post("/api/pipeline/ratify-draft", json={
        "plan_id": ids["plan_id"], "provider": "record-test",
        "profile_slug": "literary-en", "text": exact})
    assert ratify.status_code == 201, ratify.get_data(as_text=True)
    nid = ratify.get_json()["id"]

    ledger = client.get("/api/reader/narratives").get_json()["narratives"]
    mine = [n for n in ledger if n["id"] == nid]
    assert mine, "ratified narrative must appear in the ledger"
    row = mine[0]
    assert row["provider"] == "record-test"
    assert row["profile"]["slug"] == "literary-en"
    assert row["blueprint"]["title"]      # blueprint provenance present
    assert row["blueprint"]["thesis"]


def test_record_detail_returns_exact_text_and_lineage_surface(seeded):
    _, ids, client = seeded
    exact = "Verbatim record bytes ✦ 98765."
    nid = client.post("/api/pipeline/ratify-draft", json={
        "plan_id": ids["plan_id"], "provider": "record-test",
        "profile_slug": "literary-en", "text": exact}).get_json()["id"]

    detail = client.get(f"/api/reader/narratives/{nid}").get_json()
    assert detail["rendered_narrative"]["text"] == exact          # exact saved bytes
    assert detail["blueprint"]["thesis"]
    assert detail["profile"]["slug"] == "literary-en"
    # Trace-to-evidence surface is offered.
    assert "lineage" in detail["surfaces"]
    lineage_href = detail["surfaces"]["lineage"]
    assert lineage_href.endswith(nid)

    # The lineage surface resolves to an ancestry graph reaching Observations.
    graph = client.get(lineage_href).get_json()
    classes = {n["class"] for n in graph.get("nodes", [])}
    assert "RenderedNarrative" in classes
    assert "Observation" in classes      # walks back to evidence
