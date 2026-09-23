# Preservation reports bound to evaluated build evidence

Date: 2026-09-23. Starting commit: `576eef2fb447f19016eee09e6d8eccf5551028c5`
on clean `main`. This is the steward-authorized additive report-provenance packet.
The active contract is
[Preservation verification input provenance](../specs/preservation-verification-provenance.spec.md).
No publication authority, preservation-package identity/equivalence, release
identity/equivalence, historical migration, or report custody policy changed.

## Demonstrated starting failures

The old order was: parse build-adjacent build/coverage/release JSON and manifest;
reopen/hash reconstruction artifacts; reopen Blueprint for continuation; write
reports identified only by `build_id`. It did not read or validate the build-core
sidecar. The first three deterministic tests failed before production changes:

| Witness | Starting behavior | Strengthened behavior |
|---|---|---|
| Valid supported build | Report has no validated core identity or input receipt. | Records exact validated profile/core digest and exact-byte input receipts. |
| Tamper sidecar core digest, retain all old artifacts | Existing checks and report pass; sidecar is ignored. | Existing checks stay unchanged; additive provenance is invalid, with no core claim. |
| Mutate manifest after parsing, before reconstruction | Interpretation uses old bytes while hashing uses new bytes. | Both use the original capture; final drift check refuses provenance. |

Initial run: `3 failed in 0.18s`, retained at
`/private/tmp/herm-report-before.log`. These tests then pass under the repair.

Two further destructive witnesses exposed output-writing hazards: a report
hard-linked to evaluated `build.json` truncated the build inode, and redirecting
the report parent after the alias check overwrote a same-named input. Each failed
before its repair. Atomic leaf replacement and a pinned, no-follow output
directory now preserve the inputs. A reverse-redirection witness established that
the alias guard must check the pinned lexical path as well as current resolution.
This was an input non-mutation repair, not a report custody policy.

## Implementation and compatibility

- `hermeneia/build_reproducibility.py` exposes existing binding validation over
  caller-owned captures; no new core projection, digest rule, or build format.
- `hermeneia/preservation_provenance.py` captures bytes and missing/unreadable
  observations, produces a versioned receipt, and provides a read-only machine
  report-to-build association check. Invalid/unsupported coverage never receives
  an inferred core identity.
- `hermeneia/cli/preserve_cmd.py` uses the same capture for interpretation, hashes,
  intent checks and core validation; adds machine-report provenance and minimal
  Markdown core/input details; protects examined inputs during report emission.
  Existing findings, summaries, exits, export behavior and release meaning remain.
- `tests/test_preservation_provenance.py` and
  `tests/test_preservation_provenance_adversarial.py` contain capture, detachment,
  negative-finding, legacy, numeric-observation, read-only and output-alias cases.
- `tests/test_preservation.py` moves its unreadable-file injection to the new byte
  capture boundary without weakening assertions. It adds a compatibility witness
  for a malformed NUL locator retaining the exact old failed check.
- `tests/test_publication_reproducibility.py` extends exact field/file divergence
  expectations for truthful new receipt hashes. Core equality remains unchanged.
- The design inventory, active build/report specifications and documentation
  index describe the additive contract and its limits.

Every original reconstruction/continuation check is compared directly with the
historical helper's result in corrupted-artifact and missing-digest cases. A report
with missing coverage has **valid binding and failed findings**; association
returns `findings_outcome: fail`. Repairing coverage later refuses association with
the old report and leaves that old `FAIL` report unchanged. A different core with
identical paper bytes, or a later execution of the same core at the same paths,
cannot inherit the earlier report.

Capture mutation tests cover manifest, build record, coverage, Blueprint,
missing-file appearance, and sidecar mutation both from and to malformed bytes.
Association rechecks inputs after comparing findings and reading the report again.
No changed capture is adopted as replacement evidence.

Review also found that applying the strict **core** JSON domain to the entire
historical report incorrectly rejected numeric signature observations, and Python
equality treated booleans as integer counts. Three failing tests established both
defects before correction. Reports now retain legacy JSON value ranges/types,
reject duplicate keys, and compare typed JSON observations. This makes no decision
about signature validity, release authority, or release identity.

No design field needed a new steward classification. The signature test enforces
the existing distinction between an observation and release authority. Custom
`--build` behavior was found to interpret adjacent coverage/release records while
hashing conventional `publication/` records; receipts preserve both inputs/roles
without silently choosing a new resolution contract.

## Validation

Focused command:

```bash
python3 -m pytest -q tests/test_build_core_codec.py tests/test_build_reproducibility.py tests/test_publication_build.py tests/test_preservation.py tests/test_preservation_provenance.py tests/test_preservation_provenance_adversarial.py tests/test_publication_false_confidence.py tests/test_publication_reproducibility.py tests/test_reproducibility_core_design.py
```

Final focused result: **343 passed, 5 warnings in 4.09s**. Log:
`/private/tmp/herm-report-focused-final.log`.

Final full command: `python3 -m pytest -q`, with local socket/child-process access.
Result: **1864 passed, 6 failed, 21 skipped, 5 warnings in 96.92s**. Log:
`/private/tmp/herm-report-full-suite-verified.log`. There are no new failure nodes.
`python3 -m compileall -q hermeneia tests/test_preservation_provenance.py tests/test_preservation_provenance_adversarial.py`
and `git diff --check` also passed.

Before classifying failures as baseline, an independent agent extracted a clean
`git archive 576eef2` under
`/private/tmp/herm-report-baseline-576eef2-o113n00a/checkout`. The archive was both
the working directory and `PYTHONPATH`; `hermeneia.__file__` and all four Reader
test modules' `INDEX` locations were verified inside that archive. Running the
exact six nodes produced **6 failed in 0.13s**:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

Five fail markup/event-binding assertions; the other reports Node
`ReferenceError: _crSyncPageSpeechControls is not defined`. The final suite's
failure-node set was mechanically compared with this archive run and is identical.
Baseline command, environment/import verification and output are retained as
`command.txt`, `environment.json`, and `reader-baseline.log` beside the archive.
Environment: macOS 26.6.2 arm64, Python 3.13.5, pytest 9.1.0, Node v22.17.0.
Warnings are the existing PyMuPDF/SWIG deprecations. No hosted CI or cross-platform
validation is claimed.

Independent review checked capture consistency, negative findings, output aliases,
JSON observation types and authority limits. Its concrete findings were reproduced
and repaired. The final malformed-locator compatibility case was also reproduced
before repair and included in both final suites.

## Remaining boundary and exact next packet

The receipt is unsigned execution evidence, not authenticated writer identity,
retention/custody policy, or an indefinitely locked filesystem. Each report is
replaced atomically; the two reports are not one transaction. Power-loss durability,
whole-publication rollback and preservation-package/release equivalence remain
outside this packet. Historical records/reports are not backfilled or migrated.
The association checker is a Python API; existing preservation CLI exits continue
to express findings, so consumers needing core provenance must inspect the receipt.

**Next bounded packet:** measure the custom-`--build` split with distinct adjacent
and conventional coverage/release files; identify the governing resolution
contract and preserve a deterministic witness. Propose the smallest alignment
only after that contract is established. Stop for steward resolution if it would
choose artifact authority, custody or release semantics. No package-profile or
release-profile implementation is implied.
