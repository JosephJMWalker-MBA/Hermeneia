"""
Ratification Layer — Era II Sprint E7.

Creates immutable RatificationRecords — the terminal canonical object in the
epistemic chain.

The question Ratification answers: Shall this become institutional memory?

Constitutional pre-conditions (all three must be satisfied):
  1. At least one Finding exists — machine evaluation happened.
  2. Every Finding has at least one StewardDecision — governance happened.
  3. At least one WitnessSession exists — understanding reached an audience.

If any pre-condition fails, ratification is premature and raises RatificationError.

The audit_snapshot captures the full constitutional state as an immutable JSON
document at the moment of ratification. It is not a projection — it is the
permanent record of what was true when the steward declared.

Epistemic chain:
    Finding (what changed?)
        ↓
    StewardDecision (should this stand?)
        ↓
    WitnessSession (did understanding reach people?)
        ↓
    RatificationRecord (shall this become institutional memory?)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from hermeneia.storage.hashing import make_ratification_record_id

CONSTITUTION_VERSION = "1.0"


class RatificationError(Exception):
    """Raised when a pre-condition for ratification is not satisfied."""


def _build_audit_snapshot(
    rendered_narrative_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Capture the full constitutional state for the audit snapshot."""
    findings = conn.execute(
        "SELECT id, dimension, status, operation FROM findings WHERE rendered_narrative_id = ?",
        (rendered_narrative_id,),
    ).fetchall()

    decisions = conn.execute(
        """
        SELECT sd.id, sd.verdict, sd.finding_id FROM steward_decisions sd
        JOIN findings f ON f.id = sd.finding_id
        WHERE f.rendered_narrative_id = ?
        """,
        (rendered_narrative_id,),
    ).fetchall()

    sessions = conn.execute(
        "SELECT id, witness_profile, task_completed FROM witness_sessions WHERE rendered_narrative_id = ?",
        (rendered_narrative_id,),
    ).fetchall()

    findings_by_status: dict[str, int] = {}
    findings_by_dimension: dict[str, int] = {}
    for f in findings:
        findings_by_status[f["status"]] = findings_by_status.get(f["status"], 0) + 1
        findings_by_dimension[f["dimension"]] = findings_by_dimension.get(f["dimension"], 0) + 1

    decisions_by_verdict: dict[str, int] = {}
    for d in decisions:
        decisions_by_verdict[d["verdict"]] = decisions_by_verdict.get(d["verdict"], 0) + 1

    sessions_by_profile: dict[str, dict] = {}
    for s in sessions:
        p = s["witness_profile"]
        if p not in sessions_by_profile:
            sessions_by_profile[p] = {"total": 0, "completed": 0, "not_completed": 0}
        sessions_by_profile[p]["total"] += 1
        if s["task_completed"]:
            sessions_by_profile[p]["completed"] += 1
        else:
            sessions_by_profile[p]["not_completed"] += 1

    # Extract constitutional profile from execution_config
    narrative = conn.execute(
        "SELECT execution_config FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()
    constitutional_profile = None
    if narrative and narrative["execution_config"]:
        try:
            ec = json.loads(narrative["execution_config"])
            constitutional_profile = ec.get("constitutional_profile")
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "finding_count": len(findings),
        "findings_by_status": findings_by_status,
        "findings_by_dimension": findings_by_dimension,
        "steward_decision_count": len(decisions),
        "decisions_by_verdict": decisions_by_verdict,
        "witness_session_count": len(sessions),
        "sessions_by_profile": sessions_by_profile,
        "constitutional_profile": constitutional_profile,
    }


def _check_preconditions(
    rendered_narrative_id: str,
    snapshot: dict,
    conn: sqlite3.Connection,
) -> None:
    """Raise RatificationError if any pre-condition is not satisfied."""
    if snapshot["finding_count"] == 0:
        raise RatificationError(
            "Ratification requires at least one Finding. "
            "Machine evaluation has not been performed for this narrative."
        )

    # Every Finding must have at least one StewardDecision
    undecided = conn.execute(
        """
        SELECT COUNT(*) FROM findings f
        WHERE f.rendered_narrative_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM steward_decisions sd WHERE sd.finding_id = f.id
          )
        """,
        (rendered_narrative_id,),
    ).fetchone()[0]
    if undecided > 0:
        raise RatificationError(
            f"Ratification requires every Finding to have at least one StewardDecision. "
            f"{undecided} Finding(s) remain undecided. "
            "Complete steward review before ratifying."
        )

    if snapshot["witness_session_count"] == 0:
        raise RatificationError(
            "Ratification requires at least one WitnessSession. "
            "Human understanding verification has not been performed for this narrative."
        )


def create_ratification_record(
    rendered_narrative_id: str,
    ratified_by: str,
    steward_declaration: str,
    conn: sqlite3.Connection,
    *,
    ratified_at: str | None = None,
    constitution_version: str = CONSTITUTION_VERSION,
) -> dict:
    """Create a RatificationRecord for a RenderedNarrative.

    Raises RatificationError if any pre-condition is not satisfied.
    Raises ValueError for invalid inputs.
    Returns the record dict. The record is immutable once written.

    ratified_by: steward identity making the ratification declaration.
    steward_declaration: the steward's formal statement of ratification.
    """
    if not ratified_by or not ratified_by.strip():
        raise ValueError("ratified_by must be non-empty")
    if not steward_declaration or not steward_declaration.strip():
        raise ValueError("steward_declaration must be non-empty")

    row = conn.execute(
        "SELECT id FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"RenderedNarrative '{rendered_narrative_id}' does not exist")

    snapshot = _build_audit_snapshot(rendered_narrative_id, conn)
    _check_preconditions(rendered_narrative_id, snapshot, conn)

    now = datetime.now(timezone.utc).isoformat()
    ts = ratified_at or now

    record_id = make_ratification_record_id(rendered_narrative_id, ratified_by.strip(), ts)

    record = {
        "id": record_id,
        "rendered_narrative_id": rendered_narrative_id,
        "ratified_by": ratified_by.strip(),
        "ratified_at": ts,
        "steward_declaration": steward_declaration.strip(),
        "finding_count": snapshot["finding_count"],
        "steward_decision_count": snapshot["steward_decision_count"],
        "witness_session_count": snapshot["witness_session_count"],
        "constitution_version": constitution_version,
        "audit_snapshot": json.dumps(snapshot, sort_keys=True),
        "created_at": now,
    }

    conn.execute(
        """
        INSERT OR IGNORE INTO ratification_records
            (id, rendered_narrative_id, ratified_by, ratified_at,
             steward_declaration, finding_count, steward_decision_count,
             witness_session_count, constitution_version, audit_snapshot, created_at)
        VALUES
            (:id, :rendered_narrative_id, :ratified_by, :ratified_at,
             :steward_declaration, :finding_count, :steward_decision_count,
             :witness_session_count, :constitution_version, :audit_snapshot, :created_at)
        """,
        record,
    )
    conn.commit()
    return record
