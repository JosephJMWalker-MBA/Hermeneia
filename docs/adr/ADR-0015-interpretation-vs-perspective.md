# ADR-0015: Interpretation and Perspective — Formal Distinction

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P0-003 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Existential

---

## Context

The ontology spec names both `Interpretation` and `Perspective` as canonical objects. They appear together in the epistemology chain:

```
Observation → Concept → Relationship → Perspective → Interpretation → Dialogue → ...
```

Their relationship is constitutionally important: Article III declares that Perspectives accumulate and cannot be overwritten. If Perspective and Interpretation are conflated, this constraint becomes unenforceable. If they are separated incorrectly, contradictory Interpretations accumulate without any way to indicate which is authoritative within a given reading tradition.

This ADR is prerequisite for the `Perspective` schema, the `Interpretation` schema, and the entire `field` package.

---

## Decision

### Formal Definitions

A **Perspective** is a declared epistemic stance or methodological frame from which Observations may be interpreted. It is permanent, named, and append-only.

A Perspective answers: *"From what vantage point is this reading being made?"*

An **Interpretation** is a propositional statement derived from one or more Observations, made from within exactly one declared Perspective.

An Interpretation answers: *"What does this passage mean, read from this declared vantage point?"*

---

## The Structural Relationship

```
Perspective          ← the frame (permanent, append-only, named)
    │
    ├── Interpretation A   ← claim from this frame about Observation 1
    ├── Interpretation B   ← claim from this frame about Observation 1 (supersedes A)
    └── Interpretation C   ← claim from this frame about Observation 2
```

**One Perspective → many Interpretations.**  
**One Interpretation → exactly one Perspective.**

A Perspective is not a derived object. It is a declared one. It is created by a human steward (or accepted from an AI proposal via the staging protocol of ADR-0009/ADR-0010). It is named with a human-readable label ("Feminist reading," "Marxist reading," "Formalist reading," "Post-colonial reading").

An Interpretation is a derived object. It is produced by applying a Perspective to one or more Observations. It carries the Perspective that produced it in its provenance chain.

---

## The Validation Tests

**Test 1 (proposed in Q-P0-003):**

"From a feminist perspective, Daisy represents the imprisoning of female agency."

- Perspective: `Feminist reading` (a declared Perspective object with its own ID)
- Interpretation: "Daisy represents the imprisoning of female agency" (an Interpretation with `perspective_id: [feminist-reading-id]` and `source_observations: [passage IDs describing Daisy]`)
- These are two separate objects.

"From a post-colonial perspective, Daisy represents an idealization of whiteness."

- Perspective: `Post-colonial reading` (a different declared Perspective object)
- Interpretation: "Daisy represents an idealization of whiteness" (an Interpretation with `perspective_id: [post-colonial-reading-id]`)

Both Interpretations may coexist in the database, referencing the same source Observations, with different Perspectives. Their distinctness is computable from `perspective_id` alone — no text comparison is needed.

---

## Perspective Properties

| Property | Value |
|---|---|
| Permanence | Append-only. A Perspective, once created and accepted, cannot be deleted. |
| Scope | Global — not scoped to a single source document or ContextCapsule. One Perspective can be applied across an entire corpus or across multiple corpora. |
| Creation | Declared by human steward. AI may propose; steward must accept (ADR-0010). |
| Versioning | A Perspective whose factual premises are discredited is not deleted. It is marked `superseded_by` pointing to a refined Perspective. Both the original and the refined version remain in the database. |
| Uniqueness | No two Perspectives may share the same `canonical_label`. |

---

## Interpretation Properties

| Property | Value |
|---|---|
| Provenance | Every Interpretation references exactly one `perspective_id` and one or more `source_observation_ids`. |
| Derivation | An Interpretation must be derived from at least one Observation. An Interpretation with no `source_observation_ids` is constitutionally invalid. |
| Versioning | Within the same Perspective, an Interpretation may be superseded by a more refined Interpretation. The old Interpretation carries `superseded_by: [new-interpretation-id]`. It is not deleted. |
| Cross-Perspective supersession | An Interpretation from Perspective A does NOT supersede an Interpretation from Perspective B. Cross-Perspective readings coexist, not compete. Supersession only occurs within the same Perspective. |
| Authority | AI-generated Interpretations require steward acceptance (ADR-0009, ADR-0010) before entering the canonical `interpretations` table. |

---

## Required Schema Fields

### Perspective

| Field | Type | Requirement |
|---|---|---|
| `id` | String (deterministic hash) | Required |
| `canonical_label` | String | Required. Unique. Human-readable. |
| `tradition` | String or null | Optional. The scholarly tradition this Perspective belongs to (e.g. "Feminism," "Marxism"). |
| `description` | String | Required. A prose statement of what this Perspective commits to epistemically. |
| `declared_by` | String (steward ID) | Required. Human steward who declared this Perspective. |
| `declared_date` | ISO 8601 datetime | Required. |
| `superseded_by` | String or null | Null unless this Perspective is superseded. |
| `active` | Boolean | True unless superseded. Superseded Perspectives have `active: false`. |

### Interpretation

| Field | Type | Requirement |
|---|---|---|
| `id` | String (deterministic hash) | Required |
| `perspective_id` | String | Required. Foreign key to Perspectives. |
| `source_observation_ids` | List[String] | Required. Minimum one. Foreign keys to Observations. |
| `content` | String | Required. The propositional statement being made. |
| `derivation_type` | Enum | Required. One of: `direct_reading`, `synthesis`, `contrast`, `inference`. |
| `superseded_by` | String or null | Null unless superseded within the same Perspective. |
| `active` | Boolean | True unless superseded. |
| `created_by` | String (steward ID or AI provenance ID) | Required. |
| `created_date` | ISO 8601 datetime | Required. |

---

## The "Wrong Perspective" Question

Q-P0-003 asked: *"What happens when a Perspective is found to be factually wrong?"*

A Perspective is a declared methodological frame. Frames are not factually wrong — they are differently positioned. A feminist reading is not wrong in the same sense that a factual claim can be wrong.

However, a Perspective may have its foundational premise discredited. For example: a reading grounded in "Fitzgerald wrote this character as a coded autobiographical figure" may be discredited if biographical research proves otherwise.

In this case:

1. The original Perspective is **not deleted**.
2. A refined Perspective is created with a corrected premise.
3. The original carries `superseded_by: [new-perspective-id]` and `active: false`.
4. All Interpretations generated under the original Perspective remain in the database with their original `perspective_id`.
5. New Interpretations under the same tradition are generated under the refined Perspective.
6. A query for active Interpretations in this tradition returns only those under active Perspectives.
7. A query for all Interpretations (including historical) returns the full set.

This satisfies Article III (Perspectives accumulate and cannot be deleted) while allowing correction through addition.

---

## Validation Rules

```python
# Every Interpretation must have a valid Perspective
assert interpretation.perspective_id is not None
assert perspective_exists(interpretation.perspective_id)

# Every Interpretation must have at least one source Observation
assert len(interpretation.source_observation_ids) >= 1
assert all(observation_exists(oid) for oid in interpretation.source_observation_ids)

# An Interpretation may only be superseded by another Interpretation under the same Perspective
if interpretation.superseded_by is not None:
    successor = get_interpretation(interpretation.superseded_by)
    assert successor.perspective_id == interpretation.perspective_id

# Perspective canonical labels must be unique
assert count(perspectives WHERE canonical_label = X) <= 1

# A deleted Perspective is constitutionally prohibited
assert count(DELETE operations on perspectives table) == 0
```

---

## Serialization Rules

- `Perspective.id` is a deterministic hash of `(canonical_label,)`.
- `Interpretation.id` is a deterministic hash of `(perspective_id, source_observation_ids_sorted, content_hash)`.
- Both tables are append-only. No UPDATE statement may modify `perspective_id`, `source_observation_ids`, or `content` on an existing Interpretation.
- The `superseded_by` and `active` fields may be written once (from null to a value) but not reversed (a Superseded Interpretation cannot be reinstated by changing `superseded_by` back to null).

---

## Migration Policy

1. Perspectives created under this ADR are permanent.
2. If this definition is amended to change the Perspective or Interpretation schema, existing records retain their original schema, identified by `extractor_version` or a new `schema_version` field.
3. The `superseded_by` pointer allows graceful evolution without deletion.
4. A future ADR may add fields to the Perspective or Interpretation schema; existing records are not required to carry the new fields.

---

## Constitutional Alignment

- **Article I** (Reality precedes interpretation): Perspectives and Interpretations are explicitly the interpretation layer. They are separated from Observations by a named boundary (the `source_observation_ids` field).
- **Article III** (Perspectives accumulate): The `active: false` + `superseded_by` pattern satisfies accumulation without deletion. Superseded Perspectives remain as permanent epistemic records.
- **Article II** (Provenance mandatory): Every Interpretation carries the full provenance chain: `source_observation_ids` → Observations → Provenance → source document.

---

## Consequences

**Positive:**
- Perspective Debt is now measurable: the gap between which Perspectives have been applied to a given Observation and which have not.
- Cross-Perspective coexistence is structurally enforced. An Interpretation under Perspective A and a contradictory Interpretation under Perspective B are both valid database records.
- Supersession within a Perspective allows scholarly revision without deleting the historical record.

**Negative:**
- Every Interpretation must carry a `perspective_id`. An Interpretation without an explicitly declared Perspective is invalid. This means the system cannot accept "naive" readings that haven't been assigned to a named epistemic frame.
- The requirement that `source_observation_ids` be non-empty means all Interpretations must be grounded in textual evidence. An Interpretation that is purely speculative (no textual anchor) cannot be canonical. This is constitutionally correct but may frustrate use cases where stewards want to record a reading that is not yet grounded in a specific passage.

---

## Alternatives Considered

**Alternative: Interpretation IS Perspective (conflated)**  
Rejected. If Interpretation and Perspective are the same object, every new reading must "replace" or "extend" an existing one, violating Article III. There would be no stable anchor for measuring Perspective Debt. The Hermeneutic Field would have no way to distinguish "a different reading of the same passage" from "an updated reading of the same passage from the same vantage point."

**Alternative: Interpretation references multiple Perspectives**  
Deferred to Q-P1-003 (ADR-0021). An Interpretation referencing exactly one Perspective is the default. Synthetic multi-Perspective Interpretations are handled by declaring a synthetic Perspective object (see ADR-0021).
