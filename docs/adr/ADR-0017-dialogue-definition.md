# ADR-0017: Dialogue — Formal Definition

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P0-005 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

`Dialogue` appears in the epistemology chain and the canonical ontology spec. It is the primary mechanism by which human stewardship enters the Hermeneutic Field (Article VI of the Constitution). Dialogue has not been formally defined — its relationship to other canonical objects, its authorship rules, its internal structure, and its persistence model are all open.

This ADR defines Dialogue and closes Q-P0-005. Q-P1-004 (temporal vs. relational) and Q-P1-006 (Question vs. Dialogue) are resolved in ADR-0018 and ADR-0019.

---

## Decision

### Formal Definition

A **Dialogue** is a human-authored epistemic contribution to the Hermeneutic Field that is addressed to a specific named object in the field (an Observation, Interpretation, Concept, Relationship, ContinuityNode, Perspective, or another Dialogue entry) and that carries the steward's identity, timestamp, and stance.

A Dialogue answers: *"What does a human steward say in direct response to something already in the Field?"*

### Dialogue Is Always Human-Originated

Dialogue is constitutionally human-only. AI systems may not author Dialogue entries. This is a direct consequence of ADR-0010 (Human-Only Decisions) and the Constitution's treatment of human stewardship as the irreducible layer of the epistemic system.

An AI system may propose a response or question for a steward's consideration, but until a human steward accepts and publishes it as their own contribution (editing as needed), it is not a Dialogue entry. It is an AI proposal in the staging area.

A steward-accepted AI-generated text, published as the steward's Dialogue contribution, carries human provenance (the steward) with an optional note that the text was AI-assisted. The AI assistance is a disclosure, not a disqualification.

### Dialogue Types

Dialogue entries carry a `dialogue_type` field that classifies the epistemic act being performed:

| Type | Meaning |
|---|---|
| `observation` | A steward notes something about the target object without asking a question or making an interpretive claim. ("I notice that this sentence uses the same phrasing as the passage on page 42.") |
| `question` | A steward poses a question directed at the target object or the Field community. |
| `dispute` | A steward formally contests an Interpretation or another Dialogue entry. Carries a `disputes_id` reference. |
| `affirmation` | A steward explicitly endorses an Interpretation or another Dialogue entry. |
| `correction` | A steward flags a factual error in an Observation's metadata (not the text — the text is immutable) or an error in a ContinuityNode's canonical label. |
| `annotation` | A steward adds contextual information that does not fit the other types. |

---

## Required Schema Fields

| Field | Type | Requirement |
|---|---|---|
| `id` | String (deterministic hash) | Required |
| `dialogue_type` | Enum | Required. See type table above. |
| `target_object_id` | String | Required. The ID of the object this Dialogue is addressed to. |
| `target_object_type` | Enum | Required. The type of the target object (`observation`, `interpretation`, `perspective`, `concept`, `relationship`, `continuity_node`, `dialogue`). |
| `content` | String | Required. The steward's contribution, verbatim as they authored it. |
| `authored_by` | String (steward ID) | Required. |
| `authored_date` | ISO 8601 datetime | Required. |
| `disputes_id` | String or null | Required if `dialogue_type: dispute`. The ID of the Interpretation or Dialogue being disputed. |
| `ai_assisted` | Boolean | Required. True if the steward used AI assistance in drafting this entry. |
| `thread_root_id` | String or null | The ID of the first Dialogue entry in this thread, if this is a reply to a reply. Null if this is a root entry. |
| `responds_to_id` | String or null | The ID of the immediate Dialogue entry this is replying to, if this is a reply. Null if this is a root entry. |

---

## Threading Model

Dialogue supports threading: a steward may respond to another steward's Dialogue entry, creating a thread.

```
Dialogue A (root, target: Interpretation X)
    └── Dialogue B (responds_to: A, thread_root: A)
            └── Dialogue C (responds_to: B, thread_root: A)
```

The `thread_root_id` field allows retrieval of all entries in a thread with a single query. The `responds_to_id` field allows reconstruction of the thread's tree structure.

A root Dialogue entry (addressed to a non-Dialogue object) has both `thread_root_id` and `responds_to_id` set to null.

---

## Persistence Rules

1. Dialogue entries are append-only. Once authored and published, a Dialogue entry's `content`, `authored_by`, and `authored_date` may not be modified.
2. If a steward wishes to retract a Dialogue entry, they author a new Dialogue of `type: correction` that explicitly references the entry being retracted and states the retraction. The original entry is not deleted.
3. Dialogue entries may not be deleted (append-only constraint applies).
4. A retracted entry carries `retracted: true` as a metadata flag, written by the retraction process. The `content` field is not modified.

---

## Exclusion Criteria

The following do not constitute valid Dialogue entries:

1. AI-generated text that has not been accepted and published by a human steward.
2. System-generated questions from coverage analysis or Perspective Debt surfacing (these are `FieldQuestion` objects — see ADR-0019).
3. Compiler annotations or processing notes.
4. Modifications to Observation text (Observation text is immutable; corrections to metadata are Dialogue entries of type `correction`).

---

## Provenance Implications

Every Dialogue entry carries complete human provenance: `authored_by` (steward ID) and `authored_date`. These fields are immutable after publication.

If the Dialogue entry was AI-assisted, the optional `ai_provenance_id` field links to an AI Provenance record (per ADR-0009) documenting the model, prompt, and generation parameters used.

The AI Provenance record in this case documents *assistance*, not *authorship*. The steward remains the author. The AI system provided a draft that the steward accepted (in whole or in part).

---

## Validation Rules

```python
assert dialogue.target_object_id is not None
assert dialogue.target_object_type in VALID_TARGET_TYPES
assert target_object_exists(dialogue.target_object_id, dialogue.target_object_type)
assert dialogue.authored_by is not None
assert is_human_steward(dialogue.authored_by)  # per ADR-0010
assert dialogue.authored_date is not None
assert dialogue.content is not None and len(dialogue.content) > 0

if dialogue.dialogue_type == "dispute":
    assert dialogue.disputes_id is not None
    assert object_exists(dialogue.disputes_id)

if dialogue.responds_to_id is not None:
    assert dialogue_exists(dialogue.responds_to_id)
    assert dialogue.thread_root_id is not None
```

---

## Constitutional Alignment

- **Article VI** (Human Stewardship): Dialogue is the constitutional implementation of human epistemic contribution. The `authored_by` field ensures every Dialogue entry is traceable to a named human steward.
- **Article II** (Provenance mandatory): Full human provenance on every Dialogue entry.
- **Article III** (Append-only): Dialogue entries are never deleted. Retraction is a new entry, not a deletion.
- **ADR-0010** (Human-only decisions): The requirement that Dialogue is human-authored is a direct consequence of ADR-0010.

---

## Consequences

**Positive:**
- The boundary between human contribution (Dialogue) and system-generated questions (FieldQuestion, per ADR-0019) is enforced by object type.
- Threading allows scholarly conversations to be preserved and navigated.
- The `dispute` type provides a mechanism for formal scholarly disagreement without deleting the disputed claim.

**Negative:**
- Dialogue entries cannot be corrected after publication. A steward who makes a factual error must author a new Dialogue entry explicitly correcting it. This may create long retraction chains for active contributors.
- The threading model is simple (tree structure). It does not support cross-thread references or many-to-one reply structures without modification.

---

## Alternatives Considered

**Alternative: Allow AI to author Dialogue entries with a special AI flag**  
Rejected. The constitutional distinction between human contribution and AI contribution is not a matter of flagging — it is a matter of authorship authority. An AI-authored Dialogue entry would be an AI epistemic contribution, not a human one. The constitutional protection of human stewardship would be diluted. AI can assist; it cannot author.
