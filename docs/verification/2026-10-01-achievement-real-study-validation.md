# Guided Study Cycle and accomplishments: real-study validation

Date: 2026-10-01. Starting revision:
`eadde234493da9b95c23c8a3a7aea53eb48bb568`.
Observational packet for [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215),
under the steward decisions in [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214).
No production code, rules, records, schema, or historical reports were changed.

## Outcome and selected study

The genuine existing study is represented only as `study-d88c4a642956`, an alias
derived from a hash of its durable workspace identity. It has substantial retained
Reader evidence but lacks the Perspective receipt category. Both Perspective
Explorer and Second Opinion return `unsupported_due_to_missing_coverage`, and the
client communicates unavailable history without declaring failure or offering
award recording. This is a valid unsupported outcome, not a demonstration of an
earned real-study achievement.

Structural discovery examined four existing database candidates in the local
runtime and migration-backup roots: the active study, its older portable copy,
and the corresponding backup copies. None contained retained P3 receipts. The
active study was selected because it retains 395 Reader marks; the older portable
copies omit those accumulated marks. This was a bounded local search, not proof
that no richer study exists elsewhere. Exactly one study was served, through a
private copy. No records were created to qualify it.

## Safety and scope of the observation

The original database was never opened through SQLite or served. Its database,
WAL/SHM files, source upload, calibration file, and older portable-copy files were
captured and guarded privately: seven regular files in total. Paths, exact hashes,
workspace identity, source text, and complete projection data remain private and
are not included in this note.

The harness configured the production Flask app against an absent copy path,
then installed the captured legacy files. It constrained database connections to
that private copy with `mode=ro` and `PRAGMA query_only=ON`, and refused every
non-GET HTTP request. This bypasses ordinary startup schema initialization and
preserves the captured study's missing historical categories. It therefore tests
the **preserved legacy state**, not the post-initialization state of an ordinary
application launch.

That distinction matters: normal startup can initialize empty current P3/award
tables. The accepted
[P3 receipt contract](../design/perspective-execution-receipt-v1.md),
[evaluator contract](../design/perspective-achievement-evaluator-v1.md), and
[award receipt contract](../design/achievement-award-receipt-contract-v1.md)
permit extant-category coverage; they do not establish complete imported
historical activity. The harness neither manufactures those categories nor
equates a missing category with supported empty historical coverage.

Provider creation and outbound socket connections were blocked, and the app used
an unavailable credential store. There were **zero provider/outbound attempts**.
Local provider-descriptor GETs made by the existing UI are not model execution.
All observed assessment requests were read-only.

## Structural baseline

Counts describe extant storage, not intellectual completion or human authorship.

| Material/category | Captured state |
| --- | --- |
| SourceDocument | 1; none excluded from analysis |
| SourceExtraction | 1,738 |
| Canonical Observation | 2,369; source-derived units |
| Reader marks | 395: 393 observation candidates, 2 saved highlights |
| Nonempty Reader note fields | 367 mutable annotation fields; not separate note-history identities |
| Nonempty Reader question fields | 0 |
| Separately identified inquiry notes | 0 |
| Evidence Board grouping state | 1 distinct nonempty theme label, 0 evidence labels; mutable current state |
| Current workspace governing-question record | 0 |
| Saved Perspectives | 0 |
| Retained P3 execution category | Table absent; extant count unsupported, not a covered zero |
| Canonical Interpretations / staged proposals | 0 / 0 |
| Blueprint versions / supersession relations | 0 / 0 |
| Critic reports / Steward decisions | 0 / 0 |
| Award category | Table absent; no stored award rows, historical coverage unsupported |

There is no retained P3 chain, qualifying Second Opinion pair, explicit proposal
decision, or Blueprint chain to inspect in this study. The older local portable
format has no P3 coverage evidence; no export, restore, or migration was performed.
This run does not validate real P3 portability.

## Guided Study Cycle

All eleven step detail views were opened in the real client. By capability ID,
the server projection matched P1's status, availability, definition version,
reason code, readiness explanation, and coverage/unknown notes. P1's alphabetical
array order and the Guide's study order were compared separately. The Guide's
presentation status is intentionally distinct from P1's historical status.

Every step displayed **History unsupported**, with the explicit sentence
“Historical exercise is unsupported; this is not a failure.” No current material
was presented as a completed historical method. `Available now` explicitly
states that prerequisites do not authorize execution.

| Step | Current-state label | Readiness | Explanation observed | Offered action / configured destination |
| --- | --- | --- | --- | --- |
| `governing_question` | Ready to use | Available now | Current governing question is not established; set a compass, not a conclusion. | Set or revisit the governing question → Reader Question |
| `read_source` | Current material present | Available now | Source is readable; reading and comprehension are not measured. | Open the source and read a small passage → Reader |
| `mark_evidence` | Current material present | Available now | Saved marks exist; historical marking and authorship remain unknown. | Mark one passage that matters → Capture |
| `record_observation` | Current material present | Available now | Canonical source units exist; compiler segmentation differs from human attention. | Inspect source units or an anchored candidate → Observations |
| `preserve_question` | Ready to use | Available now | A separately identified inquiry question is not established. | Preserve a question beside an Observation → inquiry context/Corpus chooser |
| `organize_evidence` | Ready to use | Available now | Enough distinct anchors exist; labels establish neither organization history nor Scope admission. | Compare and group retained evidence → Evidence |
| `explore_perspective` | Prerequisite needed | Not yet available | Requires a current governing or supported preserved inquiry question. | Choose a frame and examine evidence → Perspective |
| `form_interpretation` | Prerequisite needed | Not yet available | Requires a named saved or explicitly supplied current Perspective frame. | Form or inspect a provisional interpretation → interpretation context/Corpus chooser |
| `challenge_interpretation` | Prerequisite needed | Not yet available | Requires an eligible Interpretation or staged proposal. | Search source passages for counterevidence → Search |
| `review_blueprint` | Prerequisite needed | Not yet available | Requires an eligible saved Blueprint. | Review Blueprint against evidence → Blueprint |
| `review_lineage` | Ready to use | Available now | Inspect retained history and unknowns; review itself is not durably recorded. | Inspect recorded study lineage → Evidence Board, Lineage |

The recommendation was `governing_question`. Given substantial anchors but no
current governing question, separate inquiry note, saved frame, or later retained
interpretation, this sensibly orients the study. It does not discard the existing
Reader work or infer that the study must start over. No question was written.

Historical explanations additionally distinguish mutable questions/marks/labels,
compiled units, proposals versus Interpretations, Critic output versus human
challenge, Blueprint creation versus review, and transient Lineage inspection.
They do not reconstruct missing actions from the counts above.

Configured destinations in the table were inspected in the current implementation;
only the recommended Question action and Lineage action were exercised. This is
not an audit of all eleven destination flows.

## Accomplishment assessments and client

Both live GET responses exactly matched the pure evaluator's finding fields;
evaluator version and limitations matched its enclosing assessment. The client
rendered the corresponding server states after `Check accomplishments`.

| Achievement | Rule | Status | Reason code | Review offered |
| --- | --- | --- | --- | --- |
| Perspective Explorer | `achievement.perspective_explorer`, `1.0.0` | `unsupported_due_to_missing_coverage` | `COVERAGE_UNSUPPORTED` | No |
| Second Opinion | `achievement.second_opinion`, `1.0.0` | `unsupported_due_to_missing_coverage` | `COVERAGE_UNSUPPORTED` | No |

The safe API reason was: “Required evidence coverage or identity/version support
is insufficient; past activity is unknown.” The UI stated, for each achievement:
“History unavailable: this workspace does not contain enough coverage to determine
whether this was earned.” Each showed rule version `1.0.0`.

Coverage was `perspective-retained-execution-v1`, `status: unsupported`,
`extant_records: null`, `eligible_records: 0`, and
`historical_completeness: unknown`, read from the local SQLite snapshot. The zero
eligible count does not permit a historical negative: the required receipt table
is absent. The receipt schema named by the assessment remains
`hermeneia.perspective-execution-receipt/v1`.

The unchanged limitations state that evaluation creates no award, agreement,
mastery, persistence or named-human identity; coverage concerns extant eligible
retained receipts rather than all past Perspective activity; complete Scope
metadata participates in exact equality; and exact methodology differences do
not establish intellectual independence or detect paraphrased duplicates.

Both approval packages and package digests were null. Neither `Review and record`
nor `Record achievement` appeared. Earned review, safe witness-summary confidence,
real pair ordering and final issuance were consequently **not exercised**.

Historical award listing separately returned HTTP 409,
`AWARD_COVERAGE_UNSUPPORTED`. The client preserved that uncertainty: recorded
history could not be refreshed, its existence was unknown from the request, and
history had not been read. It did not fabricate an empty supported award list.

**No historical award was issued on the original or copied study.** No award POST
or `Record achievement` action occurred; the award materialization function was
not invoked on either study. Stored award rows remained **0 → 0**, with the award
table absent before and after. This is absence of local rows, not supported
historical completeness. The harness checked unchanged award-row count after
every HTTP interaction, including the accomplishments requests.

## Lineage and navigation

The projection contained 4,503 typed items: one source document, 1,738 extractions,
2,369 canonical Observations, and 395 Reader snapshots. Typed record/event keys
were unique and all resolved to actual stored rows. The API projection equaled
the direct read-only projection. Two export GETs returned byte-identical JSON;
no export event was created.

All 395 Reader items retained their exact mark identity, source-document identity
and recorded page in their context links. Their authorship stayed `unknown`, and
their event stayed `current_snapshot`. The projection classified 4,107 units as
derived and 396 items as unknown origin, not as human/model work inferred from
their contents. No retained-execution or achievement-award item appeared.

All 4,503 projected timestamp values matched the actual designated stored fields:
1,738 `extracted_at`, 2,369 `created_at`, one `registered_at`, and 395 `updated_at`.
All were orderable recorded timestamps. The client explicitly marked equal
recorded times as having unknown sequence; mutable Reader items were described
as current snapshots whose earlier values are not recorded. This is not a
reconstruction of annotation revisions or reading sessions.

Actual navigation:

- Recommended action opened Reader Question and focused its existing question
  input. The panel acknowledged the 395 retained passages. No typing/save occurred.
- The Guide's Lineage action opened Evidence Board → Lineage.
- Reader-highlight and unknown-origin filters worked. A deterministic sampled
  mark was opened from its typed entry; its source context returned to its recorded
  document and page 1, where its durable mark anchor was present in the Reader DOM.
- No Perspective receipt or accomplishment review link existed to exercise.

Reader navigation normally posts reading progress. Both observed progress POSTs
were refused with HTTP 403 by the harness, while source navigation succeeded.
Thus this demonstrates non-mutating **guarded inspection**, not that ordinary
Reader navigation is inherently read-only.

No excluded source exists in this study. Exclusion/non-disclosure adversaries were
therefore not exercised against real records here; the existing focused tests
provide separate synthetic boundary coverage. No source/model text was exposed
through accomplishment summaries, and none is included in committed evidence.

## Integrity result

After the browser tab and local server were closed:

- All seven original file size/SHA-256 pairs matched the pre-capture measurements,
  including the database, source upload, portable copy, WAL and SHM.
- A newly captured independent private copy of the original reproduced every
  table count and the original logical database digest.
- The served copy retained identical database bytes, logical digest and all table
  counts. Missing P3 and award tables remained missing.
- Across 48 harness-observed HTTP requests, award rows stayed unchanged. Award
  POSTs: **0**. Provider/outbound attempts: **0**.

No SQLite connection was opened on the original workspace at any stage. No
original state was normalized or repaired.

## Correctness, usability and limits

**Correctness:** no product defect was found on the exercised paths. Unsupported
coverage remained unsupported through evaluator → API → client. Guide readiness
matched P1, absent mutable/current facts were explained, typed Lineage identity
and unknown authorship survived, and the exercised destinations were correct.
Private harness assertions were corrected for P1/Guide array ordering and the
API's enclosing evaluator limitations; these were harness assumptions, not product
defects or changes to the application.

**Usability observations:** the separation of Current state, Readiness and History
made existing work visible without claiming completed historical method. The
explicit “not a failure” sentence and neutral “History unavailable” language
avoided judging study quality. The question destination helped connect the
recommendation to actual accumulated marks. Historical awards' generic refresh
message suggests retrying even when the captured schema lacks the category; a
clearer explanation of legacy coverage may help. This is an observation for
review, not authorization to change legacy/startup semantics. Whether recognition
feels meaningful, and whether the earned review summary supplies enough confidence
to approve, remain untested because neither achievement earned here.

**History limits:** current annotation notes/labels and aggregate reading progress
cannot recover overwritten revisions or traversal history. Transient/unretained
Perspective activity cannot be reconstructed. Unknown origin cannot be upgraded
to attributable human authorship. Missing proposal/Interpretation/Blueprint rows
establish only missing extant material, not proof those intellectual activities
never happened. No history store, repair, synthetic receipt or provider execution
was introduced.

**Next bounded recommendation:** locate a genuine existing study with already
retained P3 receipts, then repeat only receipt provenance → exact frozen predicate
→ API/client → safe review navigation under the same no-provider/no-award guards.
If no such study is available, stop; prospective receipt-producing real use and
any specific award issuance require their own steward-approved packet. Do not
backfill this study to qualify it.

## Focused verification

Existing tests were run against the unchanged starting revision. All **567 passed**,
with no failures or skips:

| Group | Tests | Passed |
| --- | --- | --- |
| Accomplishment client integration | `test_achievement_client_integration.py` | 60 |
| Achievement API | `test_achievement_award_api.py`, `test_achievement_award_api_disclosure_boundary.py` | 95 |
| Evaluator/integrity | `test_perspective_achievements.py`, `test_perspective_achievement_integrity.py` | 92 |
| P3 receipt/core/API/Lineage/WBS/UI | `test_perspective_execution_receipts.py`, `test_perspective_execution_api.py`, `test_perspective_execution_lineage.py`, `test_perspective_execution_wbs.py`, `test_perspective_execution_ui.py` | 123 |
| Study Lineage | `test_study_lineage.py`, `test_study_lineage_api.py`, `test_study_lineage_ui.py` | 75 |
| P1 capability evaluator/Lineage | `test_capabilities.py`, `test_capabilities_lineage.py` | 55 |
| P2 Guide/core/API/UI | `test_guided_study_cycle.py`, `test_guided_study_cycle_api.py`, `test_guided_study_cycle_ui.py` | 67 |

Test issuance fixtures are disposable synthetic studies, separate from the real
study and its copy. Tested production/test bytes were unchanged. No full suite
was run or Reader baseline reclassified; the packet required focused validation
only. Private validation scripts/data were not added to the repository. The sole
committed deliverable is this privacy-safe note; `git diff --check` passed.
