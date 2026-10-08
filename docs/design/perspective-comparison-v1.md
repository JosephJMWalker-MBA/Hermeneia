# Structured Perspective Comparison v1 — P7 contract

Date: 2026-10-07. This contract was frozen before the comparator was
implemented, on `main` `13b1d7a` (P6 merged via PR #248). It implements the
deterministic part of P7 of
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215) under the
steward boundaries in
[#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214).

P7 answers one question:

> Where do retained Perspectives agree, disagree, rely on different evidence,
> make different assumptions, or leave questions unresolved?

It does not decide which Perspective is correct. A comparison is not a
synthesis, an answer, an adjudication or study history.

## Authorities reused, not redefined

- **[P3 receipt](perspective-execution-receipt-v1.md)** owns what a retained
  execution is: its exact frame, question, Scope, prompt, execution and
  response.
- **[P4 rules](perspective-achievement-rules-v1.md)** own eligibility:
  - the shared execution-validity predicate E(r) (§3);
  - the exact question equality `same_question` (§5);
  - the derived family key and methodology fields M(r) (§6);
  - the deterministic order K(r) (§8);
  - the coverage states (§7).
- **`read_perspective_achievement_evidence(conn)`** is the read-only adapter
  that applies those rules to one snapshot.
- **[Study Lineage](study-lineage-v1.md)** owns exclusion and the typed record
  of each receipt.

The comparator reads only that adapter's output. It never reads SQL, never
re-validates or re-derives eligibility, and never resolves Scope again.

## What can be established deterministically

The decisive finding of this contract comes from the P3 template
`perspective-run/v1`. It asks the model to "Return a concise proposed
reading", so **a retained response is free prose**. It carries:

- no structured claims;
- no stance markers;
- no citations of extractions or highlights.

Every receipt-level fact is exact and typed. Every claim-level fact would have
to be read out of prose.

| Required representation | v1 status | Basis |
| --- | --- | --- |
| Comparison identity and version | deterministic | `comparison_id` digests the policy and the sorted participant receipt IDs |
| Exact participating receipt IDs | deterministic | P4 eligible executions |
| Question binding | deterministic | P4 exact `same_question`; a mismatch refuses |
| Governing question binding | **not bound** | P3 Scope always excludes the governing question |
| Scope binding | deterministic, per participant | exact `scope_sha256` and the typed evidence supplied |
| Participant and model provenance | deterministic | receipt frame, family, execution, digests, retention, Lineage record |
| Evidence supplied to each Perspective | deterministic | typed Scope references |
| Evidence overlap and divergence | deterministic, over supplied evidence | set relations over typed units |
| Provenance back to exact text and evidence | deterministic | exact response text and digest; typed references |
| Explicit unknowns | deterministic | the `semantic` block and uncertainty codes |
| Comparison-policy version | deterministic | `policy_version` |
| Claims or propositions | **not established** | requires semantic extraction from prose |
| Agreement | **not established** | requires claims |
| Substantive disagreement | **not established** | requires claims |
| Evidence a response relied on | **not established** | supplied is not relied on; the prose carries no citations |
| Assumptions | **not established** | requires reading the prose; never invented |
| Unresolved disagreement | **not established** | requires disagreement |

### The boundary

Semantic claim extraction requires one of two things:

- **a model proposal**, which under #214 is a proposal only and cannot
  silently become canonical; or
- **a human-authored claim structure**, which is new governed state.

Either needs a candidate-and-acceptance pathway that does not exist. The
existing P3 template cannot be changed to request structured output: E(r)
freezes its implementation digest, and receipts must not change. Heuristic
text processing is excluded from the governed comparison layer, including:

- keyword or negation matching;
- sentence splitting into claims;
- similarity scores;
- embeddings.

v1 therefore stops at this boundary. Every claim-level field is reported as
`not_established` with reason `SEMANTIC_EXTRACTION_REQUIRED`.

## Persistence decision

**v1 is a deterministic, read-only projection. No canonical record is
created.**

- Receipts are append-only and immutable, so the deterministic comparison can
  be recomputed exactly from them. No concrete v1 claim needs durable state.
- `comparison_id` names the inputs. It is not a stored record.
- Nothing is cached or logged as history.

A future durable comparison is the one the #215 awards need: an "accepted
structured comparison". It would need a separate, reviewed contract before any
storage code. That contract must define:

- **owner:** a steward comparison-acceptance record, distinct from the receipts
  it cites;
- **identity:** a digest over the participant receipt IDs, the accepted claim
  structure and the policy version;
- **provenance:**
  - the structure's origin (a model proposal with full run lineage, or
    steward-authored);
  - the exact candidate accepted;
  - the actor and time of acceptance;
- **Lineage:** a typed record, with authorship separating the proposer from the
  accepting steward;
- **WBS:** a declared capability and component; older restorers refuse it;
- **acceptance semantics:**
  - accept or edit-and-accept tied to the exact candidate;
  - acceptance records which structure the steward kept, not which Perspective
    is right;
  - adjudication remains a separate, explicit record.

P7 v1 implements none of this.

## Admissible comparison

`compare_retained_perspectives(evidence, receipt_ids)` receives:

- the adapter's `PerspectiveAchievementEvidence` for one snapshot;
- the requested receipt IDs, in any order.

It refuses with `ComparisonRefused(code)`, checking in this order:

| Code | Condition |
| --- | --- |
| `DUPLICATE_PARTICIPANT` | a receipt ID is requested twice |
| `TOO_FEW_PARTICIPANTS` | fewer than 2 receipt IDs |
| `TOO_MANY_PARTICIPANTS` | more than 8 receipt IDs |
| `COVERAGE_UNSUPPORTED` | the evidence source state is not `supported` (for example, no receipt table) |
| `INELIGIBLE_RECEIPT` | a requested ID is not an eligible execution in the snapshot |
| `QUESTION_MISMATCH` | participants do not share exact question bytes (P4 `same_question`) |

`INELIGIBLE_RECEIPT` deliberately does not distinguish a receipt that is
missing, transient, discarded, excluded, unsupported or invalid. An excluded
receipt's text therefore never leaks through a refusal. Transient and
discarded runs have no receipt, so they can never participate.

Participants need not share a Scope, a document, a family or a model. Those
differences are what the comparison reports.

## Output — `hermeneia.perspective-comparison/v1`

The machine-readable schema is
`tests/fixtures/perspective_comparison/v1/comparison.schema.json`.

| Field | Content |
| --- | --- |
| `schema`, `policy_version` | `hermeneia.perspective-comparison/v1`, `1.0.0` |
| `comparison_id` | `perspective-comparison:sha256:<hex>` over canonical `{schema, policy_version, receipt_ids (sorted)}` |
| `inputs` | evidence source, receipt schema, eligibility authority, and the sorted requested receipt IDs |
| `coverage` | the adapter's coverage, copied unchanged |
| `question` | `{text, sha256, binding: "exact_execution_question", governing_question: "not_bound"}` |
| `participants` | one entry per receipt, ordered by P4 K(r) (`retained_at` as a UTC instant, then receipt ID) |
| `evidence` | supplied-evidence units, `shared_by_all`, `supplied_only_to`, `overall` |
| `relations` | one entry per participant pair, in participant order |
| `semantic` | `not_established` in v1 |
| `uncertainty` | qualifications, each with `code` and `statement` |
| `not_synthesis` | a fixed statement (below) |

### Participant

Each participant carries:

- `receipt_id`, `run_id`, `lineage_record` and `authorship: "model"`;
- `retention`: decision, actor, unknown actor identity, original `retained_at`;
- `executed`: `created_at` and `completed_at`;
- `perspective`:
  - `origin`, `id`, `version`, `label`;
  - `definition_fingerprint`;
  - `methodology_sha256`: the SHA-256 of P4 M(r) canonical bytes;
  - `family`: the adapter's state and key;
- `execution`: the exact recorded object;
- `digests`: question, Scope, prompt and response;
- `response`: the exact text, never trimmed or summarized;
- `evidence_supplied`:
  - the source document ID and file hash;
  - `focus`: primary-selection extraction IDs, in order;
  - `focus_locator`;
  - `context`: current-page extraction IDs, empty if not included;
  - `highlights`: `{id, page, captured_sha256}` per included highlight.
    The digest covers the captured `{text, page, locator, relevance, status}`
    snapshot.

### Evidence (supplied, not relied on)

A **unit** is a typed durable reference: either
`{table: "source_extractions", key: {id}}` or
`{table: "reader_highlights", key: {id}}`.

- Each unit lists the participants it was supplied to, with their roles
  (`focus`, `context`, `highlight`).
- A highlight also records each participant's `captured_sha256`, and
  `captured_snapshot_varies` when those differ.
- A highlight and an extraction over the same text are **different units**. No
  equivalence is inferred, because that would itself be interpretation.

Set relations use the units supplied to each participant:

- **identical:** all sets are equal;
- **disjoint:** the sets are pairwise disjoint;
- **overlapping:** otherwise.

`shared_by_all` and `supplied_only_to` are exact set operations, sorted by
table and then ID.

### Relations (per pair)

| Field | Values |
| --- | --- |
| `perspective` | `same_family` · `distinct_family_distinct_methodology` · `distinct_family_same_methodology` · `family_unsupported` |
| `execution` | `same_provider_model` · `different_provider_model` (by `provider_id`, `model_id`) |
| `response_text` | `identical` · `different` (exact bytes; a textual fact only) |
| `evidence_units` | `identical` · `overlapping` · `disjoint` |
| `evidence_focus` | `identical` · `overlapping` · `disjoint` (primary-selection extractions) |
| `same_source_document` | boolean |

`distinct_family_distinct_methodology` is P4's `distinct_perspective` (§6). A
model difference never makes Perspectives distinct.

### Semantic

```json
{"status": "not_established", "reason_code": "SEMANTIC_EXTRACTION_REQUIRED",
 "fields": ["claims", "agreement", "disagreement", "evidence_reliance", "assumptions", "unresolved"],
 "statement": "Retained Perspective responses are free prose under perspective-run/v1. Claims, agreement, disagreement, the evidence a response relied on, assumptions and unresolved disagreement cannot be established from receipt structure without semantic extraction, which this deterministic policy does not perform."}
```

The schema also defines the **populated form** a governed claim structure
would take. v1 never emits it. Only the evaluation reference annotations use
it, with origin kind `evaluation_reference`. Any other origin requires a
reviewed contract revision.

In the populated form:

- **Propositions:** each has an `id` and a neutral `statement`, and exactly one
  position per participant.
- **Stance:** `asserts`, `denies`, `does_not_address` or `unclassifiable`.
- **Quotes:**
  - `asserts` and `denies` require a quote: `{start, end, text}`, where `text`
    equals `response[start:end]` exactly;
  - `does_not_address` has none;
  - `unclassifiable` may have one.
- **Cited evidence:** must be a subset of that participant's supplied units. An
  empty list means "no cited evidence"; it is never "false".
- **Agreement:** two or more participants share `asserts`, or share `denies`,
  and no participant holds the opposite stance.
- **Disagreement:** at least one participant asserts and at least one denies.
  - Groups are listed by stance.
  - `smaller_groups` lists the participants in every group strictly smaller
    than the largest. This is a visible minority, never a loser.
  - There is no winner, majority, consensus or truth field.
- **Evidence relation:** each agreement and disagreement carries one, over the
  cited sets of its participants: `identical`, `overlapping`, `disjoint` or
  `some_uncited`.
- **Unresolved:** every disagreement, because no adjudication exists. Each has
  `resolution: "none_recorded"`.
- **Unclassifiable:** every `unclassifiable` position.
- **Assumptions:** only assumptions that are explicitly quoted. They are never
  derived.

### Uncertainty codes

| Code | When | Statement |
| --- | --- | --- |
| `GOVERNING_QUESTION_NOT_BOUND` | always | Perspective Scope excludes the workspace governing question; this comparison binds only the exact execution question. |
| `SUPPLIED_NOT_RELIED_ON` | always | Supplied evidence is what each Perspective was given, not proof that its response relied on it. |
| `EXECUTION_SETTINGS_UNDISCLOSED` | always | Undisclosed model revision, seed, temperature and runtime defaults remain unknown. |
| `NO_ADJUDICATION` | always | No user adjudication is recorded. Retention is not agreement, and this comparison does not decide which Perspective is correct. |
| `MODEL_DIFFERENCE_NOT_PERSPECTIVE` | any pair is `same_family` | Participants that share a Perspective family differ only in execution; a model difference does not make a distinct Perspective. |
| `IDENTICAL_TEXT_NOT_AGREEMENT` | any pair has `identical` response text | Identical response text is a textual fact, not recorded agreement. |
| `FAMILY_UNSUPPORTED` | any participant family state is not `supported` | Perspective family ancestry for some participants cannot be established. |
| `HIGHLIGHT_SNAPSHOT_VARIES` | any highlight has `captured_snapshot_varies` | A Reader highlight was captured with different metadata in different runs; each participant keeps its own captured snapshot. |
| `RECEIPTS_NOT_ELIGIBLE` | the adapter's classified excluded + unsupported + invalid count is nonzero | Some retained receipts in this workspace are not eligible (for example, excluded from analysis) and do not inform this comparison. |

Codes are emitted in this table's order.

### Not-synthesis statement

> This comparison is a read-only projection over retained Perspective
> receipts. It is not a synthesis and not study history. It does not decide
> which Perspective is correct, and no agreement, majority or model consensus
> becomes truth or user agreement.

## Invariants (tested)

1. **Comparison is not synthesis.** The output holds only copied receipt facts,
   set relations and fixed statements. No generated text and no answer field.
2. **Agreement does not become truth.** No field records truth, correctness or
   a best reading.
3. **Majority does not become authority.** No majority, winner or consensus
   field; every participant stays listed.
4. **Model consensus does not become user agreement.** Identical model text is
   only `response_text: identical`. `NO_ADJUDICATION` is always present.
5. **Distinct wording alone is not substantive disagreement.** The
   deterministic layer never classifies wording. Different text is only
   `different`.
6. **Similar wording alone is not agreement.** The same holds for similar text.
7. **Evidence differences stay separate from conclusion differences.**
   Evidence relations are computed from Scope only and appear apart from
   `semantic`.
8. **Unsupported assumptions are never invented.** The deterministic layer
   emits none. Reference assumptions require exact quotes.
9. **Minority positions remain visible.** Every participant is preserved; in
   the populated form, `smaller_groups` names minorities.
10. **No user adjudication is inferred.** No adjudication field exists. In the
    populated form, `resolution` is always `none_recorded`.

The comparator also:

- is deterministic;
- is invariant to the order of requested IDs, storage order and model identity
  (for the substantive sections);
- calls no provider;
- persists nothing;
- adds no telemetry;
- changes no P3 or P4 receipt, rule or award.

## Read-only API

`GET /api/perspective/comparison?receipt_id=<id>&receipt_id=<id>…` follows the
guide route's discipline:

- a read-only snapshot with `PRAGMA query_only`;
- `Cache-Control: no-store`;
- no store initialization when the workspace is missing;
- any other query parameter refuses with 400.

It returns the comparison on success. Refusals return `{error, code}`:

- **400:** shape, count and duplicate refusals;
- **409:** coverage, eligibility and question refusals.

It writes nothing.

## Evaluation corpus

`tests/fixtures/perspective_comparison/v1/cases.json` holds the synthetic
corpus. Each case is materialized through production write boundaries:

- upload, highlight, Perspective run and explicit retain, discard,
  highlight edit, and document exclusion;
- in-process fake adapters that control each response and model ID;
- no network.

Each case freezes:

- the **expected deterministic comparison**, in case-local labels;
- a **reference annotation**: the designed claim structure in the populated
  semantic form, with exact quotes and cited evidence;
- any **refusal probes**.

| Case | Controlled structure |
| --- | --- |
| C01 | same conclusion, same evidence |
| C02 | same conclusion, different evidence |
| C03 | different conclusions, same evidence; a discarded run is never comparable |
| C04 | different conclusions because of different evidence |
| C05 | a genuine assumption difference |
| C06 | wording differs only superficially (with surface negation) |
| C07 | similar wording, opposite claims |
| C08 | 2-to-1 majority with a meaningful minority |
| C09 | one Perspective makes an unsupported assertion |
| C10 | incomplete coverage: a receipt excluded from analysis |
| C11 | legitimately unclassifiable responses |
| C12 | one Perspective, two models, identical text |
| C13 | overlapping evidence with a highlight whose snapshot changed |
| N1 | question mismatch (refused) |
| N2 | legacy shape without the receipt table (refused) |

## Evaluation measures

| Measure | What is checked |
| --- | --- |
| Participant attribution | every participant maps to the exact case run: receipt, frame, family, model, response |
| Evidence overlap | units, `shared_by_all`, `supplied_only_to`, `overall` and pairwise relations equal the frozen expectation |
| Relations | the perspective, execution and response-text relations |
| Refusals | every refusal code |
| Semantic abstention | `not_established` everywhere; manufactured claims, agreement, disagreement or assumptions are counted (expected 0) |
| Reference adequacy | each reference validates against the populated form; quotes resolve exactly, cited evidence is within the participant's supplied Scope, and the derived relations are consistent |
| Minority and unknown preservation | all participants present; reference minorities and unclassifiable positions preserved; coverage gaps reported |
| Determinism | the same snapshot twice, and an independent rebuild |
| Ordering invariance | every permutation of requested IDs; reversed storage order |
| Model invariance | a rebuild with model identities changed leaves the substantive sections unchanged (question, evidence, perspective and response-text relations, semantic, and the non-execution uncertainty) |
| Evidence sensitivity | moving one participant's focus changes the evidence relations |
| Conclusion-flip boundary witness | flipping one response's conclusion changes the reference annotation but **not** the deterministic comparison, beyond response text. This records the boundary explicitly |
| No consensus→truth collapse | a recursive key scan finds no truth, correct, best, winner, majority, consensus, synthesis, answer or adjudication field |
| Provenance closure | every participant is an eligible typed Lineage item; every evidence unit resolves to a workspace row; every digest matches its text |
| Read-only | the workspace logical dump is unchanged |

## Not in P7 v1

- model-assisted or heuristic claim extraction;
- steward-authored or accepted comparison records;
- user adjudication;
- a synthesized or "best" answer;
- achievements (Multiple Lenses, Dissent Finder, Evidence Split, Assumption
  Spotter, Minority Report, Perspective Cartographer, Adjudicator);
- natural-language Blueprint proposals (P8);
- vector retrieval (P9);
- any change to P3/P4 receipts, rules or awards;
- use of the real study.
