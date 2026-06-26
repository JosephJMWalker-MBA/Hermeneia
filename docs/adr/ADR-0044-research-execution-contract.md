# ADR-0044: Research Execution Contract

**Status:** DRAFT  
**Version:** 0.1  
**Date:** 2026-06-24  
**Supersedes:** None  
**Constitutional Cost of Error:** Medium - incorrect placement could turn
research project management into ontology, or allow uncontrolled objective drift
to compromise reproducibility.

---

## Context

Hermeneia preserves knowledge about texts through canonical objects,
append-only lineage, and explicit authority. That ontology answers questions
such as:

- What Observations exist?
- What Interpretations exist?
- What evidence supports them?
- What was ratified?

Research execution raises a different class of questions:

- What experiment is currently being executed?
- What constitutes completion?
- When is it appropriate to change the protocol?

These are questions about the conduct of research over time, not about the
document being interpreted. They govern execution discipline rather than
epistemic classification.

The motivating failure mode is objective drift during an active experiment. A
research session may begin with an explicit objective:

```text
Complete controlled execution A.
Repeat controlled execution B.
Repeat controlled execution C.
Compare completed executions.
Generalize only after comparison.
```

During execution, new discoveries may appear. Some may be valuable enough to
preserve. But if those discoveries silently replace the active objective, the
experiment stops being controlled. The result is often unfinished executions,
incomparable outputs, and premature protocol revision.

The problem is not that new ideas emerge. The problem is implicit replacement
of the governing objective.

---

## Governing Distinction

The Execution Contract governs **time**, not **knowledge**.

Hermeneia's interpretive ontology governs the products of understanding:
SourceDocuments, SourceExtractions, Observations, Perspectives,
Interpretations, NarrativeBlueprints, ArchitectPlans, ExpressionProfiles,
RenderedNarratives, CriticReports, Findings where authorized, and related
projections.

An Execution Contract governs the active research interval:

- current objective;
- completion criteria;
- protocol constraints;
- permissible interruptions;
- deferred discoveries; and
- explicit investigator decisions to continue, supersede, or abandon.

It does not describe the interpreted document. It describes how the
investigation is being conducted.

Therefore the Execution Contract shall not be added to the canonical
interpretive pipeline, shall not create a new epistemic class, and shall not
be treated as evidence about the source text.

---

## Decision

Hermeneia should recognize a Research Execution Contract as a **session
orchestration principle**.

Initial classification:

```text
Research Session
    |
    +-- Active Objective
    +-- Completion Criteria
    +-- Protocol Constraints
    +-- Permissible Interruptions
    +-- Deferred Discoveries
    +-- Explicit Investigator Decisions
```

This classification is outside the interpretive ontology.

It does not authorize:

- a new canonical object;
- a new storage table;
- a new constitutional pipeline stage;
- mutation of existing ontology classifications;
- ratifiable research-management artifacts; or
- automatic protocol revision.

The governing principle is:

> An active research objective remains authoritative until completed,
> explicitly superseded, or abandoned by the investigator. New discoveries may
> be captured, but they shall not silently replace the governing objective.

The methodological order is:

```text
Execute
Repeat
Compare
Generalize
Revise Protocol
```

Protocol revision remains essential, but it belongs after comparative evidence
has accumulated unless an authorized interruption applies.

---

## Permissible Interruptions

The Execution Contract is disciplined, not rigid. It may be interrupted when:

- contradictory evidence invalidates the current protocol;
- missing prerequisites make completion impossible; or
- the investigator explicitly decides to supersede or abandon the objective.

These interruptions require explicit recognition. They do not occur merely
because a new idea is interesting, because a more general abstraction appears,
or because a protocol improvement might be possible.

New discoveries should be captured and linked to a deferred research thread
when they do not advance the active objective.

---

## Options Considered

### Option A - No Formal Contract

The current objective exists only in conversational context, notes, or human
memory.

**Primary strength:** Maximum flexibility.

**Primary failure mode:** Silent objective drift. The research process may
optimize for discovery instead of completion without any explicit decision,
making experiments unfinished or irreproducible.

**Constitutional fit:** Weak as a long-term practice. It does not alter the
ontology, but it fails to protect reproducibility.

---

### Option B - Session Orchestration Contract

The active research objective, constraints, completion criteria, and deferred
discoveries are tracked as session state or exported notes without becoming
canonical interpretive artifacts.

**Primary strength:** Preserves execution discipline without expanding the
ontology.

**Primary failure mode:** State may be ephemeral unless explicitly exported,
making historical reconstruction of the research process incomplete.

**Constitutional fit:** Strong initial fit. It respects the canonical pipeline
and treats execution discipline as governance of research time rather than
knowledge about a text.

---

### Option C - Canonical `ResearchObjective`

Research objectives become canonical, content-addressed objects with lineage,
status, and ratification semantics.

**Primary strength:** Complete historical traceability of research direction.

**Primary failure mode:** Turns project management into constitutional data and
risks expanding the ontology before the concept has been validated.

**Constitutional fit:** Not authorized for the initial capability. It would
require a separate amendment-level analysis.

---

### Option D - External Task Manager

Research objectives and deferred discoveries are tracked in external project
management tools.

**Primary strength:** Uses mature tooling for task state, assignment, due
dates, and progress tracking.

**Primary failure mode:** Loses tight coupling with the investigation and may
not preserve the relation between protocol decisions, evidence, and completed
executions.

**Constitutional fit:** Acceptable as adjunct tooling, but incomplete as a
Hermeneia methodological principle.

---

### Option E - Constitutional Amendment

The Execution Contract is immediately elevated into constitutional law.

**Primary strength:** Strongest guarantee against silent objective drift.

**Primary failure mode:** Prematurely hardens an unvalidated concept and may
force storage or ontology consequences before the boundary is proven.

**Constitutional fit:** Premature. The principle may later justify amendment if
repeated use proves it foundational.

---

## Recommended Approach

Adopt Option B initially.

The Execution Contract should be used as a research-session orchestration
discipline. It should protect the active objective from silent replacement,
while preserving every new discovery for explicit later consideration.

The system should distinguish:

```text
Discovery captured.
Objective unchanged.
Continue execution.
```

from:

```text
Investigator superseded objective.
Protocol revised.
New execution begins.
```

This mirrors Hermeneia's existing governance pattern:

- interpretive claims require explicit ratification before becoming
  established; and
- research direction changes require explicit investigator decision before
  replacing the active objective.

The first governs knowledge. The second governs investigation.

---

## Consequences

### Positive

- Prevents silent switching between exploration mode and execution mode.
- Preserves reproducibility by requiring controlled executions before
  generalization.
- Allows discoveries to be retained without derailing the active experiment.
- Keeps research-process governance outside the interpretive ontology.
- Avoids premature storage, identity, and epistemic-class commitments.

### Negative

- Session state may be lost unless exported.
- Deferred discoveries may need human discipline to revisit.
- The approach does not yet provide durable audit trails for research-objective
  changes.
- Tooling may eventually be needed if repeated sessions show that manual
  orchestration is insufficient.

### Neutral

- This ADR does not implement any code.
- This ADR does not modify the constitutional pipeline.
- This ADR does not authorize persistence of Execution Contract state.

---

## Implementation Guidance

Any future implementation must begin as a read-only or session-local
orchestration surface.

It may display:

- active objective;
- completion criteria;
- current completion status;
- blocking conditions;
- permissible interruptions;
- deferred discoveries; and
- explicit investigator decisions.

It must not:

- create a canonical object without separate authority;
- modify Observations, Interpretations, Perspectives, or generated artifacts;
- silently change the active objective;
- treat deferred discoveries as ratified knowledge; or
- revise a protocol without explicit investigator action.

---

## Non-Goals

This ADR does not define:

- a storage schema;
- an identity formula;
- a CLI command;
- a web API;
- a task manager;
- a new ontology object;
- a constitutional amendment; or
- an automatic method for deciding when an objective is complete.

---

## Open Questions

- What is the minimal export format for a completed Execution Contract?
- Should exported contracts remain ordinary notes, or eventually become
  auditable research-process records?
- How should deferred discoveries link to later research threads without
  becoming canonical interpretive claims?
- What evidence would justify promoting this principle from ADR to
  constitutional amendment?

