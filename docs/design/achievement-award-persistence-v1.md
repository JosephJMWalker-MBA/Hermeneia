# Perspective achievement award persistence v1 — P4

Implemented against starting commit `bb05d2d2bafdf6cc64f13e644915e6bc191ddf98`.
Validation completed 2026-10-01. This note records implementation and synthetic
verification, not real-workspace achievement issuance or product-use validation.

The authoritative boundary remains the
[frozen award receipt contract](achievement-award-receipt-contract-v1.md),
[Perspective rules](perspective-achievement-rules-v1.md), and
[evaluator profile](perspective-achievement-evaluator-v1.md), implementing
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215) under the
steward decisions in [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214).
No frozen rule or receipt-contract semantics changed.

## Implemented boundary

An award preserves an exact historical deterministic `earned` assessment. It
establishes neither agreement, mastery, human authorship, present qualification,
authenticated issuance, nor named-human identity. Current evaluation, historical
award, and current verification remain separate.

| Production file | Responsibility |
| --- | --- |
| `hermeneia/achievement_awards.py` | Strict receipt/package codec, exact packaging, explicit materialization, historical loading, archival parent binding |
| `hermeneia/achievement_award_verification.py` | Read-only integrity, evidence, and historical replay dimensions |
| `hermeneia/perspective_achievements.py` | Shared unchanged adapter-basis construction; evaluator results/rules stay unchanged |
| `hermeneia/storage/sqlite.py` | Additive schema 19 startup initialization |
| `hermeneia/study_lineage.py` | Safe terminal award summary and eligible exact P3 context links |
| `hermeneia/capabilities.py` | Exclude awards and their coverage from P1/P2 prerequisite/history facts |
| `hermeneia/workspace/export.py` | Snapshot award component, canonical bytes and required archival closure |
| `hermeneia/workspace/restore.py` | Strict component validation, fresh-target refusal, atomic dependency-first installation |

No API route, CLI command, achievement UI, notification, automatic issuance,
provider/model call, generic event store, or revocation mechanism was added.
Only the explicit domain mutation seam installs a new local award. Restoration
preserves received history without claiming new local issuance. Reads, Keep,
evaluation, Lineage, capability/Guide rendering and export never issue awards.
Real workspaces and Benchmark02 were not changed.

## Store and canonical bytes

Schema 19 adds `achievement_awards` through the existing SQLite startup
initializer. The migration scaffold remains unchanged; this repository uses
idempotent DDL and initializer-based additive migrations.

```text
id TEXT PRIMARY KEY
achievement_id TEXT NOT NULL
rule_id TEXT NOT NULL
rule_version TEXT NOT NULL
receipt_json TEXT NOT NULL
UNIQUE(achievement_id, rule_id, rule_version)
```

Database triggers reject UPDATE, DELETE and INSERT OR REPLACE by either ID or
logical slot, including with SQLite recursive delete triggers disabled. Domain
reads validate every mirrored column against the canonical payload. A malformed
existing slot blocks materialization; it is never silently replaced.

Receipt fields are exactly `schema`, `award_id`, `achievement_id`, `rule_id`,
`rule_version`, `evaluation_status`, `earned_at`, `awarded_at`, `issuer`,
`issuance`, `evidence_package`, and `evidence_package_sha256`.

The shared P3 codec serializes finite JSON with string keys, sorted object keys,
ASCII escapes, compact separators, UTF-8 and no newline. Array order is preserved.
Duplicate keys, nonfinite values, noncanonical stored bytes, invalid IDs/times,
unknown closed-object fields and contradictory internal bindings fail closed.
Existing execution and Perspective metadata dictionaries and versioned rule
payloads remain open finite JSON; Lineage provenance's contract fields remain
closed, preventing an extra copied response field from entering the package.
Unknown wire/schema/profile versions are unsupported, not converted.

With `C` denoting this canonical serialization, and `\0` one NUL byte:

```text
package digest = sha256:hex(SHA256(
  UTF8("hermeneia.perspective-achievement-evidence-package/v1\0") || C(package)))

award_id = achievement-award:sha256:hex(SHA256(
  UTF8("hermeneia.perspective-achievement-award/v1\0") || C(receipt without award_id)))
```

The package preserves exactly one selected finding, top-level assessment
metadata/diagnostics/limitations, the complete original adapter basis, ordered
rule declarations, and selected `{receipt_id, run_id, receipt_sha256}` bindings.
The evaluator and package share the same basis construction. The original P3
receipt SHA-256 covers its exact stored bytes including its ID; existing rule,
registry, evidence and P3 ID digest boundaries are unchanged.

Codec checks bind all parallel arrays, K order, selected retention thresholds,
coverage histograms, rule digests, captured Perspective/methodology/inquiry
metadata and explicit approval. Archival checks additionally bind every candidate
metadata snapshot to its exact P3 parent and require captured typed dependency
and eligibility identities. Rehashing contradictory metadata cannot make a
claimed supported receipt acceptable for restore.

The supported evaluator 1.0.0 registry is pinned to
`sha256:6b0065fac155c40fc25ce5cc62c53a7c250c0595dd4e49554669bab55e56197c`.
Same-version definition drift refuses materialization. Historical self-valid
bytes for a compatible unknown rule/evaluator version can be preserved, but do
not gain executable historical support.

## Explicit materialization

```python
package = prepare_perspective_achievement_award(conn, achievement_id)
# The local steward explicitly approves this exact digest before mutation.
outcome = materialize_perspective_achievement_award(
    conn, achievement_id, rule_id, rule_version, evidence_package_digest(package))
# outcome = {"status": "recorded" | "already_recorded", "receipt": exact_receipt}
```

Preparation uses one caller-preserving read snapshot. Materialization rejects a
pending caller transaction, owns `BEGIN IMMEDIATE`, validates the released rule,
and checks the logical slot. A new slot re-evaluates canonical committed evidence
and rebuilds the exact package under the same transaction. Non-earned outcomes
or any approval/package drift refuse without a row. Installed canonical bytes
are reread and validated before commit. Failure rolls back only this award
transaction; prior successful P3 retention survives.

A valid existing slot returns `already_recorded` and the exact original receipt,
even after additional candidates, a changed selected pair, current ineligibility
or evidence loss. It does not read a new issuance clock or replace evidence.
Concurrent duplicate issuers produce one row. An explicitly supported new rule
version can occupy another slot; synthetic test-only version 2 fixtures show
coexistence and a later negative assessment without changing production rules.

Explorer `earned_at` is its selected witness's retention instant in aware UTC.
Second Opinion uses the later instant of the selected ordered pair; this does
not claim the earliest theoretically possible pair. Original parent strings are
retained. `awarded_at` is the actual first insertion-attempt UTC clock reading;
retries/restores preserve it. Clock skew is retained and reported, never clamped.
Issuer is exactly `{kind: hermeneia, authorship: derived}`. Issuance records an
explicit local steward action with `actor_identity=unknown` and exact approval
digest; it is not authenticated named-person consent.

## Historical verification and Lineage

`verify_achievement_award(conn, award_id)` makes no writes, initialization,
connection-setting changes, provider calls or model regeneration. It preserves
caller transactions and checks one coherent snapshot.

| Dimension | States |
| --- | --- |
| `receipt_integrity` | `valid`, `invalid`, `unsupported` |
| `evidence_verification` | `verified`, `unverifiable_missing_evidence`, `unverifiable_missing_coverage`, `unverifiable_unsupported_rule`, `invalid_evidence` |
| `historical_snapshot_replay` | `verified`, `unsupported`, `invalid` |

Evidence precedence is invalid, missing evidence, missing coverage, unsupported
rule, verified. Per-check negatives are retained. Known immutable family
contradictions remain visible even with an unsupported evaluator or missing P3
row. Complete saved-family proof is required for Second Opinion; family-only
Explorer diagnostics do not become an extra qualification gate.

Mutable source/highlight snapshot drift is missing historical coverage, rather
than award tampering. Missing rows and known immutable digest/association
contradictions remain distinct. Rehashing the captured basis is receipt integrity,
never independent replay. Full replay is verified only when canonical current
adaptation independently reproduces the exact original basis and assessment with
required historical evidence verified. Changed candidates or unrecoverable old
mutable rows make replay unsupported. No historical snapshot store was added.

Lineage emits `perspective_achievement_award`, `event=recorded`,
`authorship=derived`, typed award ID and original issuance time. It exposes a
whitelisted summary, issuer, secondary earned time, lean selected typed P3
references, bounded coverage and explicit summary-only verification limits.
It validates receipt integrity but reports evidence verification `not_performed`
and replay `unsupported`; it never calls the full verifier recursively through
the adapter. Eligible supported links open exact P3 receipts only. Missing or
excluded ancestors suppress links/private metadata/output while preserving the
safe historical summary. Malformed awards produce bounded diagnostics rather
than an earned claim. Awards cannot satisfy P1/P2/P4 evidence/history predicates.

## WBS compatibility

Required capability: `perspective-achievement-awards-v1`. Canonical component:
`study/achievement_awards.json`. Manifest count/coverage key: `achievement_awards`.
Rows preserve exact canonical `receipt_json` strings, IDs and original times in
ASCII ID order. Covered-empty and unsupported legacy coverage remain distinct.
WBS version selection and publication/release identity are unchanged.

Missing, malformed or contradictory required archival closure refuses whole
export/restore. Excluded ancestors and legitimate mutable snapshot drift remain
archivable, without gaining present eligibility or full historical replay.
Only the selected Second Opinion pair requires complete saved-family closure;
Explorer/unrelated family diagnostics do not create invented parent requirements.
Existing independent P3/WBS graph refusal rules remain in force.

Restore validates capability, containment, hash/role/count, strict JSON keys,
canonical payloads, mirrored identities, unique IDs/slots and required closure.
It installs dependencies, P3 receipts, then awards in one transaction. Occupied
award-history targets refuse before startup mutation and again under the write
reservation; `overwrite=True` cannot authorize an award merge or replacement.
Failure installs no half-history. Compatible unknown historical rule/evaluator
versions remain structurally restorable with unsupported verification; unknown
wire formats are refused.

Old stores/bundles load under their prior contracts. There is no backfill or
migration of historical reports. Missing component/capability means unsupported
historical coverage, never zero historical awards. Startup after an old restore
creates only a new extant ledger; restore/preview retain the original unsupported
coverage result. Later exports describe the current extant category with past
completeness still unknown.

## Demonstrated tests and limits

Failing-first award tests recorded missing persistence/verification support.
Subsequent destructive fixtures demonstrated rehashed false comparison metadata,
empty dependency capture, contradictory family coverage and copied Lineage output
being accepted before the corresponding bounded integrity checks were added.
An unsupported-evaluator fixture demonstrated a known immutable family failure
being hidden; verification now retains that negative beside unsupported support.

New files contain **192 focused award cases**, including positive controls and
adversarial codec, stale, immutability, concurrency, failure-isolation, version,
coverage, exclusion, read-only and portability cases. Final focused result:
**192 passed**. Existing targeted regressions: **438 passed**:

| Group / files | Result |
| --- | --- |
| P1: `test_capabilities`, `test_capabilities_lineage` | 55 passed |
| P2: `test_guided_study_cycle`, API, UI | 67 passed |
| P3: `test_perspective_execution_receipts`, API, Lineage, WBS, UI | 123 passed |
| Read-only P4: `test_perspective_achievements`, integrity | 92 passed |
| Study Lineage: domain, API, UI | 75 passed |
| WBS: `test_workspace_export`, restore, export download | 26 passed; 32 further WBS cases included in P3 above |

Both synthetic built-in and saved-frame Second Opinion chains pass:
exact P3 pair → canonical earned package → explicit issuance → deterministic WBS
export → fresh restore → exact receipt bytes/IDs/times → read-only verified
receipt/evidence/replay → equal safe derived Lineage records. Synthetic Explorer,
unknown-version, excluded-ancestor and mutable-drift portability controls also
pass. No real-workspace achievement, real model run, cross-machine execution,
power-loss test or authenticated clock/issuer claim is made.

The independent untouched baseline archived all 630 tracked files from
`bb05d2d`, checked Git object hashes and the imported module path, ran the full
suite independently, and verified all archived tracked files unchanged afterward:
**2,320 passed, 21 skipped, six Reader failures**. A sandbox run additionally hit
localhost/runtime infrastructure failures; the unrestricted baseline reproduced
the expected six-only set. No infrastructure failure was reclassified as product
semantics.

Final full-suite result: **2,512 passed, 21 skipped, six unchanged Reader
failures** (2,539 cases, no collection errors). The exact failure-ID set matches
the independent baseline; there are no newly introduced failures. The final full
run also passes every one of the 438 existing targeted regression cases. The eight existing test-file
adjustments advance schema/capability expectations and replace one obsolete
blanket string assertion with actual zero-row/no-award-input enforcement; no
Reader test or implementation was weakened.

Baseline failure IDs:

- `test_reader_accessibility::test_read_page_button_is_rendered_in_page_header_with_accessible_label`
- `test_reader_accessibility::test_failed_or_missing_page_cannot_speak_prior_page_source`
- `test_reader_blueprint_workstation::test_blueprint_is_a_workstation_mode_not_a_separate_drawer`
- `test_reader_record_view::test_record_tab_and_panel_present`
- `test_reader_record_view::test_record_is_a_workstation_mode_not_a_separate_drawer`
- `test_reader_voice_profile::test_voice_is_a_workstation_mode_not_a_separate_drawer`

No contract ambiguity required a new authority decision. Remaining limitations
are intentional: no authenticated local steward identity, complete lost mutable
snapshot replay, rule profiles beyond the supported release, revocation, award UI
or autonomous materialization. Hash validity is not an external signature.

Next bounded packet proposed for steward review: a thin explicit issuance and
read-only inspection API exposing the exact package approval and separate
historical verification dimensions. No UI or automatic issuance is authorized
by this completed persistence packet. Stop before that next packet.
