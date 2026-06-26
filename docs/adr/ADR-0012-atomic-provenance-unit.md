# ADR-0012: The Atomic Provenance Unit Is the Sentence

> **Supersession notice (2026-06-19):** Partially superseded by
> [`CA-0001`](../amendments/CA-0001-forensic-evidence-and-identity.md).
> Provenance is orthogonal lineage and custody metadata rather than a competing
> sentence evidence object. The one-sentence Observation boundary remains
> active.

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P5-001 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

ADR-0006 established that an Observation is a single sentence — the smallest immutable record of information intentionally extracted from a source document. Every Observation requires a Provenance record. The question is: what is the atomic unit of that Provenance record?

The Provenance record must be sufficient to allow any steward, with any conforming compiler, to locate the exact source passage and verify the Observation's fidelity. The granularity of this record determines the precision of the provenance chain for the entire system.

This question must be answered before the Provenance schema can be written and before the storage schema can be initialized.

---

## Decision

**The atomic provenance unit is the sentence.**

One Observation corresponds to exactly one Provenance record. One Provenance record identifies exactly one sentence in exactly one location in exactly one version of exactly one source document.

This decision is a direct consequence of ADR-0006. ADR-0006 defined the Observation unit as a sentence. The Provenance unit tracks the Observation unit. A different provenance granularity than the Observation granularity would make the provenance chain ambiguous: a single Provenance record pointing to a paragraph would be shared by every sentence in that paragraph, making it impossible to identify which sentence any given Observation derives from.

---

## Formal Definition

An **atomic Provenance record** is the minimal set of information sufficient to uniquely identify the source location of exactly one Observation in exactly one source document.

A Provenance record is **source-unique**: no two valid Observations compiled from the same source document with the same `extractor_version` and `parser_version` may produce identical Provenance records.

A Provenance record is **reproducible**: given the Provenance record and the source document, a conforming steward must be able to locate the passage and read the Observation text from it without ambiguity.

---

## Granularity Decision

The candidates were:

| Unit | Verdict | Reason |
|---|---|---|
| Token | Rejected | Tokens are not meaningful epistemic units. Provenance would grow by 20–50× without epistemic benefit. |
| Clause (sub-sentential) | Rejected | Clause splitting requires dependency parsing — a statistical process — introducing non-determinism. ADR-0006 requires deterministic extraction. |
| **Sentence** | **Adopted** | The natural unit of the Observation. Deterministic. Sufficient for unique identification. Consistent with ADR-0006. |
| Paragraph | Rejected | Too coarse. A paragraph may contain 5+ sentences. Provenance at paragraph level cannot identify which sentence an Observation derives from. |
| Page | Rejected | Far too coarse for prose text. Acceptable only for page-image sources where the extractor cannot do better (recorded as `location_precision: page`). |

---

## Required Provenance Fields

The following fields constitute the complete atomic Provenance record for standard prose PDF sources. This is the normative schema.

| Field | Type | Requirement | Purpose |
|---|---|---|---|
| `id` | String (deterministic hash) | Required | Unique, stable identifier for this Provenance record |
| `observation_id` | String | Required | Foreign key to the Observation this Provenance describes |
| `source_document_id` | String | Required | Identifier for the source document (see ADR-0013 for versioning) |
| `source_document_hash` | String (SHA-256) | Required | Hash of the source document file at extraction time |
| `page` | Integer (1-indexed) | Required | Page number in the source document |
| `paragraph` | Integer (1-indexed) | Required | Paragraph number on the page (resets at each new page) |
| `sentence` | Integer (1-indexed) | Required | Sentence number within the paragraph (resets at each new paragraph) |
| `char_offset_start` | Integer | Optional | Character offset of the first character of the sentence in the source text |
| `char_offset_end` | Integer | Optional | Character offset of the character after the last character of the sentence |
| `extraction_method` | String | Required | Identifier for the extraction pipeline (e.g. `pdfminer-v1`) |
| `extractor_version` | SemVer String | Required | Version of the compiler that produced this record |
| `parser_version` | SemVer String | Required | Version of the sentence splitter used |
| `ocr_used` | Boolean | Required | Whether OCR was involved in extracting this text |
| `confidence` | Float [0.0–1.0] | Required | Extraction confidence; 1.0 for clean programmatic extraction |
| `location_precision` | Enum | Required | `sentence` (standard), `paragraph` (fallback), `page` (last resort) |
| `created_at` | ISO 8601 datetime | Required | When this Provenance record was created |

The `id` field of a Provenance record is a deterministic hash of `(source_document_hash, page, paragraph, sentence)`. This makes the Provenance ID reproducible across separate compilation runs of the same source document.

---

## The `location_precision` Field

Some source types cannot guarantee sentence-level precision. The `location_precision` field records the actual achieved precision:

| Value | Meaning | When used |
|---|---|---|
| `sentence` | Full sentence-level precision. `page`, `paragraph`, `sentence` all populated. | Standard PDF text extraction. |
| `paragraph` | Paragraph-level precision only. Sentence splitter failed or was not used. `page` and `paragraph` populated; `sentence` is null. | Malformed PDFs where sentence boundaries are unrecoverable. |
| `page` | Page-level precision only. `page` populated; `paragraph` and `sentence` are null. | Page-image OCR where layout analysis failed. |

**Preference order:** sentence > paragraph > page. The compiler must achieve sentence precision wherever possible. Paragraph or page precision is a last resort and must be flagged with `location_precision` so downstream consumers know the provenance is coarser than standard.

A Provenance record with `location_precision: paragraph` or `location_precision: page` is valid but constitutes a precision warning. Stewards should be alerted when the precision falls below sentence level.

---

## ID Generation

The Provenance record ID is generated as:

```python
import hashlib, json

def provenance_id(source_document_hash: str, page: int, paragraph: int, sentence: int) -> str:
    payload = json.dumps({
        "source_document_hash": source_document_hash,
        "page": page,
        "paragraph": paragraph,
        "sentence": sentence
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

This is identical in structure to the Observation ID function, which hashes `(source_document, page, paragraph, sentence)`. The difference is that Provenance ID uses the document SHA-256 hash (not the filename), making it robust to file renames and copies.

---

## Serialization Rules

- `page`, `paragraph`, `sentence` are 1-indexed integers. 0 is not a valid value.
- `char_offset_start` and `char_offset_end` are byte offsets into the UTF-8-encoded full text of the page, not the paragraph. If character offsets are not available, these fields are null.
- `source_document_hash` is the SHA-256 hex digest of the source file at compile time (not at any later time). It is computed before extraction begins and never updated.
- `ocr_used` is true if any OCR engine was involved, even if the primary extraction was programmatic.
- `confidence` is the minimum confidence across all OCR tokens in the sentence. For non-OCR extraction, it is 1.0.

---

## Validation Rules

```python
assert provenance.observation_id is not None
assert provenance.source_document_hash is not None and len(provenance.source_document_hash) == 64
assert provenance.page >= 1
assert provenance.location_precision in ("sentence", "paragraph", "page")
if provenance.location_precision == "sentence":
    assert provenance.paragraph >= 1
    assert provenance.sentence >= 1
if provenance.location_precision in ("sentence", "paragraph"):
    assert provenance.paragraph >= 1
assert provenance.confidence >= 0.0 and provenance.confidence <= 1.0
assert provenance.id == provenance_id(
    provenance.source_document_hash,
    provenance.page,
    provenance.paragraph if provenance.paragraph else 0,
    provenance.sentence if provenance.sentence else 0
)
# One Provenance record per Observation
assert count(provenance WHERE observation_id = X) == 1
# Every Observation has exactly one Provenance record
assert count(observations WHERE id NOT IN (SELECT observation_id FROM provenance)) == 0
```

Additionally:
- No UPDATE or DELETE on the `provenance` table is permitted.
- The `provenance` table must have a foreign key constraint on `observation_id`.
- The uniqueness constraint `UNIQUE(source_document_hash, page, paragraph, sentence)` must be enforced at the database level.

---

## Migration Policy

1. Provenance records created under this ADR carry `extractor_version` and `parser_version` identifying the pipeline.
2. If this definition is amended to require additional fields, existing Provenance records are not retroactively invalid. Their `extractor_version` identifies them as pre-amendment records.
3. The `location_precision` field allows future amendments to add new precision levels (e.g. `bounding_box` for scanned documents with OCR bounding boxes) without invalidating existing records.
4. No UPDATE or DELETE on existing Provenance records is permitted under any amendment. Amendment never corrects existing records — it only produces new ones for new compilation runs.

---

## Constitutional Alignment

- **Article II** (Provenance mandatory): This ADR defines the form that mandatory provenance takes for Observations. Every Observation has exactly one Provenance record, and every Provenance record is sufficient to locate the source passage.
- **Article III** (Append-only history): Provenance records are write-once. The uniqueness constraint prevents duplicate records. The no-UPDATE/DELETE rule is enforced at the database level.
- **Invariant 2** (Determinism of Primitives): The deterministic hash function for Provenance IDs ensures that separate compilations of the same source produce the same Provenance IDs.

---

## Consequences

**Positive:**
- One Observation, one Provenance record. The relationship is simple and enforced by database constraint.
- The `source_document_hash` field makes Provenance records portable: a `.herm` bundle can be verified against the source document by any steward with access to that document.
- The `location_precision` field allows graceful degradation for difficult source types without creating a separate schema.

**Negative:**
- Sentence-level provenance requires a robust sentence splitter. If the sentence splitter produces different boundaries on different runs (non-determinism), the `page + paragraph + sentence` address will differ between runs, producing different Provenance IDs for the same passage. The CI determinism test (from ADR-0006) will catch this.
- Character offsets are optional. This means some Provenance records cannot support exact sub-string location without reading the full page text. A future ADR may promote character offsets to required for specific source types.

---

## Alternatives Considered

**Alternative: One Provenance record per paragraph, with sentence index carried on the Observation**  
Rejected. This creates a many-to-one Observation-to-Provenance relationship, complicating validation and violating the one-to-one design. The uniqueness constraint becomes unenforceable at the paragraph level when multiple sentences share a Provenance record.

**Alternative: Character offset as the primary key, replacing page/paragraph/sentence**  
Rejected for normative use. Character offsets are fragile: they change if the PDF text extractor produces slightly different whitespace normalization, or if the source document is re-encoded. The `page + paragraph + sentence` address is stable across extractor versions and OCR re-runs as long as the sentence splitter is deterministic. Character offsets are preserved as optional additional fields for highest-precision use cases.
