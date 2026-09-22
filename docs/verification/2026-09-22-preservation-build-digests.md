# Preservation verification requires recorded build digests

**Date:** 2026-09-22
**Classification:** Implementation defect; verification/reporting only
**Baseline:** `9656e35a59bed02a8a5ba60e315e5a9ebda22a14` (`main`, matching `origin/main` at inspection)
**Environment:** macOS, Python 3.13.5, pytest 9.1.0

## Invariant and authority

For the Blueprint, compile manifest, and each declared source artifact,
`herm preserve verify` must compare the current bytes with a valid recorded
build-time SHA-256 before reporting verified integrity. A newly observed hash
cannot substitute for missing provenance.

This enforces the existing [Constitution](../00_Constitution.md), Articles I
and VI, and the [Sprint 005 preservation specification](../sprints/sprint_005_preservation_layer_spec.md):
reconstruction requires declared hashes and must succeed without inference;
preservation must not fill gaps or modify preserved artifacts. The existing
build implementation already emits all three digest fields. This note records
an implementation correction; it does not amend the specification or create
new ontology, storage, release, or ratification rules.

## Failure demonstrated before repair

The verifier guarded comparison with `if expected_hash`. For a nonempty file,
an absent, null, empty, or other falsey digest skipped comparison, and the
current file's digest was presented as a successful check. Empty files already
received a warning, but without a recorded digest that warning still lacked
verified provenance.

An isolated fixture reproduced the defect by deleting the evidence source's
`sha256` from `build.json` and changing that source after the build. The source
check returned `PASS`, with zero reconstruction failures. The newly observed
digest was `6598be92d7d5a689d624e8daff6122b6ca31b633386a536cd9415ea6b013c47d`;
there was no recorded digest against which it could have been verified.

Tests were added before changing production code. The new selection returned
**28 failed, 1 passed, 10 deselected**. These failures include diagnostic
assertions for nonempty malformed digests that already failed comparison;
missing/falsey digests are the demonstrated fail-open cases. The original
preservation, false-confidence, and release-authority suite passed **29 tests**
before the change.

## Observable contract

The shared reconstruction check now requires a string of 64 lowercase
hexadecimal characters, matching `herm build`'s existing `hexdigest()` output,
for each of:

- `blueprint.sha256`;
- `manifest_hash`;
- `source_artifacts[*].sha256`.

A missing or invalid digest produces `FAIL` with
`Missing or invalid build-time SHA-256 — integrity cannot be verified`.
The command emits failed JSON/Markdown reports and exits 1. It does not repair
`build.json`, insert the observed digest, or change source or steward records.
Previously accepted incomplete records must be resolved from trustworthy build
provenance before verification can succeed.

Valid but nonmatching hashes still fail as mismatches. An empty artifact with
its matching recorded hash still receives the existing content warning; an
empty artifact without a recorded digest fails. Human-signature advisories and
coverage/continuation checks retain their existing behavior. Coverage and
release records are not given invented build-time hashes.

## Validation

- `python3 -m pytest -q tests/test_preservation.py tests/test_publication_false_confidence.py tests/test_publication_release_authority.py`
  — **58 passed** after repair.
- Six separate-process invocations of
  `python3 -m hermeneia.cli.main preserve verify --build <fixture>/publication/build.json --output <reports>`:
  valid and unsigned fixtures exit 0; tampering plus a deleted Blueprint,
  manifest, or source digest exits 1; a normal hash mismatch exits 1. Reports
  match those outcomes, and every input file remains byte-for-byte unchanged.
- `python3 -m pytest -q` in the restricted execution environment:
  **1561 passed, 13 failed, 21 skipped**. Seven failures reported blocked
  loopback sockets or child startup (`Operation not permitted`). These are
  infrastructure failures, not evidence of a preservation regression.
- The six remaining Reader failures were independently reproduced against a
  `git archive` of the untouched baseline, with imports directed into that
  archive: **6 failed**. The exact failing nodes were:

  ```text
  tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
  tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
  tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
  tests/test_reader_record_view.py::test_record_tab_and_panel_present
  tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
  tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
  ```

  Five assert markup/binding strings; the other extracts a function into a
  Node harness that lacks `_crSyncPageSpeechControls`. They remain unresolved.
- `python3 -m pytest -q` with loopback/child-process access:
  **1568 passed, 6 failed, 21 skipped** in 91.57 seconds. The six failures
  are the same untouched-baseline Reader failures listed above; no failure
  touches the changed preservation code.

The regression tests are in `tests/test_preservation.py`. All destructive
actions target temporary fixtures. Existing tracked publication artifacts and
signed decisions were not rebuilt or modified.

## Inspection limits and next packet

The initial inspection covered the CLI dispatch, build, preservation,
release criteria, dependency declarations, existing tests, and open issues.
No current open issue specifically owns this digest defect; this note records
the contract correction without changing an unrelated issue or closing a
human validation gate.

This is not a claim of full preservation or reproducible-build correctness.
Independent inspection also reproduced a build output/hash race and a late
build failure leaving mixed old/new outputs. Release evaluation can also pass
a required criterion with a missing `equals` when the actual value is null;
that separate validation defect is not repaired here. Build timestamps and absolute
paths remain in the provenance records. The manifest is parsed and hashed at
different times. Preservation export uses a separate path, so this patch does
not establish missing-digest refusal or transactional export. General record
schema validation, source-list completeness, path confinement, crash recovery,
and authentication of `build.json` remain outside this slice. A matching hash
proves equality to the supplied record, not that the record itself is trusted.
No fresh-environment installation, hosted CI, cross-platform validation, or
release approval is claimed.

**Exact next bounded packet:** test and repair `_stage_compile` so
`compile.sha256` describes the bytes actually emitted as `white_paper.md`.
The reproduced witness copies version A, changes the source to version B
immediately after the copy, and observes B's digest recorded beside A's output.
Add that destructive test first, bind the recorded digest to emitted bytes,
verify ordinary-copy and CLI provenance behavior, and run the publication
suite plus regressions. Keep timestamp policy, whole-build snapshots,
transactional publication, signatures, and release decisions outside that
packet.
