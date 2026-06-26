# Constitutional Invariants

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-19  
**Ratified by:** Primary Human Steward  
**Authority:** Constitutional law  
**Implementation status:** NOT YET VALIDATED

---

## Purpose

This document translates the Constitution into falsifiable obligations.

Each invariant shall become an executable test. A passing implementation must
prove every applicable invariant across the compiler, storage layer, service
layer, and web layer.

---

## CI-001 — Source Artifact Integrity

The stored SourceDocument hash shall equal the hash of the original source
bytes accepted for compilation.

Recompiling the same source bytes shall produce the same SourceDocument
identity.

---

## CI-002 — Exact Source Extraction

`SourceExtraction.raw_text` shall equal the parser output exactly.

No normalization, trimming, punctuation repair, whitespace repair, Unicode
substitution, or inferred text may occur before persistence of the extraction.

A different parser or parser version shall create a new SourceExtraction rather
than mutate an existing one.

---

## CI-003 — Observation Fidelity

Every Observation shall:

- reference exactly one SourceExtraction;
- represent exactly one segmented semantic unit;
- preserve the exact characters selected from its SourceExtraction;
- preserve a deterministic source locator and sentence index; and
- remain immutable after insertion.

Segmentation metadata may identify boundaries. It shall not rewrite the
selected text.

---

## CI-004 — Occurrence Identity

Observation identity shall be derived only from:

```text
source_hash
source_locator
raw_text
```

The same occurrence compiled twice shall have the same identity.

Changing normalization, tokenization, interpretation, or presentation shall
not change the Observation identity.

Equal text at different source locations shall produce different occurrence
identities and may share the same semantic hash.

---

## CI-005 — Immutable Persistence

The authoritative store shall reject `UPDATE` and `DELETE` for immutable
forensic objects, including SourceDocument, SourceExtraction, Observation, and
their provenance relations.

Append-only downstream objects and authority relations shall not be rewritten
in place.

An invalid extraction requires a new compilation lineage, not mutation.

---

## CI-006 — Strict Ancestry

No canonical object may exist without all required parents.

A RenderedNarrative shall be traceable through:

```text
RenderedNarrative
    ↓
ExpressionProfile
    ↓
ArchitectPlan
    ↓
NarrativeBlueprint
    ↓
Interpretation
    ↓
Perspective
    ↓
Observation
    ↓
SourceExtraction
    ↓
SourceDocument
    ↓
original source coordinates
```

Creation shall fail if any required parent or provenance relation is absent.

---

## CI-007 — Downward Non-Interference

Interpretation, synthesis, contract compilation, expression, and evaluation
shall never modify SourceDocument, SourceExtraction, or Observation data.

Higher-layer concepts shall not leak into forensic evidence fields.

---

## CI-008 — Plural Interpretation

The system shall permit unlimited append-only Interpretations over one
Observation.

Creating 100 Interpretations shall leave the parent Observation byte-for-byte
unchanged and shall preserve all 100 claims.

A later Interpretation shall not invalidate, replace, or mutate an earlier
Interpretation.

---

## CI-009 — Contract Dominance

Every RenderedNarrative shall reference the ArchitectPlan it attempts to
fulfill and the ExpressionProfile that constrained its expression.

An Artist shall not create or replace the ArchitectPlan.

A Critic shall evaluate the RenderedNarrative against its referenced
ArchitectPlan and shall not evaluate a contract created by the evaluated
Artist.

---

## CI-010 — Deterministic Reproduction

Given identical immutable ancestors, implementation version, and configuration,
every deterministic stage shall reproduce identical output and identity.

This includes hashing, source location encoding, segmentation where the active
compiler specification declares it deterministic, and deterministic contract
compilation.

---

## CI-011 — Nondeterministic Audit Record

Every nondeterministic invocation shall persist:

- complete input;
- direct parent identities;
- provider identity;
- model identity;
- model and API configuration;
- prompt or request payload;
- execution timestamp;
- execution metadata available from the provider;
- raw output;
- resulting canonical object identity; and
- complete provenance.

The record shall support independent audit even when the provider can no
longer reproduce the same bytes.

---

## CI-012 — Side-Effect-Free Reads

Read operations shall not:

- create or migrate schemas;
- seed or initialize profiles;
- insert canonical objects;
- update timestamps;
- modify authority status; or
- perform any persistent mutation.

Tests shall compare storage state before and after representative read-only
requests.

---

## CI-013 — Singular Portable Format

Every portable Hermeneia artifact shall conform to the one active `.herm`
storage specification.

No exporter, importer, compiler, or web path may silently emit or accept a
competing authoritative bundle format.

---

## CI-014 — Monotonic Supersession

Superseding an authority shall:

- preserve the superseded artifact unchanged;
- append an AuthorityEntry status record;
- append a SupersessionRelation;
- identify the successor, reason, and ratification date; and
- leave the historical text inspectable.

---

## CI-015 — Anti-Helpfulness Compliance

A constitutional audit shall answer **No** to every question:

- Can source text be silently modified?
- Can a SourceExtraction be edited?
- Can an Observation be edited?
- Can provenance be lost?
- Can an Interpretation overwrite evidence?
- Can a RenderedNarrative exist without traceability?
- Can storage drift from the active specification?
- Can identical evidence occurrences produce different identities under the
  same active deterministic specification?
- Can a read-only operation mutate state?
- Can a downstream object obscure its ancestors?

---

## CI-016 — Derived Artifact Disposability

Derived artifacts shall be disposable.

The following may be deleted and regenerated without changing constitutional
history:

- `ObservationDerived`;
- normalization outputs;
- tokenization outputs;
- whitespace maps;
- field indexes;
- embeddings, if a future ratified layer permits them;
- vector indexes;
- search caches; and
- other computational conveniences derived from immutable ancestors.

Derived artifacts shall:

- reference the immutable ancestor from which they were derived;
- record the derivation specification or implementation version where
  applicable;
- never become the authoritative source for evidence;
- never determine Observation identity;
- never replace SourceDocument, SourceExtraction, Observation, Interpretation,
  NarrativeBlueprint, ArchitectPlan, RenderedNarrative, or CriticReport; and
- be safe to rebuild from immutable ancestors.

Deleting a derived artifact shall not delete, mutate, obscure, or supersede
any canonical object.

---

## Constitutional Compliance Report

P0 conformance shall produce a machine-generated report evaluating every
constitutional invariant.

The report shall identify, for each invariant:

- status;
- executable test or validator;
- storage or code evidence;
- failure reason, if any; and
- affected constitutional authority.

The report is a compliance certificate, not a substitute for passing tests.

---

## P0 Exit Criterion

Hermeneia reaches architectural integrity when it can truthfully assert:

> Given the same source document, Hermeneia preserves the original artifact
> and exact parser extraction immutably, assigns deterministic occurrence
> identities, maintains an append-only provenance graph, and permits unlimited
> future interpretations without ever altering the original evidence.

The assertion is valid only when the executable tests for this document pass.
