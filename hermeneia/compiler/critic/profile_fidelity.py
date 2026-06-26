"""
Profile fidelity evaluation — deterministic expression contract checks.

The Critic's semantic checks verify WHAT was said matches the Architect Plan.
These checks verify HOW it was said matches the ExpressionProfile contract.

Each check returns:
  { "expectation": str, "passed": bool, "evidence": str }

Checks are registered per profile slug. Where no checks are registered,
the module returns an explicit "not yet implemented" rather than a false pass.
"""
from __future__ import annotations

import re


# ── Primitive text utilities ───────────────────────────────────────────────────

def _sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in parts if s.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r"\b[a-zA-Z']+\b", text.lower())


# ── Individual check functions ─────────────────────────────────────────────────

def _check_no_long_sentences(text: str, max_words: int = 25) -> dict:
    sents = _sentences(text)
    long_sents = [s for s in sents if len(s.split()) > max_words]
    if long_sents:
        example = long_sents[0][:90] + ("…" if len(long_sents[0]) > 90 else "")
        return {
            "expectation": f"No sentence exceeds {max_words} words",
            "passed": False,
            "evidence": f"{len(long_sents)} long sentence(s). Example: “{example}”",
        }
    return {
        "expectation": f"No sentence exceeds {max_words} words",
        "passed": True,
        "evidence": f"All {len(sents)} sentences within limit.",
    }


def _check_no_passive_voice(text: str) -> dict:
    pattern = re.compile(
        r'\b(was|were|is|are|been|be|being)\s+\w+(?:ed|en)\b', re.IGNORECASE
    )
    matches = pattern.findall(text)
    if matches:
        return {
            "expectation": "No passive voice",
            "passed": False,
            "evidence": f"{len(matches)} passive construction(s) detected.",
        }
    return {
        "expectation": "No passive voice",
        "passed": True,
        "evidence": "No passive constructions found.",
    }


def _check_no_long_words(text: str, max_len: int = 11) -> dict:
    common_exceptions = {"understanding", "interpretation", "particularly",
                         "relationship", "imagination", "extraordinary"}
    words = _words(text)
    long_words = [w for w in words if len(w) > max_len and w not in common_exceptions]
    unique_long = list(dict.fromkeys(long_words))[:5]
    if unique_long:
        return {
            "expectation": f"No words longer than {max_len} characters (jargon proxy for young readers)",
            "passed": False,
            "evidence": f"Long words found: {', '.join(unique_long)}",
        }
    return {
        "expectation": f"No words longer than {max_len} characters (jargon proxy for young readers)",
        "passed": True,
        "evidence": "All words within accessible length.",
    }


def _check_no_rhetorical_questions(text: str) -> dict:
    sents = _sentences(text)
    questions = [s for s in sents if s.rstrip().endswith("?")]
    if questions:
        return {
            "expectation": "No rhetorical questions",
            "passed": False,
            "evidence": f"{len(questions)} question(s) found.",
        }
    return {
        "expectation": "No rhetorical questions",
        "passed": True,
        "evidence": "No questions found.",
    }


def _check_no_hedged_language(text: str) -> dict:
    hedge_phrases = [
        "perhaps", "maybe", "might suggest", "one might argue",
        "it could be", "it seems", "it appears", "arguably",
        "in a sense", "in some ways", "somewhat", "it is possible that",
        "we might", "one could", "it may be",
    ]
    text_lower = text.lower()
    found = [h for h in hedge_phrases if h in text_lower]
    if found:
        return {
            "expectation": "No hedged conclusions",
            "passed": False,
            "evidence": f"Hedged language detected: {', '.join(found)}",
        }
    return {
        "expectation": "No hedged conclusions",
        "passed": True,
        "evidence": "No hedge phrases detected.",
    }


def _check_declarative_opening(text: str) -> dict:
    sents = _sentences(text)
    first = sents[0] if sents else ""
    if first.rstrip().endswith("?"):
        return {
            "expectation": "Opens with declarative conclusion (not a question)",
            "passed": False,
            "evidence": f"First sentence is a question: “{first[:80]}”",
        }
    return {
        "expectation": "Opens with declarative conclusion (not a question)",
        "passed": True,
        "evidence": f"Opening: “{first[:80]}”",
    }


def _check_literary_vocabulary(text: str) -> dict:
    literary_terms = [
        "symbol", "metaphor", "motif", "imagery", "irony", "allegory",
        "diction", "syntax", "voice", "juxtaposition", "allusion", "subtext",
        "figur", "aesthetic", "narrative arc", "prose", "register", "trope",
    ]
    text_lower = text.lower()
    found = [t for t in literary_terms if t in text_lower]
    threshold = 3
    if len(found) < threshold:
        return {
            "expectation": f"Names at least {threshold} specific literary/formal devices",
            "passed": False,
            "evidence": (
                f"Only {len(found)} critical term(s): {', '.join(found) or 'none'}"
            ),
        }
    return {
        "expectation": f"Names at least {threshold} specific literary/formal devices",
        "passed": True,
        "evidence": f"{len(found)} device(s): {', '.join(found[:6])}",
    }


def _check_no_plot_summary(text: str) -> dict:
    summary_patterns = [
        r"\bthen he\b", r"\bthen she\b", r"\bthen they\b",
        r"\bnext,?\s+", r"\bafter that\b", r"\bthe story\b",
        r"\bthe plot\b", r"\bwhat happens\b", r"\bhe goes\b", r"\bshe goes\b",
    ]
    text_lower = text.lower()
    hits = [p for p in summary_patterns if re.search(p, text_lower)]
    if hits:
        return {
            "expectation": "Avoids plot summary language",
            "passed": False,
            "evidence": f"{len(hits)} summary pattern(s) detected.",
        }
    return {
        "expectation": "Avoids plot summary language",
        "passed": True,
        "evidence": "No plot summary patterns found.",
    }


def _check_psychoanalytic_vocabulary(text: str) -> dict:
    vocab = [
        "desire", "lack", "repression", "repressed", "displacement",
        "unconscious", "latent", "manifest", "compulsion", "repetition",
        "anxiety", "ego", "drive", "cathex", "abjection", "jouissance",
    ]
    text_lower = text.lower()
    found = [v for v in vocab if v in text_lower]
    if len(found) < 2:
        return {
            "expectation": "Uses psychoanalytic register (desire, lack, displacement, etc.)",
            "passed": False,
            "evidence": f"Only {len(found)} psychoanalytic term(s): {', '.join(found) or 'none'}",
        }
    return {
        "expectation": "Uses psychoanalytic register",
        "passed": True,
        "evidence": f"Terms present: {', '.join(found[:5])}",
    }


def _check_no_pop_psychology(text: str) -> dict:
    pop_terms = [
        "self-esteem", "toxic", "trauma response", "emotionally scarred",
        "mental health", "coping mechanism", "closure", "healing journey",
        "inner child", "narcissistic", "boundaries", "unpack",
    ]
    text_lower = text.lower()
    found = [t for t in pop_terms if t in text_lower]
    if found:
        return {
            "expectation": "Avoids pop-psychology reduction",
            "passed": False,
            "evidence": f"Reductive terms detected: {', '.join(found)}",
        }
    return {
        "expectation": "Avoids pop-psychology reduction",
        "passed": True,
        "evidence": "No pop-psychology terms detected.",
    }


def _check_avoids_vague_social(text: str) -> dict:
    vague_phrases = [
        "society as a whole", "people in general", "everyone knows",
        "things were different", "the way things were",
        "back in those days",
    ]
    # "society" alone is acceptable; only flag clearly unspecified usage
    text_lower = text.lower()
    found = [p for p in vague_phrases if p in text_lower]
    if found:
        return {
            "expectation": "Names specific historical forces rather than vague 'society'",
            "passed": False,
            "evidence": f"Vague phrases found: {', '.join(found)}",
        }
    return {
        "expectation": "Names specific historical forces rather than vague 'society'",
        "passed": True,
        "evidence": "No unspecified social generalisations detected.",
    }


# ── Check registry ─────────────────────────────────────────────────────────────
# Keys are profile slugs. Functions receive (text: str) -> dict.

_CHECKS: dict[str, list] = {
    "childrens-en": [
        _check_no_long_sentences,
        _check_no_passive_voice,
        _check_no_long_words,
    ],
    "executive-en": [
        _check_declarative_opening,
        _check_no_rhetorical_questions,
        _check_no_hedged_language,
    ],
    "literary-en": [
        _check_literary_vocabulary,
        _check_no_plot_summary,
    ],
    "literary-es": [_check_no_plot_summary],
    "literary-fr": [_check_no_plot_summary],
    "literary-zh": [_check_no_plot_summary],
    "literary-sw": [_check_no_plot_summary],
    "historical-en": [
        _check_avoids_vague_social,
    ],
    "psychoanalytic-en": [
        _check_psychoanalytic_vocabulary,
        _check_no_pop_psychology,
    ],
}


# ── Public interface ───────────────────────────────────────────────────────────

def check_profile_fidelity(text: str, profile: dict) -> dict:
    """Evaluate rendered text against the profile's expression contract.

    Semantic fidelity (did the required meaning survive?) is handled by the
    main Critic. This function asks the complementary question: did the
    required expression survive?

    Returns a self-contained dict suitable for JSON storage.
    """
    slug = profile.get("slug", "")
    check_fns = _CHECKS.get(slug, [])
    expectations = profile.get("critic_expectations", "")

    if not check_fns:
        return {
            "profile_name": profile.get("name", slug),
            "profile_slug": slug,
            "expectations": expectations,
            "checks": [],
            "profile_fidelity_score": None,
            "profile_approved": None,
            "note": "No deterministic checks defined for this profile yet.",
        }

    results = [fn(text) for fn in check_fns]
    passed = sum(1 for r in results if r["passed"])
    score = round(passed / len(results) * 100, 1)

    return {
        "profile_name": profile.get("name", slug),
        "profile_slug": slug,
        "expectations": expectations,
        "checks": results,
        "profile_fidelity_score": score,
        "profile_approved": passed == len(results),  # all checks must pass
    }
