# #215 P7 semantic extraction v1.1 experiment — `hermeneia-phi4-mini:latest` — 2026-10-08

**Decision under the frozen rule: model-limited.**

- The cross-participant invariant held in **1 of 18** applicable runs. The
  threshold was at least 50%.
- Relation recall across all runs was **1 of 18**. The threshold was at least
  0.25.

The verdict under the frozen thresholds is **P7 GOVERNANCE READY / EXTRACTION
NOT READY**. There were **zero governance defects** in 23 runs.

Per the frozen stop rule, prompt tuning stops here. The v1 baseline
(`92475b1`) is unchanged and preserved.

## What was held constant, and what changed

| | |
| --- | --- |
| **Held constant** | The model; the production candidate route; default Ollama sampling, with no temperature control; loopback only; the frozen corpus and references; the §9 scorer and every v1 metric and threshold; the 23-run plan. Nothing was accepted |
| **Changed** | Only the extraction policy |

**Order of work.**

1. The policy was frozen at `d5a8a16`, before any implementation or v1.1 call:
   - the design note;
   - the exact prompt and wire fixture;
   - the protocol, with the decision rule fixed in advance;
   - the candidate-schema definition.
2. The implementation followed at `a79d62d`:
   - v1 stays the unchanged default, and its prompts are byte-identical;
   - v1.1 is opt-in, and its candidates can never be accepted;
   - a test pins the prompt constants to the fixture.
3. The scripted v1.1 ceiling, through the same route with fakes, was perfect:
   invariant 9/9, relation recall 9/9, no defects.

## v1 → v1.1

| Measure | v1 baseline | v1.1 | v1.1 scripted ceiling |
| --- | --- | --- | --- |
| Structural refusal rate | 0.52 (12/23) | **0.87 (20/23)** | 0.00 |
| Multi-participant proposition rate | 0/12 | 1/1 | 10/19 |
| Cross-participant invariant (applicable runs) | 0/18 | **1/18** | 9/9 |
| Agreement recall | 0.00 | 0.00 | 1.00 |
| Disagreement recall | 0.00 | 1.00 (1 tp, on C03) | 1.00 |
| Relation recall, all runs | 0/18 | **1/18** | 9/9 |
| Minority preservation | 0/5 | 0/5 | 1/1 |
| Stance accuracy | 0.37 | 1.00 (2/2) | 1.00 |
| Evidence reliance P / R | 0.75 / 0.46 | 1.00 / 0.50 | 1.00 / 1.00 |
| Assumption recall | 0.00 | 1.00 | 1.00 |
| Unknown preservation | 0/6 | 0/6 | 2/2 |
| Admitted but wrong | 7/24 | 0/3 | 0/70 |
| Untraceable content rate | 0.57 | 0.53 | 0.00 |

**The improved per-item figures are not evidence of quality.** Stance 1.00,
admitted-but-wrong 0/3, reliance precision 1.00 and assumption recall all rest
on the **3 candidates** that survived refusal. Together those hold 3 admitted
items, and only one of them (C03) contains a real comparison. The refusal
rate rose from 52% to 87%.

## What happened

### One genuine cross-Perspective comparison

C03 is the only success:

- P1 `supports` and P2 `opposes`, both with exact quotes;
- a disagreement was derived from those positions;
- stance 2/2.

This shows the pipeline end to end on real model output. One success in 18
applicable runs is not a capability.

### Same failure, new shape

The model now often lists **every** participant in each proposition. But it
gives a quoted stance to only one of them. The others are marked `silent`, or
`mixed` without a quote.

C01 shows this clearly. P1 supports p2 while P2 is silent, and P2 supports p1
while P1 is silent. That is still one proposition per Perspective, now dressed
as a cross-participant classification. The invariant was designed to catch
exactly this, and it did.

### Format adherence fell under the stricter contract

Refusals came from these causes, counted across the 20 refused outputs:

- **Placeholder assumptions with empty quotes:** ×13.
- **Required fields dropped when they would be empty or null:** `relies_on`
  ×11 and `quote` ×7, despite "never omit a field".
- **Bad participant labels:** `participant: "unknown"` ×7.
- **Bad classification values:** an empty classification ×3, and the typo
  `oposes` ×2.
- **Invalid JSON:** ×3 (trailing commas).

### Near-miss quotes

38 of 72 non-null quotes (53%) were wrapped in literal quotation marks
(`"\"The lamp…\""`). These are near misses, and the exact-span rule correctly
treats them as untraceable. Nothing was relaxed.

### Other effects

- **Runaway outputs are gone.** The longest output was 1,725 characters,
  against 15,462 under v1. The 2 × participants bound was never exceeded.
- **The no-fences instruction was ignored** in 19 of 23 outputs. The parser
  tolerates one fenced block, exactly as in v1.
- **No example copying.** The illustrative example content was never copied.

## Interpretation

v1.1 changed the shape of the output but not the capability. At this size
(3.8B parameters, Q4_K_M), the model:

- does not reliably construct propositions across Perspectives;
- loses format adherence as the contract becomes more explicit.

That is a model-capability limit under the frozen rule, not a governance
failure. The governance layer handled every malformed or near-miss output
exactly as designed.

## Larger local models

| | |
| --- | --- |
| **Installed** | Only `hermeneia-phi4-mini:latest`: phi3 architecture, 3.8B parameters, Q4_K_M, 2.5 GB. No larger local model is installed |
| **Machine** | Apple M4, 16 GB RAM, about 11 GB free disk |
| **Fits comfortably** | A 7–8B instruction-tuned model at about Q4 (roughly 4.5–5 GB) |
| **Tight** | A 14B model (roughly 9 GB), on both disk and memory |

Any larger model would first have to be pulled. That is a download, and it
requires separate owner authorization. This note does not install or choose a
model.

The recommended next experiment is one separately authorized run. It would
use a 7–8B local model on the same frozen corpus, the same production route,
and the same frozen v1 and v1.1 policies, with no prompt changes. That
isolates model size, which is the variable this experiment left open.

## Tests

- P7 tests: 24 passed. That is 20 existing and 4 new v1.1 tests: the frozen
  prompt constants, canonical equivalence with v1, the bound and
  explicit-unknown rules, and that v1.1 candidates are never acceptable.
- Full suite on a clean worktree of `a79d62d`: 2873 passed, 21 skipped, 6
  failed. The six failures are exactly the inherited Reader failures. The
  extra passes are the 4 new v1.1 tests. The P5, P6, P7 Layer 1 and P7 Layer
  2 (v1) datasets all reproduce exactly.

## Preserved evidence

`research/perspective_comparison_live/v1.1/` contains:

- `results.json`: per run, the raw output, refusal or parse result,
  downgrades, candidate structure, frozen score, cross-participant metric and
  governance checks;
- `diagnostics.json`;
- `scripted_ceiling.json`;
- `summary.md`.

The v1 baseline in `research/perspective_comparison_live/v1/` is untouched.

## Not done

- no further prompt tuning;
- no temperature control;
- no larger-model run;
- no acceptance of any live candidate;
- no P8;
- no achievements;
- no receipt-format change;
- no structured Perspective output at run time;
- no cloud model.
