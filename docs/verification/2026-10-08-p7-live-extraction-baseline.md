# #215 P7 live semantic-extraction baseline — `hermeneia-phi4-mini:latest` — 2026-10-08

**Verdict (computed under the frozen protocol): P7 GOVERNANCE READY / EXTRACTION NOT READY.**

- **Governance: ready.** Across 23 live runs, zero governance defects. Every
  model output, however malformed, was either refused with a reproducible
  code or admitted only after tracing to exact text. Nothing reached study
  history.
- **Extraction: not ready.** This model, on the production path, did not
  perform comparison at all. It never placed two Perspectives in one
  proposition, so it established no agreement and no disagreement.

This run is preserved as the baseline. Nothing was tuned.

## Authorization and controls

- **Authorization.** Owner-authorized, one bounded run. Model
  `hermeneia-phi4-mini:latest` (local Ollama), called through the production
  `POST /api/perspective/comparison/candidates` route with the default
  provider registry.
- **Isolation.** Each run used a disposable synthetic workspace materialized
  from the frozen corpus under the P5 isolation. Only the extraction request
  left that isolation, and only to loopback: every non-loopback connection
  raised.
- **No credentials, no host config.** No credential store was used,
  `OLLAMA_HOST` was unset, and the connection settings were fresh.
- **Nothing accepted.** No accept, edit or discard call was made. For every
  run, the workspace logical digest was unchanged and
  `accepted_perspective_comparisons` was empty.
- **Frozen first.** The protocol was frozen before any live call, at `0b49abb`
  (`tests/fixtures/perspective_comparison/v1/live_evaluation_protocol.json`).
  It fixes the metrics, the three outcome classes, the temptation criteria,
  the governance checks and the verdict thresholds. The section 9 scorer, the
  corpus, the prompt and the rules were unchanged.
- **Dry-run proof.** The harness was first dry-run on scripted outputs with
  fakes only. Every scripted temptation was classified as designed. The
  scripted ceiling under the same metrics is perfect.
- **Sampling.** The production Ollama path sends no generation options, and
  the model file sets none, so Ollama's defaults applied. **Temperature 0 is
  not supported by the production path.** Setting it would have changed
  production behavior, so it was not done.
- **Runs.** 23 live runs in total: the 13 faithful cases, plus the 10
  adversarial cases, each run on its frozen base case. The adversarial cases
  send the identical base-case prompt to the model; their scripted outputs
  are not used. N1 and N2 are refused before any model call, so they were not
  run.

## Results against the scripted ceiling

| Measure | Live | Scripted ceiling |
| --- | --- | --- |
| Structural refusal rate | 0.52 (12/23: 7 unparseable, 5 contract violations) | 0.00 |
| Claim attribution accuracy | 0.52 (0 misattributions) | 1.00 |
| Stance accuracy | 0.37 | 1.00 |
| Agreement | P 0.00 / R 0.00 (0 tp, 0 fp, 4 fn) | 1.00 / 1.00 |
| Disagreement | P 0.00 / R 0.00 (0 tp, 0 fp, 6 fn) | 1.00 / 1.00 |
| Evidence reliance | P 0.75 / R 0.46 | 1.00 / 1.00 |
| Assumptions | P 0.00 / R 0.00 (2 fn) | 1.00 / 1.00 |
| Minority preservation | 0/5 runs (2 downgraded, 1 lost, 2 refused) | 1/1 |
| Unknown preservation | 0/6 runs | 2/2 |
| Untraceable content rate | 0.57 | 0.00 |
| Paraphrase-as-disagreement errors | 0 (vacuous, see below) | 0 |
| Silent-minority errors | 0 (vacuous, see below) | 0 |
| Admitted but wrong | 7/24 admitted items = 0.29 | 0/70 |

Of the eight frozen READY conditions, six fail:

- refusal rate;
- attribution accuracy;
- stance accuracy;
- agreement and disagreement precision and recall;
- the admitted-but-wrong rate.

The paraphrase and silent-minority conditions pass only vacuously.

## Bad model content by outcome

- **REFUSED (12 runs).** Exact causes:
  - **invalid JSON** in 7 runs:
    - trailing comma ×1;
    - unquoted tokens, such as `asserts`, `does_not_address` or `[U1]` ×3;
    - missing delimiter or bracket ×2;
    - an unterminated code fence ×1.
  - **Runaway outputs.** Five of those seven were 9,400–15,500 characters
    long, with 36–50 propositions emitted for 2–3 Perspectives.
  - **Contract violations** in 5 runs: positions missing the required
    `relies_on` ×4, and an assumption without a quote ×1.
- **DOWNGRADED TO UNKNOWN (41 items).**
  - 30 positions were left unclassified by the model.
  - 11 quoted positions could not be traced: 5 missing quotes, 5 empty
    quotes, and 1 altered quote ("harbor" became "harbour").

  No quote was attributed to the wrong participant.
- **ADMITTED BUT WRONG (7 of 24 admitted items).** This is the key quality
  risk.
  - **4 unmatched claims.** The model split one shared claim into one
    proposition per participant. That is the converse of the contract's rule
    that paraphrases of one claim are one proposition.
  - **1 stance error and 2 reliance false positives.** These sit on
    whole-sentence quotes. Some of these items arise where the model's
    per-participant granularity meets the frozen greedy matching. They were
    not rescored.

  None of these 7 items was caught by governance, because each is traceable.
  A steward would have to notice them.

## The finding that matters

**Across all 12 candidate propositions, the model classified at most one
participant per proposition.** Every other participant was left unclassified,
and is therefore `unknown`.

The model restated each Perspective in isolation instead of comparing them.
So:

- agreement and disagreement recall is 0;
- the 2-to-1 minority was never represented;
- the zero paraphrase-as-disagreement and zero silent-minority errors reflect
  the **absence of comparison**, not resistance to those errors.

### Temptations

Under the frozen criteria, every adversarial temptation reads `resisted`.
This should not be read as robustness:

- 6 of the 10 adversarial runs were refused, so there was no candidate to
  assess;
- in the 4 assessed runs, the model never related participants;
- the model never produced an authority field, but its malformed outputs were
  refused for other reasons.

### Run-to-run variability

Identical prompts produced different outputs every time. C01's prompt, sent 4
times, gave 4 distinct outputs: 2 candidates, 1 contract violation and 1
unparseable output. C08's prompt gave 5 distinct outputs. With default
sampling, any single run is unrepresentative.

## Governance verdict: no defect

Every live run passed every frozen governance check:

- each refusal is reproduced by re-parsing the preserved output;
- each candidate validates strictly against the receipt-derived view;
- re-normalizing each raw output reproduces its candidate exactly;
- each candidate ID recomputes;
- the prompt is deterministic (identical for every candidate on the same base
  case);
- no authority keys appear anywhere;
- the workspace is unchanged;
- nothing was accepted.

The deterministic machinery behaved exactly as designed on real, messy model
output. It refused what it couldn't parse, downgraded what it couldn't trace,
and derived no relation the positions did not support.

## What this is not

- **Not a model ranking.** This is one small local model on default sampling,
  with one sample per case.
- **Not a prompt or contract verdict.** Nothing was tuned or relaxed. For
  example, missing `relies_on` keys refused 4 runs under the strict contract,
  as designed.
- **Not model accuracy.** The steward-review safety net is not counted.

## Baseline preserved

`research/perspective_comparison_live/v1/` contains:

- `results.json`: per run, the raw output, refusal or parse result,
  normalization and downgrades, the final case-local candidate structure, the
  frozen score, error counts, temptation results and governance checks;
- `diagnostics.json`: the exact refusal causes, variability, and comparison
  shape;
- `scripted_ceiling.json`;
- `summary.md`.

The descriptive categories come from
`tests/perspective_comparison_live_report.py`. It recomputes no score and
changes no verdict.

## Options for a later, separately authorized packet (none taken)

1. **Production temperature control**, a production change, plus repeated
   samples per case.
2. **A larger or different local model.**
3. **A new, explicitly versioned extraction prompt** — for example, first
   enumerating shared claims, then classifying every participant. This would
   be a new frozen version, evaluated against this baseline.
4. **A governed contract revision**, for example deciding whether a missing
   `relies_on` means "none". This is a steward decision, not a tuning tweak.
5. **Option (c)**: structured, cited Perspective output at run time.

P8 has not been started.
