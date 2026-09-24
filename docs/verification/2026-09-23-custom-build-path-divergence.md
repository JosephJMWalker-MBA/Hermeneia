# Custom build preservation path divergence: witness and contract investigation

**Date:** 2026-09-23. **Starting commit:**
`f84775a9ceaf56b13ddce53a66fbb88e0474b981` on clean `main`.

**Scope:** Evidence, fixtures and characterization tests only. No production
behavior, artifact authority, schema, release identity, coverage custody or
historical report interpretation is changed or newly ratified by this note.

## Finding and classification

`herm preserve verify --build custom/build.json` parses coverage and release
records beside the selected build, while its reconstruction presence/hash checks
read `publication/coverage.json` and `publication/release_recommendation.json`
under the working-directory project root. The same report can consequently
interpret one pair and display successful hash checks for a different pair.

The strongest historical evidence identifies **an incompletely propagated
mechanical path-resolution repair**, not an intentional dual-authority contract.
Sibling resolution was explicitly selected in VS001-F02 remediation; the remaining
checks were subsequently documented as “Partial F02 propagation.” This is not
merely a guess based on filenames or the current implementation.

That conclusion does not authorize repair in this evidence-only packet. In
particular, a future repair must address how existing versioned reports remain
interpretable: their receipts intentionally bind both namespaces. Merely changing
the current algorithm would also change association checks for historical reports.

## Smallest witness

The four committed records under
[`tests/fixtures/custom-build-path-divergence/`](../../tests/fixtures/custom-build-path-divergence/)
contain conflicting, explicitly synthetic observations. No fixture signature is
an actual Steward judgment.

| Fixture pair | Coverage | Release |
|---|---|---|
| `adjacent/` | `build_id: adjacent-other-build`; `outcome: fail`; tag index includes absent `docs/adjacent-only.md` | `WITHHOLD`; signature and notes null |
| `conventional/` | Selected build ID; `outcome: pass`; empty tag index | `RECOMMEND_RELEASE`; marker signature `SYNTHETIC-CONVENTIONAL-ONLY`; synthetic notes |

The test uses the existing six-file synthetic build-input fixture, emits one real
supported build into `custom/`, and copies these two record pairs into `custom/`
and `publication/`. It does **not** create `publication/build.json`; that file is
not needed for the divergence. Clocks alone are fixed in tests; no loader, path,
check, hash or authority behavior is mocked.

The exercised production command is equivalent to:

```bash
herm preserve verify --build custom/build.json --output /temporary/reports
```

The primary witness produces:

| Report observation | Actual origin | Observed result |
|---|---|---|
| Coverage Record path/hash | `publication/coverage.json` | PASS and the conventional file's exact SHA-256 |
| Release Recommendation reconstruction path/hash | `publication/release_recommendation.json` | PASS and the conventional file's exact SHA-256 |
| Coverage Build ID | `custom/coverage.json` | WARN naming `adjacent-other-build` |
| Coverage Corpus Integrity | `custom/coverage.json` | WARN naming `docs/adjacent-only.md` |
| Steward Signature | `custom/release_recommendation.json` | ADVISORY; value null |
| Release Recommendation continuation | `custom/release_recommendation.json` | WARN; outcome `WITHHOLD` |
| Steward Notes | `custom/release_recommendation.json` | ADVISORY |
| Overall / exit | Existing summary rules | `warn` / 0; this is not release approval |
| Provenance / association | All actual captured inputs and selected build core | `valid`; accurately binds the mixed observations, not a claim that both pairs govern |

Swapping the pairs produces `pass` / exit 0. The conventional files now contain
the negative values but still receive reconstruction PASS because those checks
do not parse their JSON. Signature, notes and continuation come from the positive
adjacent pair. The tests assert the displayed conventional hashes differ from
the hashes of the interpreted adjacent records in both directions.

Additional controls start with positive records on both sides:

| Changed input | Result |
|---|---|
| Remove conventional coverage | Reconstruction FAIL; overall `fail`; exit 1 |
| Remove conventional release | Reconstruction FAIL; overall `fail`; exit 1 |
| Remove adjacent coverage | Conventional coverage check still PASS; coverage cross-checks are skipped; overall `pass`; exit 0 |
| Remove adjacent release | Conventional release check still PASS; continuation WARN/signature advisory; overall `warn`; exit 0 |
| Malform adjacent coverage or release JSON | Loader refuses; exit 1; no new report |
| Malform conventional coverage or release JSON | Bytes are hashed without JSON interpretation; overall `pass`; exit 0 |

Where reports are issued, their input receipts record the actual missing or raw
malformed observations and retain a valid build-core binding. That binding is
independent of downstream record validity, consistency, custody or release approval.

Exact fixture-byte inventory, including the terminal newline:

| Fixture | Bytes | SHA-256 |
|---|---:|---|
| `adjacent/coverage.json` | 103 | `97b23c9b0cdcb9b0a4d4120ef8029feac5f0ab551636f88a7305a1e0f80d5959` |
| `adjacent/release_recommendation.json` | 103 | `862680af17d7200fa3e558bacdb09d652905f75da76e4a1eb6751cc2555bb8bb` |
| `conventional/coverage.json` | 71 | `4f4d7c074481035f23e03d001615c59c8a1f68f2143467c9a2fb9424fa49b397` |
| `conventional/release_recommendation.json` | 188 | `866b34e476e419c6f3385143d292755b32dfc54a32ca72dff0b88272de72a9bc` |

## Complete artifact-input map for this witness

Paths below are relative to the explicitly selected working-directory project
root for presentation. Actual machine reports retain their original absolute
locators and exact byte hashes; no report or core is normalized or rewritten.
The tests assert that the primary report's receipt contains exactly these **13**
distinct artifact paths. This is an artifact-input inventory, not a trace of Python
module imports, directory traversal, or temporary output readback system calls.

| Artifact path | Consumer / observation | Current authority treatment |
|---|---|---|
| `custom/build.json` | `_load_inputs`; core binding validation | Explicit `--build` selects the build label, metadata, artifact locators and recorded hashes. |
| `custom/build.reproducibility.json` | `validate_captured_build` | Adjacent binding must validate against the exact selected build record and required core evidence. |
| `docs/builds/white_paper.compile.yaml` | Manifest interpretation; reconstruction hash; core validation | Selected build's `manifest_path` and captured build-time digest govern this input. |
| `docs/blueprint.md` | Blueprint and declared-source hashes; continuation intent; core validation | Selected build's Blueprint/source records and hashes; not inferred from conventional publication. |
| `docs/evidence.md` | Declared-source hash; core validation | Selected build's source declaration and hash. |
| `docs/paper.md` | Core validation of the copy source | Selected build/manifest's compile-source locator and exact compiled digest. |
| `custom/white_paper.md` | Compiled Artifact reconstruction check; core validation | Selected build's explicit emitted path and `compile.sha256`. |
| `custom/rc_log.md` | Core validation | Exact historical-output bytes recorded at emission; no reconstruction of missing historical facts. |
| `custom/release_decision.md` | Core validation | Same historical-output byte contract; does not establish release JSON identity. |
| `custom/coverage.json` | JSON loader; Coverage Build ID and Coverage Corpus Integrity | Sibling parsed dictionary supplies `build_id` and `tag_index`; external coverage `outcome` is not checked by these preservation checks. |
| `custom/release_recommendation.json` | JSON loader; signature, continuation outcome and notes | Sibling parsed dictionary supplies these observations. Presence of a signature is observed, not cryptographically authenticated or newly ratified. |
| `publication/coverage.json` | Reconstruction Coverage Record | Fixed conventional location; existence and current-byte SHA-256 only. No recorded expected hash, JSON validation, or selected-build association is established by this check. |
| `publication/release_recommendation.json` | Reconstruction Release Recommendation | Same fixed-location presence/hash check; does not inspect its signature or release outcome. |

`VerificationInputs` captures and later rechecks all these bytes/absences. The two
adjacent downstream records have roles `coverage-interpretation` and
`release-interpretation`; conventional records have roles
`reconstruction:Coverage Record` and `reconstruction:Release Recommendation`.
Receipt integrity establishes what was evaluated, not which of conflicting
downstream records ought to carry authority.

For a general build, the evidence paths, compile source, emitted
paper, manifest and historical outputs above come from the selected build and
manifest declarations; all declared source occurrences are checked. The selected
build and adjacent sidecar are the entry point. `project_root` is the command's
working directory, not automatically the custom build's parent. Absolute recorded
paths retain their current meaning.

The verification phase does not reread `docs/builds/white_paper_rc_log.md` or
`docs/builds/white_paper_release_decision.md`: the build copied those fixture inputs
earlier; preservation validates the recorded emitted historical outputs instead.
Report evaluation in this witness also does not read `coverage.md`, a conventional
build record, or release criteria.

### Outputs and the separate terminal advisory

The two report outputs resolve under explicit `--output`, defaulting independently
to `project_root/publication/`. Private staged bytes and installed report bytes
are read back during emission; this is output integrity, not another input scope.

After a non-failing report, the nonblocking edition advisory consults the **report
output directory**: `cycles.json`, `build.json`, `coverage.json`,
`release_recommendation.json`, and `preservation_report.json`. In this witness,
only the newly written report exists there; missing paths are probed, while the
new report is parsed. The advisory is outside report findings and input receipts
under the existing provenance specification. None of these output/advisory paths
is realigned in this packet.

## Evidence of intended contract and origin

Source line references in this note refer to starting commit `f84775a`.

1. Constitutional routing preserves provenance and human release authority:
   [Authority Index](../01_Authority_Index.md),
   [Constitution Articles II, VI, XI, XII and XV](../00_Constitution.md). These principles
   do not independently select a directory.
2. [Sprint 005, CLI flags](../sprints/sprint_005_preservation_layer_spec.md#cli-interface),
   line 191, calls `--build` the entry point and says everything else resolves
   from it. Its conventional input examples at lines 120–131 describe defaults;
   its old package layout/unsplit CLI are historical and are not a migration plan.
3. Original preservation implementation
   [`765d1401`](https://github.com/JosephJMWalker-MBA/Hermeneia/commit/765d140104cf1e980257c8ef726a1a8004da71bf)
   used conventional paths for both interpretation and reconstruction checks.
4. [VS001-F02](VS-001_findings.md#vs001-f02), lines 74–99, identified mixing a custom
   build with live publication records as misleading. It proposed sibling
   resolution, explicit downstream flags, or a clearly documented limited flag.
5. Remediation commit
   [`d18be9f2`](https://github.com/JosephJMWalker-MBA/Hermeneia/commit/d18be9f2bf5abe143655cbdd7dd703549e1550c6)
   deliberately changed `_load_inputs` alone to `build_path.parent`. The
   [remediation report](VS-001-remediation-report.md), lines 91–92, says `--build`
   now coherently controls all three input paths. This records selection of the
   sibling alternative, not an unresolved three-way choice at that time.
6. [The existing F02 test](../../tests/test_publication_release_authority.py),
   lines 285–306, explicitly requires coverage/release beside the build and
   supplies conflicting conventional values. It calls only `_load_inputs`, so
   it cannot detect the reconstruction check's partial propagation.
7. [VS-002 follow-up](VS-002-authority-boundary-reverification.md), lines 133–134
   and 154, already documents the exact residual split as “Partial F02 propagation”
   and a LOW consistency gap. Commit
   [`68732b0`](https://github.com/JosephJMWalker-MBA/Hermeneia/commit/68732b022c1ea04bca23cc39cd358e8f107218df)
   preserves that observation. The new witness strengthens its evidence; it does
   not silently rewrite the historical severity or claim a release bypass.
8. [The current receipt specification](../specs/preservation-verification-provenance.spec.md),
   lines 72–75 and 121–124, explicitly preserves both existing paths pending this
   investigation. It neither makes them interchangeable nor ratifies dual authority.
   [The prior receipt test](../../tests/test_preservation_provenance.py), lines
   150–168, distinguishes their bytes by a newline; this packet adds conflicting
   semantic values, missing-file controls and malformed-JSON controls.

Current implementation pointers: `preserve_cmd.py:670–689` (loading), `192–209`
(conventional checks), `211–253` (coverage/signature interpretation), `340–369`
(release continuation), `708–709,738–746` (report destination), `775–797` (advisory);
`build_reproducibility.py:133–196,266–277` (core evidence);
`preservation_provenance.py:118–148,152–187` (receipt and association).

Hosted issue lookup was read-only on 2026-09-23 at 22:45 UTC:
`gh issue list --repo JosephJMWalker-MBA/Hermeneia --state all --limit 500 --json number,title,url,state,body`.
It returned 87 issues; no title/body matched the case-insensitive expression
`VS-001|VS001-F02|build_path.parent|--build|herm preserve`. This does not establish
absence from issue comments, pull requests or discussions, which were not searched.
The directly relevant tracked finding lineage is the repository's VS001-F02 and
VS-002 evidence above. Query metadata is retained at
`/private/tmp/herm-custom-path-issue-audit.json`; no issue was changed or closed.

## Alternatives, consequences and compatibility

| Alternative | Consequences for new verification | Existing-contract implications |
|---|---|---|
| Custom-build-relative reconstruction checks, retaining current sibling interpretation | Hash/presence checks and interpreted records would coincide. Unrelated conventional files would no longer cause PASS/FAIL or enter the receipt. Missing adjacent records would fail presence checks even if conventional copies exist. | Best supported by F02 history and its explicit loader test. Default-directory builds are unaffected because both locations already coincide. Custom reports, counts, exits and receipts can change. It does not prove sibling records belong to the build or authenticate their release meaning. |
| Conventional-publication interpretation and checks | All downstream observations would come from live `publication/`. A custom build could now be assessed using another record's signature, release outcome, notes or coverage corpus; adjacent records would be ignored. | Reverses the deliberate F02 correction and its test. It is an observable contract and authority-selection change requiring steward authorization, not a mechanical completion of F02. |
| Retain an explicitly dual scope, or add explicit downstream selectors | Could represent separately selected records, but would need an explanation of which role each governs and how conflicts/missing evidence are handled. | No evidence found that the current accidental split was intended to encode such a scope. Precedence, fallback or custody semantics would be a new decision. Outside this packet. |

The surrounding commands do not collectively promise automatic adjacency:

- `herm coverage --build X` selects X but still writes to `publication/` unless
  `--output` is supplied (`coverage_cmd.py:220–227`;
  [Sprint 003 flags](../sprints/sprint_003_coverage_engine_spec.md), 265–266).
- `herm release` independently selects `--build`, `--coverage`, `--criteria` and
  `--output`; default coverage/output remain conventional (`release_cmd.py:234–249`;
  [Sprint 004 flags](../sprints/sprint_004_release_steward_spec.md), 319–322).
  Its signed-output guard applies to the explicitly
  selected output file; no alternate file acquires that judgment by this witness.
- `build.outputs.coverage` names `coverage.md`, not `coverage.json`
  (`build_cmd.py:320–322`). It cannot supply an inferred JSON-custody locator.
- `preserve export` currently loads the custom build but copies conventional
  build/coverage/release files (`preserve_cmd.py:621–629,827–834`). Changing that
  determines packaged evidence and requires a separate packet. No export or
  preservation-package equivalence is tested or repaired here.

Thus a future preservation check repair would require custom pipeline users to
provide the intended adjacent outputs explicitly; it must not copy, relocate,
regenerate, discover, or fall back to a signed conventional record implicitly.
Unknown: whether actual users depend on the current mixed-directory behavior.

### Historical report compatibility: stop boundary

The existing association API reevaluates the **current** algorithm and demands
exact agreement with a report's input roles/paths/digests and findings
(`preservation_provenance.py:166–185`). The new tests demonstrate that current
mixed-path reports validly associate with their actual inputs, including negative
findings. **Inference from that comparator:** naively aligning paths would make
some existing custom reports fail association even with unchanged evidence bytes.
That refusal would reflect changed verifier semantics, not demonstrated tampering.

Before implementation, the steward must choose how to handle that historical
boundary: retain the old lookup semantics for old receipt versions while using a
distinguishable corrected version for new reports, or explicitly refuse old
associations as unsupported under the corrected verifier. Neither alternative
permits rewriting old reports or substituting new findings for historical ones.
This packet does not select a versioning/retirement policy. Choosing conventional
interpretation or a new explicit dual scope additionally requires an affirmative
authority/selection decision contrary to or beyond the documented F02 direction.

## Reproduction and validation

```bash
python3 -m pytest -q tests/test_custom_build_path_divergence.py
```

The ten characterization cases pass by observing the divergence; they are not
claims that mixed resolution is desirable. Their test module is labeled as a
starting-commit characterization so a later authorized repair can deliberately
supersede it without making this note a new product contract.

An independent archive of exact `f84775a` at
`/private/tmp/herm-custom-path-baseline-tbltxzaj/archive` received only this new
test file and its four fixtures. Production module/Reader HTML hashes and imports
were verified against the starting commit. Combined run: **10 witness cases
passed; the six known Reader nodes failed in 0.58s**. Environment, import checks,
commands, JUnit, production hashes and output are retained beside the checkout.

Focused regression command:

```bash
python3 -m pytest -q tests/test_custom_build_path_divergence.py tests/test_preservation.py tests/test_preservation_provenance.py tests/test_preservation_provenance_adversarial.py tests/test_publication_release_authority.py tests/test_publication_false_confidence.py tests/test_build_reproducibility.py
```

Result: **183 passed, 5 warnings in 3.97s**;
`/private/tmp/herm-custom-path-focused.log`. The witness verifies input bytes and
modification times remain unchanged, and report association remains read-only.

Full regression: `python3 -m pytest -q`, with local socket/child-process access:
**1874 passed, 6 failed, 21 skipped, 5 warnings in 106.08s**. Log:
`/private/tmp/herm-custom-path-full.log`. The six failing node IDs were mechanically
compared with the independent `f84775a` archive run and match exactly:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

Five are the existing markup/event-binding assertions; one is the existing Node
`_crSyncPageSpeechControls` ReferenceError. No new failures were found. This does
not repair those Reader failures. Existing SWIG deprecation warnings remain.
`python3 -m compileall -q tests/test_custom_build_path_divergence.py` and
`git diff --check` passed. `git diff f84775a -- hermeneia` is empty: production
behavior is unchanged. No hosted CI or cross-platform verification is claimed.

## Bounded handoff

No production change was made. The narrower intended path contract is explicit;
there is no need to invent it. Stop before implementation because this request
is evidence-only and the historical report compatibility choice remains open.

**Next bounded packet after steward decision:** finish F02 only for reconstruction
coverage/release checks of new verification reports, under the chosen historical
receipt compatibility rule; keep interpreter selection, producer defaults,
release authority, export, edition and package equivalence out of that repair.
