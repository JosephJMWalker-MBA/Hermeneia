"""
Witness Layer — Era II Sprint E6.

Records irreducible human understanding verification acts (WitnessSessions).

A WitnessSession answers: did the intended understanding reach this audience?

It is orthogonal to StewardDecision:
  - StewardDecision evaluates machine output (was this Finding acceptable?)
  - WitnessSession verifies human reception (did the understanding arrive?)

Both are irreducible. Neither can be regenerated from any deterministic function.
Both are immutable once written. Both point to canonical objects; those objects
do not point back.

Constitutional basis: Axiom 12 (Three Domains of Verification), CI-014, CI-015.
"This is intentionally not reducible to computation." — Roadmap, Sprint E6.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from hermeneia.storage.hashing import make_witness_session_id

CONSTITUTION_VERSION = "1.0"


def record_witness_session(
    rendered_narrative_id: str,
    witness_profile: str,
    task_description: str,
    task_completed: bool,
    facilitated_by: str,
    conn: sqlite3.Connection,
    *,
    notes: str | None = None,
    session_date: str | None = None,
    constitution_version: str = CONSTITUTION_VERSION,
) -> dict:
    """Record a WitnessSession for a RenderedNarrative.

    Returns the session dict. Raises ValueError for invalid inputs.
    The RenderedNarrative is not mutated; this creates an independent
    understanding verification record that references it.

    witness_profile: audience description, e.g. "8-year-old", "80-year-old",
        "medical patient", "first-generation voter". Free text — domain-specific.
    task_description: what the witness was asked to do or demonstrate.
    task_completed: True if the witness completed the task without assistance.
    facilitated_by: identity of the session facilitator.
    notes: optional human-authored facilitation observations.
    """
    if not witness_profile or not witness_profile.strip():
        raise ValueError("witness_profile must be non-empty")
    if not task_description or not task_description.strip():
        raise ValueError("task_description must be non-empty")
    if not facilitated_by or not facilitated_by.strip():
        raise ValueError("facilitated_by must be non-empty")

    row = conn.execute(
        "SELECT id FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"RenderedNarrative '{rendered_narrative_id}' does not exist")

    now = datetime.now(timezone.utc).isoformat()
    date = session_date or now[:10]  # YYYY-MM-DD

    session_id = make_witness_session_id(rendered_narrative_id, witness_profile.strip(), date)

    session = {
        "id": session_id,
        "rendered_narrative_id": rendered_narrative_id,
        "witness_profile": witness_profile.strip(),
        "task_description": task_description.strip(),
        "task_completed": 1 if task_completed else 0,
        "notes": notes.strip() if notes and notes.strip() else None,
        "facilitated_by": facilitated_by.strip(),
        "session_date": date,
        "constitution_version": constitution_version,
        "created_at": now,
    }

    conn.execute(
        """
        INSERT OR IGNORE INTO witness_sessions
            (id, rendered_narrative_id, witness_profile, task_description,
             task_completed, notes, facilitated_by, session_date,
             constitution_version, created_at)
        VALUES
            (:id, :rendered_narrative_id, :witness_profile, :task_description,
             :task_completed, :notes, :facilitated_by, :session_date,
             :constitution_version, :created_at)
        """,
        session,
    )
    conn.commit()
    return session
