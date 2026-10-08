# #215 P7 Layer 2 — governed structured-comparison candidates — 2026-10-08

**Result.** Option (a) is implemented as a governed path across the Layer 1
boundary:

```text
eligible retained receipts
→ Layer 1 (unchanged)
→ semantic extraction proposal
→ traced candidate
→ steward accept / edit-and-accept / discard
→ append-only accepted comparison
```

The pipeline met every frozen expectation on the synthetic corpus, using
in-process fake providers only:

- **13/13 faithful cases:** the candidate's derived relations reproduce the
  frozen reference. That covers agreement, disagreement, same conclusion with
  different evidence, same evidence with a different conclusion, assumptions,
  wording-only difference, the 2-to-1 minority, the unsupported assertion and
  legitimate unknowns.
- **2/2 Layer 1 refusals:** refused before any model call.
- **10/10 adversarial scripts:** each produced its frozen governance outcome
  and its frozen score.
- **9/9 steward-acceptance scenarios** passed.

**What this measures.** These are scripted outputs, so the evaluation
measures the governed pipeline, not a model's extraction quality.
Establishing real extraction quality needs a live local model. That requires
your separate authorization, and no model was called.

## Provenance

- **Branch:** `p7-perspective-comparison`.
  - Layer 1: `5ce3bec` (contract), `43f7327` (implementation), `9027af7`
    (verification note).
  - Layer 2: contract frozen at `e3e7180` before any provider, candidate or
    storage code.
- **Layer 1 is intact.** `hermeneia/perspective_comparison.py` is
  byte-identical to `43f7327` (SHA-256 `81f76b1a…cedb8`, pinned by a test).
  Its lab, tests, fixtures and dataset are unchanged, and its 10 tests still
  pass.
- **Production code:**
  - `hermeneia/perspective_comparison_candidates.py`:
    - the comparison view, built from Layer 1 or from bound receipts;
    - the prompt `perspective-comparison-extraction/v1`;
    - strict output parsing and traceability normalization;
    - derived relations and strict steward-structure validation;
    - the candidate.
  - `hermeneia/accepted_perspective_comparisons.py`:
    - the record codec and identity;
    - the append-only table and triggers;
    - receipt closure and read-only verification.
  - `hermeneia/storage/sqlite.py`: schema 20, through the existing startup
    initializer.
  - `hermeneia/study_lineage.py`: the new `accepted_perspective_comparison`
    record type.
  - `hermeneia/capabilities.py`: accepted comparisons are excluded from P1/P2
    exactly as award receipts are.
  - `hermeneia/workspace/export.py` and `hermeneia/workspace/restore.py`: the
    `accepted-perspective-comparison-v1` component.
  - `hermeneia/web/app.py`: four routes — propose, accept / edit-and-accept,
    discard, and read accepted.
- **Unchanged:** P3 receipts, `perspective-run/v1` and E(r); P4 rules and
  awards; P5/P6 semantics and datasets.

## What the governance layer guarantees, and what it cannot

| Temptation (adversarial script) | Governance outcome | Visible in score |
| --- | --- | --- |
| Majority turned into truth (top-level `consensus` / `majority` / `verdict`; nested `truth`) | whole output refused, `EXTRACTION_OUTPUT_AUTHORITY_FIELD`; no candidate | — |
| Prose instead of the contract; invented stance | refused, `UNPARSEABLE` / `CONTRACT_VIOLATION` | — |
| Claim attributed to the wrong participant | both quotes fail to resolve in the attributed response; the positions become `unknown` and the proposition is removed | disagreement lost (fn 1): an honest unknown, not a manufactured agreement |
| Minority erased by omitting the dissenter | the omitted position becomes `unknown`; the agreement carries `not_established_for: [R3]` | agreement fp 1, disagreement fn 1, minority not preserved |
| Fabricated assumption | the untraceable assumption is dropped | — |
| A traced quote that is not an assumption | admitted | assumptions fp 1 |
| Reliance on a unit not supplied | dropped | — |
| Reliance on every supplied unit | admitted (traceable) | reliance fp 5 |
| **Paraphrase called disagreement** | admitted (both quotes are real) | disagreement fp 1, agreement fn 1 |
| **Minority erased by calling the dissenter silent** | admitted (`does_not_address` needs no quote) | agreement fp 1, disagreement fn 1, minority not preserved |

### What traceability catches

- fabrication;
- misattribution;
- out-of-scope reliance;
- authority claims;
- contract violations.

### What it cannot catch

A real quote with a wrong interpretation:

- a paraphrase read as a denial;
- a silent dissenter;
- over-claimed reliance;
- a misread assumption.

These pass governance. The extraction score and the steward show them.
Scenario ACC2 shows a steward edit-and-accept repairing the paraphrase
candidate back to the reference: the candidate records 1 disagreement, the
accepted structure records 1 agreement, and both are preserved.

### What holds regardless of the model

Relations are never taken from the model. Agreement, disagreement, minority,
unresolved and evidence use are recomputed from traced positions. No field
anywhere names a majority, consensus, winner, truth or verdict.

## Steward acceptance (measured separately from extraction)

| Scenario | Observed |
| --- | --- |
| ACC1 exact accept, C08 | 201, then a repeat returns 200 with the same record. Lineage authorship `accepted_model`. Accepted structure = candidate structure. All four verification dimensions verified; model output `preserved_not_replayed`. Export/restore preserves the exact row bytes and re-verifies identically |
| ACC2 edit-and-accept, C06 | 201. Lineage `human`. The candidate (1 disagreement) and the accepted structure (1 agreement) are both preserved; all dimensions verified |
| ACC3 discard | 200. A later accept returns 404 `UNKNOWN_CANDIDATE`; 0 records |
| ACC4 governing question changed | 409 `STALE_CANDIDATE`; 0 records |
| ACC5 participant source excluded | 409 `STALE_CANDIDATE`; 0 records |
| ACC6 wrong reviewed ID | 409 `CANDIDATE_MISMATCH`; 0 records |
| ACC7 untraceable edit | 422 `STRUCTURE_UNTRACEABLE`; 0 records |
| ACC8 authority field in an edit | 422 `STRUCTURE_INVALID`; 0 records |
| ACC9 source excluded after acceptance | The record stays (append-only). Lineage omits it and GET returns 404. Verification: integrity, closure and candidate replay verified; Layer 1 replay `participants_not_eligible`. Export/restore preserves its bytes |

## Durable record (completion gate items 4–5)

`accepted_perspective_comparisons`, schema `hermeneia.accepted-perspective-comparison/v1`.

- **Identity:** a domain-separated SHA-256 digest of the canonical record.
- **Immutability:** triggers refuse UPDATE, DELETE and REPLACE (tested).
- **Candidate binding:** `candidate_id` is unique, so one candidate yields at
  most one record.

The record binds:

- the exact receipt bytes (`receipt_sha256`), response and Scope digests;
- the exact execution question;
- the governing-question snapshot;
- the Layer 1 digest;
- the candidate's full extraction: policy, prompt version, exact prompt,
  execution, times, exact raw output and the normalized structure;
- the accepted structure and its digest;
- the acceptance: decision, `local_steward` with unknown identity, time, the
  reviewed candidate ID, and the fixed meaning ("…does not establish that any
  claim is true, that the steward agrees with any Perspective, or that any
  disagreement is resolved").

**Reconstructability.** `verify_accepted_comparison` recomputes the following
from the bound receipts and the stored structures. It never calls the model.

- receipt closure;
- every span and reliance unit;
- every derived relation;
- Layer 1;
- the exact prompt, from canonical unit texts;
- the normalized candidate, by re-normalizing the preserved raw output.

**Tamper evidence (tested).** An altered row is omitted by Lineage with
diagnostic `ACCEPTED_COMPARISON_INVALID` and verifies as `invalid`.

**Restore (tested).**

- A tampered component, or a component whose receipts are missing, refuses
  the whole restore and installs nothing.
- An old bundle without the component reports coverage `unsupported`.

**Option (b).** A steward-authored record (`origin: steward_authored`,
`decision: author`) is built from the same structure type through the same
strict validator. It projects as `human` and verifies with `candidate_replay:
not_applicable` (tested). No authoring route is added.

**Option (c).** Recorded in the contract (§8) as a future receipt version
only. No receipt contract changed.

**P1/P2.** A capability evaluation before and after an acceptance is identical
(tested).

## Corrections and clarifications after the contract freeze

1. **N2 Layer 1 refusal through the app** (the frozen corpus entry is
   corrected and annotated). Through the app, P3's documented startup
   initializer re-creates an empty receipt table before any request. A legacy
   workspace without the table therefore refuses with `INELIGIBLE_RECEIPT`.
   The read-only Layer 1 path still reports `COVERAGE_UNSUPPORTED`. Either way
   nothing is proposed and no model is called (a check was added).

   This is the existing P3 limitation that an app-migrated legacy workspace
   cannot report unsupported receipt coverage. It is not a Layer 2 defect, and
   it was not repaired.
2. **Canonical form of an edit.** The accepted edited structure is the
   canonical form of the steward's edit: positions in participant order and
   reliance sorted by table and ID. Its content is otherwise exactly what the
   steward supplied.
3. **Unreached verification dimensions.** These are reported as `unverified`.
   For example, when record integrity fails, the later dimensions are not
   attempted.
4. **Aggregate split.** The lab's adversarial aggregate now separates the
   governance outcome (`refused`, `downgraded_to_unknown`, `admitted`) from
   whether the score deviates. Merely downgraded cases were not claimed as
   fully caught.

No decision rule, derived-relation rule, frozen score or other expectation
changed.

## Tests

- `tests/test_perspective_comparison_candidates.py`: 10 passed.
- Layer 1 `tests/test_perspective_comparison.py`: 10 passed, unchanged.
- Seven existing tests pinned schema 19 or the exact WBS capability set. They
  were advanced to schema 20 and `accepted-perspective-comparison-v1`, as P3
  and P4 did for their tables. No other assertion changed.
- Full suite on a clean worktree of `aabe0f0`: 2869 passed, 21 skipped, 6
  failed. The six failures are exactly the inherited Reader failures:
  - `test_reader_accessibility` ×2;
  - `test_reader_blueprint_workstation`;
  - `test_reader_record_view` ×2;
  - `test_reader_voice_profile`.

  No new failure was introduced: 2859 passed before Layer 2, plus 10 new
  tests.
- On the same clean worktree, the P5, P6, P7 Layer 1 and P7 Layer 2 datasets
  all reproduce exactly.

## Not demonstrated

- **Real extraction quality.** Every model output was scripted. How often a
  real local model proposes faithful structure, and how often it falls into
  the paraphrase or silent-minority traps that only scoring and the steward
  can catch, is unknown. **Measuring it requires authorization to call a live
  local model.**
- **Reader or Companion UI.** There is no steward review UI. The API is
  complete; the workstation surface is not built.
- **Awards.** No P7 awards (Dissent Finder, Evidence Split, and others) are
  issued and no award semantics changed. Accepted comparisons are the evidence
  substrate those awards would cite.
- **Real study and later packets.** The real study was not used. No P8 or P9
  work.
