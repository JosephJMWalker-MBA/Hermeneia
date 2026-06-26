"""
Interpretation — a steward-authored, perspective-scoped reading of one Observation.

Invariants:
  - Append-only: once written, never modified (ADR-0001)
  - Provenance-linked: must reference a valid Observation ID
  - Perspective-scoped: every Interpretation belongs to exactly one named Perspective
  - Steward-owned: confidence = "human", source = "steward-authored" (ADR-0010)
  - ID is content-addressable: sha256({observation_id, perspective, text})
    Two identical readings of the same observation from the same perspective
    produce the same ID — preventing silent duplicates.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from .base import HermeneiaObject

EvidentialStatus = Literal["established", "contested", "speculative", "uncertain"]


class Interpretation(HermeneiaObject):
    id: str                                        # sha256 of canonical payload
    observation_id: str                            # the observation being interpreted
    perspective: str                               # named Perspective (e.g. "Literary")
    text: str                                      # the interpretation itself
    evidential_status: EvidentialStatus            # ADR-0036 enum
    evidence_observation_ids: tuple[str, ...]      # supporting Observation IDs
    confidence: Literal["human"]                   # steward-authored = human confidence
    source: Literal["steward-authored"]            # ADR-0010
    created_at: datetime
