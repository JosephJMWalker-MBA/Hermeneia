# ADR-0006: Observation — Formal Definition

> **Supersession notice (2026-06-19):** Partially superseded by
> [`CA-0001`](../amendments/CA-0001-forensic-evidence-and-identity.md).
> Parser output is now preserved as SourceExtraction, and Observation identity
> is occurrence-based. The rule that one Observation is one sentence remains
> active.

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P0-001 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Existential

> **⛔ COMPILER IMPLEMENTATION IS CONSTITUTIONALLY PROHIBITED UNTIL THIS ADR IS RATIFIED.**
> This prohibition is now lifted. Compiler implementation may proceed in strict conformance with the definition below.

---

## Context

Every downstream object in Hermeneia — Concept, Relationship, Perspective, Interpretation, Dialogue, NarrativeBlueprint — traces its provenance to at least one Observation. The boundary of an Observation is therefore the foundational architectural commitment of the system. An incorrect or ambiguous definition corrupts the provenance chain at its root and cannot be corrected without violating the append-only constraint.

This ADR closes Q-P0-001 from `EPISTEMIC_BACKLOG.md` and satisfies the prerequisite for Milestones R1 and all subsequent implementation milestones.

---

## Decision

### Formal Definition

An **Observation** is the smallest immutable record of information intentionally extracted from a source document that can be traced back to a specific location in that source without requiring interpretation.

An Observation is **descriptive, not inferential**.

It answers: *"What is present in the source?"*  
It does not answer: *"What does this mean?"*

### Validity Criteria

An Observation must satisfy all five of the following simultaneously:

1. **Immutable** — Once written, the `text` field may never be altered. No UPDATE statement may modify it. No normalization may be applied after extraction.
2. **Append-only** — Observations may only be added to a corpus, never removed or replaced.
3. **Provenance-bound** — Every Observation references a valid Provenance record that uniquely identifies its location in the source document.
4. **Interpretation-independent** — The `text` field must contain no claim about meaning, significance, or relationship. It records what exists, not what it signifies.
5. **Reproducible** — If two independent stewards extract the same location from the same source document using the same compiler version, they must produce the same Observation ID and the same `text` field. If they do not, the extraction is not an Observation.

---

## Observation Boundary

The canonical Observation boundary is **a single semantic statement**.

This is independent of physical formatting. Paragraph breaks, line breaks, page breaks, and typographic conventions are editorial artifacts. They do not determine the Observation boundary.

**Meaning determines the boundary, not formatting.**

The following source types produce one Observation per unit:

| Source type | Unit |
|---|---|
| Prose text | One sentence (one complete proposition terminated by `.`, `?`, or `!`) |
| Table | One cell |
| Figure | One caption |
| Equation | One equation (including its label) |
| Bulleted list | One bullet item |
| Labeled diagram element | One label and its associated textual descriptor |

---

## Inclusion Criteria

The following **do** constitute valid Observations:

1. A syntactically complete sentence from prose text, verbatim, regardless of its grammatical quality.
2. A syntactically incomplete fragment that nonetheless constitutes a standalone proposition in context (e.g. a heading: "Chapter Three: The Valley of Ashes").
3. A footnote or endnote, extracted as an independent Observation with its own Provenance record.
4. A table cell containing a text value, with Provenance pointing to row and column coordinates.
5. A figure caption, extracted verbatim with Provenance pointing to the figure's page and position.
6. A bullet point item, extracted verbatim with Provenance pointing to its list position.
7. Text containing OCR errors, extracted exactly as the OCR produced it, with `ocr_used: true` and `confidence` below 1.0 in the Provenance record.
8. A sentence in any language other than English, extracted verbatim with the language recorded in Provenance metadata.
9. A malformed or apparently meaningless string of text (e.g. "Dog blue quickly because mountain.") if it faithfully records what is present in the source.

---

## Exclusion Criteria

The following **do not** constitute valid Observations:

1. An image, diagram, photograph, or figure that contains no textual content. Images are source artifacts, not Observations. A textual description *about* an image feature may be an Observation; the image itself is not.
2. A page header or footer containing only navigation metadata (page numbers, chapter titles repeated from the main text).
3. A blank line or whitespace-only string.
4. A compiler annotation, comment, or processing note that is not present in the source document.
5. A normalized, corrected, or paraphrased version of source text. If the source says "hearf" the Observation says "hearf". A corrected form is a new derived object, not a replacement Observation.
6. A sentence that is an interpretation or inference produced by the extraction system rather than a transcription of source content.
7. An embedding, vector representation, or any other non-verbatim encoding of source content.

---

## Edge Cases

The following edge cases are explicitly resolved by this ADR:

**Malformed sentence** ("Dog blue quickly because mountain.")  
→ Valid Observation. Grammar is irrelevant. Faithfulness to source is the criterion.

**Sentence spanning a paragraph break**  
→ One Observation. Physical paragraph boundaries are editorial artifacts. If one proposition spans two paragraphs, the Observation boundary is the proposition, not the paragraph.

**Paragraph containing five independent propositions**  
→ Five Observations. If a paragraph contains five independently interpretable sentences, the compiler produces five Observations with sequential `sentence` numbering and shared `paragraph` and `page` coordinates.

**Embedded block quotation within a sentence**  
→ Compiler decision required per source type. Default: the block quotation and its surrounding sentence frame are one Observation if they form one semantic statement. If the block quotation is independently meaningful and separately labeled, it is a separate Observation. This default may be refined by a future ADR for specific source types.

**Footnote or endnote**  
→ Independent Observation. A footnote possesses separate provenance: `page`, `paragraph`, and `sentence` coordinates pointing to its location in the footnote region, not to the location of the in-text reference marker. The in-text reference marker (e.g. "¹") is part of the Observation in which it appears; it does not replace the footnote.

**Sentence containing a numbered or bulleted list**  
→ If the list is embedded mid-sentence and grammatically continuous, it is one Observation. If the list items are typographically separated and each is a standalone proposition, each item is a separate Observation.

**Source in a language other than English**  
→ Valid Observation. The `text` field contains the verbatim source text in its original language. Language is recorded in Provenance metadata. No translation is performed at the Observation layer.

**OCR error in source**  
→ Valid Observation. The `text` field records exactly what the OCR produced. The Provenance record carries `ocr_used: true` and a `confidence` value below 1.0. The errored text is never corrected within the Observation. If a correction is later determined, it is a new derived object with a provenance chain leading back to the original errored Observation.

**Image with no textual content**  
→ Not an Observation. The image is a source artifact. If a steward wishes to record something about the image (e.g. "The chart legend contains three categories"), that statement is a new Observation attributed to the steward (human provenance), not a compiled Observation attributed to the source document.

---

## Serialization Rules

The `text` field of an Observation:

- Contains the **verbatim** string extracted from the source, including all punctuation.
- Preserves original whitespace at the sentence level (leading and trailing whitespace is stripped; internal whitespace is preserved).
- Preserves original typographic characters where extractable (e.g. em-dashes, smart quotes) and falls back to ASCII equivalents where the PDF extractor cannot recover the original glyph.
- Never applies normalization, spellchecking, case correction, or punctuation correction.
- Is encoded as UTF-8.
- May be empty only if the source location genuinely contains no text (in which case the Observation should not be created — see Exclusion Criterion 3).

---

## Provenance Implications

Every Observation requires a corresponding Provenance record. The Provenance record must contain sufficient information to allow any steward, using any conforming compiler, to locate the source passage in the source document and verify that `Observation.text` is a faithful transcription of it.

Minimum required Provenance fields for this definition:

| Field | Requirement |
|---|---|
| `source_document` | Filename or document identifier sufficient to uniquely identify the source |
| `page` | 1-indexed page number in the source document |
| `paragraph` | 1-indexed paragraph number on the page (resets to 1 at each new page) |
| `sentence` | 1-indexed sentence number within the paragraph (resets to 1 at each new paragraph) |
| `extraction_method` | String identifying the extraction pipeline used (e.g. "pdfminer-sentence-splitter-v1") |
| `ocr_used` | Boolean |
| `confidence` | Float [0.0–1.0]; 1.0 for clean extraction, lower for OCR uncertainty |
| `extractor_version` | Semantic version string of the compiler that produced this record |
| `parser_version` | Semantic version string of the sentence splitter used |

Character offsets are not required by this ADR but are permitted as optional fields. A future ADR may promote them to required for specific source types (e.g. scanned documents with bounding-box OCR).

---

## Validation Rules

The following rules must be enforced at write time by the storage layer and must be independently testable by `validation/invariants.py`:

```python
assert len(observation.text) > 0
assert observation.text in source_document_text  # verbatim check
assert observation.page >= 1
assert observation.paragraph >= 1
assert observation.sentence >= 1
assert observation.provenance_id is not None
assert provenance_record_exists(observation.provenance_id)
assert observation.id == deterministic_hash(
    observation.source_document,
    observation.page,
    observation.paragraph,
    observation.sentence
)
```

Additionally:

- The Observation table must have `PRAGMA foreign_keys = ON` active on every connection.
- No `UPDATE` statement may target the `observations` table.
- No `DELETE` statement may target the `observations` table.
- Compiling the same source document with the same `extractor_version` and `parser_version` must produce identical Observation IDs across separate runs. This must be verified by the CI suite.

---

## Migration Policy

Observations compiled under this definition carry `extractor_version` and `parser_version` in their Provenance records. If this definition is amended in a future ADR:

1. Existing Observations compiled under ADR-0006 remain valid records. They are not retroactively invalidated.
2. Their `extractor_version` and `parser_version` Provenance fields identify them as compiled under the pre-amendment definition.
3. New compilations under the amended definition produce new Observations, potentially with different IDs for the same source locations.
4. If the amendment changes the Observation boundary definition, a recompilation run must be performed and documented as a new extraction event with new Provenance records.
5. Old and new Observations may coexist in the same `.herm` database, distinguished by their Provenance chain.
6. UPDATE or DELETE on existing Observations is never permitted under any amendment. Amendment never corrects existing records — it only produces new ones.

---

## Constitutional Alignment

This definition satisfies:

- **Article I** (Reality precedes interpretation): Observations record what is present in the source. Interpretation is forbidden at the Observation layer.
- **Article III** (Append-only history): Observations are immutable. The migration policy prohibits UPDATE or DELETE.
- **Article V** (Observations remain distinct from conclusions): The Inclusion and Exclusion criteria enforce the boundary between observation and inference.
- **Axiom 1** (Immutability): Observations are frozen at creation. Their `text` field cannot change.
- **Axiom 6** (Provenance mandatory): Every Observation is provenance-bound to a specific source location.
- **Invariant 2** (Determinism of Primitives): The validation rules enforce that identical input + identical compiler version = identical Observation IDs.
- **Invariant 4** (Architectural Decoupling): The Observation Compiler must have zero LLM imports. Observations are extracted deterministically.

---

## Consequences

**Positive:**
- The provenance chain has an unambiguous root. Every derived object can trace back to a specific, reproducible location in the source.
- The append-only constraint is computationally enforceable.
- The CI suite can verify Invariant 2 (determinism) with a byte-for-byte comparison.
- The Critic can verify Article V by checking that no Observation's `text` field contains interpretive language.

**Negative:**
- The compiler must implement a robust sentence boundary detection algorithm. This is harder than paragraph splitting. Edge cases (abbreviations, quoted speech, lists) require explicit handling.
- OCR errors are preserved verbatim. This is constitutionally correct but creates Observations that are difficult to read. The confidence field in Provenance mitigates this.
- Images produce no Observations by default. Textual descriptions of images require human stewardship, which adds friction for image-heavy corpora.

---

## Alternatives Considered

**Alternative: Paragraph as the Observation unit**  
Rejected. A paragraph may contain multiple independent propositions. Grouping them into one Observation means multiple Claims share a single Provenance unit, reducing epistemic resolution. If an Interpretation derives from one sentence within a paragraph, it cannot be traced to that sentence specifically.

**Alternative: Token as the Observation unit**  
Rejected. Tokens are not meaningful units of epistemic content. An Observation of "the" provides no interpretable information. The provenance database would grow by orders of magnitude with no epistemic benefit.

**Alternative: Allowing normalization during extraction**  
Rejected. Normalization introduces interpretation at the Observation layer. "Faithfully recording what exists" is the constitutional mandate. The compiler must preserve malformed text, typos, and weird spacing exactly as found (AGENTS.md: anti-helpfulness mandate).
