"""
Tests for the Evaluation Function Runner and full-Critic endpoint.

Proves:
- run_all_evaluation_functions returns a RunResult with one EFResult per registered EF
- Each EFResult has a dimension matching the EF's declared dimension
- All findings are accumulated in RunResult.all_findings
- A failing EF captures its error without blocking others
- dimensions filter selects a subset of EFs
- POST /api/pipeline/run-critic now returns total_findings and findings_by_dimension
- Findings from all dimensions are stored in the DB after a Critic run
- Second Critic run is idempotent (ValidationReport already exists → "already_exists")
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hermeneia.compiler.evaluation_functions.runner import (
    RunResult,
    run_all_evaluation_functions,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def seeded(tmp_path):
    db_path = tmp_path / "runner.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store, include_narrative=True, include_report=False)
    store.close()
    return db_path, ids


@pytest.fixture
def client(seeded):
    db_path, ids = seeded
    app = create_app(db_path=db_path)
    return app.test_client(), ids, db_path


# ── RunResult dataclass ────────────────────────────────────────────────────────

def test_run_result_all_findings_flat(seeded):
    db_path, ids = seeded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    result = run_all_evaluation_functions(ids["narrative_id"], ids["plan_id"], conn)
    conn.close()

    assert isinstance(result, RunResult)
    assert result.rendered_narrative_id == ids["narrative_id"]
    assert result.architect_plan_id == ids["plan_id"]
    all_f = result.all_findings
    assert isinstance(all_f, list)
    assert len(all_f) == result.total_findings


def test_run_result_covers_all_registered_dimensions(seeded):
    db_path, ids = seeded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    result = run_all_evaluation_functions(ids["narrative_id"], ids["plan_id"], conn)
    conn.close()

    dimensions = {r.dimension for r in result.ef_results}
    expected = {"structural", "semantic", "provenance",
                "observation_coverage", "accessibility", "constitutional"}
    assert expected == dimensions


def test_run_result_each_ef_result_has_dimension(seeded):
    db_path, ids = seeded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    result = run_all_evaluation_functions(ids["narrative_id"], ids["plan_id"], conn)
    conn.close()

    for ef in result.ef_results:
        assert ef.dimension, "EFResult must have a non-empty dimension"


def test_run_result_findings_by_dimension(seeded):
    db_path, ids = seeded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    result = run_all_evaluation_functions(ids["narrative_id"], ids["plan_id"], conn)
    conn.close()

    fbd = result.findings_by_dimension
    assert isinstance(fbd, dict)
    for dim, findings in fbd.items():
        assert isinstance(findings, list)


def test_dimensions_filter(seeded):
    db_path, ids = seeded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    result = run_all_evaluation_functions(
        ids["narrative_id"], ids["plan_id"], conn,
        dimensions=["structural", "semantic"],
    )
    conn.close()

    dims = {r.dimension for r in result.ef_results}
    assert dims == {"structural", "semantic"}


def test_ef_error_does_not_block_others(seeded, monkeypatch):
    """If one EF raises, others still run and the error is captured."""
    db_path, ids = seeded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    from hermeneia.compiler.evaluation_functions import structural
    original = structural.evaluate_structural

    def _boom(narrative_id, plan_id, c):
        raise RuntimeError("simulated EF failure")

    monkeypatch.setattr(structural, "evaluate_structural", _boom)

    result = run_all_evaluation_functions(ids["narrative_id"], ids["plan_id"], conn)
    conn.close()

    dims = {r.dimension for r in result.ef_results}
    assert "structural" in dims
    structural_result = next(r for r in result.ef_results if r.dimension == "structural")
    assert structural_result.error is not None
    assert "simulated EF failure" in structural_result.error

    # Other dimensions still ran
    other_dims = dims - {"structural"}
    assert len(other_dims) > 0


def test_errors_property_only_captures_failures(seeded, monkeypatch):
    db_path, ids = seeded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    from hermeneia.compiler.evaluation_functions import structural

    def _boom(narrative_id, plan_id, c):
        raise RuntimeError("boom")

    monkeypatch.setattr(structural, "evaluate_structural", _boom)

    result = run_all_evaluation_functions(ids["narrative_id"], ids["plan_id"], conn)
    conn.close()

    assert "structural" in result.errors
    assert len(result.errors) == 1  # only structural failed


# ── POST /api/pipeline/run-critic full-EF response ───────────────────────────

def test_critic_endpoint_returns_findings_by_dimension(client):
    c, ids, db_path = client

    resp = c.post("/api/pipeline/run-critic", json={"narrative_id": ids["narrative_id"]})

    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "created"
    report = data["report"]
    assert "total_findings" in report
    assert "findings_by_dimension" in report
    assert isinstance(report["findings_by_dimension"], dict)
    assert report["total_findings"] >= 0


def test_critic_endpoint_findings_stored_in_db(client):
    c, ids, db_path = client

    c.post("/api/pipeline/run-critic", json={"narrative_id": ids["narrative_id"]})

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    conn.close()
    assert count > 0


def test_critic_endpoint_idempotent(client):
    c, ids, _ = client

    r1 = c.post("/api/pipeline/run-critic", json={"narrative_id": ids["narrative_id"]})
    r2 = c.post("/api/pipeline/run-critic", json={"narrative_id": ids["narrative_id"]})

    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r2.get_json()["status"] == "already_exists"


def test_critic_endpoint_findings_per_dimension_are_counts(client):
    c, ids, _ = client

    resp = c.post("/api/pipeline/run-critic", json={"narrative_id": ids["narrative_id"]})

    report = resp.get_json()["report"]
    for dim, count in report["findings_by_dimension"].items():
        assert isinstance(count, int), f"Dimension {dim} count should be int, got {type(count)}"
        assert count >= 0
