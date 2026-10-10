# #251 R-P8-LEGACY-1 bounded remediation — 2026-10-10

**Status:** local branch `r251-legacy-blueprint-remediation`, based on `main`
`09b72cc`. Not pushed or merged, and nothing is enabled by default.

The contract was frozen first (`1729b59`,
`docs/design/r251-legacy-blueprint-remediation-v1.md`). The P10 portability
obligation is now a dedicated issue, #252, with frozen scope and acceptance
criteria; no portability change was made.

## Sequence

| Commit | Step |
| --- | --- |
| `1729b59` | Remediation contract frozen |
| `4699748` | R1–R6 promoted into permanent negative witnesses: 7 strict expected failures, each restricted to its own `AssertionError` subclass, keeping the exact evidence from #251 |
| `a4bb155` | Three more R3 witnesses for non-atomic steward ratification and P8 acceptance, found while repairing R3 (below) |
| `7a403db` | R3 repaired in every configuration. All four R3 witnesses showed strict unexpected passes (`XPASS(strict)`) before their markers were removed |
| `0815030` | Containment gate `LEGACY_BLUEPRINT_WRITES` (`legacy` default, `governed`, `disabled`; unrecognized values fail closed); exact references; additive provider labels |
| `40c712d` | Isolated, unapplied Reader patch for exact onboarding ratification, `docs/design/r251/reader-onboarding-exact-ratify.patch` |

**Order note.** The contract follows the requested order (exact approval,
references, atomicity, provenance, containment). Implementation landed R3
first, because it was the only repair safe to enable by default. The
remaining server work landed in one gated commit.

## Witness matrix (`tests/test_r251_legacy_blueprint_witnesses.py`)

| Risk | `legacy` (default) | `governed` | `disabled` |
| --- | --- | --- | --- |
| R1 unresolved-reference loss | exposed (strict xfail) | repaired | repaired |
| R2a wrong-type binding | exposed | repaired | repaired |
| R2b unshown-record binding | exposed | repaired | repaired |
| R3 non-atomic generate | **repaired** | repaired | repaired |
| R3 non-atomic steward ratification | **repaired** | — | — |
| R3 non-atomic P8 acceptance (receipt, plan) | **repaired** | — | — |
| R4 model-direct write | exposed | exposed | repaired |
| R5 unreviewed resample | exposed at the route; the Reader closes it once the patch is integrated | repaired | repaired |
| R6 placeholder commit | exposed, but every extract response is now labelled | repaired | repaired |

This matches contract §8 exactly. `tests/test_r251_legacy_blueprint_containment.py`
adds 12 tests:
- **Gate defaults:** `legacy` by default; fail-closed on unknown values.
- **The full governed reference taxonomy:** `wrong_type`, `unshown`,
  `ambiguous`, `excluded`, `unknown`, `unresolved`, numbered as the model
  returned its sections.
- **Valid references:** exact references write identically under `legacy` and
  `governed`.
- **`disabled` mode:**
  - it stops generation before any provider call;
  - preview and exact ratification stay available.
- **Labels:** extract responses say whether a model ran, in every mode.
- **Extractor:** `provider_interface()` is the extractor's branch selector.

## Found during R3: P8 acceptance was not atomic

`ensure_architect_tables()` commits through `executescript()`. It ran after
the Blueprint and links were written in two places:
- in `/api/architect/generate`, which also committed explicitly there;
- inside the shared `_persist_exact_blueprint_and_compile`.

So a later failure left a committed Blueprint without its plan, or without
its receipt, in these routes:
- `/api/architect/generate`;
- steward `/api/pipeline/ratify-blueprint`;
- `extract-blueprint save:true`;
- `/api/architect/import`;
- **P8 acceptance**, where the failure would leave a `proposal-accepted`
  Blueprint with no receipt, which Lineage projects as `unknown`.

This contradicts P8 contract invariant 8, which was never tested under
injected failure. The fix leaves the shared DDL helper untouched:
- the table check runs before the first write;
- it never runs inside a caller-owned transaction (P8 acceptance already
  ensures the tables before `BEGIN IMMEDIATE`);
- `architect/generate` rolls back on failure.

The correction is recorded in `blueprint-proposal-p8-disposition.md` §4. `main`
carries the defect until this branch merges.

## Compatibility

**Default `legacy`:**
- every existing route test passes unchanged;
- the P8 governance dataset reproduces;
- the only observable differences are that a failure no longer leaves
  partial rows (R3), and that extract responses carry a new `execution`
  field.

**User-facing changes, implemented but not enabled:**

| Change | Who sees it |
| --- | --- |
| `governed`: inexact references → 422 `BLUEPRINT_REFERENCE_INVALID` | Reader "Generate Blueprint →" users. Model replies that today persist with silent reference loss or wrong bindings would refuse and need regeneration. The refusal rate is unknown without a live model |
| `governed`: `extract-blueprint save:true` → 409 `EXACT_RATIFICATION_REQUIRED` | The **current** onboarding "Ratify & Save" button would break until the Reader patch is integrated |
| `governed`: placeholder output → 409 `NO_MODEL_EXECUTED` | Onboarding users with no configured provider (the UI falls back to `null`) would see a refusal instead of a canned Blueprint |
| `disabled`: `architect/generate` → 403 | The Reader loses model Blueprint generation until P8 propose-and-review is enabled, which is itself release-gated |

**Reader patch (unapplied):**
- **Change.** "Ratify & Save" posts the exact displayed proposal to
  `ratify-blueprint`, and placeholders get no ratify button.
- **UI test.** 4 failures on the unpatched page, 4 passes on the patched one.
- **Reader and Blueprint suites with the patch:** only the 6 inherited
  failures.
- **Applicability.** `git apply --check` succeeds against `main` and against
  the owner's working copy. The owner's `index.html` and navigation test were
  verified byte-identical before and after every step.

## Verification (clean detached worktree of `40c712d`)

- **Full suite.** 2942 passed, 21 skipped, 7 xfailed, 6 failed.
  - **Failures.** Exactly the inherited Reader baseline; each was re-run by ID
    and fails:
    - `test_reader_accessibility` ×2;
    - `test_reader_blueprint_workstation`;
    - `test_reader_record_view` ×2;
    - `test_reader_voice_profile`.
  - **Expected failures.** The 7 are the risks still exposed, in the
    configurations where contract §8 says so.
  - **Passes.** `main` `09b72cc` had 2913. The 29 extra passes are 17 passing
    witness parameters and 12 containment tests.
- **Datasets.** Every committed dataset reproduces exactly: P8 governance, P8
  live ceiling, P8 live phi4-mini, P7 steward-authored, P7 Layer 2, P7
  Layer 1, P6 and P5.
- **Real use.** No real workspace was opened; no live model and no network
  were used.

## Smallest remaining decision

Approve integrating the Reader patch. It is the precondition for any
non-`legacy` default, because `governed` would otherwise break the current
"Ratify & Save" button. After that, decide whether the default moves from
`legacy` to `governed`. That would close R1, R2a, R2b, R5 and R6 by default
and leave only R4 until P8 enablement.
