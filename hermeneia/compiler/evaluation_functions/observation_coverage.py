"""
Observation Coverage Evaluation Function — ADR-0042, Era II Sprint E3.

For every required_observation per paragraph, checks whether any 6-word
window from the observation's raw_text appears in the rendered narrative.

Necessary but not sufficient for semantic fidelity (acknowledged limitation,
ADR-0042). Named "observation_coverage" not "semantic" to preserve constitutional
honesty about what deterministic methods can prove.

Zero LLM. Deterministic. Read-only. Orthogonal.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from hermeneia.storage.hashing import make_finding_id, make_obligation_id

# ── Constitutional contract ───────────────────────────────────────────────────
dimension = "observation_coverage"
scope = ["required_observations"]
guarantees = ["deterministic", "complete", "read_only", "orthogonal", "zero_llm"]

# ── Internal constants ────────────────────────────────────────────────────────
DIMENSION = dimension
EVALUATION_METHOD = "observation_coverage-v1.0"
WINDOW_SIZE = 6  # minimum word window to avoid false positives from common phrases

CONSTITUTIONAL_PROFILE = {
    "constitution_version": "1.0.0",
    "authority_index_version": "1.0.0",
    "invariant_profile": "CI-001..CI-016",
    "architecture_profile": "v1.0",
    "adr": "ADR-0042",
}


def _text_windows(text: str, n: int) -> list[str]:
    """Return all n-word lowercased windows from text."""
    words = text.lower().split()
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def _find_coverage(obs_raw: str, narrative: str) -> tuple[bool, str | None]:
    """Return (covered, matched_window). Covered if any window found."""
    narrative_lower = narrative.lower()
    for window in _text_windows(obs_raw, WINDOW_SIZE):
        if window and window in narrative_lower:
            idx = narrative_lower.find(window)
            start = max(0, idx - 15)
            end = min(len(narrative), idx + len(window) + 15)
            return True, narrative[start:end]
    return False, None


def evaluate_observation_coverage(
    rendered_narrative_id: str,
    architect_plan_id: str,
    conn: sqlite3.Connection,
) -> list[dict]:
    """Run the Observation Coverage Evaluation Function.

    For every required_observation per paragraph: one Finding.
    """
    now = datetime.now(timezone.utc).isoformat()

    narrative_row = conn.execute(
        "SELECT id, architect_plan_id, text FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()
    if narrative_row is None:
        raise ValueError(f"RenderedNarrative not found: {rendered_narrative_id}")
    if narrative_row["architect_plan_id"] != architect_plan_id:
        raise ValueError(
            f"RenderedNarrative {rendered_narrative_id} belongs to plan "
            f"{narrative_row['architect_plan_id']}, not {architect_plan_id}"
        )
    narrative_text = narrative_row["text"] or ""

    paragraphs = conn.execute(
        "SELECT order_idx, required_observations FROM architect_plan_paragraphs "
        "WHERE plan_id = ? ORDER BY order_idx",
        (architect_plan_id,),
    ).fetchall()
    if not paragraphs:
        raise ValueError(f"No paragraphs found for plan: {architect_plan_id}")

    findings: list[dict] = []

    for para in paragraphs:
        order_idx: int = para["order_idx"]
        obs_ids: list[str] = json.loads(para["required_observations"] or "[]")

        for obs_id in obs_ids:
            obligation_id = make_obligation_id(
                dimension=DIMENSION,
                plan_id=architect_plan_id,
                paragraph_order_idx=order_idx,
                term_text=obs_id,
            )
            finding_id = make_finding_id(rendered_narrative_id, DIMENSION, obligation_id)

            obs_row = conn.execute(
                "SELECT raw_text FROM observations WHERE id = ?", (obs_id,)
            ).fetchone()

            if obs_row is None:
                covered, matched = False, None
                obs_raw = None
            else:
                obs_raw = obs_row["raw_text"] or ""
                covered, matched = _find_coverage(obs_raw, narrative_text)

            evidence = json.dumps({
                "contract_obligation": obs_id,
                "observed_render": matched,
                "supporting_trace": [rendered_narrative_id, architect_plan_id, f"paragraph:{order_idx}", obs_id],
            }, ensure_ascii=True)

            findings.append({
                "id": finding_id,
                "rendered_narrative_id": rendered_narrative_id,
                "architect_plan_id": architect_plan_id,
                "dimension": DIMENSION,
                "obligation_id": obligation_id,
                "operation": "preservation" if covered else "omission",
                "status": "preserved" if covered else "omitted",
                "evidence": evidence,
                "evaluation_method": EVALUATION_METHOD,
                "constitution_version": json.dumps(CONSTITUTIONAL_PROFILE, sort_keys=True),
                "created_at": now,
            })

    obligations_in_scope = sum(
        len(json.loads(p["required_observations"] or "[]")) for p in paragraphs
    )
    if len(findings) != obligations_in_scope:
        raise RuntimeError(
            f"Completeness Invariant violated: expected {obligations_in_scope} findings, "
            f"produced {len(findings)}"
        )

    return findings
