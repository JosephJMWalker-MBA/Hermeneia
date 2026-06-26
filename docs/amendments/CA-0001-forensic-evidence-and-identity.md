# CA-0001 — Forensic Evidence and Occurrence Identity

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-19  
**Ratified by:** Primary Human Steward

---

## Amendment

The canonical forensic evidence chain is:

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
```

`SourceExtraction` preserves parser output exactly as encountered. Its
constitutional fields are:

```text
id
document_id
page
region
raw_text
parser
parser_version
coordinates
hash
```

`Observation` remains one semantic unit, canonically one sentence. It is
derived from an immutable SourceExtraction. Its constitutional fields include:

```text
id
source_extraction_id
raw_text
sentence_index
```

Provenance is not a competing evidence object. It is orthogonal lineage and
chain-of-custody metadata, including:

```text
derived_from
extracted_by
extracted_at
parser_version
document_hash
coordinates
chain_of_custody
```

Normalization and related conveniences are derived metadata only:

```text
normalized_text
sentence_tokens
whitespace_map
```

They shall never replace SourceExtraction or Observation text.

---

## Identity

The canonical occurrence identity is:

```text
SHA256(canonical(source_hash, source_locator, raw_text))
```

Textual equivalence is independent:

```text
semantic_hash = SHA256(UTF8(raw_text))
```

Occurrence identity preserves provenance. Semantic hash permits equivalence
analysis without collapsing distinct evidence occurrences.

---

## Supersession

This amendment partially supersedes:

- ADR-0006 where parser output is treated as the Observation and where a prior
  Observation identity rule conflicts;
- ADR-0012 where Provenance competes with the sentence evidence object or
  shares its identity;
- ADR-0013 where location and identity rules conflict; and
- ADR-0024 where the canonical object list omits SourceDocument and
  SourceExtraction.

The rule that one Observation is one sentence remains active.

