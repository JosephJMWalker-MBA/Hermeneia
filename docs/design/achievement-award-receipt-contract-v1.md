# Perspective achievement award receipt contract v1 — bounded P4

**Status:** Frozen design for review under the current steward packet; not implemented.

**Date:** 2026-09-30.

**Inspected baseline:** `ec8c230bf0a201ee6f5336b0a54b92e61ea81a59`.

**Scope:** Perspective Explorer and Second Opinion only. No production, schema,
test, WBS, Lineage, API or UI change is made by this document.

## 1. Scope, authority and record category

This is the next design packet of
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215), under
[#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214), informed by
[#212](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/212) and the
[#213 audit](capability-coaching-architecture-audit.md). It does not amend the
[Constitution](../00_Constitution.md), [Authority Index](../01_Authority_Index.md),
[invariants](../02_Constitutional_Invariants.md), [Storage](../15_Storage.md),
[CA-0004](../amendments/CA-0004-auditability-and-monotonic-governance.md),
[ADR-0045](../adr/ADR-0045-perspective-definition-revisions.md),
[frozen achievement predicates](perspective-achievement-rules-v1.md) or
[P3 receipt meaning](perspective-execution-receipt-v1.md).

An award is authoritative append-only **study history of a derived system
assessment**. It is neither a new constitutional epistemic class/pipeline stage
nor a disposable cache. It does not ratify an Interpretation, change Perspective
identity, accept a Blueprint, or grant release authority. Study Lineage continues
to project the owning records; no generic event store or second history is added.

The only initial rule slots are:

| Achievement | Rule | Version |
| --- | --- | --- |
| `perspective_explorer` | `achievement.perspective_explorer` | `1.0.0` |
| `second_opinion` | `achievement.second_opinion` | `1.0.0` |

## 2. Exact historical claim and three separate read results

The receipt asserts: **At the recorded issuance time, Hermeneia recorded that its
identified deterministic evaluator returned `earned` under the identified rule
version and definition, using the captured evidence package and declared coverage.**

That is a system assertion with integrity bindings, not cryptographic attestation
of an authenticated person, provider, or external clock. It is not independent
proof of the intellectual activity without its ancestors. It proves neither
agreement with output, human authorship, mastery, independence, complete study
history, nor eligibility under every future rule. A materialization request
authorizes recording; it does not endorse the intellectual content.

Keep these outputs separate:

| Output | Meaning | Owner/mutability |
| --- | --- | --- |
| Current evaluation | Today's supported evidence assessed under an explicitly selected rule/evaluator version | Read-only, regenerable result; existing four statuses |
| Historical award | This exact assessment was recorded under this exact historical rule | Immutable receipt, original witnesses and times |
| Current historical verification | What receipt integrity, evidence bindings and historical replay can be checked now | Read-only derived report with explicit limits |

An old `earned under v1.0.0` receipt can coexist with current `not_earned` under
v1.1.0, current exclusion, or unavailable evidence. None edits/deletes the old
record. A malformed purported receipt does not become trusted history merely
because a database row exists; preserve its bytes and report invalidity.

**V1 awards are terminal derived records, not evidence generators.** Neither
Perspective achievement evaluator may consume award rows, badge display state,
notification state or prior earned assessments as substitute evidence.

## 3. Verified current seams and earned-result inventory

Current production owners:

- [Adapter](../../hermeneia/perspective_achievement_evidence.py):
  `read_perspective_achievement_evidence(conn)`, one coherent read snapshot,
  P3 validation, eligible typed Lineage identity, ancestry and coverage.
- [Evaluator](../../hermeneia/perspective_achievements.py):
  `evaluate_perspective_achievements(evidence)`, two pure frozen predicates;
  `perspective_achievement_rules()` returns copied static declarations.
- [P3](../../hermeneia/perspective_execution_receipts.py):
  `canonical_bytes`, `receipt_from_row`, `validate_execution_references`,
  `store_retained_execution` and database append-only/atomicity conventions.
- [Lineage](../../hermeneia/study_lineage.py): `project_study_lineage`, typed
  table/key identities, recorded timestamps, eligibility and provenance.
- [WBS export](../../hermeneia/workspace/export.py) and
  [restore](../../hermeneia/workspace/restore.py): snapshot export, required
  capabilities, strict P3 component validation, fresh-target atomic row restore.

These are the exact returned fields, not proposed evaluator additions:

| Level | Existing fields / meaning |
| --- | --- |
| Evaluation | `schema`, `evaluator_version`, `rules_sha256`, `evidence_sha256`, `achievements`, `coverage`, `diagnostics`, `limitations` |
| Every achievement item | `achievement_id`, `rule_id`, `rule_version`, `rule_reference`, `rule_sha256`, `status`, `reason_code`, `reason`, `evidence_refs`, `qualifying_receipt_ids`, `validated_evidence`, `coverage`, `selection_basis` |
| Validated witness | `receipt_id`, SHA-256 of exact stored receipt JSON bytes including its ID, typed dependency row digests/bases, mutable eligibility observations |
| Selection | `order`, K-sorted `candidate_receipt_ids`, selected receipt IDs, original `retained_at` and derived `retained_at_utc` |
| Second Opinion only | `question_comparison_basis`, `scope_comparison_basis`, `perspective_distinctness_basis` |
| Question basis | Exact UTF-8 codec, validated question digest, literal equality result |
| Scope basis | Complete P3 canonical codec, validated Scope digest, equality result, Scope receipt and prompt versions |
| Distinctness basis | Ordered family keys, revision IDs, definition fingerprints, methodology field names/digests, family node/relation evidence, literal difference result |

`run_id` is not an explicit achievement-result field. The future award domain
must bind it from each exact selected P3 receipt in the same recording snapshot.
No output, prompt, question or complete Scope text is copied into an award.
Existing Lineage refs include captured Perspective definitions and execution
metadata; preserve them exactly in the private receipt, subject to safe projection.
Finite provider-option floats can occur there: the build-core float-free codec
cannot replace P3's finite JSON codec.

## 4. Issuer and explicit issuance decision

**Select D: an explicit, idempotent materialization command, restricted in v1 to
an explicit local-steward request for the exact assessment package.** The request
names achievement, rule/version and the package digest. Software issues the
deterministic assertion; the unauthenticated local steward authorizes its recording.
There is no stronger participant identity or intellectual ratification claim.

| Option | Decision |
| --- | --- |
| A: automatic whenever evaluation returns earned | Reject; reads/GET/evaluation must never write |
| B: user “claim award” | Only a presentation of D; the request cannot supply qualifying facts or bypass evaluation |
| C: automatically after canonical mutation | Not authorized in v1; Keep/acceptance does not imply approval of an additional award record |
| D: explicit application mutation command | Select with exact local-steward request and stale-assessment refusal |

This conservative decision applies #214's exact human-write boundary without
creating autonomous issuance authority. It does not decide whether a later
explicitly approved system may materialize automatically. No per-model approval
is invented; no claim about named-human approval is made by the award itself.

The future command must own a **separate transaction after underlying evidence
has committed**. Reject a caller-owned pending transaction; a savepoint inside
Keep is not an independent committed award. Failed issuance never rolls back,
invalidates or loses the successful P3 retention/other study mutation.

For a new slot:

1. Start an award-owned `BEGIN IMMEDIATE`; obtain canonical evidence using the
   current adapter without initializing anything on its behalf.
2. Evaluate the selected released rule using the existing pure evaluator.
3. Assemble the package in section 6 from that same snapshot. Compare its digest
   and exact requested rule identity against the approved request. Any drift,
   including changed selection, coverage or diagnostics, refuses as stale.
4. Only `earned` permits insertion. Do not manufacture an award for another
   status or impose an invented all-local-rows-valid gate over an earned witness.
5. Capture truthful issuance time once, construct/validate complete canonical
   bytes, insert, reread and validate installed bytes, then commit or roll back
   only the award transaction.

No client-reposted result/Lineage JSON, raw bundle JSON, browser state or provider
call supplies award authority. Re-evaluation does not regenerate model output or
resolve historical Scope again. Initialization/migration remains an explicit
startup/write operation outside evaluation and verification.

## 5. Identity, slot uniqueness and retry policy

Select a digest-derived portable receipt ID, with **slot uniqueness separate
from content identity**:

```text
slot = (achievement_id, rule_id, rule_version)
       within one authoritative workspace award ledger

award_id = achievement-award:sha256:<lowercase 64 hex>
```

The ID binds every immutable receipt field except only `award_id`, including
schema, exact evidence package, issuer/request provenance and original issuance
time. Section 8 defines its hash domain. It is not a learner identity, global
achievement identity, evidence-set identity, or release identity.

One workspace ledger receives **at most one award per slot**, even when later
witnesses differ. Do not include evidence digest, current definition digest or
evaluator patch version in the uniqueness key. A new explicit rule version may
occupy a separate slot. It is a separately versioned historical assessment, not
a second accomplishment-count reward; future presentation should group versions
under the achievement without hiding their exact history.

On retry/concurrency, validate an existing slot before making new bytes:

- Same released rule definition: return the existing exact receipt with
  `already_recorded`; do not replace witnesses, times or diagnostics. Current
  evaluation/verification can be returned separately and need not remain earned.
- Later new evidence or a different selected pair: still return that original
  historical record, not a replacement or conflicting “better” award.
- Same rule/version but a different claimed released definition: refuse the
  write with a definition conflict; preserve/read the original history.
- Two concurrent issuers: transaction/unique constraint allows one insertion.
  The loser validates/returns the winner, without claiming its own requested
  package was issued. Failed first attempt leaves no half-record; retry can
  insert with its actual later issuance time.

An exact existing receipt remains readable if its evidence later disappears;
returning stored history is not new issuance or proof of present qualification.
Existing malformed slot contents block replacement and produce invalid evidence.

No workspace UUID is included in the identity or slot. The database already
owns workspace-local records. Export can use a corpus-hash fallback, and current
low-level restore does not install the manifest's workspace identity. Those are
not evidence of participant identity or identity continuity. Received award bytes
retain their original issuer/time/ID and occupy their destination ledger slot;
import does not assert that the current operator performed the underlying work.

## 6. Frozen evidence package and exact receipt payload

Freeze one selected witness for Explorer or the selected ordered pair for
Second Opinion. Never enlarge an old award with later qualifying witnesses.
The selection context records the original assessed category; it is not a list
of additional awarded achievements or a second study-history store.

The future package has exactly these keys:

| Package key | Exact source / contract |
| --- | --- |
| `profile` | `perspective-achievement-evidence-package/v1` |
| `assessment` | Exact keys: `result_schema`, `evaluator_version`, `rules_sha256`, `evidence_sha256`, `finding`, `coverage`, `diagnostics`, `limitations` |
| `adapter_basis` | Exact whole-category basis currently hashed inside `evaluate_perspective_achievements`; preserve source state, coverage, diagnostics and K-sorted candidate metadata/digests/eligibility |
| `rule_definitions` | Exact ordered declarations returned by `perspective_achievement_rules()` for the evaluated release |
| `witness_bindings` | Ordered `{receipt_id, run_id, receipt_sha256}` from selected exact canonical P3 rows |

`assessment.finding` is one **unchanged earned item** from `achievements`; the
other achievement's result is not copied. The other assessment fields come
unchanged from the top-level result (`result_schema` names its `schema`). Coverage
in finding, assessment and adapter basis must agree exactly. Diagnostics,
including unrelated invalid/unsupported records, remain exactly as observed.

The adapter basis is currently an internal local value, **not a returned field**.
Its exact existing keys are `source_state`, `coverage`, `diagnostics`, `executions`.
Each execution contains `receipt_sha256`, `lineage_ref`, `family_key`,
`family_state`, `family_evidence`, `family_reason_code`, `dependency_evidence`,
`eligibility_observations`. It contains no model output, prompt, question or Scope
payload. Future packaging must share this existing basis construction, with
unchanged evaluator behavior/results, rather than duplicate validation or invent
missing facts. Only JSON conversion already performed by the evaluator is used,
including converting tuple family keys to lists.

Retaining this metadata makes the **original evidence digest recomputable over
the original recorded basis**. It does not preserve old mutable row bytes or
prove historical enumeration independently; section 10 limits replay claims.
Storing just the selected finding while calling it the full evidence digest
would be false. Do not synthesize the basis from a later database.

The receipt has exactly these top-level keys:

| Key | Required meaning |
| --- | --- |
| `schema` | `hermeneia.perspective-achievement-award/v1` |
| `award_id` | Domain-separated content identity of the complete body excluding only this field |
| `achievement_id`, `rule_id`, `rule_version` | Exact slot, equal to the finding's fields |
| `evaluation_status` | Literal `earned`, equal to finding status |
| `earned_at` | Selected-witness retention threshold defined in section 7 |
| `awarded_at` | Truthful original issuance clock reading defined in section 7 |
| `issuer` | Exactly `{kind: hermeneia, authorship: derived}`; deterministic system assertion, no provider/human authorship attribution |
| `issuance` | Exactly `policy`, `actor`, `actor_identity`, `approved_evidence_package_sha256`; values `explicit-steward-materialization/v1`, `local_steward`, `unknown`, exact package digest |
| `evidence_package` | Exact package above |
| `evidence_package_sha256` | Section 8's distinct package digest; equals approved digest |

The envelope fields/timestamps/issuer are **new award fields**, not claims that
the evaluator already returns them. Package facts come only from available
canonical evidence, rule declarations and the actual evaluated snapshot.

## 7. `earned_at` and `awarded_at`

`earned_at` is the selected witness's recorded retention instant expressed in
aware UTC using the evaluator's timestamp conversion:

- Explorer: the selected receipt's `retained_at_utc`.
- Second Opinion: the later UTC retention instant of its selected pair.
- Equal instants: same derived time; ASCII ID determines witness order only.

Original timestamp strings remain in the finding/P3 parents. This derived field
does not rewrite them, authenticate a clock, infer a session or prove causal order.

**Do not call Second Opinion's value the earliest possible threshold over all
pairs.** The frozen evaluator chooses the lexicographically earliest K pair,
not the pair minimizing its later retention time. For example, selected K pair
at t1/t9 can precede a qualifying t2/t3 pair lexicographically, although the latter
was fully retained earlier. `earned_at` means the recorded threshold of the
selected historical justification, not the first moment the human ever earned it.

`awarded_at` is the actual aware UTC system-clock reading captured for the
successful insertion attempt immediately before constructing the receipt. It is
not an inferred execution time, atomic commit-completion timestamp, import time
or replay time. Exact retries/restores preserve it. Failed attempts do not acquire
historical receipt times. Do not backdate or clamp it to evidence times. Clock
skew can put it before a recorded retention instant; preserve both truthful
readings, report the ordering anomaly, and make no cross-clock causality claim.

## 8. Canonical codec and digest boundaries

Use P3 `canonical_bytes`: finite JSON values with string object keys, sorted
keys, ASCII escaping, compact separators, UTF-8 and **no trailing newline**.
Arrays retain order. No text normalization, field stripping or number coercion.
Do not substitute the build reproducibility core's narrower codec/profile.

Stored `receipt_json` bytes must equal this serialization. Strict parsing rejects
duplicate object keys, invalid UTF-8/BOM, nonfinite numbers, missing/unknown outer
or contract-object fields, malformed IDs/digests/times and inconsistent parallel
bindings. Explicitly open existing P3 execution/metadata dictionaries and
versioned rule-definition payloads retain their finite JSON data; do not silently
strip fields there. Unknown receipt/profile formats are unsupported and not
converted into this format.

Define new digests precisely (`\0` below means one NUL byte, not two characters):

```text
evidence_package_sha256 = "sha256:" + hex(SHA256(
    UTF8("hermeneia.perspective-achievement-evidence-package/v1\0")
    || canonical_bytes(evidence_package)))

award_id = "achievement-award:sha256:" + hex(SHA256(
    UTF8("hermeneia.perspective-achievement-award/v1\0")
    || canonical_bytes(receipt with only award_id removed)))
```

Both are lowercase 64-hex SHA-256. Keep existing meanings unchanged:

- `rule_sha256`: P3 canonical bytes of that one static rule declaration.
- `rules_sha256`: canonical bytes of the ordered declarations list.
- Evaluator `evidence_sha256`: canonical bytes of the complete adapter basis,
  without the new package's domain prefix.
- `receipt_sha256`: exact stored P3 JSON bytes **including** its receipt ID.
- P3 receipt ID: its own established body hash **excluding only its own ID**.

The package digest binds this award's exact finding, rule data, assessment
context and selected receipt/run bindings. It serves as the exact assessment
approval/integrity digest. A separate hash of the full returned two-achievement
result is unnecessary and would bind an unrelated finding; do not misname the
package digest as the evaluator's full-result or evidence digest.

Validate witness cardinality (one/two), distinct receipt/run IDs, positional
agreement of all selected arrays, typed table/key identities, exact K ordering,
time derivation and every cross-field digest. The ID is a byte integrity binding,
not a signature or external authenticity proof.

## 9. Released rule identity and version evolution

Semantic version **plus immutable rule-definition digest**, ordered registry
digest, captured rule declarations and evaluator/result format version identify
the historical assessment. This goes beyond a git SHA while storing no redundant
rule-document prose or model output. The current declarations digest is
`sha256:6b0065fac155c40fc25ce5cc62c53a7c250c0595dd4e49554669bab55e56197c`.

Future verification must use explicitly supported archived rule/evaluator
profiles, including their pinned built-in/template support. Do not call today's
different predicate a historical verifier just because achievement names match.
Captured metadata is not executable code or proof a faulty evaluator was correct.

A changed definition under the same released rule/version is a conflict, never
another slot or a reason to recalculate history. If a rule file's semantic text
changes without a version bump, stop release/materialization until the authority
and released definition are reconciled; matching metadata alone does not excuse
contradictory governing text. Unsupported historical implementation support
remains unsupported. Future implementation repairs must identify their evaluator
version/support profile while preserving issued bytes; they cannot silently
replace a historical algorithm's result.

A new explicitly versioned rule can produce another independently requested
receipt if earned. There is no automatic reaward, supersession, revocation or
mutable `current_valid` field. A new rule's negative assessment changes only the
current evaluation. Current eligibility, original history and verification are
separate outputs even when the historical and current rule versions coincide.

## 10. Historical verification, loss, exclusion and replay

Verification is read-only and never materializes/reconstructs an award. Report
three independent dimensions:

| Dimension | States / scope |
| --- | --- |
| `receipt_integrity` | `valid`, `invalid`, `unsupported`; canonical bytes, body ID, package/definition digests, shape and internal cross-bindings |
| `evidence_verification` | `verified`, `unverifiable_missing_evidence`, `unverifiable_missing_coverage`, `unverifiable_unsupported_rule`, `invalid_evidence`; exact selected historical witness and required closure under the recorded profile |
| `historical_snapshot_replay` | `verified`, `unsupported`, `invalid`; independent reproduction of the original whole-category snapshot/evaluation/selection, not merely rehashing captured metadata |

`verified` evidence requires exact supported witness receipts, the selected
rule's required immutable parents, historical eligibility observations and
available required snapshot evidence. Complete saved-family proof is required
for Second Opinion's family comparison, not for Explorer. Explorer retains its
family-only invalid/unsupported diagnostics without adding that qualification
gate. A valid envelope alone never sets it. Known required immutable
byte/binding contradictions are `invalid_evidence`. Missing rows are
`unverifiable_missing_evidence`; missing schema/coverage or irrecoverable mutable
snapshot material is `unverifiable_missing_coverage`; unavailable historical
rule/evaluator/template support is `unverifiable_unsupported_rule`.

Use deterministic precedence for aggregate evidence state: known invalidity,
then missing evidence, then missing coverage, then unsupported rule, then verified.
Also retain all per-check findings; one headline cannot erase other negatives.
Receipt-invalid/unsupported prevents an earned-provenance claim regardless of
present-looking source files. An existing row is not authenticated issuance.

The stored adapter basis makes its own original SHA-256 checkable. It contains
row **digests**, not old dependency row bytes or a full old database. Candidate
lists/counts are recorded observations, not independently complete historical
enumeration. A verifier may validate exact selected question/Scope/methodology
from intact P3 parents while reporting broader replay unsupported.

In particular:

- New candidates or changed current selection do not replace the original pair.
  A current evaluation differs legitimately; it is not the historical replay.
- Mutable highlight/source-row hash drift after edits or exclusion is not proof
  of award tampering. If the original relevant snapshot cannot be independently
  recovered, report its coverage limit. Do not hash today's row as yesterday's.
- Exclusion can make current eligibility negative while immutable P3 byte
  bindings remain intact. Preserve the historical assertion and captured original
  eligibility; current access checks still suppress excluded content/links.
- Missing ancestors, old graph absence/eligibility evidence, or unavailable
  historical implementation must never be inferred from current files.
- Cryptographic self-consistency of captured observations is not independent
  attestation that the whole past source category was complete.

No full historical snapshot store is added. Full replay after mutable snapshot
loss is expressly not guaranteed by v1. A future stronger guarantee needs a
separately bounded capture/coverage contract; it cannot silently expand this one.

## 11. Revocation, display and privacy

No v1 revocation/update/delete/replacement API. Later rule changes, ineligibility,
corruption, unavailable evidence and preferences affect derived outputs, not the
original row. An invalid purported award is reported as invalid, never rewritten
into a valid one. Formal corrective/superseding judgments or legal redaction need
their own governed append-only/redaction contract.

`award exists`, `display preference` and `notification seen` are independent.
Hiding/dismissing does not delete, revoke, modify or request an award. Notification
and preference storage are outside this packet.

Receipts are canonical local study-history derivatives, not product telemetry,
diagnostics, research/evaluation datasets or training data. Possession, restore,
export and local materialization do not grant institutional research, instruction,
model-evaluation, publication or training consent. No consent/identity system is
introduced; unknown human identity remains unknown.

## 12. Future Study Lineage representation

Use one typed owner:

```text
record = {table: achievement_awards, key: {id: award_id}}
record_type = perspective_achievement_award
event = recorded
authorship = derived
timestamp = original awarded_at
```

Expose achievement/rule/version, original `earned_at` and `awarded_at`, system
issuer, lean selected evidence identities, bounded coverage and separately
derived verification states. Those identities are exactly `{table, key}` from
each selected reference's `record`, never the unchanged `finding.evidence_refs`
objects with their embedded provenance/definition/execution metadata.
Original issuance time places the historical event
in the chronological stream; earned time is secondary recorded-evidence context.
Do not infer causal order from clock values. Unknown authorship of ancestors stays
unknown; the system award is neither human-authored nor model-authored interpretation.

Provide a **safe summary projection** even if evidence later becomes unavailable
or excluded. A valid historical receipt can remain visible with explicit
verification limits. Do not reuse generic full `record_data`/provenance previews:
the private package includes exclusion-sensitive definitions/execution metadata.
Suppress those fields and copied descendant material when access is not eligible.
Only eligible supported context links may open exact underlying P3 receipts;
never substitute a current successor, similar record, filename or model output.
Malformed records yield diagnostics rather than a displayed earned claim.

This narrowly adds a receipt-summary path to the existing shared projection;
it does not weaken P3's exclusion filter. Award rows must remain ineligible as
Perspective achievement inputs and must not accidentally satisfy existing P1/P2
history predicates merely by appearing in Lineage. Any future rule using an award
as evidence requires separate approval/versioning.

## 13. WBS export, restore and backward compatibility

Use the existing additive WBS capability mechanism, not another authoritative
format. Freeze:

```text
required capability: perspective-achievement-awards-v1
component: study/achievement_awards.json
manifest role: canonical
manifest count: achievement_awards
coverage category: achievement_awards
```

“Canonical” here preserves immutable receipt row bytes through exchange/restore
into the authoritative store; it does not promote an award into forensic evidence
or supersede the singular `.herm` Storage authority. The existing WBS version
selection and publication/release identity remain unchanged.

Component entries are exactly `{id, achievement_id, rule_id, rule_version,
receipt_json}` in ASCII ID order. Preserve `receipt_json` as the exact original
canonical string, including all original bindings/times, not re-evaluated content.
The outer WBS file uses its existing deterministic file serialization/hash rules.
Presence/declared capability requires the file and count even for zero rows.
Older readers refuse unknown required capability rather than silently drop history.

**Select strict complete-reference archival export**, consistent with P3:

- All extant award rows join the existing SQLite export snapshot; validate row
  shape/self-binding/slot uniqueness and required typed closure.
- Export exact selected P3 receipts, all supported candidate identities required
  by the stored assessment context, and their P3 reference closure through
  existing components. Complete family closure is required only where it
  supports the selected Second Opinion witness. Explorer family diagnostics and
  unrelated invalid/unsupported family context do not become new valid-parent
  prerequisites. Diagnostic references to malformed unrelated rows are recorded
  findings, not qualifying immutable parents. Existing WBS graph/refusal rules
  still apply independently; this contract does not relax them.
- Excluded ancestors remain archivable under current P3 behavior; exclusion is
  not missing evidence. Mutable historical hash drift is recorded verification
  insufficiency, not a reason to rewrite current rows or old packages.
- Missing/malformed/contradictory required immutable closure refuses the whole
  export. Do not silently omit an award while declaring complete extant coverage.
  The database/award remains untouched and its safe local summary remains readable.

An “award-only incomplete bundle” is not introduced. It would require a new
explicit coverage contract and cannot rescue current export when a P3 receipt
already has broken closure. Strict archival export does not require present
achievement eligibility or successful full historical replay: structural closure
and semantic verification are distinct.

Restore uses the existing fresh/empty-target transaction, dependencies first,
then P3 receipts, then awards. Validate containment, manifest entry uniqueness,
role/hash/count, duplicate JSON keys, exact row schema/canonical receipt bytes,
all row/payload bindings, unique IDs/slots and required closure before acceptance.
Do not let generic column filtering discard unknown award fields. Failure rolls
back award/dependency insertion; no half-history or silent conflict resolution.
An existing `overwrite` option is not permission to replace, ignore or merge
award slots; the new award component retains the fresh-target/no-merge boundary.

| Restore input | Required result |
| --- | --- |
| Valid supported receipt and complete required closure | Restore exact ID/bytes/time/package; report current verification separately |
| Exact duplicate within component | Reject duplicate entries/count ambiguity; exporter emits each row once |
| Exact award already in occupied target | Existing whole-workspace restore refusal remains; no merge/reissuance |
| Same slot, different ID/bytes | Refuse conflict; do not pick a witness/time or merge histories |
| Malformed/contradictory claimed supported receipt | Refuse entire restore |
| Missing required evidence dependency | Refuse entire restore; preview may show insufficiency, not a valid restored award |
| Unknown future rule/evaluator version in a understood receipt/profile and closed P3 graph | Preserve self-valid historical bytes; `unverifiable_unsupported_rule`, no fabricated earned revalidation |
| Unknown receipt/package format or required capability | Refuse unsupported format before accepting those records; no lossy conversion |

For the understood v1 wire shape, versioned rule-definition payloads may be
self-bound without being executable/supported; preservation does not certify
their semantics. Unknown wire structures cannot be treated as that known shape.

Legacy bundles/stores remain readable under previous contracts. No component/
capability or missing required columns means **unsupported award-history coverage**,
not zero historical awards. Supported component with zero entries covers only
zero extant awards in that export snapshot. Schema initialization after an old
restore does not manufacture imported historical coverage; import/preview must
retain the original unsupported result, while later local evaluation speaks only
about its current extant category. No backfill, migration of old reports, inferred
awards from P3 history, or claim of complete intellectual history is permitted.

## 14. Minimum future store and implementation invariants

Recommend the P3 pattern combining options A/B: one narrow append-only table
holding strict canonical receipt JSON and indexed mirrored identity fields:

```text
achievement_awards
  id              TEXT PRIMARY KEY
  achievement_id  TEXT NOT NULL
  rule_id         TEXT NOT NULL
  rule_version    TEXT NOT NULL
  receipt_json    TEXT NOT NULL
  UNIQUE(achievement_id, rule_id, rule_version)
```

Primary key supports direct lookup. The unique index supports exact slot lookup
and achievement-prefixed history. Do not add speculative indexes or duplicate
earned/current-valid columns. Enforce UPDATE/DELETE refusal and INSERT OR REPLACE
refusal by both ID and slot at database level. Domain validation checks JSON
mirrors and typed reference closure; JSON references do not become fake SQL FKs.
This is a future additive schema step, not a migration made here. Explicitly
reject generic events, award CRUD and parallel source/output stores.

Implementation must enforce:

1. Existing evaluator/rules/P3 meanings stay unchanged and provider-free.
2. No read, GET, Lineage opening/filter/export or verification issues an award.
3. Exact explicit materialization request; canonical re-evaluation and stale
   refusal; committed evidence and separate award-owned transaction.
4. Earned-only insertion, strict canonical serialization/readback, immutable
   receipt/slot guards, safe concurrent retry, original-byte return.
5. Original selected witnesses and assessment context are never enlarged/replaced.
6. Distinct package/body/P3/rule digests retain their precise boundaries.
7. Historical/current/verification outputs remain separate; every unsupported or
   invalid finding remains visible, with no invented historical snapshot.
8. Safe Lineage summaries never disclose excluded descendant content; awards
   do not become capability/achievement prerequisite evidence.
9. Required capability + complete structural WBS closure, exact restore, explicit
   legacy/unknown-format refusal and no merge or inferred identity continuity.
10. No named-person authority, intellectual ratification, consent, release identity,
    automatic notification/UI policy, new achievements or recursive rewards.

## 15. Failure and edge-case matrix

This is a **normative design matrix, not executed persistence tests**. “Current”
means an independently selected current evaluation; “verified” always has section
10's qualified scope. `closed` means structurally valid required archival closure,
not current access eligibility or complete independent historical replay.

| # / Case | Historical award exists? | New write permitted? | Current evaluation meaning | Verification meaning | Portability behavior |
| --- | --- | --- | --- | --- | --- |
| 1 Explorer earned, no prior slot | After successful issuance only | Yes, exact D request | One supported retained witness | Check original package/one witness | Export when closed |
| 2 Second Opinion earned, no prior slot | After successful issuance only | Yes, exact D request | Exact supported ordered pair | Check original package/pair | Export when closed |
| 3 `not_earned` | Any prior history stays | No for this assessment | Supported current snapshot negative | Prior receipt checked separately | Preserve prior closed receipts |
| 4 Unsupported evaluation | Any prior history stays | No | Missing support is unknown, not failure/absence | Report unsupported dimension | No inferred award/history coverage |
| 5 Invalid evaluation | Any prior history stays | No | Relevant integrity failure | Preserve exact negatives | Corrupt required closure refuses |
| 6 Retry after successful issuance | Original receipt | No new row; return original | May now differ | Original time/package unchanged | One exact portable row |
| 7 Concurrent duplicate issuance | One winner | At most one row | Each request initially earned; loser did not issue its package | Validate returned winner | No duplicate slot |
| 8 More/new qualifying evidence | Original receipt | No same-slot row | May select another witness | No original-witness replacement | Original bytes + extant study evidence |
| 9 Earned under new rule version | Old plus separately requested new receipt | Yes, new version slot | New predicate independently assessed | Each historical profile separately | Both exact rows; no merge |
| 10 New rule says not earned | Old receipt remains | No new negative award | Current negative is not revocation | Verify old rule or report unsupported | Keep old closed history |
| 11 Award write fails after Keep committed | None new; earlier awards untouched | Retry with truthful later time | Underlying retained receipt remains valid | No partial award | Existing evidence remains portable |
| 12 Referenced evidence later corrupts | Original purported record remains | No replacement | Current invalid where relevant | `invalid_evidence`, not verified | Refuse required corrupt closure |
| 13 Restore valid award/complete closure | Same received historical record | Restore exact bytes, not new issuance | Separate current assessment | Verify supported profile; replay limits remain | Exact ID/time/package round trip |
| 14 Restore missing required dependency | No new target award accepted | No | Evidence/coverage insufficient | `unverifiable_missing_evidence` in inspection | Whole restore refusal; source unchanged |
| 15 Legacy bundle, no award coverage | Unknown past awards | No fabricated restore/backfill | Current local extant result cannot prove old absence | Unsupported imported history | Previous bundle contract remains readable |
| 16 Conflicting same-slot restore | Source receipts stay; target untouched | No merge/selection | Not an eligibility decision | Conflict/invalid component | Atomic refusal |
| 17 User hides UI | Unchanged | Hiding permits no issuance | Independent | Unchanged by preference | Original row still included |
| 18 Rule semantics edited without bump | Original receipt remains | No under conflicting release | Untrusted/conflicting current rule profile | Historical frozen profile separate | Self-valid historical rows remain; no reinterpretation |
| 19 Claimed rule-definition digest mismatch | Preserve purported bytes | No | Claimed supported binding invalid | Receipt/package/rule integrity failure | Refuse malformed claimed profile |
| 20 Malformed award receipt | Purported row, not trusted earned fact | No replacement | Underlying study evaluation stays separate | `receipt_integrity=invalid` | Refuse component/restore |
| 21 Source later excluded; output intact | Original receipt remains | No same-slot replacement | Excluded witness cannot qualify now; another witness may | Byte checks can pass; original mutable snapshot may be unavailable | Excluded ancestors archivable; safe summary only |
| 22 Same snapshot repeatedly evaluated | No new history from reads | Only first exact explicit issuance | Deterministic same result | Read-only checks | Reads do not change bundle bytes/state |
| 23 Historical evaluator unavailable | Original receipt remains | No unsupported new issuance | Current supported evaluator, if any, is separate | `unverifiable_unsupported_rule`; self-binding may pass | Preserve understood closed receipt shape |
| 24 Future app does not understand old rule | Original receipt remains | No under unsupported historical profile | Cannot infer old conclusion from current rule | Unsupported semantics, never inferred pass | Preserve understood wire format; refuse unknown wire/capability |
| 25 Assessment changes before approved request is recorded | No new receipt | Refuse stale; new review required | New exact snapshot may still be earned | No old request silently substituted | Existing history unaffected |
| 26 Mutable mark legitimately edited | Original receipt remains | No same-slot reaward | P3 capture stays historical; current assessment digest may change | Old row digest drift is missing snapshot support, not tampering | Preserve original package and current records distinctly |
| 27 Clock readings place issuance before selected retention | Original receipt if otherwise valid | D may record truthful readings | Predicate/time ordering within P3 unchanged | Report anomaly; no invented clock/causal claim | Preserve both exact readings |
| 28 Unrelated malformed row beside valid earned witness | Receipt may be issued under existing existential rule | Yes if current evaluator earned and exact request matches | Invalid diagnostic remains visible | Original diagnostic retained | Existing strict P3 export may refuse corrupt row; award stays local |

## 16. Validation performed and bounded next packet

Read repository guidance/current authorities, live #212–#215 bodies and relevant
#214/#215 handoff comments, frozen designs, actual evaluator/adapter/P3/storage,
Lineage and WBS paths. Verified clean `main` includes the required evaluator commit.
Independent read-only reviews checked authority/issuance, portability and evidence
bindings; recommendations here distinguish existing behavior from future design.

A provider-free temporary synthetic probe used the **existing** evaluator test
builder to create two valid retained executions, then inspected the real returned
earned results. It confirmed the field inventory above, absence of an explicit
result `run_id`, preservation of a finite `temperature=0.7` in captured execution
metadata, and unchanged database bytes/logical rows during adapter/evaluation.
This was a field inspection, not an award implementation or persistence test.
No real workspace/private text/model was used. No production or test file changed.

Documentation references/field paths and `git diff --check` are checked for this
packet. No full suite is required or claimed for a docs-only change; the evaluator
note preserves its measured **2,320 passed / 21 skipped / six unchanged Reader
failures** baseline, which is not presented as a fresh run here.

Next bounded packet after review: implement this strict domain-specific codec,
shared exact assessment packaging, explicit idempotent materialization/store and
read-only historical verifier, together with the narrow Lineage safe-summary and
WBS capability/component/restore support and adversarial tests. No achievement UI,
notifications, automatic issuance, vectors, new families, consent system or broad
refactor. Test concurrency, stale requests, failure isolation, original bytes,
historical snapshot limits, exclusion safety and unsupported versions; rerun
focused P1/P2/P3/Lineage/WBS and the full suite against an independent baseline.
No awards are release-ready until the complete declared portability seam passes.

**GO — current evaluator/evidence architecture is sufficient for append-only award persistence with bounded additive schema/WBS/Lineage work.**

This verdict is for the narrow explicitly requested historical assessment and
honest verification limits above. It is not a claim that full historical snapshot
replay survives missing mutable history, that autonomous issuance is authorized,
or that any persistence/portability implementation already exists.
