# Build result identity and execution provenance

**Date:** 2026-09-22

**Inspected revision:** `8ff6d18728ec1767782c637a903da00d962dad1f` (`main`)

**Status:** Steward decision recorded; detailed design proposed, not implemented.

**Scope:** Build/preservation compiler outputs; no new canonical objects.

**Implementation follow-up (2026-09-23):** The steward accepted the first
build-result profile with conditional locator equivalence and strict historical
coverage refusal. The implemented scope and CLI contract are in
[`build-reproducibility.spec.md`](../specs/build-reproducibility.spec.md).
This dated proposal and its original design-packet evidence remain below;
preservation-package and release profiles remain outside the implementation.

## Decision and authority

The steward's decision for this packet is:

> Hermeneia does not require complete build/preservation execution records to be
> byte-identical across equivalent runs. It requires a deterministic authoritative
> reproducibility core, while preserving truthful run-specific provenance in a
> separate execution envelope.

The envelope must bind cryptographically to the core. This resolves the general
identity question in the [preceding measurement](../verification/2026-09-22-build-reproducibility-boundary.md).
It does not authorize rewriting historical records, migrating production schemas,
or deciding the open field classifications below. This document proposes the
mechanics and a bounded first profile; it does not claim that the steward has
ratified every detail of this proposal.

[Constitution Articles I, II and VI](../00_Constitution.md),
[CI-010/011](../02_Constitutional_Invariants.md),
[Sprint 002](../sprints/sprint_002_publication_build_spec.md), and
[Sprint 005](../sprints/sprint_005_preservation_layer_spec.md) continue to govern.
The core is an identity for a governed compiler result, not a new constitutional
object, a replacement for a SourceDocument hash, or a publication decision.
The older specifications and measured records remain unchanged. A later approved
implementation specification must explicitly narrow Sprint 002's whole-record
reproducibility wording; this draft does not silently supersede it.

## Smallest architecture

Use one **build-result core**. Build execution and subsequent preservation
verification executions can each describe that same result through their own
envelopes. Verification findings are observations about that result; they do not
need a new canonical identity or a second result core.

Initially retain each existing JSON/Markdown record byte for byte. A proposed
additive binding file contains a core and an envelope that references the exact
existing machine records by raw SHA-256. Thus all their timestamps, paths, diagnostics,
engine versions and historical context survive without duplicating every field
in a second metadata schema. "Execution provenance" below means retained in these
records, not deleted. Readable reports remain retained E projections, outside the
first binding profile; their independent timestamps/formatting are not claimed
cryptographically bound. Historical output documents are different: their content
digests belong to the proposed core below. A record may contain copies of core fields as well;
the verifier must check agreement rather than establish two authorities.

Conceptual layout (filenames are proposed, not new production outputs):

```text
build.json                         existing bytes and meaning
build.reproducibility.json         {schema, core, envelope}
preservation_report.json           existing verification observations
preservation_report.md             existing readable report
preservation.reproducibility.json  {schema, core, envelope}
```

The build and verification bindings may contain the identical core. The latter
envelope references both the exact build record and the exact report. Equal core
digests establish the same scoped build result; they do not mean identical
verification observations, successful reconstruction, identical packages, or
permission to release. No binding is emitted by this packet.

## Current field inventory

Inventory is of the actual producers in `hermeneia/cli/build_cmd.py` and
`hermeneia/cli/preserve_cmd.py`, including conditional report fields and internal
export-failure entries. Paths below are JSON pointers with `[]` for an array item.
Container rows have no independent scalar identity; their descendants determine
classification. Manifest-supplied strings/lists are retained exactly. Arbitrary
extra fields inside malformed or loosely typed input values are not silently
approved by this inventory.

**C — reproducibility core:** required result information, sometimes represented
by another bound input or derived from validated core data rather than duplicated.

**E — execution provenance:** exact record retained and bound, excluded from core.

**A — ambiguous:** no generic stripping, migration, or equivalence claim allowed.

**O — obsolete:** none of the currently emitted fields is established as obsolete.
Redundancy, constant values and awkward wording are not deletion authority.

### `build.json`

| Field | Class | Reason / proposed treatment |
|---|---|---|
| `/build_id` | C | Manifest-declared build label; existing cross-record checks depend on it. Keep exact value; equal labels alone never establish identity. |
| `/build_timestamp` | E | Actual build event time, never substituted with a source epoch. |
| `/hermeneia_version` | E | Implementation provenance; retain exact value. It is not a record-schema or comparison-profile version. |
| `/blueprint` | container | Fields below. |
| `/blueprint/path` | E | Resolved local lookup location. Manifest bytes retain the authored reference. |
| `/blueprint/id` | C | Declared Blueprint identity. |
| `/blueprint/status` | C | Declared ratification state, not a new ratification act. |
| `/blueprint/sha256` | C | Exact Blueprint bytes consumed. |
| `/manifest_path` | E | Invocation/local lookup location, sometimes absolute, sometimes relative. |
| `/manifest_hash` | C | Exact captured manifest bytes; never hash a normalized YAML representation. See A1 for authored absolute paths. |
| `/source_artifacts` | container | Declared order and multiplicity retained. |
| `/source_artifacts/[]/path` | A | Authored reference, unlike a constructed absolute locator. Portable relative references are C in the first profile; authored machine-local references require A1. |
| `/source_artifacts/[]/sha256` | C | Exact source bytes; associate with the declared occurrence, not a basename or set of hashes. |
| `/source_artifacts/[]/tags` | C | Declared coverage inputs; preserve order, duplicates and spelling. |
| `/source_artifacts/[]/status` | C | Declared artifact state. |
| `/source_artifacts/[]/role` | C | Declared role used by continuation checks. |
| `/source_artifacts/[]/resolved` | E | Observation that resolution succeeded in this execution. Successful core eligibility requires all declared sources to resolve. |
| `/coverage` | container | Structured build-stage result, distinct from downstream `coverage.json`. |
| `/coverage/sections_evaluated` | C | Derived count; validate against section detail, omit duplicate from proposed core. |
| `/coverage/sections_pass` | C | Derived count; same rule. |
| `/coverage/sections_warn` | C | Derived count; same rule. |
| `/coverage/sections_fail` | C | Derived count; same rule. |
| `/coverage/section_detail` | container | Preserve declared section order and all entries. |
| `/coverage/section_detail/[]/section` | C | Declared section identifier. |
| `/coverage/section_detail/[]/status` | C | Structured coverage result. |
| `/coverage/section_detail/[]/required_tags` | C | Declared obligation. |
| `/coverage/section_detail/[]/missing_tags` | C | Measured unmet obligation. |
| `/coverage/section_detail/[]/required_claims` | C | Declared claims, retained exactly; not a claim-evaluation result. |
| `/coverage/section_detail/[]/claims_checked` | C | Prevents unchecked claims being equated with checked claims. |
| `/compile` | container | Fields below. |
| `/compile/source` | E | Constructed local source location; authored reference remains in captured manifest. |
| `/compile/sha256` | C | Exact emitted `white_paper.md` bytes; no text normalization. |
| `/compile/method` | C | Declared operation (`copy` currently); first profile supports only this method. |
| `/compile/note` | E | Implementation explanatory prose, not an alternative compile contract. |
| `/critic` | container | Fields below. |
| `/critic/enabled` | C | Distinguishes manual/deferred work from an automated assessment. |
| `/critic/note` | E | Explanatory text retained verbatim. |
| `/warnings` | E | Human-readable diagnostics; retain all text. Structured coverage, source status and derived draft flag carry current result facts. A new warning with unrepresented semantics requires a profile review, not dropping it. |
| `/outcome` | C | Derived from coverage counts; validate, then omit redundant value from core. Equal WARN results remain WARN, never promoted to PASS. |
| `/blueprint_status` | C | Duplicate of Blueprint status; validate equality before omitting duplicate. |
| `/has_draft_artifacts` | C | Derived from source statuses; validate before omitting duplicate. |
| `/release_status` | C | Manifest-declared state, descriptive only. |
| `/release_ratification` | C | Manifest-declared ratification value, not automated approval. |
| `/outputs` | container | Existing role keys remain required; all values below are locators. |
| `/outputs/white_paper` | E | Actual output location; content bound by `compile.sha256`. |
| `/outputs/coverage` | E | Location of a readable build report with an event timestamp. |
| `/outputs/rc_log` | E | Location; historical contents handled separately below. |
| `/outputs/release_decision` | E | Location; historical contents handled separately below. |
| `/outputs/build_json` | E | Self-location; never recursively hashed into the core. |

The current record has no schema-version field. CLI-local `stages` (with
`stage/status/detail`) are not emitted. The Sprint 002 example's stage timing and
different coverage shape are specification/example fields, not additional fields
in today's `build.json`. They must not be fabricated in a migration.

Neither producer records detected OS/Python/dependency versions, host identity,
filesystem mtimes or staging names. Engine versions are currently literal strings.
The envelope preserves what was recorded; it does not claim to recover missing
environment information. Future runtime observations belong in E, while any new
declared configuration that changes the result contract needs an explicit profile
classification. No such fields are introduced here.

`white_paper.md` bytes are C. `coverage.md` generated time and presentation are E;
its structured obligations/results are C above. `rc_log.md` and
`release_decision.md` are copies of historical documents, or explicit deterministic
stubs if absent. Their exact emitted bytes are proposed C inputs to result identity:
truthful historical dates/signatures within them must NOT be stripped. Current
`build.json` does not hash these two outputs. A future new-run producer must capture
their hashes at emission; a legacy adapter cannot invent build-time evidence by
reading whatever files happen to exist now. This adds a binding, not release power.

### `preservation_report.json`

This record is an execution's assessment of a build and its surroundings. It binds
to the build core; it is not a new build identity. All outcomes remain visible and
continue to gate successful verification under the existing rules.

| Field | Class | Reason / proposed treatment |
|---|---|---|
| `/preservation_engine_version` | E | Verifier implementation provenance, not schema version. |
| `/generated_at` | E | Verification event time. |
| `/build_id` | C | Must agree with the referenced build core; no separate identity by label. |
| `/reconstruction` | container | Separate responsibility preserved. |
| `/reconstruction/summary` | container | Counts/outcome must agree with observed checks. |
| `/reconstruction/summary/pass` | E | Count of observations in this verification. |
| `/reconstruction/summary/warn` | E | Same. |
| `/reconstruction/summary/fail` | E | Same; a failure cannot be hidden by core equality. |
| `/reconstruction/summary/advisory` | E | Same; not an automated governance decision. |
| `/reconstruction/summary/outcome` | E | Current reconstruction assessment. |
| `/reconstruction/checks` | container | Ordered observations, including optional checks. |
| `/reconstruction/checks/[]/name` | E | Human-readable check name, sometimes contains an authored source path. Must not be parsed as a stable artifact ID. |
| `/reconstruction/checks/[]/status` | E | PASS/WARN/FAIL/ADVISORY observation. |
| `/reconstruction/checks/[]/path` | E | Location actually examined, optional on failure. |
| `/reconstruction/checks/[]/note` | E | Diagnostic, sometimes null, absent, or contains OS error text/local paths. |
| `/reconstruction/checks/[]/sha256` | E | Digest observed now, possibly null for absent pipeline output. Verify against C where a build-time binding exists; never substitute for missing provenance. |
| `/reconstruction/checks/[]/hash_at_build` | C | Expected digest on mismatch; must agree with referenced core. |
| `/reconstruction/checks/[]/hash_now` | E | Actual mismatching digest, kept as failure evidence. |
| `/reconstruction/checks/[]/value` | A | Steward signature copied from release record. Retain exact value in envelope; authoritative release identity requires A2. Presence alone is not cryptographic authentication. |
| `/continuation` | container | Independent from reconstruction. |
| `/continuation/summary` | container | Counts/outcome must agree with checks. |
| `/continuation/summary/pass` | E | Current continuation observations. |
| `/continuation/summary/warn` | E | Same. |
| `/continuation/summary/fail` | E | Same. |
| `/continuation/summary/advisory` | E | Same. |
| `/continuation/summary/outcome` | E | Current continuation assessment, not permission to continue or release. |
| `/continuation/checks` | container | Ordered prerequisite observations. |
| `/continuation/checks/[]/name` | E | Check label. |
| `/continuation/checks/[]/status` | E | Observation. |
| `/continuation/checks/[]/note` | E | Diagnostic, optional or null. |
| `/continuation/checks/[]/outcome` | E | Observed release recommendation outcome, possibly null; original recommendation remains bound separately. |
| `/overall_outcome` | E | Derived assessment for this execution; validate against both summaries. |
| `/note` | E | Scope limitation: restoration remains deferred. Retain verbatim. |

Conditional reconstruction checks cover missing/invalid expected hashes, empty
artifacts, mismatches, invalid compiled-output paths and read errors; coverage
build-ID/corpus warnings; and the signature advisory. Continuation covers Blueprint
presence, optional intent-hypothesis scan, evidence trail, section requirements,
research hypotheses, ratification, recommendation and notes. No other producer
fields are present. Failure records must retain missing versus null distinctions.

`preservation_report.md` contains build label, its own event time, check labels,
statuses/notes, summary counts, overall outcome and scope prose. It is an E readable
projection of the report, not an independent C surface. Its clock is currently read
separately from JSON; no assertion that both timestamps are identical is introduced.

### `preservation_package/manifest.json`

| Field | Class | Reason / proposed treatment |
|---|---|---|
| `/preservation_engine_version` | E | Export implementation provenance. |
| `/build_id` | C | Must agree with the referenced build core. |
| `/packaged_at` | E | Actual packaging event time. |
| `/artifacts` | container | Membership matters; physical flattened filenames are not source identity. |
| `/artifacts/[]/original_path` | E | Actual local source locator. |
| `/artifacts/[]/preserved_as` | E | Package-local lookup location; retain and validate, but use typed artifact roles/manifest occurrence for C identity. |
| `/artifacts/[]/sha256` | A | Exact custody hash always retained in E. For immutable source/Blueprint/manifest bytes it also supplies C; for copied execution records it must not become C transitively. See A2. |
| `/artifacts/[]/status` | E | Copy/hash comparison observation. Successful emitted manifests currently contain PASS only. |
| `/artifacts/[]/sha256_at_build` | C | Expected artifact hash on internal mismatch entries; must match original provenance. Not emitted by successful export today. |
| `/artifacts/[]/note` | E | Internal mismatch diagnostic; export aborts before writing a new manifest. |
| `/artifacts/[]/path` | E | Internal missing-copy destination name with status MISSING; likewise not written in a successful manifest. |
| `/hash_mismatches` | E | Current export observation; zero in a successful newly written manifest. |
| `/note` | E | Existing descriptive prose; does not establish completeness. |

The current exporter copies Blueprint, manifest, declared sources, `build.json`,
`coverage.json`, and `release_recommendation.json`. It does **not** copy the compiled
paper. Export failure may leave partial copies or an older manifest. Hashing the
source before copying also does not prove the final copied bytes. This design
does not turn those limitations into completeness, atomicity, or custody guarantees.
No new exporter implementation is authorized here.

Copied build fields are inventoried above. Copied coverage/release records are
opaque byte payloads in the current package, not nested fields owned by preservation.
For completeness their current producer field surfaces are:

- Coverage: `coverage_engine_version`, `build_id`, `generated_at`, `manifest_path`,
  `blueprint_id`, `tag_index` (tag → ordered paths), `sections` (each `section`,
  `status`, `required_tags`, `tag_results`, `required_claims`, `claims_checkable`,
  `claims_note`); each tag result has `tag`, `status`, `resolved_by`, optional
  `note`; `summary` has `sections_evaluated`, `pass`, `warn`, `fail`, `overall_pct`;
  also `outcome` and top-level `claims_note`.
- Release: `release_engine_version`, `generated_at`, `build_id`, `inputs`
  (`build_json`, `coverage_json`, `release_criteria`), `criteria_results` (each
  `name`, `source`, `path`, `expected`, `actual`, `required`, `status`; advisory
  entries also `passed` and optional `note`), `summary` (`required`, `required_pass`,
  `required_fail`, `advisory`, `advisory_flagged`), `outcome`, `recommendation`,
  `steward_signature`, `steward_notes`, `signed_at`.

Within those opaque payloads, engine versions, generation times, input locators
and explanatory machine prose are E candidates; declared IDs, obligations, tag
membership, structured results and their derived counts are C candidates. Signature,
notes and signing time form historical stewardship evidence, **A2 as a unit**, not
disposable runtime fields. Nested source locators share A1. Until an upstream
profile is approved, the entire copied-record identity is A2: keep exact raw hashes
in the envelope, and refuse full package equivalence. Do not recursively remove
fields named `timestamp`, `path`, `note` or `version`.

## Proposed first core profile

`hermeneia.build-result/v1` has exactly two top-level keys: `schema` with that
literal value, and `result`. Its result has exactly:

```text
build_id
manifest_hash
blueprint: {id, status, sha256}
source_artifacts[]: {path, sha256, tags[], status, role}
coverage[]: {section, status, required_tags[], missing_tags[], required_claims[], claims_checked}
compile: {sha256, method}
critic: {enabled}
release_status
release_ratification
historical_outputs: {rc_log_sha256, release_decision_sha256}
```

This is an explicit projection, never "the old JSON minus time and path keys."
The existing manifest digest intentionally makes exact declared input bytes part
of reproducibility identity. Two papers with the same bytes but different ancestry
are not the same authoritative build result. No deduplication or array sorting:
manifest order and repeated occurrences survive. Derived counts/flags/outcome are
checked against this data, not independently authoritative copies.

Eligibility is limited to currently supported copy builds with captured valid
provenance, portable manifest-authored relative file references, exact emitted
artifact hashes, and validated known field/value shapes. Every listed key is
required; no defaults, ignored unknown fields, guessed paths or inferred approvals
when admitting a core. For this first profile, text fields are strings; tags and
claims are arrays of strings; check flags are booleans; hashes are 64 lowercase
hex characters. Richer YAML values that old code happened to serialize remain
legacy-readable but are unsupported for this profile until specified.

The `resolved` flags must be true, Blueprint ratified, compile method `copy`, and
critic `enabled` false for this profile. Section status/claims flags must match
the current coverage algorithm. Legitimate build warnings remain valid warnings.
The envelope retains all diagnostics, including warnings unrelated to coverage
counts. A changed algorithm or newly meaningful field requires a new reviewed
profile; implementation version alone does not change result identity.

Portable references for the bounded first implementation are nonempty POSIX
relative paths without `.`/`..` components, backslashes, drive prefixes, or leading
slash. Reject unsupported spellings for core eligibility without changing legacy
build behavior or rewriting the manifest. Current lookup uses path joining and
existence checks; it does not establish filesystem confinement. Portable spelling
alone also does not prevent symlink escape. The future comparator must use an
explicit caller-supplied artifact set/root and reject escapes after resolution;
it must not blindly open untrusted envelope paths. That implementation boundary
needs adversarial tests and does not grant authority to reinterpret input identity.

## Exact digest and binding boundary

The proposed binding object has exactly `schema`, `core`, `envelope` keys.
`schema` is `hermeneia.reproducibility-binding/v1`. `envelope` has exactly:

```text
core_sha256: 64 lowercase hexadecimal characters
records[]: {role: string, path: string, sha256: 64 lowercase hexadecimal characters}
```

`records` contains unique roles: the first build binding profile has exactly
`build-record`; the verification binding profile has exactly `build-record` and
`preservation-report`. The role set selects these two supported cases. Other
roles require an explicit supported binding profile, not opportunistic omission.
Paths are actual locators and remain E. Record bytes are not reserialized before
hashing. The record containing this binding must never reference itself.

Let `C(core)` be the following precisely constrained canonical JSON bytes:

1. Strict UTF-8 JSON object, no BOM, duplicate object keys, NaN/Infinity, floats,
   non-string keys or lone surrogate code points. Only null, booleans, strings,
   arrays, objects, and integers in `[-9007199254740991, 9007199254740991]` are
   encodable; the profile further restricts fields as above. Negative zero integer
   spelling is parsed as zero. Reject unsupported schema/keys/types before hashing.
2. Recursively sort object keys by Unicode code point. Preserve array order,
   multiplicity, case, whitespace and Unicode code points in string values.
   No NFC/NFKC, trimming, path rewriting or newline normalization.
3. Encode as Python's `json.dumps(core, sort_keys=True, ensure_ascii=True,
   separators=(",", ":"), allow_nan=False)` after the strict validation above;
   UTF-8 encode the result, without BOM or trailing newline. Non-ASCII escapes use
   lowercase hex; supplementary characters use surrogate-pair escapes. This is
   this profile's encoding, not a claim of RFC 8785 compliance.

Then:

```text
core_sha256 = hex_lower(SHA256(b"Hermeneia reproducibility core v1\n" + C(core)))
record.sha256 = hex_lower(SHA256(exact captured record bytes))
```

Only the domain separator and core bytes enter the first digest. Neither the
envelope, physical filename, file mtime, serialization indentation, nor the core's
own digest enters it. The core schema is inside the digest. Different kinds or
profiles therefore cannot accidentally share an identity through omitted type
information. `compile.sha256` retains its old meaning: SHA-256 of exact paper
bytes, with **no** domain prefix. Existing input/output hashes are never redefined.

The digest binding detects a stale or swapped core, and raw record hashes detect
changed execution evidence. A verifier must also derive the core from captured
inputs/records and compare it, so a correctly rehashed but inconsistent envelope
is rejected. Hashes alone do not authenticate a writer: an attacker able to replace
the whole core, envelope and artifacts can recompute hashes. Authentication needs
an independently trusted digest/signature, whose policy is unchanged and outside
this packet. No new signature scheme or self-asserted trust is introduced.

## Comparing and verifying two executions

1. Read each binding and referenced record once as bytes; reject malformed JSON,
   duplicate keys, unsupported profiles and invalid digests. Keep the captures for
   parsing, digest checks and provenance validation; do not reopen and combine
   different versions of a file. Do not trust supplied digests without recomputing.
2. Check each envelope's core digest, each record's raw byte digest, all required
   roles, core/record field agreement, derived counts, and build/manifest identity.
   Recompute all required artifact hashes from exact bytes. Unavailable required
   bytes prevent fully verified equality; they must not be silently skipped. An
   offline comparison supplied only records is `NOT_COMPARABLE` for verified
   result equality. An attempted integrity check that finds a declared artifact
   missing or mismatched is `INVALID` and preserves that failure evidence.
   Missing provenance or mismatches fail closed; a current digest must
   not be backfilled as a build-time digest. Later detected mutation invalidates
   the verification, with no normalization or automatic repair.
3. Keep **binding integrity**, **result equality**, **reconstruction**, and
   **continuation** separate in the result. Historical negative observations remain
   truthful even if a later execution can verify the artifacts successfully.
   Equal cores never override a failed current integrity check or a stewardship gate.
4. For two fully verified, supported instances of the same core profile, compare
   canonical core bytes and recomputed digests. Both equal means `SAME_RESULT` for
   the declared scope. Different cores mean `DIFFERENT_RESULT`, with field-level
   differences. Envelope equality is neither required nor evidence of result
   equality; report envelope changes independently.
5. Corrupt/mismatched bindings are `INVALID`, never equivalent. Missing legacy
   cores, unknown schemas, or an unresolved classification yield `NOT_COMPARABLE`
   with the reason, never a fallback comparison after dropping fields. A failed
   execution can be audited but is not admitted as a successfully verified pair.

These are proposed comparison result labels, not current CLI exit codes or new
release states. Read-only comparison must not alter inputs or regenerate outputs.
The existing preservation command's exit/status behavior is unchanged by this design.

## Preservation inventory identity and the transitive-hash boundary

A preservation report binds the existing build core plus exact report bytes. That
is sufficient to say which result it examined. It is insufficient to assert that
two exports preserve the same complete investigation.

If package comparison is later implemented, use a separate explicit inventory
profile with `schema`, `build_core_sha256`, and ordered `artifacts`. Each artifact
has `role`, optional `source_index` for its manifest occurrence, and exactly one
typed identity: `{kind: "bytes", sha256}` for immutable evidence/historical input,
or `{kind: "core", schema, sha256}` for an execution record with its own approved
core profile. Physical package paths and every copied file's raw SHA-256 stay in
the export envelope. Changing either membership or typed identity changes the
inventory digest under the same canonical encoding and domain boundary.

This prevents a copied `build.json` timestamp from reentering identity through its
raw custody hash. That raw hash is still mandatory and must match the copied bytes.
No digest cycle: build core excludes its envelope; inventory core references build
core; export envelope references inventory core and raw copies. It never includes
its own file hash.

The inventory profile is **not ready to emit**: A2 must first settle coverage/release
references. It must label the actual membership and refuse unsupported members,
not omit them to manufacture equality. The current missing compiled-artifact copy
also prevents claiming a self-contained preservation package. Those repairs and
the package completeness/validation contract are separate bounded work.

## Compatibility, versions and migration

- Existing unversioned records remain legacy records with existing meanings,
  digests, readers, paths, statuses and authority. Engine `0.1.0` values are not
  retroactively schema versions. No mutation of signed releases or frozen evidence.
- Proposed bindings are additive and independently versioned. Core profile version
  covers field membership, semantics and encoding. Binding version covers envelope
  structure. Neither is the installed tool version. Unknown versions fail closed
  for comparison; an old reader may still read the unchanged legacy record.
- An ordinary new build could later emit a binding only after successful existing
  checks and capture of all new required digests. A missing or mismatched sidecar
  must never be treated as evidence of reproducibility. Publication of the sidecar
  must be atomic individually, and readers detect inconsistent record/sidecar
  pairs. This does not promise a whole-build transaction or power-loss durability.
- Existing records receive **no automatic migration**. Comparison returns
  `NOT_COMPARABLE: legacy record without a supported core`; existing verification
  remains available and must not be relabeled failed solely for being legacy.
  A new execution may produce new provenance; it cannot certify an old run's
  missing capture. A future explicit historical adapter needs separate approval
  and must preserve the old raw hash, derivation version, scope and limitations.
- Test vectors here are synthetic proposed-protocol examples. They neither attach
  cores to real publications nor ratify an adapter, release, source, or fixture
  signature. No production module imports the test codec or fixtures.

## Remaining steward decisions

**A1 — Authored machine-local references.** Execution-added absolute paths clearly
belong to E. An absolute path *inside authoritative manifest bytes* is harder:
`manifest_hash` already commits those bytes. Removing it from identity requires
deciding whether a portable manifest projection replaces that part of exact input
identity, and how authored locators distinguish source occurrences. Options are
to limit reproducibility eligibility to portable declarations (proposed first
profile), or authorize a separately versioned manifest identity scheme. Do not
silently rewrite YAML or claim equivalent input digests across changed manifests.

**A2 — Mixed coverage/release record identity.** Decide whether a signed release is
an indivisible historical byte artifact for package equivalence, or whether an
approved result core can separate its machine-generation metadata while preserving
the full signed record as custody. Classify `steward_signature`, `steward_notes`,
`signed_at` together; a human's historical act must not be made interchangeable
with another act by removing its date. Coverage needs its own approved profile as
well. Current signatures are human-entry fields, not cryptographic signatures.
Build-result comparison can proceed independently; full package equivalence cannot.

No additional decision is needed to keep actual event times/local lookup paths in
E, retain exact authored Blueprint/source bytes in C, or exclude staging names from
identity. No current field is declared obsolete. Review of the detailed first
profile is still required before its production introduction; this document is
the requested reviewable proposal, not evidence of a completed schema migration.

The first binding's machine-record scope also leaves readable report custody
unbound. Adding raw-byte envelope roles for those projections is a later mechanical
extension, not permission to strip their timestamps. In particular, `herm coverage`
overwrites build-stage `coverage.md`; that existing behavior must be accounted for
before claiming that a later verifier can retrieve the original report bytes.
This proposal makes no guarantee about identical or authenticated readable reports.

## Proposed implementation packet and stop fence

After acceptance of the first profile, implement **build-result bindings only**:

1. Strict versioned core codec and validator with the committed golden vectors,
   rejection cases and independent byte-hash checks.
2. Capture historical output hashes when those files are emitted; derive core
   from the same captured manifest/input/output representations already used by
   the build. Preserve the legacy build record and all existing checks.
3. Add the individually atomic build binding, its record-byte digest, and read-only
   comparison. Test two relocated/timed clean runs, changed authoritative input or
   emitted bytes, unsupported manifest references, stale/swapped sidecars,
   inconsistent core/record pairs and partial-write/replacement failures.
4. Run focused/full regressions and independently reproduce any baseline failures.
   Do not modify preservation export, coverage/release schemas, signing, rollback,
   storage ontology, or historical records. A1/A2 remain refusal boundaries.

A following packet can attach preservation verification envelopes to an already
validated build core while retaining all negative findings. Package core emission
waits for A2 and separately demonstrated export integrity/completeness. Stop before
production schema or record-format changes in this packet.

## Validation of this design packet

Environment: macOS, Python 3.13.5, pytest 9.1.0, Node.js 22.17.0. Remote `main`
was independently checked against the inspected revision before changes.

- [`tests/test_reproducibility_core_design.py`](../../tests/test_reproducibility_core_design.py)
  and the [committed vectors](../../tests/fixtures/reproducibility-core-design.json)
  provide 23 passing design checks: fixed canonical byte/digest examples;
  malformed/ambiguous JSON rejection; Unicode, newline and array preservation;
  real legacy builds at different paths/times with equal proposed cores and
  different bound execution records; stale/swapped/rehashed-inconsistent binding
  counterexamples; authoritative-content sensitivity; and refusal to infer an
  identity for legacy/unknown profiles. The current happy-path field inventory is
  checked against this document. Conditional/failure-only fields were also
  manually audited against both producers by an independent review.
- Focused command:
  `python3 -m pytest -q tests/test_reproducibility_core_design.py tests/test_publication_reproducibility.py tests/test_publication_build.py tests/test_preservation.py tests/test_publication_false_confidence.py tests/test_publication_release_authority.py --tb=short --show-capture=no`
  — **209 passed** in 1.94 seconds.
- A pristine `git archive` of exact starting commit
  `8ff6d18728ec1767782c637a903da00d962dad1f` independently reproduced the
  [six known Reader nodes](../verification/2026-09-22-preservation-build-digests.md#validation):
  **6 failed** in 0.24 seconds. Imports resolved inside the isolated archive
  `/private/tmp/herm-core-baseline-036b1aiw/repo`; no packet files were present.
  Failures are five markup/binding assertions and the undefined
  `_crSyncPageSpeechControls` Node harness reference.
- Full command: `python3 -m pytest -q --tb=short --show-capture=no`, with local
  socket/child-process access — **1719 passed, 6 failed, 21 skipped**, 5 dependency
  deprecation warnings, in 101.13 seconds. Every failure matches that independently
  reproduced baseline; no newly failing tests were observed. The suite remains red.
- Independent design review checked field completeness, digest cycles, authority,
  legacy handling and limits of the test oracle. The final proposal explicitly
  distinguishes record binding from authentication, requires artifact availability
  for verified equality, and states the readable-report custody limitation.
- Only this proposal, the documentation index, test file and synthetic fixture
  change. Production code, generated publications, historical evidence and active
  authority documents are unchanged. `git diff --check` passed.

These checks demonstrate a proposed protocol and characterize unchanged legacy
producers. They do not certify a production validator, schema migration, portable
manifest adapter, package completeness, cross-platform implementation, signing
scheme or hosted CI. Full schema validation and filesystem confinement remain
requirements for the separately authorized implementation packet.
