# Manifest interpretation and provenance share one byte capture

**Date:** 2026-09-22

**Baseline:** `26ae283af3b1a997bee425bad234e0b0ef5ce679`

**Classification:** Build implementation mechanics; manifest input provenance

**Environment:** macOS, Python 3.13.5, pytest 9.1.0, Node.js 22.17.0

## Invariant and authority

Manifest interpretation and `build.json.manifest_hash` must derive from the
same captured byte sequence. A later read may detect divergence, but must never
silently replace the manifest interpretation or its recorded identity.

The governing sources are the [Constitution](../00_Constitution.md), Articles I,
II, and VI, and [Sprint 002](../sprints/sprint_002_publication_build_spec.md),
especially invariants 2–4 concerning reproducibility, provenance, and failure.
This repair changes implementation mechanics and detected-drift failure
behavior. Manifest authority, schema validation rules, release decisions,
ratification, and output filenames remain unchanged.

## Original ordering and deterministic witness

At the baseline:

1. Stage 1 opened the manifest in text mode and parsed it with `yaml.safe_load`.
2. The resulting mapping supplied Blueprint/source paths, coverage, compilation,
   build identity, and release metadata through stages 2–7.
3. Stage 8 independently reopened the manifest path in binary mode to compute
   `manifest_hash` while constructing `build.json`.
4. No check linked that late digest to the bytes interpreted at stage 1.

Before production edits, a synchronous wrapper around the real steward-report
stage replaced manifest A with B after report generation. A declared build ID
`compile-byte-provenance`; B declared `replacement-manifest`. The baseline
reported success with A's build ID and B's digest:

| Bytes | SHA-256 |
|---|---|
| Interpreted A | `7396681edc2c1e77c45b8218b24ad2eb3e02e867212482aee823d220c49563c3` |
| Recorded B | `decf37f30a170ca2c3e3faa9b8b871abe93ffbad04ecf33ad52fea1ca5eaa6e6` |

The witness used temporary fixture files and no thread scheduling or sleeps.
The first adversarial test run on unchanged production code produced
**19 failed, 2 passed, 20 deselected**. Some failures establish the new loader
return/hook contract; this is not a claim of 19 independent defects. The
text-decoding compatibility test was added after the repair.

## Repaired ordering and observable contract

1. Stage 1 captures the manifest with one binary read and hashes those bytes.
2. It parses an in-memory text stream backed by those same bytes. The stream
   preserves the previous `open(path)` decoding and universal-newline behavior;
   the digest includes original BOM, newline, comment, and whitespace bytes.
3. Existing mapping and required-key validation applies to that capture.
   Unreadable, malformed, or invalid captured input raises `BuildError`; the
   loader does not retry or adopt a valid replacement subsequently on disk.
4. All downstream stages receive that parsed mapping. The captured digest is
   passed explicitly to the emitter, which records it without recomputing its
   authority from a later path read.
5. After coverage, before output creation or dry-run success, the current file
   must match the captured digest. Missing/unreadable input or any byte drift,
   including comment-only edits, fails closed.
6. Immediately before writing `build.json`, the emitter checks the manifest
   again alongside the existing emitted-artifact check. Detected divergence
   raises `BuildError`, exits 1, preserves any previous build record, and does
   not announce build success.

Later verification reads are comparisons only. They neither reparse the file
nor change the captured digest. The build does not rewrite the manifest,
Blueprint, source artifacts, or steward decisions. Preservation verification
continues to compare the existing `manifest_hash` field with the current file.

## Verification

- `python3 -m pytest -q tests/test_publication_build.py -k manifest --tb=short`
  on unchanged production code: **19 failed, 2 passed, 20 deselected**.
- `python3 -m pytest -q tests/test_publication_build.py tests/test_preservation.py tests/test_publication_false_confidence.py tests/test_publication_release_authority.py`
  after repair: **100 passed**, including 22 new manifest cases.
- Adversarial cases mutate the path after capture, before parsing, after parsing,
  after coverage, and after report generation. They cover atomic replacement,
  deletion, unreadable files, comment-only drift, invalid bytes replaced by valid
  bytes, and divergent downstream path/metadata proposals. Exact-byte tests
  cover UTF-8 BOM, LF/CRLF, Unicode, comments, and whitespace. A compatibility
  test confirms UTF-16 is not newly accepted by switching to PyYAML's binary
  decoding behavior.
- The six known Reader failures were independently reproduced in an isolated
  archive of the exact pre-packet commit: **6 failed in 0.11 seconds**. They are
  the same six nodes recorded in the
  [preservation verification baseline](2026-09-22-preservation-build-digests.md#validation):
  five markup/binding assertions and the Node harness's undefined
  `_crSyncPageSpeechControls`. No edited package or Reader file supplied that
  baseline run.
- `python3 -m pytest -q --tb=short`, with local socket and child-process access:
  **1610 passed, 6 failed, 21 skipped**, with 5 dependency deprecation warnings,
  in 94.41 seconds. All six failures match the independently reproduced Reader
  baseline; no newly failing tests were observed. The full suite remains red
  because those existing failures are unresolved.
- `git diff --check` passed. Only the build implementation, its tests, this
  verification record, and the documentation index changed.

## Limits and next bounded packet

Equality is checked at explicit boundaries. This does not provide locking,
permanent file immutability, or an atomic filesystem snapshot against arbitrary
concurrent writers. A file changed and restored between checks may go
undetected, but downstream interpretation and provenance still derive from the
captured bytes. Changes after the last check are left for later verification;
the recorded hash is never replaced with those later bytes.

This is not a transaction over the publication directory. A failure detected
after compilation can leave new outputs alongside an older build record, as
documented in the [preceding packet](2026-09-22-compile-emitted-bytes.md#boundary-and-remaining-work).
Whole-build rollback, source snapshots across all stages, timestamp policy,
release policy, and schema expansion remain outside this repair. Cross-platform
behavior and hosted CI have not been verified.

The next bounded packet is to inject an interrupted `build.json` write and
establish whether the previous complete record can be truncated. If reproduced,
stage and atomically replace that single JSON file, testing serialization,
write, and replacement failures while preserving the existing output schema.
Keep whole-directory transactions and release policy outside that packet.
