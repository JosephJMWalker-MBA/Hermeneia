# P7 semantic extraction policy v1.1 — experimental

Date: 2026-10-08. This policy was frozen before any v1.1 call, on
`p7-perspective-comparison` at `92475b1`, the immutable v1 live baseline.
It is part of [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215)
P7 Layer 2. It is owner-authorized as one bounded experiment.

## Purpose

The v1 baseline (`docs/verification/2026-10-08-p7-live-extraction-baseline.md`)
demonstrated one failure: the model restated each Perspective on its own and
never built a proposition across Perspectives. In 0 of 12 propositions did it
classify two participants.

Policy v1.1 tests whether an output contract that requires comparison changes
that. Model size is held constant: v1.1 runs first on the same
`hermeneia-phi4-mini:latest`, through the same production path, with the same
sampling.

## What changes

The exact prompt lines and wire contract are frozen in
`tests/fixtures/perspective_comparison/v1/extraction_policy_v1.1.json`. A test
requires the production constants to equal it.

### Required reasoning order

The prompt requires this order:

1. find the claims that are comparable across the Perspectives, as neutral
   propositions about the passage;
2. classify **every** participant for each proposition;
3. attach exact spans;
4. only then set reliance;
5. only then list stated assumptions.

Leave a classification unknown rather than invent support. Never write one
proposition per Perspective by restating each response.

### Wire format

The wire format is `hermeneia.perspective-comparison-extraction-output/v1.1`.

- `classifications` replaces `positions`, and `classification` replaces
  `stance`.
- The allowed values and their canonical stances are:

  | v1.1 value | Canonical stance |
  | --- | --- |
  | `supports` | `asserts` |
  | `opposes` | `denies` |
  | `mixed` | `unclassifiable` |
  | `silent` | `does_not_address` |
  | `unknown` | `unknown` |

### Easier JSON, same governance

The prompt adds:

- one compact example, illustrative and not about the corpus;
- the exact enum values;
- a prohibition on markdown and code fences;
- "every field, `[]` rather than omission";
- `relies_on: []` means no reliance established;
- a proposition bound of 2 × participants.

The parser **enforces** the bound: exceeding it is
`EXTRACTION_OUTPUT_CONTRACT_VIOLATION`, which also guards against v1's
runaway outputs.

## What does not change

- The traceability rules, the derived relations, the canonical structure type
  and the refusal codes.
- The fence tolerance in the parser.
- Policy v1 (`1.0.0`, prompt `perspective-comparison-extraction/v1`). It stays
  the default, unchanged, and its datasets and live baseline are untouched.
- Historical receipts and the receipt format.
- The frozen references, the §9 scorer and every v1 metric.

The only change to normalization is that an explicit `unknown` with no quote
and no reliance becomes a canonical `unknown` without an untraceable entry.
v1 output can never contain `unknown`, so v1 replay is unaffected. An
`unknown` or `silent` classification that carries a quote or reliance is
still a `contradictory_position`.

## Experimental status

- A candidate records `extraction.policy_version: "1.1.0"` and `prompt_version:
  "perspective-comparison-extraction/v1.1"`.
- Candidates under 1.1.0 can be **discarded but never accepted**. Accept and
  edit-and-accept both answer 409 `POLICY_NOT_ACCEPTABLE`. The accepted-record
  schema and validator still admit only policy 1.0.0, so no v1.1 output can
  enter study history.
- The request opts in with `"policy_version": "1.1.0"`. Without that field,
  policy 1.0.0 applies.

## Evaluation

The protocol is frozen in
`tests/fixtures/perspective_comparison/v1/live_evaluation_protocol_v1.1.json`.
It runs the same 23 runs as v1 and uses the same metrics, outcome classes,
governance checks and verdict thresholds. It adds one metric: the
cross-participant proposition rate, and its invariant. Whenever the frozen
reference contains a cross-Perspective relation, at least one proposition must
classify two or more participants with spans. Failing that invariant is an
extraction-quality failure, not a governance failure.

**Decision rule, fixed in advance.** A material change requires both:

- the invariant holds in at least 50% of applicable runs;
- relation recall is at least 0.25.

If so, the result is preserved and the remaining errors are assessed for
whether governance can handle them. Otherwise the run stops: the capability is
reported as model-limited at this size, and installed larger local models are
identified for one separately authorized run. There is no further prompt
tuning.
