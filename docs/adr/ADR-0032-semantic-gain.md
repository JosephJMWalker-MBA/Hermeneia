# ADR-0032: Semantic Gain — Formal Definition and Formula

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P3-002 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

Semantic Gain is the primary optimization target of the Transformation Planner. `docs/05_Architecture.md` references a formula for it via a broken image link. This ADR ratifies the formula.

Semantic Gain must be consistent with ADR-0031's definition of Understanding (navigability, not comprehension) and must be computable from ReaderModel state (ADR-0030) and Field metrics (ADRs 0025–0029).

---

## Decision

### Formal Definition

**Semantic Gain** for a reading session S is the value added to a reader's Understanding (ADR-0031) by the Concepts, Perspectives, and Dialogue contributions encountered in S.

```
SG(S, R_before, F) = w_C × ConceptualBreadth(S, R_before, F)
                   + w_P × PerspectivalDiversity(S, R_before, F)
                   + w_D × DialogueContribution(S)
```

### Component Definitions

**ConceptualBreadth:**  
The proportion of newly encountered Concepts in session S, weighted by their Meaning Pressure.

```
ConceptualBreadth(S, R, F) = Σ_{C ∈ new_concepts(S, R)} MP(C, F) / |concepts in F|
```

A session that introduces high-MP Concepts the reader has never seen earns high ConceptualBreadth. Revisiting known Concepts earns nothing.

**PerspectivalDiversity:**  
The proportion of newly encountered Perspectives in session S, plus a bonus for encountering high-Perspective-Debt Concepts through a new frame.

```
PerspectivalDiversity(S, R, F) = Σ_{P ∈ new_perspectives(S, R)} 1.0 / |active_perspectives in F|
                                + Σ_{(C, P) ∈ new_pairs(S, R)} PD_norm_before(C, F) / normalization_factor
```

where `new_pairs` = (Concept, Perspective) pairs where the reader has not previously seen Concept C under Perspective P.

**DialogueContribution:**  
Whether the reader authored Dialogue entries during session S.

```
DialogueContribution(S) = |{dialogue ∈ S.new_dialogue}| / |new_concepts(S, R)|
```

A reader who asks questions or submits observations about the Concepts they encounter earns a Dialogue contribution bonus. Capped at 1.0.

### Weights

| Component | Default Weight | Rationale |
|---|---|---|
| `w_C` ConceptualBreadth | 0.4 | Exploring new Concepts is the baseline epistemic act. |
| `w_P` PerspectivalDiversity | 0.5 | Encountering multiple frames is the system's primary epistemic value. Higher weight than breadth alone. |
| `w_D` DialogueContribution | 0.1 | Active contribution is valued but not required for a productive reading session. |

These weights are **calibration parameters**, not constitutional commitments. A future ADR may amend them based on empirical validation against human expert judgments of reading quality.

### Scale

`SG ∈ [0.0, 1.0]` per session when normalized. The normalization ensures that a session which introduces every new Concept in the field at full MP through every active Perspective with maximum Dialogue contribution scores 1.0. In practice, no real session approaches 1.0.

If `|concepts in F| = 0` or `|active_perspectives in F| = 0`, SG is undefined and the Planner must report an empty field.

---

## The Transformation Planner's Objective

The Planner generates candidate TransformationPlans and ranks them by projected SG. The plan it proposes to the steward is the one with the highest projected SG for the reader's current state.

Projected SG is computed by simulating the session: "if the reader encounters Concepts {C₁, C₂, C₃} through Perspective P in this sequence, what SG would that produce?" The simulation uses the Reader's current `R_before` state.

---

## What Semantic Gain Is NOT

- It is not a measure of whether the reader has "learned" anything.
- It is not a measure of whether the reader can recall or reproduce the text.
- It is not maximized by time-in-session.
- It is not improved by revisiting familiar Concepts through familiar Perspectives.

A Planner that maximizes SG routes readers toward the unfamiliar, the multiply-framed, and the actively questioned.

---

## Validation Test

Q-P3-002 proposed: *"Two Transformation Plans applied to the same ReaderModel — one maximizing SG, one minimizing it. The maximizing plan should be recognized by a human expert as a richer reading experience."*

**Minimizing plan:** Revisit Concept `Nick Carraway` through the one Perspective the reader already knows (Formalist). SG ≈ 0.0 (no new Concepts, no new Perspectives, no Dialogue).

**Maximizing plan:** Introduce `green_light` (MP ≈ 0.95, never seen) through Feminist and Marxist Perspectives (both new to this reader) and prompt a FieldQuestion for the reader to consider. SG ≈ 0.6+.

A literary scholar reviewing both plans should recognize the second as the richer reading experience.

---

## Constitutional Alignment

- **ADR-0031** (Understanding as navigability): SG rewards breadth of Concept exposure, Perspective diversity, and active questioning — all dimensions of navigability.
- **Invariant 4** (Architectural Decoupling): SG computation has zero LLM involvement. It is arithmetic over ReaderModel state and Field metrics.
- **ADR-0025** (Meaning Pressure): MP is used as the Concept weight in ConceptualBreadth.
- **ADR-0026** (Perspective Debt): PD_norm appears in the PerspectivalDiversity component.
