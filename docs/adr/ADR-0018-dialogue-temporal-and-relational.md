# ADR-0018: Dialogue Is Both Temporal and Relational

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P1-004 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

ADR-0017 defined Dialogue as a human-authored epistemic contribution addressed to a specific named object. This ADR resolves whether Dialogue is modeled as a temporal sequence, a relational graph, or both.

---

## Decision

**Dialogue is both temporal and relational. Neither model alone is sufficient.**

### The Temporal Dimension

Every Dialogue entry carries `authored_date`. The sequence of Dialogue entries in a thread, ordered by `authored_date`, constitutes the temporal record of a scholarly conversation.

Temporal ordering is necessary because:
- It allows reconstruction of the conversation as it unfolded.
- It establishes which Interpretation a steward was responding to at the time of writing (before subsequent revisions).
- It allows the system to surface recent Dialogue activity on any object in the Field.

### The Relational Dimension

Every Dialogue entry carries `target_object_id` (the object it is addressed to) and `responds_to_id` (the Dialogue entry it replies to, if it is a reply). Together these form a relational graph:

- **Root entries** connect Dialogue to non-Dialogue objects (Observations, Interpretations, Concepts, etc.)
- **Reply entries** connect Dialogue to prior Dialogue entries

This relational structure is necessary because:
- It allows the system to retrieve all Dialogue addressed to a specific Observation (the flat temporal log cannot do this efficiently without the `target_object_id` index).
- It captures the semantic relationship between a Dialogue entry and what it is responding to — not just the time ordering.
- It preserves the thread structure as a directed tree, not just a flat list.

### Why Both Are Required

A Dialogue system with only temporal ordering can retrieve "what was said and when" but cannot answer "what was this said *about* and what was it responding *to*."

A Dialogue system with only relational structure can answer "what is connected to what" but cannot reconstruct the conversation as a human would read it, ordered by time.

Hermeneutic scholarship requires both. A scholar needs to know: (a) when a challenge to an Interpretation was raised; and (b) which Interpretation it challenged, and what argument it made.

---

## Implementation

This decision is already encoded in the Dialogue schema defined in ADR-0017:

- **Temporal:** `authored_date` (ISO 8601) on every entry. Ordered traversal by timestamp reconstructs the temporal narrative.
- **Relational:** `target_object_id` + `target_object_type` (what the Dialogue is about) and `responds_to_id` + `thread_root_id` (thread structure within Dialogue-to-Dialogue replies).

No new fields are required. This ADR is a ratification of the design already embedded in ADR-0017.

---

## Constitutional Alignment

- **Axiom 8** (Dialogue expands the field): The relational model is what makes Dialogue an expansion of the field, not merely a chronological log. An entry that challenges an Interpretation is semantically connected to that Interpretation, not just temporally adjacent.

---

## Consequences

Addressed in ADR-0017. This ADR adds no new implementation requirements beyond confirming that both `authored_date` and the relational fields are mandatory.
