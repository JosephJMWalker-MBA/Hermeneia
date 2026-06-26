# ADR-0027: Coverage — Formal Definition and Dimensions

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P2-003 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

The architecture references a `HermeneuticCoverageIndex` and a Coverage Analyzer. Coverage is the metric that tells a steward how much of the corpus has been worked — how much has been observed, interpreted, and perspectivally diversified. Without a definition, it is unimplementable.

---

## Decision

Coverage is not a single number. It is a **three-dimensional index** that measures completeness across three distinct epistemic layers.

---

## The Three Coverage Dimensions

### Dimension 1: Observation Coverage (O-Cov)

Proportion of compiled Observations that have at least one active Interpretation.

```
O-Cov(F) = |{O ∈ observations : ∃I ∈ interpretations where O.id ∈ I.source_observation_ids}| / |observations|
```

`O-Cov ∈ [0.0, 1.0]`.  
`O-Cov = 0.0`: no Observation has been interpreted.  
`O-Cov = 1.0`: every Observation has at least one Interpretation.

**What it measures:** How much of the raw text has received any scholarly attention. Low Observation Coverage means the corpus is largely unread at the interpretive layer.

---

### Dimension 2: Concept Coverage (C-Cov)

Proportion of Concepts in the field that have at least one active Relationship.

```
C-Cov(F) = |{C ∈ concepts : ∃R ∈ relationships where C.id ∈ {R.source_concept_id, R.target_concept_id}}| / |concepts|
```

`C-Cov ∈ [0.0, 1.0]`.  
`C-Cov = 0.0`: no Concept has been connected to any other.  
`C-Cov = 1.0`: every Concept has at least one Relationship.

**What it measures:** How much of the Concept graph has been built out. An isolated Concept (no Relationships) is an island in the Field — it cannot participate in Transformation Planning.

---

### Dimension 3: Perspective Coverage (P-Cov)

Proportion of declared active Perspectives that have been applied to at least one Concept.

```
P-Cov(F) = |{P ∈ active_perspectives : ∃I ∈ interpretations where I.perspective_id = P.id}| / |active_perspectives|
```

`P-Cov ∈ [0.0, 1.0]`.  
`P-Cov = 0.0`: no declared Perspective has produced any Interpretation.  
`P-Cov = 1.0`: every declared Perspective has been applied to at least one Concept.

**What it measures:** How many of the declared interpretive frames are active vs. dormant. A declared Perspective that has produced no Interpretations is epistemically inert — it exists in the system but has not touched the corpus.

---

## The Coverage Index

The `HermeneuticCoverageIndex` is the harmonic mean of the three dimensions:

```
HCI(F) = 3 / (1/O-Cov(F) + 1/C-Cov(F) + 1/P-Cov(F))
```

The harmonic mean is chosen over the arithmetic mean because it penalizes imbalance. A field that is 100% complete on two dimensions but 0% on the third should not return a high overall score. The harmonic mean returns 0.0 in that case, forcing attention to the deficient dimension.

`HCI ∈ [0.0, 1.0]`.

---

## Handling Edge Cases

If `|observations| = 0`, `O-Cov = 0.0`.  
If `|concepts| = 0`, `C-Cov = 0.0`.  
If `|active_perspectives| = 0`, `P-Cov = 0.0`.  
If any dimension is 0.0, `HCI = 0.0` (harmonic mean with a zero term is zero).

---

## Implementation Notes

- Coverage dimensions are computed values, not stored fields.
- Recomputed on-demand or on a cache-invalidation schedule.
- `herm stats` must report all three dimensions and the HCI.
- Coverage is per-Field, not per-Concept. Concept-level coverage is captured by Perspective Debt (ADR-0026).

---

## Validation Rules

```python
o_cov, c_cov, p_cov = compute_coverage(field)
assert 0.0 <= o_cov <= 1.0
assert 0.0 <= c_cov <= 1.0
assert 0.0 <= p_cov <= 1.0
hci = compute_hci(field)
assert 0.0 <= hci <= 1.0
# New Interpretations increase O-Cov (never decrease it)
hci_before = compute_hci(field)
add_interpretation(field, ...)
assert compute_coverage(field)[0] >= o_cov  # O-Cov monotonically non-decreasing
```

---

## Constitutional Alignment

- **Axiom 3** (Perspectives accumulate): P-Cov reflects the constitutional commitment to Perspective diversity. A low P-Cov signals that most declared frames are not yet active.
- **ADR-0026** (Perspective Debt): Coverage and Perspective Debt are complementary metrics. Coverage measures field-level completeness; Perspective Debt measures per-Concept completeness.
