# Deterministic Companion Coach v1 — P6 contract

Date: 2026-10-07. Contract frozen before production implementation, on
`main` `ce1543f`. This implements P6 of
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215) under the
steward boundaries in
[#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214) and the
[capability-coaching audit](capability-coaching-architecture-audit.md) (§13:
a coaching evaluation records its version, inputs, coverage and what it
suggested or withheld; a recommendation is not proof it was shown, accepted
or helpful).

The [Capability Registry v1](capability-registry-v1.md) owns readiness and
historical support. The [Guided Study Cycle v1](guided-study-cycle-v1.md)
owns the ordered method and its single recommended step.
[Study Lineage](study-lineage-v1.md) owns eligibility, exclusion, authorship
and coverage. This coach owns only one question:

> Given the study state Hermeneia can actually justify, should the Companion
> intervene now? If so, what single bounded study operation should it
> suggest, and why?

It is not a chatbot, a recommender model, or a feature advertisement. It
calls no provider, persists nothing, and is not study history.

## Inputs

`coach(evaluation, guide)` receives exactly two existing production outputs,
both computed from one Lineage snapshot and one current state:

- `evaluation`: `evaluate_capabilities(...)` (`hermeneia.capability-evaluation/v1`);
- `guide`: `project_guided_study_cycle(...)` (`hermeneia.guided-study-cycle/v1`, guide `1.0.0`).

The coach never reads SQL, Lineage items or raw workspace history, and never
re-derives eligibility, authorship, exclusion or coverage. It reads only:

- P1 per-capability `availability`, `status`, reason codes and reasons,
  satisfied/missing prerequisites, typed `evidence_refs` (with Lineage
  `authorship` and `event`) and `coverage_or_unknown_notes`;
- P2 step states, `recommended_step_id`, `recommendation_reason`, each step's
  `recommended_action`, `target_surface`, `why_it_matters`, `status_reason`,
  `history_support` and `evidence_or_state_basis`;
- P2 `lineage_coverage`.

The inputs must be consistent, or the coach refuses with `ValueError`:

- the schemas are supported;
- the registry and evaluator versions and the registry digest are equal in
  both inputs;
- the recommended step exists;
- every step's P2 availability and capability status equal the P1 values.

Existing Companion presentation preferences (`paused`, `dismissed`) remain
client-side display gates. They are not coach inputs and never evidence.

## Decision rules (policy `1.0.0`)

Let `S` be P2's `recommended_step_id`. The coach never selects any other
capability and never changes P1 or P2 results. In order:

| # | Condition (production facts) | Decision | `quiet_reason` |
| --- | --- | --- | --- |
| 1 | P1 `availability(S)` is `not_yet_available` | `remain_quiet` | `NEXT_STEP_BLOCKED` (the missing prerequisites are reported, not suggested) |
| 2 | P1 `availability(S)` is `unsupported_due_to_missing_history` | `remain_quiet` | `NEXT_STEP_UNKNOWN` (readiness cannot be established; never "not done") |
| 3 | `S` is `review_lineage` | `remain_quiet` | `OPTIONAL_REVIEW_ONLY` (P2 reaches Lineage review only as its terminal resumption point; review has no recordable completion and no evidence justifies an intervention) |
| 4 | otherwise | `suggest` `S` | — |

These rules guarantee:

- **Rules 1–2:** the coach can never make an unavailable capability
  available or override a P1 prerequisite.
- **Rule 3:** mature trajectories may legitimately produce silence. Less
  intervention as retained capability grows is the intended direction, but
  silence is never claimed as evidence of independence.

A suggestion's `basis` is `durable_history` when it rests on P2's
retained-result anchor (the governing question is `currently_supported` and
`form_interpretation` is `historically_exercised`). Otherwise it is
`current_state`.

## Output — `hermeneia.companion-coach/v1`

The machine-readable schema is
`tests/fixtures/companion_coach/v1/coach-result.schema.json`.

| Field | Content |
| --- | --- |
| `schema`, `policy_version` | `hermeneia.companion-coach/v1`, `1.0.0` |
| `inputs` | guide schema/version, registry/evaluator versions and digest, and P2's `recommended_step_id` |
| `decision` | `suggest` or `remain_quiet` |
| `quiet_reason` | `null`, `NEXT_STEP_BLOCKED`, `NEXT_STEP_UNKNOWN` or `OPTIONAL_REVIEW_ONLY` |
| `suggestion` | `null`, or `{capability_id, definition_version, title, action, target_surface, basis, readiness}`. `action` and `target_surface` are P2's. `readiness` copies P1 availability, its reason code and the satisfied/missing prerequisites |
| `noticed` | the observed facts (vocabulary below), each with `fact`, `count`, `basis`, `authorship`, `statement` and `evidence` (the exact typed P1/P2 references) |
| `why_now` | P2's own `why_it_matters` and `status_reason` for `S`, plus P2's `recommendation_reason` |
| `next_action` | P2's `recommended_action` for `S` |
| `uncertainty` | qualifications, each with `code`, `statement` and `source` |
| `blocked` | for `NEXT_STEP_BLOCKED` and `NEXT_STEP_UNKNOWN`: P1 availability, reason code, reason and missing prerequisites for `S` |
| `withheld` | every other step, with a code explaining why it is not suggested |
| `not_history` | a fixed statement that this is a current coaching projection, not study history, and not proof of exposure, acceptance or benefit |

Each suggestion therefore reads as *observed evidence → why this operation
is appropriate now → bounded next action*, with one recommendation rather
than a menu.

### Fact vocabulary

Facts come only from P1 `evidence_refs` (distinct typed record keys) or P2
step state. A fact is emitted only when its count is greater than zero.
Absence is never stated as a fact.

| Fact | Source | Basis | Statement template |
| --- | --- | --- | --- |
| `governing_question_present` | P2 `governing_question` is `currently_supported` | current_state | A governing question is present now. |
| `saved_reader_marks` | P1 `organize_evidence` refs, table `reader_highlights` | current_state | {n} saved Reader mark(s) are present as current snapshots; when or by whom they were made is not recorded. |
| `grouped_marks` | P2 `organize_evidence` basis refs when the step is `currently_supported` | current_state | {n} saved Reader mark(s) currently carry group labels; labels are not organization history. |
| `canonical_observations` | P1 `form_interpretation` refs, table `observations` | durable_history | {n} canonical Observation(s) are available as compiler-derived source units. |
| `inquiry_questions` | P1 `preserve_question` refs, table `inquiry_notes` | durable_history | {n} inquiry question(s) are retained beside Observations. |
| `saved_frames` | P1 `form_interpretation` refs, table `perspectives` | durable_history | {n} saved Perspective frame(s) are declared; a frame declaration is not a run. |
| `selected_frame` | P1 `form_interpretation` current-state input `perspective_available` | current_state | A Perspective frame is selected now. |
| `retained_perspective_executions` | P1 `explore_perspective` refs, table `perspective_execution_receipts` | durable_history | {n} retained Perspective execution(s) are model-generated; keeping them is not agreement. |
| `interpretation_material` | P1 `challenge_interpretation` refs, tables `interpretations` and `proposed_interpretations`, one statement per authorship | durable_history | `human`: {n} steward-authored Interpretation(s) are retained. `accepted_model`: {n} accepted model contribution(s) are retained as Interpretations. `model`: {n} model proposal(s) are present; a proposal is not a steward-authored Interpretation. `unknown`: {n} Interpretation record(s) have unrecorded authorship. |
| `blueprints` | P1 `review_blueprint` refs, table `narrative_blueprints` | durable_history | {n} saved Blueprint(s) are retained; review of a Blueprint is not recorded. |

### Uncertainty codes

| Code | Emitted when | Statement source |
| --- | --- | --- |
| `ABSENCE_NOT_PROOF` | every `suggest` whose step is not `historically_exercised` | P1's own note: "Absence of an extant record is not proof that an operation never occurred." |
| `HISTORY_NOT_RECORDED` | the suggested step's P2 `history_support.status` is `unsupported` | P2 `history_support.reason` |
| `COVERAGE_INCOMPLETE` | `lineage_coverage` reports missing tables or columns | the missing tables/columns, stated as records Hermeneia cannot inspect |
| `RECORDS_OMITTED` | `lineage_coverage.omitted` is nonzero | Some records are omitted from this projection (for example, records from sources excluded from analysis, or records whose parents are unavailable) and do not inform this coaching result. This follows Lineage's own omission categories. |
| `AUTHORSHIP_UNKNOWN` | any P1 note reports unknown canonical Interpretation authorship | the P1 note |

### Withheld codes

| Code | Meaning |
| --- | --- |
| `PREREQUISITE_MISSING` | P2 state is `not_ready`; carries the P1 availability reason code |
| `COVERAGE_UNSUPPORTED` | P2 state is `unknown` |
| `LATER_IN_CYCLE` | the step is `ready` and ordered after `S` |
| `NOT_RECONSTRUCTED_BY_RESUMPTION` | the step is `ready` and before `S`, skipped by P2's retained-result resumption; earlier method actions are not reconstructed |
| `ALREADY_CURRENT_MATERIAL` | the step is `currently_supported` |
| `NARROW_HISTORY_RETAINED` | the step is `historically_exercised` |

## Invariants (tested)

1. Missing history stays missing: no fact is emitted for an absent record,
   and `unsupported` maps only to `NEXT_STEP_UNKNOWN`, `COVERAGE_UNSUPPORTED`
   or a coverage qualification.
2. No output text says or implies the user has not done something:
   "you haven't", "you have not", "you didn't", "you did not",
   "not yet done", "never did", "you still need to".
3. A UI action is never evidence. Mutable snapshots are labeled
   `current_state`, and no completion is claimed.
4. An unavailable capability is never suggested (rules 1–2).
5. P1 prerequisites and P2's recommendation are never overridden; the
   suggestion is always P2's `S`.
6. Model-generated activity is labeled model-generated, and never described
   as steward- or user-authored.
7. Excluded evidence never motivates a recommendation: every fact cites only
   eligible Lineage references.
8. Explanations come from P2's own purpose and status text. There is no
   feature advertisement or engagement language: streaks, praise, urgency,
   points, badges, unlocks or exclamations.
9. Mature trajectories may produce `remain_quiet`.
10. No provider or model dependency, no persistence, no telemetry.

## Read-only API

`GET /api/companion/coach` mirrors `GET /api/guided-study-cycle`: the same
optional single current frame selection, a read-only snapshot, the same
refusals, `Cache-Control: no-store`, and no store initialization. It returns
the coach result plus the validated `current_frame_selection`, as the guide route
does. It writes nothing. Companion rendering is outside this packet.

## Evaluation

The seven frozen P5 trajectories are the initial evaluation set; their facts
are unchanged. Two P6 negative scenarios add a blocked next step
(N1: a governing question with no source) and an unknown next step (N2: a
labeled legacy shape missing `source_extractions`). Frozen expectations live
in `tests/fixtures/companion_coach/v1/expectations.json`.

## Not in P6

- vector retrieval (P9);
- natural-language Blueprint control (P8);
- Perspective comparison (P7);
- providers;
- persisted coaching outcomes;
- engagement telemetry;
- an Independent Investigator claim;
- any change to P1, P2 or P5 semantics.
