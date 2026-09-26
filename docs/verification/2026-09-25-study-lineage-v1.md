# Study Lineage v1 verification

Starting revision: `64f3a5bdf9c169b9cca36e034e34681bc1f7b007` on `main`.
Inventory began 2026-09-24; implementation validation completed 2026-09-25.
This is a bounded projection implementation for [#111](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/111),
not closure of the entire issue or a new history/preservation authority.

## Inspected behavior and implemented result

The Evidence Board from PRs #200/#201 exposed accumulated Reader marks,
Field Notes and Observations, with transient highlight selection and explicit
Scope admission. The existing attention timeline and individual object-lineage
graphs did not provide a study-wide view across these different durable record
types. The [preimplementation inventory](../design/study-lineage-v1.md)
classified existing storage before production changes.

Evidence Board → Lineage now presents extant study records in a chronological
view with type/origin filters, stable existing-context links, and full deterministic
JSON export. Real source table/key identities, raw records, provenance rows,
composite relationship keys and historical timestamp strings remain distinct.
There are no new tables, provider calls, backfilled events, source edits, or
changes to Blueprint, Scope, publication or release authority.

## Demonstrated boundaries

- Equal IDs and equal passage text across different tables/occurrences remain
  separate. Proposal generation and explicit decision are event views of the
  same existing proposal, not synthetic canonical identities.
- Current mutable annotations/questions are labeled current snapshots. Missing,
  naive and malformed times remain outside established chronology; ties do not
  claim causal order.
- Model/accepted-model labels require the existing explicit generation and
  acceptance links. Contradictory or absent provenance remains unknown; content
  similarity never supplies a link or an inferred editing event. Adversarial
  tests first demonstrated false accepted-model labels for differing/missing
  fields copied by the acceptance writer. Exact stored-field checks now leave
  those records unknown while retaining their recorded content and provenance.
  Missing/null/empty simple IDs cannot become fabricated durable identities.
- Excluded source evidence and its linked descendants are omitted from both
  rendering and export. A failing adversarial witness exposed unchecked
  Architect paragraph dependencies; the repair checks their recorded evidence
  and retains paragraph/Blueprint-link composite identities.
- Supersession typing checks all canonical endpoint types supported by the
  existing storage trigger. Same-ID ExpressionProfile/validation collisions
  were demonstrated and now refuse an ambiguous association.
- A reproduced UI defect retained an old workspace's type filter while its
  dropdown appeared to show all types. Context reset now clears type/origin
  filters; late responses cannot repopulate another workspace's view.
- Repeated API/export responses over unchanged state are byte-identical. GETs
  use a single read-only SQLite transaction, cannot initialize workspace identity
  or storage, and reject mutation methods. Workspace databases are not joined.
- Both rollback-journal and live-WAL fixtures preserve stored rows and database
  bytes. The WAL test sees the newest committed WAL data without rewriting it;
  it does not use SQLite's `immutable=1` shortcut. SQLite runtime coordination
  files are not represented as canonical study history.

## Synthetic browser witness

A disposable database seeded through existing test fixtures and storage methods
contained Reader marks (including a dismissed mark), corpus/instrument Field
Notes, source evidence, human and model interpretations, pending/accepted/rejected
proposals, two Blueprints with an explicit supersession, an Architect plan,
rendered output, and Critic records. All additional scenario text explicitly
identified itself as synthetic; no external inference was performed.

The browser showed 33 projected entries across 17 record types. The accepted-model
filter selected the expected canonical interpretation; opening its provenance
showed the exact stored model/version/prompt/acceptance record. Its existing
object-lineage graph resolved through Observation, extraction and document.
The export link returned HTTP 200, and no browser console errors were observed.

Across Lineage rendering, filtering, detail expansion, object-lineage navigation
and export, both the stored-row digest and database-file digest were unchanged.
The browser's ordinary initial Reader load updates reading progress; the
read-only witness starts after that load. Explicit source-page navigation retains
that existing Reader behavior and is labeled accordingly. The smoke check used
the app's available narrow browser pane; it is not a desktop/mobile usability study.
No actual user study database was available for live-use validation.

## Regression results

Focused and related regression tests: **190 passed, 5 warnings in 7.25s**:

```text
python3 -m pytest -q tests/test_study_lineage.py tests/test_study_lineage_api.py tests/test_study_lineage_ui.py tests/test_evidence_board_api.py tests/test_evidence_board_ui.py tests/test_lineage_api.py tests/test_synthesis_lineage.py tests/test_corpus_scope_boundary.py tests/test_scope_resolution.py tests/test_workspace_lifecycle.py tests/test_reader_blueprint_editor.py tests/test_reader_return_to_book.py
```

Full suite (`python3 -m pytest -q`): **1966 passed, 21 skipped, 6 failed,
5 warnings in 94.94s**. The failed node IDs were mechanically compared with the
independent starting-commit run below and match exactly. No additional failures
were introduced. `git diff --check` also passes. Warnings are existing SWIG
type deprecations; skipped tests remain skipped, not claimed as validated.

The six known failures were independently reproduced from an archive of the
starting commit before classifying them as baseline. Import paths and the
Reader HTML path resolved inside that archive, not the changed checkout:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

The independent run reported **6 failed in 0.12s** under Python 3.13 and Node
22.17.0: five historical markup assertions and one missing
`_crSyncPageSpeechControls` JavaScript reference. These failures were not fixed
or weakened in this packet. Existing Evidence Board tests change only their
extracted-function harness to declare the additional view state/reset function.

## Files and remaining boundary

- `hermeneia/study_lineage.py`: schema-discovered projection and deterministic codec.
- `hermeneia/web/app.py`: read-only projection/export GET routes.
- `hermeneia/web/static/index.html`: Evidence Board Lineage view and filters.
- `tests/test_study_lineage.py`, `tests/test_study_lineage_api.py`,
  `tests/test_study_lineage_ui.py`: provenance, identity, time, isolation,
  export, access and non-mutation checks.
- `tests/test_evidence_board_ui.py`: compatible test harness declarations.
- Inventory, this verification record, documentation map and dated status update.

Unrecorded transient Perspective/Room outputs, overwritten or deleted annotation
history, reading sessions, bucket/motif histories and unassociated export/build
events cannot be reconstructed truthfully. V1 does not infer them. Large-study
performance is unmeasured: the server captures all supported records per request;
the browser pages their presentation. Existing application-startup migrations
are unchanged and outside the new read path.

Next bounded packet: validate this projection on one steward-selected existing
workspace, checking a Reader mark → interpretation/proposal → Blueprint chain
against its stored identities and provenance. Preserve any concrete missing-link
or navigation witness. Do not add a history store or synthesize missing events
as part of that validation.
