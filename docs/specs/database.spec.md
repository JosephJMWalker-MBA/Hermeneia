# Database Specification

**Status:** ACTIVE IMPLEMENTATION SPECIFICATION  
**Constitutional authority:** [`../00_Constitution.md`](../00_Constitution.md), [`../01_Authority_Index.md`](../01_Authority_Index.md), [`../02_Constitutional_Invariants.md`](../02_Constitutional_Invariants.md), [`../15_Storage.md`](../15_Storage.md)  
**Implements:** Articles I, II, III, V, VI, VII, X, XII, XIII  
**Affected invariants:** CI-001 through CI-016  
**Implementation status:** NOT YET VALIDATED

---

## Role of This Specification

This specification is subordinate to the Constitution and the active storage
specification.

It defines the target SQLite shape for P0-A2 implementation. Existing code is
not yet conformant.

---

## Required Schema Principles

The database shall make the evidence/claim distinction impossible to blur.

Every canonical table shall encode its epistemic class directly through a
column, constraint, view, or stricter equivalent mechanism.

No canonical object may exist without required parentage.

Immutable evidence tables shall reject `UPDATE` and `DELETE` at the database
level.

---

## Evidence Tables

### `source_documents`

Epistemic class: `Artifact`

Required fields:

- `id`;
- `epistemic_class`;
- `original_filename`;
- `content_hash`;
- `media_type`;
- `byte_size`;
- `registered_at`;
- `compiler_version`.

Identity:

```text
SHA256(raw_source_bytes)
```

### `source_extractions`

Epistemic class: `Evidence`

Required fields:

- `id`;
- `epistemic_class`;
- `document_id`;
- `page`;
- `region`;
- `raw_text`;
- `parser`;
- `parser_version`;
- `coordinates`;
- `source_locator`;
- `source_hash`;
- `hash`;
- `extracted_at`.

`raw_text` is exact parser output.

### `observations`

Epistemic class: `Evidence`

Required fields:

- `id`;
- `epistemic_class`;
- `source_extraction_id`;
- `raw_text`;
- `source_locator`;
- `sentence_index`;
- `semantic_hash`;
- `preceding_observation_id`;
- `following_observation_id`;
- `created_at`.

Identity:

```text
SHA256(canonical(source_hash, source_locator, raw_text))
```

Semantic equivalence:

```text
SHA256(UTF8(raw_text))
```

### `observation_derived`

Epistemic class: `DerivedMetadata`

Required fields:

- `observation_id`;
- `normalized_text`;
- `sentence_tokens`;
- `whitespace_map`;
- `derivation_version`;
- `derived_at`.

This table is disposable and regenerable. It shall not determine Observation
identity.

---

## Provenance and Lineage

The database shall preserve append-only ancestry relations.

Required lineage behavior:

- every child references required parents;
- no floating nodes;
- no orphan Interpretations;
- no RenderedNarrative without ArchitectPlan and ExpressionProfile;
- no CriticReport without RenderedNarrative and ArchitectPlan;
- no downstream object may mutate evidence.

A lineage relation table may be used where direct foreign keys are
insufficient, but it must itself be append-only.

### `supersession_relations`

Epistemic role: append-only lineage relation.

Required fields:

- `old_id`;
- `new_id`;
- `reason`;
- `ratified_at`.

Supersession shall never be represented by mutating the superseded object.
Multiple rows with the same `old_id` and different `new_id` values are valid:
competing supersessions coexist.

`UPDATE` and `DELETE` are constitutionally prohibited for this table.

---

## Understanding Tables

### `perspectives`

Epistemic class: `Frame`

Append-only interpretive lens registry.

### `interpretations`

Epistemic class: `Claim`

Required parentage:

```text
Interpretation
    ↓
Perspective
    ↓
Observation
```

Interpretations are append-only claims. Multiple Interpretations may reference
one Observation.

---

## Synthesis, Contract, Expression, Evaluation

### `narrative_blueprints`

Epistemic class: `Synthesis`

Blueprints organize claims and evidence. They are not direct Artist contracts.

### `architect_plans`

Epistemic class: `Contract`

ArchitectPlans compile semantic obligations from NarrativeBlueprints.

### `expression_profiles`

Epistemic class: `Constraint`

ExpressionProfiles constrain expression without changing meaning.

### `rendered_narratives`

Epistemic class: `Expression`

RenderedNarratives shall persist complete nondeterministic audit metadata.

Required audit fields include:

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
- parse errors;
- runtime version.

### `critic_reports`

Epistemic class: `Evaluation`

CriticReports evaluate RenderedNarratives against their referenced
ArchitectPlans and ExpressionProfiles.

---

## Immutability Triggers

At minimum, database-level triggers shall abort `UPDATE` and `DELETE` for:

- `source_documents`;
- `source_extractions`;
- `observations`; and
- provenance/lineage relation tables.

Append-only downstream tables shall also reject in-place replacement where a
new historical object is constitutionally required.

---

## Read-Only Connections

Read-only application paths shall open storage in a mode that cannot mutate
state.

Read paths shall not call schema creation, migration, profile seeding, or any
write helper.

---

## Legacy Databases

Existing databases without SourceExtraction and constitutional triggers are
legacy v0 databases.

They are read-only historical artifacts. A conversion process shall create a
new constitutional artifact rather than rewriting them in place.
