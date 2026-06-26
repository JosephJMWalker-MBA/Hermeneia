"""
Review Queue projection — Era II Sprint E5.

Findings for a RenderedNarrative that have not yet received a StewardDecision.
Regenerated from Finding[] and StewardDecision[] — nothing persisted.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def review_queue(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Findings awaiting a StewardDecision for a given RenderedNarrative.

    Returns only Findings with zero associated StewardDecisions.
    A decided Finding may still appear if its decision was later superseded
    and the new decision has not yet been recorded — that state is intentional.
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
            "pending": [],
            "pending_count": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    pending = conn.execute(
        """
        SELECT f.id, f.dimension, f.obligation_id, f.status, f.operation,
               f.evaluation_method, f.created_at
        FROM findings f
        WHERE f.rendered_narrative_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM steward_decisions sd WHERE sd.finding_id = f.id
          )
        ORDER BY f.dimension, f.created_at
        """,
        (rendered_narrative_id,),
    ).fetchall()

    return {
        "narrative_id": rendered_narrative_id,
        "architect_plan_id": narrative["architect_plan_id"],
        "provider": narrative["provider"],
        "pending": [dict(r) for r in pending],
        "pending_count": len(pending),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
