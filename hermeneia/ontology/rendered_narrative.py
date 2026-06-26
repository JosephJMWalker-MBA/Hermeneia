"""
RenderedNarrative — prose produced by the Artist from an ArchitectPlan.

The Artist is responsible only for expression. It receives a fully specified
ArchitectPlan — every semantic commitment already decided — and converts it
to prose. It invents nothing: all meaning comes from the epistemic chain above.

Invariants:
  - Content-addressable ID: sha256({architect_plan_id, provider})
  - prompt_used is stored verbatim — the generated prompt is an inspectable artifact
  - provider names the ArtistProvider implementation that produced this text
  - Append-only: once rendered, never mutated
"""
from __future__ import annotations

from datetime import datetime

from .base import HermeneiaObject


class RenderedNarrative(HermeneiaObject):
    id: str                    # sha256({architect_plan_id, provider})
    architect_plan_id: str     # FK to the ArchitectPlan this was rendered from
    provider: str              # e.g. "null", "anthropic", "openai", "ollama"
    text: str                  # the rendered prose (or placeholder for NullArtist)
    prompt_used: str           # the generated prompt — inspectable, deterministic
    created_at: datetime
