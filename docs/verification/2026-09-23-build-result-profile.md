# First build-result reproducibility profile

**Starting commit:** `e79778a9bb922078db98a34ee1f8c845f35193f9` (local and remote `main`).

**Scope:** Implement the steward-accepted first build-result profile. No historical
migration, preservation-package equivalence, release equivalence or authority change.

The active implementation contract is
[`build-reproducibility.spec.md`](../specs/build-reproducibility.spec.md).
The earlier [design and inventory](../design/build-preservation-reproducibility.md)
and [raw-record divergence measurements](2026-09-22-build-reproducibility-boundary.md)
remain historical evidence. This packet changes the comparison boundary; it does
not remove truthful provenance to make complete records equal.

## Demonstrated starting gap and resulting invariant

Before integrating production bindings, two new tests failed deterministically:
a successful build emitted no `build.reproducibility.json`, and no read-only
build-result comparison implementation existed. Command:

```text
python3 -m pytest -q tests/test_build_reproducibility.py --tb=short --show-capture=no
2 failed in 0.09s
```

The strengthened invariant is: supported complete builds identify exact authoritative
inputs/results with one strictly encoded deterministic core, while execution records
remain exact-byte evidence bound to that core. Only two independently verified,
compatible, complete cores can compare `equivalent` or `different`. Missing/mixed
coverage, unsupported locators or profile versions refuse comparison; corruption
has a separate invalid-integrity result. Comparisons do not write artifacts.

## Implementation

- `hermeneia/build_core.py`: strict codec, complete schema/type checks, unchanged
  design golden vectors, domain-separated core digest, current-copy-build projection
  and internal consistency checks. Array occurrences and exact strings survive.
- `hermeneia/build_reproducibility.py`: captured manifest/record/artifact checks,
  confined reads, complete atomic binding publication, read-only verification and
  comparison, field-level differences and independent execution-evidence reporting.
- `hermeneia/cli/build_cmd.py`: capture each historical output digest immediately
  after its emission; bind the existing record's intended serialized bytes; preserve
  existing record serialization/publication checks. Unsupported legacy-valid builds
  explicitly lack a new supported binding; no partial core or backfill.
- `hermeneia/cli/build_compare_cmd.py` and `main.py`: additive `herm build-compare`
  command with explicit roots and distinct equality/difference/unsupported/invalid
  exit behavior. Existing build flags and interpretation comparison are retained.

Binding publication serializes first, writes privately, flushes/closes, verifies
staged bytes, rechecks captured evidence, replaces atomically, verifies installed
bytes and checks evidence again. An old sidecar surviving a failed new publication
cannot validate changed `build.json` bytes. No multi-file rollback is promised.

Existing preservation/release implementations, tracked publications, design golden
fixtures and historical records are unchanged. Earlier measurement tests now account
for the additional sidecar and its third staging directory; their original raw
timestamp/path divergence assertions remain. The independent design oracle now
also checks that the production core matches its proposed core exactly.

## Adversarial evidence and review

The new suites cover:

- Exact committed canonical bytes/digests, malformed encoding, duplicate JSON keys,
  floats/nonfinite values, integer limits, surrogate rejection, cyclic values,
  Unicode/newline preservation, source/section order and incomplete schema refusal.
- Equivalent results under distinct roots and deterministic injected event times;
  execution evidence remains different and truthful. Different paper/source bytes,
  obligations/configuration and historical contents/dates produce different valid
  cores rather than being normalized away.
- Detached digest, modified record, modified/rehashed inconsistent core, changed
  source/paper/history, missing required artifacts and incompatible/mixed coverage.
  Legacy records still work with old readers and preservation verification.
- Read-only snapshots of contents and modification times; no new comparison outputs.
  Manifest mutation after capture and first-run drift while reading the second run
  are detected, not adopted as replacement inputs.
- Staging creation, partial write, flush, interruption, staged readback, replacement
  failure, installed corruption and record mutation at binding installation. Previous
  bindings survive pre-replacement failures; stale pairs fail closed afterward.
- Authored absolute references are retained but unsupported; wrong roots and symlink
  escape cannot establish equivalence even with identical bytes.

Independent review found three issues in the initial implementation and all were
repaired before final validation: NUL locators could escape structured error handling;
resolve/check/open permitted a symlink race before later drift detection; and
comparison initially omitted field-level differences. The final tests replace both
the leaf and a parent with outside symlinks after resolution, assert that outside
bytes are never read, and verify refusal even when those bytes match. Directory
descriptor traversal and no-follow opens enforce this boundary. Re-review independently
passed 115 codec/binding tests and found no remaining integrity/equality blocker.
Execution-record/envelope differences were also added independently of core identity.

## Real-input witness

An isolated manual witness copied the current manifest and its 14 required input
files, including historical output source documents, into two fresh temporary roots.
Both used real clocks and the real build command. Neither overwrote the repository's
publication directory. Original input bytes were checked unchanged afterward.

Witness directory: `/private/tmp/herm-build-core-real-inputs-nvi95q6p`.
This disposable path is diagnostic location evidence, not required result identity.

Both runs verified and compared `equivalent` with no core differences:

```text
core SHA-256 (both): c5ee8068ba0cf4b5dd40314b89bb16c8c7a759303f80ce58e9b6427348e74dda
first record SHA-256: edbdda7b27d46a48af21b485ad77fefc0e491d5c33d29d6b1123dcd5ebc4fec7
second record SHA-256: d1dcadbd34bfe68956d05474c990701f7265227f601d39d89f48add714daa76d
execution_evidence_changed: true
```

This is one runtime and filesystem with the current input set, not a cross-platform
claim or an assertion about publication/release eligibility.

## Regression validation

Environment: macOS 26.6.2 arm64, Python 3.13.5, pytest 9.1.0, Node.js 22.17.0.

- Focused:
  `python3 -m pytest -q tests/test_build_core_codec.py tests/test_build_reproducibility.py tests/test_reproducibility_core_design.py tests/test_publication_reproducibility.py tests/test_publication_build.py tests/test_preservation.py tests/test_publication_false_confidence.py tests/test_publication_release_authority.py --tb=short --show-capture=no`
  — **324 passed**, 5 dependency deprecation warnings, in 2.77 seconds.
- Independent baseline: a pristine archive of exact starting commit `e79778a`
  reproduced all [six known Reader nodes](2026-09-22-preservation-build-digests.md#validation)
  — **6 failed in 0.12 seconds**. Imports, test modules and Reader HTML paths all
  resolved inside `/private/tmp/hermeneia-build-core-baseline.e803dc70`.
  Five failures are markup/binding assertions and one is the existing Node harness
  `_crSyncPageSpeechControls` ReferenceError.
- Full suite: `python3 -m pytest -q --tb=short --show-capture=no`, with required
  local socket/child-process access — **1834 passed, 6 failed, 21 skipped**, 5
  dependency deprecation warnings, in 97.57 seconds. All six failures match the
  independently reproduced Reader baseline; no newly failing tests were observed.
  The full suite remains red because that baseline is unresolved.
- Final scope review and `git diff --check` passed. No preservation/release code,
  tracked publication, historical golden fixture or constitutional document changed.

## Remaining boundaries and exact next packet

No field required an unapproved authority/classification change. Authored local
references remain unsupported where equivalence would require normalizing the exact
manifest identity. Old/mixed records cannot gain missing build-time core evidence by
reading current files. These are explicit refusal boundaries, not silent omissions.

The filesystem verifier requires POSIX-style confined-open primitives; other runtime
platforms and filesystems remain unverified/unsupported where those primitives are
absent. Digests do not authenticate wholesale replacement of all evidence. Readable
report custody, historical adapters, power-loss durability and whole-build transactions
remain out of scope. Current preservation export still omits the compiled artifact
and does not carry these bindings; this packet makes no package-completeness claim.

Next bounded packet: attach a preservation **verification report envelope** to an
already validated build core and exact report bytes, preserving all negative findings,
legacy verification and non-mutation of the artifacts examined. Keep package/release
equivalence and historical migration out of that packet.
