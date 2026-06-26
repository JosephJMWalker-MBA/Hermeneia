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


def _seed_architect_explorer_db(tmp_path: Path) -> tuple[Path, dict]:
    db_path = tmp_path / "architect_explorer.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(
        store,
        architect_terms=["evidence", "fixed"],
        report_overrides={
            "semantic_fidelity": 100.0,
            "required_terms_present": json.dumps(["evidence remains fixed", "evidence remains", "remains fixed"]),
        },
    )
    store.close()
    return db_path, ids


def test_architect_blueprints_lists_existing_blueprint_and_plan(tmp_path):
    db_path, ids = _seed_architect_explorer_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get("/api/architect/blueprints")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    blueprint = payload["blueprints"][0]
    assert blueprint["id"] == ids["bp_id"]
    assert blueprint["has_architect_plan"] is True
    assert blueprint["architect_plan_id"] == ids["plan_id"]
    assert blueprint["linked_obs_count"] == 1
    assert blueprint["linked_interp_count"] == 1
    assert blueprint["section_count"] == 1


def test_architect_blueprint_detail_preserves_authorized_objects(tmp_path):
    db_path, ids = _seed_architect_explorer_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(f"/api/architect/blueprints/{ids['bp_id']}")

    assert response.status_code == 200
    detail = response.get_json()
    assert detail["id"] == ids["bp_id"]
    assert detail["section_count"] == 1
    assert detail["architect_plan"]["id"] == ids["plan_id"]
    assert detail["architect_plan"]["paragraph_count"] == 1

    section = detail["sections"][0]
    assert section["supporting_observations"] == [ids["obs_id"]]
    assert section["supporting_interpretations"] == [ids["interp_id"]]
    assert section["obs_texts"][ids["obs_id"]]["text"] == "Evidence remains fixed."
    assert section["interp_texts"][ids["interp_id"]]["text"] == (
        "The phrase encodes an epistemological claim."
    )

    paragraph = detail["architect_plan"]["paragraphs"][0]
    assert paragraph["required_observations"] == [ids["obs_id"]]
    assert paragraph["required_interpretations"] == [ids["interp_id"]]
    assert paragraph["required_terms"] == [
        {"term": "evidence remains fixed", "priority": "critical"},
        {"term": "evidence remains", "priority": "critical"},
        {"term": "remains fixed", "priority": "critical"},
    ]


def test_architect_explorer_is_read_only(tmp_path):
    db_path, ids = _seed_architect_explorer_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    responses = [
        client.get("/api/architect/blueprints"),
        client.get(f"/api/architect/blueprints/{ids['bp_id']}"),
    ]

    assert [response.status_code for response in responses] == [200, 200]
    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts


def test_architect_explorer_rejects_unknown_blueprint(tmp_path):
    db_path, _ = _seed_architect_explorer_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(f"/api/architect/blueprints/{'0' * 64}")

    assert response.status_code == 404
    assert response.get_json()["error"] == "blueprint not found"
