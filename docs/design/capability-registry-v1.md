# Capability Registry v1 — P1 implementation boundary

Date: 2026-09-30. Starting commit: `1af8381be534e796f63b9e9c1ed3a64a8cb5422a`.

This implements P1 of [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215),
under the steward decisions in [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214)
and the [architecture audit](capability-coaching-architecture-audit.md).
It is a software configuration and read-only derivation, not new constitutional
ontology or workspace authority. The [Authority Index](../01_Authority_Index.md),
[Storage read-only rule](../15_Storage.md#read-only-storage-rule), and
[Study Lineage contract](study-lineage-v1.md) continue to govern source facts.

The capability graph describes a **possible trajectory**. Study Lineage describes
the supported **observed trajectory**. A recommendation cannot supply evidence
that an operation occurred, admit material to Scope, accept a proposal, or revise
a Blueprint. Readiness does not authorize provider execution.

## Single definition source and programmatic seam

`hermeneia/data/capability-registry-v1.json` is the canonical static definition
source, included in the Python package. `hermeneia/capabilities.py` exposes only
the loader, evaluator, and invalid-registry exception needed by a later consumer:

```python
from hermeneia.capabilities import load_capability_registry, evaluate_capabilities
from hermeneia.study_lineage import project_study_lineage

registry = load_capability_registry()
# Caller owns an existing read-only snapshot/connection; no initialization.
lineage = project_study_lineage(read_only_connection)
result = evaluate_capabilities(lineage, registry, current_state={
    "governing_question": "What does this evidence permit?",
    "perspective_available": True,
})
```

The evaluator performs no SQL, network calls, timestamp capture, or persistence.
It consumes the access-filtered `hermeneia.study-lineage/v1` projection, including
its coverage. It does not independently authenticate supplied dictionaries or
recheck source files: callers must use the existing Lineage projection owner,
not fabricate facts. Unknown projection versions or malformed inputs refuse
evaluation. Only the two explicit current-state keys shown above are accepted;
onboarding/localStorage flags and historical-completion hints are rejected.

Each definition requires `capability_id`, `definition_version`, `title`,
`purpose`, `prerequisites`, `positive_evidence`, `refusal_or_unknown_conditions`,
`expected_outputs`, `related_or_next_capabilities`, and `user_facing_explanation`.
Predicates contain a known symbolic `fact` and positive integer `minimum`;
prerequisites also contain a symbolic reason code and explanation. No expression
evaluation, dynamic imports, or scripts occur in definitions. Unknown fields,
facts, related IDs, duplicate IDs/predicates, malformed versions, duplicate JSON
keys, and nonfinite JSON values fail closed as `CapabilityRegistryError`.

Definitions belong to versioned software rather than the workspace DB. No WBS
change or retention contract is needed for these ephemeral evaluations. Vectors
are absent: all v1 decisions follow explicit, inspectable predicates.

## Readiness facts and supported historical limits

The adapter preserves Lineage's typed table/key, event, timestamp, authorship,
and provenance exactly in evidence references. Equal text or IDs across types
do not collapse. Multiple views of one typed key count as one durable identity;
their separate audit references remain available. Decision views do not create
additional evidence/interpretation identities. The adapter does not recompute
acceptance or authorship, invent chronology, or inspect excluded children.

Missing relevant tables/columns or omitted records remain coverage unknowns.
Extant eligible facts can satisfy a minimum despite other missing coverage;
insufficient extant facts with incomplete coverage cannot establish known absence.
The original Lineage coverage is also returned unchanged in the result.

| Capability ID | Current readiness prerequisite | Historical evidence in v1 |
| --- | --- | --- |
| `governing_question` | None; setting a current question is possible | Unsupported: mutable question state does not record formulation/revision history |
| `read_source` | Eligible extraction with nonblank raw text | Unsupported: extraction/progress does not establish reading/comprehension |
| `mark_evidence` | Eligible extraction with nonblank raw text | Unsupported: Reader mark snapshots do not establish historical marking behavior/authorship |
| `record_observation` | Eligible Observation or Reader mark | Unsupported: compiler segmentation is not a human observation act; promotion marks a candidate |
| `preserve_question` | Eligible Observation or Reader mark | Narrow retained result: separately identified, nonblank recorded `inquiry_notes` question; authorship can remain unknown |
| `organize_evidence` | At least two distinct eligible Observation/Reader mark identities | Unsupported: buckets/rankings/selections do not establish organization history |
| `explore_perspective` | Supported inquiry context and eligible evidence | Unsupported: saved Perspective declarations and transient receipts do not establish durable execution |
| `form_interpretation` | Eligible Observation and named saved/current Perspective frame | Narrow retained result: recorded nonblank canonical Interpretation whose Lineage origin is `human` or `accepted_model` |
| `challenge_interpretation` | Eligible nonblank proposal/canonical Interpretation and Observation | Unsupported: Critic findings/decisions do not establish human review or contradiction-seeking |
| `review_blueprint` | Eligible saved Blueprint | Unsupported: creation/supersession is not evidence of review |
| `review_lineage` | At least one eligible Lineage record | Unsupported: opening/filtering/exporting is not a durable review event |

The `record_observation` ID is retained, with the title “Record or inspect an
observation,” to distinguish inspecting a compiler-derived canonical unit from
designating an anchored Reader candidate. Neither operation rewrites evidence.

Inquiry context uses a recorded inquiry note, the current
`workspace_investigation.id='current'` thesis snapshot, or the explicitly supplied
current question. A supplied question replaces the singleton fallback; it does
not replace preserved inquiry notes. The optional frame boolean replaces the
saved named-Perspective fallback for current readiness only. Saved declarations
are never Perspective run evidence or provider identity.

The two supported retained-result claims are existential and narrow. They do
not establish authenticated user identity, mastery, a complete operation history,
question resolution, or all formation steps. A proposal alone cannot prove
canonical formation. Mutable highlight questions are not separate question
identities. Absence of an extant record never proves an operation never occurred.

## Result and status interpretation

The result uses `hermeneia.capability-evaluation/v1`, identifies registry and
evaluator versions/digest, copies workspace/Lineage coverage, and returns each
definition version, status, reason code/reason, evidence references, coverage
notes, and satisfied/missing prerequisites. Reasons are symbolic data; prose is
explanatory. The separate `availability` and `availability_reason_code` fields
describe readiness even when historical exercise cannot be established.

| `status` | Meaning |
| --- | --- |
| `already_exercised_under_supported_evidence` | The definition's narrow retained-result predicate has an eligible witness; current readiness is still reported independently |
| `not_yet_available` | Current prerequisites are known insufficient, with an explicit missing-prerequisite reason |
| `unsupported_due_to_missing_history` | Required coverage is incomplete (`COVERAGE_UNSUPPORTED`), or the historical claim is unsupported (`HISTORY_UNSUPPORTED`) |
| `available` | Current prerequisites are satisfied, the definition supports a narrow retained-result check, and no such extant result is present; this does not claim historical non-occurrence |

Precedence is: supported retained result; unresolved current readiness; historical
unsupported condition; otherwise available. Thus nine definitions can have
`availability=available` while `status=unsupported_due_to_missing_history`.
A later recommendation consumer must use readiness separately and retain the
historical limit. Conversely, a retained Interpretation can establish the narrow
result while today's selected frame is unavailable. No award is issued.

Reason codes are `READY`, `MISSING_SOURCE`, `INSUFFICIENT_EVIDENCE`,
`MISSING_INQUIRY_CONTEXT`, `MISSING_PERSPECTIVE`, `NO_INTERPRETATION`,
`NO_BLUEPRINT`, `NO_LINEAGE`, `COVERAGE_UNSUPPORTED`, `HISTORY_UNSUPPORTED`,
and `ALREADY_EXERCISED`.

## Versions and deterministic identity

The registry and each definition start at `1.0.0`, as does the evaluator's fact
adapter/rule version. Versions use ASCII `major.minor.patch` without leading
zeros. Definition changes must advance the affected definition version and
registry version. Adapter/status semantics changes must also advance the
evaluator version and affected definition/registry versions; a git SHA alone
does not identify the rule. Released v1 definitions are guarded by a digest test.

`registry_sha256` hashes validated definitions ordered by capability ID, serialized
as finite JSON with sorted object keys, UTF-8, unescaped Unicode, compact separators,
and one trailing LF. Predicate/related/output list order remains part of this
identity. Evaluation returns capabilities in ID order and references/unknown notes
in deterministic order. Repeating the same supported facts and versions produces
identical output; input dictionaries and source state remain unchanged. The digest
identifies definitions, not a persisted award, verified workspace snapshot, or
new build/release identity.

## Validation and remaining boundary

Focused tests cover strict definitions, all requested scenario categories, typed
identity, exact copied provenance, unknown authorship, partial/legacy coverage,
current readiness without completion, and read-only/provider-free evaluation.
Actual Lineage fixtures include accepted-model provenance, excluded parent closure,
missing inquiry identity, and malformed saved frames. The wheel includes the
static registry and loads it outside the source checkout.

Measured validation on 2026-09-30 (Python 3.13.5, Node 22.17.0):

- `python3 -m pytest -q tests/test_capabilities.py tests/test_capabilities_lineage.py
  tests/test_study_lineage.py tests/test_study_lineage_api.py tests/test_study_lineage_ui.py`:
  **130 passed** (55 P1 and 75 existing Lineage tests), five existing dependency warnings.
- `python3 -m pytest -q`: **2,038 passed, 21 skipped, six Reader failures**,
  five existing dependency warnings. No live-provider opt-in was used.
- Independently archived starting commit `1af8381` full suite: **1,983 passed,
  21 skipped, the same six Reader failures**. All 605 archived tracked files
  retained their original bytes. The failed test-ID sets match exactly.
- Wheel build with no dependency installation or build isolation succeeded;
  isolated Python loading from that wheel returned all 11 definitions and the
  expected registry digest. `git diff --check` passed.

The six unchanged failures are:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

Adversarial tests first failed against the initial P1 implementation for malformed
reason codes, Unicode version digits, duplicate views inflating evidence counts,
missing inquiry identity reported by Lineage, and missing/blank named frames.
The bounded codec/fact-adapter repairs made those tests pass. Existing Lineage
eligibility, canonical data, and Reader failure assertions were not changed.

No real user workspace is inspected or changed. No schema migration, WBS change,
evaluation persistence, generic history store, coaching UI, achievements, badges,
providers, Blueprint authority changes, or P2 implementation is included.
P2 may consume this seam for a Guided Study Cycle, preserving explicit Scope and
approval boundaries and the unsupported histories above; it must not convert
readiness or UI completion flags into accomplishments.
