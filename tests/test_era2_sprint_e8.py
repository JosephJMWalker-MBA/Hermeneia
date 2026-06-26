"""
Era II Sprint E8 — Interpretation Staging tests.

Verifies:
- Two-Table Invariant: proposed_interpretations and interpretations are separate tables.
  A proposed interpretation is not an interpretation with lower confidence.
  It is a different constitutional state. (Architecture_Proofs.md — Staging Constitutional Principle)
- propose_interpretation: creates ai_provenance + proposed_interpretation; status='pending'
- accept_proposed_interpretation: status→'accepted', ai_provenance acceptance fields populated,
  canonical interpretation row inserted with ai_provenance_id
- reject_proposed_interpretation: status→'rejected', rejected object remains permanently in staging,
  ai_provenance acceptance fields remain NULL, no canonical row created
- Immutability: terminal status cannot be re-decided; generation fields of ai_provenance immutable;
  ai_provenance acceptance fields set only once; proposed_interpretations cannot be deleted
- Dual provenance: accepted canonical interpretation has ai_provenance_id; provenance records full chain
- Lineage completeness: accepted interpretation traversable to Observation
- Projections: staging_queue (pending only), staging_ledger (all with breakdown)
- Storage: insert, query, count methods for both new tables
- Two-Table Invariant enforced structurally: interpretations has no 'status' column;
  proposed_interpretations has no immutability trigger blocking all updates (status is mutable)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.compiler.staging.interpretation import (
    StagingError,
    accept_proposed_interpretation,
    propose_interpretation,
    reject_proposed_interpretation,
    staging_ledger,
    staging_queue,
)
from hermeneia.storage.hashing import (
    make_ai_provenance_id,
    make_interpretation_id,
    make_proposed_interpretation_id,
)
from hermeneia.storage.sqlite import SQLiteStore

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def store_with_obs(tmp_path):
    """Store with a minimal evidence chain providing one observation_id."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store)
    yield store, ids
    store.close()


def _propose(store, ids, *, text="The green light symbolises hope.", model="claude-sonnet-4-6", ts=None):
    """Helper: create a proposal with sensible defaults."""
    return propose_interpretation(
        observation_id=ids["obs_id"],
        perspective="literary",
        text=text,
        evidential_status="speculative",
        generating_model=model,
        prompt_reference="sha256:abc123",
        prompt_reference_type="hash",
        conn=store,
        generation_timestamp=ts or "2026-06-20T12:00:00+00:00",
        parent_object_ids=[ids["obs_id"]],
    )


# ── Two-Table Invariant ───────────────────────────────────────────────────────

def test_interpretations_table_has_no_status_column(store_with_obs):
    """The collapse error: interpretations must not have a status column."""
    store, _ = store_with_obs
    cols = {row[1] for row in store._conn.execute("PRAGMA table_info(interpretations)")}
    assert "status" not in cols, (
        "interpretations.status would collapse the Two-Table Invariant. "
        "A proposed interpretation is not an interpretation with lower confidence — "
        "it is a different constitutional state."
    )


def test_proposed_interpretations_table_has_no_canonical_ancestors(store_with_obs):
    """Staging table is not a canonical layer — it has no upstream canonical parent."""
    store, _ = store_with_obs
    cols = {row[1] for row in store._conn.execute("PRAGMA table_info(proposed_interpretations)")}
    # Must carry observation_id (for lineage) but must NOT carry rendered_narrative_id,
    # architect_plan_id, or any field that would make it a canonical pipeline object.
    assert "observation_id" in cols
    assert "rendered_narrative_id" not in cols
    assert "architect_plan_id" not in cols


def test_interpretations_has_ai_provenance_id_column(store_with_obs):
    """Canonical interpretations carry ai_provenance_id to record AI-assisted origin."""
    store, _ = store_with_obs
    cols = {row[1] for row in store._conn.execute("PRAGMA table_info(interpretations)")}
    assert "ai_provenance_id" in cols


def test_human_authored_interpretation_has_null_ai_provenance_id(store_with_obs):
    """Pre-E8 human-authored rows have ai_provenance_id = NULL."""
    store, ids = store_with_obs
    row = store._conn.execute(
        "SELECT ai_provenance_id FROM interpretations WHERE observation_id = ?",
        (ids["obs_id"],),
    ).fetchone()
    assert row is not None
    assert row["ai_provenance_id"] is None


# ── Proposal creation ─────────────────────────────────────────────────────────

def test_propose_returns_dict(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    assert isinstance(proposal, dict)
    assert proposal["status"] == "pending"
    assert proposal["observation_id"] == ids["obs_id"]


def test_propose_creates_ai_provenance_record(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    prov = store.get_ai_provenance(proposal["ai_provenance_id"])
    assert prov is not None
    assert prov["generating_model"] == "claude-sonnet-4-6"
    assert prov["accepting_steward"] is None   # not yet accepted
    assert prov["acceptance_timestamp"] is None
    assert prov["acceptance_rationale"] is None


def test_propose_creates_staging_row(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    stored = store.get_proposed_interpretation(proposal["id"])
    assert stored is not None
    assert stored["status"] == "pending"
    assert stored["steward_id"] is None


def test_propose_id_is_deterministic(store_with_obs):
    store, ids = store_with_obs
    ts = "2026-06-20T12:00:00+00:00"
    proposal = _propose(store, ids, ts=ts)
    expected = make_proposed_interpretation_id(
        ids["obs_id"], "literary", "The green light symbolises hope.", "claude-sonnet-4-6", ts
    )
    assert proposal["id"] == expected


def test_propose_ai_provenance_id_is_deterministic(store_with_obs):
    store, ids = store_with_obs
    ts = "2026-06-20T12:00:00+00:00"
    proposal = _propose(store, ids, ts=ts)
    expected = make_ai_provenance_id(proposal["id"], "claude-sonnet-4-6", ts)
    assert proposal["ai_provenance_id"] == expected


def test_propose_requires_existing_observation(store_with_obs):
    store, ids = store_with_obs
    with pytest.raises(StagingError, match="not found"):
        propose_interpretation(
            observation_id="nonexistent-observation-id",
            perspective="literary",
            text="Some text.",
            evidential_status="speculative",
            generating_model="claude-sonnet-4-6",
            prompt_reference="sha256:abc",
            prompt_reference_type="hash",
            conn=store,
        )


def test_propose_requires_nonempty_text(store_with_obs):
    store, ids = store_with_obs
    with pytest.raises(StagingError):
        propose_interpretation(
            observation_id=ids["obs_id"],
            perspective="literary",
            text="   ",
            evidential_status="speculative",
            generating_model="claude-sonnet-4-6",
            prompt_reference="sha256:abc",
            prompt_reference_type="hash",
            conn=store,
        )


def test_propose_requires_valid_evidential_status(store_with_obs):
    store, ids = store_with_obs
    with pytest.raises(StagingError):
        propose_interpretation(
            observation_id=ids["obs_id"],
            perspective="literary",
            text="Some text.",
            evidential_status="high_confidence",  # not in the vocabulary
            generating_model="claude-sonnet-4-6",
            prompt_reference="sha256:abc",
            prompt_reference_type="hash",
            conn=store,
        )


def test_two_different_proposals_for_same_observation_coexist(store_with_obs):
    """Multiple proposals for the same observation are distinct staging objects."""
    store, ids = store_with_obs
    p1 = _propose(store, ids, text="Interpretation A.", model="claude-sonnet-4-6", ts="2026-06-20T10:00:00+00:00")
    p2 = _propose(store, ids, text="Interpretation B.", model="gpt-4o", ts="2026-06-20T11:00:00+00:00")
    assert p1["id"] != p2["id"]
    assert store.proposed_interpretation_count() == 2


# ── Acceptance workflow ───────────────────────────────────────────────────────

def test_accept_returns_canonical_interpretation(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    canonical = accept_proposed_interpretation(
        proposal["id"], "steward-1", "Semantically sound.", store
    )
    assert isinstance(canonical, dict)
    assert canonical["source"] == "ai-accepted"
    assert canonical["observation_id"] == ids["obs_id"]


def test_accept_creates_canonical_interpretation_row(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    canonical = accept_proposed_interpretation(
        proposal["id"], "steward-1", "Semantically sound.", store
    )
    row = store._conn.execute(
        "SELECT * FROM interpretations WHERE id = ?", (canonical["id"],)
    ).fetchone()
    assert row is not None
    assert row["source"] == "ai-accepted"
    assert row["ai_provenance_id"] == proposal["ai_provenance_id"]


def test_accept_canonical_id_matches_content_addressable_formula(store_with_obs):
    """Accepted interpretation ID uses the same formula as human-authored interpretations."""
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    canonical = accept_proposed_interpretation(
        proposal["id"], "steward-1", "Looks good.", store
    )
    expected = make_interpretation_id(
        proposal["observation_id"], proposal["perspective"], proposal["text"]
    )
    assert canonical["id"] == expected


def test_accept_updates_proposal_status(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    accept_proposed_interpretation(proposal["id"], "steward-1", "Accepted.", store)
    updated = store.get_proposed_interpretation(proposal["id"])
    assert updated["status"] == "accepted"
    assert updated["steward_id"] == "steward-1"
    assert updated["decided_at"] is not None


def test_accept_completes_ai_provenance_record(store_with_obs):
    """After acceptance, ai_provenance has accepting_steward and acceptance_timestamp."""
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    accept_proposed_interpretation(
        proposal["id"], "steward-1", "Good interpretation.", store
    )
    prov = store.get_ai_provenance(proposal["ai_provenance_id"])
    assert prov["accepting_steward"] == "steward-1"
    assert prov["acceptance_timestamp"] is not None
    assert prov["acceptance_rationale"] == "Good interpretation."


def test_accept_requires_rationale(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    with pytest.raises(StagingError, match="acceptance_rationale"):
        accept_proposed_interpretation(proposal["id"], "steward-1", "   ", store)


def test_accept_requires_steward(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    with pytest.raises(StagingError, match="accepting_steward"):
        accept_proposed_interpretation(proposal["id"], "", "Rationale.", store)


def test_accept_nonexistent_proposal_raises(store_with_obs):
    store, _ = store_with_obs
    with pytest.raises(StagingError, match="not found"):
        accept_proposed_interpretation("nonexistent-id", "steward-1", "Rationale.", store)


# ── Rejection workflow ────────────────────────────────────────────────────────

def test_reject_updates_proposal_status(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    result = reject_proposed_interpretation(
        proposal["id"], "steward-1", "Factually inaccurate.", store
    )
    assert result["status"] == "rejected"
    assert result["steward_id"] == "steward-1"
    assert result["steward_rationale"] == "Factually inaccurate."


def test_reject_does_not_create_canonical_interpretation(store_with_obs):
    """Rejected proposals must never enter canonical interpretations."""
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    count_before = store.interpretation_count()
    reject_proposed_interpretation(
        proposal["id"], "steward-1", "Factually inaccurate.", store
    )
    count_after = store.interpretation_count()
    assert count_after == count_before


def test_reject_leaves_ai_provenance_acceptance_fields_null(store_with_obs):
    """For rejected proposals, ai_provenance acceptance fields remain NULL."""
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    reject_proposed_interpretation(
        proposal["id"], "steward-1", "Inaccurate.", store
    )
    prov = store.get_ai_provenance(proposal["ai_provenance_id"])
    assert prov["accepting_steward"] is None
    assert prov["acceptance_timestamp"] is None
    assert prov["acceptance_rationale"] is None


def test_reject_requires_rationale(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    with pytest.raises(StagingError, match="rejection_rationale"):
        reject_proposed_interpretation(proposal["id"], "steward-1", "", store)


def test_reject_nonexistent_proposal_raises(store_with_obs):
    store, _ = store_with_obs
    with pytest.raises(StagingError, match="not found"):
        reject_proposed_interpretation("nonexistent", "steward-1", "Reason.", store)


# ── Immutability constraints ──────────────────────────────────────────────────

def test_accepted_proposal_cannot_be_accepted_again(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    accept_proposed_interpretation(proposal["id"], "steward-1", "Good.", store)
    with pytest.raises(StagingError, match="accepted"):
        accept_proposed_interpretation(proposal["id"], "steward-2", "Also good.", store)


def test_accepted_proposal_cannot_be_rejected(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    accept_proposed_interpretation(proposal["id"], "steward-1", "Good.", store)
    with pytest.raises(StagingError, match="accepted"):
        reject_proposed_interpretation(proposal["id"], "steward-2", "Actually bad.", store)


def test_rejected_proposal_cannot_be_accepted(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    reject_proposed_interpretation(proposal["id"], "steward-1", "Bad.", store)
    with pytest.raises(StagingError, match="rejected"):
        accept_proposed_interpretation(proposal["id"], "steward-2", "Actually good.", store)


def test_rejected_proposal_cannot_be_deleted(store_with_obs):
    """ADR-0009: rejected objects are never deleted — permanent record."""
    import sqlite3
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    reject_proposed_interpretation(proposal["id"], "steward-1", "Bad.", store)
    with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)):
        store._conn.execute(
            "DELETE FROM proposed_interpretations WHERE id = ?", (proposal["id"],)
        )


def test_pending_proposal_cannot_be_deleted(store_with_obs):
    """All proposed_interpretations rows are protected from deletion."""
    import sqlite3
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)):
        store._conn.execute(
            "DELETE FROM proposed_interpretations WHERE id = ?", (proposal["id"],)
        )


def test_ai_provenance_generation_fields_immutable(store_with_obs):
    """ai_provenance generation fields cannot be changed after write."""
    import sqlite3
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)):
        store._conn.execute(
            "UPDATE ai_provenance SET generating_model = 'evil-model' WHERE id = ?",
            (proposal["ai_provenance_id"],),
        )


def test_ai_provenance_acceptance_fields_set_only_once(store_with_obs):
    """ai_provenance acceptance fields cannot be overwritten after being set."""
    import sqlite3
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    accept_proposed_interpretation(proposal["id"], "steward-1", "Good.", store)
    with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)):
        store._conn.execute(
            "UPDATE ai_provenance SET accepting_steward = 'hacker' WHERE id = ?",
            (proposal["ai_provenance_id"],),
        )


def test_ai_provenance_cannot_be_deleted(store_with_obs):
    import sqlite3
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)):
        store._conn.execute(
            "DELETE FROM ai_provenance WHERE id = ?", (proposal["ai_provenance_id"],)
        )


def test_terminal_status_cannot_transition(store_with_obs):
    """Database trigger: status may not transition from a terminal state."""
    import sqlite3
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    accept_proposed_interpretation(proposal["id"], "steward-1", "Good.", store)
    with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)):
        store._conn.execute(
            "UPDATE proposed_interpretations SET status = 'rejected' WHERE id = ?",
            (proposal["id"],),
        )


# ── Dual provenance chain ────────────────────────────────────────────────────

def test_canonical_interpretation_has_ai_provenance_id(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    canonical = accept_proposed_interpretation(proposal["id"], "steward-1", "Good.", store)
    row = store._conn.execute(
        "SELECT ai_provenance_id FROM interpretations WHERE id = ?", (canonical["id"],)
    ).fetchone()
    assert row["ai_provenance_id"] == proposal["ai_provenance_id"]


def test_ai_provenance_records_full_generation_trail(store_with_obs):
    store, ids = store_with_obs
    proposal = propose_interpretation(
        observation_id=ids["obs_id"],
        perspective="literary",
        text="The green light is an existential cipher.",
        evidential_status="speculative",
        generating_model="claude-sonnet-4-6",
        prompt_reference="sha256:deadbeef",
        prompt_reference_type="hash",
        conn=store,
        model_version="claude-sonnet-4-6-20251001",
        generation_timestamp="2026-06-20T09:00:00+00:00",
        parent_object_ids=[ids["obs_id"]],
        generation_parameters={"temperature": 0.3, "max_tokens": 512},
    )
    prov = store.get_ai_provenance(proposal["ai_provenance_id"])
    assert prov["model_version"] == "claude-sonnet-4-6-20251001"
    assert prov["prompt_reference"] == "sha256:deadbeef"
    assert prov["prompt_reference_type"] == "hash"
    assert json.loads(prov["parent_object_ids"]) == [ids["obs_id"]]
    params = json.loads(prov["generation_parameters"])
    assert params["temperature"] == 0.3


# ── Lineage completeness ──────────────────────────────────────────────────────

def test_accepted_interpretation_lineage_to_observation(store_with_obs):
    """LCP: accepted interpretation is traversable back to its originating observation."""
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    canonical = accept_proposed_interpretation(proposal["id"], "steward-1", "Good.", store)

    # Step 1: canonical interpretation → ai_provenance_id
    interp_row = store._conn.execute(
        "SELECT * FROM interpretations WHERE id = ?", (canonical["id"],)
    ).fetchone()
    assert interp_row["ai_provenance_id"] is not None

    # Step 2: ai_provenance → staged_object_id → proposed_interpretations
    prov = store.get_ai_provenance(interp_row["ai_provenance_id"])
    staged = store.get_proposed_interpretation(prov["staged_object_id"])
    assert staged is not None

    # Step 3: proposed_interpretation → observation_id
    obs = store._conn.execute(
        "SELECT id FROM observations WHERE id = ?", (staged["observation_id"],)
    ).fetchone()
    assert obs is not None

    # Full chain: interpretation → ai_provenance → proposed_interpretation → observation
    assert obs["id"] == ids["obs_id"]


def test_accepted_interpretation_also_has_direct_observation_fk(store_with_obs):
    """Canonical interpretation carries observation_id directly (LCP without provenance hop)."""
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    canonical = accept_proposed_interpretation(proposal["id"], "steward-1", "Good.", store)
    row = store._conn.execute(
        "SELECT observation_id FROM interpretations WHERE id = ?", (canonical["id"],)
    ).fetchone()
    assert row["observation_id"] == ids["obs_id"]


# ── Projections ───────────────────────────────────────────────────────────────

def test_staging_queue_shows_pending_only(store_with_obs):
    store, ids = store_with_obs
    p1 = _propose(store, ids, text="Text A.", ts="2026-06-20T10:00:00+00:00")
    p2 = _propose(store, ids, text="Text B.", ts="2026-06-20T11:00:00+00:00")
    accept_proposed_interpretation(p1["id"], "steward-1", "Good.", store)

    queue = staging_queue(store)
    assert queue["pending_count"] == 1
    pending_ids = {p["id"] for p in queue["proposals"]}
    assert p2["id"] in pending_ids
    assert p1["id"] not in pending_ids


def test_staging_ledger_shows_all_proposals(store_with_obs):
    store, ids = store_with_obs
    p1 = _propose(store, ids, text="Text A.", ts="2026-06-20T10:00:00+00:00")
    p2 = _propose(store, ids, text="Text B.", ts="2026-06-20T11:00:00+00:00")
    p3 = _propose(store, ids, text="Text C.", ts="2026-06-20T12:00:00+00:00")

    accept_proposed_interpretation(p1["id"], "steward-1", "Good.", store)
    reject_proposed_interpretation(p2["id"], "steward-1", "Bad.", store)

    ledger = staging_ledger(store)
    assert ledger["total"] == 3
    assert ledger["by_status"]["accepted"] == 1
    assert ledger["by_status"]["rejected"] == 1
    assert ledger["by_status"]["pending"] == 1


def test_staging_queue_and_ledger_agree_on_pending_count(store_with_obs):
    store, ids = store_with_obs
    _propose(store, ids, text="Text A.", ts="2026-06-20T10:00:00+00:00")
    p2 = _propose(store, ids, text="Text B.", ts="2026-06-20T11:00:00+00:00")
    accept_proposed_interpretation(p2["id"], "steward-1", "Good.", store)

    queue = staging_queue(store)
    ledger = staging_ledger(store)
    assert queue["pending_count"] == ledger["by_status"]["pending"]


# ── Storage count methods ─────────────────────────────────────────────────────

def test_proposed_interpretation_count_by_status(store_with_obs):
    store, ids = store_with_obs
    p1 = _propose(store, ids, text="Text A.", ts="2026-06-20T10:00:00+00:00")
    p2 = _propose(store, ids, text="Text B.", ts="2026-06-20T11:00:00+00:00")
    accept_proposed_interpretation(p1["id"], "steward-1", "Good.", store)
    reject_proposed_interpretation(p2["id"], "steward-1", "Bad.", store)

    assert store.proposed_interpretation_count() == 2
    assert store.proposed_interpretation_count(status="accepted") == 1
    assert store.proposed_interpretation_count(status="rejected") == 1
    assert store.proposed_interpretation_count(status="pending") == 0


def test_ai_provenance_for_staged_object(store_with_obs):
    store, ids = store_with_obs
    proposal = _propose(store, ids)
    prov = store.ai_provenance_for_staged_object(proposal["id"])
    assert prov is not None
    assert prov["id"] == proposal["ai_provenance_id"]


# ── Two-Table Invariant structural proof ─────────────────────────────────────

def test_ai_provenance_has_no_fk_to_interpretations(store_with_obs):
    """ai_provenance uses staged_object_id as plain TEXT (no FK to proposed_interpretations).

    This avoids a circular FK dependency and enforces the directionality:
    proposed_interpretations → ai_provenance (not the reverse).
    """
    store, _ = store_with_obs
    cols = {row[1] for row in store._conn.execute("PRAGMA table_info(ai_provenance)")}
    assert "staged_object_id" in cols
    assert "interpretation_id" not in cols


def test_proposed_interpretations_fk_to_ai_provenance(store_with_obs):
    """proposed_interpretations.ai_provenance_id is a FK to ai_provenance."""
    store, _ = store_with_obs
    # Verify FK: inserting a proposed_interpretation with nonexistent ai_provenance_id fails.
    import sqlite3
    store._conn.execute("PRAGMA foreign_keys=ON")
    now = datetime.now(timezone.utc).isoformat()
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            """
            INSERT INTO proposed_interpretations
                (id, observation_id, perspective, text, evidential_status,
                 evidence_observation_ids, ai_provenance_id, status,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("fake-pi-id", "fake-obs-id", "literary", "Some text.", "speculative",
             "[]", "nonexistent-prov-id", "pending", now),
        )
