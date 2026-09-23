# Preservation verification input provenance

**Status:** Implemented additive integrity contract, 2026-09-23.

**Authority:** Steward authorization to bind verification reports to the validated
[build-result v1 core](build-reproducibility.spec.md) they actually evaluated.
Subordinate to the existing preservation specification and constitutional authority.
No preservation-package identity, release identity, report custody policy, or new
artifact authority is defined here.

## Existing findings and new binding integrity

`herm preserve verify` keeps its reconstruction and continuation checks, summaries,
overall outcome, and exit behavior. Reports add a `provenance` object with schema
`hermeneia.preservation-verification-inputs/v1`. Binding integrity is independent
of the preservation outcome: a correctly bound report can contain `FAIL`, and a
legacy `PASS` report can lack sufficient evidence to claim a validated core.

| Integrity | Core claim | Meaning |
|---|---|---|
| `valid` | `build_core.profile`, `build_core.sha256` | The supported core, exact build record binding, and required artifact bytes validated from this verification's captures. |
| `unsupported` | Absent | Legacy/missing/incompatible/incomplete coverage, unsupported locator or platform. `reason` states the refusal. |
| `invalid` | Absent | Malformed, detached, mismatched, unreadable required evidence, or detected input drift. `reason` states the refusal. |

No core is reconstructed from current files for a historical build. The descriptive
`build_id` remains for compatibility; by itself it establishes no validated
association. A malformed build/coverage/release JSON input still aborts under its
previous loading contract rather than issuing a successful report.

## Captured inputs and precise digest boundary

One capture context supplies all build/coverage/release JSON interpretation,
manifest interpretation, Blueprint intent scanning, reconstruction hashes, and
build-core validation. Hashing consumes raw captured bytes; text interpretation
retains the previous decoding/newline behavior. Subsequent reads detect drift and
never replace the captured version. Missing observations are cached and rechecked
too; a later file appearance cannot repair an earlier failed finding.

`provenance.inputs` contains the exact lookup path, resolved path and sorted roles
for every observed input (resolved path is null when a malformed locator cannot
resolve). Entries are sorted by lookup-path string. Each records:

- `state: present`, exact-byte `sha256` and integer `size_bytes`;
- `state: missing`, with no invented digest; or
- `state: unreadable`, with the observed `error` and no invented digest.

Roles distinguish `build-record`, `coverage-interpretation`,
`release-interpretation`, `manifest-interpretation`, `reconstruction:<check name>`,
`continuation:Blueprint`, and `build-core-validation`. The latter covers the exact
sidecar and required core evidence, including copy source and historical outputs.
The input list remains a truthful observation receipt even when no core claim is
permitted. Its bytes are not historical build-time evidence.

```text
inputs_sha256 = lower_hex(SHA256(
    b"Hermeneia preservation verification inputs v1\n"
    + canonical_json(provenance.inputs)
))
```

`canonical_json` is the existing strict build-core encoding: sorted keys,
ASCII-escaped JSON, compact separators, UTF-8, no trailing newline or content/path
normalization. This domain applies to the new receipt only. Existing release
signature observations retain their previous JSON value types and ranges; they
do not become core or release identity through this packet.

The core digest retains its existing profile/domain. The receipt digest is an
execution observation, **not** report identity or preservation-package identity.
The machine report carries both in one complete JSON record. Markdown adds the
core claim/refusal and input digest while retaining every existing finding.

With a custom `--build`, existing preservation behavior interprets coverage/release
beside that build but checks the conventional `publication/` files separately.
This packet records **both** locations and roles. It does not silently change that
resolution contract or claim that these distinct files are interchangeable.

## Read-only report association check

The Python API `hermeneia.preservation_provenance.verify_report_binding` accepts a
machine-report path, build-record path and explicit `project_root`. It reads the
report once, evaluates the current inputs using shared captures, and checks:

1. Supported report receipt and verifier versions; an actual validated core claim.
2. Successful current validation of the complete build core and exact record.
3. Exact agreement of the core claim and all input receipts/digests/roles/locations.
4. Agreement of original checks, summaries and outcome with those captured inputs,
   preserving JSON value types (`false`, `0`, and `0.0` are distinct observations).
5. Report-byte and input rechecks before returning valid.

It returns `integrity: valid`, `invalid`, or `unsupported`, with a reason on refusal.
A valid result also returns `build_core` and `findings_outcome`; that outcome can be
`fail`. It never rewrites the report, substitutes new findings, repairs missing
evidence, or declares two packages/reports/releases equivalent. A new build with
the same paper bytes, label, or even core digest cannot inherit an earlier report
whose exact execution/input bytes differ. An old failed report remains intact
after the underlying problem is fixed; its association to the changed inputs is
refused. Historical reports without receipts remain readable under their original
contract but have insufficient evidence for this association check.

No new CLI command or preservation exit status is introduced. Existing CLI users
must inspect the additive provenance field when they need a validated core claim.

## Emission and limits

Examined artifacts remain read-only. Only the two requested report outputs are
written. Known input/output aliases are refused. Reports are fully serialized,
privately staged, flushed/closed, checked, individually atomically replaced and
read back. Replacement detaches hard links rather than truncating input inodes.
On platforms supporting the build-core confined-read contract, the checked report
directory is also pinned by directory descriptor so later parent redirection
cannot redirect the report writes. Unsupported platforms retain the legacy
report path with atomic leaf replacement but cannot claim supported core validation.

This is not a two-report transaction, whole-publication rollback, power-loss
durability guarantee, indefinitely locked filesystem, retention/archive policy,
or authenticated report writer. Someone able to replace all evidence and recompute
digests is outside unsigned integrity. The existing edition advisory printed by
the CLI is not a report finding or input to this receipt. Export/package and release
behavior are unchanged; old reports and records are not migrated.

The next bounded investigation is the existing custom-`--build` split between
interpreted and conventionally checked coverage/release inputs. Establish its
intended resolution contract before changing that behavior; no custody or
preservation-package identity decision is implied.
