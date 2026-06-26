"""
Audit Dashboard projection — Era II Sprint E4.

Regenerated from Finding[] and canonical objects.
Nothing persisted. Everything disposable.

Authorized by the Regeneration Principle (Architecture_Patterns.md §1)
and ADR-0041 §7 / ADR-0042.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

OPERATION_STATES = ("preservation", "omission", "transformation", "injection", "not_evaluated")
STATUS_STATES = ("preserved", "omitted", "transformed", "injected", "not_evaluated")


def audit_dashboard(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Regenerate an Audit Dashboard from Finding[] for a given RenderedNarrative.

    Returns a dict grouping Finding counts by dimension and status.
    Deleting this projection loses no canonical knowledge.
    """
    findings = conn.execute(
        "SELECT dimension, status, operation FROM findings WHERE rendered_narrative_id = ?",
        (rendered_narrative_id,),
    ).fetchall()

    narrative = conn.execute(
        "SELECT id, architect_plan_id, provider, expression_profile_id FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()

    if narrative is None:
        return {
            "narrative_id": rendered_narrative_id,
            "error": "RenderedNarrative not found",
            "dimensions": {},
            "total_findings": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    dimensions: dict[str, dict] = {}
    for f in findings:
        dim = f["dimension"]
        if dim not in dimensions:
            dimensions[dim] = {s: 0 for s in STATUS_STATES}
            dimensions[dim]["total"] = 0
        dimensions[dim][f["status"]] += 1
        dimensions[dim]["total"] += 1

    return {
        "narrative_id": rendered_narrative_id,
        "architect_plan_id": narrative["architect_plan_id"],
        "provider": narrative["provider"],
        "expression_profile_id": narrative["expression_profile_id"],
        "dimensions": dimensions,
        "total_findings": len(findings),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
