# ADR-0033: ReaderModel Evolution Is Append-Only

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P3-003 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

The ReaderModel tracks a reader's epistemic exposure (ADR-0030). As the reader engages with more sessions, the ReaderModel must update. The question is how: can prior states be replaced, or must the history be preserved?

---

## Decision

**ReaderModel evolution is append-only. Prior states are never replaced or deleted.**

Each reading session produces a new ReaderModel snapshot with an incremented `snapshot_version`. The lists in each snapshot (`known_concept_ids`, `encountered_perspective_ids`, etc.) are cumulative from the reader's first session. The ordered `traversal_history` grows with each session.

A reader cannot "un-know" a Concept. A reader cannot "un-encounter" a Perspective. The model of epistemic exposure is monotonically growing.

---

## Evolution Trigger

A new ReaderModel snapshot is created at the end of each reading session. A reading session ends when:
1. The reader signals completion (clicks "Done" or equivalent).
2. A session timeout occurs (configurable).
3. The TransformationPlan for the session is exhausted.

The snapshot captures the cumulative state at that moment. The Planner reads the latest snapshot when generating the next session's TransformationPlan.

---

## Can a ReaderModel Regress?

No. There is no mechanism for a ReaderModel to regress. If a reader "forgets" something in the cognitive sense, the ReaderModel does not reflect this. The ReaderModel records exposure, not retention. It is constitutionally immune to regression because it tracks what happened (immutable history), not what the reader currently knows (unmeasurable cognitive state).

---

## Provenance of ReaderModel Snapshots

Each snapshot carries:
- `created_at`: timestamp of session end
- `created_by_session_id`: the reading session that produced this snapshot
- `snapshot_version`: integer, incrementing from 0

The sequence of snapshots for a reader constitutes their complete reading provenance on a given corpus. This sequence is append-only and stored in the `reader_model_snapshots` table.

The current active model for a reader is `WHERE reader_id = X AND corpus_id = Y ORDER BY snapshot_version DESC LIMIT 1`.

---

## Validation Rules

```python
snapshots = get_snapshots(reader_id, corpus_id)
for i in range(1, len(snapshots)):
    prev, curr = snapshots[i-1], snapshots[i]
    assert curr.snapshot_version == prev.snapshot_version + 1
    assert set(prev.known_concept_ids).issubset(set(curr.known_concept_ids))
    assert set(prev.encountered_perspective_ids).issubset(set(curr.encountered_perspective_ids))
    assert curr.created_at >= prev.created_at
```

---

## Constitutional Alignment

- **Axiom 1** (Immutability): ReaderModel snapshots are immutable after creation. Each session produces a new snapshot, not an update to the old one.
- **ADR-0030** (ReaderModel): This ADR specifies the evolution model for the schema defined in ADR-0030.
