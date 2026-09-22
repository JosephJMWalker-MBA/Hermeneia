# Atomic replacement of the build provenance record

**Date:** 2026-09-22

**Baseline:** `4dc7b0e2353da62c3b50d6daa8fe78efa44ccf79`

**Classification:** Build implementation mechanics; single-file replacement

**Environment:** macOS, Python 3.13.5, pytest 9.1.0, Node.js 22.17.0

## Invariant and governing boundary

During replacement by `herm build`, `build.json` exposes either the previous
complete record or the complete new record. Incomplete writes remain in private
staging. With no prior record, the destination remains absent until replacement.
Success additionally requires installed bytes to equal the intended serialized
bytes exactly.

The governing sources are the [Constitution](../00_Constitution.md), Articles I,
II, and VI, and [Sprint 002](../sprints/sprint_002_publication_build_spec.md),
particularly provenance invariant 3, failure invariant 4, and stage 8. The record
retains its existing role as build provenance; this does not promote compiler
outputs into constitutional evidence or change publication authority. Whole-build
transaction semantics, schema, and release policy are unchanged.

## Original ordering and reproduced failures

At the baseline, `_emit_build_json` constructed the mapping, checked the compiled
artifact and manifest, evaluated `json.dumps`, then called `Path.write_text`
directly on `build.json`. That call opened/truncated the destination before text
encoding, writing, and closing. No staging, replacement, or readback followed.

Before production edits, 28 adversarial cases were added and run:

`python3 -m pytest -q tests/test_publication_build.py -k build_record --tb=short`

Result: **28 failed, 42 deselected**. This includes assertions for newly required
staging/replacement hooks and controlled error types, not 28 independent defects.
In particular, no staging or atomic-replacement operation existed to fail in
the baseline; injecting those failure hooks did not stop its direct write.

The demonstrated distinctions were:

| Failure point | Baseline behavior |
|---|---|
| Unsupported object / circular JSON structure | Serialization raised before destination opening; prior bytes survived, but errors escaped the CLI's `BuildError` handling. |
| Text encoding | Encoding could fail after truncating the destination. |
| Open / write / flush / close | I/O errors escaped without a controlled build failure; errors after opening could leave empty, partial, or newly written bytes. |
| Silent short write | The emitter accepted incomplete bytes without checking them. |
| Process interruption | A child process wrote and flushed 16 bytes, then exited immediately with code 73; the destination contained only `{"build_id": ...`'s opening prefix rather than the previous record. |
| Atomic replacement | Absent: readers and linked aliases observed an in-place rewrite. |

The interruption witness actually terminated a subprocess using `os._exit`,
without relying on sleeps or thread scheduling. The observed 16-byte output was
`b'{\n  "build_id": '`. All destructive tests used temporary fixture publications.

## Repaired ordering

1. Serialize fully using the existing indentation and `ensure_ascii=False`, and
   encode the intended UTF-8 bytes before opening an output file. No terminal
   newline is added; existing JSON field/acceptance rules remain unchanged.
2. Create a private `.herm-build-record-*` directory within the output directory,
   keeping staging on the destination filesystem.
3. Write the bytes to staged `build.json`, flush, and close the stream.
4. Read staging and require exact equality with the intended bytes. This prevents
   a silent short write or corrupted staging content from becoming visible at
   the destination.
5. Recheck the compiled artifact and captured manifest immediately before
   replacement. Their verification is not left ahead of serialization/staging,
   where later mutation could make the new provenance stale.
6. Atomically replace the destination with `os.replace` exactly once.
7. Read the installed path and require exact equality with the intended bytes
   before returning success.

Expected serialization, encoding, and I/O errors become `BuildError`; the CLI
exits 1 without announcing success. Pre-replacement failures preserve prior
bytes, or prior absence, unchanged. Handled failures clean private staging.
If replacement succeeds and an error is then reported, or installed readback
fails, the emitter does not delete the destination or blindly restore an older
record. It fails closed while leaving whatever installed state remains.

Destination symlinks/hardlinks are replaced rather than written through; linked
targets remain unchanged. Readers holding an old file descriptor continue to
read the previous complete record. Replacement creates a new inode and does
not preserve the prior inode's metadata or ACLs.

## Verification

- Initial adversarial run on unchanged production code: **28 failed, 42
  deselected**. After the repair, those same cases passed. Additional cases then
  covered absent destinations, staged read failure, same-length corruption,
  input mutation during staging, and CLI failure reporting.
- `python3 -m pytest -q tests/test_publication_build.py tests/test_preservation.py tests/test_publication_false_confidence.py tests/test_publication_release_authority.py --tb=short`
  — **142 passed**, including 42 new record cases.
- Tests observe old destination bytes throughout staging and complete new bytes
  after replacement, check that staging is private and closed before replacement,
  compare installed bytes to intended Unicode JSON, inject faults at each I/O
  boundary, and terminate a subprocess during a partial write with and without
  a previous valid record.
- Independent review found no blocking defect. A test was adjusted to distinguish
  the new record by an explicit value rather than assuming timestamp advancement.
- The six Reader failures were independently reproduced from an isolated archive
  of exact baseline `4dc7b0e2353da62c3b50d6daa8fe78efa44ccf79`, with archive-local
  imports and Reader fixtures: **6 failed in 0.11 seconds**. They match the
  [six recorded nodes](2026-09-22-preservation-build-digests.md#validation): five
  markup/binding assertions and the undefined `_crSyncPageSpeechControls` Node
  harness reference.
- `python3 -m pytest -q --tb=short`, with local socket and child-process access:
  **1652 passed, 6 failed, 21 skipped**, with 5 dependency deprecation warnings,
  in 91.77 seconds. All six failures match the independently reproduced Reader
  baseline; no newly failing tests were observed. The full suite remains red
  because those existing failures are unresolved.
- `git diff --check` passed. Only the build implementation, its tests, this
  verification record, and the documentation index changed.

## Limits and next bounded packet

The visibility guarantee concerns this writer's replacement under ordinary
same-filesystem atomic-rename semantics. It does not prevent arbitrary external
writers from changing either path between verification steps or afterward.
Detected installed divergence fails closed without adopting the changed bytes.
No file/directory `fsync` or power-loss durability guarantee is introduced.
Abrupt process termination can leave private staging for inspection; the tests
confirm that its partial bytes never appear at the destination.

Other publication outputs are still separate writes. They may contain a newer
build while an earlier `build.json` remains after failure; this packet neither
solves nor hides that existing whole-publication consistency gap. Cross-platform
behavior and hosted CI have not been verified.

The next bounded packet is a tests-first audit of preservation reconstruction:
build a valid fixture, mutate only the emitted `white_paper.md` while retaining
its recorded `compile.sha256`, and establish whether `herm preserve verify`
rejects that mismatch. If it does not, enforce that existing digest comparison
without changing packaging, authority, or whole-build transaction semantics.
