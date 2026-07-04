"""
Study Compiler (Issue #35) - the deterministic core of the interpretation compiler.

Takes the reader's marks (``reader_highlights`` rows, as dicts) and compiles them
into a structured study summary: thesis candidates, strongest observations, open
questions, weak areas, thematic-bucket summary, the evidence bucket (working set),
counts, and deterministic next-step suggestions.

Deterministic and AI-free by design. The Architecture Blueprint's first
``compileStudyState`` was explicitly "then AI can enrich this later" - this is that
substrate. The user's ranks and buckets are authoritative signals; the compiler
organizes them, it never reinterprets them.

Two senses of "bucket", kept distinct (Reader Shell Spec section 0.1):
  * ``theme_bucket``    - a meaning CATEGORY (thematic grouping): aspiration, covenant.
  * ``evidence_bucket`` - a working-SET / shell-tray membership: what feeds one run.
"""
from __future__ import annotations

import json
from typing import Any

# The mark types (Blueprint Layer 2). Derived from the durable fields already on
# reader_highlights rather than stored as a separate column: the model is
# first-class in code; its substrate is the existing hardened write path.
MARK_TYPES: tuple[str, ...] = ("highlight", "note", "question", "concept", "observation")

RANK_LABELS: dict[int, str] = {
    5: "foundational",
    4: "strong",
    3: "useful",
    2: "minor",
    1: "speculative",
}


def _tags(h: dict[str, Any]) -> list:
    tags = h.get("tags")
    if isinstance(tags, list):
        return tags
    if isinstance(tags, str):
        try:
            parsed = json.loads(tags)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    return []


def classify_mark(h: dict[str, Any]) -> str:
    """Deterministically classify a highlight row into a mark type.

    Priority: an observation candidate/promotion is an observation; a concept tag
    makes it a concept; a question text makes it a question; a note text makes it a
    note; otherwise it is a plain highlight.
    """
    status = (h.get("status") or "").strip()
    if status in ("observation_candidate", "promoted_to_observation"):
        return "observation"
    if any(isinstance(t, str) and t.startswith("concept:") for t in _tags(h)):
        return "concept"
    if (h.get("question_text") or "").strip():
        return "question"
    if (h.get("note_text") or "").strip():
        return "note"
    return "highlight"


def _rank(h: dict[str, Any]) -> int:
    """Return a valid 1-5 rank, or 0 for unranked/invalid; never raises."""
    r = h.get("rank")
    if isinstance(r, bool):  # guard: bool is an int subclass
        return 0
    if isinstance(r, int) and 1 <= r <= 5:
        return r
    if isinstance(r, str) and r.strip().isdecimal():
        parsed = int(r.strip())
        return parsed if 1 <= parsed <= 5 else 0
    return 0


def _by_rank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort rank-descending, then created_at-ascending for stable output."""
    return sorted(
        items,
        key=lambda a: (
            -_rank(a),
            a.get("created_at") or "",
            a.get("id") or "",
            a.get("selected_text") or "",
        ),
    )


def compile_study(
    annotations: list[dict[str, Any]],
    *,
    include_dismissed: bool = False,
) -> dict[str, Any]:
    """Compile ranked marks into a structured study summary. Pure and deterministic."""
    active = [
        a for a in annotations
        if include_dismissed or (a.get("status") != "dismissed")
    ]
    typed = [(a, classify_mark(a)) for a in active]

    thesis_candidates = _by_rank([a for a in active if _rank(a) >= 5])
    strongest_observations = _by_rank(
        [a for (a, t) in typed if t == "observation" and _rank(a) >= 4]
    )
    open_questions = _by_rank([a for (a, t) in typed if t == "question"])
    weak_areas = _by_rank([a for a in active if 1 <= _rank(a) <= 2])

    # Theme buckets: meaning categories, distinct from the evidence bucket.
    theme: dict[str, list[dict[str, Any]]] = {}
    for a in active:
        tb = (a.get("theme_bucket") or "").strip()
        if tb:
            theme.setdefault(tb, []).append(a)
    theme_bucket_summary = [
        {
            "bucket": name,
            "count": len(items),
            "avg_rank": round(sum(_rank(i) for i in items) / len(items), 2),
            "top": _by_rank(items)[:3],
        }
        # Strongest, largest buckets first; ties broken alphabetically.
        for name, items in sorted(
            theme.items(),
            key=lambda kv: (-(sum(_rank(i) for i in kv[1])), -len(kv[1]), kv[0]),
        )
    ]

    # Evidence bucket: working-set membership, not meaning.
    evidence_bucket = _by_rank(
        [a for a in active if (a.get("evidence_bucket") or "").strip()]
    )

    counts = {
        "total": len(active),
        "ranked": sum(1 for a in active if _rank(a) > 0),
        "unranked": sum(1 for a in active if _rank(a) == 0),
        "by_type": {t: sum(1 for (_, tt) in typed if tt == t) for t in MARK_TYPES},
        "themes": len(theme_bucket_summary),
        "in_evidence_bucket": len(evidence_bucket),
    }

    return {
        "thesis_candidates": thesis_candidates,
        "strongest_observations": strongest_observations,
        "open_questions": open_questions,
        "weak_areas": weak_areas,
        "theme_bucket_summary": theme_bucket_summary,
        "evidence_bucket": evidence_bucket,
        "counts": counts,
        "suggested_next_steps": _suggest(
            active, counts, thesis_candidates, open_questions, theme_bucket_summary
        ),
    }


def _suggest(
    active: list[dict[str, Any]],
    counts: dict[str, Any],
    thesis: list[dict[str, Any]],
    open_qs: list[dict[str, Any]],
    themes: list[dict[str, Any]],
) -> list[str]:
    """Deterministic next-step hints from the shape of the marks. No AI."""
    steps: list[str] = []
    if not active:
        return ["Mark a passage to begin: highlight what catches your eye, then say why it matters."]
    if counts["ranked"] == 0:
        steps.append("Rank your marks 1-5 so the strongest evidence rises to the top.")
    if not thesis:
        steps.append("No thesis-level (rank 5) marks yet; promote your strongest observation when one earns it.")
    if open_qs:
        steps.append(f"You have {len(open_qs)} open question(s); gather evidence toward the highest-ranked one.")
    if counts["by_type"]["observation"] and counts["by_type"]["concept"] == 0:
        steps.append("Many observations, no named concepts; define the terms your observations keep circling.")
    if not themes:
        steps.append("No thematic buckets yet; group related marks so patterns become visible.")
    return steps
