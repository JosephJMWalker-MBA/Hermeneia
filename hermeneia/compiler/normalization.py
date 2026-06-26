"""
Text normalization for the Hermeneia compiler.

Design principle: Observations endure. The canonical layer is raw_text.
normalized_text is a convenience layer derived from raw_text — never the reverse.

Two normalization stages:
  1. normalize_paragraph()  — applied before sentence splitting
     Repairs PDF rendering artifacts (soft line breaks, text reflow).

  2. normalize_sentence()   — applied to each sentence after splitting
     Applies semantic normalizations (Unicode quotes, whitespace).

Preservation rules (things we NEVER touch):
  - Em dash  — (U+2014): carries semantic weight in prose; preserved verbatim
  - En dash  – (U+2013): used in ranges and compounds; preserved verbatim
  - Intentional hyphens: "well-known" has no \n after the hyphen; untouched
  - Ellipsis …: preserved
  - Content: zero words are added, removed, or substituted
"""
from __future__ import annotations

import re
import unicodedata

# ── Stage 1: paragraph-level (artifact repair) ────────────────────────────────

def normalize_paragraph(raw: str) -> str:
    """Repair PDF text-reflow artifacts before sentence splitting.

    Soft line break: a hyphen at end of a word followed by a newline and
    the continuation of that word. Example: "van-\nished" → "vanished".
    Intentional hyphens (no newline) are NOT touched: "well-known" stays.
    """
    # 1. Dehyphenate soft line breaks: lowercase-letter + hyphen + newline + lowercase-letter
    #    "van-\nished" → "vanished"
    #    "well-\nknown" → "wellknown"  (intentional hyphens won't have \n, so this is safe)
    text = re.sub(r'([a-zA-Z])-\n([a-zA-Z])', r'\1\2', raw)

    # 2. Remaining newlines are paragraph-internal reflow; convert to space
    text = re.sub(r'\n', ' ', text)

    # 3. Collapse runs of spaces (but not em-dash surroundings)
    text = re.sub(r'  +', ' ', text)

    return text.strip()


# ── Stage 2: sentence-level (semantic normalization) ─────────────────────────

# Unicode directional quotes → ASCII equivalents
_QUOTE_MAP: dict[str, str] = {
    '“': '"',   # LEFT DOUBLE QUOTATION MARK  "
    '”': '"',   # RIGHT DOUBLE QUOTATION MARK "
    '‘': "'",   # LEFT SINGLE QUOTATION MARK  '
    '’': "'",   # RIGHT SINGLE QUOTATION MARK '
    '‚': "'",   # SINGLE LOW-9 QUOTATION MARK ‚
    '„': '"',   # DOUBLE LOW-9 QUOTATION MARK „
    '«': '"',   # LEFT-POINTING DOUBLE ANGLE «
    '»': '"',   # RIGHT-POINTING DOUBLE ANGLE »
}

# Characters to PRESERVE exactly — never substitute
_PRESERVE: frozenset[str] = frozenset({
    '—',  # EM DASH —
    '–',  # EN DASH –
    '…',  # HORIZONTAL ELLIPSIS …
})


def normalize_sentence(raw: str) -> str:
    """Apply semantic normalizations to a sentence string.

    Preserves: em dash, en dash, ellipsis, intentional hyphens.
    Normalizes: Unicode directional quotes → ASCII, whitespace collapse.
    """
    text = raw

    # 1. Normalize directional quotes to ASCII equivalents
    for src, dst in _QUOTE_MAP.items():
        text = text.replace(src, dst)

    # 2. Normalize Unicode whitespace variants to plain space
    #    (non-breaking space, thin space, etc.) — but NOT em/en dash
    result = []
    for ch in text:
        if ch in _PRESERVE:
            result.append(ch)
        elif unicodedata.category(ch) == 'Zs':  # Unicode space separator
            result.append(' ')
        else:
            result.append(ch)
    text = ''.join(result)

    # 3. Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)

    return text.strip()


# ── Combined convenience function ─────────────────────────────────────────────

def normalize_for_indexing(sentence: str) -> str:
    """Full normalization pipeline for a sentence.

    Use this when the sentence has already been split from a normalized paragraph.
    Applies sentence-level normalizations only.
    """
    return normalize_sentence(sentence)
