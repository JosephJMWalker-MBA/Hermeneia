# Study Lineage v1: real-workspace validation and navigation stop

Discovery: 2026-09-27. Validation: 2026-09-28. Starting revision: `a9739ba`
(`feat: add read-only study lineage v1`). Production code and existing tests
remain unchanged. This is evidence for [#111](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/111),
not acceptance of its complete study-history experience.

**Result: bounded projection checks passed; source-context navigation failed.
Stop for review before repair.** The selected real workspace has substantial
Reader activity but no durable model/interpretation/Blueprint chain. Gatsby was
not found in the inspected locations. Those coverage gaps remain unvalidated.

## Workspace selection and custody of the validation copy

Selected existing workspace: **Benchmark 02 Attribution Audit**, durable identity
`50a8d313f4394b4b9f39714201ae5e7d`. Its local database is
`~/Hermeneia/workspaces/benchmark-02-attribution-audit/hermeneia.db`, outside the
Desktop development checkout. This is accumulated user study data, not a seeded
acceptance scenario. No records were added to it.

The Desktop checkout had no study database. The former Documents/GitHub location
was unavailable. The other local checkout, its migration backup, and the Orin
paths supplied by the steward revealed the benchmark workspace and copies, not
a Gatsby study database. On Orin, the runtime and pre-v17 backup each contained
395 Reader marks and no proposals, interpretations, or Blueprints; its portable
bundle had no Reader marks. The Gatsby corpus README is a placeholder, and a
Gatsby PDF/example is not accumulated workspace history. This search is not proof
that no Gatsby backup exists elsewhere.

The pasted shell session's `cd /path/to/gatsby-workspace` failed. Its subsequent
home-directory hash listing was not used as a Gatsby baseline.

**Discovery limitation:** read-only SQLite discovery on two Orin archival
candidates changed the observed DB/WAL file set. Subsequent filesystem-only
inspection found zero-byte WAL files and 32 KiB SHM files; main database mtimes
were still historical. The initial probe retained only an aggregate equality
result, not separate before hashes, so byte preservation for those first two
archival reads cannot be proven retrospectively. No claim of record mutation
is made either. No cleanup, repair, migration, or further validation was applied
to those archival candidates. This coordination-file observation is separate
from the fully measured selected local workspace below.

The selected local workspace's **seven files matched byte-for-byte before and
after capture and validation**, including its database, existing WAL/SHM, source PDF,
calibration file, and portable bundle contents. Full file hashes are in
[workspace-files-integrity.json](fixtures/study-lineage-v1-real-workspace/workspace-files-integrity.json).
The database SHA-256 remained
`d2139970ed4ee29ea413f1301fd4f035bea9037590e8d8a02e7bd385846d7c81`.

The manual [API harness](fixtures/study-lineage-v1-real-workspace/validate_readonly.py)
opens the source with `mode=ro`, `query_only`, and a read transaction, then backs
up that transaction to a private temporary copy. Logical-record hashes match
source/copy and before/after. It constructs the app before the destination exists,
avoiding the existing startup migration path. All endpoint database connections
are restricted to that private copy and forced read-only. This is a validation
guard, not a new product runtime or authority.

The [browser harness](fixtures/study-lineage-v1-real-workspace/serve_readonly.py)
serves the unchanged product HTML over another copy, with allowlisted GETs and
read-only database connections. It blocks writes and unrelated endpoints. In
particular, existing Reader navigation attempts to save reading progress; those
requests were blocked. **This does not establish that ordinary Reader navigation
is non-mutating.** It preserves the user's requested read-only validation boundary.
Both private copies' durable bytes and logical records remained unchanged.

## What the real records establish

The API and two exports returned identical bytes, SHA-256
`2fdf336b84b52b6c729e986b1afb8da2f42143f47e363fa8e1742e34a66497bc`.
[api-result.json](fixtures/study-lineage-v1-real-workspace/api-result.json) contains
counts, coverage, sampled IDs, timestamps, and integrity hashes; it contains no
source text or database. Full projection output and database copies are private
temporary artifacts, not committed history stores.

| Durable records | Stored/projected | Observed result |
| --- | ---: | --- |
| Source document | 1 / 1 | Exact source identity retained; authorship unknown |
| Source extractions | 1,738 / 1,738 | Exact typed rows retained; source-derived |
| Observations | 2,369 / 2,369 | Exact typed rows and recorded provenance retained; source-derived |
| Reader marks | 395 / 395 | Exact typed rows retained; current snapshots, authorship unknown |
| Proposals, AI provenance, interpretations | 0 / 0 | No model identity, acceptance/rejection, or interpretation chain to test |
| Blueprints and supersessions | 0 / 0 | No creation/revision/supersession chain to test |
| Field Notes, inquiry notes, observation reviews | 0 / 0 | No extant rows to test |
| Publication authoring tables | Absent | Projection reports missing coverage; no tables created |
| Excluded source documents | 0 | Real excluded-descendant leakage case not exercised |

All **4,503** projected raw records were compared to the exact stored row selected
by their typed key. All attached provenance rows were checked the same way. Every
projected historical timestamp matches its stored field; timezone conversions
represent the same instant and the emitted sequence is monotonic. All times in
this sample are orderable. Missing/naive/malformed-time behavior therefore remains
synthetic-regression coverage, not a real-data observation in this workspace.
Equal recorded times do not establish an action sequence.

All 395 Reader entries are explicitly checked as `current_snapshot`, using
`updated_at` and `authorship = unknown`. Together with the source document, this
produces 396 unknown-origin entries; the 4,107 extraction/Observation entries are
derived evidence. No entry is fabricated as human-, model-, or accepted-model
authorship. The browser showed 4,503 total items and 395 when filtered to Reader
highlights with unknown authorship; it displayed the current-snapshot warning.

### Durable traces actually checked

Three Reader IDs were traced from SQLite through the projection to the document
pages endpoint, which contains the exact mark at its recorded page:

- `6932bf50-8517-4440-ac87-b128d033b81f`
- `05da9585-915c-4a1b-81a7-98a4d8e41893`
- `dfb19e19-6e51-473a-849c-c986491731da`

Each refers to page 1 of source document
`311e01f51d3493badb5cebd780b849e87c6f55d0b8c2e4a32dce2cf798b9cc44`.
Their projected update times are respectively `2026-08-13T13:58:23.226477+00:00`,
`2026-08-13T13:58:38.888295+00:00`, and
`2026-08-13T13:59:07.256617+00:00`. These are current-state timestamps, not claims
that every current annotation was authored at initial highlight capture.

Three Observation object-lineage endpoints also resolved the exact stored
Observation → extraction → document chain. For example:

```text
Observation 001028d602daa25b871aac5493891f57e89f0960a95e09ecf5638a5dfb66cd7a
  → extraction 724955b944e5de6886eec0620652c9fd262f3c0d663b0e007cdfcfd610bc175b
  → document 311e01f51d3493badb5cebd780b849e87c6f55d0b8c2e4a32dce2cf798b9cc44
```

The other two full traces are in the API result. **None of the 395 Reader marks
has a nonempty `observation_id`.** Sharing a document, page, text, or date does
not establish a Reader → Observation causal link. The 393 `observation_candidate`
statuses do not supply one: the existing promotion endpoint changes mark status
without creating a canonical Observation. The remaining two are saved highlights.

## Preserved negative witness: source-page link

The browser expanded Reader mark `6932bf50-8517-4440-ac87-b128d033b81f` and displayed
its exact durable identity. Its projection context correctly records page 1.
Clicking **Open source page in Reader** produced:

```text
TypeError: Cannot set properties of null (setting 'innerHTML')
_crRenderPage → _crGoToPage → _attnOpen → _studyLineageOpenContext
```

The visible Reader subsequently settled on **page 62**, matching the existing
`reading_progress.last_page`, rather than the requested page 1. The document/pages
and highlights requests returned 200. The failure occurs before a progress write;
blocked progress/ancillary requests do not explain the missing page container.

Mechanism in unchanged production JavaScript:

1. `_studyLineageOpenContext` passes the correct document/page to `_attnOpen`.
2. `_attnOpen` calls `e10Go('reader')`.
3. That starts `e10LoadCloseReader`, which synchronously replaces the Reader DOM
   with its loading placeholder, then awaits the document list.
4. The same-document branch immediately calls `_crGoToPage(1)` and attempts to
   render into the removed page container.
5. The asynchronous reload later rebuilds the Reader and restores saved page 62.

The [minimal witness](fixtures/study-lineage-v1-real-workspace/reader_context_witness.py)
extracts nine actual production functions and uses a deliberately deferred
document response. Native child removal is represented by a small DOM double;
source text, a database, providers, wall-clock sleeps, and a seeded study are
unnecessary. [Reader-context metadata](fixtures/study-lineage-v1-real-workspace/reader-context-witness.json)
preserves the real identities and page values. Its expected-failure classification
accepts only the exact observed TypeError and saved-page result; unrelated probe
failures remain failures. A corrected implementation would produce a strict
unexpected pass and require review of this frozen witness.

Classification: **context-navigation integration defect exposed by the Lineage
projection**, in reused Reader navigation. The projection's ID/page data is correct.
This is an additional real-use failure, not one of the six existing suite failures.
No production repair was attempted.

The browser run stopped here. Newest-first interaction, browser object-lineage
opening, and the browser download control were not exercised after the failure.
Their API checks and existing synthetic tests are distinct evidence.
[browser-result.json](fixtures/study-lineage-v1-real-workspace/browser-result.json)
records the guarded requests, completed UI observations, and unchanged copy hashes.
The initial narrow pane obscured workstation controls; the observed navigation
failure was reproduced at a 1280×900 viewport, then the override was reset.

## Missing history: classification rather than reconstruction

| Category | Real evidence and limit |
| --- | --- |
| Missing product history / association | No Reader mark has an Observation link; no durable proposal, interpretation, or Blueprint records exist here. This prevents the desired chain. Absence does not prove that comparable work never occurred elsewhere. |
| Overwritten mutable state | 393 marks have different creation/update times. Current rows survive; earlier field values, edit actors, and a sequence of edits do not. The earliest mark creation is `2026-08-13T13:58:23.184708+00:00`; latest mark update is `2026-08-13T19:12:37.879633+00:00`. These facts cannot reconstruct the missing versions. |
| Transient/non-durable activity | Current Perspective/Room execution and workspace-export paths do not provide a durable study event log. There is no evidence here that such actions occurred; do not turn this schema limitation into an asserted user history. Reading progress is current/aggregate state, not a session log. |
| Projection/context defect | The exact page-1 context link fails through the existing Reader rebuild, then displays page 62. Preserved above; repair stopped. No raw-row, identity, provenance, or timestamp mismatch was found in the completed checks. |
| Genuinely unsupported provenance | Reader annotation/selected-text authorship is not attributable from these rows; it remains unknown. No model, provider, acceptance, or Blueprint provenance can be inferred from similar text, candidate status, current configuration, or filesystem names. |
| Unexercised exclusion boundary | This workspace contains no excluded documents. Existing adversarial tests passed, but real excluded-parent/child leakage was not validated and no exclusions were manufactured. |

## Checks and reproduction

API validation command (requires the existing local database; output must not exist):

```sh
PYTHONPATH=. python3 docs/verification/fixtures/study-lineage-v1-real-workspace/validate_readonly.py "$HOME/Hermeneia/workspaces/benchmark-02-attribution-audit/hermeneia.db" /private/tmp/herm-lineage-new-capture
```

The browser harness takes that completed private snapshot and a second fresh
temporary directory. Neither script is a supported application startup mode.
Do not serve the live workspace or commit the private copies/full exports.

Focused existing regression suite: **96 passed, 5 warnings in 2.09s**:

```text
python3 -m pytest -q tests/test_study_lineage.py tests/test_study_lineage_api.py tests/test_study_lineage_ui.py tests/test_evidence_board_api.py tests/test_evidence_board_ui.py tests/test_lineage_api.py
```

Full existing suite on unchanged `a9739ba` production/tests: **1,966 passed,
21 skipped, 6 failed, 5 warnings in 104.07s**. The first sandboxed run had seven
additional socket/child-runtime permission failures (1,959 passed, 13 failed).
Repeating with local loopback permission removed those infrastructure failures.
The remaining six exactly match the independently established Reader baseline
in the [implementation verification note](2026-09-25-study-lineage-v1.md):

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

Frozen negative witness: **1 expected failure** in 0.06s with normal invocation;
`--runxfail` exposes the exact TypeError/page-62 assertion failure. It is kept under
verification fixtures, outside automatic test filename discovery, and does not relabel a baseline
Reader test or weaken an existing test:

```text
python3 -m pytest -q -rx docs/verification/fixtures/study-lineage-v1-real-workspace/reader_context_witness.py
python3 -m pytest -q --runxfail docs/verification/fixtures/study-lineage-v1-real-workspace/reader_context_witness.py
```

An independent agent reviewed and reproduced the navigation ordering. The manual
harness mechanics were first exercised on an existing synthetic test fixture;
its incomplete context rows and newly created empty WAL stopped that probe.
That run was not treated as real-workspace evidence or a product failure. The
subsequent real capture passed with separately recorded file and logical checks.

## Next bounded packet — requires review before implementation

Repair only recorded-source navigation's lifecycle ordering: finish loading the
intended Reader document before applying the recorded target page, without
silently restoring a different saved page. Cover same-document and cross-document
links, repeated/late navigation, and existing reading-progress semantics. Promote
the preserved witness to a passing regression only after demonstrating the repair,
then repeat the guarded real-workspace link check. No history store or provenance
repair is needed for this navigation defect.

Separately, a Gatsby database/backup containing durable proposals/interpretations
and Blueprint revisions is still needed to validate the motivating full chain.
Do not fill that gap by creating records, changing candidate marks, or inferring
relationships in the benchmark workspace.
