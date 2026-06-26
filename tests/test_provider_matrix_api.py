from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.hashing import (
    make_rendered_narrative_id,
    make_validation_report_id,
    sha256_file,
)
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


def _add_render(
    store: SQLiteStore,
    ids: dict,
    *,
    provider_identity: str,
    provider_id: str,
    model_id: str,
    fidelity: float | None,
    approved: bool = False,
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    narrative_id = make_rendered_narrative_id(
        ids["plan_id"],
        provider_identity,
        ids["profile_id"],
    )
    store.insert_rendered_narrative({
        "id": narrative_id,
        "architect_plan_id": ids["plan_id"],
        "provider": provider_identity,
        "expression_profile_id": ids["profile_id"],
        "text": f"Rendered by {provider_identity}.",
        "prompt_used": "Shared ArchitectPlan prompt.",
        "execution_config": json.dumps({
            "provider": provider_id,
            "model_id": model_id,
            "sdk_version": "test",
            "request_schema_version": "1",
            "constitutional_profile": {
                "constitution_version": "1.0.0",
                "authority_index_version": "1.0.0",
                "invariant_profile": "CI-001..CI-016",
                "architecture_profile": "v1.0",
            },
        }),
        "created_at": now,
    })
    if fidelity is not None:
        store.insert_validation_report({
            "id": make_validation_report_id(narrative_id),
            "rendered_narrative_id": narrative_id,
            "architect_plan_id": ids["plan_id"],
            "expression_profile_id": ids["profile_id"],
            "semantic_fidelity": fidelity,
            "required_terms_present": "[]",
            "required_terms_missing": "[]",
            "unsupported_claims": "[]",
            "omitted_observations": "[]",
            "omitted_interpretations": "[]",
            "semantic_drift": "[]",
            "warnings": "[]",
            "approved": int(approved),
            "created_at": now,
        })
    return narrative_id


def _seed_provider_matrix_db(tmp_path: Path) -> tuple[Path, dict]:
    db_path = tmp_path / "provider-matrix.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(
        store,
        report_overrides={"semantic_fidelity": 100.0},
    )
    ids["openai_narrative_id"] = _add_render(
        store,
        ids,
        provider_identity="openai/model-a",
        provider_id="openai",
        model_id="model-a",
        fidelity=92.0,
        approved=True,
    )
    ids["legacy_narrative_id"] = _add_render(
        store,
        ids,
        provider_identity="legacy/model-z",
        provider_id="legacy",
        model_id="model-z",
        fidelity=None,
    )
    store.close()
    return db_path, ids


def test_provider_matrix_preserves_every_realization_without_ranking(tmp_path):
    db_path, ids = _seed_provider_matrix_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(
        f"/api/provider-matrix/{ids['plan_id']}/literary-en"
    )

    assert response.status_code == 200
    matrix = response.get_json()
    assert matrix["architect_plan"]["id"] == ids["plan_id"]
    assert matrix["expression_profile"]["id"] == ids["profile_id"]
    assert len(matrix["executions"]) == 3

    by_identity = {
        execution["rendered_narrative"]["provider_identity"]: execution
        for execution in matrix["executions"]
    }
    assert set(by_identity) == {
        "legacy/model-z",
        "null",
        "openai/model-a",
    }
    assert by_identity["openai/model-a"]["provider"] == {
        "id": "openai",
        "display_name": "OpenAI",
        "registered": True,
        "model_id": "model-a",
    }
    assert by_identity["legacy/model-z"]["provider"]["registered"] is False
    assert by_identity["legacy/model-z"]["validation_report"] is None
    assert by_identity["openai/model-a"]["validation_report"]["approved"] is True

    serialized = json.dumps(matrix).lower()
    assert '"rank"' not in serialized
    assert '"winner"' not in serialized
    assert '"quality"' not in serialized
    assert '"phenotype"' not in serialized


def test_provider_matrix_surfaces_are_bound_to_each_narrative(tmp_path):
    db_path, ids = _seed_provider_matrix_db(tmp_path)
    matrix = create_app(db_path=db_path).test_client().get(
        f"/api/provider-matrix/{ids['plan_id']}/literary-en"
    ).get_json()

    for execution in matrix["executions"]:
        narrative_id = execution["rendered_narrative"]["id"]
        surfaces = execution["surfaces"]
        assert surfaces["trust"].endswith(narrative_id)
        assert surfaces["lineage"].endswith(narrative_id)
        assert f"narrative={narrative_id}" in surfaces["semantic_contract"]


def test_fidelity_api_can_select_one_provider_realization(tmp_path):
    db_path, ids = _seed_provider_matrix_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(
        f"/api/fidelity/{ids['bp_id']}/literary-en"
        f"?narrative={ids['openai_narrative_id']}"
    )

    assert response.status_code == 200
    audit = response.get_json()
    assert audit["rendered_narrative"]["id"] == ids["openai_narrative_id"]
    assert audit["rendered_narrative"]["provider"] == "openai/model-a"
    assert audit["validation_report"]["semantic_fidelity"] == 92.0


def test_provider_matrix_and_selected_fidelity_are_read_only(tmp_path):
    db_path, ids = _seed_provider_matrix_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    assert client.get(
        f"/api/provider-matrix/{ids['plan_id']}/literary-en"
    ).status_code == 200
    assert client.get(
        f"/api/fidelity/{ids['bp_id']}/literary-en"
        f"?narrative={ids['openai_narrative_id']}"
    ).status_code == 200

    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts


def test_expression_matrix_reports_counts_without_collapsing_provider_results(tmp_path):
    db_path, ids = _seed_provider_matrix_db(tmp_path)
    matrix = create_app(db_path=db_path).test_client().get("/api/matrix").get_json()
    blueprint = next(
        item for item in matrix["blueprints"]
        if item["id"] == ids["bp_id"]
    )
    cell = blueprint["cells"]["literary-en"]

    assert cell == {
        "rendered": True,
        "render_count": 3,
        "reviewed_count": 2,
        "approved_count": 2,
    }
    assert "approved" not in cell
    assert "fidelity" not in cell


def test_provider_matrix_ui_uses_neutral_render_counts():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "/api/provider-matrix/" in index_html
    assert "Number of Artist realizations" in index_html
    assert "historical adapter not currently registered" in index_html
    assert "data-provider-matrix" in index_html
