"""
Evaluation Function constitutional contract — ADR-0041, Era II.

Every Evaluation Function must declare its dimension, scope, and guarantees
as class-level attributes. This metadata is the function's constitutional contract:
it prevents accidental overlap between dimensions and makes guarantees
machine-verifiable before any Finding is produced.

Engineering rule (established before Sprint E3):
    Every EF must satisfy EvaluationFunctionContract.
    Guarantees are not aspirational. They are declared and checked.
"""
from __future__ import annotations

import sqlite3
from typing import Protocol, runtime_checkable

# Ratified guarantee vocabulary (ADR-0041, Amendment III)
VALID_GUARANTEES = frozenset({
    "deterministic",    # same canonical inputs → same Finding IDs
    "complete",         # every obligation in scope → exactly one Finding
    "read_only",        # writes only to findings table
    "orthogonal",       # evaluates exactly one dimension
    "zero_llm",         # no LLM dependency
})

# Ratified dimension vocabulary — extended by future ADRs as new EFs are authorized
RATIFIED_DIMENSIONS = frozenset({
    "structural",           # ADR-0041: required_terms presence check
    "provenance",           # ADR-0042: required_observations exist with provenance records
    "observation_coverage", # ADR-0042: required_observations text present in narrative
    "constitutional",       # ADR-0042: execution_config carries constitutional profile
    "accessibility",        # ADR-0042: structural heuristics (sentence length, paragraphs)
})


@runtime_checkable
class EvaluationFunctionContract(Protocol):
    """Protocol every Evaluation Function module must satisfy.

    Declare at module level:
        dimension: str          — the single orthogonal dimension evaluated
        scope: list[str]        — the obligation types in scope
        guarantees: list[str]   — subset of VALID_GUARANTEES

    And expose the callable:
        def evaluate_<dimension>(
            rendered_narrative_id: str,
            architect_plan_id: str,
            conn: sqlite3.Connection,
        ) -> list[dict]: ...
    """
    dimension: str
    scope: list[str]
    guarantees: list[str]


def validate_ef_contract(module) -> list[str]:
    """Validate that an EF module satisfies the constitutional contract.

    Returns a list of violations. Empty list means the contract is satisfied.
    """
    violations: list[str] = []
    name = getattr(module, "__name__", str(module))

    # Required attributes
    for attr in ("dimension", "scope", "guarantees"):
        if not hasattr(module, attr):
            violations.append(f"{name}: missing required attribute '{attr}'")

    if violations:
        return violations

    dim = module.dimension
    if not isinstance(dim, str) or not dim.strip():
        violations.append(f"{name}: 'dimension' must be a non-empty string")

    scope = module.scope
    if not isinstance(scope, list) or not scope:
        violations.append(f"{name}: 'scope' must be a non-empty list")

    guarantees = module.guarantees
    if not isinstance(guarantees, list) or not guarantees:
        violations.append(f"{name}: 'guarantees' must be a non-empty list")
    else:
        unknown = set(guarantees) - VALID_GUARANTEES
        if unknown:
            violations.append(
                f"{name}: unknown guarantees {unknown!r} — must be from {sorted(VALID_GUARANTEES)}"
            )
        required = {"complete", "read_only", "orthogonal"}
        missing = required - set(guarantees)
        if missing:
            violations.append(
                f"{name}: missing required guarantees {sorted(missing)}"
            )

    return violations
