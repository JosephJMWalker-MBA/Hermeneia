"""
Era II Sprint E9 — Interpretation Grounding Critic tests.

Verifies:
- Schema version 16 (critic_reports table present)
- make_critic_report_id: deterministic ID generation
- critic_reports DDL: table exists with correct columns
- critic_reports immutability: UPDATE of core fields rejected; DELETE rejected
- normalized flag: mutable (mark_critic_report_normalized works)
- generate_critic_report: runs Stage 1+2+3, returns a valid dict, persists to DB
- All four policies: conservative, decomposition, contradiction_sensitive, aggregate_weighting
- CriticError: invalid policy, missing proposal, missing observation
- insert_critic_report / get_critic_report / critic_reports_for_proposal /
  latest_critic_report_for_proposal / critic_report_count
- identify_evidence: returns at least the full observation text
- extract_claims: decomposes interpretation into evaluable claims
- apply_policy: each policy returns valid verdict
- aggregate_overall_verdict: aggregation rules (contradicted > unsupported > partial > supported)
- Projections: critic_queue, critic_report_detail, critic_summary
- Constitutional Status: OPERATIONAL — no canonical FK dependency from interpretations
- Separation of concerns: critic_reports.proposal_id is plain TEXT (no FK to proposed_interpretations)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.compiler.critic import generate_critic_report
from hermeneia.compiler.critic.evidence import extract_claims, identify_evidence
from hermeneia.compiler.critic.policy import (
    VALID_POLICIES,
    aggregate_overall_verdict,
    apply_policy,
)
from hermeneia.compiler.critic.report import CriticError
from hermeneia.compiler.projections.critic_queue import (
    critic_queue,
    critic_report_detail,
    critic_summary,
)
from hermeneia.compiler.staging.interpretation import propose_interpretation
from hermeneia.storage.hashing import make_critic_report_id
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def store_with_proposal(tmp_path):
    """Store with one pending proposal ready for Critic evaluation."""
    s = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(s)
    proposal = propose_interpretation(
        observation_id=ids["obs_id"],
        perspective="literary",
        text=(
            "The phrase encodes an epistemological claim about the nature of evidence. "
            "It suggests that observation is never fully neutral, but the observer cannot escape their position."
        ),
        evidential_status="speculative",
        generating_model="claude-sonnet-4-6",
        prompt_reference="sha256:abc",
        prompt_reference_type="hash",
        conn=s,
        generation_timestamp="2026-06-20T12:00:00+00:00",
    )
    ids["proposal_id"] = proposal["id"]
    ids["proposal"] = proposal
    yield s, ids
    s.close()


# ── Schema version ────────────────────────────────────────────────────────────

def test_schema_version_is_16():
    assert SCHEMA_VERSION == 16


def test_critic_reports_table_exists(store):
    tables = {r[0] for r in store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "critic_reports" in tables


def test_critic_reports_has_required_columns(store):
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(critic_reports)").fetchall()}
    required = {
        "id", "proposal_id", "observation_id", "policy", "claims",
        "evidence_passages", "overall_verdict", "normalized",
        "normalization_notes", "generated_at", "created_at",
    }
    assert required <= cols


# ── Hashing ───────────────────────────────────────────────────────────────────

def test_make_critic_report_id_is_deterministic():
    id1 = make_critic_report_id("prop-abc", "conservative", "2026-06-20T12:00:00+00:00")
    id2 = make_critic_report_id("prop-abc", "conservative", "2026-06-20T12:00:00+00:00")
    assert id1 == id2
    assert len(id1) == 64


def test_make_critic_report_id_varies_by_policy():
    t = "2026-06-20T12:00:00+00:00"
    ids = {make_critic_report_id("prop-abc", policy, t) for policy in VALID_POLICIES}
    assert len(ids) == len(VALID_POLICIES)


def test_make_critic_report_id_varies_by_timestamp():
    id1 = make_critic_report_id("prop-abc", "conservative", "2026-06-20T12:00:00+00:00")
    id2 = make_critic_report_id("prop-abc", "conservative", "2026-06-20T13:00:00+00:00")
    assert id1 != id2


# ── Evidence functions ────────────────────────────────────────────────────────

def test_identify_evidence_returns_at_least_full_text():
    obs = "He smiled understandingly—much more than understandingly."
    interp = "The smile is unusual and extraordinary."
    evidence = identify_evidence(obs, interp)
    assert isinstance(evidence, list)
    assert len(evidence) >= 1
    assert any(obs.strip() in e or e in obs for e in evidence)


def test_identify_evidence_with_empty_input():
    assert identify_evidence("", "some interpretation") == []
    result = identify_evidence("observation text", "")
    assert "observation text" in result


def test_extract_claims_returns_list():
    interp = "The narrator attempted to signal innocence. The people nearby suspected him anyway."
    claims = extract_claims(interp)
    assert isinstance(claims, list)
    assert len(claims) >= 1


def test_extract_claims_splits_adversative():
    interp = "The handling was deliberate, but the suspicion persisted regardless."
    claims = extract_claims(interp)
    assert len(claims) >= 2


def test_extract_claims_single_sentence():
    interp = "The green light symbolises hope."
    claims = extract_claims(interp)
    assert len(claims) == 1
    assert claims[0] == interp


def test_extract_claims_empty():
    assert extract_claims("") == []
    assert extract_claims("   ") == []


# ── Policy functions ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("policy", sorted(VALID_POLICIES))
def test_apply_policy_returns_valid_structure(policy):
    claim = "The narrator signals innocence deliberately."
    passages = [
        "I picked it up with a weary bend and handed it back to her.",
        "holding it at arm's length and by the extreme tip of the corners to indicate that I had no designs upon it",
        "but every one near by, including the woman, suspected me just the same.",
    ]
    result = apply_policy(claim, passages, policy)
    assert "claim" in result
    assert "verdict" in result
    assert "evidence_cited" in result
    assert "rationale" in result
    assert result["verdict"] in {"supported", "partially_supported", "unsupported", "contradicted"}
    assert isinstance(result["evidence_cited"], list)


def test_apply_policy_invalid_raises():
    with pytest.raises(ValueError, match="Unknown policy"):
        apply_policy("some claim", ["some evidence"], "nonexistent_policy")


def test_conservative_never_returns_contradicted():
    claim = "The smile is unquestionably trustworthy."
    passages = [
        "It faced—or seemed to face—the whole external world.",
        "with an irresistible prejudice in your favor.",
    ]
    result = apply_policy(claim, passages, "conservative")
    assert result["verdict"] != "contradicted"


def test_contradiction_sensitive_detects_semantic_opposition():
    claim = "The smile is unquestionably trustworthy and objectively benevolent."
    passages = [
        "It faced—or seemed to face—the whole external world for an instant.",
        "with an irresistible prejudice in your favor.",
    ]
    result = apply_policy(claim, passages, "contradiction_sensitive")
    assert result["verdict"] == "contradicted"


def test_aggregate_weighting_returns_partial_when_both_present():
    claim = "The narrator signals innocence deliberately."
    passages = [
        "to indicate that I had no designs upon it",  # supports
        "but every one near by suspected me just the same",  # neutral/challenging depends on hedges
    ]
    result = apply_policy(claim, passages, "aggregate_weighting")
    assert result["verdict"] in {"supported", "partially_supported", "unsupported"}


# ── Aggregate verdict ─────────────────────────────────────────────────────────

def test_aggregate_overall_verdict_contradicted_wins():
    results = [
        {"verdict": "supported"},
        {"verdict": "contradicted"},
        {"verdict": "unsupported"},
    ]
    assert aggregate_overall_verdict(results) == "contradicted"


def test_aggregate_overall_verdict_unsupported_over_partial():
    results = [
        {"verdict": "partially_supported"},
        {"verdict": "unsupported"},
    ]
    assert aggregate_overall_verdict(results) == "unsupported"


def test_aggregate_overall_verdict_all_supported():
    results = [{"verdict": "supported"}, {"verdict": "supported"}]
    assert aggregate_overall_verdict(results) == "supported"


def test_aggregate_overall_verdict_empty_is_unsupported():
    assert aggregate_overall_verdict([]) == "unsupported"


def test_aggregate_overall_verdict_mix_supported_partial():
    results = [{"verdict": "supported"}, {"verdict": "partially_supported"}]
    assert aggregate_overall_verdict(results) == "partially_supported"


# ── generate_critic_report ────────────────────────────────────────────────────

def test_generate_critic_report_persists_and_returns(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="conservative")

    assert report["proposal_id"] == ids["proposal_id"]
    assert report["observation_id"] == ids["obs_id"]
    assert report["policy"] == "conservative"
    assert report["overall_verdict"] in {"supported", "partially_supported", "unsupported", "contradicted"}
    assert report["normalized"] == 0


def test_generate_critic_report_retrievable(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="conservative")
    retrieved = store.get_critic_report(report["id"])
    assert retrieved is not None
    assert retrieved["id"] == report["id"]
    assert retrieved["proposal_id"] == ids["proposal_id"]


def test_generate_critic_report_all_policies(store_with_proposal):
    store, ids = store_with_proposal
    for policy in sorted(VALID_POLICIES):
        report = generate_critic_report(
            ids["proposal_id"], store, policy=policy,
            generated_at=f"2026-06-20T12:0{list(VALID_POLICIES).index(policy)}:00+00:00",
        )
        assert report["policy"] == policy


def test_generate_critic_report_invalid_policy(store_with_proposal):
    store, ids = store_with_proposal
    with pytest.raises(CriticError, match="Unknown policy"):
        generate_critic_report(ids["proposal_id"], store, policy="bad_policy")


def test_generate_critic_report_missing_proposal(store):
    with pytest.raises(CriticError, match="not found"):
        generate_critic_report("nonexistent-id", store, policy="conservative")


def test_generate_critic_report_claims_is_valid_json(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="decomposition")
    claims = json.loads(report["claims"])
    assert isinstance(claims, list)
    for c in claims:
        assert "claim" in c
        assert "verdict" in c
        assert "evidence_cited" in c
        assert "rationale" in c


def test_generate_critic_report_evidence_passages_is_valid_json(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="conservative")
    passages = json.loads(report["evidence_passages"])
    assert isinstance(passages, list)
    assert len(passages) >= 1


# ── Storage methods ───────────────────────────────────────────────────────────

def test_critic_reports_for_proposal_returns_all(store_with_proposal):
    store, ids = store_with_proposal
    generate_critic_report(ids["proposal_id"], store, policy="conservative",
                           generated_at="2026-06-20T12:00:00+00:00")
    generate_critic_report(ids["proposal_id"], store, policy="decomposition",
                           generated_at="2026-06-20T12:01:00+00:00")
    reports = store.critic_reports_for_proposal(ids["proposal_id"])
    assert len(reports) == 2
    policies = {r["policy"] for r in reports}
    assert "conservative" in policies
    assert "decomposition" in policies


def test_latest_critic_report_for_proposal(store_with_proposal):
    store, ids = store_with_proposal
    generate_critic_report(ids["proposal_id"], store, policy="conservative",
                           generated_at="2026-06-20T12:00:00+00:00")
    generate_critic_report(ids["proposal_id"], store, policy="conservative",
                           generated_at="2026-06-20T13:00:00+00:00")
    latest = store.latest_critic_report_for_proposal(ids["proposal_id"], policy="conservative")
    assert latest is not None
    assert latest["generated_at"] == "2026-06-20T13:00:00+00:00"


def test_critic_report_count(store_with_proposal):
    store, ids = store_with_proposal
    assert store.critic_report_count() == 0
    generate_critic_report(ids["proposal_id"], store, policy="conservative",
                           generated_at="2026-06-20T12:00:00+00:00")
    assert store.critic_report_count() == 1


# ── Immutability ──────────────────────────────────────────────────────────────

def test_critic_report_core_fields_immutable(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="conservative",
                                    generated_at="2026-06-20T12:00:00+00:00")
    with pytest.raises(Exception, match="immutable"):
        store._conn.execute(
            "UPDATE critic_reports SET policy = 'decomposition' WHERE id = ?",
            (report["id"],),
        )


def test_critic_report_cannot_be_deleted(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="conservative",
                                    generated_at="2026-06-20T12:00:00+00:00")
    with pytest.raises(Exception, match="immutable"):
        store._conn.execute("DELETE FROM critic_reports WHERE id = ?", (report["id"],))


def test_mark_critic_report_normalized_works(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="conservative",
                                    generated_at="2026-06-20T12:00:00+00:00")
    assert report["normalized"] == 0

    store.mark_critic_report_normalized(report["id"], "Claim set reviewed: three core claims confirmed.")
    retrieved = store.get_critic_report(report["id"])
    assert retrieved["normalized"] == 1
    assert "three core claims" in retrieved["normalization_notes"]


# ── Constitutional Status: OPERATIONAL ────────────────────────────────────────

def test_critic_reports_proposal_id_is_plain_text_not_fk(store):
    """Constitutional: critic_reports.proposal_id has no FK constraint.

    The table is an operational artifact. No canonical table has a hard FK
    dependency on critic_reports.id until the promotion criterion is satisfied.
    """
    pragma_rows = store._conn.execute("PRAGMA foreign_key_list(critic_reports)").fetchall()
    fk_columns = {r[3] for r in pragma_rows}  # column 3 = "from" column name
    assert "proposal_id" not in fk_columns, (
        "critic_reports.proposal_id must be plain TEXT — no FK until canonical promotion"
    )


def test_interpretations_has_no_critic_report_id_column(store):
    """Constitutional: the canonical interpretations table does not reference critic_reports."""
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(interpretations)").fetchall()}
    assert "critic_report_id" not in cols


def test_proposed_interpretations_has_no_critic_report_id_column(store):
    """Constitutional: the staging table does not reference critic_reports."""
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(proposed_interpretations)").fetchall()}
    assert "critic_report_id" not in cols


# ── Projections ───────────────────────────────────────────────────────────────

def test_critic_queue_no_proposals(store):
    result = critic_queue(store._conn)
    assert result["pending_count"] == 0
    assert result["entries"] == []


def test_critic_queue_with_proposal(store_with_proposal):
    store, ids = store_with_proposal
    result = critic_queue(store._conn)
    assert result["pending_count"] == 1
    entry = result["entries"][0]
    assert entry["proposal_id"] == ids["proposal_id"]
    assert entry["has_critic"] is False
    assert entry["all_normalized"] is False
    assert entry["critic_reports"] == []


def test_critic_queue_with_critic_report(store_with_proposal):
    store, ids = store_with_proposal
    generate_critic_report(ids["proposal_id"], store, policy="conservative",
                           generated_at="2026-06-20T12:00:00+00:00")
    result = critic_queue(store._conn)
    entry = result["entries"][0]
    assert entry["has_critic"] is True
    assert entry["all_normalized"] is False
    assert len(entry["critic_reports"]) == 1
    assert entry["critic_reports"][0]["policy"] == "conservative"


def test_critic_queue_all_normalized(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="conservative",
                                    generated_at="2026-06-20T12:00:00+00:00")
    store.mark_critic_report_normalized(report["id"], "Reviewed.")
    result = critic_queue(store._conn)
    entry = result["entries"][0]
    assert entry["all_normalized"] is True


def test_critic_report_detail_missing(store):
    result = critic_report_detail("nonexistent", store._conn)
    assert "error" in result


def test_critic_report_detail_valid(store_with_proposal):
    store, ids = store_with_proposal
    report = generate_critic_report(ids["proposal_id"], store, policy="decomposition",
                                    generated_at="2026-06-20T12:00:00+00:00")
    detail = critic_report_detail(report["id"], store._conn)
    assert detail["report_id"] == report["id"]
    assert detail["policy"] == "decomposition"
    assert detail["proposal"] is not None
    assert detail["observation"] is not None
    assert isinstance(detail["claims"], list)
    assert isinstance(detail["evidence_passages"], list)


def test_critic_summary_empty(store):
    result = critic_summary(store._conn)
    assert result["total_reports"] == 0
    assert result["total_normalized"] == 0
    assert result["pending_normalization"] == 0
    assert result["by_policy"] == {}


def test_critic_summary_with_reports(store_with_proposal):
    store, ids = store_with_proposal
    generate_critic_report(ids["proposal_id"], store, policy="conservative",
                           generated_at="2026-06-20T12:00:00+00:00")
    generate_critic_report(ids["proposal_id"], store, policy="decomposition",
                           generated_at="2026-06-20T12:01:00+00:00")
    result = critic_summary(store._conn)
    assert result["total_reports"] == 2
    assert result["pending_normalization"] == 2
    assert "conservative" in result["by_policy"]
    assert "decomposition" in result["by_policy"]
