"""SystemPrompt — a named theme that shapes Artist output."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from .base import HermeneiaObject


class SystemPrompt(HermeneiaObject):
    id: str                              # sha256(slug)
    slug: str                            # url-safe key e.g. "literary"
    name: str                            # display name e.g. "Literary"
    focus: str                           # what to attend to
    quality_criteria: str                # what a good output looks like
    source: Literal["built-in", "steward-authored"]
    created_at: datetime
