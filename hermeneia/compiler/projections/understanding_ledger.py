"""
Understanding Ledger projection — Era II Sprint E6.

Detailed view of all WitnessSessions for a RenderedNarrative with full session
records and narrative context.
Regenerated from WitnessSession[] — nothing persisted.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def understanding_ledger(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Detailed WitnessSession view for a RenderedNarrative.

    Returns each session with all fields for human inspection.
    Deleting this projection loses no canonical knowledge.
    """
    narrative = conn.execute(
        "SELECT id, architect_plan_id, provider, expression_profile_id FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()

    if narrative is None:
        return {
            "narrative_id": rendered_narrative_id,
            "error": "RenderedNarrative not found",
            "sessions": [],
            "session_count": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    rows = conn.execute(
        """
        SELECT id, witness_profile, task_description, task_completed,
               notes, facilitated_by, session_date, constitution_version, created_at
        FROM witness_sessions
        WHERE rendered_narrative_id = ?
        ORDER BY session_date, created_at
        """,
        (rendered_narrative_id,),
    ).fetchall()

    sessions = [
        {
            "session_id": r["id"],
            "witness_profile": r["witness_profile"],
            "task_description": r["task_description"],
            "task_completed": bool(r["task_completed"]),
            "notes": r["notes"],
            "facilitated_by": r["facilitated_by"],
            "session_date": r["session_date"],
            "constitution_version": r["constitution_version"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    profiles_tested = sorted({s["witness_profile"] for s in sessions})

    return {
        "narrative_id": rendered_narrative_id,
        "architect_plan_id": narrative["architect_plan_id"],
        "provider": narrative["provider"],
        "expression_profile_id": narrative["expression_profile_id"],
        "sessions": sessions,
        "session_count": len(sessions),
        "profiles_tested": profiles_tested,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
