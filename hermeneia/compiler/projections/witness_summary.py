"""
Witness Summary projection — Era II Sprint E6.

Aggregate view of WitnessSessions for a RenderedNarrative.
Answers: across all audience profiles tested, how many sessions succeeded?
Regenerated from WitnessSession[] — nothing persisted.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def witness_summary(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Aggregate WitnessSession outcomes for a RenderedNarrative.

    Returns total session counts, completion rates, and a breakdown by
    witness_profile. Deleting this projection loses no canonical knowledge.
    """
    narrative = conn.execute(
        "SELECT id, architect_plan_id, provider FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()

    if narrative is None:
        return {
            "narrative_id": rendered_narrative_id,
            "error": "RenderedNarrative not found",
            "total_sessions": 0,
            "completed": 0,
            "not_completed": 0,
            "by_profile": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    sessions = conn.execute(
        "SELECT witness_profile, task_completed FROM witness_sessions WHERE rendered_narrative_id = ?",
        (rendered_narrative_id,),
    ).fetchall()

    completed = sum(1 for s in sessions if s["task_completed"])
    not_completed = len(sessions) - completed

    by_profile: dict[str, dict] = {}
    for s in sessions:
        profile = s["witness_profile"]
        if profile not in by_profile:
            by_profile[profile] = {"total": 0, "completed": 0, "not_completed": 0}
        by_profile[profile]["total"] += 1
        if s["task_completed"]:
            by_profile[profile]["completed"] += 1
        else:
            by_profile[profile]["not_completed"] += 1

    return {
        "narrative_id": rendered_narrative_id,
        "architect_plan_id": narrative["architect_plan_id"],
        "provider": narrative["provider"],
        "total_sessions": len(sessions),
        "completed": completed,
        "not_completed": not_completed,
        "by_profile": by_profile,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
