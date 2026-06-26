"""
ArchitectPlan — the composition specification produced by the Architect.

This is the first object in the Composition layer. It crosses the boundary
from understanding to expression without generating any prose.

The Architect reads a NarrativeBlueprint and produces a deterministic
specification of WHAT must be communicated in each paragraph:
  - which observations provide the evidence
  - which interpretations frame the reading
  - which field terms are required or recommended
  - the communicative purpose of each paragraph

Invariants:
  - source is always 'deterministic' — no human authorship, no LLM
  - identical Blueprint input always produces identical ArchitectPlan
  - content-addressable ID: sha256(blueprint_id) via make_architect_plan_id
  - blueprint_hash captures the Blueprint state at plan creation time;
    if the Blueprint changes, the plan is marked stale on trace
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from .base import HermeneiaObject


class RequiredTerm(HermeneiaObject):
    term: str
    priority: Literal["critical", "recommended"]


class ArchitectParagraph(HermeneiaObject):
    order: int                                    # 1-indexed, matches blueprint section
    purpose: str                                  # the claim this paragraph must establish
    blueprint_section: int                        # which section (1-indexed) this maps to
    required_observations: tuple[str, ...]        # Observation IDs that must be engaged
    required_interpretations: tuple[str, ...]     # Interpretation IDs that must be applied
    required_terms: tuple[RequiredTerm, ...]      # field terms + priority
    forbidden_claims: tuple[str, ...] = ()        # claims the Artist must not assert
    notes: str | None = None


class ArchitectPlan(HermeneiaObject):
    id: str                                       # sha256("architect:" + blueprint_id)
    blueprint_id: str                             # FK to the originating Blueprint
    blueprint_hash: str                           # sha256 of blueprint payload at creation
    title: str                                    # copied from Blueprint title
    paragraphs: tuple[ArchitectParagraph, ...]    # one per Blueprint section, ordered
    source: Literal["deterministic"]
    created_at: datetime
