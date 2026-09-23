# Build-result reproducibility v1

**Status:** Accepted first profile, implemented in the bounded build-result packet.

**Date:** 2026-09-23

**Authority:** Steward acceptance of the first profile in
[`build-preservation-reproducibility.md`](../design/build-preservation-reproducibility.md),
with the locator and historical/mixed-coverage decisions below. Subordinate to the
Constitution, Authority Index and constitutional invariants. No new canonical
object, publication authority, release identity or preservation-package identity.

## Result and execution are distinct

For this profile, the reproducibility promise in
[Sprint 002](../sprints/sprint_002_publication_build_spec.md) applies to the
deterministic build-result core. Complete execution records retain truthful event
timestamps and locations and need not be byte-identical. This narrows that
specification's whole-record equality wording; all provenance and stewardship
obligations remain in force. The earlier document and existing records are retained.

Supported new `herm build` executions additionally emit
`publication/build.reproducibility.json` (or beside `build.json` under `--output`).
Existing `build.json`, Markdown content, paths and CLI build flags keep their
meaning. No old record is rewritten to add a core. The sidecar contains:

```text
schema: hermeneia.reproducibility-binding/v1
core:
  schema: hermeneia.build-result/v1
  result: <complete accepted profile>
envelope:
  core_sha256: <core digest>
  records:
    - role: build-record
      path: <actual build.json locator>
      sha256: <SHA-256 of exact serialized build.json bytes>
```

The first binding profile requires exactly that one record role. Partial or mixed
profiles are unsupported. No fallback drops unknown fields to manufacture equality.

## Complete core and encoding

The core contains exactly the accepted design's fields: `build_id`,
`manifest_hash`, Blueprint ID/status/digest, ordered source declarations and
digests, ordered structured coverage results, compile method/digest, critic enabled
state, descriptive manifest release status/ratification, and exact emitted
`rc_log.md`/`release_decision.md` hashes. Descriptive release fields and preserved
historical document bytes are build inputs/results; equality does not establish
release equivalence or grant approval. No release-record profile is implemented.

Source and section order, duplicates, whitespace, spelling and Unicode code points
are retained. Build counts/outcome, draft flag and repeated Blueprint status must
agree with the core. The copy method, ratified Blueprint and deferred manual critic
are required. Structured coverage must reproduce the current tag algorithm. Only
its known missing-tag warnings may be projected out as execution prose; a new
warning category requires profile review. Engine version is retained in the exact
bound build record, separately from core/profile versions.

The canonical serialization and committed golden vectors remain unchanged:

```python
json.dumps(core, sort_keys=True, ensure_ascii=True,
           separators=(",", ":"), allow_nan=False).encode("utf-8")
```

Validation precedes encoding. Strict UTF-8 JSON rejects BOM, duplicate keys,
floats, NaN/Infinity, non-string keys, lone surrogates, cyclic/deep values and
integers outside `[-9007199254740991, 9007199254740991]`. Keys sort by Unicode code
point; arrays retain order. No Unicode, newline, YAML, artifact or path normalization.
No trailing newline enters the encoding. Unsupported profile fields/types are
refused; malformed digests and contradictory evidence are invalid.

```text
core_sha256 = lower_hex(SHA256(b"Hermeneia reproducibility core v1\n" + canonical_core_bytes))
record.sha256 = lower_hex(SHA256(exact captured build.json bytes))
```

`compile.sha256` and all old input hashes retain their raw-byte SHA-256 meanings.
The envelope and its paths never enter the core digest. Hashes establish binding,
not authenticity of a writer able to replace the entire evidence set.

## Locator proof and unsupported references

The steward permits exclusion of a local reference from result identity only when
its locator-only role and matching authoritative content are established. The
implementation proves this for execution-added locations: the caller supplies
each project root, captured manifest declarations establish roles/occurrences,
recorded locations must agree with those declarations, and all required exact
artifact hashes must verify. Identical portable manifest bytes at different roots
can therefore yield equal cores without rewriting either execution record.

The v1 core still includes the exact captured manifest digest and source reference
strings. Authored absolute paths, traversal/ambiguous spellings and references whose
exclusion would require normalizing the manifest remain **unsupported**. This is
not a claim that every authored absolute path is semantic; it is a refusal to
invent a different manifest identity scheme. Exact authored references remain in
the original manifest and bound build record. Additional authored manifest fields
such as `artist`, `critics` and configuration remain covered by the raw manifest
digest, even if the copy compiler does not execute them.

Lookup stays inside each explicit caller root; no old-root inference, basename
matching or suffix remapping. Reads use directory-descriptor traversal with
no-follow opens for parents and leaf, then require a regular file. A symlink
replacement between resolution and opening must not cause an outside-root read.
Platforms lacking these primitives are unsupported for binding/comparison; their
legacy build/read contracts are not migrated. This implementation has been tested
on macOS, not certified across platforms or filesystems.

## Emission and failure boundaries

1. Capture each historical output's raw hash immediately after that output's
   copy/write completes. Never backfill an older run from current files.
2. Serialize the legacy build record using its existing format. Derive the core
   from the build's captured representations and historical emission hashes;
   verify manifest/record consistency and required artifact bytes against them.
3. Install `build.json` through its existing atomic staging/readback procedure.
4. Bind those exact intended serialized record bytes. Privately stage the complete
   canonical sidecar on the destination filesystem, flush/close, verify staged
   bytes, recheck captured record/artifacts, atomically replace, verify installed
   bytes and recheck for drift. No partial sidecar is authoritative.

Pre-replacement sidecar failures retain the prior sidecar unchanged. If the new
build record was already installed, a surviving previous sidecar is stale and
comparison fails closed. This is individual-file atomicity, not a whole-build
transaction, rollback or power-loss durability guarantee. The build reports
failure for invalid provenance/I/O failures; already emitted outputs may remain.

An otherwise legacy-valid build outside profile eligibility continues under its
existing contract with an explicit `Reproducibility unsupported` diagnostic and
no new sidecar. An older sidecar is not deleted or reinterpreted; if its raw record
hash no longer matches, verification reports invalid evidence. Unsupported results
are never presented as reproducible merely because a sidecar filename exists.

Readable `coverage.md` custody remains outside v1. That report is later overwritten
by `herm coverage`. Exact historical output documents are required core content;
their dates and signatures are never stripped. Preservation export remains unchanged
and does not acquire package equivalence or a core binding through this feature.

## Read-only comparison

```bash
herm build-compare /work/a/publication/build.json /work/b/publication/build.json \
  --left-root /work/a --right-root /work/b
```

Both roots are required. `herm compare` retains its interpretation-comparison role.
The command emits JSON and does not write any artifact, migrate records, regenerate
content, or replace missing build-time evidence with current hashes.

Each file is captured once for interpretation/hashing; later reads only check for
drift and never replace the capture. Validate both bindings, complete compatible
profiles, raw execution-record digests, manifest agreement, derived facts and all
required artifacts: manifest, Blueprint, declared sources, copy source, emitted
paper and both historical output documents. Recheck the first execution after
capturing the second. Unavailable required evidence prevents verified equality.

| Comparison | Per-side integrity | Meaning | Exit |
|---|---|---|---|
| `equivalent` | both `valid` | Canonical cores and recomputed core digests match | 0 |
| `different` | both `valid` | Valid complete cores differ; deterministic JSON-pointer `differences` identify fields and values | 1 |
| `unsupported` | at least one `unsupported`, none invalid | Legacy/missing/mixed coverage, incompatible version, unsupported locator or platform | 2 |
| `unsupported` | at least one `invalid` | Corruption, detached/stale binding, missing declared artifact, contradictory evidence or detected drift | 3 |

Reasons accompany unsuccessful integrity checks. A corrupt artifact is invalid
evidence, not another valid result. The command's comparison labels and exit codes
are separate from preservation outcomes and release states.

Valid sides also report their bound raw `record_sha256` and a diagnostic
`envelope_sha256` (raw SHA-256 of canonical envelope JSON, without the core domain
prefix). `execution_evidence_changed` compares the latter independently of core
equality. These diagnostics do not enter result identity or replace original
provenance; equal results normally have different execution evidence.

Legacy records remain readable/verifiable through previous commands. Without a
supported complete binding they return explicit insufficient evidence here; they
are neither guessed into v1 nor declared historically invalid solely for being old.

## Limits and next boundary

No classification required silently changing authority. Implementation confirms
two important limits: raw authored manifest identity cannot be normalized within
v1, and historical hashes absent from old build records cannot be recovered as
build-time facts. Missing/mixed coverage remains a refusal, per steward decision.

Verification observes a bounded capture and recheck sequence, not an indefinitely
locked filesystem or authenticated publisher. Malicious replacement of all evidence
and recomputation of hashes is outside unsigned digest integrity. Release signing,
preservation-package completeness/equivalence, historical adapters, power-loss
durability and whole-publication transactions remain separate work.

The subsequent bounded packet implements
[preservation verification input provenance](preservation-verification-provenance.spec.md):
reports reference an already validated build core and exact captured verification
inputs while retaining all existing negative findings and read-only artifact
behavior. This does not introduce preservation-package or release equivalence.
