# #251 / #252: merge order and readiness to make `proposal` the default

**Status:** 2026-10-13. Prepared for owner decision. Nothing is merged,
switched or deployed, and no issue is closed.

## Owner decisions recorded (2026-10-13)

| Decision | Status |
| --- | --- |
| **D1:** legacy-origin candidates reuse the P8 acceptance receipt | **approved** (#254, contract v1.1 §2 option (a)) |
| **G1:** WBS spec corrections | **approved** (#255, contract §2 and §9) |
| **D2:** Reader integration | **approved for an isolated branch and verification only**, not merging (this branch) |
| **G2:** one private-copy real-study validation | **approved and done** (`docs/verification/2026-10-13-g2-real-study-portability.md` on #255) |
| **D3:** `proposal` as the default | **deferred** |
| **G3:** open the P8 portability gate (chain export on by default) | **deferred** |

## Merge order

| Step | PR | Base | Why at this point |
| --- | --- | --- | --- |
| 1 | [#253](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/253): atomic writes, containment gate, exact references | `main` | Repairs R3 in every mode, including **P8 acceptance atomicity, a live defect on `main`**. It is additive: the default `legacy` keeps every success path |
| 2 | [#254](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/254): `proposal` mode | retarget to `main` after 1 | Server-side, non-default. Needs #253's gate |
| 3 | Reader integration (this branch) | retarget to `main` after 2 | Needs #254's routes. Without it, enabling `proposal` would misreport a held candidate as "Blueprint created" |
| 4 | [#255](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/255): gated chain portability and coverage audit | `main` (merge `main` in after 3) | Independent of #251, but merging it last activates its `#252 x #251` interplay test. Chain export stays gated |

**Merge mechanics, verified on scratch merges:**
- steps 3 and 4 both change `hermeneia/web/static/index.html`, in disjoint
  regions, and the merge is automatic;
- the owner's uncommitted `index.html` and navigation-test edits compose with
  the result in both directions;
- with them applied, only the 6 inherited Reader failures remain, and the
  navigation test passes.

Rebase or merge `main` into each PR before merging. Do not squash #254 into
#253: the separate commits keep the contract-first evidence readable.

## What making `proposal` the default (D3) would change

- **Model output.** "Generate Blueprint →" and onboarding extraction stop
  writing directly. Every model Blueprint needs an explicit Accept,
  Edit-and-accept or Discard. R1–R6 are closed for ordinary use.
- **Stale and placeholder outcomes.** A candidate built on evidence that
  later changes is refused as stale. Placeholder providers are refused
  (`NO_MODEL_EXECUTED`).
- **Existing data.** Existing `ai-generated` and `extracted` rows are
  untouched; their Lineage stays `unknown` and `derived`.

## Evidence held

| Requirement | Evidence |
| --- | --- |
| R1–R6 witnesses repaired in `proposal` | #254 witness matrix; strict xfails unchanged in `legacy` and `governed` |
| Exact acceptance, edits, discard, stale, no client substitution, CI-011 record, tamper detection | #254: 14 tests |
| The Reader inspects, accepts, edits, discards, blocks stale and expired candidates, and reports unsaved state | this branch: 15 Node UI tests, plus a replay of the Reader's own request bodies against the real routes |
| P8 unchanged | P8 tests and its three committed datasets reproduce on every branch |
| Receipts survive WBS when the chain gate is open | #255 interplay test; synthetic laboratory |
| Rollback | see below |

**Rollback, tested 2026-10-13.** Setting
`HERMENEIA_LEGACY_BLUEPRINT_WRITES=legacy` restores today's behavior.
Proposal-mode receipts stay valid under #254 code. Under **pre-#254 code**
(current `main`), a proposal-mode receipt is omitted from Lineage and its
Blueprint projects as `unknown`. It is never misattributed. A code rollback
below #254 is therefore safe, but it demotes displayed authorship until the
code returns.

## Evidence still missing before D3 (each needs owner authorization)

| ID | Missing evidence | Detail |
| --- | --- | --- |
| E1 | Refusal rate with a real local model | `proposal` and `governed` refuse inexact references that `legacy` silently dropped or rebound. How often a real model's reply is refused is **unknown**; no live model has been run against these routes. A bounded live diagnostic, like P8's, would measure it: frozen protocol, local model, synthetic studies, no acceptance |
| E2 | Browser review of the Reader surface | The UI tests run the real functions under Node with a fake DOM. A manual or in-app browser pass, in a synthetic workspace with a real candidate, has not been done |
| E3 | Real-data exercise | G2's real study holds **no** Interpretations or Blueprints, so proposal review has not met real chain data |
| E4 | Coupling with G3 | While the chain gate is closed, receipts created under `proposal` are **not** in default WBS bundles. They are declared in `manifest.not_exported` and on restore. Choosing D3 without G3 means newly accepted Blueprints and their provenance are local-only in backups. Decide D3 and G3 together, or accept that coupling explicitly |
| E5 | Competence | `proposal` proves provenance and the exact steward decision. Neither legacy generator has been evaluated for quality, and P8's GENERATION_NOT_READY finding still stands |

## Not affected by D3

- P8 generation stays gated (`BLUEPRINT_PROPOSAL_GENERATION`).
- `architect/import` keeps its legacy reference resolver (a human path,
  recorded in v1 §4).

## Integration verification (2026-10-13)

- **What was merged.** A scratch merge `f2a2872` of this branch (`706cb63`,
  which contains #253 and #254) with #255 (`f47b4ec`). It merged
  automatically. It is not pushed; it is evidence only.

| Run | Passed | Skipped | Failed | Expected failures |
| --- | --- | --- | --- | --- |
| Clean `main` `09b72cc` | 2913 | 21 | 6 | 0 |
| Integration merge | 2999 | 21 | 6 | 9 strict |

- **Failures.** The integration's failure set is **identical** to `main`'s:
  - `test_reader_accessibility` ×2;
  - `test_reader_blueprint_workstation`;
  - `test_reader_record_view` ×2;
  - `test_reader_voice_profile`.

  The skip set is identical as well.
- **Expected failures.** No unexpected pass occurred. The 9 strict xfails
  are:
  - R1, R2a, R2b, R5 and R6 in `legacy`, and R4 in `legacy` and `governed`,
    exactly as the contract's witness matrix states;
  - the two G2-found Observation-provenance witnesses.
- **Datasets.** Every offline dataset reproduces on the merge: P5, P6, P7
  (Layer 1, candidate, authored), P8 governance, P8 ceiling, P8 phi4-mini,
  and P10.
- **Later test.** `37883e5` (#255) was added after this run. It is
  test-only: the closed-gate interplay test. It passes on the merge, 2 of 2.

## Update (2026-10-15)

**Merge order is now five PRs, plus one independent PR:**
#253 → #254 → this branch (#256) → #255 →
[#257](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/257).

- **#257** repairs the provenance and index loss on WBS restore that G2
  found (`observation-compile-records-v1`, on by default). It is stacked on
  #255. New default bundles are refused by earlier restorers (its decision
  R1). The two G2 provenance witnesses now pass.
- **[#258](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/258)** is
  based on `main`, independent of the stack, and may merge at any point. It
  repairs the six inherited Reader failures. They were stale test pins, left
  behind by `8428ffe` and `f36328d`; no product code changed.

**Whole stack.** A scratch merge of this branch, #257 and #258 gives 3026
passed, 21 skipped, 7 strict xfails and **0 failed**. The 7 xfails are the
R-witnesses in `legacy` and `governed` only.

**Unchanged.** D3 and G3 are still deferred, and E1–E5 are still open.
