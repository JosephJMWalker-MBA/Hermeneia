"""
Steward Ledger projection — Era II Sprint E5.

All StewardDecisions for a RenderedNarrative, joined with their Finding context.
Regenerated from Finding[] and StewardDecision[] — nothing persisted.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def steward_ledger(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """All StewardDecisions for Findings produced from a RenderedNarrative.

    Joins each StewardDecision with the Finding it governs.
    Deleting this projection loses no canonical knowledge.
    """
    narrative = conn.execute(
        "SELECT id, architect_plan_id, provider FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()

    if narrative is None:
        return {
            "narrative_id": rendered_narrative_id,
            "error": "RenderedNarrative not found",
            "decisions": [],
            "decision_count": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    rows = conn.execute(
        """
        SELECT sd.id          AS decision_id,
               sd.finding_id,
               sd.verdict,
               sd.rationale,
               sd.steward_id,
               sd.decided_at,
               sd.constitution_version,
               sd.created_at  AS decision_created_at,
               f.dimension,
               f.obligation_id,
               f.status       AS finding_status,
               f.operation    AS finding_operation,
               f.evaluation_method
        FROM steward_decisions sd
        JOIN findings f ON f.id = sd.finding_id
        WHERE f.rendered_narrative_id = ?
        ORDER BY sd.decided_at, sd.created_at
        """,
        (rendered_narrative_id,),
    ).fetchall()

    by_verdict: dict[str, int] = {"accepted": 0, "rejected": 0, "deferred": 0}
    for r in rows:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1

    return {
        "narrative_id": rendered_narrative_id,
        "architect_plan_id": narrative["architect_plan_id"],
        "provider": narrative["provider"],
        "decisions": [dict(r) for r in rows],
        "decision_count": len(rows),
        "by_verdict": by_verdict,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
