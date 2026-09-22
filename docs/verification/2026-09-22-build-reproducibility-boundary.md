# Build and preservation reproducibility: measured boundary

**Date:** 2026-09-22

**Starting commit:** `acf753ac987f599d2ff7e0322e1d8b38b2dde22d`

**Classification:** Tests and evidence only; production repair stopped at a provenance-semantics boundary

**Environment:** macOS, Python 3.13.5, pytest 9.1.0, Node.js 22.17.0

## Result

Identical authoritative input bytes are insufficient for byte-identical complete
build/preservation records. Two independent sources of divergence are measured:
operation timestamps and recorded filesystem paths. The emitted paper itself
remains byte-identical.

With identical paths and injected operation times, all collected build,
verification, and export file contents are byte-identical in the tested fixture
and runtime. Distinct staging paths, Python hash seeds, timezone settings, input
modification times, and file creation order did not introduce additional
divergence in the controlled tests. This conditional result is not a claim of
reproducibility for ordinary executions at different times or locations.

No production code, timestamp, path convention, schema, historical record,
release decision, or publication authority was changed.

## Measurement protocol

The committed tests are in
[`tests/test_publication_reproducibility.py`](../../tests/test_publication_reproducibility.py).
They create a temporary corpus containing a manifest, Blueprint, evidence,
compiled manuscript, and fixed steward-history fixtures. Every run asserts that
the input bytes remain unchanged.

Each run starts without either output directory, calls the real `cmd_build`,
`cmd_preserve_verify`, and `cmd_preserve_export`, and captures every output file's
raw bytes. For repeat runs at the same paths, previous output directories are
moved into a separate temporary archive rather than reused. Verification must
report overall `pass` in every run.

Coverage and release JSON are fixed synthetic downstream inputs supplied between
build and preservation. These fixtures isolate the requested build/preservation
surfaces; coverage/release generation is not measured. Fixture signatures are
not actual steward decisions. The tests never touch tracked publications.

Clock injection is test-only. Build times are 12:00 and 12:01 UTC; preservation
times are 13:00 and 13:01 UTC on 2026-09-22. This makes each cause repeatable
without sleeping or depending on scheduler timing. No production clock is
overridden. No timestamp or path is removed, rewritten, or normalized for byte
comparison. Parsed JSON is used only after raw comparison to identify changed
fields.

## First result and controlled comparisons

The first test was run before other measurement cases were added or any repair
was considered. It passed by demonstrating the smallest concrete build-record
difference: **only `build_timestamp` changes within `build.json` when only the
build clock changes**. Input digests, compiled digest, and all other build fields
remain identical. This is a characterization of divergence, not a passing
assertion that ordinary builds are reproducible.

| Controlled variation | Observed differing files/fields |
|---|---|
| Build time only; same root, preservation time, and inputs | `build.json`: only `build_timestamp`; `coverage.md`: generated time; exported copy of `build.json`: same changed bytes; package manifest: only that copy's digest. Four files differ. |
| Preservation time only; identical build bytes and paths | Verification JSON: only `generated_at`; verification Markdown: generated time; package manifest: only `packaged_at`. Three files differ. |
| Project root only; identical input bytes and operation times | `build.json`: `blueprint.path`, `compile.source`, `manifest_path`, and five `outputs.*` paths; verification JSON: reconstruction `path` fields; package manifest: `original_path` entries plus copied build-record digest; exported build-record copy. Four files differ. |
| Distinct private staging directory names; fixed root/time | No differing output bytes. All four staging paths across two runs are distinct, are absent from records, and are cleaned afterward. |
| Separate processes: hash seed `1` versus `8675309` | No differing output bytes with root/time fixed. |
| Separate processes: timezone `UTC` versus `Pacific/Honolulu` | No differing output bytes with injected UTC operation times. |
| Input filesystem modification times changed | No differing output bytes with root/time fixed. |
| Reversed input file creation order | No differing output bytes with the same manifest bytes and root/time. |

The last four variations are applied separately against a baseline, not bundled
into one comparison. Full raw-byte equality includes JSON key ordering, array
ordering, and formatting. Reordering manifest content is not used as a control:
that would change the authoritative input bytes.

Source inspection agrees with these observations: build and preservation loops
follow fixed lists or manifest order; the coverage ghost-path set is sorted
before reporting. Temporary compile/record paths are not persisted. Current
engine-version fields are fixed strings, not detected host metadata. This audit
does not cover every possible branch or malformed input.

## Why no production repair was made

[Constitution Article II](../00_Constitution.md#article-ii--auditability-over-determinism)
and [CI-010](../02_Constitutional_Invariants.md#ci-010--deterministic-reproduction)
require deterministic reproduction while preserving complete provenance for
nondeterministic execution.
[Sprint 002](../sprints/sprint_002_publication_build_spec.md) promises the same
outputs/provenance from the same inputs and explicitly includes `build_timestamp`
in the build record. [Sprint 005](../sprints/sprint_005_preservation_layer_spec.md)
requires preserved artifacts to remain unchanged and records their original paths.

The inspected authorities do not settle whether record identity describes an
individual execution event or a repeatable result independent of when and where
it ran. They do not authorize substituting a source epoch for event time or
discarding filesystem origin information. Converting existing path fields also
affects consumers that resolve them; it is not merely sorting serialized keys.

Deleting timestamps, freezing them in production, or normalizing historical
records would silently choose what information Hermeneia preserves. No mechanical
repair found in this packet resolves that boundary. The user explicitly required
a stop before making that decision, so this packet commits the measurements and
leaves production behavior intact.

## Validation

- First required result:
  `python3 -m pytest -q tests/test_publication_reproducibility.py --tb=short --show-capture=no`
  — **1 passed**, demonstrating clock-only divergence before adding the remaining
  measurement cases. The completed measurement file contains five tests.
- `python3 -m pytest -q tests/test_publication_reproducibility.py tests/test_publication_build.py tests/test_preservation.py tests/test_publication_false_confidence.py tests/test_publication_release_authority.py --tb=short --show-capture=no`
  — **186 passed** with the final measurement matrix.
- Independent review found no hidden normalization or unsupported equality claim.
  The final matrix varies environment conditions individually and keeps both
  preservation timestamps later than both build timestamps.
- All six Reader failures were independently reproduced from an isolated archive
  of exact starting commit `acf753ac987f599d2ff7e0322e1d8b38b2dde22d`, with package
  imports and Reader HTML paths verified inside that archive: **6 failed in
  0.12 seconds**. They are the
  [same six recorded nodes](2026-09-22-preservation-build-digests.md#validation):
  five markup/binding assertions and the undefined `_crSyncPageSpeechControls`
  Node harness reference.
- `python3 -m pytest -q --tb=short`, with local socket and child-process access:
  **1696 passed, 6 failed, 21 skipped**, with 5 dependency deprecation warnings,
  in 96.06 seconds. All six failures match the independently reproduced Reader
  baseline; no newly failing tests were observed. The full suite remains red
  because those existing failures are unresolved.
- `git diff --check` passed. Only the new measurement tests, this evidence
  record, and the documentation index changed; production and authority files
  are untouched.

## Remaining unknowns and exact next bounded packet

This is one fixture and one runtime. Cross-platform text encoding/newlines,
dependency-version changes, different filesystem implementations, and hosted CI
remain unverified. File contents are compared; filesystem metadata and any
compressed archive container bytes are not. The existing compiled-artifact
export omission is unchanged and does not become package-completeness evidence
because the exported files match.

The next bounded packet is a **steward decision about reproducibility identity**:
decide whether separate executions must have identical complete provenance
records or whether their truthful execution history is intentionally distinct,
and specify the byte-comparison boundary accordingly. Resolve the status of
operation timestamps first, then recorded local paths. Preserve the current
measurements and historical records while that decision is made; do not begin
an implementation that assumes either answer.
