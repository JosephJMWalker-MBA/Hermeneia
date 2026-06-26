# ADR-0026: Perspective Debt — Formal Definition and Formula

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** ADR-0005  
**Closes:** Q-P2-002 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

ADR-0005 (Proposed) stated: "Perspective Debt measures missing viewpoints relative to expected diversity. The engine should expose missing voices instead of pretending completeness." This was a philosophical commitment without a formula.

This ADR supersedes ADR-0005 with a ratified definition, formula, and schema.

---

## Decision

### Formal Definition

**Perspective Debt** for a Concept C in Field F is the number of Perspectives declared in F that have not produced any Interpretation of C.

```
PD(C, F) = |P(F)| - |P_applied(C, F)|
```

where:
- `P(F)` = set of all active Perspectives declared in Field F
- `P_applied(C, F)` = set of Perspectives that have at least one active Interpretation referencing an Observation linked to C

`PD(C, F) ∈ [0, |P(F)|]`.  
`PD = 0` means every declared Perspective has been applied to C.  
`PD = |P(F)|` means no Perspective has been applied to C at all.

---

## Why Corpus-Relative, Not Normative

Q-P2-002 asked: "Who defines which Perspectives are relevant?" and raised the possibility of "expected perspectives" drawn from a normative list of required scholarly frames.

This ADR rejects normative expected Perspectives. The reason is constitutional:

A normative list of "required" Perspectives would itself constitute a Perspective — a meta-level judgment about which epistemic stances are valid. Installing such a list into the system would privilege a particular scholarly tradition's view of completeness. This violates the constitutional principle that Perspectives accumulate without any single frame being authoritative.

The corpus-relative definition avoids this: Perspective Debt is measured relative to what the stewards of this corpus have chosen to declare. If a steward has declared a Marxist Perspective and a Feminist Perspective and a Formalist Perspective, every Concept in the corpus carries Perspective Debt for each of those three frames that hasn't been applied to it. The system does not judge whether those three are the "right" frames — it only tracks which declared frames have and haven't been applied.

---

## Normalised Perspective Debt

For ranking and reporting, a normalized form is useful:

```
PD_norm(C, F) = PD(C, F) / |P(F)|    if |P(F)| > 0, else 0.0
```

`PD_norm ∈ [0.0, 1.0]`. A Concept with `PD_norm = 1.0` has been interpreted through no declared Perspectives. A Concept with `PD_norm = 0.0` has been interpreted through every declared Perspective.

---

## Field-Level Perspective Debt

The Perspective Debt for the entire Field is the mean over all Concepts:

```
PD_field(F) = Σ_{C ∈ F} PD_norm(C, F) / |C(F)|
```

This provides a single-number summary of how thoroughly the corpus's declared Perspectives have been applied across its Concept graph.

---

## Can Perspective Debt Be Negative?

Q-P2-002 asked whether Perspective Debt can be negative (too many Perspectives applied to a Concept, creating noise).

**Answer: No.** Perspective Debt cannot be negative. More Perspectives applied is always an increase in epistemic richness, not noise. The accumulation axiom (Axiom 3) treats Perspective accumulation as unconditionally desirable. A Concept with many applied Perspectives has more epistemic material, not less. There is no constitutionally valid concept of "over-interpreted."

If a concept has been interpreted through too many poorly-grounded Perspectives (quality concern), that is an issue for human stewardship review, not a signal to be encoded in the Perspective Debt metric.

---

## Implementation Notes

- Perspective Debt is a computed value, not stored.
- Requires the `concept_observations` join table (from ADR-0025 context).
- Recomputed whenever new Perspectives are declared or new Interpretations are accepted into canonical tables.
- The `herm stats` command must report PD_field and flag the top-N Concepts with highest PD_norm.

---

## Validation Rules

```python
pd_scores = compute_perspective_debt(field)
assert all(pd >= 0 for pd in pd_scores.values())
assert all(pd <= len(get_active_perspectives(field)) for pd in pd_scores.values())
# A concept with no Interpretations at all has PD = total active Perspectives
uninterpreted_concept_pd = pd_scores[concept_with_no_interpretations]
assert uninterpreted_concept_pd == len(get_active_perspectives(field))
```

---

## What ADR-0005 Committed and What This ADR Changes

ADR-0005 committed to the philosophical principle (expose missing voices). This ADR retains that commitment and adds:
- A formal definition
- A computable formula
- A normalization for ranking
- A field-level aggregate
- An explicit rejection of normative expected Perspectives

ADR-0005 is superseded. Its philosophical commitment is preserved in this ADR's preamble and the corpus-relative design.

---

## Constitutional Alignment

- **Axiom 3** (Perspectives accumulate): The formula measures accumulation gaps without privileging any single Perspective's authority.
- **ADR-0015** (Perspective definition): PD is scoped to declared Perspectives (`active: true`). Superseded Perspectives (`active: false`) do not contribute to PD_field.
- **ADR-0010** (Human-only decisions): The decision about which Perspectives to declare in a corpus remains human-only. PD measures gaps against human-declared Perspectives, not against a system-imposed list.
