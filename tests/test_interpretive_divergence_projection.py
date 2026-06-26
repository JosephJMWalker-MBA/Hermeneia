from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.hashing import (
    make_interpretation_id,
    make_perspective_id,
    sha256_file,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _schema(db_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT type, name
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    conn.close()
    return rows


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


def _seed_divergence_db(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    db_path = tmp_path / "divergence.db"
    store = SQLiteStore(db_path)
    now = datetime.now(timezone.utc).isoformat()
    document_id = "d" * 64
    extraction_id = "e" * 64
    observation_a_id = "a" * 64
    observation_b_id = "b" * 64

    store.insert_source_document({
        "id": document_id,
        "original_filename": "gatsby.pdf",
        "file_hash": document_id,
        "total_pages": 1,
        "registered_at": now,
        "compiler_version": "test",
    })
    store.insert_source_extractions_batch([{
        "id": extraction_id,
        "epistemic_class": "Evidence",
        "document_id": document_id,
        "page": 1,
        "region": "page:1",
        "raw_text": "Gatsby was exempt. Gatsby had an extraordinary gift for hope.",
        "parser": "test",
        "parser_version": "1",
        "coordinates": "{}",
        "source_locator": "page:1",
        "source_hash": document_id,
        "hash": extraction_id,
        "extracted_at": now,
    }])
    store.insert_observations_batch([
        {
            "id": observation_a_id,
            "source_document_id": document_id,
            "source_extraction_id": extraction_id,
            "raw_text": "Only Gatsby was exempt from my reaction.",
            "source_locator": "page:1:paragraph:1:sentence:1",
            "page": 1,
            "paragraph": 1,
            "sentence": 1,
            "preceding_observation_id": None,
            "following_observation_id": None,
            "created_at": now,
        },
        {
            "id": observation_b_id,
            "source_document_id": document_id,
            "source_extraction_id": extraction_id,
            "raw_text": "He had an extraordinary gift for hope.",
            "source_locator": "page:1:paragraph:1:sentence:2",
            "page": 1,
            "paragraph": 1,
            "sentence": 2,
            "preceding_observation_id": None,
            "following_observation_id": None,
            "created_at": now,
        },
    ])

    literary_id = make_perspective_id("Literary")
    social_id = make_perspective_id("Social")
    store.register_perspective({
        "id": literary_id,
        "name": "Literary",
        "description": "Attends to rhetorical and symbolic structure.",
        "created_at": now,
    })
    store.register_perspective({
        "id": social_id,
        "name": "Social",
        "description": "Attends to social roles and exceptions.",
        "created_at": now,
    })

    shared_text = "Gatsby is treated as an exception."
    distinct_text = "Gatsby's hope creates an aesthetic exception."
    interpretation_a_id = make_interpretation_id(
        observation_a_id, "Literary", shared_text
    )
    interpretation_same_id = make_interpretation_id(
        observation_a_id, "Social", shared_text
    )
    interpretation_b_id = make_interpretation_id(
        observation_b_id, "Social", distinct_text
    )

    for row in (
        {
            "id": interpretation_a_id,
            "observation_id": observation_a_id,
            "perspective": "Literary",
            "perspective_id": literary_id,
            "text": shared_text,
            "evidential_status": "established",
            "evidence_observation_ids": json.dumps([observation_a_id]),
        },
        {
            "id": interpretation_same_id,
            "observation_id": observation_a_id,
            "perspective": "Social",
            "perspective_id": social_id,
            "text": shared_text,
            "evidential_status": "established",
            "evidence_observation_ids": json.dumps([observation_a_id]),
        },
        {
            "id": interpretation_b_id,
            "observation_id": observation_b_id,
            "perspective": "Social",
            "perspective_id": social_id,
            "text": distinct_text,
            "evidential_status": "speculative",
            "evidence_observation_ids": json.dumps([observation_b_id]),
        },
    ):
        store.insert_interpretation({
            **row,
            "confidence": "human",
            "source": "steward-authored",
            "created_at": now,
        })
    store.close()

    return db_path, {
        "interpretation_a": interpretation_a_id,
        "interpretation_same": interpretation_same_id,
        "interpretation_b": interpretation_b_id,
        "observation_a": observation_a_id,
        "observation_b": observation_b_id,
    }


def test_identical_interpretation_claims_produce_minimal_divergence(tmp_path):
    db_path, ids = _seed_divergence_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(
        "/api/divergence/interpretations/"
        f"{ids['interpretation_a']}/{ids['interpretation_a']}"
    )

    assert response.status_code == 200
    projection = response.get_json()
    assert len(projection["shared_claims"]) == 1
    assert projection["distinct_claims"] == {
        "interpretation_a": [],
        "interpretation_b": [],
    }
    assert projection["evidence_differences"]["only_interpretation_a"] == []
    assert projection["evidence_differences"]["only_interpretation_b"] == []
    assert projection["contradictory_claims"]["status"] == "not_computed"
    assert projection["expressive_divergence"]["status"] == "not_evaluated"
    assert projection["interpretive_summary"]["what_changed"] == []
    assert projection["interpretive_summary"]["why_it_changed"] == []


def test_distinct_interpretations_produce_detectable_divergence(tmp_path):
    db_path, ids = _seed_divergence_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(
        "/api/divergence/interpretations/"
        f"{ids['interpretation_a']}/{ids['interpretation_b']}"
    )

    assert response.status_code == 200
    projection = response.get_json()
    assert projection["shared_claims"] == []
    assert len(projection["distinct_claims"]["interpretation_a"]) == 1
    assert len(projection["distinct_claims"]["interpretation_b"]) == 1
    assert {
        row["id"]
        for row in projection["evidence_differences"]["only_interpretation_a"]
    } == {ids["observation_a"]}
    assert {
        row["id"]
        for row in projection["evidence_differences"]["only_interpretation_b"]
    } == {ids["observation_b"]}
    assert "The claims use different Perspectives." in (
        projection["interpretive_summary"]["what_changed"]
    )
    assert "The supporting Observation sets differ." in (
        projection["interpretive_summary"]["what_changed"]
    )


def test_projection_regenerates_without_persistence_or_schema_changes(tmp_path):
    db_path, ids = _seed_divergence_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    url = (
        "/api/divergence/interpretations/"
        f"{ids['interpretation_a']}/{ids['interpretation_b']}"
    )
    before_hash = sha256_file(db_path)
    before_schema = _schema(db_path)
    before_counts = _table_counts(db_path)

    first = client.get(url)
    second = client.get(url)

    assert first.status_code == second.status_code == 200
    assert first.get_json() == second.get_json()
    assert first.get_json()["persistence"] == "none"
    assert first.get_json()["regeneration"]["persisted"] is False
    assert sha256_file(db_path) == before_hash
    assert _schema(db_path) == before_schema
    assert _table_counts(db_path) == before_counts


def test_projection_rejects_missing_interpretation(tmp_path):
    db_path, ids = _seed_divergence_db(tmp_path)
    response = create_app(db_path=db_path).test_client().get(
        "/api/divergence/interpretations/"
        f"{ids['interpretation_a']}/{'0' * 64}"
    )

    assert response.status_code == 404
    assert response.get_json()["error"].startswith("interpretation missing:")
