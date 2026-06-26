# Experiment 001 — First Cross-Provider Interpretation

**Status:** COMPLETED  
**Date:** 2026-06-20  
**Steward:** Joseph Walker  
**Constitutional gate:** Pre-E8 (staging protocol not yet used — proposals submitted informally; this experiment preceded the E8 gate and serves as baseline)

---

## Purpose

Verify that multiple AI providers can generate candidate interpretations grounded in Hermeneia observations. Establish baseline interpretation behavior across providers before the E8 staging protocol is exercised.

This experiment ran before its scope was fully defined. The object under interpretation was not a single observation. It was a 10-row slice from the observations table — the first rows returned by `SELECT * FROM observations LIMIT 10` after compiling gatsby.pdf. This scope ambiguity became the central finding.

---

## Document

**Source document:** The Great Gatsby, F. Scott Fitzgerald (Planet eBook edition)  
**File path:** `examples/gatsby.pdf`  
**Document ID (sha256):** *(to be recorded from build/hermeneia.db source_documents)*  
**Total observations extracted:** 2,823  
**Source extractions:** 1,459  
**Schema version at compile time:** 15

---

## Observation IDs

The object provided to all five providers was the first 10 rows from the observations table, not a single observation. This was unintentional. It became the experiment.

| Observation ID | Source Locator | Raw Text |
|---|---|---|
| c25522fe… | page:1:block:0:sentence:1 | Download free eBooks of classic literature, books and novels at Planet eBook. |
| 99ca3691… | page:1:block:0:sentence:2 | Subscribe to our free eBooks blog and email newsletter. |
| f1ac3a4c… | page:1:block:1:sentence:1 | The Great Gatsby |
| 6e576d8e… | page:1:block:2:sentence:1 | By F. Scott Fitzgerald |
| b6a0e9d2… | page:2:block:0:sentence:1 | The Great Gatsby *(with trailing whitespace — different hash)* |
| 0b18da03… | page:2:block:1:sentence:1 | Then wear the gold hat, if that will move her… *(epigraph)* |
| 38506053… | page:2:block:2:sentence:1 | —THOMAS PARKE D'INVILLIERS |
| 7bc535fb… | page:3:block:0:sentence:1 | Free eBooks at Planet eBook.com |
| 1e994489… | page:3:block:1:sentence:1 | Chapter 1 |
| e17a0861… | page:3:block:3:sentence:1 | n my younger and more vulnerable years my father gave me some advice that I've been turning over in my mind ever since. |

---

## Proposed Interpretations

Five providers were given the 10-row slice and asked to generate three candidate interpretations. No staging protocol was used. Interpretations recorded verbatim below.

### Grok

**Candidate 1:** The narrator recalls a specific piece of advice given by his father during his younger and more vulnerable years, and states that he has continued to reflect on that advice up to the present moment.

**Candidate 2:** The narrator identifies a period in his life ("younger and more vulnerable years") in which his father delivered advice, and explicitly notes the ongoing mental activity of turning that advice over in his mind ever since.

**Candidate 3:** The narrator establishes a temporal relationship between a past event (receiving paternal advice in his vulnerable youth) and his current state (still actively considering that same advice).

---

### Gemini

**Candidate 1:** The id column utilizes 64-character hexadecimal strings rather than sequential integers — the system assigns primary keys using a hashing algorithm, likely SHA-256, generated from raw_text content or metadata to ensure uniqueness and detect duplication.

**Candidate 2:** The observations table stores document content by breaking it into discrete, granular text blocks. The query output reads in the exact chronological order of the book's front matter and first chapter — the ingestion process preserves the original sequential structure of the source document.

**Candidate 3:** The data pipeline populates raw_text verbatim without applying semantic cleaning — evidenced by the retention of publisher promotional text, encoding artifacts likely representing page numbers, and truncation of drop-cap formatting ("n my younger" instead of "In my younger").

---

### Meta

**Interpretation 1:** The observations table contains text entries that include lines from *The Great Gatsby* by F. Scott Fitzgerald. Evidence: title row, author row, chapter text.

**Interpretation 2:** The observations table contains text entries that include promotional material for Planet eBook. Evidence: "Download free eBooks…" row, "Subscribe…" row, "Free eBooks at Planet eBook.com" row.

**Interpretation 3:** The observations table contains text entries that include an epigraph attributed to Thomas Parke D'Invilliers preceding Chapter 1. Evidence: epigraph text, attribution row.

---

### Claude

**Candidate 1 (Two interleaved provenance strata):** The set contains both the work and the distribution platform's paratext woven together — platform boilerplate holds the same observational status as the text proper, indicating ingestion captured the container alongside the content without marking a boundary.

**Candidate 2 (Content-addressing is whitespace-sensitive):** "The Great Gatsby" appears twice with different hashes despite identical visible text; the second carries trailing blank lines. The id is computed over raw bytes including layout whitespace, so semantically identical strings resolve to distinct observations.

**Candidate 3 (The chapter opening lost a typographic initial):** The first-sentence row begins "n my younger and more vulnerable years," missing the leading "I," preceded by a standalone "Chapter 1" row. The source rendered the chapter's first letter as a decorative drop-cap that the extractor failed to recover.

---

### GPT

**Candidate 1:** The observation contains bibliographic information identifying a work titled *The Great Gatsby* and attributing authorship to F. Scott Fitzgerald. Evidence: title row, author row.

**Candidate 2:** The observation contains the opening portion of a narrative text that begins with a first-person narrator recalling advice received from his father. Evidence: "In my younger and more vulnerable years…" row.

**Candidate 3:** The observation appears to include front matter from a digital book edition distributed by Planet eBook before the start of Chapter 1. Evidence: Planet eBook rows, "Chapter 1" row.

---

## Steward Decisions

No formal steward decisions recorded — the E8 staging protocol was not in use at the time of this experiment. This experiment is the baseline preceding the constitutional gate.

---

## Results

**Providers queried:** 5 (Grok, Gemini, Meta, Claude, GPT)  
**Proposals submitted per provider:** 3  
**Total proposals:** 15  
**Formally accepted into canonical corpus:** 0 (pre-staging)

**Lineage verified:** N/A (no canonical objects created)

**Constitutional gate held:** N/A (gate not yet used)

---

## Notes

### The central finding

The object under interpretation was ambiguous. All five providers received the same 10-row database slice. They interpreted different objects:

| Provider | Object Interpreted | Interpretation Type |
|---|---|---|
| Grok | The narrator (row 10 only) | Narrative |
| Claude | The database slice as a database slice | Structural |
| Gemini | The extraction pipeline's behavior | System |
| GPT | The document's content and structure | Descriptive |
| Meta | What categories of content are present | Catalog |

None of these are wrong. They answered different questions about the same evidence.

### The scope ambiguity was the most important finding

Claude and Gemini correctly identified that the object under interpretation was a database slice, not a literary passage. Grok implicitly narrowed scope to row 10 and produced literary interpretation. GPT and Meta cataloged what was present across all 10 rows.

In Hermeneia terms: the Perspective determines what layer of reality is habitually interpreted. These five responses suggest that "Perspective" may encode not just a viewpoint but a **default interpretive layer** — some providers interpret at the narrative layer, others at the evidence layer, others at the system layer. That is a research hypothesis worth carrying forward.

### What this demonstrates architecturally

Without the E8 staging gate, all 15 interpretations would appear equally authoritative. With Hermeneia, each becomes a proposal carrying its provenance — which model, which prompt, which parent observation IDs. The steward can accept the structural read, reject the narrative read, or accept both as distinct Perspectives. The reasons are preserved permanently.

This is the first time the architecture was exercised against genuinely different understandings of the same evidence. It did not fail. It produced exactly the kind of plurality the system was designed to preserve.

### For Experiment 002

Scope must be unambiguous. A single observation. One model at a time. Identical prompt across providers. The object under interpretation must not be in question.

Target observation: `e17a0861dbef5c372d0b77124057c0d22af65280af5d3caf6844880203d61f9e`  
Source locator: `page:3:block:3:sentence:1`  
Raw text: `n my younger and more vulnerable years my father gave me some advice that I've been turning over in my mind ever since.`
