"""
Semantic Evaluation Function — Era II Sprint E3.

Maps (ArchitectPlan, RenderedNarrative) → Finding[]  with dimension="semantic"

For every contracted obligation (required term), this function answers:
  Is the term's presence in the narrative backed by the evidence chain?

The Structural function already answers "is the term present?"
This function answers "should we trust that presence?"

Evidence chain traversal (read-only, no LLM):
    required_term (ArchitectPlan)
      → NarrativeBlueprint          (via architect_plans.blueprint_id)
        → blueprint_interpretation_links → Interpretations (text overlap)
        → blueprint_observation_links   → Observations    (text overlap)

Four verdicts:
    preserved       term in narrative + ≥1 interpretation + ≥1 observation backs it
    transformed     term in narrative + interpretation exists but observation trace thin
    not_evaluated   term in narrative, no interpretation chain in blueprint
    omitted         term absent from narrative entirely

Support levels are encoded in Finding.evidence as supporting_trace JSON so that
any UI or projection layer can explain the verdict without touching the DB.

Completeness Invariant: every obligation produces exactly one Finding.
No LLM dependency. Deterministic. Read-only. Orthogonal.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from hermeneia.storage.hashing import make_finding_id, make_obligation_id

# ── Constitutional contract ────────────────────────────────────────────────────
dimension = "semantic"
scope = ["required_terms", "evidence_chain"]
guarantees = ["deterministic", "complete", "read_only", "orthogonal", "zero_llm"]

DIMENSION = dimension
EVALUATION_METHOD = "semantic-v1.0"

CONSTITUTIONAL_PROFILE = {
    "constitution_version": "1.0.0",
    "authority_index_version": "1.0.0",
    "invariant_profile": "CI-001..CI-016",
    "architecture_profile": "v1.0",
}

# ── Tuning constants ───────────────────────────────────────────────────────────
# Minimum token-overlap ratio to count a text as "mentioning" the term.
_OVERLAP_THRESHOLD = 0.15
# Minimum number of term tokens that must appear in source text.
_MIN_TOKEN_HITS = 1


def evaluate_semantic(
    rendered_narrative_id: str,
    architect_plan_id: str,
    conn: sqlite3.Connection,
) -> list[dict]:
    """Run the Semantic Evaluation Function.

    Returns Finding rows ready for SQLiteStore.insert_findings_batch().
    Raises ValueError if plan or narrative cannot be loaded.
    Raises RuntimeError if Completeness Invariant is violated.
    """
    now = datetime.now(timezone.utc).isoformat()

    # ── Load RenderedNarrative ────────────────────────────────────────────────
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

    # ── Load ArchitectPlan paragraphs ─────────────────────────────────────────
    paragraphs = conn.execute(
        "SELECT order_idx, required_terms FROM architect_plan_paragraphs "
        "WHERE plan_id = ? ORDER BY order_idx",
        (architect_plan_id,),
    ).fetchall()
    if not paragraphs:
        raise ValueError(f"No paragraphs found for architect plan: {architect_plan_id}")

    # ── Resolve blueprint linked to this plan ─────────────────────────────────
    plan_row = conn.execute(
        "SELECT blueprint_id FROM architect_plans WHERE id = ?",
        (architect_plan_id,),
    ).fetchone()
    blueprint_id: str | None = plan_row["blueprint_id"] if plan_row else None

    # ── Load linked interpretations and observations for this blueprint ────────
    linked_interpretations: list[dict] = []
    linked_observations: list[dict] = []

    if blueprint_id:
        interp_rows = conn.execute(
            """
            SELECT i.id, i.text AS interpretation_text
            FROM interpretations i
            JOIN blueprint_interpretation_links bil ON bil.interpretation_id = i.id
            WHERE bil.blueprint_id = ?
            """,
            (blueprint_id,),
        ).fetchall()
        linked_interpretations = [dict(r) for r in interp_rows]

        obs_rows = conn.execute(
            """
            SELECT o.id, o.raw_text
            FROM observations o
            JOIN blueprint_observation_links bol ON bol.observation_id = o.id
            WHERE bol.blueprint_id = ?
            """,
            (blueprint_id,),
        ).fetchall()
        linked_observations = [dict(r) for r in obs_rows]

    # ── Produce one Finding per obligation ────────────────────────────────────
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

            term_in_narrative = term_text.lower() in narrative_text.lower()

            if not term_in_narrative:
                # Omitted — not present in the narrative at all
                findings.append(_make_finding(
                    finding_id=finding_id,
                    rendered_narrative_id=rendered_narrative_id,
                    architect_plan_id=architect_plan_id,
                    obligation_id=obligation_id,
                    operation="omission",
                    status="omitted",
                    evidence={
                        "contract_obligation": term_text,
                        "observed_render": None,
                        "supporting_trace": {
                            "support_level": "omitted",
                            "interpretation_matches": [],
                            "observation_matches": [],
                        },
                    },
                    now=now,
                ))
                continue

            # Term is in the narrative — assess evidence depth
            matching_interps = _find_matches(term_text, linked_interpretations, "interpretation_text")
            matching_obs = _find_matches(term_text, linked_observations, "raw_text")

            support_level, operation, status = _verdict(
                has_interp=len(matching_interps) > 0,
                has_obs=len(matching_obs) > 0,
            )

            # Excerpt: where the term appears in the narrative (context window)
            idx = narrative_text.lower().find(term_text.lower())
            start = max(0, idx - 30)
            end = min(len(narrative_text), idx + len(term_text) + 30)
            observed_render = narrative_text[start:end]

            findings.append(_make_finding(
                finding_id=finding_id,
                rendered_narrative_id=rendered_narrative_id,
                architect_plan_id=architect_plan_id,
                obligation_id=obligation_id,
                operation=operation,
                status=status,
                evidence={
                    "contract_obligation": term_text,
                    "observed_render": observed_render,
                    "supporting_trace": {
                        "support_level": support_level,
                        "interpretation_matches": [
                            {"id": m["id"], "excerpt": _excerpt(m["interpretation_text"], term_text)}
                            for m in matching_interps[:3]
                        ],
                        "observation_matches": [
                            {"id": m["id"], "excerpt": _excerpt(m["raw_text"], term_text)}
                            for m in matching_obs[:3]
                        ],
                    },
                },
                now=now,
            ))

    # Completeness Invariant
    obligations_in_scope = sum(
        len(json.loads(p["required_terms"] or "[]")) for p in paragraphs
    )
    if len(findings) != obligations_in_scope:
        raise RuntimeError(
            f"Completeness Invariant violated: expected {obligations_in_scope} findings, "
            f"produced {len(findings)}"
        )

    return findings


# ── Verdict logic ─────────────────────────────────────────────────────────────

def _verdict(
    has_interp: bool,
    has_obs: bool,
) -> tuple[str, str, str]:
    """Return (support_level, operation, status) for a present term."""
    if has_interp and has_obs:
        return "supported", "preservation", "preserved"
    elif has_interp:
        return "partially_supported", "transformation", "transformed"
    else:
        return "weak", "not_evaluated", "not_evaluated"


# ── Helpers ───────────────────────────────────────────────────────────────────

_WORD = re.compile(r'\b[a-z]+\b', re.IGNORECASE)
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "is", "it",
    "that", "this", "with", "for", "on", "at", "be", "as", "by",
    "not", "are", "was", "were", "has", "have", "had", "but",
}


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)} - _STOPWORDS


def _find_matches(term: str, items: list[dict], text_key: str) -> list[dict]:
    """Return items whose text meaningfully overlaps with the term."""
    term_tokens = _tokenize(term)
    if not term_tokens:
        return []

    matches = []
    for item in items:
        source = item.get(text_key, "") or ""
        source_tokens = _tokenize(source)
        hits = len(term_tokens & source_tokens)
        if hits >= _MIN_TOKEN_HITS and hits / len(term_tokens) >= _OVERLAP_THRESHOLD:
            matches.append(item)
    return matches


def _excerpt(text: str, term: str, window: int = 80) -> str:
    """Return a short excerpt of text centred on the term, or the first window chars."""
    idx = text.lower().find(term.lower())
    if idx == -1:
        return text[:window]
    start = max(0, idx - window // 2)
    end = min(len(text), start + window)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def _make_finding(
    *,
    finding_id: str,
    rendered_narrative_id: str,
    architect_plan_id: str,
    obligation_id: str,
    operation: str,
    status: str,
    evidence: dict,
    now: str,
) -> dict:
    return {
        "id": finding_id,
        "rendered_narrative_id": rendered_narrative_id,
        "architect_plan_id": architect_plan_id,
        "dimension": DIMENSION,
        "obligation_id": obligation_id,
        "operation": operation,
        "status": status,
        "evidence": json.dumps(evidence, ensure_ascii=True),
        "evaluation_method": EVALUATION_METHOD,
        "constitution_version": json.dumps(CONSTITUTIONAL_PROFILE, sort_keys=True),
        "created_at": now,
    }
