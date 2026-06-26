"""
ExpressionProfile — a named philosophy of communication that shapes Artist output.

An ExpressionProfile is not a presentation style. It is a complete specification
of how meaning should be realized in language: what to attend to, for whom, in
what register, toward what end.

The Architect Plan remains invariant across all profiles.
Only the Artist changes. This means every profile — including translations —
shares the same semantic commitments. Meaning is stable; expression adapts.
"""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from .base import HermeneiaObject


class ExpressionProfile(HermeneiaObject):
    id: str                              # sha256(slug)
    slug: str                            # url-safe key e.g. "literary-en", "childrens-sw"
    name: str                            # display name e.g. "Literary"
    description: str | None             # one-line description for the UI
    language: str                        # ISO 639-1 code e.g. "en", "sw", "ar"
    audience: str | None                 # e.g. "academic", "children", "executive"
    reading_level: str | None            # e.g. "grade 4", "undergraduate"
    tone: str | None                     # e.g. "formal", "accessible", "analytical"
    voice: str | None                    # e.g. "third-person critical", "narrative"
    artist_prompt: str                   # directive injected into the Artist prompt
    critic_expectations: str | None      # what the Critic should verify
    source: Literal["built-in", "steward-authored"]
    created_at: datetime
