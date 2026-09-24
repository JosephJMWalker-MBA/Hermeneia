# VS001-F02: complete sibling resolution without historical reinterpretation

**Starting commit:** `2fdfde6e0f06a5c044967fb1b93dac1b5aad091b`.
**Scope:** preservation verification path propagation and report association only.
**Authority:** the steward accepted sibling/custom-build-relative coverage and
release resolution, immutability of historical reports, and explicit unsupported
association for old mixed-namespace evidence. This completes the intended contract
already selected by VS001-F02 remediation; it does not choose release identity,
package equivalence, custody, or a new publication authority.

The [prior divergence note](2026-09-23-custom-build-path-divergence.md) remains
unchanged historical evidence, including its old PASS/WARN/FAIL observations.
The current contract is in the
[preservation provenance specification](../specs/preservation-verification-provenance.spec.md).

## Demonstrated defect and bounded correction

Before repair, `_load_inputs` interpreted coverage/release beside the selected
build, but `_verify_reconstruction` hashed fixed `publication/` files. Missing
custom coverage could produce PASS from unrelated conventional bytes. Missing
conventional records could cause FAIL despite complete custom siblings.

The original ten characterization tests independently pass on an archive of
`2fdfde6`. Revised assertions demanding corrected behavior then produced **9
failures and 2 passes** before production edits. These tests preserve the four
conflicting JSON fixture payloads unchanged; swapping the two record pairs still
exercises negative coverage, withholding, signature and notes observations.

New verification pins the resolved parent of the selected build once. The selected
build, adjacent `build.reproducibility.json`, `coverage.json`, and
`release_recommendation.json` must resolve within that namespace under their exact
filenames. Coverage/release interpretation and reconstruction share the same lookup
paths and captured bytes. Cross-parent leaf redirection is refused even for
identical bytes. Guards apply both before capture and during each read/recheck;
existing confined opens prevent redirection between resolution and opening.

The complete prior input inventory is accounted for as follows:

| Previous witness inputs | Corrected resolution |
|---|---|
| `custom/build.json` | Explicit selected entry point; its resolved parent pins the sibling namespace. |
| `custom/build.reproducibility.json` | Required adjacent binding; no conventional substitution. |
| `docs/builds/white_paper.compile.yaml` | Existing selected-build declaration and exact hash; unchanged. |
| `docs/blueprint.md`, `docs/evidence.md`, `docs/paper.md` | Existing declared Blueprint, sources and compile source; unchanged. |
| `custom/white_paper.md`, `custom/rc_log.md`, `custom/release_decision.md` | Existing declared emitted/historical outputs and captured hashes; unchanged. |
| `custom/coverage.json`, `publication/coverage.json` | One selected sibling `custom/coverage.json`, consumed by both roles. |
| `custom/release_recommendation.json`, `publication/release_recommendation.json` | One selected sibling `custom/release_recommendation.json`, consumed by both roles. |

Thus **13 old distinct inputs become 11**, without relocating declared source or
output locators. The project root remains explicit. Authored lookup spellings,
including `docs/../custom/build.json`, remain truthful in receipts. Consistent
parent-directory aliases are supported; recorded resolved locations establish
the one namespace. No heuristic content/path normalization is used.

Missing selected siblings now produce the existing FAIL reconstruction finding
and exit 1. Missing or malformed unrelated conventional files have no effect on a
custom verification. Malformed selected JSON still aborts. Negative coverage,
release-withholding and signature observations retain their existing meaning.
A correctly bound report can still contain FAIL: integrity of observations is
separate from preservation success. Later evidence drift refuses a core claim.

## Historical compatibility and frozen evidence

New receipts use `hermeneia.preservation-verification-inputs/v2` and digest domain
`Hermeneia preservation verification inputs v2\n`. The build core and engine
label are unchanged. This versions the input-resolution contract, not release or
package identity.

`verify_report_binding` examines a v1 receipt's **recorded** roles and lookup /
resolved paths before any current evaluation. It requires unique role coverage
and agreement with the recorded build's sibling namespace. Mixed, missing, null
or duplicate association evidence returns `integrity: unsupported` and
`compatibility: legacy-unsupported-association`, with no core or findings-outcome
claim. Today's matching files cannot repair that historical evidence. A v2 mixed
receipt is invalid; it cannot use a legacy fallback.

Fully unmixed v1 reports remain eligible for exact association. Current captures
are encoded in memory using v1's original domain/schema for exact comparison;
all historical findings, summaries and the outcome must also match. Nothing is
written to the report, and no old finding is recomputed as a replacement.

The committed [legacy mixed report fixture](../../tests/fixtures/custom-build-path-divergence/legacy-mixed-report.json)
is an actual report emitted by the archived starting code, copied byte-for-byte:

- SHA-256: `4b99379a8f92cf6bf27c9821f8b325cc2b1f66aaae9f0c7800dd97092ecc3b56`.
- Historical result: WARN, valid provenance, 13 captured inputs.
- Historical association: valid, findings WARN, core
  `4461dd5d721e892b1e2a3a1a6ae29de310d0a36348270a15aa85f14991a39cad`.
- Origin: `/private/tmp/herm-f02-baseline-aqubn50j/witness-reports/preservation_report.json`.
- Its absolute paths, timestamps, hashes and findings are intentionally preserved.
  It is synthetic test-project evidence, not an actual Steward release decision.

The frozen fixture is refused before current evaluation; its bytes and mtime stay
unchanged. Additional synthetic v1 encodings are explicitly labeled as test
encodings, not historical reports. The 12 compatibility cases were also run with
only their test/fixture copied into the starting archive: **11 failed, 1 passed**.
The unchanged unmixed-v1 control passed there; new version/refusal/namespace
assertions exposed the missing behavior.

An independently generated **actual default-build v1** report also associates
successfully under the corrected implementation. A fresh v2 report has identical
reconstruction checks/summary, continuation checks/summary, and overall PASS;
all input and old-report bytes/mtimes remain unchanged. Old report SHA-256:
`e5549de28a823739f64b2de99d6e52c035982f8e716b4e871578b2668c702748`.
Evidence: `/private/tmp/herm-f02-baseline-aqubn50j/default-current-results.json`.

## Validation

Independent starting checkout:
`/private/tmp/herm-f02-baseline-aqubn50j/archive`.
Metadata verifies the starting SHA and that Python imports and Reader HTML resolve
inside that archive. The six Reader nodes independently fail there (**6 failed in
0.23s**); the old divergence cases pass (**10 passed in 0.49s**). Logs and import
metadata are in the enclosing baseline directory.

Focused command:

```bash
python3 -m pytest -q tests/test_custom_build_path_divergence.py tests/test_preservation_namespace_compatibility.py tests/test_preservation.py tests/test_preservation_provenance.py tests/test_preservation_provenance_adversarial.py tests/test_publication_release_authority.py tests/test_publication_false_confidence.py tests/test_build_reproducibility.py tests/test_publication_reproducibility.py tests/test_reproducibility_core_design.py
```

**228 passed, 5 existing warnings in 6.34s**.
Log: `/private/tmp/herm-f02-focused.log`.
Tests cover conflicting fixtures in both directions, absence/malformed input,
constant-byte cross-namespace redirection before/during capture, later drift,
valid parent aliases, authored lookup preservation, legacy compatibility and
read-only input/report snapshots. An independent review identified the authored
`..` self-association edge; its failing witness was retained at
`/private/tmp/herm-f02-parent-component-review.log` before the two locator tests
were added and passed.

Full regression: `python3 -m pytest -q`, with local socket/child-process access:
**1891 passed, 6 failed, 21 skipped, 5 existing warnings in 140.68s**.
Log: `/private/tmp/herm-f02-full.log`. The six failing node IDs were mechanically
compared with the independent `2fdfde6` run and match exactly:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

Five are markup/event-binding assertions; one is the existing Node
`_crSyncPageSpeechControls` ReferenceError. **No new failures.** Compilation of the
two changed production modules and three changed/new test modules, plus
`git diff --check`, passed. Original four fixture payloads and the previous evidence
note were byte-compared against `2fdfde6` and remain unchanged. Independent review
found no further actionable correctness or scope issues after the lookup fix.

## Deliberate limits and stop

No fixture payloads or old evidence notes/reports were rewritten. Corrected
reports were emitted into fresh output directories. The existing explicit report
output/replacement mechanism remains unchanged; this packet does not introduce
retention or report custody policy. Read-only association never writes.

Coverage/release producer defaults, `preserve export`, edition advisory, declared
source/output meanings, release identities/signatures, and package equivalence
are unchanged. Unsupported-platform and unsigned-integrity limitations remain
as documented in the existing provenance contract. No hosted CI or cross-platform
verification is claimed; dependency on old mixed behavior in real use is unknown.

Stop after this bounded correction. Any next examination of custom-build export
or package selection requires its own evidence packet and explicit scope; it is
not part of F02 verification completion.
