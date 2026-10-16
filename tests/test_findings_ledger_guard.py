"""ADR-0046 D-3: the Finding ledger write guard at its callers (the Critic route and the CLI) and at the store.

The store-level witnesses converted by this change are in tests/test_adr0042_provenance_absence.py. These tests cover
what the callers must keep: idempotent retries, legitimate partial-run recovery, all-or-nothing refusal (the Critic
report included), and explicit reporting of retained evaluator versions. Historical Findings are never changed.
"""
from __future__ import annotations

import sqlite3

import pytest

import synthetic_study_lab as lab
from adr0046_witness_state import Pair, connect, rows
from hermeneia.cli import critic_cmd
from hermeneia.storage.sqlite import FindingLedgerRefusal, SQLiteStore
from hermeneia.web.app import create_app


@pytest.fixture
def pair(tmp_path):
    with lab.isolated(tmp_path):
        yield Pair(tmp_path)


def _critic(pair: Pair, db):
    client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
    response = client.post("/api/pipeline/run-critic", json={"narrative_id": pair.narrative_id})
    return response.status_code, response.get_json()


def _reports(db) -> int:
    conn = connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM validation_reports").fetchone()[0]
    finally:
        conn.close()


def test_a_critic_retry_is_idempotent_and_says_so(pair):
    status, first = _critic(pair, pair.source)
    assert status == 201 and first["report"]["ledger"]["inserted"] == first["report"]["total_findings"] > 0
    stored = rows(pair.source, "findings")
    status, again = _critic(pair, pair.source)
    assert status == 200 and again["status"] == "already_exists"
    assert again["ledger"] == {"inserted": 0, "identical": len(stored), "retained": []}
    assert again["findings_completed"] == 0
    assert rows(pair.source, "findings") == stored


def test_a_partial_ledger_is_completed_by_a_retry(pair):
    """Legitimate recovery: a ledger left incomplete (older code, or a CLI run in which some EFs failed)."""
    stored = pair.critic(pair.source)[:2]
    pair.persist(pair.source, stored)
    status, body = _critic(pair, pair.source)
    assert status == 201
    ledger = body["report"]["ledger"]
    assert ledger["identical"] == 2 and ledger["retained"] == []
    assert ledger["inserted"] == body["report"]["total_findings"] - 2
    assert len(rows(pair.source, "findings")) == body["report"]["total_findings"]


def test_a_divergent_critic_run_is_refused_and_records_nothing(pair):
    divergent = dict(pair.critic(pair.source)[0], operation="not_evaluated", status="not_evaluated")
    pair.persist(pair.source, [divergent])
    status, body = _critic(pair, pair.source)
    assert status == 409 and body["status"] == "refused"
    assert body["refusal"]["class"] == "divergent_result" and body["refusal"]["finding_ids"] == [divergent["id"]]
    assert _reports(pair.source) == 0  # the Critic report is not recorded without its ledger
    assert [(f["id"], f["status"]) for f in rows(pair.source, "findings")] == [(divergent["id"], "not_evaluated")]


def test_a_retained_older_evaluator_version_is_reported_by_the_critic_route(pair):
    older = [dict(f, evaluation_method="provenance-v0.9") for f in pair.critic(pair.source)]
    pair.persist(pair.source, older)
    status, body = _critic(pair, pair.source)
    assert status == 201
    retained = body["report"]["ledger"]["retained"]
    assert {r["id"] for r in retained} == {f["id"] for f in older}
    assert {(r["stored_method"], r["computed_method"]) for r in retained} == {("provenance-v0.9", "provenance-v1.0")}
    assert {f["evaluation_method"] for f in rows(pair.source, "findings") if f["dimension"] == "provenance"} == {"provenance-v0.9"}


def test_one_batch_cannot_carry_two_results_for_one_finding(pair):
    finding = pair.critic(pair.restored)[0]
    store = SQLiteStore(pair.restored)
    try:
        assert store.insert_findings_batch([finding, dict(finding)])["inserted"] == [finding["id"]]
        with pytest.raises(FindingLedgerRefusal) as refused:
            store.insert_findings_batch([dict(finding, id="d" * 64), dict(finding, id="d" * 64, status="omitted", operation="omission")])
        assert refused.value.refusal_class == "divergent_result"
    finally:
        store.close()
    assert [f["id"] for f in rows(pair.restored, "findings")] == [finding["id"]]


def test_a_refusal_inside_a_caller_transaction_leaves_the_caller_able_to_roll_back(pair):
    store = SQLiteStore(pair.restored)
    try:
        with pytest.raises(FindingLedgerRefusal):
            with store.atomic():
                store.insert_findings_batch(pair.critic(pair.restored)[:1])
                store.insert_findings_batch([dict(pair.critic(pair.restored)[1], evidence=None)])
    finally:
        store.close()
    assert rows(pair.restored, "findings") == []  # the earlier batch in the same transaction is rolled back too


def test_the_cli_reports_a_refusal_and_records_nothing(pair, capsys):
    divergent = dict(pair.critic(pair.source)[0], operation="not_evaluated", status="not_evaluated")
    pair.persist(pair.source, [divergent])
    conn = sqlite3.connect(pair.source)
    conn.row_factory = sqlite3.Row
    try:
        critic_cmd._run_and_display_evaluation_functions(pair.narrative_id, pair.plan_id, pair.source, conn)
    finally:
        conn.close()
    assert "Finding ledger refused" in capsys.readouterr().out
    assert [f["id"] for f in rows(pair.source, "findings")] == [divergent["id"]]
