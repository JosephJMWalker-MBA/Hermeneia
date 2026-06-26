"""
Era II Sprint E7 — Ratification tests.

Verifies:
- RatificationRecord as the terminal canonical object in the epistemic chain
- Pre-condition gates: Finding, StewardDecision, WitnessSession all required
- Immutability: UPDATE and DELETE rejected
- Audit snapshot captures full constitutional state at ratification
- Directionality: RatificationRecord points to RenderedNarrative; never the reverse
- ratification_certificate projection: human-readable certificate for a narrative
- institutional_memory projection: all ratified narratives across the store
- Supersession: a superseded ratification links old to new via supersession_relations
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermeneia.compiler.evaluation_functions.structural import evaluate_structural
from hermeneia.compiler.projections.institutional_memory import institutional_memory
from hermeneia.compiler.projections.ratification_certificate import ratification_certificate
from hermeneia.compiler.ratification.record import (
    RatificationError,
    create_ratification_record,
)
from hermeneia.compiler.stewardship.decision import record_steward_decision
from hermeneia.compiler.witness.session import record_witness_session
from hermeneia.storage.hashing import make_ratification_record_id
from hermeneia.storage.sqlite import SQLiteStore

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def chain(tmp_path):
    """Full chain with Findings seeded but no decisions or witnesses yet."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store, architect_terms=["evidence", "fixed"])

    findings = evaluate_structural(ids["narrative_id"], ids["plan_id"], store._conn)
    store.insert_findings_batch(findings)
    ids["finding_ids"] = [f["id"] for f in findings]

    yield store, ids
    store.close()


@pytest.fixture
def fully_ratifiable(chain):
    """Chain where all pre-conditions for ratification are met."""
    store, ids = chain
    for fid in ids["finding_ids"]:
        record_steward_decision(fid, "accepted", "Approved.", "steward-1", store._conn)
    record_witness_session(
        ids["narrative_id"], "8-year-old",
        "Explain the main idea in your own words.",
        True, "facilitator-1", store._conn, session_date="2026-06-20",
    )
    yield store, ids


# ── Pre-condition gates ───────────────────────────────────────────────────────

def test_ratification_fails_without_findings(tmp_path):
    """No Findings → ratification premature."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store)
    with pytest.raises(RatificationError, match="Finding"):
        create_ratification_record(
            ids["narrative_id"], "steward-1",
            "I declare this ratified.", store._conn,
        )
    store.close()


def test_ratification_fails_without_all_decisions(chain):
    """Findings exist but not all decided → ratification premature."""
    store, ids = chain
    # Decide only the first finding, leave the rest
    record_steward_decision(ids["finding_ids"][0], "accepted", "Approved.", "steward-1", store._conn)
    record_witness_session(
        ids["narrative_id"], "8-year-old", "Task.", True, "facilitator-1", store._conn,
        session_date="2026-06-20",
    )
    with pytest.raises(RatificationError, match="StewardDecision"):
        create_ratification_record(
            ids["narrative_id"], "steward-1",
            "I declare this ratified.", store._conn,
        )


def test_ratification_fails_without_witness_session(chain):
    """All Findings decided but no WitnessSession → ratification premature."""
    store, ids = chain
    for fid in ids["finding_ids"]:
        record_steward_decision(fid, "accepted", "Approved.", "steward-1", store._conn)
    with pytest.raises(RatificationError, match="WitnessSession"):
        create_ratification_record(
            ids["narrative_id"], "steward-1",
            "I declare this ratified.", store._conn,
        )


# ── Happy path ────────────────────────────────────────────────────────────────

def test_ratification_succeeds_when_all_preconditions_met(fully_ratifiable):
    store, ids = fully_ratifiable
    record = create_ratification_record(
        ids["narrative_id"], "steward-1",
        "I have reviewed all Findings, confirmed all steward decisions, and verified "
        "that an 8-year-old completed the understanding task. I ratify this narrative.",
        store._conn,
    )
    assert isinstance(record, dict)
    assert record["rendered_narrative_id"] == ids["narrative_id"]
    assert record["ratified_by"] == "steward-1"


def test_ratification_record_id_content_addressable(fully_ratifiable):
    store, ids = fully_ratifiable
    ts = "2026-06-20T12:00:00+00:00"
    record = create_ratification_record(
        ids["narrative_id"], "steward-1", "Ratified.", store._conn, ratified_at=ts,
    )
    expected = make_ratification_record_id(ids["narrative_id"], "steward-1", ts)
    assert record["id"] == expected


def test_ratification_record_persisted(fully_ratifiable):
    store, ids = fully_ratifiable
    record = create_ratification_record(
        ids["narrative_id"], "steward-1", "Ratified.", store._conn,
    )
    rows = store.ratification_records_for_narrative(ids["narrative_id"])
    assert len(rows) == 1
    assert rows[0]["id"] == record["id"]


def test_ratification_snapshot_contains_counts(fully_ratifiable):
    store, ids = fully_ratifiable
    record = create_ratification_record(
        ids["narrative_id"], "steward-1", "Ratified.", store._conn,
    )
    assert record["finding_count"] == len(ids["finding_ids"])
    assert record["steward_decision_count"] == len(ids["finding_ids"])
    assert record["witness_session_count"] == 1


def test_ratification_snapshot_is_valid_json(fully_ratifiable):
    store, ids = fully_ratifiable
    record = create_ratification_record(
        ids["narrative_id"], "steward-1", "Ratified.", store._conn,
    )
    snapshot = json.loads(record["audit_snapshot"])
    assert "finding_count" in snapshot
    assert "findings_by_dimension" in snapshot
    assert "decisions_by_verdict" in snapshot
    assert "sessions_by_profile" in snapshot


def test_ratification_snapshot_frozen_at_ratification_time(fully_ratifiable):
    """Snapshot does not change when new decisions are added after ratification."""
    store, ids = fully_ratifiable
    record = create_ratification_record(
        ids["narrative_id"], "steward-1", "Ratified.", store._conn,
        ratified_at="2026-06-20T10:00:00+00:00",
    )
    snapshot_before = json.loads(record["audit_snapshot"])

    # Add a second decision after ratification
    record_steward_decision(
        ids["finding_ids"][0], "rejected", "Reconsidering.", "steward-1", store._conn,
        decided_at="2026-06-20T11:00:00+00:00",
    )

    # The stored snapshot is unchanged — it was frozen at ratification time
    stored = store.ratification_records_for_narrative(ids["narrative_id"])[0]
    stored_snapshot = json.loads(stored["audit_snapshot"])
    assert stored_snapshot["steward_decision_count"] == snapshot_before["steward_decision_count"]


# ── Immutability ─────────────────────────────────────────────────────────────

def test_ratification_record_update_rejected(fully_ratifiable):
    store, ids = fully_ratifiable
    record = create_ratification_record(
        ids["narrative_id"], "steward-1", "Ratified.", store._conn,
    )
    with pytest.raises(Exception, match="immutable"):
        store._conn.execute(
            "UPDATE ratification_records SET ratified_by = 'attacker' WHERE id = ?",
            (record["id"],),
        )


def test_ratification_record_delete_rejected(fully_ratifiable):
    store, ids = fully_ratifiable
    record = create_ratification_record(
        ids["narrative_id"], "steward-1", "Ratified.", store._conn,
    )
    with pytest.raises(Exception, match="immutable"):
        store._conn.execute(
            "DELETE FROM ratification_records WHERE id = ?", (record["id"],)
        )


# ── Directionality constraint ────────────────────────────────────────────────

def test_rendered_narratives_has_no_ratification_column(fully_ratifiable):
    """rendered_narratives must not reference RatificationRecord — sealed table."""
    store, ids = fully_ratifiable
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(rendered_narratives)").fetchall()}
    assert "ratification_record_id" not in cols


def test_ratification_fk_enforced(fully_ratifiable):
    """Inserting a RatificationRecord with a nonexistent narrative_id must fail."""
    store, ids = fully_ratifiable
    with pytest.raises(Exception):
        store._conn.execute(
            """
            INSERT INTO ratification_records
                (id, rendered_narrative_id, ratified_by, ratified_at,
                 steward_declaration, finding_count, steward_decision_count,
                 witness_session_count, constitution_version, audit_snapshot, created_at)
            VALUES
                ('test-id', 'nonexistent-narrative', 'steward-1', '2026-06-20T00:00:00+00:00',
                 'Ratified.', 1, 1, 1, '1.0', '{}', '2026-06-20T00:00:00+00:00')
            """
        )
        store._conn.commit()


# ── Input validation ─────────────────────────────────────────────────────────

def test_empty_ratified_by_rejected(fully_ratifiable):
    store, ids = fully_ratifiable
    with pytest.raises(ValueError, match="ratified_by"):
        create_ratification_record(ids["narrative_id"], "", "Ratified.", store._conn)


def test_empty_declaration_rejected(fully_ratifiable):
    store, ids = fully_ratifiable
    with pytest.raises(ValueError, match="steward_declaration"):
        create_ratification_record(ids["narrative_id"], "steward-1", "   ", store._conn)


def test_nonexistent_narrative_rejected(fully_ratifiable):
    store, ids = fully_ratifiable
    with pytest.raises(ValueError, match="RenderedNarrative"):
        create_ratification_record("nonexistent-id", "steward-1", "Ratified.", store._conn)


# ── Supersession ─────────────────────────────────────────────────────────────

def test_ratification_supersession(fully_ratifiable):
    """A second ratification can supersede the first via supersession_relations."""
    store, ids = fully_ratifiable
    r1 = create_ratification_record(
        ids["narrative_id"], "steward-1", "Initial ratification.",
        store._conn, ratified_at="2026-06-20T10:00:00+00:00",
    )
    r2 = create_ratification_record(
        ids["narrative_id"], "steward-2",
        "Re-ratified after additional witness session.",
        store._conn, ratified_at="2026-06-21T10:00:00+00:00",
    )
    store.insert_supersession_relation({
        "old_id": r1["id"],
        "new_id": r2["id"],
        "reason": "Additional witness session completed by 80-year-old profile.",
        "ratified_at": "2026-06-21T10:00:00+00:00",
    })
    all_records = store.ratification_records_for_narrative(ids["narrative_id"])
    assert len(all_records) == 2
    supersessions = store.supersessions_from(r1["id"])
    assert supersessions[0]["new_id"] == r2["id"]


# ── ratification_certificate projection ──────────────────────────────────────

def test_certificate_unratified(chain):
    store, ids = chain
    result = ratification_certificate(ids["narrative_id"], store._conn)
    assert result["ratified"] is False
    assert result["certificate"] is None


def test_certificate_after_ratification(fully_ratifiable):
    store, ids = fully_ratifiable
    create_ratification_record(
        ids["narrative_id"], "steward-1", "Ratified.", store._conn,
    )
    result = ratification_certificate(ids["narrative_id"], store._conn)
    assert result["ratified"] is True
    cert = result["certificate"]
    assert cert["ratified_by"] == "steward-1"
    assert cert["finding_count"] == len(ids["finding_ids"])
    assert "findings_by_dimension" in cert
    assert "decisions_by_verdict" in cert
    assert "sessions_by_profile" in cert


def test_certificate_is_read_only(fully_ratifiable):
    store, ids = fully_ratifiable
    create_ratification_record(ids["narrative_id"], "steward-1", "Ratified.", store._conn)
    count_before = store.ratification_record_count()
    ratification_certificate(ids["narrative_id"], store._conn)
    assert store.ratification_record_count() == count_before


def test_certificate_regeneratable(fully_ratifiable):
    store, ids = fully_ratifiable
    create_ratification_record(ids["narrative_id"], "steward-1", "Ratified.", store._conn)
    r1 = ratification_certificate(ids["narrative_id"], store._conn)
    r2 = ratification_certificate(ids["narrative_id"], store._conn)
    r1.pop("generated_at"); r2.pop("generated_at")
    assert r1 == r2


def test_certificate_unknown_narrative(fully_ratifiable):
    store, ids = fully_ratifiable
    result = ratification_certificate("nonexistent-id", store._conn)
    assert "error" in result
    assert result["ratified"] is False


# ── institutional_memory projection ──────────────────────────────────────────

def test_institutional_memory_empty_before_ratification(chain):
    store, ids = chain
    result = institutional_memory(store._conn)
    assert result["total_ratified"] == 0
    assert result["entries"] == []


def test_institutional_memory_after_ratification(fully_ratifiable):
    store, ids = fully_ratifiable
    create_ratification_record(ids["narrative_id"], "steward-1", "Ratified.", store._conn)
    result = institutional_memory(store._conn)
    assert result["total_ratified"] == 1
    entry = result["entries"][0]
    assert entry["narrative_id"] == ids["narrative_id"]
    assert entry["ratified_by"] == "steward-1"
    assert entry["finding_count"] == len(ids["finding_ids"])


def test_institutional_memory_is_read_only(fully_ratifiable):
    store, ids = fully_ratifiable
    create_ratification_record(ids["narrative_id"], "steward-1", "Ratified.", store._conn)
    count_before = store.ratification_record_count()
    institutional_memory(store._conn)
    assert store.ratification_record_count() == count_before


def test_institutional_memory_regeneratable(fully_ratifiable):
    store, ids = fully_ratifiable
    create_ratification_record(ids["narrative_id"], "steward-1", "Ratified.", store._conn)
    r1 = institutional_memory(store._conn)
    r2 = institutional_memory(store._conn)
    r1.pop("generated_at"); r2.pop("generated_at")
    assert r1 == r2


# ── Full epistemic chain ──────────────────────────────────────────────────────

def test_full_epistemic_chain_end_to_end(fully_ratifiable):
    """Finding → StewardDecision → WitnessSession → RatificationRecord.

    Verifies the complete epistemic chain is traversable from a single
    RatificationRecord back to all four layers.
    """
    store, ids = fully_ratifiable
    record = create_ratification_record(
        ids["narrative_id"], "steward-1",
        "All layers verified. This narrative becomes institutional memory.",
        store._conn,
    )

    # Layer 1: Findings exist
    findings = store._conn.execute(
        "SELECT id FROM findings WHERE rendered_narrative_id = ?",
        (ids["narrative_id"],),
    ).fetchall()
    assert len(findings) > 0

    # Layer 2: Every Finding has a StewardDecision
    for f in findings:
        decisions = store.decisions_for_finding(f["id"])
        assert len(decisions) >= 1

    # Layer 3: At least one WitnessSession
    sessions = store.sessions_for_narrative(ids["narrative_id"])
    assert len(sessions) >= 1

    # Layer 4: RatificationRecord captures everything
    snapshot = json.loads(record["audit_snapshot"])
    assert snapshot["finding_count"] == len(findings)
    assert snapshot["steward_decision_count"] >= len(findings)
    assert snapshot["witness_session_count"] >= 1

    # Certificate confirms ratified
    cert = ratification_certificate(ids["narrative_id"], store._conn)
    assert cert["ratified"] is True

    # Institutional memory includes this narrative
    memory = institutional_memory(store._conn)
    narrative_ids = {e["narrative_id"] for e in memory["entries"]}
    assert ids["narrative_id"] in narrative_ids
