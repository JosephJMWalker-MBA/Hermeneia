# Preservation verification input provenance

**Status:** Implemented additive integrity contract; VS001-F02 sibling-resolution
completion and historical association compatibility authorized 2026-09-23.

**Authority:** Steward authorization to bind verification reports to the validated
[build-result v1 core](build-reproducibility.spec.md) they actually evaluated.
Subordinate to the existing preservation specification and constitutional authority.
No preservation-package identity, release identity, report custody policy, or new
artifact authority is defined here.

## Existing findings and new binding integrity

`herm preserve verify` retains its check definitions, summary algorithm and exit
status rules. Corrected sibling resolution can change which inputs and findings
those rules evaluate. Reports carry a `provenance` object with schema
`hermeneia.preservation-verification-inputs/v2`. Version 2 completes VS001-F02
sibling resolution. Binding integrity is independent of the preservation outcome: a correctly bound report can contain `FAIL`, and a
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
    b"Hermeneia preservation verification inputs v2\n"
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

With `--build`, the selected build's parent establishes one resolved namespace
for the build, its adjacent build binding, `coverage.json` and
`release_recommendation.json`. Coverage/release interpretation and reconstruction
presence/hash checks use the same sibling lookup paths and byte captures. There
is no conventional `publication/` fallback. Missing siblings retain FAIL presence
findings even when other copies exist; malformed sibling JSON still aborts.

The namespace is pinned before reading and checked when capturing and rechecking
these inputs. Leaf redirection into another namespace is refused, including when
the other bytes are identical. Directory aliases are permitted only when these
lookups resolve consistently to the selected parent. Later drift invalidates the
core claim. Declared manifest, source, compile source and historical/output paths
retain their existing project-root/recorded semantics: they are not relocated
under the selected build. The original 13-path witness now has 11 distinct inputs,
as the two coverage and two release observations share their respective captures.
Sibling selection neither authenticates a signature nor defines release identity.

## Read-only report association check

The Python API `hermeneia.preservation_provenance.verify_report_binding` accepts a
machine-report path, build-record path and explicit `project_root`. It reads the
report once, evaluates the current inputs using shared captures, and checks:

1. Supported report receipt and verifier versions; unambiguous sibling association
   evidence and an actual validated core claim.
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

### Historical association compatibility

Version 1 receipts are immutable observations of the old verifier. Before current
input evaluation, the association API inspects only their recorded lookup paths,
resolved paths and roles, without resolving historical locators on today's disk.
Exactly one selected-build observation and one observation per coverage/release
interpretation/reconstruction role must establish the same sibling paths in both
lookup and resolved namespaces. Missing, null, duplicate or mixed association
evidence returns:

```json
{"integrity": "unsupported", "compatibility": "legacy-unsupported-association", "reason": "..."}
```

This result carries neither a core claim nor a reevaluated finding outcome. It
never promotes an old PASS, FAIL or WARN into a corrected-contract success. Current
files with matching names, locations or bytes cannot fill that historical gap.
Version 2 namespace inconsistencies are invalid, not eligible for legacy fallback.

A fully unmixed v1 receipt (including the conventional default) remains eligible
for exact association. The current captured receipt is encoded **in memory** under
v1's original schema and `Hermeneia preservation verification inputs v1\n` domain,
then compared to the entire recorded receipt. All original findings and summaries
must still match. No old bytes, paths, digests or findings are rewritten. Reports
without supported receipts remain unsupported; no historical backfill is allowed.
The engine label `0.1.0` and build-core profile remain unchanged; receipt v2 marks
the corrected input-resolution contract.

No new CLI command or preservation exit status is introduced. Existing CLI users
must inspect the additive provenance field when they need a validated core claim.
Custom builds can now correctly exit 1 for missing siblings that previously passed
using unrelated conventional files. A valid association of a negative report still
returns its negative `findings_outcome`; provenance is not preservation approval.

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

The [F02 completion evidence](../verification/2026-09-23-F02-sibling-resolution.md)
records the steward decision, immutable old witness and current validation.
Report generation retains its explicit output/replacement behavior; use a fresh
`--output` directory when retaining historical reports. Association never writes.
No retention, report custody or migration policy is introduced. Export, edition
advisories, producer defaults and package/release equivalence remain outside F02.
