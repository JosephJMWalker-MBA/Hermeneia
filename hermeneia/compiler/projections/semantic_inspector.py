"""
Semantic Inspector projection — Era II Sprint E4.

Detailed Finding view with parsed evidence and lineage summary.
Regenerated from Finding[] — nothing persisted.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def _parse_evidence(evidence_raw: str) -> dict:
    """Parse Finding evidence JSON; return empty dict on failure."""
    try:
        return json.loads(evidence_raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _lineage_summary(finding_row, conn: sqlite3.Connection) -> dict:
    """Compact lineage for a single Finding."""
    rn_id = finding_row["rendered_narrative_id"]
    rn = conn.execute(
        "SELECT architect_plan_id, provider, expression_profile_id FROM rendered_narratives WHERE id = ?",
        (rn_id,),
    ).fetchone()
    if rn is None:
        return {"rendered_narrative_id": rn_id, "error": "RenderedNarrative not found"}

    plan = conn.execute(
        "SELECT blueprint_id FROM architect_plans WHERE id = ?",
        (rn["architect_plan_id"],),
    ).fetchone()

    blueprint_id = plan["blueprint_id"] if plan else None

    obs_count = 0
    if blueprint_id:
        obs_count = conn.execute(
            """
            SELECT COUNT(DISTINCT bil.interpretation_id) FROM blueprint_interpretation_links bil
            WHERE bil.blueprint_id = ?
            """,
            (blueprint_id,),
        ).fetchone()[0]

    return {
        "rendered_narrative_id": rn_id,
        "architect_plan_id": rn["architect_plan_id"],
        "blueprint_id": blueprint_id,
        "provider": rn["provider"],
        "expression_profile_id": rn["expression_profile_id"],
        "linked_interpretation_count": obs_count,
    }


def semantic_inspector(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Detailed Finding view with evidence and lineage for a RenderedNarrative.

    Returns all Findings with parsed evidence fields and a compact lineage summary.
    Deleting this projection loses no canonical knowledge.
    """
    findings = conn.execute(
        """
        SELECT id, dimension, obligation_id, operation, status, evidence,
               evaluation_method, constitution_version, created_at,
               rendered_narrative_id
        FROM findings
        WHERE rendered_narrative_id = ?
        ORDER BY dimension, created_at
        """,
        (rendered_narrative_id,),
    ).fetchall()

    narrative = conn.execute(
        "SELECT id, architect_plan_id, provider FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()

    if narrative is None:
        return {
            "narrative_id": rendered_narrative_id,
            "error": "RenderedNarrative not found",
            "findings": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    finding_records = []
    for f in findings:
        evidence = _parse_evidence(f["evidence"])
        lineage = _lineage_summary(f, conn)
        finding_records.append({
            "finding_id": f["id"],
            "dimension": f["dimension"],
            "obligation_id": f["obligation_id"],
            "operation": f["operation"],
            "status": f["status"],
            "evaluation_method": f["evaluation_method"],
            "constitution_version": f["constitution_version"],
            "created_at": f["created_at"],
            "evidence": {
                "contract_obligation": evidence.get("contract_obligation"),
                "observed_render": evidence.get("observed_render"),
                "supporting_trace": evidence.get("supporting_trace"),
            },
            "lineage": lineage,
        })

    return {
        "narrative_id": rendered_narrative_id,
        "architect_plan_id": narrative["architect_plan_id"],
        "provider": narrative["provider"],
        "total_findings": len(finding_records),
        "dimensions_present": sorted({f["dimension"] for f in finding_records}),
        "findings": finding_records,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
