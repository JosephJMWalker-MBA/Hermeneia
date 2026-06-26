"""
Era II Sprint E5 — Stewardship Layer tests.

Verifies:
- StewardDecision as a canonical, immutable, append-only governance object
- Directionality: StewardDecision.finding_id → findings.id (never the reverse)
- Finding table has no steward_decision_id column (sealed)
- review_queue projection: Findings without decisions
- steward_ledger projection: all decisions with Finding context
- Supersession: a revised decision supersedes the old via supersession_relations
- Storage methods: insert, query, count
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.compiler.evaluation_functions.structural import evaluate_structural
from hermeneia.compiler.projections.review_queue import review_queue
from hermeneia.compiler.projections.steward_ledger import steward_ledger
from hermeneia.compiler.stewardship.decision import record_steward_decision, VERDICTS
from hermeneia.storage.hashing import make_steward_decision_id
from hermeneia.storage.sqlite import SQLiteStore

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def seeded(tmp_path):
    """Full chain with structural Findings stored."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store, architect_terms=["evidence", "fixed"])

    findings = evaluate_structural(ids["narrative_id"], ids["plan_id"], store._conn)
    store.insert_findings_batch(findings)
    ids["finding_ids"] = [f["id"] for f in findings]

    yield store, ids
    store.close()


def _first_finding_id(store, ids):
    return store._conn.execute(
        "SELECT id FROM findings WHERE rendered_narrative_id = ? LIMIT 1",
        (ids["narrative_id"],),
    ).fetchone()["id"]


# ── StewardDecision canonical object ────────────────────────────────────────

def test_record_decision_returns_dict(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    decision = record_steward_decision(fid, "accepted", "Structurally sound.", "steward-1", store._conn)
    assert isinstance(decision, dict)
    assert decision["finding_id"] == fid
    assert decision["verdict"] == "accepted"


def test_record_decision_id_content_addressable(seeded):
    """Same inputs produce the same decision ID."""
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    ts = "2026-06-20T10:00:00+00:00"
    d1 = record_steward_decision(fid, "accepted", "Looks good.", "steward-1", store._conn, decided_at=ts)
    expected = make_steward_decision_id(fid, "accepted", ts)
    assert d1["id"] == expected


def test_record_decision_persisted(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    decision = record_steward_decision(fid, "rejected", "Missing key term.", "steward-1", store._conn)
    rows = store.decisions_for_finding(fid)
    assert len(rows) == 1
    assert rows[0]["id"] == decision["id"]
    assert rows[0]["verdict"] == "rejected"


def test_all_three_verdicts_accepted(seeded):
    """accepted, rejected, deferred are all valid verdicts (one decision per finding)."""
    store, ids = seeded
    all_findings = store._conn.execute(
        "SELECT id FROM findings WHERE rendered_narrative_id = ?",
        (ids["narrative_id"],),
    ).fetchall()

    verdicts = ["accepted", "rejected", "deferred"]
    # Use the findings we have, cycling through them with unique decided_at timestamps
    # to avoid id collisions when the same finding receives multiple decisions
    used: set[str] = set()
    for i, verdict in enumerate(verdicts):
        fid = all_findings[i % len(all_findings)]["id"]
        ts = f"2026-06-20T{10 + i:02d}:00:00+00:00"
        record_steward_decision(fid, verdict, f"Rationale for {verdict}.", "steward-1", store._conn, decided_at=ts)

    counts = store._conn.execute("SELECT verdict, COUNT(*) FROM steward_decisions GROUP BY verdict").fetchall()
    by_verdict = {r[0]: r[1] for r in counts}
    for v in verdicts:
        assert by_verdict.get(v, 0) >= 1


def test_invalid_verdict_rejected(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    with pytest.raises(ValueError, match="verdict"):
        record_steward_decision(fid, "invalid", "Some rationale.", "steward-1", store._conn)


def test_empty_rationale_rejected(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    with pytest.raises(ValueError, match="rationale"):
        record_steward_decision(fid, "accepted", "   ", "steward-1", store._conn)


def test_empty_steward_id_rejected(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    with pytest.raises(ValueError, match="steward_id"):
        record_steward_decision(fid, "accepted", "Valid rationale.", "", store._conn)


def test_nonexistent_finding_rejected(seeded):
    store, ids = seeded
    with pytest.raises(ValueError, match="Finding"):
        record_steward_decision("nonexistent-finding-id", "accepted", "Rationale.", "steward-1", store._conn)


# ── Immutability ─────────────────────────────────────────────────────────────

def test_steward_decision_update_rejected(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    decision = record_steward_decision(fid, "accepted", "Good.", "steward-1", store._conn)
    with pytest.raises(Exception, match="immutable"):
        store._conn.execute(
            "UPDATE steward_decisions SET verdict = 'rejected' WHERE id = ?",
            (decision["id"],),
        )


def test_steward_decision_delete_rejected(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    decision = record_steward_decision(fid, "accepted", "Good.", "steward-1", store._conn)
    with pytest.raises(Exception, match="immutable"):
        store._conn.execute("DELETE FROM steward_decisions WHERE id = ?", (decision["id"],))


# ── Directionality constraint ────────────────────────────────────────────────

def test_finding_table_has_no_steward_decision_column(seeded):
    """Finding table must not have a steward_decision_id column — it is sealed."""
    store, ids = seeded
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(findings)").fetchall()}
    assert "steward_decision_id" not in cols, (
        "findings table must not reference StewardDecision — "
        "the directionality constraint requires StewardDecision to point to Finding, not the reverse."
    )


def test_steward_decision_fk_to_finding(seeded):
    """steward_decisions.finding_id is a FK to findings.id — enforced at schema level."""
    store, ids = seeded
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(steward_decisions)").fetchall()}
    assert "finding_id" in cols


def test_steward_decision_finding_id_fk_enforced(seeded):
    """Inserting a StewardDecision with a nonexistent finding_id must fail."""
    store, ids = seeded
    with pytest.raises(Exception):
        store._conn.execute(
            """
            INSERT INTO steward_decisions
                (id, finding_id, verdict, rationale, steward_id, decided_at, constitution_version, created_at)
            VALUES
                ('test-id', 'nonexistent-fk-id', 'accepted', 'Rationale', 'steward-1',
                 '2026-06-20T00:00:00+00:00', '1.0', '2026-06-20T00:00:00+00:00')
            """
        )
        store._conn.commit()


# ── Supersession ─────────────────────────────────────────────────────────────

def test_decision_supersession_via_relation(seeded):
    """A changed mind creates a new StewardDecision; old and new both remain accessible."""
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    ts1 = "2026-06-20T10:00:00+00:00"
    ts2 = "2026-06-20T11:00:00+00:00"

    d1 = record_steward_decision(fid, "deferred", "Needs more review.", "steward-1", store._conn, decided_at=ts1)
    d2 = record_steward_decision(fid, "accepted", "Reviewed and accepted.", "steward-1", store._conn, decided_at=ts2)

    store.insert_supersession_relation({
        "old_id": d1["id"],
        "new_id": d2["id"],
        "reason": "Steward revised verdict after further review.",
        "ratified_at": ts2,
    })

    # Both decisions remain accessible
    all_decisions = store.decisions_for_finding(fid)
    assert len(all_decisions) == 2

    # Supersession relation recorded
    supersessions = store.supersessions_from(d1["id"])
    assert len(supersessions) == 1
    assert supersessions[0]["new_id"] == d2["id"]


def test_steward_decision_in_supersession_existence_check(seeded):
    """supersession_relations existence trigger now covers steward_decisions."""
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    decision = record_steward_decision(fid, "accepted", "Fine.", "steward-1", store._conn)

    # Should succeed — decision exists
    d2 = record_steward_decision(fid, "rejected", "On reflection, rejected.", "steward-1", store._conn,
                                  decided_at="2026-06-20T12:00:00+00:00")
    store.insert_supersession_relation({
        "old_id": decision["id"],
        "new_id": d2["id"],
        "reason": "revised",
        "ratified_at": "2026-06-20T12:00:00+00:00",
    })
    # Verify old still accessible
    old_row = store._conn.execute(
        "SELECT * FROM steward_decisions WHERE id = ?", (decision["id"],)
    ).fetchone()
    assert old_row is not None


# ── review_queue projection ───────────────────────────────────────────────────

def test_review_queue_all_pending_before_decisions(seeded):
    store, ids = seeded
    result = review_queue(ids["narrative_id"], store._conn)
    assert result["pending_count"] > 0
    assert len(result["pending"]) == result["pending_count"]


def test_review_queue_shrinks_after_decision(seeded):
    store, ids = seeded
    before = review_queue(ids["narrative_id"], store._conn)["pending_count"]
    fid = _first_finding_id(store, ids)
    record_steward_decision(fid, "accepted", "Good.", "steward-1", store._conn)
    after = review_queue(ids["narrative_id"], store._conn)["pending_count"]
    assert after == before - 1


def test_review_queue_empty_after_all_decided(seeded):
    store, ids = seeded
    all_findings = store._conn.execute(
        "SELECT id FROM findings WHERE rendered_narrative_id = ?",
        (ids["narrative_id"],),
    ).fetchall()
    for i, row in enumerate(all_findings):
        record_steward_decision(row["id"], "accepted", f"Decision {i}.", "steward-1", store._conn)
    result = review_queue(ids["narrative_id"], store._conn)
    assert result["pending_count"] == 0


def test_review_queue_is_read_only(seeded):
    store, ids = seeded
    count_before = store._conn.execute("SELECT COUNT(*) FROM steward_decisions").fetchone()[0]
    review_queue(ids["narrative_id"], store._conn)
    count_after = store._conn.execute("SELECT COUNT(*) FROM steward_decisions").fetchone()[0]
    assert count_before == count_after


def test_review_queue_unknown_narrative(seeded):
    store, ids = seeded
    result = review_queue("nonexistent-id", store._conn)
    assert "error" in result
    assert result["pending_count"] == 0


# ── steward_ledger projection ─────────────────────────────────────────────────

def test_steward_ledger_empty_before_decisions(seeded):
    store, ids = seeded
    result = steward_ledger(ids["narrative_id"], store._conn)
    assert result["decision_count"] == 0
    assert result["decisions"] == []


def test_steward_ledger_records_decisions(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    record_steward_decision(fid, "accepted", "Well structured.", "steward-1", store._conn)
    result = steward_ledger(ids["narrative_id"], store._conn)
    assert result["decision_count"] == 1
    d = result["decisions"][0]
    assert d["verdict"] == "accepted"
    assert d["finding_id"] == fid
    assert "dimension" in d
    assert "finding_status" in d


def test_steward_ledger_by_verdict_counts(seeded):
    store, ids = seeded
    all_findings = store._conn.execute(
        "SELECT id FROM findings WHERE rendered_narrative_id = ?",
        (ids["narrative_id"],),
    ).fetchall()
    record_steward_decision(all_findings[0]["id"], "accepted", "Good.", "steward-1", store._conn)
    if len(all_findings) > 1:
        record_steward_decision(all_findings[1]["id"], "rejected", "Bad.", "steward-1", store._conn)

    result = steward_ledger(ids["narrative_id"], store._conn)
    assert result["by_verdict"]["accepted"] >= 1
    if len(all_findings) > 1:
        assert result["by_verdict"]["rejected"] >= 1


def test_steward_ledger_is_read_only(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    record_steward_decision(fid, "accepted", "OK.", "steward-1", store._conn)
    count_before = store._conn.execute("SELECT COUNT(*) FROM steward_decisions").fetchone()[0]
    steward_ledger(ids["narrative_id"], store._conn)
    count_after = store._conn.execute("SELECT COUNT(*) FROM steward_decisions").fetchone()[0]
    assert count_before == count_after


def test_steward_ledger_regeneratable(seeded):
    store, ids = seeded
    fid = _first_finding_id(store, ids)
    record_steward_decision(fid, "accepted", "Good.", "steward-1", store._conn)
    r1 = steward_ledger(ids["narrative_id"], store._conn)
    r2 = steward_ledger(ids["narrative_id"], store._conn)
    r1.pop("generated_at")
    r2.pop("generated_at")
    assert r1 == r2


def test_steward_ledger_unknown_narrative(seeded):
    store, ids = seeded
    result = steward_ledger("nonexistent-id", store._conn)
    assert "error" in result
    assert result["decision_count"] == 0


# ── review_queue + ledger consistency ────────────────────────────────────────

def test_queue_plus_ledger_equals_total_findings(seeded):
    """pending_count + decision_count == total Finding count for the narrative."""
    store, ids = seeded
    all_findings = store._conn.execute(
        "SELECT id FROM findings WHERE rendered_narrative_id = ?",
        (ids["narrative_id"],),
    ).fetchall()
    total = len(all_findings)

    # Decide on first half
    decided = all_findings[: total // 2]
    for row in decided:
        record_steward_decision(row["id"], "accepted", "Accepted.", "steward-1", store._conn)

    queue = review_queue(ids["narrative_id"], store._conn)
    ledger = steward_ledger(ids["narrative_id"], store._conn)

    assert queue["pending_count"] + ledger["decision_count"] == total
