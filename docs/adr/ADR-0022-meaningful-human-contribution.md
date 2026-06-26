# ADR-0022: Meaningful Human Contribution

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P6-002 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

Hermeneia's human stewardship model requires that human contribution be preserved, attributed, and distinguished from AI contribution. But what counts as a meaningful human contribution? This question matters for audit trail design, stewardship metrics, and the integrity of the human provenance layer.

---

## Decision

### Formal Definition

A **meaningful human contribution** is any deliberate act by a named human steward that modifies the canonical state of the Hermeneutic Field and is traceable through a human provenance record.

The word "deliberate" is critical: a rubber-stamp that requires no thought is not meaningful by design, though the system cannot distinguish it from a thoughtful acceptance. The design must create conditions for deliberateness; it cannot enforce it.

### Three Types of Meaningful Contribution

**Type 1: Ratification acts**  
Any act from the seven constitutionally reserved categories (ADR-0010):
- Ratifying an ADR
- Accepting/rejecting an amendment
- Promoting an Interpretation to canonical status
- Resolving an epistemic conflict
- Authorizing a deletion or suppression
- Assigning an ethical/moral judgment
- Certifying/publishing a knowledge artifact

These are the highest form of human contribution. They carry the full weight of the constitutional framework.

**Type 2: Authorship acts**  
Creating or accepting objects that bear the steward's identity:
- Authoring a Dialogue entry (including questions, disputes, annotations)
- Declaring a Perspective
- Creating or ratifying a ContinuityNode
- Registering a source document
- Authoring or modifying a ContextCapsule

**Type 3: Review and acceptance acts**  
Reviewing AI-generated objects and making acceptance or rejection decisions:
- Accepting an AI-proposed Interpretation (moves from staging to canonical, per ADR-0009)
- Rejecting an AI-proposed object (marks it rejected in staging)
- Dismissing a FieldQuestion (marks it dismissed with rationale)
- Accepting a ContinuityNode proposed by entity recognition

---

## The Rubber-Stamp Problem

Q-P6-002 asked: *"Is a human who reviews and approves AI output without modifying it a meaningful contributor?"*

The answer: **Yes, constitutionally.** Steward acceptance of an AI-generated object is a meaningful human contribution (Type 3 above). The steward takes responsibility for the object entering the canonical corpus.

However, the system should make acceptance non-trivial by design:
- Stewards must read and consider the object before accepting.
- The system may require a minimum character count for `acceptance_rationale` in AI Provenance records (a future configuration option).
- The audit trail records how many objects each steward accepted and how quickly.

The system cannot enforce thoughtfulness, but it can create friction against rubber-stamping and can expose suspicious patterns (e.g., a steward accepting 500 AI-generated Interpretations in 10 minutes) to review.

---

## What Is NOT a Meaningful Contribution

The following do not constitute meaningful human contributions:

1. Automated pipeline execution (running the compiler, running the planner). These are system acts, not human acts.
2. Login or authentication events. These are not epistemic acts.
3. Reading without writing. The system records reading activity for the ReaderModel, but reading alone is not a contribution to the Field.
4. An AI-generated Dialogue entry not yet accepted by a human steward. It is in staging, not contributed.

---

## Serialization

Every meaningful contribution is recorded through the existing provenance fields on the relevant object type:
- `authored_by` / `declared_by` / `ratified_by` / `accepting_steward` — these are the canonical fields.
- All are non-null for any canonical object that was the result of a meaningful human contribution.
- All are immutable after writing.

There is no separate `contribution` table. Contributions are the sum of human-provenance records across all canonical object types. A steward's contribution profile is computable by querying:
- All Dialogue entries where `authored_by = steward_id`
- All Perspectives where `declared_by = steward_id`
- All ContinuityNodes where `ratified_by = steward_id`
- All AI Provenance records where `accepting_steward = steward_id`
- All source_documents where `registered_by = steward_id`

---

## Validation Rules

```python
# Every canonical object with human authorship must have a non-null steward ID
# (enforced at write time by the storage layer)
assert obj.authored_by is not None or obj.accepting_steward is not None or obj.ratified_by is not None

# The steward ID must correspond to a registered human steward
assert is_human_steward(get_author(obj))
```

---

## Constitutional Alignment

- **Article VI** (Human Stewardship): This ADR operationalizes what it means to steward the Field — not just to exist in the system, but to perform traceable epistemic acts.
- **ADR-0010** (Human-only decisions): All Type 1 contributions are constitutionally reserved.
- **ADR-0009** (AI provenance): Type 3 contributions are the human side of every AI-assisted object's dual provenance.

---

## Consequences

**Positive:**
- A steward's contribution is fully auditable from the provenance records without a separate contribution tracking system.
- The three-type taxonomy gives the system a vocabulary for surfacing contribution gaps: "this corpus has no Type 2 contributions from any steward for three months — it may be understewarded."

**Negative:**
- The rubber-stamp problem cannot be fully solved technically. Governance culture around stewardship quality is beyond the system's enforcement capacity.
