# ADR-0037: Style and Semantics Can Be Partially Separated

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P4-003 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Existential

---

## Context

The two-writer model (ADR-0003) depends on the premise that style and semantics can be separated: the Architect encodes what to say; the Artist decides how to say it; the Critic detects violations.

Q-P4-003 challenges this premise directly. The research literature consistently warns that rhetorical choices — ordering, framing, emphasis, omission, metaphor — can alter meaning even when propositions are preserved. The question is constitutional: if separation is impossible, ADR-0003 must be reconsidered.

This ADR carries Existential constitutional cost because if the answer invalidates ADR-0003, the entire narrative layer would need to be redesigned. The answer must be made explicitly, not silently inherited from implementation decisions.

---

## Decision

**Style and semantics can be partially separated, and partial separation is constitutionally sufficient for Hermeneia's purposes, provided the Critic validates against a machine-readable Blueprint.**

Complete separation is impossible. The research literature is correct on this. Ordering, register, and metaphor all carry semantic residue. ADR-0003 is NOT invalidated — it is refined.

---

### Operational Definition of Style

**Style**, for Hermeneia's purposes, is defined as:

> Any transformation applied to a NarrativeBlueprint that does not alter the Blueprint's truth conditions, entailments, uncertainty markers, or evidential status attributions.

This is not a philosophical claim that style is semantically neutral. It is a constitutional decision to treat the Blueprint's truth conditions as the enforced boundary and to accept that stylistic choices outside this boundary are the Artist's responsibility.

### The Four Semantic Invariants

A stylistic transformation is permissible if and only if it preserves all four semantic invariants:

1. **Truth conditions**: The set of world states that would make the output true must not change.
2. **Entailments**: Every logical consequence derivable from the Blueprint's claims must remain derivable from the output.
3. **Evidential status**: If a claim in the Blueprint is marked `speculative`, the output must not present it as `established`. If marked `contested`, the output must not resolve the contest.
4. **Uncertainty attribution**: Uncertainty must remain attributed to its source (the Perspective, the Observation, the FieldContradiction). The Artist cannot suppress uncertainty to improve rhetorical flow.

### Permitted Stylistic Moves

The Artist may, without Critic intervention:
- Substitute synonyms within the same semantic field
- Reorder paragraphs, provided logical dependency sequence from `depends_on_claim_ids` is preserved
- Add illustrative analogies, provided they are flagged as analogies (not as evidence)
- Adjust register (formal vs. accessible) without changing propositional content
- Choose sentence structure, voice (active/passive), and rhythm
- Select citation style within the allowed `cited_observation_ids`
- Choose whether to acknowledge a FieldContradiction explicitly or implicitly — but if `field_contradiction_ids` is non-empty, acknowledgment is mandatory

### Forbidden Stylistic Moves

The Critic detects and blocks:
- Adding causal claims not in the Blueprint (`claims[*].proposition`)
- Omitting `evidential_status` markers (converting `speculative` claims to unhedged assertions)
- Changing the scope of a claim (from "in this Perspective" to "universally")
- Converting interpretive claims to observational claims ("Daisy is oppressed" stated as a fact rather than a Feminist Perspective reading)
- Inverting a claim's valence (even if the inversion would "read better")
- Introducing new Observations not in `cited_observation_ids`
- Asserting a proposition in `forbidden_inferences`

---

### Why Partial Separation Is Constitutionally Sufficient

Complete separation would require the Artist to be a semantic-preserving translator with zero expressive freedom. That produces prose that is technically correct and unreadable. Hermeneia's design goal includes producing prose that a reader can engage with — which requires genuine stylistic agency for the Artist.

The constitutionally important constraint is not that style is semantically inert — it is that the **Critic can detect semantic violations** by checking the output against the Blueprint. This is possible because:

1. The Blueprint's semantic commitments are machine-readable (ADR-0036 schema).
2. The Critic validates against structured fields, not against free-text prose.
3. The four semantic invariants are enforceable as algorithmic checks, not as qualitative judgments.

If the Critic detects a violation, it returns a structured fault report identifying which BlueprintClaim was violated and what the violation was. The Artist's output is blocked until the violation is corrected. The human steward reviews borderline cases (ADR-0010).

---

### What This Means for ADR-0003

**ADR-0003 stands.** The two-writer model is not invalidated. It is confirmed with the following refinements:

1. "Separation of style and semantics" is formally defined as preservation of the four semantic invariants, not as metaphysical independence.
2. The Critic's role is formalized: it validates the four invariants, not stylistic quality.
3. The Artist has genuine agency within the invariant boundary.
4. Ambiguous cases are resolved by the human steward, not by algorithmic arbitration.

---

## Validation Test

Q-P4-003 proposed: *"Apply three different stylistic transformations (register, order, analogy) to the same Blueprint and test whether a human reader reaches the same epistemic conclusions from each. If yes, the separation is sufficient."*

Under this ADR: the test is reframed. The question is not whether readers reach the same conclusions — different readers will not — but whether the four semantic invariants are preserved across all three renderings. A literary scholar reviewing the three renderings should find that:
- Each rendering expresses the same claims at the same evidential status
- No rendering introduces propositions not in the Blueprint
- No rendering suppresses uncertainty that the Blueprint marks as uncertain

---

## Constitutional Alignment

- **ADR-0003** (Two-writer model): Confirmed and refined. Not superseded.
- **ADR-0036** (NarrativeBlueprint): The Blueprint schema enables the four-invariant validation.
- **ADR-0010** (Human-only decisions): Ambiguous violations are resolved by human stewards.
- **Project Philosophy**: "The goal is not answers, but questions well-posed." A rendering that converts speculative claims to established claims violates this philosophy and will be caught by invariant 3.
