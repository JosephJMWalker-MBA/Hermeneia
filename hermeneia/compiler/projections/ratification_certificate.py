"""
Ratification Certificate projection — Era II Sprint E7.

Human-readable summary of a RatificationRecord and the constitutional state
it captures. Regenerated from RatificationRecord[] — nothing persisted.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def ratification_certificate(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Most recent RatificationRecord for a RenderedNarrative as a readable certificate.

    Returns None in the `certificate` field if no record exists yet.
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
            "ratified": False,
            "certificate": None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    records = conn.execute(
        "SELECT * FROM ratification_records WHERE rendered_narrative_id = ? ORDER BY ratified_at DESC LIMIT 1",
        (rendered_narrative_id,),
    ).fetchone()

    if records is None:
        return {
            "narrative_id": rendered_narrative_id,
            "ratified": False,
            "certificate": None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    snapshot = {}
    try:
        snapshot = json.loads(records["audit_snapshot"])
    except (json.JSONDecodeError, TypeError):
        pass

    certificate = {
        "ratification_id": records["id"],
        "ratified_by": records["ratified_by"],
        "ratified_at": records["ratified_at"],
        "steward_declaration": records["steward_declaration"],
        "constitution_version": records["constitution_version"],
        "finding_count": records["finding_count"],
        "steward_decision_count": records["steward_decision_count"],
        "witness_session_count": records["witness_session_count"],
        "findings_by_dimension": snapshot.get("findings_by_dimension", {}),
        "decisions_by_verdict": snapshot.get("decisions_by_verdict", {}),
        "sessions_by_profile": snapshot.get("sessions_by_profile", {}),
        "constitutional_profile": snapshot.get("constitutional_profile"),
    }

    return {
        "narrative_id": rendered_narrative_id,
        "architect_plan_id": narrative["architect_plan_id"],
        "provider": narrative["provider"],
        "ratified": True,
        "certificate": certificate,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
