# #215 P5 Synthetic Study Laboratory v1 — 2026-10-07

**Result:** All seven planned trajectories were evaluated by the production
P1 Capability Registry and P2 Guided Study Cycle over disposable synthetic
workspaces.

| Measure | Result |
| --- | --- |
| Capability states | 231/231 agree with the frozen, authority-derived expectations |
| Unsupported vs not-yet distinction | 75/75 |
| Next step | 7/7 preferred and permitted |
| Forbidden suggestions | 0/7 |
| Repeatable | 7/7 |
| Invariant to Lineage item order and storage order | 7/7 |
| No manufactured history | 7/7 |
| Invariant to labels and wording | 7/7 |

No product defect was found, so no issue was filed.

- **Base:** `main` `01fa7d9`; branch `p5-synthetic-study-lab`
- **Packet:** [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215)
  P5, under [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214)
  and [audit §12](../design/capability-coaching-architecture-audit.md#12-synthetic-study-lab-strategy)
- **Production under evaluation:** registry `1.1.0` (digest
  `eafda6b4081c…`), evaluator `1.1.0`, guide `1.0.0`; lab policy
  `p5-lab-1.0.0`
- **Production code changed:** none

## Deliverables

| Artifact | Path |
| --- | --- |
| Versioned trajectory schema | `tests/fixtures/synthetic_study_lab/v1/trajectory.schema.json` (`hermeneia.synthetic-study-trajectory/v1`) |
| Seven frozen trajectories | `tests/fixtures/synthetic_study_lab/v1/trajectories/T1…T7.json` |
| Deterministic runner | `tests/synthetic_study_lab.py` (`--write` / `--check`) |
| Machine-readable results | `research/synthetic_study_lab/v1/results.json` (`hermeneia.synthetic-study-lab-results/v1`) |
| Human-readable matrix | `research/synthetic_study_lab/v1/summary.md` |
| Regression tests | `tests/test_synthetic_study_lab.py` |

The contract (schema and seven trajectories) was committed as `b18131a`
**before the runner existed**. The fixtures have not changed since.

The expected states and recommendations were derived by hand:

- from `capability-registry-v1.md`: status precedence, readiness facts and
  authorship origin;
- from `guided-study-cycle-v1.md`: guide states, the ordinary ordered walk
  and the two retained-result resumption anchors.

The first run agreed in every cell, so no expectation was adjusted to fit
production.

## Method

Each trajectory declares synthetic documents, an ordered list of operations,
the explicit current-state inputs, the exact expected Lineage item counts
(`table|event|authorship`), the explicit coverage limits, and its
expectations.

The runner materializes each trajectory into a disposable workspace. Every
operation goes through an existing production write boundary:

- upload, governing question, Reader marks, inquiry questions and saved
  Perspectives;
- retained Perspective runs through `/api/perspective/run` and `/retain`;
- steward-authored Interpretations through
  `SQLiteStore.insert_interpretation`;
- E10 proposal generation and acceptance;
- Blueprint ratification;
- source exclusion.

T3's single labeled legacy-shape operation (dropping the `perspectives`
table) is the only direct SQL. Per audit §12, it is not proof that a user
workflow produces that state.

The runner then reads the workspace read-only (`mode=ro`,
`PRAGMA query_only=ON`) and calls `project_study_lineage`,
`evaluate_capabilities` and `project_guided_study_cycle`. They receive only
the Lineage snapshot and the declared current state. A regression test spies
on these calls and confirms that no trajectory ID, profile, reason, derivation
or edge text reaches them.

Adapters were in-process fakes: the repository's own P3 fake Ollama client
and a canned OpenAI-shaped E10 adapter. Outbound sockets were blocked, no
credential store was used, connection settings were throwaway, and no real
workspace or private text was involved.

Metrics per trajectory:

| Metric | How it is checked |
| --- | --- |
| Capability state | `availability`, `status` and guide state for all 11 capabilities (33 cells) |
| Unsupported vs not-yet | the cells expected as `not_yet_available` or `unsupported_due_to_missing_history` |
| Next step | production recommendation is the preferred step and in the permitted set |
| Forbidden suggestion | production recommendation appears in `must_not_suggest` |
| Repeatability | byte-identical evaluation of the same workspace twice, and identical decisions from an independently materialized second workspace |
| Order invariance | byte-identical results with Lineage items reversed and seeded-shuffled, and identical decisions from a copy whose rows are stored in reverse physical order |
| No manufactured history | the workspace's logical dump is unchanged by evaluation; production Lineage equals the declared item counts and coverage exactly; every record reference (124–187 per trajectory) resolves to a real Lineage item; current-state references only name declared inputs |
| Evidence, not labels | the same trajectory with all text and labels neutralized yields identical decisions |

## Results

| Trajectory (#215 profile) | Edge discriminated | Production next |
| --- | --- | --- |
| T1 highlights heavily, weak synthesis | Six unlabeled marks do not make organizing currently supported; no saved frame is a *known* absence (`not_yet_available`) | `preserve_question` |
| T2 forms interpretations too early | Unrecorded earlier steps are not reconstructed; resumes at counterevidence | `challenge_interpretation` |
| T3 many questions, never resolves (legacy shape) | Inquiry questions are not relabeled as the governing question; a missing `perspectives` table makes frame readiness *unknown* (`unsupported_due_to_missing_history`, guide `unknown`), not `not_ready` | `governing_question` |
| T4 relies on model Perspectives | An unaccepted proposal neither attributes formation nor triggers the counterevidence anchor; built-in runs are history, not saved frames | `read_source` |
| T5 organizes, never reviews Blueprint | A saved Blueprint is material, never evidence of review; routes to Lineage | `review_lineage` |
| T6 careful worker, open questions | Excluded-source records are omitted as coverage gaps (5 tables) while extant records satisfy minimums; a supplied question replaces the singleton fallback | `form_interpretation` |
| T7 advanced, self-directed | Everything earlier is material or narrow history; only Lineage review is suggested, with no Full Cycle claim | `review_lineage` |

Two tests prove the results come from production rules rather than the
fixtures:

- Raising the attributable-Interpretation minimum in the production registry
  changes T2's recommendation to `read_source`, and the runner reports
  exactly the two affected cells as mismatches.
- A deliberately wrong T1 expectation is reported as a mismatch, and the
  fixture file is left unchanged.

## Policy observations (laboratory/specification, not defects)

These follow from current authority and are inputs for P6 policy design, not
corrections to P1 or P2:

1. **T5:** P2 cannot direct a user to an unreviewed Blueprint, because review
   is not durably recorded. It routes to Lineage inspection instead.
2. **T1:** the fixed ordered walk asks a heavy highlighter with weak
   synthesis to preserve a question before organizing evidence.
3. **T4:** a user who has only run built-in Perspectives sees
   `form_interpretation` as not ready until a frame is saved or selected,
   because a run is not a frame declaration.
4. **T3:** a legacy workspace's frame readiness is reported as `unknown`
   rather than missing. That is correct, but it will need careful wording in
   any coaching surface.

## What P5 demonstrates

The production P1/P2 policy behaves as its own authority specifies across
seven lawful trajectories, one of them ending in a legacy shape:

- it separates current readiness from historical support;
- it distinguishes unsupported coverage from known absence;
- it refuses superficially similar evidence;
- it never manufactures history;
- it is deterministic and insensitive to row order, storage order and
  wording.

The laboratory can now compare policies reproducibly, which is the #215 P5
gate.

## What P5 does not demonstrate

- **Real users.** It establishes nothing about real learners. The
  trajectories are synthetic, few, and not a representative sample.
- **Pedagogy.** Expectations encode current authority, not pedagogically
  optimal coaching.
- **Coaching effectiveness.** Nothing is measured about whether coaching
  helps, and no adaptive policy is evaluated.
- **No P6 or later.** There is no Companion behavior, vector retrieval,
  achievement or award, and no claim about answer quality or source
  fidelity.
- **Legacy fixture.** The T3 shape is labeled direct SQL and is not a
  reachable user workflow.
- **No history written.** The fixtures and results are evaluation data, not
  study history, and require no change to the Workspace Bundle.
