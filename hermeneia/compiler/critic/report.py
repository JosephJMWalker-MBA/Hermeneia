"""Stage 1 + 2 + 3 orchestration: generate a CriticReport.

Produces one CriticReport per (proposal_id, observation_id, policy) run.
The report is written as an operational artifact (immutable, not yet canonical).

Constitutional Status: OPERATIONAL — see CONSTITUTIONAL_COMPLIANCE.md.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ...storage.hashing import make_critic_report_id
from .evidence import extract_claims, identify_evidence
from .policy import VALID_POLICIES, aggregate_overall_verdict, apply_policy


class CriticError(Exception):
    """Raised when pre-conditions for a CriticReport are not satisfied."""


def generate_critic_report(
    proposal_id: str,
    conn,
    *,
    policy: str = "conservative",
    generated_at: str | None = None,
) -> dict:
    """Generate and persist a CriticReport for a ProposedInterpretation.

    Retrieves the proposal and its parent observation, runs Stage 1 (evidence
    identification), Stage 2 (claim extraction), and Stage 3 (verdict classification)
    under the named policy.

    The resulting CriticReport is written to critic_reports as an operational artifact.
    normalized=0 on all new reports — steward claim review is required before
    treating claim verdicts as authoritative (Experiment 008 finding).

    Returns the persisted critic_report dict.

    Raises CriticError if:
    - proposal not found
    - observation not found
    - policy is not a valid policy name
    """
    if policy not in VALID_POLICIES:
        raise CriticError(f"Unknown policy {policy!r}. Valid: {sorted(VALID_POLICIES)}")

    proposal = conn.get_proposed_interpretation(proposal_id)
    if proposal is None:
        raise CriticError(f"ProposedInterpretation {proposal_id!r} not found")

    observation = conn.get_observation_by_id(proposal["observation_id"])
    if observation is None:
        raise CriticError(f"Observation {proposal['observation_id']!r} not found")

    now = datetime.now(timezone.utc).isoformat()
    ts = generated_at or now
    report_id = make_critic_report_id(proposal_id, policy, ts)

    obs_text: str = observation["raw_text"]
    interp_text: str = proposal["text"]

    # Stage 1: Evidence Identification
    evidence_passages: list[str] = identify_evidence(obs_text, interp_text)

    # Stage 2: Claim Extraction
    claims: list[str] = extract_claims(interp_text)

    # Stage 3: Verdict Classification under named policy
    claim_results: list[dict] = [
        apply_policy(claim, evidence_passages, policy)
        for claim in claims
    ]

    overall_verdict: str = aggregate_overall_verdict(claim_results)

    row = {
        "id": report_id,
        "proposal_id": proposal_id,
        "observation_id": proposal["observation_id"],
        "policy": policy,
        "claims": json.dumps(claim_results),
        "evidence_passages": json.dumps(evidence_passages),
        "overall_verdict": overall_verdict,
        "normalized": 0,
        "normalization_notes": None,
        "generated_at": ts,
        "created_at": now,
    }

    conn.insert_critic_report(row)
    return row
