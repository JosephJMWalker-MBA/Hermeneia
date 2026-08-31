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


def test_artist_preview_stays_out_of_record_until_exact_save(tmp_path):
    db_path = tmp_path / "preview.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store, include_narrative=False, include_report=False)
    store.close()
    client = create_app(db_path=db_path).test_client()

    preview = client.post("/api/pipeline/preview-artist", json={
        "plan_id": ids["plan_id"],
        "provider": "null",
        "profile": "literary-en",
    })

    assert preview.status_code == 200, preview.get_data(as_text=True)
    assert preview.get_json()["persisted"] is False
    assert client.get("/api/reader/narratives").get_json()["count"] == 0

    exact = "Preview text saved exactly — no second Artist call."
    ratify = client.post("/api/pipeline/ratify-draft", json={
        "plan_id": ids["plan_id"],
        "provider": "null",
        "profile_slug": "literary-en",
        "text": exact,
    })

    assert ratify.status_code == 201, ratify.get_data(as_text=True)
    payload = client.get("/api/reader/narratives").get_json()
    assert payload["count"] == 1
    detail = client.get(f"/api/reader/narratives/{ratify.get_json()['id']}").get_json()
    assert detail["rendered_narrative"]["text"] == exact


def test_record_list_exposes_pending_accepted_rejected_without_filtering(tmp_path):
    db_path = tmp_path / "statuses.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store, include_narrative=False, include_report=False)
    conn = store._conn
    rows = [
        ("record-pending", "stub-pending", "pending", None, "2026-08-30T21:10:00+00:00"),
        ("record-accepted", "stub-accepted", "accepted", "Accepted by steward.", "2026-08-30T21:12:00+00:00"),
        ("record-rejected", "stub-rejected", "rejected", "Rejected by steward.", "2026-08-30T21:11:00+00:00"),
    ]
    for narrative_id, provider, status, rationale, created_at in rows:
        conn.execute(
            """
            INSERT INTO rendered_narratives
                (id, architect_plan_id, provider, expression_profile_id, text,
                 prompt_used, execution_config, created_at, narrative_status,
                 narrative_rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                narrative_id,
                ids["plan_id"],
                provider,
                ids["profile_id"],
                f"Text for {status}",
                "Prompt.",
                '{"provider":"stub"}',
                created_at,
                status,
                rationale,
            ),
        )
    conn.commit()
    store.close()
    client = create_app(db_path=db_path).test_client()

    payload = client.get("/api/reader/narratives").get_json()

    assert payload["count"] == 3
    assert [row["id"] for row in payload["narratives"]] == [
        "record-accepted",
        "record-rejected",
        "record-pending",
    ]
    statuses = {row["id"]: row["narrative_status"] for row in payload["narratives"]}
    assert statuses == {
        "record-pending": "pending",
        "record-accepted": "accepted",
        "record-rejected": "rejected",
    }
    rejected = next(row for row in payload["narratives"] if row["id"] == "record-rejected")
    assert rejected["narrative_rationale"] == "Rejected by steward."
