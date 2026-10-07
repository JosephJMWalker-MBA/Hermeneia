# #215 P6 Deterministic Companion Coach v1 — 2026-10-07

**Result:** The production coach was evaluated over the seven frozen P5
trajectories (facts unchanged) and two P6 negative scenarios. It met the
frozen contract in all nine scenarios, passing all 22 checks in each:

- 0/9 forbidden suggestions;
- no unavailable capability was ever suggested;
- it always followed P2's recommendation;
- both mature trajectories stayed quiet;
- both negatives stayed quiet with the prerequisite or coverage gap
  reported;
- it was repeatable and invariant to item order, storage order and text.

No defect in existing P1, P2 or P5 authority was found.

- **Base:** `main` `ce1543f` (P5 merged via PR #247); branch `p6-companion-coach`
- **Contract frozen first:** `040f750`, before any production code. It
  contains `docs/design/companion-coach-v1.md`,
  `tests/fixtures/companion_coach/v1/coach-result.schema.json` and
  `expectations.json`.
- **Production code:**
  - `hermeneia/companion_coach.py`: pure, standard library only;
  - `GET /api/companion/coach`: read-only;
  - a shared `_current_frame_selection` helper factored from the existing
    guide route, whose behavior is unchanged (the P2 API and projection tests
    still pass).
- **P1, P2 and P5 semantics:** unchanged; no provider, persistence or
  telemetry.

## What the coach does

`coach(evaluation, guide)` reads only the production P1 evaluation and P2
projection of one snapshot. It refuses inputs that do not come from the same
registry, evaluator and snapshot.

It never chooses a step other than P2's `recommended_step_id`. It stays
quiet when:

- P1 reports that step `not_yet_available` (`NEXT_STEP_BLOCKED`, with the
  missing prerequisites);
- P1 reports it `unsupported_due_to_missing_history` (`NEXT_STEP_UNKNOWN`);
- the step is only optional Lineage review (`OPTIONAL_REVIEW_ONLY`).

Otherwise it suggests that one step, with:

- **noticed facts:** counts of typed production records, each carrying its
  Lineage authorship and basis (`current_state` or `durable_history`);
- **why now:** P2's own purpose and status text;
- **next action:** P2's own action and target;
- **uncertainty:** absence is not proof, history is not recorded, coverage is
  incomplete, records are omitted, authorship is unknown;
- **withheld:** a code for every other step;
- **a fixed not-history statement.**

## Evaluation

`tests/companion_coach_lab.py` materializes each scenario with the P5
laboratory: production write boundaries, disposable synthetic workspaces,
in-process fakes, no network. Production P1/P2 decide, and the production
coach advises. Results are in `research/companion_coach/v1/results.json` and
`summary.md`.

| Scenario | P2 next | Coach |
| --- | --- | --- |
| T1 heavy highlighter | `preserve_question` | suggests `preserve_question` (current state) |
| T2 early interpreter | `challenge_interpretation` | suggests `challenge_interpretation` (durable history) — the #215 example |
| T3 questions, legacy shape | `governing_question` | suggests `governing_question`; withholds interpretation as `COVERAGE_UNSUPPORTED` |
| T4 model-reliant | `read_source` | suggests `read_source`; both model artifacts labeled model-generated |
| T5 Blueprint, unreviewed | `review_lineage` | `remain_quiet` (`OPTIONAL_REVIEW_ONLY`) |
| T6 careful worker, excluded source | `form_interpretation` | suggests `form_interpretation`; counts only eligible records; `RECORDS_OMITTED` |
| T7 advanced | `review_lineage` | `remain_quiet` (`OPTIONAL_REVIEW_ONLY`) |
| N1 question, no source | `read_source` (blocked) | `remain_quiet` (`NEXT_STEP_BLOCKED`, `MISSING_SOURCE`) |
| N2 legacy, no extractions | `read_source` (unknown) | `remain_quiet` (`NEXT_STEP_UNKNOWN`, `COVERAGE_UNSUPPORTED`) |

Checks applied to every scenario:

- schema validity;
- decision, quiet reason, suggestion and basis;
- forbidden suggestions;
- never suggesting an unavailable capability;
- following P2;
- required and forbidden facts with exact counts and authorship;
- required uncertainty and withheld codes;
- blocked details and statement fragments;
- unsupported-as-not-done wording;
- engagement language;
- authorship distinctions;
- evidence correspondence (every fact's evidence resolves to a real Lineage
  item with the same authorship, and counts equal distinct records);
- silence where preferred or required;
- repeatability (same snapshot, and an independent rebuild);
- invariance to item order, reversed storage order, and neutralized text and
  labels;
- workspace unchanged.

Regression tests (`tests/test_companion_coach.py`, 8 passed):

- the committed dataset and matrix are reproduced;
- **negative:** with a tampered guide pointing at each capability P1 marks
  unavailable in T1, the coach stays quiet and reports the prerequisite;
- inputs from different snapshots, loosened availability, or an unsupported
  guide version are refused;
- the module imports only the standard library;
- the API equals the function result, is read-only (logical dump unchanged,
  `no-store`), refuses unsupported input, and creates no workspace when none
  exists.

Focused P1/P2/P5/P6 suites: 138 passed. Neighboring suites: 365 passed.

## The four P5 observations

1. **T1:** P2 orders preserving an inquiry question before organizing
   evidence. The coach keeps that order rather than reordering for
   effectiveness. Six unlabeled marks are noticed only as current snapshots,
   never as grouped evidence.
2. **T3:** legacy frame readiness stays `unknown`. The coach withholds
   interpretation as `COVERAGE_UNSUPPORTED`, names the records it cannot
   inspect, and never says a frame was not saved.
3. **T4:** Perspective runs and the proposal are stated as model-generated
   and "not a steward-authored Interpretation". They never substitute for
   user-authored interpretation, and the coach returns to the source.
4. **T5:** no Blueprint review is recorded, so the Blueprint is described
   only as "review of a Blueprint is not recorded". The coach stays quiet
   rather than claiming or demanding review.

## Contract correction disclosed

After the contract commit, two template details were corrected before this
evaluation was finalized:

- the `RECORDS_OMITTED` statement now ends "…do not inform this coaching
  result" instead of "…this suggestion", because it also appears in quiet
  results;
- the API description now names its `current_frame_selection` field.

No expectation, decision rule or vocabulary changed.

## What P6 demonstrates

A provider-free coaching layer can decide when to intervene and what single
operation to suggest, from production P1/P2 outputs alone. It:

- never bypasses a prerequisite or P2's order;
- never treats unsupported state as undone work;
- never presents model work as user reasoning;
- never lets excluded evidence motivate a suggestion;
- stays quiet for mature trajectories and blocked or unknown next steps;
- is deterministic and read-only.

That is the #215 P6 gate.

## What P6 does not demonstrate

- **Effectiveness.** Nothing shows that the coaching helps learners, that
  silence reflects independence, or how real users respond. No exposure,
  acceptance or outcome is recorded, by design.
- **No rendering.** The Companion does not yet render the coach.
- **Wording.** Explanations reuse P2's production text and are not tuned for
  pedagogy.
- **No P7–P9 work.** There is no Perspective comparison (P7),
  natural-language Blueprint control (P8) or vector retrieval (P9).
- **No Independent Investigator claim.**
