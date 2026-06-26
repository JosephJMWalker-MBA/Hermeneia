# ADR-0028: Interpretive Density — Formal Definition

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P2-004 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Low

---

## Context

The architecture implies that some Concepts are more richly interpreted than others. Meaning Pressure (ADR-0025) measures structural centrality in the Relationship graph. A separate measure — Interpretive Density — is needed to capture how richly a Concept has been *read*, independent of how well-connected it is in the graph.

A Concept might have high Meaning Pressure (many Relationships) but low Interpretive Density (few Interpretations of the Observations referencing it). The Transformation Planner can use this gap to prioritize under-interpreted high-pressure Concepts.

---

## Decision

### Formal Definition

**Interpretive Density** for a Concept C in Field F is the ratio of active Interpretations referencing C to the number of Observations linked to C.

```
ID(C, F) = |I_active(C)| / |O(C)|    if |O(C)| > 0, else 0.0
```

where:
- `I_active(C)` = active Interpretations with at least one `source_observation_id` ∈ `O(C)`
- `O(C)` = Observations linked to Concept C via the `concept_observations` join table

`ID ≥ 0`. There is no upper bound: a Concept may have more Interpretations than source Observations if multiple Interpretations are derived from the same Observation under different Perspectives.

---

## How It Differs from Meaning Pressure

| Metric | Measures | Graph or Text? | Bounded? |
|---|---|---|---|
| Meaning Pressure | Connectivity in Relationship graph, weighted by Interpretations and Dialogue | Graph | [0.0, 1.0] normalized |
| Interpretive Density | Richness of Interpretation relative to textual presence | Text | [0.0, ∞) |

A Concept with:
- **High MP, Low ID**: Many Relationships but few Interpretations relative to its Observations. It is structurally important but interpretively thin. The Planner should prioritize it.
- **Low MP, High ID**: Few Relationships but densely interpreted. A specialist Concept that has been studied intensely without being connected to the broader field.
- **High MP, High ID**: The core of the Field. Well-connected and richly read.
- **Low MP, Low ID**: A peripheral, under-studied Concept.

---

## Normalization for Ranking

For ranking purposes, ID is normalized within the Field by the maximum ID score:

```
ID_norm(C, F) = ID(C, F) / max_{C' ∈ F} ID(C', F)    if max > 0, else 0.0
```

---

## The Under-Interpreted Concept Signal

The primary use of Interpretive Density in the Transformation Planner is identifying **under-interpreted high-pressure Concepts**:

```
gap(C) = MP(C, F) - ID_norm(C, F)
```

A high `gap` value means the Concept is structurally central (high Meaning Pressure) but has received little interpretive attention relative to its textual presence. These are the most epistemically productive Concepts for a reader to encounter next — they are important, and their importance has not yet been fully read.

---

## Implementation Notes

- ID is computed, not stored.
- Requires the `concept_observations` join table.
- Recomputed when new Interpretations are accepted or when `concept_observations` is updated.
- The gap metric `MP - ID_norm` must be exposed by `field/graph.py` for the Planner's curiosity engine.

---

## Validation Test

**Test:** In a *Gatsby* corpus where `green_light` has 8 source Observations and 40 Interpretations across 5 Perspectives, and `Nick's car` has 3 source Observations and 1 Interpretation:

- `ID(green_light) = 40/8 = 5.0`
- `ID(Nick's car) = 1/3 ≈ 0.33`
- `ID_norm(green_light) = 1.0`; `ID_norm(Nick's car) = 0.066`

If `MP(Nick's car) = 0.3` and `MP(green_light) = 0.95`:
- `gap(green_light) = 0.95 - 1.0 = -0.05` (well-studied relative to its pressure)
- `gap(Nick's car) = 0.3 - 0.066 = 0.234` (structurally present but under-interpreted)

The Planner should consider routing toward `Nick's car` as an underdeveloped concept with meaningful structural position.

---

## Constitutional Alignment

- **Invariant 4** (Architectural Decoupling): Interpretive Density computation has zero LLM involvement. It is arithmetic over stored record counts.
