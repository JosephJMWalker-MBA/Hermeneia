"""
Institutional Memory projection — Era II Sprint E7.

All ratified RenderedNarratives across the store — the body of understanding
that has passed every layer of the epistemic chain.
Regenerated from RatificationRecord[] — nothing persisted.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def institutional_memory(conn: sqlite3.Connection) -> dict:
    """All ratified RenderedNarratives, oldest first.

    Returns the ratified memory projection: machine-evaluated,
    steward-governed, witness-verified, and formally declared. Deleting this
    projection loses no canonical knowledge.
    """
    records = conn.execute(
        """
        SELECT rr.id              AS ratification_id,
               rr.rendered_narrative_id,
               rr.ratified_by,
               rr.ratified_at,
               rr.steward_declaration,
               rr.finding_count,
               rr.steward_decision_count,
               rr.witness_session_count,
               rr.constitution_version,
               rr.audit_snapshot,
               rn.architect_plan_id,
               rn.provider,
               rn.expression_profile_id
        FROM ratification_records rr
        JOIN rendered_narratives rn ON rn.id = rr.rendered_narrative_id
        ORDER BY rr.ratified_at, rr.created_at
        """,
    ).fetchall()

    entries = []
    for r in records:
        snapshot = {}
        try:
            snapshot = json.loads(r["audit_snapshot"])
        except (json.JSONDecodeError, TypeError):
            pass

        entries.append({
            "ratification_id": r["ratification_id"],
            "narrative_id": r["rendered_narrative_id"],
            "architect_plan_id": r["architect_plan_id"],
            "provider": r["provider"],
            "expression_profile_id": r["expression_profile_id"],
            "ratified_by": r["ratified_by"],
            "ratified_at": r["ratified_at"],
            "steward_declaration": r["steward_declaration"],
            "constitution_version": r["constitution_version"],
            "finding_count": r["finding_count"],
            "steward_decision_count": r["steward_decision_count"],
            "witness_session_count": r["witness_session_count"],
            "constitutional_profile": snapshot.get("constitutional_profile"),
        })

    return {
        "total_ratified": len(entries),
        "entries": entries,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
