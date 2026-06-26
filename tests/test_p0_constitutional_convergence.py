from __future__ import annotations

import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.storage.hashing import (
    make_observation_id,
    make_rendered_narrative_id,
    make_semantic_hash,
    make_source_extraction_id,
    make_source_locator,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

from test_constitutional_p0 import GATSBY_PDF, _seed_full_chain


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


def _insert_orphan_first_observation(store: SQLiteStore) -> str:
    """Insert an observation that sorts before the seeded blueprint observation."""
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "0" * 64
    raw = "Orphan observation."
    extraction_locator = make_source_locator(0, 1)
    extraction_id = make_source_extraction_id(
        doc_id,
        extraction_locator,
        raw,
        "test-parser",
        "test",
    )
    obs_locator = make_source_locator(0, 1, 1)
    obs_id = make_observation_id(doc_id, obs_locator, raw)

    store.insert_source_document({
        "id": doc_id,
        "original_filename": "orphan.pdf",
        "file_hash": doc_id,
        "total_pages": 1,
        "registered_at": now,
        "compiler_version": "test",
    })
    store.insert_source_extractions_batch([{
        "id": extraction_id,
        "epistemic_class": "Evidence",
        "document_id": doc_id,
        "page": 0,
        "region": "block:1",
        "raw_text": raw,
        "parser": "test-parser",
        "parser_version": "test",
        "coordinates": "{}",
        "source_locator": extraction_locator,
        "source_hash": doc_id,
        "hash": extraction_id,
        "extracted_at": now,
    }])
    store.insert_observations_batch([{
        "id": obs_id,
        "epistemic_class": "Evidence",
        "source_document_id": doc_id,
        "source_extraction_id": extraction_id,
        "raw_text": raw,
        "source_locator": obs_locator,
        "semantic_hash": make_semantic_hash(raw),
        "page": 0,
        "paragraph": 1,
        "sentence": 1,
        "preceding_observation_id": None,
        "following_observation_id": None,
        "created_at": now,
    }])
    store.insert_provenance_batch([{
        "id": obs_id,
        "observation_id": obs_id,
        "source_document_id": doc_id,
        "source_extraction_id": extraction_id,
        "source_document_hash": doc_id,
        "page": 0,
        "paragraph": 1,
        "sentence": 1,
        "verbatim_text": raw,
        "location_precision": "sentence",
        "char_offset_start": None,
        "char_offset_end": None,
        "bbox_x": None,
        "bbox_y": None,
        "bbox_width": None,
        "bbox_height": None,
        "bbox_dpi": None,
        "created_at": now,
        "compiler_version": "test",
        "compilation_run_id": "test-run",
    }])
    return obs_id


def test_interpretations_are_immutable_and_review_patch_does_not_mutate(tmp_path):
    db_path = tmp_path / "p0.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    original = dict(store._conn.execute(
        "SELECT * FROM interpretations WHERE id = ?",
        (ids["interp_id"],),
    ).fetchone())

    with pytest.raises(sqlite3.IntegrityError, match="Interpretation immutable"):
        store._conn.execute(
            "UPDATE interpretations SET evidential_status = 'contested' WHERE id = ?",
            (ids["interp_id"],),
        )
    store._conn.rollback()

    with pytest.raises(sqlite3.IntegrityError, match="Interpretation immutable"):
        store._conn.execute(
            "DELETE FROM interpretations WHERE id = ?",
            (ids["interp_id"],),
        )
    store._conn.rollback()
    store.close()

    client = create_app(db_path=db_path).test_client()
    response = client.patch(
        f"/api/review/interpretations/{ids['interp_id']}",
        json={"evidential_status": "contested", "steward_note": "Do not mutate."},
    )
    assert response.status_code == 409

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    after = dict(conn.execute(
        "SELECT * FROM interpretations WHERE id = ?",
        (ids["interp_id"],),
    ).fetchone())
    conn.close()
    assert after == original


def test_historical_lineage_artifacts_are_append_only(tmp_path):
    store = SQLiteStore(tmp_path / "lineage.db")
    ids = _seed_full_chain(store)

    checks = [
        ("narrative_blueprints", "id", ids["bp_id"], "thesis", "NarrativeBlueprint immutable"),
        ("architect_plans", "id", ids["plan_id"], "title", "ArchitectPlan immutable"),
        (
            "architect_plan_paragraphs",
            "plan_id",
            ids["plan_id"],
            "purpose",
            "ArchitectPlanParagraph immutable",
        ),
        ("expression_profiles", "id", ids["profile_id"], "name", "ExpressionProfile immutable"),
        ("rendered_narratives", "id", ids["narrative_id"], "text", "RenderedNarrative immutable"),
        ("validation_reports", "id", ids["report_id"], "semantic_fidelity", "ValidationReport immutable"),
    ]

    for table, key, value, field, message in checks:
        with pytest.raises(sqlite3.IntegrityError, match=message):
            store._conn.execute(
                f"UPDATE {table} SET {field} = ? WHERE {key} = ?",
                ("mutated", value),
            )
        store._conn.rollback()

        with pytest.raises(sqlite3.IntegrityError, match=message):
            store._conn.execute(f"DELETE FROM {table} WHERE {key} = ?", (value,))
        store._conn.rollback()

    relation_checks = [
        (
            "blueprint_observation_links",
            "observation_id",
            "blueprint_id = ? AND observation_id = ?",
            (ids["bp_id"], ids["obs_id"]),
            "BlueprintObservationLink immutable",
        ),
        (
            "blueprint_interpretation_links",
            "interpretation_id",
            "blueprint_id = ? AND interpretation_id = ?",
            (ids["bp_id"], ids["interp_id"]),
            "BlueprintInterpretationLink immutable",
        ),
    ]
    for table, field, where_clause, params, message in relation_checks:
        with pytest.raises(sqlite3.IntegrityError, match=message):
            store._conn.execute(
                f"UPDATE {table} SET {field} = {field} WHERE {where_clause}",
                params,
            )
        store._conn.rollback()

        with pytest.raises(sqlite3.IntegrityError, match=message):
            store._conn.execute(f"DELETE FROM {table} WHERE {where_clause}", params)
        store._conn.rollback()

    store.close()


def test_pipeline_run_artist_uses_deterministic_identity_and_audit_config(tmp_path):
    db_path = tmp_path / "artist.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store, include_narrative=False, include_report=False)
    store.close()

    client = create_app(db_path=db_path).test_client()
    response = client.post(
        "/api/pipeline/run-artist",
        json={"obs_ref": "OBS-1", "provider": "null", "profile": "literary-en"},
    )
    assert response.status_code == 201
    body = response.get_json()
    expected_id = make_rendered_narrative_id(ids["plan_id"], "null", ids["profile_id"])
    assert body["id"] == expected_id
    assert body["provider"] == "null"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute(
        "SELECT * FROM rendered_narratives WHERE id = ?",
        (expected_id,),
    ).fetchone())
    assert row["provider"] == "null"
    execution_config = json.loads(row["execution_config"])
    assert execution_config["provider"] == "null"
    assert execution_config["constitutional_profile"]["invariant_profile"] == "CI-001..CI-016"

    second = client.post(
        "/api/pipeline/run-artist",
        json={"obs_ref": "OBS-1", "provider": "null", "profile": "literary-en"},
    )
    assert second.status_code == 200
    assert second.get_json()["status"] == "already_exists"
    count = conn.execute("SELECT COUNT(*) FROM rendered_narratives").fetchone()[0]
    conn.close()
    assert count == 1


def test_pipeline_run_critic_resolves_narrative_id_without_obs_placeholder(tmp_path):
    db_path = tmp_path / "critic.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store, include_report=False)
    _insert_orphan_first_observation(store)
    store.close()

    client = create_app(db_path=db_path).test_client()
    response = client.post(
        "/api/pipeline/run-critic",
        json={"narrative_id": ids["narrative_id"]},
    )
    assert response.status_code == 201

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute(
        "SELECT * FROM validation_reports WHERE rendered_narrative_id = ?",
        (ids["narrative_id"],),
    ).fetchone())
    conn.close()
    assert isinstance(json.loads(row["required_terms_missing"]), list)
    assert isinstance(json.loads(row["warnings"]), list)


@pytest.mark.skipif(not GATSBY_PDF.exists(), reason="gatsby.pdf not found")
def test_upload_returns_success_after_compile_and_retry_is_idempotent(tmp_path):
    db_path = tmp_path / "upload" / "hermeneia.db"
    client = create_app(db_path=db_path).test_client()
    payload = GATSBY_PDF.read_bytes()

    first = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(payload), "gatsby.pdf")},
        content_type="multipart/form-data",
    )
    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["status"] == "compiled"
    assert first_body["observation_count"] > 0
    assert first_body["term_count"] > 0
    counts_after_first = _table_counts(db_path)

    second = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(payload), "gatsby.pdf")},
        content_type="multipart/form-data",
    )
    assert second.status_code == 200
    assert _table_counts(db_path) == counts_after_first
