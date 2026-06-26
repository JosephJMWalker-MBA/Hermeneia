# Hermeneia Ontology

**Status:** ACTIVE IMPLEMENTATION AUTHORITY  
**Constitutional authority:** [`00_Constitution.md`](00_Constitution.md), [`01_Authority_Index.md`](01_Authority_Index.md), [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)  
**Implements:** Articles III, V, VI, VII, VIII, IX, X  
**Affected invariants:** CI-001 through CI-011, CI-016  
**Implementation status:** NOT YET VALIDATED

---

## Role of This Document

This ontology is subordinate to the Constitution.

It does not invent domain objects or pipeline stages. It records the
implementation-facing shape of objects already ratified by constitutional
authority.

---

## Evidence Ladder

| Object | Epistemic class | Purpose | Mutability |
|---|---|---|---|
| SourceDocument | Artifact | Original object | Immutable |
| SourceExtraction | Evidence | Exact parser extraction | Immutable |
| Observation | Evidence | Atomic observed unit | Immutable |
| ObservationDerived | Derived metadata | Regenerable convenience layer | Disposable |
| Perspective | Frame | Interpretive lens | Append-only |
| Interpretation | Claim | Meaning proposed under a frame | Append-only |
| NarrativeBlueprint | Synthesis | Structured organization of claims | Append-only |
| ArchitectPlan | Contract | Communication obligations | Append-only |
| ExpressionProfile | Constraint | Stylistic and rhetorical limits | Append-only |
| RenderedNarrative | Expression | Human-facing realization | Append-only |
| CriticReport | Evaluation | Assessment of expression against contract | Append-only |

`ObservationDerived` is not evidence. It is cache-like metadata derived from
evidence and may be regenerated.

---

## SourceDocument

`SourceDocument` is the artifact accepted for compilation.

Required properties:

- deterministic identity derived from original source bytes;
- original filename or source label;
- source content hash;
- registration timestamp;
- compiler or ingestion version; and
- artifact metadata needed for future audit.

`SourceDocument` is immutable.

---

## SourceExtraction

`SourceExtraction` is the forensic record of parser output.

Required properties:

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
- extraction timestamp; and
- chain-of-custody metadata.

`SourceExtraction.raw_text` shall equal parser output exactly. No trimming,
normalization, punctuation substitution, whitespace repair, or inferred text may
occur before persistence.

A new parser or parser version creates a new SourceExtraction. It shall not
mutate an existing one.

---

## Observation

`Observation` is one semantic unit, canonically one sentence, selected from a
SourceExtraction.

Required properties:

- `id`;
- `source_extraction_id`;
- `raw_text`;
- `source_locator`;
- `sentence_index`;
- `semantic_hash`;
- adjacency references where applicable; and
- creation timestamp.

The canonical Observation identity is:

```text
SHA256(canonical(source_hash, source_locator, raw_text))
```

`semantic_hash` is:

```text
SHA256(UTF8(raw_text))
```

Observation identity is occurrence identity. Equal text at different source
locations shall produce different Observation IDs.

`Observation.raw_text` shall preserve the exact characters selected from the
parent SourceExtraction.

---

## ObservationDerived

`ObservationDerived` contains disposable metadata derived from Observation.

Examples:

- `normalized_text`;
- `sentence_tokens`;
- `whitespace_map`;
- term extraction;
- search indexes;
- vector indexes, if future authority permits them.

Derived metadata shall reference its source Observation and derivation version.
It shall not replace evidence, determine identity, or become the parent of a
canonical historical object.

---

## Perspective

`Perspective` is a frame.

It does not assert truth. It defines how truth is being examined.

Perspectives are append-only. They may accumulate but shall not rewrite
Interpretations or evidence.

---

## Interpretation

`Interpretation` is a claim about an Observation under a Perspective.

Required ancestry:

```text
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

Interpretations are append-only. Unlimited Interpretations may refer to one
Observation without mutating it.

---

## NarrativeBlueprint

`NarrativeBlueprint` is synthesis.

It organizes claims and evidence into a structured communicative intent. It is
not prose and is not an Artist contract.

---

## ArchitectPlan

`ArchitectPlan` is the compiled semantic contract.

It derives from a NarrativeBlueprint and defines obligations every valid
RenderedNarrative must satisfy.

The ArchitectPlan is the canonical interface between synthesis and expression.

---

## ExpressionProfile

`ExpressionProfile` is a communication constraint.

It constrains audience, language, register, tone, and rhetorical limits. It
does not change meaning and does not create claims.

---

## RenderedNarrative

`RenderedNarrative` is expression produced by an ArtistProvider from:

```text
ArchitectPlan
ExpressionProfile
ArtistProvider invocation metadata
```

A RenderedNarrative is append-only and auditable. It shall preserve enough
nondeterministic execution context for independent review even when the
provider cannot reproduce identical bytes later.

---

## CriticReport

`CriticReport` is evaluation.

It evaluates a RenderedNarrative against the ArchitectPlan and
ExpressionProfile that constrained it.

The evaluated ArtistProvider shall not create the ArchitectPlan or CriticReport.

---

## Provenance

Provenance is not a competing evidence object.

Provenance is the append-only lineage and custody metadata that relates objects
to their parents. No canonical object may exist without required provenance.
