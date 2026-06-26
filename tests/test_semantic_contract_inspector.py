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


def _seed_contract_db(
    tmp_path: Path,
    *,
    include_report: bool = True,
    report_overrides: dict | None = None,
) -> tuple[Path, dict]:
    db_path = tmp_path / "contract.db"
    store = SQLiteStore(db_path)
    overrides = {
        "semantic_fidelity": 50.0,
        "required_terms_present": json.dumps(["evidence remains"]),
        "required_terms_missing": json.dumps(["remains fixed"]),
        "approved": 0,
        **(report_overrides or {}),
    }
    ids = _seed_full_chain(
        store,
        architect_terms=["evidence", "fixed"],
        include_report=include_report,
        report_overrides=overrides,
    )
    store.close()
    return db_path, ids


def test_semantic_contract_api_returns_atomic_authoritative_statuses(tmp_path):
    db_path, ids = _seed_contract_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get("/api/fidelity/" + ids["bp_id"] + "/literary-en")

    assert response.status_code == 200
    audit = response.get_json()
    obligations = audit["obligations"]

    term_statuses = {
        item["obligation"]: item["status"]
        for item in obligations
        if item["kind"] == "required_term"
    }
    assert term_statuses == {
        "evidence remains fixed": "not_evaluated",
        "evidence remains": "satisfied",
        "remains fixed": "missing",
    }

    unevaluated_kinds = {
        item["kind"]
        for item in obligations
        if item["status"] == "not_evaluated"
    }
    assert {
        "purpose",
        "required_observation",
        "required_interpretation",
    } <= unevaluated_kinds
    assert "partial" not in json.dumps(audit).lower()

    assert audit["obligation_summary"] == {
        "total": 6,
        "satisfied": 1,
        "missing": 1,
        "violations": 0,
        "not_evaluated": 4,
    }


def test_semantic_contract_api_marks_all_obligations_not_evaluated_without_critic(tmp_path):
    db_path, ids = _seed_contract_db(tmp_path, include_report=False)

    audit = create_app(db_path=db_path).test_client().get(
        "/api/fidelity/" + ids["bp_id"] + "/literary-en"
    ).get_json()

    assert audit["validation_report"] is None
    assert audit["obligation_summary"]["not_evaluated"] == 6
    assert {
        item["status"]
        for item in audit["obligations"]
    } == {"not_evaluated"}


def test_semantic_contract_api_is_read_only(tmp_path):
    db_path, ids = _seed_contract_db(tmp_path)
    client = create_app(db_path=db_path).test_client()
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    response = client.get("/api/fidelity/" + ids["bp_id"] + "/literary-en")

    assert response.status_code == 200
    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts


def test_semantic_contract_inspector_and_trust_explanation_are_presentation_only():
    root = Path(__file__).parent.parent
    index_html = (root / "hermeneia" / "web" / "static" / "index.html").read_text()
    inspector_html = (
        root / "hermeneia" / "web" / "static" / "fidelity.html"
    ).read_text()

    assert "No confidence score is inferred from model identity." in index_html
    assert "Constitutional Invariants" in index_html
    assert "Semantic Contract" in index_html
    assert "Critic Evaluation" in index_html
    assert "Provenance Chain" in index_html
    assert "item.status" in inspector_html
    assert "prohibited_claim_detected" in inspector_html
    assert "Not evaluated" in inspector_html
    assert "Partial" not in inspector_html
