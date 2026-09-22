# Compile provenance binds emitted file bytes

**Date:** 2026-09-22

**Baseline:** `90af8a9c2ad614741387e7a84ba450788f7f297a`

**Classification:** Build implementation mechanics; single-artifact publication

**Environment:** macOS, Python 3.13.5, pytest 9.1.0

## Invariant and authority

On successful compilation, `compile.sha256` must describe the exact bytes
published to `white_paper.md`. The compiler must refuse to emit a new build
record if it detects that those bytes diverge from the compile digest.

The governing sources are the [Constitution](../00_Constitution.md), Articles I,
II, and VI, and [Sprint 002](../sprints/sprint_002_publication_build_spec.md),
particularly emitted-artifact provenance (invariant 3) and stage 5's copy/hash
contract. This is a mechanical repair under that existing contract. No artifact
authority, ratification, release criterion, schema, or output filename changes.

## Original ordering and deterministic witness

At the baseline, `_stage_compile` performed:

1. Check that the compiled source exists.
2. `shutil.copy2(source, white_paper.md)`, writing directly to the final path.
3. Hash the source path again and return that hash in `compile.sha256`.
4. Later, `_emit_build_json` writes the record without checking the emitted file.

There was no staging, rename, or destination verification. A source edit after
the copy therefore changed the digest without changing the already-copied
output. A failed copy could also expose truncated output.

Before editing production code, tests wrapped the real copy operation, copied
version A, then synchronously replaced the source with version B. No timing or
thread scheduling was needed. The baseline emitted A while returning B's hash:

| Bytes | SHA-256 |
|---|---|
| Emitted A | `ce093e52841cc0f2933f4235f2307d7b7e1d4bdb9a88acc1a0ad37bbeae0b822` |
| Recorded B | `fb63d30144474685c6b58afcfd87369407a7642f46d0075a06e37d54144bb667` |

A second test changed or removed `white_paper.md` during the later report
stage. The old implementation still emitted `build.json` and reported success.

The initial new test file produced **16 failed, 3 passed** on unchanged
production code. This count includes tests for the new atomic-publication
hooks and controlled error types; it is not a claim of 16 independent defects.
A dry-run compatibility test was added afterward.

## Repaired ordering

1. Retain refusal when source and destination refer to the same file, including
   hardlink and symlink aliases.
2. Copy to a private temporary directory inside the output directory, on the
   same filesystem as the final destination.
3. Hash the staged file in binary mode. No text decode, newline conversion, or
   in-memory reconstruction supplies the digest.
4. Atomically replace `white_paper.md` with the completed staged file.
5. Hash the published path and require equality with the staged digest. Return
   the verified published digest in the existing compile record.
6. After constructing the build record, immediately before writing
   `build.json`, recheck the emitted file against `compile.sha256`.

The `source`, `sha256`, `method`, and `note` compile fields retain their existing
shape. The source path remains the original path, never the staging path.
`copy2` retains its content/metadata copying role. All five ordinary publication
outputs retain their names and provenance paths; dry runs create no staging or
output directory.

## Failure behavior

Copy, staged-hash, or replacement failure removes temporary staging and leaves
any previous `white_paper.md` intact. With no previous output, none is published.

A mismatch or unreadable/missing output after publication or before record
emission raises `BuildError`; the CLI exits 1 and emits no new successful build
record. It does not recompute a new accepted digest for divergent bytes. It
also does not delete an output that another writer might now own. The CLI
therefore reports that the build did not complete and outputs may need rebuilding,
instead of incorrectly asserting that no output was written.

Atomic replacement replaces a destination symlink itself; it does not overwrite
the symlink's unrelated target. Aliases of the source remain refused. These
behaviors are tested without modifying authoritative repository artifacts.

## Verification

- `python3 -m pytest -q tests/test_publication_build.py tests/test_preservation.py tests/test_publication_false_confidence.py tests/test_publication_release_authority.py`
  — **78 passed**, including 20 new compile tests.
- Tests cover exact bytes across multiple hash chunks (BOM, CRLF, Unicode,
  NUL/non-UTF-8 bytes), empty content, source edit/removal after copying,
  interrupted copies, staged-hash failure, failed replacement, corruption
  immediately before/after replacement, readback failure, later-stage drift,
  source aliases, destination symlinks, ordinary provenance, and dry runs.
- An independent review found no blocking defect in the implementation or tests.
- All six known Reader failures were independently reproduced on an isolated
  `git archive` of the exact baseline: **6 failed**. They match the six nodes
  listed in the [prior verification record](2026-09-22-preservation-build-digests.md#validation):
  five markup/binding assertions and the Node harness missing
  `_crSyncPageSpeechControls`.
- `python3 -m pytest -q --tb=short`, with local socket and child-process access:
  **1588 passed, 6 failed, 21 skipped**, with 5 dependency deprecation warnings,
  in 94.99 seconds. All six failures match the independently reproduced Reader
  baseline; no newly failing tests were observed. The full suite remains red
  because those existing failures are unresolved.

## Boundary and remaining work

This establishes equality at the post-publication and pre-record verification
boundaries. It does not claim permanent protection against arbitrary writers
after verification. The artifact and `build.json` are still separate files;
atomic replacement of one artifact is not a transaction over the publication
directory. A detected post-replacement failure may leave the newly emitted
artifact, other outputs, and an older build record on disk. This existing
whole-build atomicity gap remains open; the failure diagnostic exposes it.

No locking/immutability protocol, whole-build rollback, crash durability or
directory `fsync`, source snapshot across all stages, timestamp policy, release
policy, or signature machinery is introduced. Cross-platform behavior and
hosted CI have not been validated. Private temporary storage is cleaned on
handled failures; abrupt process termination may leave staging for inspection.

The next bounded provenance packet is the independently identified manifest
race: parse and hash the same captured manifest bytes, with a deterministic
test that replaces the manifest between load and build-record emission. Keep
that repair separate from publication transactions and release policy.
