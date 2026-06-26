"""
Provenance Evaluation Function — ADR-0042, Era II Sprint E3.

For every required_observation in every paragraph, verifies that:
- the observation exists in the database
- a provenance record exists for it

One Finding per required observation per paragraph.
Zero LLM. Deterministic. Read-only. Orthogonal.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from hermeneia.storage.hashing import make_finding_id, make_obligation_id

# ── Constitutional contract ───────────────────────────────────────────────────
dimension = "provenance"
scope = ["required_observations"]
guarantees = ["deterministic", "complete", "read_only", "orthogonal", "zero_llm"]

# ── Internal constants ────────────────────────────────────────────────────────
DIMENSION = dimension
EVALUATION_METHOD = "provenance-v1.0"

CONSTITUTIONAL_PROFILE = {
    "constitution_version": "1.0.0",
    "authority_index_version": "1.0.0",
    "invariant_profile": "CI-001..CI-016",
    "architecture_profile": "v1.0",
    "adr": "ADR-0042",
}


def evaluate_provenance(
    rendered_narrative_id: str,
    architect_plan_id: str,
    conn: sqlite3.Connection,
) -> list[dict]:
    """Run the Provenance Evaluation Function.

    For every required_observation per paragraph: one Finding.
    Raises ValueError if plan or narrative cannot be loaded.
    Raises RuntimeError if Completeness Invariant is violated.
    """
    now = datetime.now(timezone.utc).isoformat()

    narrative = conn.execute(
        "SELECT id, architect_plan_id FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()
    if narrative is None:
        raise ValueError(f"RenderedNarrative not found: {rendered_narrative_id}")
    if narrative["architect_plan_id"] != architect_plan_id:
        raise ValueError(
            f"RenderedNarrative {rendered_narrative_id} belongs to plan "
            f"{narrative['architect_plan_id']}, not {architect_plan_id}"
        )

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

            obs_exists = conn.execute(
                "SELECT 1 FROM observations WHERE id = ?", (obs_id,)
            ).fetchone() is not None

            prov_exists = conn.execute(
                "SELECT 1 FROM provenance WHERE observation_id = ?", (obs_id,)
            ).fetchone() is not None

            if obs_exists and prov_exists:
                operation, status = "preservation", "preserved"
            elif obs_exists and not prov_exists:
                operation, status = "transformation", "transformed"
            else:
                operation, status = "omission", "omitted"

            evidence = json.dumps({
                "contract_obligation": obs_id,
                "observed_render": {
                    "observation_exists": obs_exists,
                    "provenance_exists": prov_exists,
                },
                "supporting_trace": [rendered_narrative_id, architect_plan_id, f"paragraph:{order_idx}"],
            }, ensure_ascii=True)

            findings.append({
                "id": finding_id,
                "rendered_narrative_id": rendered_narrative_id,
                "architect_plan_id": architect_plan_id,
                "dimension": DIMENSION,
                "obligation_id": obligation_id,
                "operation": operation,
                "status": status,
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
