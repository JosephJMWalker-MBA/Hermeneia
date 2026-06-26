"""
Accessibility Evaluation Function — ADR-0042, Era II Sprint E3.

Structural heuristics on RenderedNarrative.text. One Finding per
accessibility obligation. No paragraph-level iteration — these are
narrative-level checks.

Zero LLM. Deterministic. Read-only. Orthogonal.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from hermeneia.storage.hashing import make_finding_id, make_obligation_id

# ── Constitutional contract ───────────────────────────────────────────────────
dimension = "accessibility"
scope = ["rendered_text"]
guarantees = ["deterministic", "complete", "read_only", "orthogonal", "zero_llm"]

# ── Internal constants ────────────────────────────────────────────────────────
DIMENSION = dimension
EVALUATION_METHOD = "accessibility-v1.0"
MAX_MEAN_SENTENCE_WORDS = 35   # conservative readable ceiling (ADR-0042)

CONSTITUTIONAL_PROFILE = {
    "constitution_version": "1.0.0",
    "authority_index_version": "1.0.0",
    "invariant_profile": "CI-001..CI-016",
    "architecture_profile": "v1.0",
    "adr": "ADR-0042",
}

# Each key is both the obligation identifier and a human-readable label
OBLIGATIONS: list[tuple[str, str]] = [
    ("text_present",         "Narrative text is non-empty"),
    ("paragraph_structure",  "Narrative contains paragraph breaks"),
    ("sentence_length",      f"Mean sentence length ≤ {MAX_MEAN_SENTENCE_WORDS} words"),
]


def _mean_sentence_words(text: str) -> float:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def evaluate_accessibility(
    rendered_narrative_id: str,
    architect_plan_id: str,
    conn: sqlite3.Connection,
) -> list[dict]:
    """Run the Accessibility Evaluation Function.

    One Finding per accessibility obligation (narrative-level).
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
    text = narrative_row["text"] or ""

    checks: dict[str, tuple[bool, str]] = {
        "text_present": (
            bool(text.strip()),
            f"length={len(text.strip())}",
        ),
        "paragraph_structure": (
            "\n\n" in text,
            f"paragraph_breaks={text.count(chr(10) + chr(10))}",
        ),
        "sentence_length": (
            _mean_sentence_words(text) <= MAX_MEAN_SENTENCE_WORDS,
            f"mean_words_per_sentence={_mean_sentence_words(text):.1f}",
        ),
    }

    findings: list[dict] = []

    for obligation_key, _label in OBLIGATIONS:
        passed, observed = checks[obligation_key]

        # Accessibility obligations are narrative-level: use narrative_id as anchor
        obligation_id = make_obligation_id(
            dimension=DIMENSION,
            plan_id=architect_plan_id,
            paragraph_order_idx=0,
            term_text=obligation_key,
        )
        finding_id = make_finding_id(rendered_narrative_id, DIMENSION, obligation_id)

        evidence = json.dumps({
            "contract_obligation": obligation_key,
            "observed_render": observed,
            "supporting_trace": [rendered_narrative_id, architect_plan_id],
        }, ensure_ascii=True)

        findings.append({
            "id": finding_id,
            "rendered_narrative_id": rendered_narrative_id,
            "architect_plan_id": architect_plan_id,
            "dimension": DIMENSION,
            "obligation_id": obligation_id,
            "operation": "preservation" if passed else "omission",
            "status": "preserved" if passed else "omitted",
            "evidence": evidence,
            "evaluation_method": EVALUATION_METHOD,
            "constitution_version": json.dumps(CONSTITUTIONAL_PROFILE, sort_keys=True),
            "created_at": now,
        })

    if len(findings) != len(OBLIGATIONS):
        raise RuntimeError(
            f"Completeness Invariant violated: expected {len(OBLIGATIONS)} "
            f"findings, produced {len(findings)}"
        )

    return findings
