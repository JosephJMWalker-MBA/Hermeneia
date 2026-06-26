# Storage Specification: The `.herm` Corpus

**Status:** ACTIVE IMPLEMENTATION AUTHORITY  
**Constitutional authority:** [`00_Constitution.md`](00_Constitution.md), [`01_Authority_Index.md`](01_Authority_Index.md), [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)  
**Implements:** Articles I, II, III, V, VI, X, XII, XIII  
**Affected invariants:** CI-001 through CI-016  
**Implementation status:** NOT YET VALIDATED

---

## Role of This Document

This document defines the active portable storage target for Hermeneia.

It is subordinate to the Constitution. It shall not create competing authority
for evidence, identity, provenance, or mutation rules.

---

## Authoritative Bundle Shape

The one active `.herm` format is:

```text
bundle.herm/
    context.json
    hermeneia.db
```

`context.json` contains corpus-level context and storage metadata.

`hermeneia.db` is the authoritative graph and evidence store.

No JSONL export is authoritative. JSONL may exist only as an explicitly labeled
derived export.

---

## Legacy Bundle Classification

Previous bundle layouts such as:

```text
bundle.herm/
    manifest.json
    source_document.json
    observations.jsonl
    provenance.jsonl
```

are classified as:

```text
Hermeneia v0
Legacy
Non-Constitutional
Read-only
Convertible by import only
```

A legacy importer shall create a new constitutional artifact linked back to the
legacy source. It shall not rewrite the legacy bundle.

---

## Required Evidence Tables

The storage layer shall distinguish evidence from claims at the schema level.

The forensic evidence chain is:

```text
source_documents
    ↓
source_extractions
    ↓
observations
    ↓
observation_derived
```

`observation_derived` is disposable metadata, not evidence.

---

## SourceDocument Identity

`source_documents.id` shall be derived from the original source bytes.

```text
SHA256(raw_source_bytes)
```

Recompiling identical source bytes shall produce the same SourceDocument
identity.

---

## SourceExtraction Storage

`source_extractions` shall preserve exact parser output.

Required fields include:

- `id`;
- `document_id`;
- `page`;
- `region`;
- `raw_text`;
- `parser`;
- `parser_version`;
- `coordinates`;
- `source_locator`;
- `hash`;
- `extracted_at`; and
- chain-of-custody metadata.

`raw_text` shall equal parser output exactly. It shall not be trimmed,
normalized, corrected, or otherwise made more useful before persistence.

---

## Observation Identity

The canonical Observation identity is:

```text
SHA256(canonical(source_hash, source_locator, raw_text))
```

The active implementation shall define a deterministic canonical encoding for
the tuple above.

Observation identity shall not depend on normalization, tokenization,
interpretation, presentation, provider, or Critic output.

The semantic equivalence hash is:

```text
semantic_hash = SHA256(UTF8(raw_text))
```

Occurrence identity and semantic equivalence shall remain distinct.

---

## Derived Metadata

`observation_derived` may contain:

- normalized text;
- sentence tokens;
- whitespace maps;
- field terms;
- search indexes;
- vector indexes, if future authority permits them.

Derived metadata is disposable. It shall be safe to delete and regenerate from
immutable ancestors.

---

## Append-Only Enforcement

The authoritative store shall reject `UPDATE` and `DELETE` for immutable
forensic objects and provenance relations.

At minimum, the following tables require no-update and no-delete enforcement:

- `source_documents`;
- `source_extractions`;
- `observations`; and
- provenance/lineage relation tables.

The enforcement mechanism shall be database-level, not merely application
discipline.

Example pattern:

```sql
CREATE TRIGGER observations_no_update
BEFORE UPDATE ON observations
BEGIN
    SELECT RAISE(ABORT, 'Observation immutable');
END;

CREATE TRIGGER observations_no_delete
BEFORE DELETE ON observations
BEGIN
    SELECT RAISE(ABORT, 'Observation immutable');
END;
```

Equivalent triggers shall exist for all immutable evidence tables.

---

## Lineage Enforcement

No canonical object may exist without required parents.

The storage layer shall enforce ancestry through foreign keys, lineage
relations, or stricter equivalent constraints.

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
```

Creation shall fail if required ancestry is missing.

---

## Nondeterministic Audit Records

Every frontier-model invocation shall persist:

- parent object identity;
- provider;
- model;
- model revision, if exposed;
- SDK version;
- API endpoint;
- request payload;
- response payload;
- system prompt;
- user prompt;
- tool schema, if any;
- temperature;
- `top_p`;
- seed, if any;
- execution start timestamp;
- execution finish timestamp;
- latency in milliseconds;
- cost, if available;
- raw output;
- parsed output;
- parse errors; and
- runtime version.

The purpose is auditability, not guaranteed byte-for-byte reproduction.

---

## Read-Only Storage Rule

Read operations shall not initialize, migrate, seed, update, insert, delete, or
touch timestamps.

Any path that performs storage initialization is a write path, regardless of
HTTP method or UI label.

---

## Constitutional Compliance

The storage implementation is conformant only when the executable tests for
[`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md) pass and a
machine-generated compliance report verifies every applicable invariant.
