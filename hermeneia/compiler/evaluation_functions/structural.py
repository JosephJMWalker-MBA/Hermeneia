"""
Structural Evaluation Function — ADR-0041, Era II Sprint E1.

Maps (ArchitectPlan, RenderedNarrative) → Finding[]

One Finding per required term per paragraph. No term is skipped.
No LLM dependency. Deterministic. Read-only. Orthogonal.

Completeness Invariant (Amendment III): every obligation in scope
produces exactly one Finding — preserved or omitted.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from hermeneia.storage.hashing import make_finding_id, make_obligation_id

if TYPE_CHECKING:
    pass

# ── Constitutional contract (required by base.EvaluationFunctionContract) ────
dimension = "structural"
scope = ["required_terms"]
guarantees = ["deterministic", "complete", "read_only", "orthogonal", "zero_llm"]

# ── Internal constants ────────────────────────────────────────────────────────
DIMENSION = dimension
EVALUATION_METHOD = "structural-v1.0"

CONSTITUTIONAL_PROFILE = {
    "constitution_version": "1.0.0",
    "authority_index_version": "1.0.0",
    "invariant_profile": "CI-001..CI-016",
    "architecture_profile": "v1.0",
    "adr": "ADR-0041",
}


def evaluate_structural(
    rendered_narrative_id: str,
    architect_plan_id: str,
    conn: sqlite3.Connection,
) -> list[dict]:
    """Run the Structural Evaluation Function.

    For every required term in every architect plan paragraph, produce exactly
    one Finding: preserved (term present) or omitted (term absent).

    Returns the Finding rows ready for SQLiteStore.insert_findings_batch().
    Raises ValueError if plan or narrative cannot be loaded.
    Raises RuntimeError if Completeness Invariant is violated (should never happen).
    """
    now = datetime.now(timezone.utc).isoformat()

    # Load RenderedNarrative
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

    # Load ArchitectPlan paragraphs
    paragraphs = conn.execute(
        "SELECT order_idx, required_terms FROM architect_plan_paragraphs "
        "WHERE plan_id = ? ORDER BY order_idx",
        (architect_plan_id,),
    ).fetchall()
    if not paragraphs:
        raise ValueError(f"No paragraphs found for architect plan: {architect_plan_id}")

    findings: list[dict] = []

    for para in paragraphs:
        order_idx: int = para["order_idx"]
        required_terms: list[dict] = json.loads(para["required_terms"] or "[]")

        for term_entry in required_terms:
            term_text: str = term_entry["term"]

            obligation_id = make_obligation_id(
                dimension=DIMENSION,
                plan_id=architect_plan_id,
                paragraph_order_idx=order_idx,
                term_text=term_text,
            )
            finding_id = make_finding_id(
                rendered_narrative_id=rendered_narrative_id,
                dimension=DIMENSION,
                obligation_id=obligation_id,
            )

            # Case-insensitive substring match — necessary but not sufficient
            # for semantic fidelity (acknowledged limitation, ADR-0041 §6)
            term_present = term_text.lower() in narrative_text.lower()

            # Find verbatim excerpt for evidence (first 120 chars of context window)
            observed_render = None
            if term_present:
                idx = narrative_text.lower().find(term_text.lower())
                start = max(0, idx - 20)
                end = min(len(narrative_text), idx + len(term_text) + 20)
                observed_render = narrative_text[start:end]

            # Amendment II: evidence preserves observations, not conclusions
            evidence = json.dumps(
                {
                    "contract_obligation": term_text,
                    "observed_render": observed_render,
                    "supporting_trace": [
                        rendered_narrative_id,
                        architect_plan_id,
                        f"paragraph:{order_idx}",
                    ],
                },
                ensure_ascii=True,
            )

            findings.append({
                "id": finding_id,
                "rendered_narrative_id": rendered_narrative_id,
                "architect_plan_id": architect_plan_id,
                "dimension": DIMENSION,
                "obligation_id": obligation_id,
                "operation": "preservation" if term_present else "omission",
                "status": "preserved" if term_present else "omitted",
                "evidence": evidence,
                "evaluation_method": EVALUATION_METHOD,
                "constitution_version": json.dumps(
                    CONSTITUTIONAL_PROFILE, sort_keys=True
                ),
                "created_at": now,
            })

    # Completeness Invariant: every obligation must have exactly one Finding
    obligations_in_scope = sum(
        len(json.loads(p["required_terms"] or "[]")) for p in paragraphs
    )
    if len(findings) != obligations_in_scope:
        raise RuntimeError(
            f"Completeness Invariant violated: expected {obligations_in_scope} findings, "
            f"produced {len(findings)}"
        )

    return findings
