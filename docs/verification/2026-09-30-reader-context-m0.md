# M0 — Reader context navigation after load

Verified 2026-09-30 against starting `main` commit
`886f788b6b7644c6126e409b58fcfda29c3b43f9`. This implements only the Reader
navigation packet in [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215),
under the steward decisions in [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214).
The working tree was clean before implementation. No push was performed.

## Result and boundary

The exact Reader mark preserved in `5e14463` now opens its recorded page **1**,
instead of throwing on a missing page container and settling on saved page **62**.
Both the deterministic witness and the guarded Benchmark02 browser check pass.

An explicit document/page request now travels through the existing Reader route
and loader. Only after the Reader DOM, requested document pages, and highlight
load complete does the loader apply the requested page. Ordinary openings retain
their existing saved-progress restoration timing. Subsequent ordinary paging
still submits progress requests. A newer navigation, route departure, or workspace
change invalidates older pending document/highlight results before they can
install state or render into replaced containers. An unavailable requested
document produces an error rather than silently selecting the primary document.

This is a frontend lifecycle repair. The only production file changed is
`hermeneia/web/static/index.html`; its verified SHA-256 is
`67f7fca117057a7e4ad8cd215a1b9512e28f9e0317776fa19e5fcec32b45736f`.
No schema, WBS, provider/model code, canonical records, Study Lineage projection
semantics, or progress storage model changed. The Lineage dispatcher only returns
the existing context-navigation promise. No arbitrary load delay was added.

## Failure first

The untouched starting tree was independently extracted with `git archive` into
a private temporary directory, without Git metadata. After its tests, all 601
tracked regular files still matched the starting commit.

The preserved fixture
[`reader_context_witness.py`](fixtures/study-lineage-v1-real-workspace/reader_context_witness.py)
was run there before repair:

```text
python3 -m pytest -q -rx docs/verification/fixtures/study-lineage-v1-real-workspace/reader_context_witness.py
1 xfailed in 0.06s

python3 -m pytest -q --runxfail docs/verification/fixtures/study-lineage-v1-real-workspace/reader_context_witness.py
1 failed in 0.05s

KnownReaderContextFailure:
  TypeError: Cannot set properties of null (setting 'innerHTML')
  settled_page: 62; requested_page: 1
```

Current-code inspection confirmed the ordering: `_attnOpen` began rebuilding the
Reader, then immediately called `_crGoToPage` for the same document while
`cr-page-view` was absent. The later default document open restored page 62.

After repair, the fixture produced a strict unexpected pass before its expected
failure marker was removed. Its real IDs, input JSON, original failure
classification, and page/error assertions remain intact. Only the harness's new
navigation-generation variable and expected-failure promotion were needed.
The old negative verification note and recorded results remain unchanged.

Review also demonstrated two introduced regressions before completion: minting
a document-load generation without Reader DOM canceled the legitimate route
load; restoring ordinary progress after highlights overwrote a Next action with
page 62. Both were corrected and covered deterministically. The latter test
failed before correction (`doc-a`, page 62 instead of 63); ordinary restoration
now stays before the highlight await, exactly as on the starting implementation.

## Tests and exact results

Environment: Python 3.13.5, Node v22.17.0, pytest 9.1.0. Repository test governance
was active; no live-provider flag was used. Full runs required local loopback
permission for the existing server/socket tests.

Added `tests/test_reader_context_navigation.py`: **17 tests**, including a wrapper
that runs the promoted real-ID witness in normal suite discovery. Deferred
responses exercise same/cross/unloaded Reader context, exact document selection,
explicit-target precedence, ordinary/picker restoration, ordinary Next/Prev and
progress requests, Next during highlight loading, repeated/reversed responses,
stale success/error/highlights, route/workspace cancellation, missing-DOM calls,
unavailable targets, and unchanged Lineage projection data. No clock sleeps,
provider calls, or real database writes are used.

Mechanical extraction/harness updates, with existing behavioral assertions retained:

- `tests/test_guide_reading_first.py` — expected Reader route call now returns the coordinated loader.
- `tests/test_reader_accessibility.py` — extraction finds the extended `_crOpenDoc` signature.
- `tests/test_study_lineage_ui.py` — section boundary finds that extended signature.
- `tests/test_missing_workspace_navigation.py` — declare the new navigation generation in the harness.
- `tests/test_perspective_room_ui_state.py` — same harness declaration.
- `tests/test_reader_blueprint_editor.py` — same harness declaration.
- `tests/test_reader_blueprint_workstation.py` — same harness declaration.
- `tests/test_workspace_browser_create_ui.py` — same harness declaration.
- `tests/test_workspace_draft_scope_ui.py` — same harness declaration.

Focused final command:

```sh
python3 -m pytest -q tests/test_reader_context_navigation.py tests/test_study_lineage_ui.py tests/test_study_lineage_api.py tests/test_reader_highlights.py tests/test_reader_return_to_book.py tests/test_reader_boot_destination.py tests/test_reader_timeline.py tests/test_missing_workspace_navigation.py tests/test_guide_reading_first.py tests/test_workspace_browser_create_ui.py tests/test_perspective_room_ui_state.py tests/test_reader_blueprint_editor.py tests/test_workspace_draft_scope_ui.py
```

Result: **143 passed, 5 warnings in 11.16s**.

Full command, both starting archive and final repair: `python3 -m pytest -q`.

| Tree | Result |
| --- | --- |
| Untouched starting commit, local loopback allowed | 6 failed, 1966 passed, 21 skipped, 5 warnings in 97.70s |
| Final M0 repair, local loopback allowed | 6 failed, 1983 passed, 21 skipped, 5 warnings in 100.17s |

The six failures are identical in both runs:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

Five fail exact HTML/handler-string assertions. The speech-source test fails its
extracted-function harness with `ReferenceError: _crSyncPageSpeechControls is not
defined`. None is the original M0 null-container TypeError. Their failing
assertions were neither removed nor weakened. The starting sandbox run also had
seven denied local-server/socket failures; all seven disappeared when the same
untouched archive was run with loopback permission. An intermediate repaired run
found one additional harness omission in workspace draft switching; declaring
the new generation variable resolved it. The final run above follows all fixes.

Sanitized summaries and full-log digests are preserved in
[`test-results.json`](fixtures/reader-context-m0/test-results.json).

## Guarded real-workspace repeat

Source: the existing Benchmark 02 Attribution Audit workspace. No records were
added to manufacture this witness. The existing read-only capture harness used
`mode=ro`, `query_only`, and a read transaction to produce a private snapshot.
Only a second private copy was served by the existing browser guard; all writes,
providers, and unrelated endpoints remained blocked. No live database was served.

The refreshed projection had 4,503 records, including 395 Reader marks. The exact
identity opened through **Evidence → Lineage → reader highlight → unknown** was:

```text
workspace: 50a8d313f4394b4b9f39714201ae5e7d
reader_highlights.id: 6932bf50-8517-4440-ac87-b128d033b81f
document: 311e01f51d3493badb5cebd780b849e87c6f55d0b8c2e4a32dce2cf798b9cc44
recorded page: 1; existing saved page: 62; total pages: 85
```

The expanded item's typed durable key and actual context-button arguments agreed
on that ID/document/page. Ordinary opening displayed **PAGE 62 OF 85**. Clicking
that exact item's source-page button displayed **PAGE 1 OF 85**, with the correct
document button active. Console inspection found **zero TypeErrors**; its two
errors were expected guard refusals for observations/findings startup requests.
The final browser guard captured 33 requests and refused both progress POSTs.

The final server was stopped gracefully to produce its integrity report. Its
database, WAL, SHM, and logical rows all remained equal. A browser/process
interruption during the earlier pass prevented that earlier server's final
report; the complete final repeat supplies the committed guard evidence.

All **seven** live-workspace file inventories, sizes, and hashes were equal
before capture, after browser checking, and after the final source read. This
includes the database, WAL, SHM, PDF, calibration, and historical `.herm` bundle.
The final source logical hash also equals the original capture hash:
`f95c9193e675f99a2a4a032e795ef151748b71b5380b4475a8668f7393e4197d`.
These checks span both browser passes. Exact metadata and guard requests are in
[`result.json`](fixtures/reader-context-m0/result.json). Private databases, source
text/PDF, full projection exports, and private-content screenshots are excluded.

## Remaining limits / stop

The guarded browser proves navigation and nonmutation; because progress writes
were deliberately refused, it does not prove successful real progress persistence.
Deterministic tests check the actual progress request bodies, while existing API
tests remain in the focused/full suites. This packet does not coordinate arrival
order of previously submitted progress POSTs or all ancillary trail/related-panel
responses. The separate legacy corpus-search context opener has not been migrated
to this seam or claimed fixed. Its premature call can no longer cancel an active
Reader load, as covered by the missing-DOM regression.

Benchmark02 still lacks a real proposal/interpretation/Blueprint chain and a real
excluded-source witness; no broader Study Lineage validation is claimed here.
M0 stops here. No P1, capability coaching, achievements, or unrelated Reader
refactor is included.
