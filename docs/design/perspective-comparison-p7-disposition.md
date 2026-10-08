# P7 disposition and closeout amendment — steward-authored structured comparison

Date: 2026-10-08. Owner-directed. This amends the
[Layer 2 contract](perspective-comparison-layer2-v1.md). It was frozen before
any closeout code, on `p7-perspective-comparison` at `3bcdbe3`. It is part of
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215) P7.

## 1. Empirical conclusion (frozen)

> **Governance is demonstrated; current semantic extraction is not
> production-ready.**

There were 92 live calls across four frozen configurations:

- `hermeneia-phi4-mini` under v1 and v1.1;
- `qwen2.5:7b-instruct` under v1 and v1.1.

Governance produced **zero defects**. Neither tested model met the
cross-Perspective comparison gate:

| Configuration | Invariant (applicable runs) | Relation recall (all runs) |
| --- | --- | --- |
| phi4-mini, v1 | 0/18 | 0/18 |
| phi4-mini, v1.1 | 1/18 | 1/18 |
| qwen2.5-7b, v1 | 5/18 | 0/18 |
| qwen2.5-7b, v1.1 | 3/18 | 2/18 |
| Required | at least 9/18 | at least 5/18 |

The evidence is preserved unchanged:

- `research/perspective_comparison_live/v1/`, `v1.1/` and
  `qwen2.5-7b-instruct/`;
- the verification notes of 2026-10-08.

Provider-backed semantic extraction is therefore a **future optional
capability behind a competence gate**. It is not a requirement for P7 v1.

## 2. P7 v1 product capability

**Structured Perspective comparison, with a deterministic substrate and a
steward-governed durable structure.**

```text
eligible retained Perspective receipts
→ deterministic Layer 1 (unchanged)
→ steward-authored comparison structure
→ strict validation (the existing validator)
→ append-only accepted comparison (the existing record and machinery)
```

No model is called. Option (b) uses the **same** structure type, validator,
record, table, Lineage projection, WBS component and verifier as the model
path. There is no parallel representation.

## 3. Provenance: one origin field, three kinds, one schema

`origin.kind` in `hermeneia.accepted-perspective-comparison/v1` is amended
from `model_candidate | steward_authored` to the values below. Each kind must
agree with `acceptance.decision` and with `candidate`.

| `origin.kind` | `acceptance.decision` | `candidate` | Lineage authorship |
| --- | --- | --- | --- |
| `model_proposed_steward_accepted` | `accept` | the exact model candidate | `accepted_model` |
| `model_proposed_steward_edited` | `edit_and_accept` | the exact model candidate | `human` |
| `steward_authored` | `author` | `null` | `human` |

This is not a schema fork by origin; the schema stays single.

**Pre-merge amendment, disclosed.** The amendment lands before P7 is merged.
No accepted comparison exists outside disposable synthetic tests, so no
record is rewritten or migrated. Record identity, codec, triggers and replay
are unchanged except for the new enum values.

## 4. Steward-authored API (the smallest product boundary)

### Read-only basis

`GET /api/perspective/comparison/authoring-basis?receipt_id=…&receipt_id=…`

- Returns `{binding, layer1}`:
  - `binding` is the exact binding a record will carry: receipt bytes
    digests, the exact question, the governing-question snapshot, and the
    Layer 1 schema, policy, ID and digest;
  - `layer1` is the deterministic comparison: participants, exact responses,
    supplied evidence and relations.
- No store initialization, `no-store`, and Layer 1 refusals are passed through
  unchanged.

### Submit

`POST /api/perspective/comparison/authored` with exactly
`{"binding": <as reviewed>, "structure": {"participants", "propositions", "assumptions"}}`.

| Outcome | Status and code |
| --- | --- |
| Any bound input differs (receipt bytes, question, governing question, Layer 1 digest), including a participant that has become ineligible | 409 `STALE_INPUT`. This is the same binding comparison as model-assisted acceptance |
| The structure fails the strict validator | 422 `STRUCTURE_INVALID` or `STRUCTURE_UNTRACEABLE` |
| Valid | 201 with an append-only record: `origin: steward_authored`, `decision: author`, `candidate: null`. Relations are server-derived |
| An identical record (same binding and canonical structure) already exists | 200 with that record, never a duplicate |
| Any other body | 400 `INVALID_REQUEST` |

The strict validator is the one already used for steward edits. It requires:

- exact eligible receipt IDs in Layer 1 order;
- one position per participant, so every position is attributed;
- a span equal to the participant's response text for every `asserts`,
  `denies` or `unclassifiable` position;
- `does_not_address` and `unknown` with no span and no reliance;
- reliance only on units supplied to that participant.

It refuses any authority key and any authored `relations` or `untraceable`.
`reliance: []` means **no reliance established**. It is the canonical-structure
counterpart of the extraction wire's `relies_on: []`.

**Meaning.** An authored record means only *"the steward authored and accepted
this comparison structure."* It does not establish that any claim is true,
that the steward agrees with any Perspective, or that any disagreement is
resolved. No adjudication is inferred.

## 5. Disposition of the model routes

The smallest conforming disposition is a **configuration gate, disabled by
default.** Its scope:

- **Candidate generation:** `POST /api/perspective/comparison/candidates`
  answers 403 `SEMANTIC_EXTRACTION_DISABLED` before any input read or provider
  call. It runs only when the app is configured with
  `PERSPECTIVE_SEMANTIC_EXTRACTION = "experimental"`, either set on the app or
  via the environment variable
  `HERMENEIA_SEMANTIC_EXTRACTION=experimental`.
- **Who enables it:** only the evaluation laboratories and tests. The ordinary
  product flow never does. No Reader or Companion UI reaches these routes.
- **When enabled:** behavior is unchanged. Policy 1.0.0 candidates remain
  steward-reviewable for evaluation, and experimental 1.1.0 candidates remain
  non-accepting.
- **What is kept:** nothing is deleted. The implementation, its tests, the
  live harnesses (rerunnable with the environment variable) and all evidence
  stay.

This is configuration, not an ontology or authority change. It is reversible
by configuration once a future competence gate is passed.

## 6. Completion evidence (expectations frozen here)

### Authored structures

For each of the 13 compared Layer 1 cases, the steward authors the case's
**frozen reference annotation** directly through the API. Every case must
reproduce the frozen reference relations exactly, including:

| Behavior | Case |
| --- | --- |
| Agreement | C01, C12 |
| Disagreement | C03, C07, C10 |
| Same conclusion, different evidence (agreement with reliance `disjoint`) | C02 |
| Same evidence, different conclusion (disagreement with reliance `identical`) | C03 |
| Assumption difference (two quoted assumptions, no relation) | C05 |
| Wording-only paraphrase with no false disagreement (agreement W; `BEACON` denied only by R2, so no disagreement) | C06 |
| A meaningful minority (`minority_participants = [R3]`) | C08 |
| Legitimate unknowns (`unclassifiable`) | C08, C11 |
| No reliance established (`reliance: []` on an asserted position) | C09 `SMUGGLE` |

Two demonstrations go beyond the references:

- **E1 explicit unknown:** C11 with R2 authored as `unknown` (no span). It
  appears in `unknown_positions` with stance `unknown`, and nothing is
  untraceable.
- **E2 no reliance established:** C09's `SMUGGLE`, R2 `asserts` with
  `reliance: []`. R2's `evidence_use.relied_on` is `[]`, and its supplied unit
  appears under `supplied_not_relied_on`.

### Checks for every authored record

- 201, origin `steward_authored`, decision `author`, `candidate: null`;
- stored bytes equal the canonical record;
- update, delete and replace are refused;
- an identical resubmission returns 200 with the same record;
- Lineage `accepted_perspective_comparison` with authorship `human` and origin
  `steward_authored`;
- independent verification: integrity `valid`, closure `verified`, Layer 1
  replay `verified`, candidate replay `not_applicable`;
- export/restore preserves the exact row bytes and verifies identically;
- the P1 capability evaluation is identical before and after.

### Refusals

| Scenario | Expected |
| --- | --- |
| Governing question changed after the basis was read | 409 `STALE_INPUT`, 0 records |
| A participant's source excluded after the basis was read | 409 `STALE_INPUT`, 0 records |
| A binding whose Layer 1 digest was altered | 409 `STALE_INPUT`, 0 records |
| An untraceable span | 422 `STRUCTURE_UNTRACEABLE`, 0 records |
| A position carrying an authority key | 422 `STRUCTURE_INVALID`, 0 records |
| A position missing for one participant | 422 `STRUCTURE_INVALID`, 0 records |

### Exclusion after authoring (C08)

- Lineage omits the record, and `GET` returns 404.
- Verification: integrity `valid`, closure `verified`, Layer 1 replay
  `participants_not_eligible`.
- Export/restore preserves the record's bytes.

### Model gate

On a default app, the candidate route answers 403
`SEMANTIC_EXTRACTION_DISABLED`, with no provider call and no write.

### Regressions

The P5, P6, P7 Layer 1 and P7 Layer 2 datasets reproduce unchanged.

## 7. Not in this closeout

- no further model run;
- no prompt or policy tuning;
- no Reader or Companion UI;
- no achievements;
- no P8;
- no receipt-format change;
- no deletion of experimental code or evidence.
