# #215 P8 live Blueprint proposal diagnostic — 2026-10-10

**Verdict: `P8_GOVERNANCE_READY_GENERATION_NOT_READY`.**

- **Governance held on every run.** No defect occurred, nothing was written,
  and every refusal reproduced.
- **Generation failed every criterion** of the frozen thresholds
  (`blueprint-proposal-live-thresholds/v1`).
- Generation stays disabled by default. Passing would not have authorized
  ordinary use either (disposition §3).

## Authorization and freeze

- **Owner authorization, 2026-10-10:**
  - installed `hermeneia-phi4-mini:latest` through the existing local Ollama
    path;
  - isolated synthetic workspaces;
  - six cases, three samples each;
  - nothing accepted;
  - no tuning, no expectation changes, no other model.
- **Frozen before the first call** at `3c129a1`:
  - `tests/fixtures/blueprint_proposal/v1/live_evaluation_protocol.json`:
    cases, evidence sets, rubric v1, thresholds v1, defect checks;
  - `tests/blueprint_proposal_live_eval.py`: harness, independent census,
    aggregation;
  - the scripted ceiling and its grades.

  The harness refuses to run live unless both files are committed and the
  installed model digest matches.
- **Pinned:** `tests/test_blueprint_proposal_live_protocol.py` pins both
  files' bytes.
- **Ceiling correction (before freezing, before any output).** The P10
  governance script was not used as the L4 ceiling. Under the rubric, its
  thesis ("is lit again at dusk") misdescribes A:5, which records a *second*
  lamp, and asserts the open sequence. It remains valid governance test data.

## Run

- **Model:** digest `df37b15c…85ffa0f`, phi3 3.8B Q4_K_M, identical before
  and after.
- **Production route:** `POST /api/blueprint/proposals`, with the gate set on
  the evaluation app only and adapter `OllamaArtistProvider`.
- **Isolation:** loopback only, fresh connection settings, P5 isolation for
  setup.
- **Sampling:** the production path sends no generation options, so Ollama
  defaults apply.
- **Calls:** 18, in round-robin order; mean latency 6.3 s.
- **Retries:** none; no provider failures.
- **Preserved per run** (`research/blueprint_proposal_live/phi4-mini/results.json`):
  - prompt and digest;
  - raw output and digest;
  - full response body (candidate or refusal);
  - census;
  - governance checks;
  - case-local proposal;
  - reference scores.
- **Grades** (`grading.json`): the 4 admitted outputs, graded under rubric v1
  after the run and before any aggregate. Grading is bound by digest to those
  exact outputs.
- **Reproducibility:** the aggregate recomputes offline (`check`, and a test).

## Results

| Criterion | Result |
| --- | --- |
| Governance D1–D7 | **0 defects** on 18 runs |
| C1 invented/excluded references (non-negotiable, 0) | **fails**: 7 runs, 8 tokens |
| C2 admission (≥17/18; ≥2 per case) | **fails**: 4/18; L3–L6 admitted 0 |
| C3 references (per sample and pooled) | **fails**: 2 of 4 admitted miss a required reference; pooled expected recall 0.5625 |
| C4 semantic fidelity | **fails**: see below |
| C5 consistency | **fails**: no case had ≥2 passing samples; L1 Jaccard 0.33, L2 0.40 |

### Governance

On all 18 runs:
- the generation request left the workspace digest and the canonical counts
  unchanged;
- no receipt exists.

Every 422 code reproduced by re-parsing the preserved output. The parser's
behavior agrees with the independent census:
- no contract-invalid output was admitted;
- no contract-valid output was refused.

Each admitted candidate's ID, prompt, binding and execution verify.

### Refusals

The 14 refused outputs break down as:
- 7 `PROPOSAL_OUTPUT_INVALID`;
- 6 `PROPOSAL_REFERENCE_UNKNOWN`;
- 1 `PROPOSAL_OUTPUT_UNPARSEABLE`.

### Failure modes (descriptive)

- **Invented I-labels where none existed.** In all 7 runs with invented
  references, the case exposes **no** Interpretations (L1, L3, L5, L6): 7 of
  those 12 runs. The model cites `I1`/`I2`, which matches the prompt's shape
  example (`"interpretations":["I1"]`). This is reported as policy pressure,
  **not** tuned (§ Next decision).
- **Section field loss.** In 4 runs a later section dropped `observations`
  and `interpretations`.
- **Interpretations echoed as objects.** In 3 runs, plus the unparseable one,
  Interpretations came back as objects pasting the prompt line (for example
  `{"I1 (steward-authored; on O5)": "…"}`). This includes all three L4
  revise runs, so **no revise proposal was admitted**.
- **Excluded evidence.** None was cited, and no ineligible record ID appeared.
  L6's bell entered outputs only from the request text.

### Semantic fidelity (the 4 admitted samples)

| Run | Intent | Supported claims | Uncertainty | Severe |
| --- | --- | --- | --- | --- |
| L1-s1 | 2 | 0/6 | flattened | S4 |
| L1-s2 | 2 | 0/2 | flattened | — |
| L2-s1 | 2 | 1/5 | flattened | S1 |
| L2-s2 | 1 | 1/3 | flattened | — |

- **L1-s1 (S4).** It states "The fact that by morning, both lamps are found
  unlit" and tags it `(O4)`; A:4 records only the empty harbor. Its inline
  labels `(O2)` and `(O6)` also point to records other than those its claims
  draw on. Governance cannot see inline labels.
- **L2-s1 (S1).** "no records have been entered" contradicts A:6, the ledger
  records the oil.
- **All four flatten an open matter**, for example "A second lamp was used
  intentionally to indicate…" and "There was an intentional omission…".

**Concealment.** Pooled reference precision is **1.0**, while the
supported-claim rate is **0.125** (2/16). Set-level citation accuracy says
almost nothing about whether claims are supported. The per-sample rule decides
it.

**Ungraded, descriptive only** (refused outputs are outside the rubric):
- all three L5 outputs adopt the unsupported premise and supply a cause
  ("an undisclosed emergency", "resource depletion");
- the L6 outputs assert bell facts or a connection.

Governance refused them for format and reference reasons, not for those
claims.

### What this shows

- **The governance layer works as designed.** It confines references and
  commits nothing. It caught every fabricated *reference*.
- **It does not judge semantics, and was not designed to.** Fabricated
  *content*, contradictions, flattened uncertainty and inline mis-citation
  pass governance whenever the JSON is well formed. On this evidence, steward
  review is the only safeguard for content. A competent generator would need
  to make that safeguard rarely necessary; this one makes it necessary on
  every admitted sample.
- **Generalization.** One small local model on six cases over a tiny corpus.
  This is diagnostic evidence about this model and policy, not about natural-
  language Blueprint proposal in general.

## Verification

- **Full suite** on a clean detached worktree of `871d1b5`: 2913 passed, 21
  skipped, 6 failed. The six failures are exactly the inherited Reader
  failures:
  - `test_reader_accessibility` ×2;
  - `test_reader_blueprint_workstation`;
  - `test_reader_record_view` ×2;
  - `test_reader_voice_profile`.

  `e7db9e4` had 2885 passed. The 28 extra passes are the 2 P8 boundary tests
  in `9484cc9` and the 26 live-protocol tests.
- **Datasets.** On the same worktree, every committed dataset reproduces
  exactly:
  - P8 governance corpus;
  - P8 live ceiling;
  - P8 live phi4-mini (aggregate from preserved outputs and grades);
  - P7 steward-authored, Layer 2 and Layer 1;
  - P6;
  - P5.

  The first P5 check used a wrong path (`research/synthetic_study`); rerun
  with `research/synthetic_study_lab/v1`, it matches.
- **Reader edits.** The owner's uncommitted Reader changes were never staged.

## Next decision (smallest)

Generation stays disabled; nothing in this result requires changing it. The
smallest owner decision is whether P8 closes as **governance complete with
generation not ready**, gated as it is now. That is the same disposition P7
reached.

Separately and optionally, the owner can authorize a frozen **policy v1.1**
experiment. It would address the observed shape-example copying (an empty-
list example when no Interpretations are exposed, and object echoes), and be
evaluated under these same thresholds. This would be new authorization, not
tuning of v1.

P9 has not been started.
