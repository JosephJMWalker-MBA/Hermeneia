# Explicit Perspective accomplishment client v1 — P4

Implemented from `728cc3f9c562dc9ab7673bec31735a2fefff3615` for
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215), under the
steward decisions in [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214).
This is a presentation and API-orchestration packet governed by the
[award API](achievement-award-api-v1.md),
[frozen receipt contract](achievement-award-receipt-contract-v1.md),
[award persistence](achievement-award-persistence-v1.md),
[read-only evaluator](perspective-achievement-evaluator-v1.md), and
[Perspective rules](perspective-achievement-rules-v1.md).
It changes no achievement predicate, record format, persistence, WBS, or authority.

## Placement and supported states

**Reader tools dock → Guide → Study accomplishments**, immediately below the
existing Companion-led Study Cycle. A unique host uses the existing Guide
styles; it is not duplicated in the first-run guide or made into another screen.
The section starts closed. **Check accomplishments** explicitly reads the two
current assessments and historical award list; there is no polling or automatic
check from ordinary Guide rendering.

Only `perspective_explorer` (Perspective Explorer) and `second_opinion`
(Second Opinion) are exposed. Current assessment is separate from historical
awards and current verification. The client presents server states without
recomputing qualification:

| Server assessment | Presentation / permitted action |
| --- | --- |
| `earned` | Ready to record; may open review |
| `not_earned` | Neutral statement that current qualifying evidence is absent; cannot record |
| `unsupported_due_to_missing_coverage` | History unavailable; never translated into not earned |
| `invalid_evidence` | Unable to verify; cannot record |
| Failed or unsupported response | Current assessment unavailable; explicit check again |

History preserves the server's order, award IDs, original UTC strings and rule
versions. An empty list and history that has not been read are distinct states.
Current eligibility does not rewrite, remove or replace an original award.

## Review, approval and stale evidence

**Review and record** opens an inline review region without a POST. It displays
the exact server rule/version, safe qualifying-receipt count and coverage state.
Second Opinion explains the server's recorded question/Scope/frame and distinct
methodology finding; this copy is not a client-side predicate. Recording is
described as an append-only historical award, not proof of agreement or mastery.

Only the separate **Record achievement** click calls the award API. Its JSON
body contains exactly the reviewed `rule_id`, `rule_version` and
`assessment_package_sha256`, unchanged. No digest, Perspective distinctness,
question equality, Scope equality, award ID or verification finding is computed
in the browser. Server idempotence and the domain transaction remain authoritative.
The client guards and disables pending issuance to prevent rapid duplicate
requests; it never optimistically inserts an award into history.

On `409 STALE_ASSESSMENT`, the reviewed approval is discarded and the affected
current assessment is removed. **Review updated assessment** performs fresh
reads, opens the newly supported review, and requires another final recording
click. It never automatically reissues. Refreshes discard prior approval;
request sequence and workspace-epoch guards reject late responses. A workspace
switch in progress blocks recording. A read discarded during an aborted switch
releases only its own loading state and requests another check.

`recorded` and `already_recorded` responses trigger a historical-list read, not
local award construction. An unknown write outcome requires successful history
reconciliation before another approval is offered. A failed reconciliation
keeps recording disabled and offers an explicit history refresh. Refused
requests and local failures use bounded deterministic copy, never an inference
that an award cannot exist. Achievement requests suppress the shared error
banner's response text; the consumed presentation option is not sent to fetch.
Other callers retain the helper's existing error behavior.

## Inspection and safe disclosure

**Inspect** independently reads the safe detail and verification routes. It
shows rule/version, earned time, recorded time, recorded issuer kind/authorship
and three separate server dimensions:

- `receipt_integrity` — receipt integrity, not an authenticated actor or clock;
- `evidence_verification` — currently available required canonical evidence;
- `historical_snapshot_replay` — independent replay of the original assessment
  under its recorded profile, not today's current eligibility.

Each dimension retains its server state with bounded explanatory text. Missing
evidence, missing coverage, unsupported rules/replay and invalid evidence remain
limitations or negatives; none becomes success. Failed reads leave the listed
historical record visible and explain what could not be determined. Verification
does not issue, delete or rewrite an award.

The assessment endpoint supplies its approval package, but the client retains
only a small presentation descriptor and the exact approval digest. It never
renders or retains the package, definitions, execution metadata or full evidence
references in feature state. History/detail use labelled `safe_summary`
representations. No raw P3 result, source passage, model response, hidden prompt,
SQL diagnostic or excluded source context is fetched to enrich the display.
API-derived display strings are escaped. Awards are not stored in localStorage.

## Read-only defaults, provider independence and accessibility

Opening Companion, Study Cycle, Accomplishments, review, history, inspection or
Lineage; closing review; keeping a Perspective; and reloading do not issue an
award. Existing Companion rendering only rerenders this disposable projection.
Existing workspace reset clears its state; no event bus, preference persistence
or second canonical store is added.

The surface uses deterministic copy and local APIs. It needs no API key, provider,
model, model-generated explanation or outbound network connection.

Review and inspection are labelled inline regions, following the Guide pattern,
not modal dialogs. Focus moves to their heading and survives asynchronous or
ordinary Companion rerenders. Escape closes the region without closing the Guide
and returns focus to the invoking button; unavailable/disabled invokers fall
back to the live status area. Buttons have explicit labels. Loading, bounded
errors and outcomes use status/live-region announcements. Pending Record is
disabled; keyboard activation follows the same explicit approval guard.

## Verification — 2026-10-01

`tests/test_achievement_client_integration.py` adds **60 passing cases** executing
the actual extracted client JavaScript with the established Node/DOM convention.
These include actual shared JSON-helper tests and three client-JavaScript → real
Flask API sequences over disposable canonical study fixtures: Explorer, Second
Opinion and stale assessment A → B. Provider creation and outbound socket
tripwires enforce the provider-free boundary. API GETs preserve award row counts;
only an explicitly confirmed successful POST adds a row. Existing P3 bytes remain
unchanged in the successful Explorer/Second Opinion tests.

Deterministic failures were preserved before their bounded UI repairs: overlapping
full/history reads left loading stuck; a late old-workspace refresh opened a new
workspace review; native node replacement lost inspection/review focus; a disabled
invoker could not regain focus; an aborted switch left loading stuck; replay used
current-evidence wording; and adversarial GET/POST error text escaped through the
generic banner. The banner witness is an adversarial client boundary finding,
not an observed leak from the current server, whose handled errors are bounded.
Tests retain their failing assertions after repair.

Checks on the final source:

| Check | Result |
| --- | --- |
| New executed client/UI/API integration cases | 60 passed |
| Existing Companion + P2 | 80 passed, including 27 UI cases |
| Existing P3 Perspective receipts/API/Lineage/WBS/UI | 123 passed, including 14 UI cases |
| Achievement API/disclosure boundary | 95 passed |
| Award persistence/verifier/Lineage/WBS | 192 passed |
| Read-only achievement evaluator | 92 passed |
| Study Lineage | 75 passed |
| P1 and existing WBS controls | 81 passed |
| Existing focused regression total | 738 passed |
| Full suite | 2,667 passed; 21 skipped; six unchanged Reader failures |

Commands were `python3 -m pytest -q tests/test_achievement_client_integration.py`,
the 27 existing files listed by the above groups, and `python3 -m pytest -q`.
Independent starting-baseline testing used a Git archive of `728cc3f`, verified
all 640 tracked files against Git blobs before/after, and verified package imports
resolved to that archive: **2,607 passed, 21 skipped, six Reader failures**. The
final suite includes all 60 new cases and exactly the same six failure IDs:

```text
tests.test_reader_accessibility::test_failed_or_missing_page_cannot_speak_prior_page_source
tests.test_reader_accessibility::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests.test_reader_blueprint_workstation::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests.test_reader_record_view::test_record_is_a_workstation_mode_not_a_separate_drawer
tests.test_reader_record_view::test_record_tab_and_panel_present
tests.test_reader_voice_profile::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

An actual in-app browser smoke used a separate localhost server and synthetic
database, with an unavailable credential store and provider-creation tripwire.
It did not touch the existing browser/workspace at port 8967. Opening Guide,
checking both earned assessments and opening review left zero award rows.
Appending a synthetic retained receipt while Explorer review was open made the
first explicit POST return `409 STALE_ASSESSMENT` (0 → 0 rows). Updated review
still left zero rows; a new final click returned 201 (0 → 1). Second Opinion's
review and separate keyboard recording returned 201 (1 → 2). Both inspections
showed `valid` / `verified` / `verified` separately, retained focus after loading,
and Escape restored the historical invoking button. After the final client reload,
an explicit Explorer retry returned 200 (2 → 2), preserved both original recorded
times, and final inspection showed the distinct replay explanation. Ordinary
Guide/reload/inspection/Lineage navigation issued no POST. The only four POSTs
were those explicit final actions; all observed GETs preserved award counts and
the provider tripwire remained untouched.

Disposable logs/JUnit and browser witness metadata are under
`/private/tmp/hermeneia-award-client-*20261001*` and
`/private/tmp/hermeneia-achievement-client-*`. The committed tests preserve
repeatable witnesses; temporary runtime databases are not product evidence stores.

## Deferred boundary and next packet

No new API/server/domain/schema/WBS semantics were needed. No ambiguity required
a new steward decision. This validates local synthetic execution and browser
interaction, not live study usefulness, cross-browser coverage, a screen-reader
audit or hosted CI. Existing Reader failures remain unresolved.

Next bounded packet: steward-supervised real-use validation of these two
accomplishment flows on one existing study, preserving the original records and
documenting current assessment versus historical award versus verification.
Any historical write still requires the steward's explicit final approval. Stop
on inadequate coverage or misleading presentation before repairing semantics.

Deeper achievement families, dashboards, points, notifications, revocation,
rule migration, generic award architecture and provider work remain deferred.
