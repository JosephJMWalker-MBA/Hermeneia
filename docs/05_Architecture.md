# System Architecture

**Status:** ACTIVE IMPLEMENTATION AUTHORITY  
**Constitutional authority:** [`00_Constitution.md`](00_Constitution.md), [`01_Authority_Index.md`](01_Authority_Index.md), [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)  
**Implements:** Articles I, II, III, IV, VI, VIII, IX, X, XII, XIII  
**Affected invariants:** CI-001 through CI-016  
**Implementation status:** NOT YET VALIDATED

---

## Role of This Document

This document is subordinate to the Constitution.

It does not create first principles, ontology, pipeline stages, or storage
authority. It explains how the ratified constitutional architecture is to be
implemented.

If this document conflicts with the Constitution, the Constitution governs.

---

## P0-A Constitutional Conformance Gates

Hermeneia's next implementation milestone is P0-A: Constitutional Conformance.

P0-A is divided into two gates:

```text
P0-A1
Constitutional Conformance of Specifications

↓

P0-A2
Constitutional Conformance of Implementation

↓

P1
Semantic Communication
```

P0-A1 aligns subordinate specifications with constitutional authority.

P0-A2 aligns code, schema, compiler output, web behavior, and tests with those
specifications.

P1 work shall not proceed until P0-A2 can prove immutable ancestry,
append-only storage, side-effect-free reads, and auditable lineage.

---

## Canonical Pipeline

The constitutional pipeline is:

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
    ↓
Interpretation
    ↓
Perspective
    ↓
NarrativeBlueprint
    ↓
ArchitectPlan
    ↓
ExpressionProfile
    ↓
ArtistProvider
    ↓
RenderedNarrative
    ↓
CriticReport
    ↓
Stewardship
```

The only replaceable execution component in this pipeline is the ArtistProvider.

The ArtistProvider receives an ArchitectPlan and ExpressionProfile, then
produces a RenderedNarrative. It shall not create the ArchitectPlan, evaluate
itself, or alter any ancestor.

A Provider may represent a cloud service, an on-device runtime, a local model, a specialized execution environment, or any future expression mechanism capable of realizing an ArchitectPlan. Provider identity is ecological rather than constitutional.

---

## Evidence Ladder

Hermeneia is a forensic knowledge system.

| Object | Epistemic status | Mutability |
|---|---|---|
| SourceDocument | Artifact | Immutable |
| SourceExtraction | Evidence | Immutable |
| Observation | Evidence | Immutable |
| ObservationDerived | Derived metadata | Disposable and regenerable |
| Perspective | Frame | Append-only |
| Interpretation | Claim | Append-only |
| NarrativeBlueprint | Synthesis | Append-only |
| ArchitectPlan | Semantic contract | Append-only |
| ExpressionProfile | Communication constraint | Append-only |
| RenderedNarrative | Expression | Append-only |
| CriticReport | Evaluation | Append-only |

`ObservationDerived` is the only regenerable object in the ladder. It is cache,
not history.

---

## Forensic Evidence Layer

The evidence layer is deterministic, local, immutable, and non-inferential.

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
```

`SourceDocument` preserves the original artifact identity.

`SourceExtraction` records exact parser output and extraction custody.

`Observation` records one semantic unit selected from a SourceExtraction without
altering its characters.

Normalization, tokenization, field extraction, search indexes, and embeddings
are derived metadata. They shall not replace evidence or determine occurrence
identity.

---

## Understanding Layer

The understanding layer is append-only.

`Perspective` defines an interpretive frame.

`Interpretation` records a claim about an Observation under a Perspective.

Multiple Interpretations may coexist over the same Observation. A later
Interpretation shall not mutate, invalidate, or replace an earlier
Interpretation.

---

## Synthesis and Contract Layer

`NarrativeBlueprint` answers:

> What should be communicated?

`ArchitectPlan` answers:

> What obligations must every valid communication satisfy?

The ArchitectPlan is the canonical semantic contract between synthesis and
expression.

An ArtistProvider receives the ArchitectPlan. It shall not reconstruct
obligations directly from the NarrativeBlueprint.

---

## Expression and Evaluation Layer

`ExpressionProfile` constrains how the ArchitectPlan may be expressed.

`RenderedNarrative` is an ArtistProvider output. Because frontier model
invocations may be nondeterministic or unreproducible years later, every
RenderedNarrative shall preserve the execution context required for audit.

`CriticReport` evaluates a RenderedNarrative against its referenced
ArchitectPlan and ExpressionProfile. The evaluated model shall not create the
contract or evaluate itself.

---

## Read-Only Architecture

Read paths shall be genuinely read-only.

HTTP `GET`, lineage inspection, audit views, search, matrix rendering, and
trace endpoints shall not:

- initialize schemas;
- migrate tables;
- seed profiles;
- insert objects;
- update timestamps; or
- perform any persistent mutation.

Initialization and migration are explicit write operations, never side effects
of inspection.

---

## Portable Artifact

The active portable artifact is a `.herm` directory or archive containing:

```text
bundle.herm/
    context.json
    hermeneia.db
```

Legacy JSONL bundle layouts are non-constitutional v0 artifacts. They may be
read for historical import, but they are not authoritative P0 storage.

---

## Governing Summary

Hermeneia preserves artifacts, records evidence, accumulates claims,
synthesizes understanding, constrains communication through explicit semantic
contracts, and maintains an append-only, independently auditable lineage from
every rendered expression back to immutable source material.
