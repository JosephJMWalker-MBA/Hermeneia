# ADR-0013: Provenance Granularity — Document Versioning and Source Mutability

> **Supersession notice (2026-06-19):** Partially superseded by
> [`CA-0001`](../amendments/CA-0001-forensic-evidence-and-identity.md) where
> location and identity rules conflict. Occurrence identity is derived from
> source hash, source locator, and raw text.

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P5-002 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

ADR-0012 established that the atomic provenance unit is the sentence, and that a Provenance record contains `(source_document_hash, page, paragraph, sentence)` as its identifying coordinates. This ADR resolves the remaining granularity questions:

1. For PDF documents: is `page + paragraph + sentence` sufficient, or are character offsets required?
2. For OCR documents: should bounding-box coordinates be stored?
3. For versioned sources: how does Provenance distinguish edition 1.0 from edition 1.1 of the same document?
4. For mutable sources (web pages, revised editions): how is Provenance preserved when the source changes?

These are implementation-level choices with existential consequences: the wrong answer makes two different editions of the same text look identical, or makes the same edition look different on two different machines.

---

## Decision

### Rule 1: PDF text documents — page + paragraph + sentence is normative; character offsets are optional

For standard PDF documents where text extraction is deterministic (pdfminer, pypdf, or equivalent rule-based extractor), `page + paragraph + sentence` is sufficient to uniquely identify a source passage across re-compilations of the same document version.

Character offsets (byte positions in the page text stream) are permitted as optional fields. They become required only when:
- The compiler is configured to produce them (via a `require_char_offsets: true` flag in compiler configuration).
- The source type is scanned (OCR), where paragraph and sentence boundaries may be uncertain.

**Default:** `page + paragraph + sentence` only. Character offsets null.

### Rule 2: OCR scanned documents — bounding boxes are a named optional field set

For scanned documents where the compiler uses an OCR engine that produces bounding-box coordinates:

```
bbox_x, bbox_y, bbox_width, bbox_height
```

These are stored as optional fields on the Provenance record (four separate integer columns, or a JSON blob in a `bbox` column). They are in pixels relative to the page image at a stated DPI (stored in `bbox_dpi`).

When bounding boxes are available, `location_precision` is upgraded to `sentence_with_bbox`.

**This does not replace** `page + paragraph + sentence`. Bounding boxes are supplementary. If an OCR re-run at different DPI produces different pixel coordinates, the bounding boxes diverge — but `page + paragraph + sentence` remains stable (assuming the sentence splitter produces the same boundaries). The primary identifying coordinates are always `page + paragraph + sentence`; bounding boxes are forensic aids.

### Rule 3: Document versioning — source_document_hash is mandatory and authoritative

The `source_document_hash` field (SHA-256 of the source file) is the mechanism that distinguishes versions. It is not optional.

Two Provenance records with identical `page + paragraph + sentence` but different `source_document_hash` values refer to different versions of the document. They are not duplicates — they are separate, valid records.

**Named consequence:** A `.herm` bundle compiled from the 1925 Scribner first edition of *The Great Gatsby* and a `.herm` bundle compiled from the 1990 Penguin edition will produce Provenance records with different `source_document_hash` values even if the text of a given sentence is identical. Their Observation IDs will therefore differ (since the Observation hash includes the source document identifier). The two bundles are not interchangeable.

The `source_document_id` field (human-readable identifier: title, edition, publisher, year) provides the human-readable label. The `source_document_hash` provides the machine-verifiable identity. Both are required.

### Rule 4: Mutable sources — compile against a frozen snapshot; hash the snapshot

For sources that change — web pages, digitized manuscripts under revision, living documents — Hermeneia does not track the change. Instead:

1. **At compile time**, a frozen snapshot of the source is taken (saved to a specified snapshot directory).
2. **The snapshot hash** is what appears in `source_document_hash`.
3. **The snapshot file** is what the compiler reads.
4. If the source changes after compilation, the existing `.herm` bundle remains valid — it is compiled against the snapshot, not the live source.
5. If the steward wants to compile against the new version, they take a new snapshot, run a new compilation, and produce a new `.herm` bundle with new Provenance records carrying the new `source_document_hash`.

The two bundles (old version, new version) may coexist. The steward decides which is canonical for their corpus. The Provenance records in each bundle unambiguously identify which version of the source they derive from.

**The compiler must refuse to compile from a source with no stable hash** (e.g. a live URL without a snapshot). The steward must snapshot the source first. This is not optional.

---

## The Edition Verification Test

The validation method proposed in Q-P5-002: *"Compile the same paragraph from two different editions of the same book. The Provenance records must differ in a way that makes the edition distinguishable without reading the Observation text."*

This test is now formally satisfied by Rule 3:

- Edition A (1925 Scribner): `source_document_hash = abc123...`
- Edition B (1990 Penguin): `source_document_hash = def456...`

Even if page 1, paragraph 1, sentence 1 is identical in both editions, their Provenance records differ at `source_document_hash`. The edition is identifiable without reading any Observation text, as required.

---

## Complete Provenance Schema (Normative)

This is the normative Provenance record schema, incorporating ADR-0012 fields and the additions from this ADR:

| Field | Type | Requirement |
|---|---|---|
| `id` | String (SHA-256 hash) | Required. Deterministic. |
| `observation_id` | String | Required. Foreign key to Observations. |
| `source_document_id` | String | Required. Human-readable: title + edition + publisher + year. |
| `source_document_hash` | String (SHA-256, 64 hex chars) | Required. Machine-verifiable document identity. |
| `page` | Integer (1-indexed) | Required for `location_precision: sentence/paragraph`. |
| `paragraph` | Integer (1-indexed) | Required for `location_precision: sentence`. |
| `sentence` | Integer (1-indexed) | Required for `location_precision: sentence`. |
| `char_offset_start` | Integer or null | Optional. |
| `char_offset_end` | Integer or null | Optional. |
| `bbox_x` | Integer or null | Optional. Pixels. OCR sources only. |
| `bbox_y` | Integer or null | Optional. Pixels. OCR sources only. |
| `bbox_width` | Integer or null | Optional. Pixels. OCR sources only. |
| `bbox_height` | Integer or null | Optional. Pixels. OCR sources only. |
| `bbox_dpi` | Integer or null | Optional. DPI of the page image the bounding box was computed against. |
| `extraction_method` | String | Required. Pipeline identifier. |
| `extractor_version` | SemVer String | Required. |
| `parser_version` | SemVer String | Required. |
| `ocr_used` | Boolean | Required. |
| `confidence` | Float [0.0–1.0] | Required. |
| `location_precision` | Enum | Required. `sentence`, `sentence_with_bbox`, `paragraph`, `page`. |
| `created_at` | ISO 8601 datetime | Required. |

---

## Source Document Registration

Before a source document can be compiled, it must be registered in a `source_documents` table. Registration captures:

| Field | Type | Purpose |
|---|---|---|
| `id` | String | Matches `source_document_id` in Provenance |
| `hash` | String (SHA-256) | Matches `source_document_hash` in Provenance |
| `title` | String | Human-readable title |
| `edition` | String or null | Edition identifier if known |
| `publisher` | String or null | Publisher name if known |
| `year` | Integer or null | Publication year if known |
| `filename` | String | Filename of the source file at compile time |
| `snapshot_path` | String or null | Path to the frozen snapshot, if source is mutable |
| `registered_at` | ISO 8601 datetime | When this source was registered |
| `registered_by` | String | Steward who registered this source |

The `source_documents` table is append-only. A source document registered under one hash may not have its hash changed. If a new version is compiled, a new `source_documents` row is added with the new hash.

---

## Validation Rules

```python
assert len(provenance.source_document_hash) == 64
assert all(c in '0123456789abcdef' for c in provenance.source_document_hash)
assert provenance.source_document_id is not None and len(provenance.source_document_id) > 0
assert source_document_is_registered(provenance.source_document_hash)

# Two editions of the same title must produce different hashes
assert hash("gatsby_1925.pdf") != hash("gatsby_1990.pdf")

# Bounding box fields must be all present or all absent
if provenance.bbox_x is not None:
    assert provenance.bbox_y is not None
    assert provenance.bbox_width is not None
    assert provenance.bbox_height is not None
    assert provenance.bbox_dpi is not None

# Character offsets must be internally consistent if present
if provenance.char_offset_start is not None:
    assert provenance.char_offset_end is not None
    assert provenance.char_offset_end > provenance.char_offset_start
```

---

## Migration Policy

1. Bundles compiled before this ADR lack the `source_document_id` and `source_document_hash` fields in Provenance. They are identified by `extractor_version` carrying a pre-ADR-0013 version tag.
2. Existing bundles without document hashes remain valid for reading. They cannot participate in edition-distinguishing queries until recompiled under this ADR.
3. Optional fields (`char_offset_*`, `bbox_*`) may be added to existing Provenance records by a recompilation run that produces them. The recompilation adds new Provenance records (with the new fields) alongside the old ones; the old records are not deleted or updated.
4. The `location_precision` enum may be extended with new values in future ADRs. Readers must treat unknown `location_precision` values gracefully (warn, do not fail).

---

## Constitutional Alignment

- **Article II** (Provenance mandatory): The full Provenance schema defined here satisfies the constitutional mandate. No Observation may exist without a Provenance record sufficient to uniquely locate its source passage.
- **Article III** (Append-only history): `source_documents` table is append-only. Provenance records are write-once. New versions create new records, not updates to old ones.
- **Invariant 2** (Determinism): The `source_document_hash` ensures that Provenance IDs are stable across compilation environments, as long as the source file is identical.

---

## Consequences

**Positive:**
- Two `.herm` bundles from different source editions are unambiguously distinguishable by `source_document_hash` without reading any content.
- Mutable sources (web pages, living documents) are handled by a snapshot requirement, not by a complex versioning scheme. The append-only constraint is preserved.
- OCR bounding boxes are accommodated as optional supplementary fields without breaking the normative schema.

**Negative:**
- The compiler must hash the source document before extraction begins. For large PDFs this is fast (SHA-256 on a 10MB PDF takes <1 second), but the hash adds a step that cannot be parallelized with extraction.
- Stewards must maintain a snapshot archive for mutable sources. If the snapshot is lost, the `source_document_hash` in Provenance cannot be verified against any available file. The Observations remain valid (they are verbatim), but the provenance chain loses its verifiability for that source.
- The optional character offset and bounding box fields add schema complexity. The CI test suite must verify that optional fields do not accidentally become required in practice (i.e. that bundles without them are accepted by all bundle readers).

---

## Alternatives Considered

**Alternative: Use a content-addressed URI (e.g. IPFS CID) instead of SHA-256**  
Considered. Rejected for the normative schema. IPFS CIDs are content-addressed SHA-256 digests with a different encoding (multihash). They are not widely available in Python without additional dependencies. The plain SHA-256 hex digest achieves the same uniqueness guarantee without external dependencies.

**Alternative: Require character offsets for all PDF sources**  
Rejected. Character offsets are fragile across extractor versions. The same sentence may produce different offsets if the extractor normalizes whitespace differently between versions. `page + paragraph + sentence` is more stable and adequate for unique identification. Character offsets are available as optional fields for use cases that need sub-sentence precision.
