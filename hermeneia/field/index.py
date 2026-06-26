"""
Field v0.1 — deterministic term index.

No AI. No embeddings. No metaphors.

Relationships implemented:
  - adjacent_to   : Observation → Observation (via preceding/following IDs, already in DB)
  - contains_term : Observation → Term (built here)

A Term is any alphabetic token of length ≥ 3 extracted from normalized_text.
Tokens are lowercased. Punctuation is stripped. Stop words are NOT filtered —
the field makes no judgment about which words matter.

The term ID is sha256 of the term string, for determinism.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


_TOKEN_RE = re.compile(r"[a-z][a-z']*")
_MIN_TERM_LEN = 3


def extract_terms(text: str) -> list[str]:
    """Extract unique lowercase alphabetic tokens from a normalized sentence."""
    tokens = _TOKEN_RE.findall(text.lower())
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        t = t.strip("'")  # strip leading/trailing apostrophes
        if len(t) >= _MIN_TERM_LEN and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def term_id(term: str) -> str:
    return hashlib.sha256(term.encode("utf-8")).hexdigest()


def build_term_index(store) -> tuple[int, int]:
    """Build the term index from all observations in the store.

    Returns (terms_indexed, observation_term_pairs).
    Idempotent: INSERT OR IGNORE means safe to call repeatedly.
    """
    all_obs = store.all_observations_with_derived()

    unique_terms: dict[str, str] = {}  # term → term_id
    obs_term_pairs: list[dict] = []

    for obs in all_obs:
        text = obs.get("normalized_text") or obs.get("raw_text", "")
        terms = extract_terms(text)
        for t in terms:
            tid = term_id(t)
            if t not in unique_terms:
                unique_terms[t] = tid
            obs_term_pairs.append({
                "observation_id": obs["id"],
                "term_id": tid,
            })

    # Insert terms
    term_rows = [{"id": tid, "term": t} for t, tid in unique_terms.items()]
    store.insert_terms_batch(term_rows)
    store.insert_observation_terms_batch(obs_term_pairs)

    return len(unique_terms), len(obs_term_pairs)
