# ADR-0021: Interpretation References Exactly One Perspective; Synthetic Perspectives Handle Multi-Frame Readings

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P1-003 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

ADR-0015 established that an Interpretation references exactly one Perspective. Q-P1-003 asks whether this should be relaxed to allow an Interpretation to reference multiple Perspectives — for example, a reading that is simultaneously feminist and post-colonial.

---

## Decision

**An Interpretation references exactly one Perspective.**

Multi-Perspective synthesis is handled through the declaration of a **synthetic Perspective** — a named Perspective that explicitly states its derivation from two or more constituent Perspectives.

---

## Rationale

### The Provenance Argument

If an Interpretation referenced multiple Perspectives, the provenance chain for the Interpretation would be ambiguous: which Perspective produced which aspect of the Interpretation? An Interpretation that draws on feminist theory and post-colonial theory simultaneously cannot be cleanly attributed to either without knowing which claim came from which frame.

A synthetic Perspective solves this: "Feminist post-colonial reading" is a named Perspective with its own `canonical_label`. Its `description` field states what it commits to. Its provenance is a single anchor. Interpretations under it are provenance-clean.

### The Accumulation Argument

Article III requires Perspectives to accumulate, not replace. If Interpretations could reference two Perspectives simultaneously, and a new reading wanted to challenge the contribution of one Perspective to the Interpretation but not the other, there would be no clean mechanism. Under the single-Perspective model, each Perspective's Interpretations accumulate independently. Cross-Perspective synthesis is represented as a new named Perspective.

### The Constituent Perspectives Field

A synthetic Perspective carries an optional `constituent_perspective_ids` field: a list of the Perspective IDs it was derived from. This field:

- Is informational, not structural. It is not used to retrieve Interpretations under the constituent Perspectives.
- Allows tracing the intellectual lineage of a synthetic Perspective.
- Is append-only: additional constituent Perspectives may be added if the synthetic frame broadens, but existing ones may not be removed.

---

## Schema Addition to Perspective (from ADR-0015)

Add one optional field to the Perspective schema:

| Field | Type | Requirement |
|---|---|---|
| `constituent_perspective_ids` | List[String] or null | Optional. IDs of Perspectives this one was derived from. Null for primary (non-synthetic) Perspectives. |
| `is_synthetic` | Boolean | Required. True if this Perspective was declared as a synthesis of constituent Perspectives. |

---

## Validation Test

Q-P1-003 proposed: *"Produce an Interpretation that synthesizes two Perspectives without flattening either. The provenance of each Perspective must remain traceable independently."*

Under this ADR:

1. Declare Perspective A: `Feminist reading` (primary, `is_synthetic: false`)
2. Declare Perspective B: `Post-colonial reading` (primary, `is_synthetic: false`)
3. Declare Perspective C: `Feminist post-colonial reading` (`is_synthetic: true`, `constituent_perspective_ids: [A.id, B.id]`)
4. Author Interpretation D under Perspective C, referencing Observation O.

- Perspective A's independent Interpretations remain unaffected.
- Perspective B's independent Interpretations remain unaffected.
- Perspective C's Interpretation synthesizes both without belonging to either.
- The provenance of each constituent frame remains traceable through `constituent_perspective_ids`.
- Neither A nor B is "flattened" — they remain distinct, named, append-only Perspectives.

---

## Validation Rules

```python
assert interpretation.perspective_id is not None
# Exactly one perspective per Interpretation — enforced by schema, not asserted at runtime

# Synthetic Perspective must declare its constituents
if perspective.is_synthetic:
    assert perspective.constituent_perspective_ids is not None
    assert len(perspective.constituent_perspective_ids) >= 2
    assert all(perspective_exists(pid) for pid in perspective.constituent_perspective_ids)
```

---

## Constitutional Alignment

- **Article III** (Perspectives accumulate): Constituent Perspectives are not altered or merged. They remain independent, permanent objects.
- **Article II** (Provenance mandatory): Every Interpretation's provenance chain is unambiguous — one Perspective ID per Interpretation.

---

## Consequences

**Positive:**
- Provenance chains remain clean. Every Interpretation belongs to exactly one Perspective.
- Cross-Perspective synthesis is fully representable through synthetic Perspectives.
- Constituent Perspective lineage is traceable through `constituent_perspective_ids`.

**Negative:**
- A steward who wants to produce a single synthesis Interpretation must first declare a synthetic Perspective, which adds friction. For ad hoc cross-frame readings, this is a meaningful bottleneck.
- The synthetic Perspective declaration requires a steward name for the synthetic frame. Naming scholarly traditions is a judgment call. The system cannot enforce that the name is accurate.
