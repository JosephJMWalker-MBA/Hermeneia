# #215 P7 closeout — steward-authored structured comparison — 2026-10-08

**Result.** The steward-authored path, option (b), passes every completion
expectation frozen in
[the P7 disposition](../design/perspective-comparison-p7-disposition.md) §6
(`dde076e`). It was evaluated on the frozen synthetic corpus, with no model
called:

| Group | Passed |
| --- | --- |
| Authored references | 13/13 |
| Demonstrations | 2/2 |
| Refusals | 6/6 |
| Exclusion | 1/1 |
| Model gate | 1/1 |

## P7 disposition

**P7 v1 product capability:** structured Perspective comparison, built on a
deterministic substrate with a steward-governed durable structure.

```text
eligible retained Perspective receipts
→ deterministic Layer 1 (byte-identical since 43f7327)
→ steward-authored comparison structure
→ strict validation (the existing validator)
→ append-only accepted comparison (the existing record, Lineage, WBS and verifier)
```

**Experimental capability:** automatic semantic extraction.

- **Governance is ready:** zero defects in 92 live calls across four frozen
  configurations.
- **Extraction competence is not demonstrated:** neither
  `hermeneia-phi4-mini` nor `qwen2.5:7b-instruct` met the cross-Perspective
  gate under either policy.
- **Disabled and deferred:**
  - `POST /api/perspective/comparison/candidates` answers 403
    `SEMANTIC_EXTRACTION_DISABLED` unless the app is explicitly configured with
    `PERSPECTIVE_SEMANTIC_EXTRACTION = "experimental"`, or
    `HERMENEIA_SEMANTIC_EXTRACTION=experimental`;
  - only the evaluation laboratories enable it;
  - the implementation and all live evidence are preserved unchanged.

## What was built (`ae6d58b`)

### Two routes on the existing machinery

- **`GET /api/perspective/comparison/authoring-basis?receipt_id=…`:**
  - returns the exact binding a record will carry (receipt bytes, question,
    governing-question snapshot, Layer 1 digest), plus Layer 1 itself;
  - read-only, `no-store`, with Layer 1 refusals passed through.
- **`POST /api/perspective/comparison/authored`** with
  `{binding, structure: {participants, propositions, assumptions}}`:
  - **409 `STALE_INPUT`:** the same binding comparison as model acceptance;
  - **422:** the same strict validator as steward edits;
  - **201:** a new append-only record, `origin: steward_authored`,
    `decision: author`, `candidate: null`;
  - **200:** an idempotent resubmission returns the existing record.

### One provenance field

`origin.kind` takes one of:

- `model_proposed_steward_accepted`;
- `model_proposed_steward_edited`;
- `steward_authored`.

It must agree with the decision and the candidate. A contradictory origin is
refused even with a recomputed digest (tested). The schema is single, not
forked.

This amendment lands before merge; no record existed outside disposable tests.

## Completion evidence

The data is in `research/perspective_comparison_authored/v1/`. Each of the 13
frozen references was authored directly, and each reproduced its frozen
relations exactly:

| Behavior | Shown in |
| --- | --- |
| Agreement | C01, C12 |
| Disagreement | C03, C07, C10 |
| Same conclusion, different evidence | C02: agreement, reliance `disjoint` |
| Same evidence, different conclusion | C03: disagreement, reliance `identical` |
| Assumption difference | C05: two quoted assumptions, no relation |
| Wording-only paraphrase without false disagreement | C06: agreement W; R2's surface negation of `BEACON` creates no disagreement |
| A meaningful minority | C08: `minority_participants [R3]` |
| Legitimate unknowns | C08, C11 |
| No reliance established | C09: R2 asserts `SMUGGLE` with `reliance: []`; `relied_on []`, `supplied_not_relied_on [A:1]` |
| Explicit unknown (E1) | C11 with R2 authored `unknown`: kept without support; no relation manufactured |

### Checks on every authored record

- The basis is read-only and `no-store`.
- It is recorded as `steward_authored`.
- The stored bytes are canonical.
- Update, delete and replace are refused.
- An identical resubmission returns the same record.
- Lineage authorship is `human`, with origin `steward_authored`.
- Independent verification: `valid` / `verified` / `verified` /
  `not_applicable` / `preserved_not_replayed`.
- Export/restore keeps identical bytes and verifies identically.
- P1, P2 and P6 are unchanged before and after the record.
- No authority fields.

### Refusals

Each answers as frozen and records nothing:

| Scenario | Answer |
| --- | --- |
| Governing question changed after the basis was read | 409 `STALE_INPUT` |
| A participant's source excluded after the basis was read | 409 `STALE_INPUT` |
| Layer 1 digest altered | 409 `STALE_INPUT` |
| An untraceable span | 422 `STRUCTURE_UNTRACEABLE` |
| An authority key | 422 `STRUCTURE_INVALID` |
| A missing participant position | 422 `STRUCTURE_INVALID` |

### Exclusion after authoring (C08)

- Lineage omits the record, and GET returns 404.
- The record is preserved.
- Verification: `valid` / `verified` / `participants_not_eligible`.
- Export/restore keeps identical bytes.

### Model gate

On a default app, candidate generation answers 403
`SEMANTIC_EXTRACTION_DISABLED`, with no model call and no write.

## Tests

- P7 tests: 29 passed, of which 5 are new closeout tests. They cover:
  - dataset reproduction;
  - one origin field with three kinds matching the schema;
  - origin/decision/candidate agreement;
  - model-assisted records carrying the new kinds;
  - the gate defaulting to disabled.
- Full suite on a clean worktree of `ae6d58b`: 2878 passed, 21 skipped, 6
  failed. The six failures are exactly the inherited Reader failures. The
  extra passes are the 5 new closeout tests.
- On a clean worktree of the same commit, all five datasets reproduce
  exactly:
  - P5 synthetic study laboratory;
  - P6 Companion coach;
  - P7 Layer 1;
  - P7 Layer 2;
  - P7 closeout.

  That covers P5 and P6 behavior; P1, P2 and P6 are also checked per
  authored record.

## What P7 does not include

- a Reader or Companion UI for authoring or reviewing comparisons (API only);
- achievements;
- P8;
- any receipt-format change;
- any production use of model extraction.
