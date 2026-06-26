"""
Architect — deterministic compiler from NarrativeBlueprint to ArchitectPlan.

No prose. No LLM. No randomness.
Identical Blueprint input always produces identical ArchitectPlan output.

Algorithm per BlueprintSection:
  1. purpose             = section.claim
  2. required_obs        = section.supporting_observations (preserved verbatim)
  3. required_interps    = section.supporting_interpretations (preserved verbatim)
  4. required_terms      = semantic obligations extracted from:
                             (a) the section's claim text       [primary source]
                             (b) linked interpretation texts    [secondary source]
                           Extraction: content n-grams (2-3 words) ranked by
                           coverage across claim + interpretation sources,
                           then content unigrams (≥4 chars, non-stopword).
                           Top 3 → critical, rest → recommended.
                           Previous approach (word-token frequency from obs)
                           produced lexical artifacts ("the", "and", "from").
                           Obligations are now semantic phrases, not tokens.
  5. forbidden_claims    = () for now (Critic adds these later)
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

# ── Stopword filter ────────────────────────────────────────────────────────────
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "of", "in", "to", "is", "it",
    "that", "this", "with", "for", "on", "at", "be", "as", "by", "not",
    "are", "was", "were", "has", "have", "had", "he", "she", "they",
    "his", "her", "its", "their", "him", "them", "who", "which", "what",
    "from", "into", "than", "then", "when", "where", "while", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "so", "yet", "up", "out", "if", "do", "did",
    "does", "been", "will", "would", "could", "should", "may", "might",
    "must", "can", "also", "just", "only", "even", "over", "after",
    "before", "between", "through", "about", "because", "since", "until",
    "rather", "therefore", "thus", "however", "although", "though",
})

_WORD_RE = re.compile(r"\b[a-zA-Z][a-zA-Z'-]{2,}\b")


def _content_words(text: str) -> list[str]:
    """Return non-stopword words of ≥4 chars from text, lowercased."""
    return [
        w.lower() for w in _WORD_RE.findall(text)
        if w.lower() not in _STOPWORDS and len(w) >= 4
    ]


def _bigrams(words: list[str]) -> list[str]:
    """Return consecutive two-word phrases."""
    return [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]


def _trigrams(words: list[str]) -> list[str]:
    """Return consecutive three-word phrases."""
    return [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words) - 2)]


def _semantic_obligations(
    claim: str,
    interp_texts: list[str],
) -> list[dict]:
    """
    Extract semantic obligations from a section claim and its linked interpretations.

    Priority order:
      1. Bigrams and trigrams that appear in the claim (highest semantic density)
      2. Bigrams from interpretations that also appear in the claim (cross-validated)
      3. Content unigrams from the claim (fallback)

    Returns list of {"term": str, "priority": "critical"|"recommended"}.
    Top 3 → critical.
    """
    claim_words = _content_words(claim)
    claim_bigrams = _bigrams(claim_words)
    claim_trigrams = _trigrams(claim_words)

    # Score each candidate by how many sources it appears in
    scores: dict[str, int] = {}

    # Trigrams from claim: high value — they encode specific semantic claims
    for phrase in claim_trigrams:
        scores[phrase] = scores.get(phrase, 0) + 3

    # Bigrams from claim
    for phrase in claim_bigrams:
        scores[phrase] = scores.get(phrase, 0) + 2

    # Bigrams from interpretations that overlap with claim vocabulary
    claim_word_set = set(claim_words)
    for interp_text in interp_texts:
        interp_words = _content_words(interp_text)
        for phrase in _bigrams(interp_words):
            parts = phrase.split()
            # Only include if it shares vocabulary with the claim
            if any(p in claim_word_set for p in parts):
                scores[phrase] = scores.get(phrase, 0) + 1

    # Content unigrams from claim as fallback (lower base score)
    for word in claim_words:
        if word not in scores:
            scores[word] = 1

    # Deduplicate: if a bigram is present, suppress its component unigrams
    covered_words: set[str] = set()
    for phrase in list(scores.keys()):
        if " " in phrase:
            for part in phrase.split():
                covered_words.add(part)

    final: dict[str, int] = {
        phrase: score
        for phrase, score in scores.items()
        if " " in phrase or phrase not in covered_words
    }

    ranked = sorted(final.items(), key=lambda kv: (-kv[1], kv[0]))

    result = []
    for rank_idx, (term, _score) in enumerate(ranked):
        priority = "critical" if rank_idx < 3 else "recommended"
        result.append({"term": term, "priority": priority})

    return result


def compile_architect_plan(
    blueprint_id: str,
    conn: sqlite3.Connection,
) -> dict:
    """Compile an ArchitectPlan for the given blueprint.

    Returns a dict with keys: plan_row, paragraph_rows — ready for
    SQLiteStore.insert_architect_plan().

    Raises ValueError if the blueprint is not found.
    """
    from ..storage.hashing import make_architect_plan_id, make_blueprint_id

    # ── Load blueprint ──────────────────────────────────────────────────────
    bp_row = conn.execute(
        "SELECT * FROM narrative_blueprints WHERE id = ?", (blueprint_id,)
    ).fetchone()
    if bp_row is None:
        raise ValueError(f"Blueprint not found: {blueprint_id}")

    bp = dict(bp_row)
    sections = json.loads(bp["sections"])

    blueprint_hash = make_blueprint_id(bp["title"], bp["thesis"], sections)
    plan_id = make_architect_plan_id(blueprint_id)

    # ── Compile paragraphs ──────────────────────────────────────────────────
    paragraph_rows = []
    for section_idx, section in enumerate(sections):
        obs_ids    = section.get("supporting_observations", [])
        interp_ids = section.get("supporting_interpretations", [])

        # Load linked interpretation texts for semantic cross-validation
        interp_texts: list[str] = []
        for iid in interp_ids:
            row = conn.execute(
                "SELECT text FROM interpretations WHERE id = ?", (iid,)
            ).fetchone()
            if row and row[0]:
                interp_texts.append(row[0])

        # Semantic obligation extraction from claim + interpretations
        required_terms = _semantic_obligations(section["claim"], interp_texts)

        paragraph_rows.append({
            "plan_id":                  plan_id,
            "order_idx":                section_idx + 1,
            "purpose":                  section["claim"],
            "blueprint_section":        section_idx + 1,
            "required_observations":    json.dumps(obs_ids),
            "required_interpretations": json.dumps(interp_ids),
            "required_terms":           json.dumps(required_terms),
            "forbidden_claims":         json.dumps([]),
            "notes":                    None,
        })

    plan_row = {
        "id":             plan_id,
        "blueprint_id":   blueprint_id,
        "blueprint_hash": blueprint_hash,
        "title":          bp["title"],
        "source":         "deterministic",
        "created_at":     datetime.now(timezone.utc).isoformat(),
    }

    return {"plan_row": plan_row, "paragraph_rows": paragraph_rows}
