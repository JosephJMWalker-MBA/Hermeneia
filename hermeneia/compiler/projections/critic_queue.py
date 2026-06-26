"""Critic Queue projection — Sprint E9.

Shows pending proposed interpretations that have been run through the Interpretation
Grounding Critic, with their CriticReport verdicts. A pure projection — disposable
and regenerable from canonical staging state + critic_reports.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def critic_queue(conn: sqlite3.Connection) -> dict:
    """Pending proposals and their CriticReport verdicts (one per policy, most recent).

    Each entry shows:
    - proposal_id, observation_id, perspective, text (excerpt)
    - critic_reports: list of {report_id, policy, overall_verdict, normalized}
    - has_critic: bool
    - all_normalized: bool (True only if at least one report and all are normalized)
    """
    pending_rows = conn.execute(
        """
        SELECT pi.id AS proposal_id, pi.observation_id, pi.perspective,
               pi.text, pi.created_at AS proposed_at
        FROM proposed_interpretations pi
        WHERE pi.status = 'pending'
        ORDER BY pi.created_at
        """,
    ).fetchall()

    entries = []
    for row in pending_rows:
        proposal_id = row["proposal_id"]
        reports_raw = conn.execute(
            """
            SELECT id, policy, overall_verdict, normalized, generated_at
            FROM critic_reports
            WHERE proposal_id = ?
            ORDER BY policy, generated_at DESC
            """,
            (proposal_id,),
        ).fetchall()

        # Deduplicate: keep most recent report per policy
        seen_policies: set[str] = set()
        reports = []
        for r in reports_raw:
            if r["policy"] not in seen_policies:
                seen_policies.add(r["policy"])
                reports.append({
                    "report_id": r["id"],
                    "policy": r["policy"],
                    "overall_verdict": r["overall_verdict"],
                    "normalized": bool(r["normalized"]),
                    "generated_at": r["generated_at"],
                })

        has_critic = bool(reports)
        all_normalized = has_critic and all(r["normalized"] for r in reports)

        entries.append({
            "proposal_id": proposal_id,
            "observation_id": row["observation_id"],
            "perspective": row["perspective"],
            "text_excerpt": row["text"][:120] + ("…" if len(row["text"]) > 120 else ""),
            "proposed_at": row["proposed_at"],
            "critic_reports": reports,
            "has_critic": has_critic,
            "all_normalized": all_normalized,
        })

    return {
        "pending_count": len(entries),
        "entries": entries,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def critic_report_detail(report_id: str, conn: sqlite3.Connection) -> dict:
    """Full detail for a single CriticReport, including claim-level verdicts.

    Returns the report plus the proposal text and observation text for context.
    """
    report = conn.execute(
        "SELECT * FROM critic_reports WHERE id = ?", (report_id,)
    ).fetchone()
    if report is None:
        return {
            "report_id": report_id,
            "error": "CriticReport not found",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    report = dict(report)
    claims = json.loads(report.get("claims", "[]"))
    evidence_passages = json.loads(report.get("evidence_passages", "[]"))

    proposal = conn.execute(
        "SELECT id, observation_id, perspective, text, status FROM proposed_interpretations WHERE id = ?",
        (report["proposal_id"],),
    ).fetchone()
    observation = conn.execute(
        "SELECT id, raw_text, source_locator FROM observations WHERE id = ?",
        (report["observation_id"],),
    ).fetchone()

    return {
        "report_id": report_id,
        "proposal_id": report["proposal_id"],
        "observation_id": report["observation_id"],
        "policy": report["policy"],
        "overall_verdict": report["overall_verdict"],
        "normalized": bool(report["normalized"]),
        "normalization_notes": report.get("normalization_notes"),
        "generated_at": report["generated_at"],
        "evidence_passages": evidence_passages,
        "claims": claims,
        "claim_count": len(claims),
        "proposal": dict(proposal) if proposal else None,
        "observation": dict(observation) if observation else None,
        "generated_at_projection": datetime.now(timezone.utc).isoformat(),
    }


def critic_summary(conn: sqlite3.Connection) -> dict:
    """Summary statistics for all CriticReports by policy and verdict.

    Pure projection — disposable and regenerable.
    """
    rows = conn.execute(
        """
        SELECT policy, overall_verdict, COUNT(*) AS count,
               SUM(normalized) AS normalized_count
        FROM critic_reports
        GROUP BY policy, overall_verdict
        ORDER BY policy, overall_verdict
        """,
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM critic_reports").fetchone()[0]
    total_normalized = conn.execute(
        "SELECT COUNT(*) FROM critic_reports WHERE normalized = 1"
    ).fetchone()[0]

    by_policy: dict[str, dict] = {}
    for row in rows:
        p = row["policy"]
        if p not in by_policy:
            by_policy[p] = {"verdicts": {}, "normalized": 0, "total": 0}
        by_policy[p]["verdicts"][row["overall_verdict"]] = row["count"]
        by_policy[p]["normalized"] += row["normalized_count"]
        by_policy[p]["total"] += row["count"]

    return {
        "total_reports": total,
        "total_normalized": total_normalized,
        "pending_normalization": total - total_normalized,
        "by_policy": by_policy,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
