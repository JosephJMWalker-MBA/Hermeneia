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


def _seed_reader_db(tmp_path: Path) -> tuple[Path, dict]:
    db_path = tmp_path / "reader.db"
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


def test_reader_narratives_lists_rendered_reports(tmp_path):
    db_path, ids = _seed_reader_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get("/api/reader/narratives")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    narrative = payload["narratives"][0]
    assert narrative["id"] == ids["narrative_id"]
    assert narrative["provider"] == "null"
    assert narrative["profile"]["slug"] == "literary-en"
    assert narrative["blueprint"]["id"] == ids["bp_id"]
    assert narrative["architect_plan"]["id"] == ids["plan_id"]
    assert narrative["validation_report"]["id"] == ids["report_id"]
    assert narrative["validation_report"]["semantic_fidelity"] == 100.0


def test_reader_narrative_detail_returns_readable_artifact_and_surfaces(tmp_path):
    db_path, ids = _seed_reader_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(f"/api/reader/narratives/{ids['narrative_id']}")

    assert response.status_code == 200
    detail = response.get_json()
    assert detail["rendered_narrative"]["id"] == ids["narrative_id"]
    assert detail["rendered_narrative"]["text"] == "Evidence remains fixed."
    assert detail["profile"]["slug"] == "literary-en"
    assert detail["blueprint"]["title"] == "Test Blueprint"
    assert detail["blueprint"]["thesis"] == "Evidence is fixed."
    assert detail["architect_plan"]["id"] == ids["plan_id"]
    assert detail["validation_report"]["id"] == ids["report_id"]
    assert detail["validation_report"]["approved"] is True
    assert detail["validation_report"]["semantic_fidelity"] == 100.0
    assert detail["surfaces"] == {
        "copy_source": "rendered_narrative.text",
        "trust": f"/api/trust/rendered_narrative/{ids['narrative_id']}",
        "lineage": f"/api/lineage/rendered_narrative/{ids['narrative_id']}",
        "semantic_contract": (
            f"/api/fidelity/{ids['bp_id']}/literary-en"
            f"?narrative={ids['narrative_id']}"
        ),
    }


def test_reader_view_is_read_only(tmp_path):
    db_path, ids = _seed_reader_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    responses = [
        client.get("/api/reader/narratives"),
        client.get(f"/api/reader/narratives/{ids['narrative_id']}"),
    ]

    assert [response.status_code for response in responses] == [200, 200]
    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts


def test_reader_view_rejects_unknown_narrative(tmp_path):
    db_path, _ = _seed_reader_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(f"/api/reader/narratives/{'0' * 64}")

    assert response.status_code == 404
    assert response.get_json()["error"] == "rendered narrative not found"


def test_reader_ui_exposes_dedicated_reader_surface():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "/api/reader/narratives" in index_html
    assert "reader-panel" in index_html
    assert "Read Report" in index_html
    assert "copyReaderText" in index_html
