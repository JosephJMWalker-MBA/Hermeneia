"""Promoted regressions for #230: a Critic run records its complete Finding ledger or reports failure.

ADR-0042 Completeness: every obligation in scope produces exactly one Finding,
so the full ledger is computable for any narrative. A run-critic request
whose Evaluation Functions fail must not report a created evaluation with an
incomplete ledger, and a retry (including over a report left without its
ledger) completes the missing Findings; Finding IDs are deterministic, so
re-evaluation is idempotent (ADR-0041). Commit 9e71daa preserves the
negative versions; the repair demonstrated strict unexpected passes before the
expected failures were removed. Synthetic PDF; offline `null` Artist.
"""
from __future__ import annotations

import io
import sqlite3

import fitz
import pytest

from hermeneia.compiler.critic import run_critic
from hermeneia.compiler.evaluation_functions import runner
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


class IncompleteFindingLedger(AssertionError):
    """Only the observed incomplete-ledger failures are expected here."""


@pytest.fixture
def narrative(tmp_path):
    db = tmp_path / "ws" / "workspace.db"
    SQLiteStore(db).close()
    client = create_app(db_path=db).test_client()
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "The lamp burned all night. Nobody asked why it burned.")
    client.post("/api/upload", data={"file": (io.BytesIO(doc.tobytes()), "s.pdf")}, content_type="multipart/form-data")
    obs = [r[0] for r in sqlite3.connect(db).execute("SELECT id FROM observations")]
    plan = client.post("/api/pipeline/ratify-blueprint", json={"candidate": {
        "title": "Lamp", "thesis": "The lamp signals unrest.",
        "sections": [{"claim": "The lamp burns all night.", "supporting_observations": obs}]}}).get_json()["plan_id"]
    slug = client.get("/api/profiles").get_json()["profiles"][0]["slug"]
    nid = client.post("/api/pipeline/run-artist",
                      json={"plan_id": plan, "provider": "null", "profile": slug}).get_json()["id"]
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    expected = {f["id"] for f in runner.run_all_evaluation_functions(nid, plan, conn).all_findings}
    conn.close()
    assert expected
    return db, client, nid, expected


def _finding_ids(db, nid) -> set[str]:
    return {r[0] for r in sqlite3.connect(db).execute(
        "SELECT id FROM findings WHERE rendered_narrative_id = ?", (nid,))}


def _critic(client, nid):
    return client.post("/api/pipeline/run-critic", json={"narrative_id": nid})


def test_transient_runner_failure_is_reported_and_retry_completes_the_ledger(narrative, monkeypatch):
    db, client, nid, expected = narrative
    with monkeypatch.context() as patch:
        patch.setattr(runner, "run_all_evaluation_functions",
                      lambda *_a, **_k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        failed = _critic(client, nid)
    retry = _critic(client, nid)
    if failed.status_code < 400 or retry.status_code >= 400 or _finding_ids(db, nid) != expected:
        raise IncompleteFindingLedger(
            f"failed={failed.status_code} {failed.get_json().get('status')} retry={retry.status_code} "
            f"findings={len(_finding_ids(db, nid))}/{len(expected)}")


def test_failing_evaluation_function_is_reported_and_retry_completes_the_ledger(narrative, monkeypatch):
    db, client, nid, expected = narrative
    real_load = runner._load_efs

    def provenance_fails():
        def broken(*_args):
            raise sqlite3.OperationalError("database is locked")
        return [(dimension, broken if dimension == "provenance" else ef) for dimension, ef in real_load()]

    with monkeypatch.context() as patch:
        patch.setattr(runner, "_load_efs", provenance_fails)
        failed = _critic(client, nid)
    retry = _critic(client, nid)
    if failed.status_code < 400 or retry.status_code >= 400 or _finding_ids(db, nid) != expected:
        raise IncompleteFindingLedger(
            f"failed={failed.status_code} {failed.get_json().get('status')} retry={retry.status_code} "
            f"findings={len(_finding_ids(db, nid))}/{len(expected)}")


def test_retry_completes_the_ledger_of_a_report_left_without_findings(narrative):
    db, client, nid, expected = narrative
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    report = run_critic(0, [], conn, narrative_id=nid)
    conn.execute(
        "INSERT INTO validation_reports (id, rendered_narrative_id, architect_plan_id, semantic_fidelity, "
        "required_terms_present, required_terms_missing, approved, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (report["id"], report["rendered_narrative_id"], report["architect_plan_id"], report["semantic_fidelity"],
         report["required_terms_present"], report["required_terms_missing"], int(report.get("approved", False)),
         report["created_at"]))
    conn.commit()
    conn.close()
    retry = _critic(client, nid)
    assert retry.get_json().get("status") == "already_exists", retry.get_json()
    if _finding_ids(db, nid) != expected:
        raise IncompleteFindingLedger(f"findings={len(_finding_ids(db, nid))}/{len(expected)}")


def test_successful_run_records_report_and_complete_ledger(narrative):
    db, client, nid, expected = narrative
    first, second = _critic(client, nid), _critic(client, nid)
    assert (first.status_code, first.get_json()["status"]) == (201, "created")
    assert first.get_json()["report"]["total_findings"] == len(expected)
    assert (second.status_code, second.get_json()["status"]) == (200, "already_exists")
    assert _finding_ids(db, nid) == expected
