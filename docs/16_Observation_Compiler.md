# Compiler Stage 1: Source Extraction and Observation Compiler

**Status:** ACTIVE IMPLEMENTATION AUTHORITY  
**Constitutional authority:** [`00_Constitution.md`](00_Constitution.md), [`01_Authority_Index.md`](01_Authority_Index.md), [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)  
**Implements:** Articles I, III, IV, V, VI, X, XIV  
**Affected invariants:** CI-001 through CI-005, CI-007, CI-010, CI-015, CI-016  
**Implementation status:** NOT YET VALIDATED

---

## Role of This Document

This compiler specification is subordinate to the Constitution.

It defines how Stage 1 shall preserve artifacts, record exact parser evidence,
derive Observations, and produce disposable metadata without violating the
Anti-Helpfulness mandate.

---

## Stage 1 Boundary

Stage 1 is deterministic, local, and non-inferential.

Stage 1 shall not use:

- LLMs;
- embeddings;
- sentiment analysis;
- symbolic interpretation;
- pronoun resolution;
- named entity resolution;
- typo correction;
- grammar repair; or
- semantic inference.

---

## Canonical Stage 1 Flow

The Stage 1 flow is:

```text
SourceDocument
    ↓
exact parser output
    ↓
SourceExtraction
    ↓
sentence segmentation
    ↓
Observation
    ↓
ObservationDerived
```

Parser output is not an Observation.

Observation is derived from immutable SourceExtraction.

ObservationDerived is disposable metadata.

---

## SourceDocument Registration

The compiler shall register the input artifact as a SourceDocument.

The SourceDocument identity is:

```text
SHA256(raw_source_bytes)
```

The compiler shall preserve enough artifact metadata to support future audit.

---

## SourceExtraction

The parser shall produce SourceExtraction records before normalization or
segmentation.

Each SourceExtraction shall record:

- parent SourceDocument;
- page;
- region;
- exact `raw_text`;
- parser;
- parser version;
- coordinates where available;
- source locator;
- extraction timestamp; and
- custody metadata.

`SourceExtraction.raw_text` shall equal parser output exactly.

The compiler shall not call `.strip()`, collapse whitespace, repair line
breaks, normalize Unicode, or filter text before persisting SourceExtraction.

Empty or non-text parser outputs may be excluded only by an explicit compiler
rule documented and tested as extraction selection, not as text modification.

---

## Observation Segmentation

Every Observation shall:

- reference exactly one SourceExtraction;
- represent exactly one semantic unit, canonically one sentence;
- preserve the exact characters selected from SourceExtraction;
- record source locator and sentence index; and
- have deterministic occurrence identity.

Segmentation metadata may identify boundaries. It shall not rewrite selected
text.

---

## Observation Identity

The canonical Observation identity is:

```text
SHA256(canonical(source_hash, source_locator, raw_text))
```

Changing normalization, tokenization, field extraction, interpretation,
presentation, provider, or Critic output shall not change the Observation ID.

Equal text at different source locations shall produce different Observation
IDs.

---

## ObservationDerived

After SourceExtraction and Observation are persisted, the compiler may derive:

- normalized text;
- sentence tokens;
- whitespace maps;
- field terms;
- search indexes; and
- other cache-like metadata.

Derived metadata shall be safe to delete and regenerate.

Derived metadata shall never replace SourceExtraction or Observation text.

---

## Forbidden Operations

During Stage 1, the compiler shall not:

- clean up malformed parser output;
- normalize punctuation before SourceExtraction persistence;
- normalize whitespace before SourceExtraction persistence;
- correct typos;
- resolve ambiguity;
- merge evidence occurrences;
- deduplicate Observations by text alone;
- overwrite prior evidence;
- mutate an existing SourceExtraction;
- mutate an existing Observation; or
- create downstream claims.

---

## Output

The compiler output is a constitutional `.herm` artifact:

```text
bundle.herm/
    context.json
    hermeneia.db
```

Legacy JSONL bundle output is not constitutional P0 storage.

---

## Success Criteria

Stage 1 succeeds only when tests prove:

- SourceDocument hash equals source bytes;
- SourceExtraction preserves parser output exactly;
- Observation text is selected from SourceExtraction without character
  rewriting;
- Observation identity follows the occurrence formula;
- derived metadata is disposable;
- immutable evidence rejects update and delete;
- recompilation of identical input preserves deterministic identities; and
- no read path mutates state.
