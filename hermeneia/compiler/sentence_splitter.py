"""
Deterministic rule-based sentence splitter (ADR-0006, ADR-0014).

Properties:
- No NLP library dependencies (regex only)
- Identical input → identical output on any machine
- Handles common abbreviations to avoid false splits
- Returns verbatim sentence strings (no normalization)

Sentence boundary: [.!?]+ followed by whitespace + uppercase/quote/paren,
unless the preceding token is a known abbreviation or part of a decimal.
"""
from __future__ import annotations

import re

# Abbreviations that should NOT trigger a sentence boundary
# Even when followed by a capital letter.
_ABBREVS: frozenset[str] = frozenset({
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "no",
    "vol", "pp", "ch", "fig", "dept", "approx", "est",
    "rev", "gen", "lt", "col", "sgt", "cpl", "pvt",
    "st", "ave", "blvd", "rd",
    "jan", "feb", "mar", "apr", "aug", "sep", "oct", "nov", "dec",
    "a.m", "p.m", "i.e", "e.g", "etc",
    # single letters (initials): A. B. C. etc.
    *[chr(c) for c in range(ord("a"), ord("z") + 1)],
})

# Matches a sentence-ending punctuation + whitespace boundary
_BOUNDARY = re.compile(r'([.!?]+)(\s+)')


def _is_boundary(text: str, match_start: int) -> bool:
    """Return True if the match at match_start is a real sentence boundary."""
    # Get the token immediately before this punctuation
    preceding = text[:match_start].rstrip()
    # Extract the last word before the punctuation
    last_word_match = re.search(r'\b(\w+)\s*$', preceding)
    if not last_word_match:
        return True
    last_word = last_word_match.group(1).lower()
    if last_word in _ABBREVS:
        return False
    # Don't split on decimal numbers: "3.14 x" — but if followed by capital it's fine
    return True


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph string into a list of sentence strings.

    Does not normalize the paragraph before splitting. The returned strings are
    the raw_text selected for each Observation; normalization is derived later.
    """
    return [paragraph[start:end] for start, end in sentence_spans(paragraph)]


def sentence_spans(paragraph: str) -> list[tuple[int, int]]:
    """Return the ``[start, end)`` offsets of each ``split_sentences`` result.

    Sentence ``n`` (1-indexed) of an Observation is ``paragraph[start:end]`` of
    span ``n - 1`` — the canonical occurrence, recoverable without text search.
    """
    text = paragraph

    if not text or not text.strip():
        return []

    sentences: list[tuple[int, int]] = []
    current_start = 0

    for m in _BOUNDARY.finditer(text):
        punct_start = m.start(1)
        after_end = m.end(2)

        if not _is_boundary(text, punct_start):
            continue

        # Check what comes after the whitespace
        remainder = text[after_end:]
        if not remainder:
            # Boundary at end of text — include punctuation in current sentence
            break

        # Next char must be uppercase, quote, open paren, or digit to split
        next_char = remainder[0]
        if not (next_char.isupper() or next_char in '"\'('):
            continue

        if text[current_start:after_end].strip():
            sentences.append((current_start, after_end))
        current_start = after_end

    # Append the final sentence
    if text[current_start:].strip():
        sentences.append((current_start, len(text)))

    return sentences
