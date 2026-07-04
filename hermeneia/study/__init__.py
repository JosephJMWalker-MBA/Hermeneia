"""Study layer - the deterministic core of the interpretation compiler (Issue #35).

The user marks meaning; the machine reasons over the marked meaning. This package
holds the deterministic substrate that organizes a reader's ranked marks into a
structured study summary. AI enrichment (Blueprint Layer 3) builds on top of this;
it never replaces it.
"""
from .compiler import MARK_TYPES, RANK_LABELS, classify_mark, compile_study

__all__ = ["MARK_TYPES", "RANK_LABELS", "classify_mark", "compile_study"]
