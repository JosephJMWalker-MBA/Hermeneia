"""Deterministic literal concordance helpers.

The concordance layer is a derived, read-only projection. It counts literal
substrings inside the current searchable text representation; it never mutates
canonical evidence and never interprets the term's significance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


MATCHING_MODE = "literal-case-insensitive-substring-v1"
SEARCH_TEXT_SOURCE = "observation_derived.normalized_text_fallback_raw_text"
RESULT_UNIT = "observation"


@dataclass(frozen=True)
class LiteralOccurrence:
    start: int
    end: int
    matched_text: str


def literal_occurrence_spans(text: str, query: str) -> list[LiteralOccurrence]:
    """Return non-overlapping case-insensitive literal substring matches.

    The query is not regex. Punctuation adjacent to the phrase does not affect
    matching because the phrase is searched as a literal substring.
    """
    if not query:
        return []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return [
        LiteralOccurrence(
            start=match.start(),
            end=match.end(),
            matched_text=text[match.start():match.end()],
        )
        for match in pattern.finditer(text)
    ]
