"""
Perspective — a named interpretive lens that governs how observations are read.

A Perspective is not an Observation and not an Interpretation. It is the
epistemological frame that makes an Interpretation possible. Without a named
Perspective, an interpretation has no declared standpoint and therefore no
defensible claim to validity.

Invariants:
  - Append-only (ADR-0001): once registered, a Perspective is never deleted
  - ID is content-addressable: sha256(lower(name)) — "Literary" and "literary"
    are the same Perspective
  - A Perspective can have many Interpretations across many Observations
  - A Perspective has no knowledge of individual Observations — that is the
    Interpretation's job
"""
from __future__ import annotations

from datetime import datetime

from .base import HermeneiaObject


class Perspective(HermeneiaObject):
    id: str           # sha256(name.lower().strip())
    name: str         # canonical display name, e.g. "Literary"
    description: str  # what this lens attends to; may be empty at registration
    created_at: datetime
