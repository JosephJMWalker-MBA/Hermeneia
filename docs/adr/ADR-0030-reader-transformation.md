# ADR-0030: Reader Transformation — Formal Definition and ReaderModel Schema

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P0-006 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

The Transformation Planner's goal is to move a reader from their current epistemic state to a richer one. Without a formal representation of "reader state," the Planner has no input and no way to measure progress.

The question is: what counts as a reader's state of understanding? The architecture says the system must represent reader understanding computably — but it must not adopt a behaviorist model (clicks and dwell time) or a cognitivist model (retention and transfer). Both would violate the project philosophy.

---

## Decision

### The Constitutional Constraint on Reader Modeling

The project philosophy states: "The goal is not answers, but questions well-posed."

This is a constitutional rejection of comprehension as the optimization target. Hermeneia does not measure whether a reader has "learned" the text. It does not test recall. It does not score understanding against a rubric.

What it models instead is **epistemic exposure**: what parts of the Hermeneutic Field has this reader engaged with? What Concepts have they encountered? What Perspectives have they seen applied? What questions have they asked?

The **ReaderModel** is a formal record of epistemic exposure, not a model of cognitive state.

---

### Formal Definition

A **ReaderModel** is a representation of a reader's engagement with a Hermeneutic Field, tracking the Concepts, Perspectives, and Observations they have encountered and the Dialogue they have contributed.

A ReaderModel answers: *"Where has this reader been in the Field, and what remains beyond their current horizon?"*

A ReaderModel does NOT answer: *"What does this reader know, believe, or remember?"*

---

### ReaderModel Schema

| Field | Type | Requirement |
|---|---|---|
| `id` | String (hash) | Required |
| `reader_id` | String | Required. Steward ID for the reader. |
| `corpus_id` | String | Required. Which `.herm` bundle this model is for. |
| `snapshot_version` | Integer | Required. Increments with each session. Starts at 0 (empty model). |
| `known_concept_ids` | List[String] | Required. Concept IDs the reader has encountered in any session. |
| `encountered_perspective_ids` | List[String] | Required. Perspective IDs the reader has been introduced to. |
| `encountered_observation_ids` | List[String] | Required. Observation IDs the reader has seen cited or rendered. |
| `traversal_history` | List[TraversalEvent] | Required. Ordered sequence of (concept_id, perspective_id, session_id, timestamp) tuples. |
| `dialogue_ids` | List[String] | Required. IDs of Dialogue entries this reader has authored. |
| `field_questions_answered` | List[String] | Required. FieldQuestion IDs answered by this reader's Dialogue entries. |
| `created_at` | ISO 8601 datetime | Required. When this snapshot was created. |
| `created_by_session_id` | String | Required. The reading session that produced this snapshot. |

---

### Reader Transformation

**Reader Transformation** is the delta between two consecutive ReaderModel snapshots for the same reader on the same corpus:

```
Δ(R_before, R_after) = {
    new_concepts:       R_after.known_concept_ids - R_before.known_concept_ids,
    new_perspectives:   R_after.encountered_perspective_ids - R_before.encountered_perspective_ids,
    new_observations:   R_after.encountered_observation_ids - R_before.encountered_observation_ids,
    new_dialogue:       R_after.dialogue_ids - R_before.dialogue_ids,
}
```

Reader Transformation is the input to the Semantic Gain formula (Q-P3-002, ADR-0032).

---

### Append-Only Evolution

The ReaderModel is append-only, consistent with Axiom 1. Each reading session creates a new `snapshot_version`. The lists (`known_concept_ids`, etc.) are cumulative: they only grow. A reader never "un-knows" a Concept.

If a reader encounters the same Concept twice, the second encounter is recorded in `traversal_history` but does not change `known_concept_ids` (it is already there).

Provenance: each snapshot carries `created_by_session_id`, identifying the reading session that produced it. Reading sessions are themselves provenance-tracked: session start time, duration, Concepts presented, Planner that generated the plan.

---

### Who Defines the Target State?

Q-P0-006 asked: who defines the target state — the human, the system, or the corpus?

**Answer: The human steward who commissions a reading, guided by the system.**

The Transformation Planner generates candidate TransformationPlans targeting different possible next states. The steward (or reader, if they have stewardship authority) selects which plan to execute. The system does not unilaterally choose the reader's next epistemic destination.

This is a constitutional requirement: the system may propose paths, but it may not impose them (ADR-0010: human-only decisions).

---

## Validation Rules

```python
# ReaderModel lists are monotonically non-decreasing
assert set(r_before.known_concept_ids).issubset(set(r_after.known_concept_ids))
assert set(r_before.encountered_perspective_ids).issubset(set(r_after.encountered_perspective_ids))

# Snapshot versions are sequential
assert r_after.snapshot_version == r_before.snapshot_version + 1

# Every encountered Concept ID must exist in the Field
assert all(concept_exists(cid) for cid in reader_model.known_concept_ids)
```

---

## Constitutional Alignment

- **Project Philosophy** ("Questions well-posed"): The ReaderModel tracks exposure and questioning (Dialogue), not comprehension.
- **Article VI** (Human stewardship): The reader's agency is preserved: the system proposes plans; the human selects them.
- **Axiom 1** (Immutability / append-only): ReaderModel states are snapshots. Prior states are never overwritten.
