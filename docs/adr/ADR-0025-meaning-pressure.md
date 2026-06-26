# ADR-0025: Meaning Pressure — Formal Definition and Formula

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P2-001 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

The architecture defines Meaning Pressure qualitatively as "the density of connections radiating from a conceptual node over its historical documentation coverage." The Transformation Planner uses it to sequence Concept visits for a reader. Without a formula, the Planner cannot compute traversal order.

---

## Decision

### Formal Definition

**Meaning Pressure** (MP) for a Concept C in a Hermeneutic Field F is the weighted sum of epistemic connections to C, normalized by the maximum such score across all Concepts in F.

```
MP(C, F) = W(C, F) / max_{C' ∈ F} W(C', F)
```

where the raw connection weight W is:

```
W(C, F) = w_R × |R(C)| + w_I × |I(C)| + w_D × |D(C)|
```

| Symbol | Meaning | Default Weight |
|---|---|---|
| `R(C)` | Count of Relationships where C is source or target, across all Perspectives | `w_R = 1.0` |
| `I(C)` | Count of Interpretations whose `source_observation_ids` reference Observations linked to C | `w_I = 0.5` |
| `D(C)` | Count of Dialogue entries with `target_object_type: concept` and `target_object_id: C.id` | `w_D = 0.25` |

`MP(C, F) ∈ [0.0, 1.0]`. The Concept with the highest raw connection weight in the field receives MP = 1.0. All other Concepts are normalized relative to it.

If the field contains no Concepts, Meaning Pressure is undefined and the Planner must not be invoked.

---

## Rationale for the Formula

**Why include Relationships, Interpretations, and Dialogue?**  
A Concept may be central in the Field for different reasons: it may be structurally connected to many other Concepts (Relationships), richly interpreted from many angles (Interpretations), or actively contested in steward discourse (Dialogue). All three are evidence of epistemic density. Excluding any one would produce a formula blind to that dimension of centrality.

**Why the weights 1.0 / 0.5 / 0.25?**  
Relationships are the primary structural measure of Concept centrality — they define the Field topology. Interpretations add semantic richness but are applied to Observations, not directly to Concepts, so their link to a specific Concept is indirect (via Observation-to-Concept extraction, deferred to R4 implementation). Dialogue entries are the weakest signal — they may represent uncertainty or disagreement rather than settled centrality. The weights are calibration parameters, not constitutionally fixed values.

**These weights are the constitutional default.** A future ADR may amend them based on empirical validation. The formula structure is constitutional; the weight values are calibratable.

**Why normalize by field maximum rather than by a fixed scale?**  
A fixed scale (e.g., divide by total Concepts) would make MP sensitive to corpus size. A field with 1,000 Concepts would systematically produce lower scores than a field with 100 Concepts, making corpora incomparable. Max normalization produces relative scores within a field, which is what the Transformation Planner needs.

---

## The Observation-to-Concept Link

`I(C)` requires knowing which Observations reference Concept C. This is a data extraction problem resolved by the `field/` package's Concept extraction pipeline. At R4 implementation time, the pipeline must produce a `concept_observations` join table that maps `(concept_id, observation_id)` pairs.

The ADR for the Concept object schema (deferred, pending R4 ratification of the Concept schema) must include this join table.

---

## Validation Test

**Test:** Compute MP for the Concept `green_light` in a *Great Gatsby* corpus with 12 Perspectives applied.

**Expected result:** `green_light` has MP close to 1.0, reflecting:
- Many Relationships (symbolizes the American Dream, represents Daisy, appears in descriptions of Gatsby's desire, etc.)
- Many Interpretations (from Symbolist, Marxist, feminist, psychoanalytic Perspectives)
- Active Dialogue about its meaning

**Failure condition:** If a generic Concept like `Tom's house` has a higher MP than `green_light` in a fully annotated corpus, the formula is miscalibrated. Human expert judgment is the calibration benchmark.

---

## Implementation Notes

- MP is a computed value, not a stored field. It is computed on-demand by `field/graph.py` from the live state of the `relationships`, `interpretations`, and `dialogues` tables.
- MP must be recomputed whenever new Relationships, Interpretations, or Dialogue entries are added to the Field.
- For efficiency, the raw weight W(C) may be cached with an invalidation timestamp. When any of the three contributing tables is written to, affected Concept caches are invalidated.
- The formula must be stateless and deterministic: the same database state must always produce the same MP scores.

---

## Validation Rules

```python
mp_scores = compute_meaning_pressure(field)
assert all(0.0 <= mp <= 1.0 for mp in mp_scores.values())
assert max(mp_scores.values()) == 1.0  # at least one concept is maximally central
assert compute_meaning_pressure(field) == compute_meaning_pressure(field)  # deterministic
```

---

## Constitutional Alignment

- **Invariant 4** (Architectural Decoupling): Meaning Pressure computation has zero LLM imports. It is a graph-theoretic function over stored records.
- **Invariant 2** (Determinism): The formula is deterministic given fixed database state.
- **ADR-0023** (Contradiction preservation): MP counts Relationships across ALL Perspectives, including contradictory ones. A Concept contested across Perspectives has higher MP than one with a single settled reading.

---

## Migration Policy

If the formula weights are amended by a future ADR:
1. All cached MP values are invalidated.
2. MP is recomputed from the live database using the new weights.
3. No stored records are affected — MP is computed, not stored.
