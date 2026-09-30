# Guided Study Cycle v1 — P2 implementation boundary

Date: 2026-09-30. Starting commit: `922e47271f3643204bca1e4edb92d7b9f14e001b`.

This implements P2 of [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215),
following the product direction in [#212](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/212)
and the steward boundaries in [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214).
The [Capability Registry v1 contract](capability-registry-v1.md) remains the single
owner of capability definitions, prerequisites, readiness, and supported historical
results. [Study Lineage](study-lineage-v1.md) owns source eligibility, typed durable
identity, authorship, acceptance provenance, and coverage. The
[Authority Index](../01_Authority_Index.md) and
[Storage read-only rule](../15_Storage.md#read-only-storage-rule) continue to govern
the underlying records.

The guide teaches a possible study method. It does not record a completed study
cycle, issue an accomplishment, admit evidence to Scope, accept a proposal, or
revise a Blueprint. Those boundaries apply even when current material is present.

## Projection and API

`hermeneia/guided_study_cycle.py` exposes
`project_guided_study_cycle(lineage, registry=None, *, current_state=None)`.
It invokes the P1 evaluator, then adds ordered presentation metadata and a bounded
resumption recommendation. It performs no SQL, provider calls, writes, or timestamp
capture. The registry must contain exactly the initial 11 capabilities.

The flow is:

```text
eligible Study Lineage snapshot + validated current selection
    → Capability Registry v1 evaluator
    → Guided Study Cycle projection
    → Companion guide presentation / existing navigation
```

`GET /api/guided-study-cycle` returns `hermeneia.guided-study-cycle/v1`, guide
version `1.0.0`, registry/evaluator versions and registry digest, workspace and
Lineage coverage, the 11 steps, `recommended_step_id`, `recommendation_reason`,
and `current_frame_selection`. Each step includes its capability/definition
identity, ordinal, title, purpose, status and explanation, unchanged P1 capability
status/readiness, recommended action, existing target surface, evidence/current
state basis, history support, and coverage notes. Serialization reuses Lineage's
deterministic JSON serializer; successful responses have `Cache-Control: no-store`.

For an existing database, the endpoint uses `mode=ro`, `PRAGMA query_only=ON`, and
one transaction. It does not initialize a `SQLiteStore` or migrate records during
the GET. Existing app startup migration remains outside this read boundary. If
the database does not exist, an empty in-memory Lineage query supplies truthful
missing-storage coverage without creating the database or its parent directory.
The empty guide recommends establishing a governing question. Read/evaluation
errors return a refusal without a partial guide or inferred progress; mutation
methods are not supported.

The only optional query inputs are a single `perspective_kind=builtin|saved` and
exact `perspective_id`. Built-in IDs are checked against existing frame metadata.
A saved selection must name an eligible Lineage Perspective record with the
existing `perspective-frame-v2` scheme and a nonblank name. Missing, unknown,
duplicate, legacy-label, and extra query inputs are refused. A validated selection
is labeled `basis=current_ui_selection`; it supplies current frame availability,
never a Perspective execution receipt. The frontend sends no custom-draft or Room
hint and clears a prior workspace's frame hint on workspace reset.

The browser validates the response shape and renders it. It does not derive
capability eligibility, classify provenance, or turn a local action into history.
Exact typed references are carried through from P1; equal strings across record
types remain distinct. Excluded evidence and its ineligible descendants cannot
supply guide support.

## Ordered cycle and existing destinations

| Ordinal | Capability ID | Projection target | Existing destination/action |
| --- | --- | --- | --- |
| 1 | `governing_question` | `question` | Reader question card; existing Setup question form before a readable source is available |
| 2 | `read_source` | `reader` | Reader page; close the bottom workstation to return attention to the passage |
| 3 | `mark_evidence` | `capture` | Reader Capture inspector |
| 4 | `record_observation` | `observations` | Reader Observations inspector; Capture candidate inspector when only a Reader mark supplies the context |
| 5 | `preserve_question` | `inquiry` | Existing Observation inquiry panel using a single exact typed Observation context; otherwise the Corpus chooser |
| 6 | `organize_evidence` | `evidence` | Evidence Board workstation |
| 7 | `explore_perspective` | `perspective` | Perspectives / Ask the Room workstation |
| 8 | `form_interpretation` | `interpretation` | Existing Observation interpretation context; otherwise the Corpus chooser |
| 9 | `challenge_interpretation` | `search` | Existing Reader corpus Search; search source passages for counterevidence |
| 10 | `review_blueprint` | `blueprint` | Existing Blueprint workstation |
| 11 | `review_lineage` | `lineage` | Evidence Board with its Lineage view selected |

Step 4 inspects compiler-derived canonical units or an anchored candidate. It does
not automatically promote a Reader mark or rewrite evidence. Step 9 uses the
existing corpus Search to examine source passages for counterevidence. Manual
inspection showed that the existing `e10Go('critic')` stage reads publication
`validation_reports`/rendered narratives, so it cannot truthfully serve as the
interpretation-counterevidence destination. The bounded guide uses the existing
source challenge surface rather than implying a new Critic workflow or invoking
an automatic critique. Search/navigation still supplies no human-review credit.
Opening any destination is navigation, not approval or provider execution. Model
features reached from these destinations retain their own existing execution and
human-approval requirements.

## Current material, readiness, and history

P1 `availability` and `capability_status` remain visible independently. The guide
adds these presentation states:

| Guide state | Meaning shown to the user |
| --- | --- |
| `ready` | The capability is available now; the guide has no supported current material to skip the step |
| `currently_supported` | Available now with retained current material at which study can resume; this is not a historical completion claim |
| `historically_exercised` | P1 supports its narrow retained-result predicate; current prerequisites are still displayed separately |
| `not_ready` | P1 reports a known missing current prerequisite |
| `unknown` | P1 cannot establish current readiness from available coverage |

The separate History field says either that a narrow retained result is supported
or that historical exercise is unsupported. Unsupported history is explicitly
described as **not a failure**. P2 preserves P1's limited retained-question and
attributable canonical-Interpretation claims; it adds no further completion claim.

Current material is described only from eligible references supplied by P1:
the singleton current governing question, Reader marks, canonical Observations,
separately identified inquiry questions, current labels on distinct marks, saved
or explicitly selected frames, retained interpretations/proposals, and Blueprints.
An inquiry question is not silently relabeled as the workspace governing question.
A proposal remains a proposal. Two current group labels do not establish durable
bucket identity, organization history, or Scope admission. A saved frame does not
establish a run; a saved Blueprint does not establish review or the cause of a
revision. Review of Critic findings and Lineage remains historically unsupported.

Readable extraction and compiler Observation presence make source/observation work
available. They do not supply a Reader attention record. The guide therefore keeps
reading/marking available for a newly imported source with canonical units but no
saved Reader marks. Saved eligible marks can support resumption past this part of
the method without proving reading, comprehension, or historical marking.

## Deterministic recommendation and presentation preferences

The ordinary rule walks the ordered cycle and recommends the first step that is
neither `currently_supported` nor `historically_exercised`. A blocked step explains
its P1 prerequisite rather than using a model to jump elsewhere. A usable step is
not blocked because its history is unsupported. If current support reaches the
end, the fallback is Lineage review, not a historical Full Cycle claim.

There is one explicit retained-result resumption case: when a governing question
is present and P1 supports an attributable canonical Interpretation, recommend
challenge/counterevidence. If an eligible Blueprint is also retained, recommend
Lineage inspection. This lets an existing study resume at a legitimate later
point without pretending that earlier method actions or review occurred. An
unaccepted proposal or unknown-origin Interpretation does not supply that anchor.
The guide explains this adjustment instead of forcing cosmetic sequentiality.

The existing Companion guide renders the checklist, selected-step purpose, current
state, separate readiness/history, one direct action, and inspectable evidence
basis. Reader remains the primary surface. Users can inspect any step, refresh,
continue later, hide the guide, use the workbench freely, reopen, or restart.
Companion's ordinary chat remains a separate feature.

The existing `hermeneia_companion_onboarding_v1` browser key now stores only
`paused` and `dismissed` presentation preferences. Old completion/finished flags
are ignored. Legacy Reader completion hooks request a fresh projection and do not
persist completion. The selected checklist step is presentation state in memory.
Restart clears those preferences and selection, then re-reads authoritative
current state; it does not reset a workspace or manufacture new study history.

Guide refresh and navigation use request/workspace sequence guards to discard
stale guide responses and stop subsequent guide navigation after a workspace
reset. Shared navigation functions and their lifecycle remain in their existing
owners. The existing asynchronous `e10SelectObservation` helper does not guard
its own response internally against workspace changes; the guide checks after
awaiting it. That wider shared-navigation boundary is unchanged in P2. Likewise,
the existing governing-question `invSave` write is fire-and-forget: an immediate
guide refresh can precede save completion. Explicit Refresh or reopening reads
the persisted state; the guide never substitutes browser question text as proof.

## Validation and deferred boundary

Measured on Python 3.13.5, Node 22.17.0, pytest 9.1.0, macOS 26.6.2 arm64:

- P2 adds **67 tests**: 24 domain/projection, 23 API, and 20 UI/navigation tests in
  `tests/test_guided_study_cycle.py`, `tests/test_guided_study_cycle_api.py`, and
  `tests/test_guided_study_cycle_ui.py`.
- The focused P2/P1/Lineage/Companion and relevant Reader set: **279 passed**,
  five existing dependency warnings, in 5.74s. This includes all 55 P1 and 75
  existing Study Lineage tests. Separate Perspective Room regression: **6 passed**.
- `python3 -m pytest -q`: **2,105 passed, 21 skipped, six Reader failures**, five
  existing dependency warnings, in 98.60s. No live-provider opt-in was used.
- Independently archived starting `922e472` full suite: **2,038 passed, 21 skipped,
  the same six Reader failures**, five existing dependency warnings, in 97.21s.
  All 610 archived tracked files retained their original SHA-256 bytes.

The failure-ID sets match exactly; no Reader assertion was weakened:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

Tests separately enforce exact ordering/registered capability mapping, unchanged
P1 readiness and history, current-state scenarios, unknown provenance, excluded
parent closure, read-only bytes/mtimes, missing-store noncreation, provider-free
evaluation, strict frame inputs, workspace isolation, refusal without partial
progress, browser preference separation, safe rendering, and real navigation
destinations. A test first demonstrated refusal of a real saved v2 frame due to
an incorrect scheme literal; using the existing `FRAME_V2_SCHEME` fixed it.
Another witness keeps compiler units from standing in for Reader attention.

Synthetic local browser smoke has confirmed an empty guide, governing-question
save advancing the recommendation to source attention, and source import with
three compiler Observations and no Reader marks retaining the reading
recommendation. Reader remains primary; Evidence Board, named Perspective
frames, Blueprint, and Lineage are reachable. The three distinct Observation
contexts correctly require the existing Corpus chooser for inquiry/interpretation;
manual selection reaches Inquiry Notes and existing provider controls without
generating output. Lineage showed the six recorded items. Pause/reopen, restart
returning to the persisted-state reading recommendation, hide-guide preferences,
and ordinary Companion chat input/Ask availability were confirmed. No Companion
request or model generation was executed during this smoke.

These are temporary synthetic workspace observations, not validation of a
complete real-user study cycle. All 11 actions were manually checked. The final
challenge action visibly opens the existing Reader Search workstation without
invoking Critic or a model. Use-workbench-freely closes the guide, and reopening
restores the guide without creating study completion or an award.

One cold browser reload left Reader at "Loading pages" until the existing Source
picker was used to reselect the source. The page API returned 200, and reselection
restored the actual source text and three derived Observations. This is an
observed Reader lifecycle limitation, distinct from the six independently
reproduced test failures. A temporary deterministic harness reproduced the same
invalidation mechanism in both starting `922e472` and current code: changed
workspace metadata invalidates a pending pages response, leaves the loading
state, and a second document selection renders successfully. The relevant Reader
load functions are byte-identical; P2's workspace hook resets guide state only.
This establishes a pre-existing mechanism, not the confirmed cause of that
particular browser stall: its actual metadata/timing were not captured. No Reader
repair is included here.

No database schema/migration, WBS change, canonical persistence, generic event
store, evaluation persistence, coaching history, Perspective execution receipt,
achievement, award, Full Cycle claim, vectors, or Blueprint authority change is
included. Guidance requires no configured provider, API key, or local model.

The next planned boundary is P3's smallest governed durable Perspective receipt,
only after its own evidence/authority contract is established. P2 supplies no such
receipt and makes no forward inference from a selected frame or transient output.
P3 and later packets are not implemented here.
