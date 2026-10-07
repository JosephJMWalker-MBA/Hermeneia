# #215 P4 gate closeout: real-study portability — 2026-10-07

**Result:** The P3/P4 real-data portability sub-gate is **demonstrated** on
merged `main` `44d44fd`.

- **Part A.** The real study's retained Perspective evidence survives a WBS
  export and restore with exact equivalence.
- **Part B.** A Perspective Explorer award was issued only inside a private
  copy, through the explicit product route. The award, its receipt bytes,
  evidence package, rule, dependencies, Lineage and independent verification
  all survive export and restore unchanged.

The original study was never opened with SQLite and holds no award.

- **Commit tested:** `44d44fd` (merge of PR #242; tree identical to `d9ea324`)
- **Safe study alias:** `study-d88c4a642956`
- **Packet:** [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215)
  P4 gate closeout
- **Supersedes the gate consequence of:**
  [`2026-10-04-real-study-wbs-roundtrip.md`](2026-10-04-real-study-wbs-roundtrip.md),
  kept unchanged as the historical failure witness. Its export defect was
  repaired as #216 and merged in PR #242.

## Safety boundary

Both parts started from a fresh copy of the workspace's seven regular files,
made with filesystem reads only:

- The copy was verified byte-identical to the original before any database
  access.
- No SQLite connection was opened on the original.
- Afterward, all seven original files were byte-identical to their
  pre-copy hashes.
- Outbound sockets were blocked in-process, and no network attempt was
  recorded.
- No Perspective was rerun, and no provider or model was called.
- The product server ran only against the private copy and the fresh restore
  target, with no credential store and with throwaway connection settings.

## Part A — retained Perspective evidence

On the private copy, captures were taken read-only with `mode=ro` and
`PRAGMA query_only=ON`. The copy was exported with `export_workspace_bundle`
and restored into a fresh database with `restore_workspace`.

| Check | Result |
| --- | --- |
| Identity vs 2026-10-03 | receipt `perspective-execution-receipt:sha256:5870a94e…c0c45e`, run, evidence-package digest and alias all match |
| Export | WBS 1.1; 1 retained receipt; 0 awards; `source_bytes` 1 document, 0 missing; the copy's bytes, logical dump and counts unchanged by export |
| Restore | not refused; receipt category covered |
| Perspective Explorer / Second Opinion | `earned` → `earned` / `not_earned` → `not_earned` |
| Evidence digest, package digest, receipt bytes, Lineage item, coverage, diagnostics | all equal |
| Dependency drift | none |
| Decision | **`exact_equivalence`**, identical to the earlier runs at `242a826` and `09b94b2` except for the commit tested |

## Part B — award portability, private copy only

**Before issuance (read-only):**

- Perspective Explorer is `earned` under `achievement.perspective_explorer`
  version `1.0.0`. The rule digest is
  `sha256:86b2d70b234bae34247764d97993f37a4c3a9e0e3bbe04741f7973d5dfaa3f73`,
  and the rules set digest is
  `sha256:6b0065fac155c40fc25ce5cc62c53a7c250c0595dd4e49554669bab55e56197c`.
- The evidence-package digest is
  `sha256:5ad385a0263ab96678fc405a7c9fea33c87e7ce751e27ad29d53fc946f047c71`,
  exactly the package validated on 2026-10-03.
- There are five dependencies: four `source_extractions` with basis
  `immutable_reference` and one `source_documents` with basis
  `evaluation_snapshot`. Their canonical map digest is
  `sha256:2712f4ff94683c5f97487ff07c8e17e0339549ff5ceeef343601bf5345ac020d`,
  equal to the Part A capture.
- The copy held no awards.
- After server startup on the copy, `GET …/perspective_explorer/assessment`
  returned the same package digest. The startup changed neither the package
  nor the dependencies.

**Issuance.** `POST /api/achievements/perspective/perspective_explorer/award`
carried the exact `rule_id`, `rule_version` and `assessment_package_sha256`,
and returned **201 `recorded`**:

- award id
  `achievement-award:sha256:e668a7290cc63edbe6229dc869db9ed3a4ccbc21ab4a7e0ab1fd2293ae6069ea`;
- canonical receipt of 15,889 bytes, digest
  `sha256:021c3324610b906828ec8160bea6a29c7bcf81c984dbfc0e71e4dc9d6c9b9c57`;
- issuance policy `explicit-steward-materialization/v1`, actor
  `local_steward`, identity `unknown`, approved package equal to the digest
  above;
- Lineage item `perspective_achievement_award`, authorship `derived`, event
  `recorded`;
- independent verifier: receipt integrity `valid`, evidence verification
  `verified`, historical snapshot replay `verified`. The API verification
  equals the direct verifier function.

**Export and restore.** WBS 1.1 required both
`perspective-achievement-awards-v1` and `perspective-retained-execution-v1`,
and carried 1 award and 1 receipt. Export left the copy's logical dump
unchanged. The restore was not refused and restored 1 award and 1 receipt;
both categories are reported `covered` with no complete-history claim.

| Pass requirement | Result |
| --- | --- |
| Award record survives | yes (1 → 1) |
| Award identity and canonical receipt bytes | equal |
| Evidence-package digest | equal, still `sha256:5ad385a0…f047c71` |
| Rules digest | equal |
| Dependency evidence | equal; no drift |
| Retained receipt bytes and receipt Lineage | equal |
| Award Lineage item | equal |
| Independent verification | equal (`valid` / `verified` / `verified`), both directly and through the restored server's API |
| Decision | **`award_portability_exact`** |

## Gate consequence

The P3 requirement for explicit WBS export/restore coverage of retained
receipts, and the P4 requirement for declared export/restore behavior of
historical award receipts, are both demonstrated on real data:

- retained receipts and award receipts survive a WBS round trip
  byte-for-byte;
- their evidence and verification conclusions are unchanged;
- the restored workspace claims only extant-record coverage, not complete
  history.

## Not established

- **Source fidelity.** Issuing the award does not validate the retained
  Perspective response. The 2026-10-03 source-fidelity and attribution
  failures (changed quotations, altered dialogue wording, unsupported
  certainty) remain a separate steward-review item. An award records that
  the evaluator returned `earned` under rule `1.0.0`; it does not attest
  correctness or quality.
- **No award in the original study.** The original holds no award; whether
  to record one there is a steward decision.
- **Second Opinion** remains `not_earned`, and its real-data award path was
  not exercised.
- This is one real study and one retained execution. Neither complete
  historical activity nor named human identity is established.

Raw source text, the question, prompt, response, private paths and workspace
identity remain outside this note.
