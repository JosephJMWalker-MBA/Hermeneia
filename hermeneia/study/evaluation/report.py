"""Deterministic evaluation report (design §10).

Aggregates scorer verdicts into an inspectable, provider-free report. The
report always declares ``provider_free`` and ``canonical_evidence_modified:
false`` so any consumer can confirm the harness stayed within its non-goals.
``generated_at`` is an explicit argument so identical inputs produce identical
output.
"""
from __future__ import annotations

from typing import Any

from .scorer import FAIL, NOT_APPLICABLE, PASS, ScorerVerdict


HARNESS_VERSION = "eval-harness-v1"


def build_evaluation_report(
    cases: list[tuple[str, list[ScorerVerdict]]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    """Build a deterministic report from ``(case_name, verdicts)`` pairs.

    ``cases`` are sorted by name and verdicts by dimension so identical inputs
    yield byte-identical output.
    """
    summary = {PASS: 0, FAIL: 0, NOT_APPLICABLE: 0}
    ordered_cases = []
    for case_name, verdicts in sorted(cases, key=lambda item: item[0]):
        ordered_verdicts = sorted(verdicts, key=lambda verdict: verdict.dimension)
        for verdict in ordered_verdicts:
            summary[verdict.verdict] += 1
        ordered_cases.append(
            {
                "case": case_name,
                "verdicts": [verdict.to_dict() for verdict in ordered_verdicts],
            }
        )

    return {
        "harness_version": HARNESS_VERSION,
        "generated_at": generated_at,
        "provider_free": True,
        "canonical_evidence_modified": False,
        "cases": ordered_cases,
        "summary": summary,
    }
