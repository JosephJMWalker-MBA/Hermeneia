"""
Evaluation Function Runner — executes all registered EFs for a (narrative, plan) pair.

This is the single entry point for the Critic's Finding generation step.
Each EF is run independently; a failure in one does not block others.

Returns a RunResult with per-dimension findings and errors.
The caller is responsible for persisting the findings.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Callable

# ── EF registry (ordered by dependency depth, shallowest first) ───────────────

def _load_efs() -> list[tuple[str, Callable]]:
    from .structural        import evaluate_structural
    from .semantic          import evaluate_semantic
    from .provenance        import evaluate_provenance
    from .observation_coverage import evaluate_observation_coverage
    from .accessibility     import evaluate_accessibility
    from .constitutional    import evaluate_constitutional
    return [
        ("structural",          evaluate_structural),
        ("semantic",            evaluate_semantic),
        ("provenance",          evaluate_provenance),
        ("observation_coverage", evaluate_observation_coverage),
        ("accessibility",       evaluate_accessibility),
        ("constitutional",      evaluate_constitutional),
    ]


@dataclass
class EFResult:
    dimension: str
    findings: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class RunResult:
    rendered_narrative_id: str
    architect_plan_id: str
    ef_results: list[EFResult] = field(default_factory=list)

    @property
    def all_findings(self) -> list[dict]:
        """Flat list of all findings across all dimensions."""
        out: list[dict] = []
        for r in self.ef_results:
            out.extend(r.findings)
        return out

    @property
    def findings_by_dimension(self) -> dict[str, list[dict]]:
        return {r.dimension: r.findings for r in self.ef_results}

    @property
    def errors(self) -> dict[str, str]:
        return {r.dimension: r.error for r in self.ef_results if r.error}

    @property
    def total_findings(self) -> int:
        return sum(len(r.findings) for r in self.ef_results)


def run_all_evaluation_functions(
    rendered_narrative_id: str,
    architect_plan_id: str,
    conn: sqlite3.Connection,
    *,
    dimensions: list[str] | None = None,
) -> RunResult:
    """Run all (or a subset of) evaluation functions for a rendered narrative.

    Args:
        rendered_narrative_id: ID of the RenderedNarrative to evaluate.
        architect_plan_id:     ID of the ArchitectPlan to evaluate against.
        conn:                  Read-only connection to the database.
        dimensions:            If provided, only run EFs whose dimension is in this list.
                               Default: run all registered EFs.

    Returns:
        RunResult with per-dimension EFResult objects.
        Errors in individual EFs are captured in EFResult.error and do not raise.
    """
    result = RunResult(
        rendered_narrative_id=rendered_narrative_id,
        architect_plan_id=architect_plan_id,
    )

    for dimension, ef_func in _load_efs():
        if dimensions is not None and dimension not in dimensions:
            continue
        try:
            findings = ef_func(rendered_narrative_id, architect_plan_id, conn)
            result.ef_results.append(EFResult(dimension=dimension, findings=findings))
        except Exception as exc:
            result.ef_results.append(EFResult(dimension=dimension, error=str(exc)))

    return result
