from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hermeneia.storage.hashing import sha256_file
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

from test_constitutional_p0 import _seed_full_chain


def _table_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    conn.close()
    return counts


def _seed_workspace_db(tmp_path: Path) -> tuple[Path, dict]:
    db_path = tmp_path / "workspace.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(
        store,
        architect_terms=["evidence"],
        report_overrides={
            "semantic_fidelity": 100.0,
            "required_terms_present": json.dumps(["evidence"]),
        },
    )
    store.close()
    return db_path, ids


def _without_interface_profile(projection: dict) -> dict:
    return {
        key: value
        for key, value in projection.items()
        if key != "interface_profile"
    }


def test_workspace_projection_returns_canonical_references_only(tmp_path):
    db_path, ids = _seed_workspace_db(tmp_path)
    unrelated_document_id = "d" * 64
    store = SQLiteStore(db_path)
    store.insert_source_document({
        "id": unrelated_document_id,
        "original_filename": "unrelated.pdf",
        "file_hash": unrelated_document_id,
        "total_pages": 1,
        "registered_at": "2026-06-20T00:00:00+00:00",
        "compiler_version": "test",
    })
    store.close()
    client = create_app(db_path=db_path).test_client()

    response = client.get(
        f"/api/workspace/rendered_narrative/{ids['narrative_id']}?profile=scholar"
    )

    assert response.status_code == 200
    projection = response.get_json()
    assert projection["focus"] == {
        "epistemic_class": "RenderedNarrative",
        "id": ids["narrative_id"],
    }
    assert projection["interface_profile"] == "scholar"
    assert projection["related"]["ArchitectPlan"] == [ids["plan_id"]]
    assert projection["related"]["Blueprint"] == [ids["bp_id"]]
    assert projection["related"]["Interpretation"] == [ids["interp_id"]]
    assert projection["related"]["Observation"] == [ids["obs_id"]]
    assert projection["related"]["SourceExtraction"] == [ids["extraction_id"]]
    assert projection["related"]["SourceDocument"] == [ids["doc_id"]]
    assert projection["related"]["ExpressionProfile"] == [ids["profile_id"]]
    assert projection["related"]["CriticReport"] == [ids["report_id"]]

    serialized = json.dumps(projection)
    assert "workspace_id" not in serialized
    assert "created_at" not in serialized
    assert '"label"' not in serialized
    assert '"icon"' not in serialized
    assert "Story" not in serialized
    assert unrelated_document_id not in serialized


def test_workspace_profiles_change_expression_only(tmp_path):
    db_path, ids = _seed_workspace_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    projections = {
        profile: client.get(
            f"/api/workspace/rendered_narrative/{ids['narrative_id']}"
            f"?profile={profile}"
        ).get_json()
        for profile in ("child", "elder", "scholar")
    }

    assert {
        profile: projection["interface_profile"]
        for profile, projection in projections.items()
    } == {
        "child": "child",
        "elder": "elder",
        "scholar": "scholar",
    }
    assert (
        _without_interface_profile(projections["child"])
        == _without_interface_profile(projections["elder"])
        == _without_interface_profile(projections["scholar"])
    )


def test_workspace_projection_is_reconstructible_and_has_no_persisted_state(tmp_path):
    db_path, ids = _seed_workspace_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    url = (
        f"/api/workspace/observation/{ids['obs_id']}?profile=child"
    )
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    first = client.get(url)
    second = client.get(url)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == second.get_json()
    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts

    projection = first.get_json()
    assert projection["related"]["RenderedNarrative"] == [ids["narrative_id"]]
    assert projection["related"]["CriticReport"] == [ids["report_id"]]


def test_workspace_projection_returns_existing_inspection_surfaces(tmp_path):
    db_path, ids = _seed_workspace_db(tmp_path)
    projection = create_app(db_path=db_path).test_client().get(
        f"/api/workspace/rendered_narrative/{ids['narrative_id']}?profile=elder"
    ).get_json()

    assert projection["surfaces"]["lineage"]["href"] == (
        f"/api/lineage/rendered_narrative/{ids['narrative_id']}"
    )
    assert projection["surfaces"]["trust"] == [{
        "rendered_narrative": {
            "epistemic_class": "RenderedNarrative",
            "id": ids["narrative_id"],
        },
        "href": f"/api/trust/rendered_narrative/{ids['narrative_id']}",
    }]
    contract = projection["surfaces"]["semantic_contract"][0]
    critic = projection["surfaces"]["critic"][0]
    assert contract["architect_plan"]["id"] == ids["plan_id"]
    assert contract["rendered_narrative"]["id"] == ids["narrative_id"]
    assert contract["href"].startswith(f"/api/fidelity/{ids['bp_id']}/")
    assert critic["critic_report"]["id"] == ids["report_id"]
    assert critic["href"] == contract["href"]


def test_workspace_projection_rejects_missing_profile_and_unknown_class(tmp_path):
    db_path, ids = _seed_workspace_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    missing_profile = client.get(
        f"/api/workspace/rendered_narrative/{ids['narrative_id']}"
    )
    unknown_profile = client.get(
        f"/api/workspace/rendered_narrative/{ids['narrative_id']}?profile=brand"
    )
    unknown_class = client.get(
        f"/api/workspace/story/{ids['narrative_id']}?profile=child"
    )

    assert missing_profile.status_code == 400
    assert unknown_profile.status_code == 400
    assert unknown_class.status_code == 400
