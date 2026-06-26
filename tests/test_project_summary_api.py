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


def _seed_project_summary_db(tmp_path: Path) -> tuple[Path, dict]:
    db_path = tmp_path / "project_summary.db"
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


def test_project_summary_exposes_goal_document_and_status_counts(tmp_path):
    db_path, ids = _seed_project_summary_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get("/api/project/summary")

    assert response.status_code == 200
    summary = response.get_json()
    assert summary["blueprint_title"] == "Test Blueprint"
    assert summary["thesis"] == "Evidence is fixed."
    assert summary["project_goal"] == {
        "label": "Research Question",
        "text": "Evidence is fixed.",
        "source": "latest_narrative_blueprint",
    }
    assert summary["document"]["filename"] == "evidence.pdf"
    assert summary["document"]["source_document_id"] == ids["doc_id"]
    assert summary["counts"]["observations"] == 1
    assert summary["counts"]["interpretations"] == 1
    assert summary["counts"]["blueprints"] == 1
    assert summary["counts"]["architect_plans"] == 1
    assert summary["counts"]["narratives"] == 1
    assert summary["counts"]["audits"] == 1
    assert summary["counts"]["critic_reports"] == 0
    assert summary["counts"]["findings"] == 0


def test_project_summary_pipeline_uses_existing_surfaces(tmp_path):
    db_path, _ = _seed_project_summary_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    pipeline = client.get("/api/project/summary").get_json()["pipeline"]

    assert [stage["key"] for stage in pipeline] == [
        "observations",
        "interpretations",
        "blueprints",
        "architect_plans",
        "narratives",
        "audits",
    ]
    assert [stage["count"] for stage in pipeline] == [1, 1, 1, 1, 1, 1]
    assert pipeline[0]["surface"] == "/api/e10/observations"
    assert pipeline[2]["surface"] == "/api/architect/blueprints"
    assert pipeline[4]["surface"] == "/api/reader/narratives"
    assert pipeline[5]["surface"] == "/api/critic/reports"


def test_project_summary_is_read_only(tmp_path):
    db_path, _ = _seed_project_summary_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    first = client.get("/api/project/summary")
    second = client.get("/api/project/summary")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == second.get_json()
    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts


def test_project_summary_ui_presents_project_goal_language():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "/api/project/summary" in index_html
    assert "Project Goal" in index_html
    assert "research-question-banner" in index_html
