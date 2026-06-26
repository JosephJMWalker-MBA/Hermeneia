"""
Trust Card projection — Era II Sprint E4.

Compact compliance summary per dimension and overall.
Regenerated from Finding[] — nothing persisted.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

# Thresholds for dimension-level verdicts
_FAIL_IF_ANY = {"omitted", "not_evaluated"}


def _dimension_verdict(counts: dict) -> str:
    """Return 'pass', 'partial', or 'fail' for one dimension's counts."""
    total = counts.get("total", 0)
    if total == 0:
        return "not_evaluated"
    if counts.get("preserved", 0) == total:
        return "pass"
    if counts.get("omitted", 0) == total:
        return "fail"
    return "partial"


def trust_card(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Compact compliance summary for a RenderedNarrative.

    Returns per-dimension verdicts (pass / partial / fail / not_evaluated)
    and an overall verdict. Deleting this projection loses no canonical knowledge.
    """
    findings = conn.execute(
        "SELECT dimension, status FROM findings WHERE rendered_narrative_id = ?",
        (rendered_narrative_id,),
    ).fetchall()

    narrative = conn.execute(
        "SELECT id, architect_plan_id, provider, expression_profile_id, created_at "
        "FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()

    if narrative is None:
        return {
            "narrative_id": rendered_narrative_id,
            "error": "RenderedNarrative not found",
            "overall": "unknown",
            "dimensions": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    dim_counts: dict[str, dict] = {}
    for f in findings:
        dim = f["dimension"]
        if dim not in dim_counts:
            dim_counts[dim] = {"preserved": 0, "omitted": 0, "transformed": 0,
                               "injected": 0, "not_evaluated": 0, "total": 0}
        dim_counts[dim][f["status"]] += 1
        dim_counts[dim]["total"] += 1

    dimension_verdicts = {dim: _dimension_verdict(counts) for dim, counts in dim_counts.items()}

    verdict_order = {"fail": 0, "partial": 1, "not_evaluated": 2, "pass": 3}
    if not dimension_verdicts:
        overall = "not_evaluated"
    else:
        worst = min(dimension_verdicts.values(), key=lambda v: verdict_order.get(v, 2))
        overall = worst

    return {
        "narrative_id": rendered_narrative_id,
        "architect_plan_id": narrative["architect_plan_id"],
        "provider": narrative["provider"],
        "expression_profile_id": narrative["expression_profile_id"],
        "rendered_at": narrative["created_at"],
        "overall": overall,
        "dimensions": dimension_verdicts,
        "finding_count": len(findings),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
