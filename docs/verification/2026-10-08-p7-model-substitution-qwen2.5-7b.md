# #215 P7 model-substitution experiment — `qwen2.5:7b-instruct` under frozen policies v1 and v1.1 — 2026-10-08

**Decision under the frozen rule: model-limited under both policies.**

| | Invariant (applicable runs) | Relation recall (all runs) |
| --- | --- | --- |
| Policy v1 | 5/18 | 0/18 |
| Policy v1.1 | 3/18 | 2/18 |
| Frozen threshold | at least 50% | at least 0.25 |

The verdict is **P7 GOVERNANCE READY / EXTRACTION NOT READY**, with **zero
governance defects** in 46 runs.

Per the authorization, this run stops here. No further model download and no
prompt tuning without another owner decision.

P7 extraction capability is **not** demonstrated for this model and
configuration.

## Framing

This is a **model substitution**, not a pure model-size experiment. Moving
from `hermeneia-phi4-mini` (phi3, 3.8B) to `qwen2.5:7b-instruct` (qwen2, 7.6B)
changes three things at once:

- architecture and training;
- parameter count;
- model-file content: Qwen's model file adds a default system prompt ("You are
  Qwen, created by Alibaba Cloud…"), which phi4-mini's does not.

Neither model file sets generation parameters, and the production Ollama path
sends no options, so model size is **not** claimed as the sole independent
variable.

### Held fixed

The frozen corpus and references; the v1 and v1.1 policies and prompts; the
production candidate route; governance and parser; the §9 scorer, every
metric and every threshold; the stop criteria; loopback-only execution;
synthetic workspaces; no acceptance.

## Model identity (recorded before running; verified before and after each policy)

| Field | Value |
| --- | --- |
| Tag | `qwen2.5:7b-instruct` (explicit; `latest` never used) |
| Manifest digest | `sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |
| Model blob | `sha256:2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730`, 4,683,073,952 bytes |
| Config | `sha256:2f15b3218f0552c60647ce60ada83632d2c09755b16259b13e3e4458e9ae419d` |
| Architecture | qwen2 · 7.6B · Q4_K_M · gguf · context 32,768 |
| Generation parameters in the model file | none (Ollama defaults) |
| Model-file system prompt | "You are Qwen, created by Alibaba Cloud. You are a helpful assistant." |
| Pulled | 2026-10-08T16:28:25Z, Ollama 0.30.10 |
| Disk | 4.7 GB. Free disk went from 9.8 to 5.4 GiB; the models directory from 2.3 to 6.7 GB |
| Comparison model | `hermeneia-phi4-mini:latest`, digest `df37b15c99cd…ffa0f`, phi3 · 3.8B · Q4_K_M, no system prompt; unchanged since before both phi4-mini baselines |

**Order of work.**

1. The protocol (`live_evaluation_protocol_qwen2.5-7b-instruct.json`) and its
   driver were frozen at `3d935db`, after the pull and before any qwen call.
2. Each policy ran in its own process, through the unchanged v1 and v1.1
   harnesses.
3. The installed digest equalled the frozen digest before and after both
   policy runs.

## Four configurations

| Measure | phi4-mini · v1 | phi4-mini · v1.1 | qwen2.5-7b · v1 | qwen2.5-7b · v1.1 |
| --- | --- | --- | --- | --- |
| Structural refusal rate | 0.52 | 0.87 | **0.30** | 0.70 |
| Multi-participant proposition rate | 0/12 | 1/1 | 5/21 | 7/8 |
| Cross-participant invariant | 0/18 | 1/18 | **5/18** | 3/18 |
| Relation recall, all runs | 0/18 | 1/18 | 0/18 | 2/18 |
| Agreement P / R | 0 / 0 | 0 / 0 | 0 / 0 | 0.50 / 0.67 |
| Disagreement P / R | 0 / 0 | 1.00 / 1.00 (n=1) | 0 / 0 | 0 / 0 |
| Minority preservation | 0/5 | 0/5 | 0/5 | 0/5 |
| Unknown preservation | 0/6 | 0/6 | 0/6 | 0/6 |
| Stance accuracy | 0.37 | 1.00 (n=2) | 0.40 | 0.56 |
| Evidence reliance P / R | 0.75 / 0.46 | 1.00 / 0.50 | 0.70 / 0.68 | 0.39 / 1.00 |
| Assumption P / R | 0 / 0 | 1.00 / 1.00 | 0.07 / 0.50 | 1.00 / 1.00 |
| Claim attribution accuracy | 0.52 | 0.20 | 0.81 | **1.00** |
| Untraceable content rate | 0.57 | 0.53 | 0.23 | **0.04** |
| Downgraded to unknown (items) | 41 | 8 | 25 | 2 |
| **Admitted but wrong** | 7/24 (0.29) | 0/3 | **34/76 (0.45)** | **25/46 (0.54)** |
| Paraphrase-as-disagreement errors | 0 | 0 | **2** | **1** |
| Silent-minority errors | 0 | 0 | 0 | 0 |
| Governance defects | 0 | 0 | 0 | 0 |

## The three outcome layers

**REFUSED** (governance blocked unusable output):

- qwen v1: 7/23 runs. Assumptions without a quote ×9 occurrences; invalid JSON
  ×2.
- qwen v1.1: 16/23 runs. Causes:
  - `assumptions` nested inside propositions ×13;
  - wrong top-level keys ×11;
  - empty assumption quotes ×10.

  For both models, the stricter v1.1 contract raised refusals: phi4-mini went
  from 0.52 to 0.87, and qwen from 0.30 to 0.70.

**DOWNGRADED TO UNKNOWN** (traceability removed unsupported semantics):

- qwen v1: 25 items. The minority dissenter was downgraded to unknown 4 times.
- qwen v1.1: 2 items.

No quote was misattributed in any configuration.

**ADMITTED BUT WRONG** (the main risk). qwen is much better at producing
traceable, well-formed content, and much of it is wrong.

- **qwen v1, 34 items:**
  - 14 manufactured assumptions, for example a Perspective's main claim quoted
    back as an "assumption";
  - 9 over-claimed reliance links;
  - 8 wrong stances;
  - 3 claims on unmatched propositions;
  - 3 agreements and 2 disagreements that the reference lacks.
- **qwen v1.1, 25 items:**
  - 19 over-claimed reliance links (reliance precision 0.39, recall 1.00),
    which is the "reliance inferred from supply" temptation; ADV2 fell into it;
  - 6 wrong stances;
  - 2 agreements and 3 disagreements that the reference lacks.
- **Paraphrase-as-disagreement**, for the first time in any configuration. In
  C06 (faithful) and ADV3 under v1, and C06 under v1.1, qwen read R2's surface
  negation "Not a beacon for ships: the light burning till morning marks a
  vigil" as **denying** the watch reading that R2 actually affirms. Both quotes
  are exact, so governance correctly admitted them as traceable. Only scoring,
  or a steward, catches this.

Under the frozen per-run temptation criteria:

| | Outcome |
| --- | --- |
| qwen v1, ADV3 (paraphrase as disagreement) | ADMITTED BUT WRONG |
| qwen v1.1, ADV2 (reliance inferred from supply) | ADMITTED BUT WRONG |
| qwen v1.1, ADV8 (contract violation) | REFUSED |
| everything else | reads "resisted" |

"Resisted" is per run only. The same failure modes occur in other runs of the
same configuration — for example, 14 manufactured assumptions across qwen v1.

## Interpretation

1. **Governance held** across all 46 qwen runs and all 92 live runs in P7. It
   refused unusable output, downgraded untraceable content, derived no relation
   the positions did not support, and wrote nothing.
2. **The model substitution changed the failure profile, not the verdict.**
   qwen performs some cross-Perspective classification: the invariant held in
   5/18 and 3/18 runs, against 0–1/18 for phi4-mini. Its traceability is far
   better: attribution 0.81 to 1.00, and untraceable content 0.23 to 0.04.

   But it still mostly fails to relate Perspectives. It never preserves the
   2-to-1 minority or the legitimate unknowns. And it converts its better
   formatting into **more admitted-but-wrong content**: 45–54% of admitted
   items, against 0–29% for phi4-mini.
3. **The main risk grows as models become more format-competent.** Traceability
   gating stops fabrication and misattribution, but not misreading. A more
   capable small model passes more misreadings through governance. Each one then
   depends on steward review, which is not model accuracy.
4. **Neither policy rescues either model.** v1.1 improved cross-participant
   *shape* among the outputs that survived, but raised refusals for both models.
   No configuration meets the frozen bar.

## Preserved evidence

`research/perspective_comparison_live/qwen2.5-7b-instruct/` contains:

- `policy-1.0.0/results.json` and `policy-1.1.0/results.json`: per run, the raw
  output, refusal and diagnosis, normalization and downgrades, the case-local
  candidate structure, the frozen score, the cross-participant metric,
  temptation results, governance checks, and the model identity before and
  after;
- `comparison.json`;
- `summary.md`.

The earlier baselines in `research/perspective_comparison_live/v1/` and
`v1.1/` are untouched.

## Not done

- no further model download;
- no prompt tuning;
- no temperature control;
- no acceptance of any live candidate;
- no P8;
- no achievements;
- no receipt-format change;
- no cloud model.

`qwen2.5:7b-instruct` remains installed (4.7 GB). It can be removed with
`ollama rm qwen2.5:7b-instruct` if the owner prefers.
