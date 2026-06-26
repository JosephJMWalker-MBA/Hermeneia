"""Stage 1 + Stage 2: Evidence Identification and Evidence-Claim Mapping.

These two stages produce HIGH to MODERATE cross-provider convergence (Experiments 005–007).
They are automatable without AI — operating purely on text overlap and structural analysis.

Stage 1 (identify_evidence): finds observation passages relevant to the interpretation.
Stage 2 (extract_claims): decomposes the interpretation into evaluable claims.

Constitutional note (Experiment 008):
    Claim extraction is not a neutral decomposition step. It is an interpretive act.
    The extracted claim set should be subject to steward review (mark_critic_report_normalized).
    The normalized=0 flag on every new CriticReport records that the claim set is raw.
"""
from __future__ import annotations

import re


def identify_evidence(observation_text: str, interpretation_text: str) -> list[str]:
    """Stage 1: Extract passages from observation_text that are relevant to interpretation_text.

    Strategy: sentence-level overlap detection.
    - Split observation into candidate passages (by sentence boundary or the whole text).
    - Return passages that share significant lexical content with the interpretation.
    - Always returns at least the full observation text as a fallback.

    HIGH convergence stage — these are the passages every provider finds.
    Returns a deduplicated list of passage strings, most specific first.
    """
    if not observation_text or not interpretation_text:
        return [observation_text] if observation_text else []

    obs_sentences = _split_sentences(observation_text)
    interp_tokens = _tokenize(interpretation_text)

    scored: list[tuple[float, str]] = []
    for sentence in obs_sentences:
        sent_tokens = _tokenize(sentence)
        if not sent_tokens:
            continue
        overlap = len(sent_tokens & interp_tokens) / len(sent_tokens)
        if overlap > 0.0:
            scored.append((overlap, sentence))

    scored.sort(key=lambda t: t[0], reverse=True)
    passages = [s for _, s in scored if s.strip()]

    # Always include the full observation text if not already present
    if observation_text.strip() not in passages:
        passages.append(observation_text.strip())

    return _deduplicate(passages)


def extract_claims(interpretation_text: str) -> list[str]:
    """Stage 2: Decompose interpretation_text into evaluable propositions.

    Strategy: sentence-boundary decomposition followed by clause-level splitting.

    Splitting order per sentence:
    1. Adversative conjunctions (but, however, yet, although, while, …)
    2. Participial / appositive commas (, anchored to X / , suggesting that X)
       These mark a secondary proposition attached to the primary clause.

    Each split produces complete propositional units — subject-verb-predicate
    structures that can be individually evaluated against evidence.

    Constitutional note: this is not a neutral parser. Claim granularity is a
    policy choice. The steward should review the produced claim set via
    mark_critic_report_normalized() before treating verdicts as authoritative.
    Experiment 008 finding: the granularity at which claims are extracted is itself
    an interpretive act. Two readers of the same interpretation may draw different
    claim boundaries.

    Returns a list of claim strings, in document order.
    """
    if not interpretation_text or not interpretation_text.strip():
        return []

    sentences = _split_sentences(interpretation_text)
    claims: list[str] = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue

        # Pass 1: adversative split
        sub_claims = _split_adversative(sentence)

        # Pass 2: participial split on any sub-claim that is still a single unit
        final_claims: list[str] = []
        for sub in sub_claims:
            participial = _split_participial(sub)
            final_claims.extend(participial)

        claims.extend(final_claims)

    if not claims:
        claims = [interpretation_text.strip()]

    return claims


# ── Internal helpers ──────────────────────────────────────────────────────────

_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z"])|(?<=—)\s+(?=[A-Z])')
_ADVERSATIVE = re.compile(
    r'\b(?:but|however|yet|although|while|whereas|nevertheless|nonetheless|even\s+so)\b',
    re.IGNORECASE,
)
# Participial / appositive comma: comma followed by a past-participle or gerund
# that introduces a secondary propositional clause ("the reading is X, anchored to Y")
_PARTICIPIAL = re.compile(
    r',\s*(?='
    r'(?:anchored|grounded|rooted|situated|tied|linked|based|derived|drawn|taken|'
    r'showing|suggesting|indicating|implying|demonstrating|reveal(?:ing)?|'
    r'emphasiz(?:ing)?|highlight(?:ing)?|captur(?:ing)?|reflect(?:ing)?|'
    r'assert(?:ing)?|claim(?:ing)?|argu(?:ing)?|provid(?:ing)?|'
    r'with(?:out)?|through|despite|rather|instead)'
    r'\b)',
    re.IGNORECASE,
)
_WORD = re.compile(r'\b[a-z]+\b', re.IGNORECASE)


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_BOUNDARY.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_adversative(sentence: str) -> list[str]:
    """Split a sentence at an adversative conjunction into two propositional claims."""
    match = _ADVERSATIVE.search(sentence)
    if match is None:
        return [sentence]
    before = sentence[: match.start()].strip().rstrip(',').strip()
    after = sentence[match.end() :].strip()
    parts = []
    if before and len(before) >= 10:
        parts.append(before)
    if after and len(after) >= 10:
        parts.append(after)
    return parts if len(parts) == 2 else [sentence]


def _split_participial(sentence: str) -> list[str]:
    """Split on a participial / appositive comma into primary + secondary proposition.

    "The reading is open to interpretation, anchored to the observed wording."
    → ["The reading is open to interpretation", "anchored to the observed wording"]

    The secondary clause inherits the subject from the primary clause by context.
    Both are treated as evaluable propositions against the observation.
    """
    match = _PARTICIPIAL.search(sentence)
    if match is None:
        return [sentence]
    before = sentence[: match.start()].strip()
    after = sentence[match.end() :].strip()
    if before and len(before) >= 10 and after and len(after) >= 10:
        return [before, after]
    return [sentence]


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
