"""Staging workflow for AI-proposed Interpretations (Sprint E8, ADR-0009).

Constitutional note:
    A proposed interpretation is not an interpretation with lower confidence.
    It is a different constitutional state.

    proposed_interpretations → (steward accepts) → interpretations
    proposed_interpretations → (steward rejects) → remains in staging forever

Two canonical objects are created or updated during acceptance:
    1. proposed_interpretations.status → 'accepted'
    2. ai_provenance.accepting_steward / acceptance_timestamp / acceptance_rationale populated
    3. interpretations: new canonical row inserted (INSERT OR IGNORE)

Rejection only updates the staging row. The ai_provenance acceptance fields remain NULL.
Rejected objects are never deleted (ADR-0009).
"""
import json
from datetime import datetime, timezone

from ...storage.hashing import (
    make_ai_provenance_id,
    make_interpretation_id,
    make_proposed_interpretation_id,
)

CONSTITUTION_VERSION = "ADR-0009-v1.0"
_VALID_EVIDENTIAL_STATUSES = frozenset({"established", "contested", "speculative", "uncertain"})
_VALID_PROMPT_REF_TYPES = frozenset({"template_id", "hash", "full_text"})


class StagingError(Exception):
    """Raised when a staging pre-condition is not satisfied."""


def propose_interpretation(
    observation_id: str,
    perspective: str,
    text: str,
    evidential_status: str,
    generating_model: str,
    prompt_reference: str,
    prompt_reference_type: str,
    conn,
    *,
    model_version: str = "",
    generation_timestamp: str | None = None,
    parent_object_ids: list[str] | None = None,
    generation_parameters: dict | None = None,
    perspective_id: str | None = None,
    evidence_observation_ids: list[str] | None = None,
) -> dict:
    """Stage an AI-generated Interpretation candidate.

    Creates:
    - one ai_provenance record (acceptance fields NULL)
    - one proposed_interpretation record (status='pending')

    Returns the proposed_interpretation dict.
    """
    if not observation_id or not observation_id.strip():
        raise StagingError("observation_id is required")
    if not perspective or not perspective.strip():
        raise StagingError("perspective is required")
    if not text or not text.strip():
        raise StagingError("text is required")
    if evidential_status not in _VALID_EVIDENTIAL_STATUSES:
        raise StagingError(f"evidential_status must be one of {sorted(_VALID_EVIDENTIAL_STATUSES)}")
    if not generating_model or not generating_model.strip():
        raise StagingError("generating_model is required")
    if not prompt_reference or not prompt_reference.strip():
        raise StagingError("prompt_reference is required")
    if prompt_reference_type not in _VALID_PROMPT_REF_TYPES:
        raise StagingError(f"prompt_reference_type must be one of {sorted(_VALID_PROMPT_REF_TYPES)}")

    # Validate observation exists
    row = conn._conn.execute(
        "SELECT 1 FROM observations WHERE id = ?", (observation_id,)
    ).fetchone()
    if row is None:
        raise StagingError(f"Observation {observation_id!r} not found")

    now = datetime.now(timezone.utc).isoformat()
    gen_ts = generation_timestamp or now

    proposal_id = make_proposed_interpretation_id(
        observation_id, perspective, text, generating_model, gen_ts
    )
    prov_id = make_ai_provenance_id(proposal_id, generating_model, gen_ts)

    provenance = {
        "id": prov_id,
        "staged_object_id": proposal_id,
        "generating_model": generating_model,
        "model_version": model_version,
        "generation_timestamp": gen_ts,
        "prompt_reference": prompt_reference,
        "prompt_reference_type": prompt_reference_type,
        "parent_object_ids": json.dumps(parent_object_ids or []),
        "generation_parameters": json.dumps(generation_parameters or {}),
        "schema_version": CONSTITUTION_VERSION,
        "accepting_steward": None,
        "acceptance_timestamp": None,
        "acceptance_rationale": None,
        "created_at": now,
    }
    conn.insert_ai_provenance(provenance)

    proposal = {
        "id": proposal_id,
        "observation_id": observation_id,
        "perspective": perspective,
        "perspective_id": perspective_id,
        "text": text,
        "evidential_status": evidential_status,
        "evidence_observation_ids": json.dumps(evidence_observation_ids or []),
        "ai_provenance_id": prov_id,
        "status": "pending",
        "steward_id": None,
        "decided_at": None,
        "steward_rationale": None,
        "created_at": now,
    }
    conn.insert_proposed_interpretation(proposal)

    return proposal


def accept_proposed_interpretation(
    proposal_id: str,
    accepting_steward: str,
    acceptance_rationale: str,
    conn,
    *,
    accepted_at: str | None = None,
) -> dict:
    """Accept a staged proposal and promote it to canonical interpretations.

    Three writes in sequence:
    1. proposed_interpretations.status → 'accepted'
    2. ai_provenance acceptance fields populated
    3. interpretations: canonical row inserted (INSERT OR IGNORE)

    Returns the canonical interpretation dict.

    Raises StagingError if:
    - proposal not found
    - proposal is not in 'pending' status
    - accepting_steward is empty
    - acceptance_rationale is empty
    """
    if not accepting_steward or not accepting_steward.strip():
        raise StagingError("accepting_steward is required")
    if not acceptance_rationale or not acceptance_rationale.strip():
        raise StagingError("acceptance_rationale is required")

    proposal = conn.get_proposed_interpretation(proposal_id)
    if proposal is None:
        raise StagingError(f"ProposedInterpretation {proposal_id!r} not found")
    if proposal["status"] != "pending":
        raise StagingError(
            f"ProposedInterpretation {proposal_id!r} is already {proposal['status']!r} — cannot accept"
        )

    now = datetime.now(timezone.utc).isoformat()
    ts = accepted_at or now

    # 1. Mark staging row accepted
    conn.decide_proposed_interpretation(
        proposal_id,
        status="accepted",
        steward_id=accepting_steward,
        decided_at=ts,
        steward_rationale=acceptance_rationale,
    )

    # 2. Complete ai_provenance acceptance record
    conn.complete_ai_provenance_acceptance(
        ai_provenance_id=proposal["ai_provenance_id"],
        accepting_steward=accepting_steward,
        acceptance_timestamp=ts,
        acceptance_rationale=acceptance_rationale,
    )

    # 3. Insert canonical interpretation
    canonical_id = make_interpretation_id(
        proposal["observation_id"], proposal["perspective"], proposal["text"]
    )
    canonical = {
        "id": canonical_id,
        "observation_id": proposal["observation_id"],
        "perspective": proposal["perspective"],
        "perspective_id": proposal["perspective_id"],
        "text": proposal["text"],
        "evidential_status": proposal["evidential_status"],
        "evidence_observation_ids": proposal["evidence_observation_ids"],
        "confidence": "ai-accepted",
        "source": "ai-accepted",
        "ai_provenance_id": proposal["ai_provenance_id"],
        "created_at": ts,
    }
    conn.insert_interpretation_with_provenance(canonical)

    return canonical


def reject_proposed_interpretation(
    proposal_id: str,
    rejecting_steward: str,
    rejection_rationale: str,
    conn,
    *,
    rejected_at: str | None = None,
) -> dict:
    """Reject a staged proposal.

    The proposal remains in the staging table permanently (ADR-0009).
    The ai_provenance acceptance fields remain NULL.
    No canonical interpretation row is created.

    Returns the updated proposed_interpretation dict.

    Raises StagingError if:
    - proposal not found
    - proposal is not in 'pending' status
    - rejecting_steward is empty
    - rejection_rationale is empty
    """
    if not rejecting_steward or not rejecting_steward.strip():
        raise StagingError("rejecting_steward is required")
    if not rejection_rationale or not rejection_rationale.strip():
        raise StagingError("rejection_rationale is required")

    proposal = conn.get_proposed_interpretation(proposal_id)
    if proposal is None:
        raise StagingError(f"ProposedInterpretation {proposal_id!r} not found")
    if proposal["status"] != "pending":
        raise StagingError(
            f"ProposedInterpretation {proposal_id!r} is already {proposal['status']!r} — cannot reject"
        )

    now = datetime.now(timezone.utc).isoformat()
    ts = rejected_at or now

    conn.decide_proposed_interpretation(
        proposal_id,
        status="rejected",
        steward_id=rejecting_steward,
        decided_at=ts,
        steward_rationale=rejection_rationale,
    )

    return conn.get_proposed_interpretation(proposal_id)


def staging_queue(conn) -> dict:
    """Projection: all pending proposed interpretations awaiting steward decision.

    This is a pure projection — disposable, regenerable from canonical staging state.
    """
    pending = conn.pending_proposed_interpretations()
    return {
        "pending_count": len(pending),
        "proposals": pending,
    }


def staging_ledger(conn) -> dict:
    """Projection: all proposed interpretations with their disposition status.

    This is a pure projection — disposable, regenerable from canonical staging state.
    """
    all_proposals = conn.all_proposed_interpretations()
    by_status: dict[str, int] = {"pending": 0, "accepted": 0, "rejected": 0}
    for p in all_proposals:
        by_status[p["status"]] = by_status.get(p["status"], 0) + 1
    return {
        "total": len(all_proposals),
        "by_status": by_status,
        "proposals": all_proposals,
    }
