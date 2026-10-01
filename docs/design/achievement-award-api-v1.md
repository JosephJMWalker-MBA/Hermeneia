# Explicit Perspective achievement award API v1 — P4

Implemented from `e038e6d1b64dea9e7aa80356669555166104c825` for
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215), under the
steward decisions in [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214).
This is a thin web interface over the existing award domain, governed by the
[frozen receipt contract](achievement-award-receipt-contract-v1.md),
[persistence implementation](achievement-award-persistence-v1.md), and
[read-only evaluator](perspective-achievement-evaluator-v1.md).
It adds no rule, receipt codec, schema, authority, UI, or automatic issuance.

## Routes and representations

| Method / route | Meaning |
| --- | --- |
| `GET /api/achievements/perspective/<achievement_id>/assessment` | Current read-only evaluation and, only when earned, exact approval package |
| `POST /api/achievements/perspective/<achievement_id>/award` | Explicit materialization through the domain transaction |
| `GET /api/achievements/perspective/awards` | Validated historical award summaries |
| `GET /api/achievements/perspective/awards/<award_id>` | One validated historical award summary |
| `GET /api/achievements/perspective/awards/<award_id>/verification` | Current verification of that historical record |

All handled responses are JSON with `Cache-Control: no-store`; unsupported HTTP
methods retain Flask's existing 405 behavior. No generic achievement
family, update, delete, revocation, or evaluation-as-issuance route is introduced.

Assessment returns the selected evaluator finding unchanged as top-level fields,
including `achievement_id`, `rule_id`, `rule_version`, `status`, `reason_code`,
`reason`, `evidence_refs`, `qualifying_receipt_ids`, `coverage` and the other
existing finding fields. It adds the actual `evaluator_version`, `limitations`,
`assessment_package`, and `assessment_package_sha256`.

For `earned`, the package and domain-separated digest are the exact domain
preparation result; no alternate approval representation is hashed. For
`not_earned`, `unsupported_due_to_missing_coverage`, or `invalid_evidence`, both
package fields are null and the evaluator's state/reason remain intact. The
preparation seam only returns earned packages, so the route obtains negative
findings from the existing evaluator in the same read-only SQL snapshot.

POST accepts exactly:

```json
{
  "rule_id": "achievement.perspective_explorer",
  "rule_version": "1.0.0",
  "assessment_package_sha256": "sha256:<64 lowercase hex characters>"
}
```

The achievement is named in the route. Both rule fields remain explicit intent
guards; the domain decides executable support. Additional content, receipt,
actor, or client-authored evidence fields are refused. Duplicate JSON object
keys are also refused, including identical repeats; the decoder never chooses
one of multiple approval values through last-key-wins parsing.

Successful POST returns `status` (`recorded` or `already_recorded`), `award_id`,
`receipt_representation: "safe_summary"`, and `receipt_projection`. Detail uses
the same labelled projection without issuance status. List returns `awards`
containing those summaries and the same representation label. A projection is
never advertised as the complete canonical receipt or used to regenerate its ID.
The exact canonical receipt remains unchanged in the database and WBS contract.

## Current approval versus historical disclosure

The frozen contract preserves captured Perspective definitions and open execution
metadata in a private historical package, while section 12 specifies a safe
award-summary projection. This initially appeared to conflict with exposing an
exact current assessment. Examination of the actual adapter resolves the current
case: each packaged candidate comes from an already-eligible P3 Lineage item,
with source/reference closure validated. Those definition/execution fields are
already inspectable through eligible Lineage/P3 context, and the explicit API
packet requests this exact current approval package.

The package does not copy the retained response, prompt, inquiry question, or
complete Scope text. It contains unchanged eligible provenance, typed references,
digest/binding evidence and the existing evaluator metadata. Excluded candidates
do not enter its adapter basis; bounded diagnostics retain codes/typed IDs.
This is not permission to disclose an arbitrary historical private package.

A historical award survives exclusion, missing ancestors and changed eligibility.
Its raw package may therefore contain metadata no longer accessible through
current contexts. All historical list/detail and issuance responses use the
existing Lineage `record_data` whitelist, even when ancestors remain eligible:

- Award, achievement, rule/version, original earned/issuance times and system issuer.
- Package profile, lean selected `{table, key}` receipt identities and bounded coverage.
- Explicit summary-only verification limits: receipt integrity validated,
  evidence verification `not_performed`, replay `unsupported`,
  `reason_code: LINEAGE_SUMMARY_ONLY`.

No historical response copies definitions, execution options, the full finding,
adapter basis, model output, source content, or raw receipt JSON. The pure web
helper reproduces the approved whitelist from a domain-validated receipt without
calling Lineage, preparation or the current evaluator just to inspect history.
Tests compare it directly with existing Lineage summaries to prevent drift.
Idempotent POST retries use this boundary too, including after source exclusion.

## HTTP and domain states

| Condition | HTTP / response |
| --- | --- |
| Successful read, including negative assessment | 200; exact structured domain state |
| New award | 201, `recorded` |
| Existing logical slot | 200, `already_recorded` |
| Malformed intent/body/digest | 400, `MALFORMED_AWARD_REQUEST` |
| Unknown achievement or absent award in supported storage | 404, `UNKNOWN_ACHIEVEMENT` / `UNKNOWN_AWARD` |
| Missing workspace database | 404, `WORKSPACE_NOT_FOUND` |
| Changed approval digest or current non-earned assessment | 409, `STALE_ASSESSMENT` |
| Unavailable/wrong executable rule or issuance coverage | 409, `UNSUPPORTED_AWARD_RULE` |
| Invalid canonical award on inspection/issuance | 409, `AWARD_INTEGRITY_INVALID` |
| Unsupported historical format/profile or unreadable read coverage | 409, `AWARD_COVERAGE_UNSUPPORTED` |
| Issuance storage failure | 409, `AWARD_STORAGE_UNAVAILABLE` |
| Unexpected internal failure | 500, bounded `AWARD_REQUEST_FAILED` |

Errors do not expose raw exception text, SQL, payload content or tracebacks.
Missing award-category coverage is refused rather than displayed as empty history.
List validates all rows before emitting any summary; one malformed record refuses
the read. Unsupported executable historical rules do not block structurally valid
historical detail; format support and current rule execution remain separate.

Verification returns the existing verifier report directly, including separate
`receipt_integrity`, `evidence_verification`, `historical_snapshot_replay`, checks
and limitations. Its negative/unsupported findings remain structured 200 reports,
including malformed receipt findings; no Boolean success collapse or repair is
performed. Unknown IDs are distinguished before verification.

History order is canonical UTC `awarded_at`, then ASCII `award_id`. Receipt
validation establishes canonical timestamps/IDs before ordering. Current
eligibility does not affect historical list/detail contents or ordering.

## Explicit writes, staleness and retries

```text
GET current assessment → approve exact digest A
canonical committed evidence changes
POST A → 409 STALE_ASSESSMENT; no award added
GET current assessment → approve exact digest B
POST B → 201 recorded
POST B again → 200 already_recorded; original award ID/bytes/times preserved
```

After a valid logical slot exists, the domain returns its historical receipt even
after additional evidence, a changed selected witness or current ineligibility.
The route neither retries preparation for the client nor replaces that witness.

Every new GET opens the existing SQLite `mode=ro` connection with `query_only`
and one snapshot, then closes it. It never constructs a store, initializes
award coverage, writes preferences/progress, or invokes materialization. Existing
Study Lineage and Guide reads remain non-issuing. P1 currently has no standalone
Capability GET; its evaluator and the Guide's Capability projection remain reads.

Only the explicit new POST invokes materialization. It opens the existing write
connection with foreign keys enabled and supplies the exact request fields to
the domain. It does not start a competing transaction. The unchanged domain owns
committed re-evaluation, `BEGIN IMMEDIATE`, slot idempotence, byte verification,
commit/rollback and preservation of previously committed P3 evidence.

The existing unauthenticated local-steward/loopback runtime assumptions remain
unchanged. No authentication, CSRF, custody, participant identity or disclosure
exception is invented. All operations use recorded evidence and require no
provider/model call or historical regeneration.

## Verification and limits

Validation completed 2026-10-01 against disposable synthetic studies. No real
workspace issuance, provider access or user-facing achievement UI was exercised.

Focused tests passed **95 cases**: **85 API** and **10 disclosure-boundary** tests.
Both Explorer and Second Opinion exercised the complete synthetic prepare,
explicit issue, history, detail and three-dimension verification flow with provider
and network tripwires. No manual UI or live-provider validation is claimed.
Focused evidence: `/private/tmp/hermeneia-award-api-focused.xml`.

The initial API tests failed with 404 before route registration, preserving the
missing-interface witness. Additional safety fixtures preserve exact historical
metadata while proving that its summary is not a substitute approval package.
Three adversarial duplicate-field cases first returned **201**, demonstrating
that Flask discarded contradictory approval fields and issued an award. After
the bounded request-decoder repair, all return **400** with unchanged study
rows. The failing JUnit witness is
`/private/tmp/hermeneia-award-api-duplicate-intent-before.xml`.

An independent archive of starting `e038e6d` reproduced **2,512 passed,
21 skipped and six established Reader failures**. All 637 tracked archived files
matched Git blobs and stayed unchanged. Imported modules resolved into the archive.
Evidence: `/private/tmp/hermeneia-award-api-baseline-e038e6d-20261001`.

Existing focused regression suites with the integrated routes passed **630** cases:
P1 55; P2 67; P3 123; read-only P4 evaluator 92; award persistence/verifier/Lineage/WBS
192; Study Lineage 75; existing WBS 26. Runtime/JUnit/grouped evidence:
`/private/tmp/hermeneia-award-api-regressions-20261001`.

The final full suite completed with **2,607 passed, 21 skipped and six failures**
(2,634 collected cases, 125.46 seconds). All 95 new cases were included, and the
production/test bytes remained unchanged through final verification. JUnit
comparison against the independent archive confirmed these exact unchanged
failure identities:

```text
tests.test_reader_accessibility::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests.test_reader_accessibility::test_failed_or_missing_page_cannot_speak_prior_page_source
tests.test_reader_blueprint_workstation::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests.test_reader_record_view::test_record_tab_and_panel_present
tests.test_reader_record_view::test_record_is_a_workstation_mode_not_a_separate_drawer
tests.test_reader_voice_profile::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

The first full run completed before the last six request-validation cases were
collected; the final run above includes them all. It supersedes that incomplete
collection. Final evidence:
`/private/tmp/hermeneia-award-api-full-final.xml`,
`/private/tmp/hermeneia-award-api-full-final.log`, and
`/private/tmp/hermeneia-award-api-full-final-result.json`.
`git diff --check` also passed. This packet changes only production web routes
and response/request helpers in `hermeneia/web/app.py`, the two API/safety test
files and this note.

Achievement UI, notification/preferences, automatic issuance, new rules/families,
release/package equivalence, revocation and authenticated participant authority
remain deferred. The next bounded packet should first validate the explicit
prepare/approve/inspect flow through a separately authorized client integration;
it must preserve these read/write and disclosure boundaries.
