"""
Stewardship Layer — Era II Sprint E5.

Records irreducible human governance acts (StewardDecisions) against canonical Findings.

Constitutional constraint (Projection Sufficiency Theorem, Architecture_Proofs.md):
    StewardDecision.finding_id → findings.id
    Finding has no steward_decision_id column.
    The governance layer annotates itself; it does not annotate the machine layer.

A StewardDecision is immutable once written. A changed mind creates a new
StewardDecision and links the old to the new via supersession_relations.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from hermeneia.storage.hashing import make_steward_decision_id

VERDICTS = frozenset({"accepted", "rejected", "deferred"})

CONSTITUTION_VERSION = "1.0"


def record_steward_decision(
    finding_id: str,
    verdict: str,
    rationale: str,
    steward_id: str,
    conn: sqlite3.Connection,
    *,
    decided_at: str | None = None,
    constitution_version: str = CONSTITUTION_VERSION,
) -> dict:
    """Record a StewardDecision for a Finding.

    Returns the decision dict. Raises ValueError for invalid inputs.
    The Finding is not mutated; this creates an independent governance record
    that references it.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VERDICTS)}, got '{verdict}'")
    if not rationale or not rationale.strip():
        raise ValueError("rationale must be non-empty")
    if not steward_id or not steward_id.strip():
        raise ValueError("steward_id must be non-empty")

    # Verify the Finding exists before recording a decision about it
    row = conn.execute("SELECT id FROM findings WHERE id = ?", (finding_id,)).fetchone()
    if row is None:
        raise ValueError(f"Finding '{finding_id}' does not exist")

    now = datetime.now(timezone.utc).isoformat()
    ts = decided_at or now

    decision_id = make_steward_decision_id(finding_id, verdict, ts)

    decision = {
        "id": decision_id,
        "finding_id": finding_id,
        "verdict": verdict,
        "rationale": rationale.strip(),
        "steward_id": steward_id.strip(),
        "decided_at": ts,
        "constitution_version": constitution_version,
        "created_at": now,
    }

    conn.execute(
        """
        INSERT OR IGNORE INTO steward_decisions
            (id, finding_id, verdict, rationale, steward_id,
             decided_at, constitution_version, created_at)
        VALUES
            (:id, :finding_id, :verdict, :rationale, :steward_id,
             :decided_at, :constitution_version, :created_at)
        """,
        decision,
    )
    conn.commit()
    return decision
