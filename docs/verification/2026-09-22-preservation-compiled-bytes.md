# Preservation verification binds compiled bytes to build provenance

**Date:** 2026-09-22

**Baseline:** `6941e42dbf132abac954e4f41a30aebf9257bb85`

**Classification:** Preservation verification/reporting implementation defect

**Environment:** macOS, Python 3.13.5, pytest 9.1.0, Node.js 22.17.0

## Invariant and authority

The emitted artifact declared by `build.json.outputs.white_paper` must match
the exact SHA-256 recorded in `build.json.compile.sha256`. Current bytes cannot
substitute for missing or invalid build-time provenance. Verification must not
rewrite the build, its inputs/outputs, preserved package artifacts, or steward
records.

This enforces the [Constitution](../00_Constitution.md), Articles I and VI,
[Sprint 002](../sprints/sprint_002_publication_build_spec.md)'s emitted-artifact
provenance contract, and [Sprint 005](../sprints/sprint_005_preservation_layer_spec.md)'s
declared-hash reconstruction and read-only preservation invariants. It adds no
schema fields, ontology, publication authority, release criteria, or signatures.

## Original behavior and deterministic witness

At the baseline, reconstruction checked recorded hashes for the Blueprint,
compile manifest, and source artifacts. It checked the existence of coverage
and release records. It never inspected `outputs.white_paper` or
`compile.sha256`; even missing compiled content and provenance were ignored.

Before changing production code, an adversarial test:

1. Created a temporary corpus with valid coverage/release fixtures and ran the
   real build command to emit the compiled artifact and its build record.
2. Ran preservation verification and confirmed overall `pass`, with all existing
   files unchanged.
3. Appended a tampering marker only to the emitted `white_paper.md`, leaving the
   original manuscript and build record unchanged.
4. Ran preservation verification again, expecting exit 1 and a digest mismatch.

The old verifier still returned successfully and reported **8 reconstruction
PASS, 8 continuation PASS, overall PASS**. The test failed because no
`SystemExit` occurred. It did not rely on timing or external services.

The full initial adversarial selection returned **39 failed, 39 deselected**
on unchanged production code. Those failures include checks for the new
per-artifact result and malformed provenance diagnostics, not 39 independent
defects. All destructive writes targeted temporary fixtures.

## Observable contract after repair

Reconstruction now includes a **Compiled Artifact** check:

- Resolve `outputs.white_paper` as recorded: relative paths are relative to the
  project root; absolute paths remain absolute. There is no fallback to
  `compile.source`, the manifest's original manuscript, or a conventional
  publication location.
- Require `compile.sha256` to be a string of exactly 64 lowercase hexadecimal
  characters, using the same validator as existing build-time digest checks.
- Hash the declared output in binary mode with the existing chunked SHA-256
  utility. Do not decode, normalize, render, regenerate, or rewrite content.
- Compare actual bytes against the recorded digest. Mismatches report `FAIL`
  with the existing `hash_at_build`, `hash_now`, and mismatch-note fields.
- Missing/malformed digest provenance, invalid output-path containers or values,
  absent artifacts, directories, and read failures produce a dedicated `FAIL`.
  No observed digest is adopted as replacement provenance.

The existing JSON and Markdown report shapes remain unchanged; their check
lists/counters now include the compiled artifact. A failing compiled check makes
reconstruction and overall verification fail, and the CLI exits 1. Other checks
continue to report their own results: in the tampering witness, continuation
remains `pass` and the compiled artifact is the only reconstruction failure.

Empty bytes with their matching recorded hash retain the shared check's existing
content `WARN`; missing provenance still fails. Steward signature advisories,
release decisions, and continuation rules are unchanged. Incomplete older build
records cannot claim verified compiled integrity by guessing a path or digest.

Verification still writes its requested derived reports. Tests place these
reports outside the corpus and compare all pre-existing files byte for byte,
including a retained preservation-package fixture. Neither verification success
nor failure mutates the files being verified.

## Verification

- `python3 -m pytest -q tests/test_preservation.py -k compiled_artifact --tb=short --show-capture=no`
  before production edits: **39 failed, 39 deselected**.
- `python3 -m pytest -q tests/test_preservation.py tests/test_publication_build.py tests/test_publication_false_confidence.py tests/test_publication_release_authority.py --tb=short --show-capture=no`
  after repair: **181 passed**, including 39 new cases.
- Tests cover valid/mutated compiled bytes, missing/malformed digest and record
  containers, absent/invalid output paths, custom relative and absolute paths,
  unchanged original input with changed emitted bytes, and changed original input
  with valid emitted bytes. Exact-byte cases include BOM, CRLF, Unicode,
  NUL/non-UTF-8 bytes spanning multiple hash chunks, and empty bytes. All cases
  check nonmutation of existing files.
- The existing valid corpus fixture now includes the compiled file and existing
  build fields already emitted by the real compiler. No production artifacts
  were rebuilt to make tests pass.
- Independent review found no blocking defect in the implementation or tests.
- All six known Reader failures were independently reproduced from an isolated
  archive of exact pre-packet commit `6941e42dbf132abac954e4f41a30aebf9257bb85`,
  with archive-local imports and static Reader fixtures: **6 failed in 0.13
  seconds**. They are the [same six nodes](2026-09-22-preservation-build-digests.md#validation):
  five markup/binding assertions and the undefined `_crSyncPageSpeechControls`
  Node harness reference.
- `python3 -m pytest -q --tb=short`, with local socket and child-process access:
  **1691 passed, 6 failed, 21 skipped**, with 5 dependency deprecation warnings,
  in 93.91 seconds. All six failures match the independently reproduced Reader
  baseline; no newly failing tests were observed. The full suite remains red
  because those existing failures are unresolved.
- `git diff --check` passed. Only the preservation implementation, its tests,
  this verification record, and the documentation index changed.

## Limits and next bounded packet

This verifies equality to the supplied build record at the time of reading. It
does not authenticate that record or prevent an external writer from changing
files after verification. General schema validation and path confinement are
outside this slice; the existing recorded-path semantics are preserved.

The separate export implementation currently omits the compiled output from its
package inventory. It is unchanged here. This packet verifies the emitted file
at its recorded path and does not establish integrity of an exported archive.
Coverage/release records retain their existing checks; no absent digest is
invented for them. Whole-publication rollback, power-loss durability, and release
policy remain outside scope. Cross-platform behavior and hosted CI were not
verified.

The next bounded packet is to reproduce the compiled-output omission in
`herm preserve export` using a valid fixture, then assess the smallest way to
preserve the already-declared output together with its build-time digest and
verify the copied bytes. Keep package transactions and release policy separate;
stop if the repair requires a package-format or authority decision.
