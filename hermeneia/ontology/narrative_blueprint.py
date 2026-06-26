"""
NarrativeBlueprint — the structural skeleton of an argument.

A Blueprint is NOT prose. It is the logical architecture that prose must
later conform to. It answers: what is being argued, in what order, from
which evidence, under which interpretive lens?

The Artist (Session 006+) receives a ratified Blueprint and produces prose
from it. The Blueprint constrains what the Artist may say. Nothing in the
Blueprint is stylistic.

Structure:
  title    — what this argument is called
  thesis   — the single claim the Blueprint defends
  sections — ordered argument steps, each with:
               claim                    the local point of this section
               supporting_observations  the raw evidence (Observation IDs)
               supporting_interpretations the readings brought to bear (Interpretation IDs)

Invariants:
  - Append-only (ADR-0001): once saved, never modified
  - Content-addressable ID: sha256({title, thesis, sections})
  - No prose, no style, no register — those belong to the rendering layer
  - Every cited observation and interpretation must exist at creation time
  - Source is always 'steward-authored' (ADR-0010)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from .base import HermeneiaObject


class BlueprintSection(HermeneiaObject):
    claim: str
    supporting_observations: tuple[str, ...]     # Observation IDs
    supporting_interpretations: tuple[str, ...]  # Interpretation IDs


class NarrativeBlueprint(HermeneiaObject):
    id: str                               # sha256 of canonical payload
    title: str
    thesis: str
    sections: tuple[BlueprintSection, ...]
    source: Literal["steward-authored"]
    created_at: datetime
