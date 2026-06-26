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


def _seed_trust_db(
    tmp_path: Path,
    *,
    report_overrides: dict | None = None,
) -> tuple[Path, dict]:
    db_path = tmp_path / "trust.db"
    store = SQLiteStore(db_path)
    overrides = {"semantic_fidelity": 100.0, **(report_overrides or {})}
    ids = _seed_full_chain(store, report_overrides=overrides)
    store.close()
    return db_path, ids


def test_trust_summary_reports_authoritative_passes(tmp_path):
    db_path, ids = _seed_trust_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(
        f"/api/trust/rendered_narrative/{ids['narrative_id']}"
    )

    assert response.status_code == 200
    summary = response.get_json()
    assert summary["rendered_narrative_id"] == ids["narrative_id"]
    assert {
        key: finding["status"]
        for key, finding in summary["checks"].items()
    } == {
        "evidence_preserved": "pass",
        "lineage_complete": "pass",
        "constitutional_profile_recorded": "pass",
        "semantic_contract_satisfied": "pass",
        "critic_approved": "pass",
    }

    profile = summary["checks"]["constitutional_profile_recorded"]["evidence"][
        "constitutional_profile"
    ]
    assert profile["constitution_version"] == "1.0.0"
    assert summary["checks"]["semantic_contract_satisfied"]["evidence"][
        "validation_report_id"
    ] == ids["report_id"]


def test_trust_summary_keeps_contract_satisfaction_distinct_from_critic_approval(tmp_path):
    db_path, ids = _seed_trust_db(
        tmp_path,
        report_overrides={
            "semantic_fidelity": 80.0,
            "required_terms_missing": json.dumps(["recommended-term"]),
            "approved": 1,
        },
    )

    summary = create_app(db_path=db_path).test_client().get(
        f"/api/trust/rendered_narrative/{ids['narrative_id']}"
    ).get_json()

    assert summary["checks"]["semantic_contract_satisfied"]["status"] == "fail"
    assert summary["checks"]["critic_approved"]["status"] == "pass"


def test_trust_summary_is_read_only(tmp_path):
    db_path, ids = _seed_trust_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    response = client.get(
        f"/api/trust/rendered_narrative/{ids['narrative_id']}"
    )

    assert response.status_code == 200
    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts


def test_trust_summary_ui_renders_backend_findings_without_recomputing_them():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "/api/trust/rendered_narrative/" in index_html
    for key in (
        "evidence_preserved",
        "lineage_complete",
        "constitutional_profile_recorded",
        "semantic_contract_satisfied",
        "critic_approved",
    ):
        assert key in index_html
    assert "finding?.status" in index_html
