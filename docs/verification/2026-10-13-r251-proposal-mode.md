# #251 v1.1 `proposal` mode — 2026-10-13

**Status:** branch `r251-proposal-mode`, stacked on
`r251-legacy-blueprint-remediation` `d38fdbc` (draft PR #253). Nothing is
merged, the default is unchanged (`legacy`), P8 generation stays gated, and
no Reader change is applied.

**Result:** a non-default mode in which the legacy model-to-Blueprint
generators can no longer write canonical state. Their output reaches
canonical state only through an exact steward decision on the exact held
candidate, and the P8 acceptance receipt carries its CI-011 record.

In this mode all six #251 risks are repaired, including **R4**, which every
v1 mode that kept generation left exposed.

## Sequence

| Commit | Step |
| --- | --- |
| `1ecb18f` | Contract v1.1 frozen first (`docs/design/r251-legacy-blueprint-remediation-v1.1.md`). Golden legacy prompt captured twice, byte-identical, from the unmodified route at `d38fdbc` |
| `68b90b0` | Implementation, witnesses (`proposal` column), 14 tests |
| `abfd794` | Isolated, unapplied Reader patch, `docs/design/r251/reader-proposal-mode.patch` |

## What was observed

- **Prompt identity.** The legacy Architect prompt is byte-identical to the
  golden capture in `legacy`, `governed` and `proposal`. The golden study
  has 55 Observations (40 shown), a non-primary document, and 3
  Interpretations, one of them on an unshown Observation. The f-string moved
  verbatim; the exact-reference resolver moved unchanged.
- **Generation writes nothing.** The workspace's logical dump is unchanged
  after `proposal`-mode generation. The candidate binds:
  - the directive or source text (complete input);
  - every shown record, with P8's digests;
  - the exact prompt (plus the system prompt for extract);
  - the recorded execution: `execution_config()`, provider ID, adapter,
    and, for extract, the interface, model and `max_tokens` actually sent;
  - timestamps;
  - the raw output.
- **Exact acceptance**, through the unchanged P8 route:
  - it commits the held proposal byte for byte;
  - the Blueprint is `proposal-accepted`, the plan is compiled, and one
    receipt is written;
  - `verify_blueprint_proposal_acceptance` gives `valid`, `verified`,
    `verified` and `preserved_not_replayed`;
  - Lineage authorship is `accepted_model`;
  - a repeat decision is idempotent.
- **Edit-and-accept** gives `proposal-edited` and Lineage `human`. The
  model's proposal is preserved in the receipt.
- **Discard** leaves no history. An accept naming a body Blueprint is
  refused (400), so no client substitution is possible. Unknown or discarded
  candidates give 404.
- **Stale.** Excluding the source after generation gives 409
  `STALE_CANDIDATE`, and nothing is written.
- **Extract.**
  - the preview is the candidate, and `save: true` gives 409;
  - acceptance commits "Previewed proposal", the reviewed content, after
    exactly one model call;
  - the receipt replays.
- **Refusals hold nothing and write nothing:**
  - the null provider gives `NO_MODEL_EXECUTED`, and render is never called;
  - a provider with no execution record gives `EXECUTION_NOT_RECORDABLE`;
  - inexact references give 422 `BLUEPRINT_REFERENCE_INVALID`, itemized;
  - unparseable output gives 422, with the raw output returned;
  - a provider failure gives 502, with no traceback;
  - an extract placeholder or an anonymous model is refused.
- **Tamper detection.**
  - A receipt with altered execution bytes fails `record_integrity`.
    Lineage then omits it, and its Blueprint projects as `unknown`.
  - A rewritten bound Observation makes `candidate_replay` a `mismatch`.
- **P8 is unchanged:**
  - P8 candidate-ID bytes are identical (unit-tested);
  - `test_blueprint_proposals.py` and the live-protocol tests pass (35);
  - the governance (`research/blueprint_proposal/v1`), live-ceiling and
    live phi4-mini datasets reproduce exactly.

## Witness matrix (`tests/test_r251_legacy_blueprint_witnesses.py`)

| Risk | `legacy` (default) | `governed` | `proposal` | `disabled` |
| --- | --- | --- | --- | --- |
| R1 unresolved loss | exposed (strict xfail) | repaired | repaired | repaired |
| R2a wrong-type binding | exposed | repaired | repaired | repaired |
| R2b unshown binding | exposed | repaired | repaired | repaired |
| R3 non-atomic | repaired | repaired | repaired | repaired |
| R4 model-direct write | exposed | exposed | **repaired** | repaired |
| R5 unreviewed resample | exposed at the route | repaired | **repaired** | repaired |
| R6 placeholder commit | exposed but labelled | repaired | repaired | repaired |

v1's strict markers are unchanged: the same 7 expected failures.

## Reader compatibility

- **The current Reader cannot use `proposal`.** On any 2xx, "Generate
  Blueprint →" reports "Blueprint created", so it would misreport a held
  candidate. Onboarding "Ratify & Save" is refused.
- **The unapplied patch fixes both.** It is stacked on v1's onboarding
  patch:
  - the Architect panel says "Model proposal — nothing saved yet", shows
    cited labels and the proposing model, and offers Accept exactly or
    Discard;
  - onboarding accepts the held candidate behind its preview.
- **Patch evidence:**
  - both patches apply in sequence to `main`'s `index.html` and to a copy
    of the owner's working copy;
  - its UI test passes 7 of 7 patched and fails 6 of 7 unpatched (the
    seventh pins the unchanged legacy message);
  - with both patches, the Reader suites show only the 6 inherited
    failures (343 passed).
- The owner's `index.html` and navigation test are byte-identical
  throughout (SHA-256 `906ed4d7…` and `90e3b31e…`).

## Verification (clean detached worktree of `68b90b0`)

- **Full suite:** 2964 passed, 21 skipped, 7 xfailed, 6 failed.
  - **Failures:** exactly the inherited Reader baseline:
    - `test_reader_accessibility` ×2;
    - `test_reader_blueprint_workstation`;
    - `test_reader_record_view` ×2;
    - `test_reader_voice_profile`.
  - **Passes:** the checkpoint `d38fdbc` re-ran today at 2942. The 22 extra
    passes are the 14 new tests and 8 new witness and containment
    parameters.
- **Datasets:** P5, P6 and P7 reproduce in the full suite; P8 governance,
  ceiling and phi4-mini were checked directly.
- **Isolation:** synthetic workspaces only, under P5 isolation (sockets
  blocked); in-process fake providers. No real workspace, no live model, no
  network.

## What this does not demonstrate

- **Competence.** That either legacy generator produces good or supported
  Blueprints; neither has been evaluated. A receipt proves provenance and
  the exact steward decision, not quality. P8's GENERATION_NOT_READY
  finding is untouched.
- **Old code.** Behavior under code without this change. By inspection,
  `main` would reject a legacy-origin receipt as invalid, so Lineage omits it
  and the Blueprint projects as `unknown`, never misattributed. It is not
  executed here.
- **Portability.** Receipts share P8's WBS `unsupported` declaration until
  #252.
- **`architect/import`.** It still uses the legacy digit resolver. It is a
  human import, outside the model path, and left unchanged per v1 §4.

## Decisions requested (smallest first)

| Decision | Question |
| --- | --- |
| **D1** | Accept option (a): legacy-generated provenance reuses the P8 acceptance receipt, through two candidate schemas (contract v1.1 §2). Alternatives (b)–(d) are documented there |
| **D2** | Integrate the two Reader patches: onboarding (v1) and proposal mode (v1.1) |
| **D3** | After D2, whether to move the default from `legacy` to `proposal`. That would close R1–R6 for ordinary use while keeping model drafting, and it would meet #251's first closure criterion for these routes |
