"""Stage 3: Verdict Classification under named evaluation policies.

Four stable policies empirically identified across Experiments 005–008:

    conservative            — absence of support = Unsupported; no contradiction required
    decomposition           — split claim into components; aggregate per-component verdicts
    contradiction_sensitive — key-term semantic violation = Contradicted
    aggregate_weighting     — weigh supporting vs. challenging evidence; partial if both

Policy is POLICY DEPENDENT (LOW cross-provider convergence). The steward selects
the policy at CriticReport generation time. The policy is stored in the report.

Constitutional consequence: the steward governs policy selection. Verdicts from
different policies on the same claim are all valid — they reflect different epistemic
standards, not factual disagreements.
"""
from __future__ import annotations

import re

VALID_POLICIES = frozenset({
    "conservative",
    "decomposition",
    "contradiction_sensitive",
    "aggregate_weighting",
})

VERDICT_SUPPORTED = "supported"
VERDICT_PARTIALLY = "partially_supported"
VERDICT_UNSUPPORTED = "unsupported"
VERDICT_CONTRADICTED = "contradicted"

_WORD = re.compile(r'\b[a-z]+\b', re.IGNORECASE)

# Words that signal epistemic hedging in an evidence passage
_HEDGE_WORDS = frozenset({
    "seemed", "seem", "appears", "appear", "perhaps", "maybe", "might",
    "could", "possibly", "presumably", "apparently", "supposedly",
    "questioned", "uncertain", "unclear", "ambiguous", "suggested",
})

# Antonym pairs: if claim uses the key word and evidence contains the value word,
# flag as a semantic contradiction candidate.
_ANTONYM_PAIRS: dict[str, frozenset[str]] = {
    "unquestionably": frozenset({"seemed", "seem", "questioned", "uncertain"}),
    "objectively": frozenset({"prejudice", "bias", "subjective", "partial", "partiality"}),
    "undifferentiated": frozenset({"distinct", "separate", "individual", "different", "named"}),
    "unified": frozenset({"separate", "distinct", "divided", "individual"}),
    "constant": frozenset({"rare", "occasional", "sometimes", "episodic"}),
    "genuine": frozenset({"seemed", "performed", "appear", "fake", "false"}),
    "simple": frozenset({"complex", "complicated", "intricate", "elaborate"}),
    "complete": frozenset({"partial", "incomplete", "fragment", "part"}),
}


def apply_policy(
    claim: str,
    evidence_passages: list[str],
    policy: str,
) -> dict:
    """Classify a single claim against evidence under a named policy.

    Returns a dict:
        {
            "claim": str,
            "verdict": str,          # one of VERDICT_* constants
            "evidence_cited": list[str],
            "rationale": str,
            "policy": str,
        }
    """
    if policy not in VALID_POLICIES:
        raise ValueError(f"Unknown policy {policy!r}. Valid: {sorted(VALID_POLICIES)}")

    if policy == "conservative":
        return _apply_conservative(claim, evidence_passages)
    if policy == "decomposition":
        return _apply_decomposition(claim, evidence_passages)
    if policy == "contradiction_sensitive":
        return _apply_contradiction_sensitive(claim, evidence_passages)
    if policy == "aggregate_weighting":
        return _apply_aggregate_weighting(claim, evidence_passages)
    raise ValueError(f"Unhandled policy: {policy!r}")  # unreachable


def aggregate_overall_verdict(claim_results: list[dict]) -> str:
    """Aggregate per-claim verdicts into a single overall verdict.

    Rules (conservative aggregation — the weakest verdict determines the floor):
    - Any Contradicted → overall = Contradicted
    - Any Unsupported (no Contradicted) → overall = Unsupported
    - All Supported → overall = Supported
    - Mix of Supported + Partially_Supported → overall = Partially_Supported
    - All Partially_Supported → overall = Partially_Supported
    """
    if not claim_results:
        return VERDICT_UNSUPPORTED

    verdicts = {r["verdict"] for r in claim_results}

    if VERDICT_CONTRADICTED in verdicts:
        return VERDICT_CONTRADICTED
    if VERDICT_UNSUPPORTED in verdicts:
        return VERDICT_UNSUPPORTED
    if VERDICT_PARTIALLY in verdicts:
        return VERDICT_PARTIALLY
    return VERDICT_SUPPORTED


# ── Policy implementations ────────────────────────────────────────────────────

def _apply_conservative(claim: str, passages: list[str]) -> dict:
    """Conservative policy (Meta-style): absence of support = Unsupported.

    Active contradiction is not required for Unsupported. No Contradicted verdict
    is ever returned under the conservative policy — only Supported or Unsupported.
    """
    supporting = _find_supporting(claim, passages)
    if supporting:
        return _result(claim, VERDICT_SUPPORTED, supporting,
                       "Evidence is present and directly supports the claim.", "conservative")
    return _result(claim, VERDICT_UNSUPPORTED, [],
                   "No supporting evidence was identified. "
                   "Absence of support is sufficient for Unsupported under the conservative policy.",
                   "conservative")


def _apply_decomposition(claim: str, passages: list[str]) -> dict:
    """Decomposition policy (Claude-style): split claim into sub-propositions; evaluate each.

    Sub-propositions are syntactic clauses (adversative splits, participial phrases,
    comma-delimited independent clauses) — not individual words. Each sub-proposition
    is evaluated as a complete propositional unit against the evidence passages using
    token-overlap detection, with antonym opposition checked separately.

    This is proposition-level decomposition, not word-level decomposition.
    See research/synthesis_001 — Experiment 008 finding: claim granularity is a
    policy choice, not a neutral parsing step.
    """
    sub_propositions = _decompose_into_propositions(claim)

    if not sub_propositions:
        return _apply_conservative(claim, passages)

    prop_verdicts: list[str] = []
    prop_notes: list[str] = []
    cited: list[str] = []

    for prop in sub_propositions:
        supporting = _find_supporting(prop, passages)
        opposing = _find_semantic_opposition(prop, passages)

        if opposing and not supporting:
            prop_verdicts.append(VERDICT_CONTRADICTED)
            prop_notes.append(f"'{_truncate(prop)}': semantically opposed by evidence")
            cited.extend(opposing)
        elif supporting:
            prop_verdicts.append(VERDICT_SUPPORTED)
            prop_notes.append(f"'{_truncate(prop)}': supported")
            cited.extend(supporting)
        else:
            prop_verdicts.append(VERDICT_UNSUPPORTED)
            prop_notes.append(f"'{_truncate(prop)}': no supporting evidence found")

    cited = list(dict.fromkeys(cited))  # deduplicate preserving order
    rationale = "; ".join(prop_notes)

    if VERDICT_CONTRADICTED in prop_verdicts:
        verdict = VERDICT_CONTRADICTED
    elif VERDICT_UNSUPPORTED in prop_verdicts:
        verdict = VERDICT_PARTIALLY if VERDICT_SUPPORTED in prop_verdicts else VERDICT_UNSUPPORTED
    else:
        verdict = VERDICT_SUPPORTED

    return _result(claim, verdict, cited, f"Decomposition ({len(sub_propositions)} sub-propositions): {rationale}", "decomposition")


def _apply_contradiction_sensitive(claim: str, passages: list[str]) -> dict:
    """Contradiction-Sensitive policy (Gemini-style).

    If a claim's load-bearing term has a semantic antonym in the evidence, verdict = Contradicted.
    Requires direct lexical or antonym-pair collision, not mere insufficiency.
    """
    claim_tokens = _tokenize(claim)
    all_text = " ".join(passages).lower()

    for antonym_key, antonym_vals in _ANTONYM_PAIRS.items():
        if antonym_key.lower() in claim_tokens:
            for aval in antonym_vals:
                if re.search(r'\b' + re.escape(aval) + r'\b', all_text):
                    cited = [p for p in passages if re.search(r'\b' + re.escape(aval) + r'\b', p, re.IGNORECASE)]
                    return _result(
                        claim, VERDICT_CONTRADICTED, cited,
                        f"Claim uses '{antonym_key}'; evidence contains '{aval}' — "
                        f"a definitional opposition under the contradiction-sensitive policy.",
                        "contradiction_sensitive",
                    )

    # Check for hedge words in evidence that undercut absolute claim terms
    hedge_found = []
    for passage in passages:
        for hw in _HEDGE_WORDS:
            if re.search(r'\b' + re.escape(hw) + r'\b', passage, re.IGNORECASE):
                hedge_found.append((hw, passage))

    absolute_terms = frozenset({"unquestionably", "certainly", "definitively", "objectively", "always", "never"})
    if hedge_found and (claim_tokens & absolute_terms):
        cited = list(dict.fromkeys(p for _, p in hedge_found))
        hedges = list(dict.fromkeys(h for h, _ in hedge_found))
        return _result(
            claim, VERDICT_CONTRADICTED, cited,
            f"Claim asserts absolute certainty; evidence contains epistemic hedges ({', '.join(hedges[:3])}) "
            f"that mechanically invalidate the absolute qualifier.",
            "contradiction_sensitive",
        )

    # Fall through to standard support check
    supporting = _find_supporting(claim, passages)
    if supporting:
        return _result(claim, VERDICT_SUPPORTED, supporting,
                       "No semantic contradictions found; evidence supports the claim.",
                       "contradiction_sensitive")
    return _result(claim, VERDICT_UNSUPPORTED, [],
                   "No contradiction found, but no supporting evidence identified either.",
                   "contradiction_sensitive")


def _apply_aggregate_weighting(claim: str, passages: list[str]) -> dict:
    """Aggregate-Weighting policy (GPT/Grok-style).

    Weigh supporting vs. challenging evidence. Returns Partially Supported when
    both types are present. Returns Supported when only supporting evidence exists.
    Returns Unsupported when no evidence of either type is found.
    """
    supporting = _find_supporting(claim, passages)
    challenging = _find_challenging(claim, passages)

    if supporting and challenging:
        cited = list(dict.fromkeys(supporting + challenging))
        return _result(claim, VERDICT_PARTIALLY, cited,
                       f"Both supporting ({len(supporting)}) and challenging ({len(challenging)}) "
                       f"evidence passages found. Partially supported under aggregate weighting.",
                       "aggregate_weighting")
    if supporting:
        return _result(claim, VERDICT_SUPPORTED, supporting,
                       "Supporting evidence found; no challenging evidence identified.",
                       "aggregate_weighting")
    return _result(claim, VERDICT_UNSUPPORTED, [],
                   "No supporting or challenging evidence identified.",
                   "aggregate_weighting")


# ── Text-analysis helpers ─────────────────────────────────────────────────────

# Participial / appositive markers that signal a secondary proposition
_PARTICIPIAL_SPLIT = re.compile(
    r',\s*(?='
    r'(?:anchored|grounded|rooted|situated|tied|linked|based|derived|drawn|taken|'
    r'showing|suggesting|indicating|implying|demonstrating|reveal(?:ing)?|'
    r'emphasiz(?:ing)?|highlight(?:ing)?|captur(?:ing)?|reflect(?:ing)?|'
    r'assert(?:ing)?|claim(?:ing)?|argu(?:ing)?|provid(?:ing)?|'
    r'with(?:out)?|through|despite|regard(?:less)?|rather|instead)'
    r'\b)',
    re.IGNORECASE,
)

# Clause-boundary comma followed by a subject-like token (pronoun or proper-case word)
_CLAUSE_COMMA = re.compile(r',\s+(?=[A-Z](?:[a-z]+\s){1,3}(?:is|are|was|were|has|have|had|does|did|will|would|can|could|should|may|might)\b)', re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


def _decompose_into_propositions(claim: str) -> list[str]:
    """Split a claim into sub-propositions at syntactic clause boundaries.

    This is proposition-level decomposition — each part is a complete semantic unit
    that can be evaluated against evidence in full, not a single extracted keyword.

    Split order:
    1. Adversative conjunctions (but, however, yet, although, while, …)
    2. Participial / appositive commas (, anchored to / , suggesting that / …)
    3. Clause-comma followed by a subject+verb pattern
    4. Fall through: the whole claim is one proposition
    """
    _ADVERSATIVE = re.compile(
        r'\b(?:but|however|yet|although|while|whereas|nevertheless|nonetheless|even\s+so)\b',
        re.IGNORECASE,
    )

    parts: list[str] = []

    # Step 1: adversative split
    adv_match = _ADVERSATIVE.search(claim)
    if adv_match:
        before = claim[: adv_match.start()].strip().rstrip(',').strip()
        after = claim[adv_match.end() :].strip()
        if before and len(before) >= 10:
            parts.append(before)
        if after and len(after) >= 10:
            parts.append(after)
        if len(parts) == 2:
            return parts
        parts = []

    # Step 2: participial comma
    part_match = _PARTICIPIAL_SPLIT.search(claim)
    if part_match:
        before = claim[: part_match.start()].strip()
        after = claim[part_match.end() :].strip()
        if before and len(before) >= 10 and after and len(after) >= 10:
            return [before, after]

    # Step 3: clause-level comma (subject + finite verb)
    cl_match = _CLAUSE_COMMA.search(claim)
    if cl_match:
        before = claim[: cl_match.start()].strip()
        after = claim[cl_match.end() :].strip()
        if before and len(before) >= 10 and after and len(after) >= 10:
            return [before, after]

    # Step 4: whole claim as one proposition
    return [claim.strip()] if claim.strip() else []


def _find_supporting(claim: str, passages: list[str]) -> list[str]:
    """Passages with meaningful lexical overlap with the claim (≥25% of claim tokens)."""
    claim_tokens = _tokenize(claim)
    if not claim_tokens:
        return []
    result = []
    for passage in passages:
        p_tokens = _tokenize(passage)
        if not p_tokens:
            continue
        overlap = len(claim_tokens & p_tokens) / len(claim_tokens)
        if overlap >= 0.25:
            result.append(passage)
    return result


def _find_semantic_opposition(claim: str, passages: list[str]) -> list[str]:
    """Passages that contain a semantic antonym of a load-bearing term in the claim."""
    claim_tokens = _tokenize(claim)
    result = []
    for antonym_key, antonym_vals in _ANTONYM_PAIRS.items():
        if antonym_key.lower() in claim_tokens:
            for passage in passages:
                for aval in antonym_vals:
                    if re.search(r'\b' + re.escape(aval) + r'\b', passage, re.IGNORECASE):
                        if passage not in result:
                            result.append(passage)
                        break
    return result


def _find_challenging(claim: str, passages: list[str]) -> list[str]:
    """Passages that contain hedge language that undercuts the claim."""
    result = []
    for passage in passages:
        for hw in _HEDGE_WORDS:
            if re.search(r'\b' + re.escape(hw) + r'\b', passage, re.IGNORECASE):
                if passage not in result:
                    result.append(passage)
                break
    return result


def _truncate(text: str, n: int = 60) -> str:
    return text if len(text) <= n else text[:n] + "…"


def _result(claim: str, verdict: str, cited: list[str], rationale: str, policy: str) -> dict:
    return {
        "claim": claim,
        "verdict": verdict,
        "evidence_cited": cited,
        "rationale": rationale,
        "policy": policy,
    }
