# #252 P10 Blueprint dependency chain portability — 2026-10-13

**Status:** branch `p10-blueprint-chain-portability` from `main` `09b72cc`.

- Nothing is merged.
- Chain export is **gated and off by default**, and the P8 portability gate
  stays closed.
- No real workspace was opened.

**Result:** the Blueprint dependency chain round-trips through WBS with its
closure intact, or it is explicitly declared unsupported. It is never
partial, fabricated or relabelled. All #252 criteria 1–7 are evidenced on
synthetic studies. Criterion 8's private-copy validation and criterion 9's
gate decision belong to the owner.

## Sequence

| Commit | Step |
| --- | --- |
| `3cad6c3` | Contract frozen first (`docs/design/blueprint-chain-portability-v1.md`), with the inventory of actual WBS coverage |
| `2771ffb` | **Amendment 1**, found during implementation: chain export is gated, default off |
| `709c606` | Component, export and restore integration, web gate, spec §6/§6.2/§6.3, laboratory, dataset, tests |

## Inventory finding (main `09b72cc`)

- **No chain table is exported.** The spec's `interpretations` row was
  never implemented.
- **Three more §6 rows** are also not written by any exporter, and are
  outside #252's scope:
  - `study/reviews.json` (`observation_reviews`, `inquiry_notes`);
  - `reports/*` (rendered narratives, critic reports);
  - `reports/governance.json`.

  The spec now says so (§6.3). As a consequence, P1 `preserve_question` does
  not survive WBS today.

## Amendment 1: why export is gated

Exporting the chain unconditionally made every fresh export report P8
acceptance history `covered`. Two P8 tests and P8's committed governance
dataset failed, because they pin the disposition's obligation that the
history stays "declared unsupported by WBS until the gate passes".

#252 criterion 9 reserves opening that gate for the owner. So chain export is
an explicit option:
- the web setting is `WBS_BLUEPRINT_CHAIN`, default `disabled`, enabled with
  `HERMENEIA_WBS_BLUEPRINT_CHAIN=enabled`;
- disabled, bundles are byte-identical to before;
- restore always understands the component.

With the gate: P8's tests pass unchanged, and its dataset reproduces.

## Evidence (`research/blueprint_chain_portability/v1`)

The laboratory builds studies through production routes: E10 generate,
accept and reject; ratify and revise; P8 propose and accept; legacy generate
and extract-save; exclusion. It exports with the chain enabled, restores into
a fresh target, and compares.

| Kind | Cases | Result |
| --- | --- | --- |
| Lawful round trips (L1–L8) | 8 | each passes 9 of 9 checks |
| Gate-off bundle (L9) | 1 | WBS 1.x-shaped; chain `unsupported`; nothing reconstructed |
| Export adversarial (A1–A3) | 3 | declared `CHAIN_INTEGRITY_INVALID`, `CHAIN_CLOSURE_INCOMPLETE` and `CHAIN_SUPERSESSION_OUT_OF_SCOPE`; no chain file; the rest exported; restore reports the reason |
| Restore adversarial (A4–A12, A5b) | 10 | each refused, with nothing restored |

The nine lawful checks are:
1. a deterministic double export;
2. the source is unchanged by export;
3. the capability is declared;
4. coverage is `covered`;
5. counts are declared;
6. chain rows are identical;
7. Lineage chain items are identical;
8. P1 decisions are identical;
9. receipt verdicts are identical.

The restore-adversarial refusals:

| Stage | Cases |
| --- | --- |
| `read_bundle`, before any write | edited without rehash; capability without file; file without capability; count mismatch; duplicate key; unknown column; contradictory declaration |
| Restore transaction | rehashed bundles with a removed Blueprint (refused by the supersession endpoint trigger) or a removed plan (refused by chain closure) |
| Occupied target | refused even with `overwrite=True`; target unchanged |

**Authorship survives exactly.** It is recomputed by Lineage, never copied:
- accepted E10 Interpretation → `accepted_model`;
- P8 exact acceptance → `accepted_model`;
- P8 edit → `human`;
- legacy `ai-generated` → `unknown`;
- `extracted` → `derived`;
- Blueprint edges → `unknown`, as in the source.

Both P8 receipts verify identically after restore (`valid`, `verified`,
`verified`).

## Tests

- `tests/test_blueprint_chain_portability.py`: 7 tests.
  - the dataset reproduces, and every case meets the contract;
  - a default export is unchanged and keeps P8's declaration and reason;
  - the web gate is off by default and opens only through configuration;
  - the restorer supports the capability;
  - an unmigrated schema is declared, not narrowed;
  - an empty current store exports a covered empty chain.
- Neighboring suites (WBS export and restore, Perspective execution, award
  and hybrid WBS, P8, Lineage, P1, comparisons): 294 passed.
- The P8 governance dataset reproduces.
- **Full suite** (clean detached worktree of `709c606`):
  2920 passed, 21 skipped, 6 failed.
  - **Failures:** exactly the inherited Reader baseline:
    - `test_reader_accessibility` ×2;
    - `test_reader_blueprint_workstation`;
    - `test_reader_record_view` ×2;
    - `test_reader_voice_profile`.
  - **Passes:** `main` `09b72cc` had 2913. The 7 extra passes are this
    packet's tests.
- **Interplay with #254 (scratch merge only, not committed).**
  - The `r251-proposal-mode` + P10 merge has no conflicts.
  - A `proposal`-mode legacy-origin receipt is covered by chain export and
    restored, then verifies `valid`, `verified`, `verified`.
  - The #251, P8 and P10 suites pass together (67 passed, 7 xfailed).

## Not demonstrated

- **Real-workspace validation** (#252 criterion 8, last bullet). It needs owner
  authorization for one private-copy run.
- **Uncovered surfaces.** Portability of `observation_reviews`,
  `inquiry_notes`, rendered narratives, critic reports and governance
  records. They are out of scope, now declared in the spec but not yet in
  restore coverage.
- **Legacy-origin receipts** (#254, unmerged). On this branch alone they
  would be declared `CHAIN_INTEGRITY_INVALID`. Merged with #254, they are
  covered; the scratch merge above observed this.

## Decisions requested

| Decision | Question |
| --- | --- |
| **G1** | Confirm the recorded spec correction: three canonical files replace the single "machine / authored-on-adopt" row |
| **G2** | Authorize, or decline, one private-copy validation on a real study (criterion 8) |
| **G3** | After G1–G2: open the P8 portability gate, that is, enable chain export by default (criterion 9). This does not clear P8's other release blockers |
