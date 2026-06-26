"""
ValidationReport — the Critic's output.

The Critic does not judge writing quality. It judges semantic fidelity.
That distinction is essential.

v0.1 is fully deterministic: no LLM, no subjectivity.
It answers one question: did the Artist satisfy the semantic contract
established by the Architect?
"""
from __future__ import annotations
from datetime import datetime
from .base import HermeneiaObject


class ValidationReport(HermeneiaObject):
    id: str                                  # sha256("critic:" + rendered_narrative_id)
    rendered_narrative_id: str
    architect_plan_id: str
    expression_profile_id: str | None

    semantic_fidelity: float                 # 0.0–100.0 — percentage of checks passing

    required_terms_present: tuple[str, ...]  # terms found in the rendered text
    required_terms_missing: tuple[str, ...]  # required terms absent from rendered text
    unsupported_claims: tuple[str, ...]      # forbidden claims detected in text
    omitted_observations: tuple[str, ...]    # obs IDs not referenced (v0.2)
    omitted_interpretations: tuple[str, ...] # interp IDs not represented (v0.2)
    semantic_drift: tuple[str, ...]          # detected departures from plan (v0.2)
    warnings: tuple[str, ...]                # non-fatal issues

    approved: bool
    created_at: datetime
