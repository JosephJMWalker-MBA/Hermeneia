"""
Perspective — a declared interpretive frame for canonical interpretation.

A Perspective is not an Observation and not an Interpretation. It is the frame
that makes an Interpretation's standpoint explicit. Without a declared
Perspective, an Interpretation has no auditable vantage point.

ADR-0015 legacy Perspectives use ``perspective-label-v1`` identity: the
canonical object ID is derived from the normalized human label.

ADR-0045 frame-v2 Perspectives use ``perspective-frame-v2`` identity: the
canonical object ID identifies one immutable human declaration or revision,
derived from the identity scheme, semantic definition fingerprint, and
declaration context. The semantic definition fingerprint records what the frame
means; it is not the canonical Perspective object ID by itself.

Invariants:
  - Append-only: once registered, a Perspective is never deleted or mutated.
  - Perspective != Interpretation: one Perspective can have many
    Interpretations, and each Interpretation references an exact Perspective.
  - Perspective is independent of individual Observations; grounding source
    evidence is the Interpretation's job.
  - Provider, model, Scope, user Question, and expression constraints are not
    Perspective semantics.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from .base import HermeneiaObject


class Perspective(HermeneiaObject):
    id: str
    name: str
    description: str
    created_at: datetime

    identity_scheme: Literal["perspective-label-v1", "perspective-frame-v2"] = "perspective-label-v1"
    definition_fingerprint: str | None = None
    purpose: str | None = None
    questions: tuple[str, ...] | None = None
    challenges: tuple[str, ...] | None = None
    limitations: tuple[str, ...] | None = None
    declared_by: str | None = None
    declared_date: datetime | None = None
