# Hermeneia Architecture Patterns

**Status:** NON-NORMATIVE IMPLEMENTATION GUIDE
**Authority:** None
**Date:** 2026-06-20
**Scope:** Recurring implementation patterns already present in Hermeneia

---

## Role of This Document

This document is a contributor guide, not constitutional law, ontology,
specification, or an Architecture Decision Record.

It does not authorize new domain objects, pipeline stages, persistence models,
APIs, fields, or epistemic classes.

All implementations remain subordinate to:

1. [`00_Constitution.md`](00_Constitution.md);
2. [`01_Authority_Index.md`](01_Authority_Index.md);
3. ratified amendments;
4. [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md);
5. active ADRs; and
6. active implementation specifications.

If a pattern conflicts with an authority above it, the pattern does not apply.

The purpose of this guide is to help contributors recognize recurring solution
shapes and ask:

> Which existing Hermeneia pattern does this implementation belong to?

Patterns describe implementation. They do not create architecture.

---

## Regeneration Principle

### Statement

If an artifact can be losslessly regenerated from immutable canonical
constituents, it should be implemented as a disposable projection or derived
artifact rather than a canonical object.

### Intent

Preserve only irreducible epistemic objects as canonical artifacts.

Regenerable arrangements are useful. They focus attention, support search,
summarize state, and help humans inspect the corpus. They become dangerous when
they are granted independent ontology, authority, provenance, or lifecycle.

### Properties

A regenerable artifact:

- possesses no independent identity;
- possesses no constitutional authority;
- possesses no provenance of its own;
- possesses no supersession of its own;
- possesses no constitutional profile of its own;
- may be reconstructed on demand from canonical objects; and
- may be discarded without changing constitutional history.

### Known Instances

- `ObservationDerived`;
- Workspace Projection;
- Trust Card;
- Audit Vector;
- provider ecology projection;
- Expression Matrix cells; and
- dashboard summaries.

### Anti-Patterns

- persisting dashboards as ontology;
- persisting aggregate scores as authority;
- persisting regenerated summaries as canonical history;
- granting authority to projections;
- allowing a projection to drift from its source objects; and
- making a projection the parent of canonical lineage.

### Constitutional Basis

The Regeneration Principle follows from Article I, Article VI, Article XII,
Article XIII, CI-006, CI-012, CI-015, and CI-016.

It is also a discipline against ontology drift: if the artifact is not the
smallest object that must be independently preserved, witnessed, or governed,
then it should not be canonical.

---

## Pattern 1 — Pure Projection

```text
Canonical Object
    ↓
Read-only Projection
    ↓
Expression
```

### Intent

Present canonical truth for a particular human purpose without creating,
changing, or duplicating epistemic objects.

A pure projection may select, arrange, summarize, or translate existing
canonical references. It may not infer missing ontology, fabricate lineage, or
acquire independent authority.

### Properties

- read-only;
- fully regenerable from canonical objects;
- no persistent identity of its own;
- no provenance, supersession, or ratification of its own;
- canonical IDs remain unchanged;
- interface profiles change expression only; and
- deleting the projection changes no knowledge.

### Current Examples

#### Workspace Projection

```text
focus = { epistemic_class, canonical_id }
profile = child | elder | scholar
    ↓
canonical related IDs
    +
available inspection surfaces
```

`GET /api/workspace/<epistemic_class>/<object_id>` returns a disposable view
over canonical references. The workspace has no workspace ID and is never
persisted.

#### Trust Card

```text
Persisted lineage, execution, contract, and Critic facts
    ↓
Trust Summary projection
    ↓
Compact human-facing card
```

The interface renders authoritative findings returned by
`GET /api/trust/rendered_narrative/<id>`. It does not calculate trust from
provider identity or invent a confidence score.

#### Lineage Explorer

```text
Canonical ancestry graph
    ↓
Expert or Universal vocabulary
    ↓
Clickable lineage presentation
```

The backend returns ontology classes, IDs, and edges. The interface changes
labels and icons only. Both vocabularies traverse the same graph.

### Use This Pattern When

- the requested feature is a dashboard, workspace, card, summary, matrix, or
  alternate view;
- all required information already exists canonically;
- the result can be reconstructed from canonical IDs; and
- different audiences need different expressions of the same truth.

### Do Not

- create a table for a view merely because the view feels important;
- give a projection an epistemic class;
- persist navigation or layout as knowledge;
- infer an absent relationship in the frontend; or
- return presentation labels from an ontology API.

---

## Pattern 2 — Disposable Derived

```text
Canonical Object
    ↓
Deterministic Derivation
    ↓
Disposable Metadata or Index
```

### Intent

Support computation, search, segmentation, or display without allowing a
derived convenience artifact to replace its immutable ancestor.

### Properties

- references the canonical ancestor from which it was derived;
- records the derivation version where required;
- may be deleted and rebuilt;
- does not determine canonical identity;
- does not overwrite evidence; and
- never becomes the authoritative source for canonical content.

### Current Examples

- `ObservationDerived.normalized_text`;
- sentence tokens;
- whitespace maps;
- deterministic field-term indexes;
- search indexes; and
- future caches permitted by CI-016.

The defining relationship is:

```text
Observation.raw_text
    ↓
ObservationDerived
```

Normalization belongs below the immutable Observation as disposable metadata.
It never replaces `SourceExtraction.raw_text` or `Observation.raw_text`.

### Use This Pattern When

- the output is reproducible from an immutable ancestor;
- the output exists for computational convenience;
- deleting it should not alter epistemic history; and
- rebuilding it is safer than treating it as permanent knowledge.

### Do Not

- use derived text to compute Observation identity;
- store normalized text in evidence fields;
- promote a cache to a canonical object;
- cascade deletion from derived data into canonical ancestors; or
- conceal the canonical ancestor behind a derived representation.

---

## Pattern 3 — Contract-Constrained Expression

```text
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
```

### Intent

Permit broad expressive variation while preserving a stable, inspectable
semantic contract.

### Responsibilities

| Component | Responsibility |
|---|---|
| NarrativeBlueprint | Defines what should be communicated |
| ArchitectPlan | Compiles obligations every valid expression must satisfy |
| ExpressionProfile | Constrains how those obligations are communicated |
| ArtistProvider | Produces expression without creating the contract |
| RenderedNarrative | Records the human-facing result and execution audit data |
| CriticReport | Independently evaluates the result against the contract |

### Properties

- the ArchitectPlan is invariant across Artist providers;
- the Artist does not create or modify its contract;
- the evaluated model does not evaluate itself;
- provider identity does not determine semantic standing;
- execution metadata supports independent audit; and
- expressions may vary while contractual meaning remains fixed.

### Current Examples

- OpenAI, Anthropic, Gemini, Grok, and Null providers implementing the same
  `ArtistProvider` interface;
- multiple ExpressionProfiles rendering one ArchitectPlan;
- the Expression Matrix;
- the Semantic Contract Inspector; and
- Critic approval and semantic-contract satisfaction remaining distinct.

### Use This Pattern When

- a canonical synthesis must support multiple audiences or providers;
- semantic obligations must remain inspectable before and after expression;
- provider comparison must be contract-neutral; or
- generated communication requires independent evaluation.

### Do Not

- send a NarrativeBlueprint directly to an Artist as the canonical contract;
- let a provider reconstruct obligations independently;
- let the Artist write or revise its CriticReport;
- infer contract fulfillment from fluent wording; or
- treat provider reputation as evidence of fidelity.

---

## Pattern 4 — Inspection Surface

```text
Canonical ID
    ↓
Read-only API
    ↓
Projection
    ↓
Human Inspection
```

### Intent

Make constitutional truth inspectable without giving the interface authority
to construct it.

An inspection surface answers a bounded question about an existing canonical
object.

### Current Examples

| Surface | Question |
|---|---|
| Canonical Lineage API | Where did this come from? |
| Trust Summary API | What persisted facts support trusting this? |
| Semantic Contract Inspector | Which obligations were measured and what did the Critic report? |
| Workspace Projection API | Which canonical objects and inspection surfaces surround the current focus? |

### Properties

- begins with a canonical class and ID;
- uses read-only database access;
- returns explicit references and persisted findings;
- reports missing parentage rather than repairing it;
- exposes `not_evaluated` when no authoritative evaluation exists;
- performs no schema initialization, migration, seeding, or timestamp update;
  and
- allows the frontend to explain results without recomputing them.

### Use This Pattern When

- a user must verify lineage, trust, contract fulfillment, provenance, or
  execution metadata;
- the same underlying facts need multiple presentation profiles;
- the interface would otherwise be tempted to join or infer ontology; or
- progressive disclosure requires a stable authoritative source.

### Do Not

- make a `GET` request mutate storage;
- silently omit a missing required ancestor;
- convert “not evaluated” into “partial” or “probably satisfied”;
- localize ontology class names in the API; or
- let a frontend reconstruct constitutional relations.

---

## Choosing a Pattern

| Question | Pattern |
|---|---|
| Can this be losslessly regenerated from immutable canonical constituents? | Apply the Regeneration Principle first |
| Is this a temporary way of arranging existing canonical objects? | Pure Projection |
| Can this data be deleted and deterministically rebuilt? | Disposable Derived |
| Is an Artist expressing a precompiled semantic contract? | Contract-Constrained Expression |
| Is a human inspecting authoritative facts about a canonical ID? | Inspection Surface |

A feature may use more than one pattern.

For example, the Workspace is a **Pure Projection** delivered through an
**Inspection Surface**. The Trust Card is a **Pure Projection** over several
**Inspection Surfaces**. The Semantic Contract Inspector is an **Inspection
Surface** for the **Contract-Constrained Expression** pattern.

---

## Pattern Review Checklist

Before implementing a feature, answer:

1. Which canonical object or objects already contain the truth?
2. Is the proposed result canonical, derived, projected, expressed, or
   inspected?
3. Can the result be regenerated without loss?
4. Does it require a new ontology object? If so, stop and seek architectural
   authority.
5. Does the frontend translate persisted truth or infer missing truth?
6. Can every returned relation be demonstrated by an existing foreign key,
   relation table, or canonical artifact?
7. Does every read remain side-effect-free?
8. Which constitutional invariant proves the implementation is safe?

If these questions cannot be answered from existing authority, the pattern is
not permission to improvise. Open an architectural discussion.

---

## Summary

Hermeneia implementations should preserve a stable distinction:

```text
Ontology     — what exists
Lineage      — how it came to exist
Expression   — how it is communicated
Projection   — how it is currently arranged for attention
Inspection   — how a human verifies it
```

Presentation is disposable. Ontology is durable.

The interface may focus, translate, compress, and reveal. It may not invent
what exists, how it is related, or why it should be trusted.
