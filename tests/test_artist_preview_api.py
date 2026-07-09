"""POST /api/pipeline/preview-artist — a non-persisting Artist draft preview.

The Reader "Draft" tab renders a Blueprint's ArchitectPlan under a chosen
ExpressionProfile and shows the draft as a PREVIEW — nothing is saved or
accepted. These tests guard that contract: full text is returned, the selected
profile applies, and the rendered_narratives table is never written to.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


@pytest.fixture
def seeded(tmp_path):
    db_path = tmp_path / "preview.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    return db_path, ids, create_app(db_path=db_path).test_client()


def _rn_count(db_path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM rendered_narratives").fetchone()[0]
    finally:
        conn.close()


def test_preview_returns_full_text_and_persists_nothing(seeded):
    db_path, ids, client = seeded
    before = _rn_count(db_path)
    r = client.post("/api/pipeline/preview-artist",
                    json={"plan_id": ids["plan_id"], "provider": "null"})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["preview"] is True
    assert body["persisted"] is False
    assert body["text"], "full draft text should be present"
    assert body["provider"] == "null"
    # The defining guarantee: a preview adds nothing to the record.
    assert _rn_count(db_path) == before


def test_preview_applies_selected_profile(seeded):
    db_path, ids, client = seeded
    before = _rn_count(db_path)
    r = client.post("/api/pipeline/preview-artist", json={
        "plan_id": ids["plan_id"], "provider": "null", "profile": "literary-en"})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["profile_slug"] == "literary-en"
    assert body["profile_name"], "resolved profile name should be echoed so the UI can show it"
    assert _rn_count(db_path) == before


def test_preview_requires_plan_id(seeded):
    _, _, client = seeded
    assert client.post("/api/pipeline/preview-artist",
                       json={"provider": "null"}).status_code == 400


def test_render_for_plan_persist_flag(tmp_path):
    from hermeneia.narrative.artist_service import render_for_plan
    from hermeneia.storage.hashing import make_rendered_narrative_id

    db_path = tmp_path / "persist.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()

    # The deterministic id for a null-provider, no-profile render of this plan.
    narrative_id = make_rendered_narrative_id(ids["plan_id"], "null", None)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        def _has(nid):
            return conn.execute(
                "SELECT 1 FROM rendered_narratives WHERE id = ?", (nid,)).fetchone() is not None

        before = conn.execute("SELECT COUNT(*) FROM rendered_narratives").fetchone()[0]
        # persist=False renders but writes nothing…
        render_for_plan(ids["plan_id"], conn, provider_name="null", persist=False)
        assert conn.execute("SELECT COUNT(*) FROM rendered_narratives").fetchone()[0] == before
        assert not _has(narrative_id)
        # …while the default persist=True records this exact narrative.
        render_for_plan(ids["plan_id"], conn, provider_name="null")
        assert _has(narrative_id)
    finally:
        conn.close()
