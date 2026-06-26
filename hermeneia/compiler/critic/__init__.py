"""Interpretation Grounding Critic — Sprint E9.

Constitutional Status: OPERATIONAL artifact producer.
Promotion criterion defined in CONSTITUTIONAL_COMPLIANCE.md.

This package also contains the Narrative Fidelity Critic, which operates on
RenderedNarrative inputs and produces validation_reports.

This module operates on proposed_interpretations → critic_reports.

Three-stage model (empirically grounded, Experiments 001–008):
    Stage 1: Evidence Identification  — HIGH cross-provider convergence
    Stage 2: Evidence-Claim Mapping   — MODERATE convergence
    Stage 3: Verdict Classification   — POLICY DEPENDENT

The human steward is placed at Stage 3 (claim normalization and policy selection)
precisely because that is where provider variance persists after available convergence
has occurred. See research/synthesis_001_convergence_governance_pattern.md.
"""
from .narrative_fidelity import run_critic, validate
from .report import generate_critic_report

__all__ = ["generate_critic_report", "run_critic", "validate"]
