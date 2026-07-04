"""Deterministic, provider-free evaluation harness for interpretation quality.

Design: docs/evaluation-harness-design.md (issue #63). This package names
obligations and checks whether they held for a compiled study record. It makes
no provider call, reads no canonical evidence for mutation, and never claims to
measure understanding — only whether specific, named obligations were met.
"""
from .scorer import PASS, FAIL, NOT_APPLICABLE, Scorer, ScorerVerdict
from .evidence_preservation import (
    EVIDENCE_PRESERVATION,
    score_evidence_preservation,
)
from .corpus_boundary import CORPUS_BOUNDARY, score_corpus_boundary
from .unsupported_claims import UNSUPPORTED_CLAIMS, score_unsupported_claims
from .report import HARNESS_VERSION, build_evaluation_report

__all__ = [
    "PASS",
    "FAIL",
    "NOT_APPLICABLE",
    "Scorer",
    "ScorerVerdict",
    "EVIDENCE_PRESERVATION",
    "score_evidence_preservation",
    "CORPUS_BOUNDARY",
    "score_corpus_boundary",
    "UNSUPPORTED_CLAIMS",
    "score_unsupported_claims",
    "HARNESS_VERSION",
    "build_evaluation_report",
]
