# Structured Perspective Comparison v1, Layer 2 — governed candidate and accepted comparison

Date: 2026-10-07. This contract was frozen before any provider, candidate or
storage code, on branch `p7-perspective-comparison` at `9027af7`. It
continues P7 of [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215)
under [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214),
using the owner's option (a): a model proposes structure and a steward
governs it.

**Layer 1** ([perspective-comparison-v1.md](perspective-comparison-v1.md)) is
the deterministic receipt and evidence comparison. It stays unchanged and is
the substrate Layer 2 binds to. Its inability to infer agreement from free
prose is an intentional epistemic boundary. Layer 2 does not patch that
boundary with heuristics. It adds a governed path across it:

```text
eligible retained receipts
→ Layer 1 comparison (deterministic, unchanged)
→ semantic extraction model (proposal only)
→ structured comparison candidate (transient; every assertion traced or unknown)
→ steward accept / edit-and-accept / discard
→ accepted structured comparison (append-only canonical record)
```

The model proposes structure. It never decides truth, authority or
adjudication. Agreement, disagreement and minority relations are **never taken
from the model**. They are derived deterministically from traced positions.

## 1. One structure type — `hermeneia.perspective-comparison-structure/v1`

Model candidates, steward edits and future steward authoring (option (b)) all
use this single type and its single validator. There is no parallel
representation.

```text
structure = {
  schema, participants,            # Layer 1 participant receipt IDs, in Layer 1 order
  propositions: [{id, statement, positions: [position per participant, in participant order]}],
  assumptions: [{id, participant, span}],
  untraceable: [...],              # model-proposed items that could not be traced (candidates only)
  relations: {...}                 # derived; never authored
}
position = {participant, stance, span, reliance}
span     = {start, end, text}      # text == participant.response[start:end], exactly
```

| Stance | Span | Reliance | Meaning |
| --- | --- | --- | --- |
| `asserts` | required | allowed | the response asserts the proposition |
| `denies` | required | allowed | the response denies it |
| `unclassifiable` | required | allowed | the response speaks to it, but its stance cannot be determined (a legitimate unknown) |
| `does_not_address` | none | none | an absence classification; never counts toward any relation |
| `unknown` | none | none | no traceable basis (the model gave none, or its quote could not be traced) |

**Reliance** is the evidence a Perspective **explicitly connects** to a
positioned statement. Each entry is a typed Layer 1 unit (`source_extractions`
or `reader_highlights`) that was supplied to that participant. Supplied
evidence is not reliance.

Traceability guarantees two things about reliance: its span exists in that
participant's response, and the unit was supplied to them. It does not
guarantee that the span really refers to the unit. That is semantic, and is
measured (§9) and reviewed by the steward.

**Proposition statements** are neutral restatements written by the candidate's
origin. They are labels, not quotations. Every claim attributed to a
Perspective rests on a position span.

### Derived relations (deterministic; recomputed on every validation)

For each proposition:

- **Agreement:**
  - two or more participants share `asserts` (or share `denies`), and no
    participant holds the opposite stance;
  - each entry lists `{proposition, stance, participants, not_established_for,
    reliance, same_reasoning: "not_established"}`.
- **Disagreement:**
  - at least one participant asserts and at least one denies;
  - each entry lists `{proposition, groups, minority_participants,
    not_established_for, reliance, resolution: "none_recorded"}`;
  - `groups` lists the `asserts` group, then the `denies` group, each in
    participant order;
  - `minority_participants` are the members of every group strictly smaller
    than the largest. A 1-vs-1 split has no minority.
- **`not_established_for`:** participants whose position is `unknown` or
  `unclassifiable`. Agreement among some participants never hides a
  participant whose position is unknown.
- **`reliance`** over the reliance sets of the participants involved:
  - `identical`, `overlapping` or `disjoint`;
  - `some_uncited` when any involved participant cites nothing.
- **Same conclusion is not same reasoning.** `same_reasoning` is always
  `not_established`. An agreement whose reliance is not `identical` is
  "same conclusion, different reliance".
- **`unresolved`:** every disagreement. No adjudication exists.
- **`unknown_positions`:** every `unknown` or `unclassifiable` position.
- **`evidence_use`:** per participant, `relied_on` (the union of its reliance)
  and `supplied_not_relied_on` (Layer 1 supplied units minus `relied_on`).

There is no majority, consensus, winner, truth, correctness, verdict, score
or adjudication field anywhere. Agreement among models is not truth, and model
consensus is not steward agreement.

### Strict validation (steward edits and authored structures)

A structure supplied by a steward is validated strictly. Any of the following
refuses with `STRUCTURE_INVALID` or `STRUCTURE_UNTRACEABLE`; it is never
downgraded silently:

- an unknown field, or any authored `relations` or `untraceable` field;
- participants that differ from Layer 1;
- a missing or duplicate position;
- a span that does not equal `response[start:end]`;
- a span on `does_not_address` or `unknown`;
- a missing span on `asserts`, `denies` or `unclassifiable`;
- reliance outside the participant's supplied units;
- a duplicate ID.

The server then derives `relations`. In a steward structure `untraceable` is
always empty.

## 2. Semantic extraction policy `1.0.0`, prompt `perspective-comparison-extraction/v1`

The prompt is built deterministically from the Layer 1 comparison and the
canonical text of each supplied unit:

- the source-extraction `raw_text`;
- for a Reader highlight, its captured text from the receipt.

Participants are labeled `P1…Pn` in Layer 1 order, and units `U1…Um` in Layer 1
unit order. For each participant the prompt gives:

- its Perspective label and ID;
- its supplied units and their roles;
- its exact response.

It also gives the exact execution question. The instructions say the output is
a proposal for steward review, not a synthesis, verdict or adjudication:

- quote exactly from the participant's own response;
- treat paraphrases as one proposition;
- record assumptions only when stated;
- list reliance only when the response connects to it;
- give every participant one position per proposition;
- emit no other field.

### Wire output (`hermeneia.perspective-comparison-extraction-output/v1`)

```json
{"propositions": [{"id": "p1", "statement": "…", "positions": [
   {"participant": "P1", "stance": "asserts|denies|does_not_address|unclassifiable",
    "quote": "exact text or null", "relies_on": ["U1"]}]}],
 "assumptions": [{"participant": "P1", "quote": "exact text"}]}
```

The output may be wrapped in one fenced code block. Nothing else is tolerated.

### Refused output (no candidate)

The whole output is refused, and no candidate is held, in these cases:

| Code | Condition |
| --- | --- |
| `EXTRACTION_OUTPUT_UNPARSEABLE` | not one JSON object, or duplicate keys |
| `EXTRACTION_OUTPUT_AUTHORITY_FIELD` | any key at any depth in {`truth`, `true`, `correct`, `correctness`, `best`, `winner`, `majority`, `consensus`, `verdict`, `adjudication`, `answer`, `synthesis`, `score`, `confidence`, `probability`} |
| `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` | any other unknown key, unknown stance, unknown participant or unit label, a duplicate position, a blank statement, or more than 50 propositions or assumptions |

### Normalization (untraced means unknown)

The candidate is built from the output in order. Propositions get IDs
`p1…pk` in output order; IDs skip where a proposition was removed.

| Model-proposed item | Admitted when | Otherwise (recorded in `untraceable`) |
| --- | --- | --- |
| `asserts`, `denies` or `unclassifiable` position | its quote occurs **exactly once** in that participant's response | the position becomes `unknown` (`untraceable_position`, with the proposed stance, quote and reliance) |
| `does_not_address` | it has no quote and no reliance | becomes `unknown` (`contradictory_position`) |
| a missing participant position | — | `unknown` (`position_not_classified`) |
| a reliance unit on an admitted position | the unit was supplied to that participant | dropped (`reliance_outside_supplied_scope`) |
| a proposition | it keeps at least one `asserts`, `denies` or `unclassifiable` position | removed (`untraceable_proposition`, with the statement) |
| an assumption | its quote occurs exactly once in that participant's response | dropped (`untraceable_assumption`) |

Quoting another participant's text is therefore always caught: it does not
resolve in the attributed response. So is a fabricated quote. A quote that
occurs twice is ambiguous and stays unknown.

## 3. Candidate — `hermeneia.perspective-comparison-candidate/v1`

| Field | Content |
| --- | --- |
| `candidate_id` | `perspective-comparison-candidate:sha256:<hex>` = SHA-256 of `"hermeneia.perspective-comparison-candidate/v1\0"` ‖ C(candidate without `candidate_id`) |
| `binding.receipts` | per participant in Layer 1 order: `receipt_id`, `receipt_sha256` (SHA-256 of the exact stored `receipt_json` bytes), `response_sha256`, `scope_sha256` |
| `binding.question` | the exact execution question and its digest (Layer 1) |
| `binding.governing_question` | the workspace governing question captured at generation: `{status: captured, text, sha256}` or `{status: absent, text: null, sha256: null}`, with `basis: "current_snapshot_at_generation"`. The Perspectives never saw it; it records the study context the steward reviewed under |
| `binding.layer1` | Layer 1 `schema`, `policy_version`, `comparison_id` and `digest` |
| `extraction` | `policy_version`, `prompt_version`, exact `prompt` and `prompt_sha256`, exact recorded `execution` (`provider_id` and `model_id` required), `created_at`, `completed_at`, exact raw `output` and `output_sha256` |
| `structure` | the normalized structure (§1, §2) |

C is the P3 canonical codec.

The **Layer 1 digest** is the SHA-256 of `"hermeneia.perspective-comparison/v1\0"`
‖ C of `{schema, policy_version, comparison_id, question, participants,
evidence, relations}`. This is the part of Layer 1 that depends only on the
participants. `coverage` and `uncertainty` describe the rest of the workspace
snapshot, so they are context and are not bound.

Candidates are transient. They are held only in server memory, per app and
workspace, bounded to 100. Generation never writes.

## 4. Steward decisions

All decisions bind to the exact `candidate_id` the steward reviewed. The body
repeats that ID, and it must equal the held candidate.

| Decision | Body | Effect |
| --- | --- | --- |
| accept | `{"decision": "accept", "candidate_id": id}` | the candidate structure becomes the accepted structure, byte for byte |
| edit-and-accept | `{"decision": "edit_and_accept", "candidate_id": id, "structure": {participants, propositions, assumptions}}` | the strictly validated edited structure, with server-derived relations, becomes the accepted structure; the candidate is preserved beside it |
| discard | `{"decision": "discard", "candidate_id": id}` | the transient candidate is removed; no canonical comparison exists and no negative event is recorded |

### Refusals

The workspace is unchanged after every refusal.

| Code | When |
| --- | --- |
| `UNKNOWN_CANDIDATE` (404) | unknown, discarded, evicted or lost after restart |
| `CANDIDATE_MISMATCH` (409) | the body ID differs from the held candidate |
| `STALE_CANDIDATE` (409) | at acceptance, inside the write transaction, any bound input differs: the recomputed Layer 1 digest, any participant receipt's stored bytes, or the current governing question snapshot. This includes a participant that has become ineligible |
| `STRUCTURE_INVALID` / `STRUCTURE_UNTRACEABLE` (422) | edit validation failed |
| (400) | extra or missing body fields |
| (409) | discarding an already accepted candidate |

Repeat acceptance of an accepted candidate returns the same record (200).

## 5. Accepted comparison — durable canonical record

### Why durable

Future Perspective achievements (#215: Dissent Finder, Evidence Split,
Assumption Spotter, Perspective Cartographer, Multiple Lenses) must cite "an
accepted structured comparison plus its retained input receipts". That claim
needs a reconstructable record of what the steward accepted. The Layer 1
projection stays non-durable.

### Meaning

> The steward accepted this comparison structure. It does not establish that
> any claim is true, that the steward agrees with any Perspective, or that
> any disagreement is resolved.

### Ownership and authorship

- **Owner:** the local steward's explicit acceptance decision.
- **Lineage authorship:**
  - **exact acceptance:** `accepted_model`. The model proposed the structure
    and the steward accepted it exactly;
  - **edit-and-accept:** `human`. The steward-edited structure is accepted, and
    the model candidate is preserved;
  - **future steward-authored records:** `human`.
- **Actor:** `local_steward`, with `actor_identity: "unknown"`.

### Record `hermeneia.accepted-perspective-comparison/v1`

Fields:

- `schema`;
- `id`;
- `origin`: `{kind: model_candidate | steward_authored}`;
- `binding`: as in the candidate;
- `candidate`: `{candidate_id, extraction, structure}`, or `null` for
  `steward_authored`;
- `structure`: the accepted structure;
- `acceptance`:
  - `decision`: `accept`, `edit_and_accept` or `author`;
  - `actor` and `actor_identity`;
  - `accepted_at`;
  - `reviewed_candidate_id`;
  - `structure_sha256`;
  - `meaning`.

### Identity, immutability and versioning

- **Identity:** `accepted-perspective-comparison:sha256:<hex>` = SHA-256 of
  `"hermeneia.accepted-perspective-comparison/v1\0"` ‖ C(record without `id`).
- **Table:** `accepted_perspective_comparisons(id TEXT PRIMARY KEY,
  candidate_id TEXT UNIQUE, comparison_json TEXT NOT NULL)`. Stored bytes are
  exactly C(record).
- **Immutability:** triggers refuse UPDATE, DELETE and INSERT OR REPLACE by
  `id` or `candidate_id`. One candidate yields at most one record. There is
  no withdrawal subsystem.
- **Schema:** schema 20 adds the table through the existing startup
  initializer. Read-only readers never create it.
- **Versioning:** the record pins its structure schema, extraction policy and
  prompt versions, and the Layer 1 policy version. Unknown versions are
  unsupported, never converted. A later policy coexists; it never rewrites an
  existing record.

### Receipt closure

- Every participant receipt must exist, with exact stored-bytes digests equal
  to `binding.receipts`.
- Every span, in both the accepted structure and the candidate structure, must
  resolve in its bound receipt's response.
- Every reliance unit must be in that participant's supplied Scope.

### Lineage

Lineage projects a new record type, `accepted_perspective_comparison`:

- **Item:** `event: recorded`, the authorship above, timestamp `accepted_at`,
  and a fixed content line with no response text.
- **Summary:**
  - the ID, origin, decision and participants;
  - proposition, agreement, disagreement and unknown counts;
  - the extraction model;
  - verification `{record_integrity: valid, replay: not_performed}`.
- **Contexts:** each participant's exact receipt.
- **Eligibility:**
  - if **any** participant receipt is not eligible (for example, excluded),
    the whole record is omitted, because its spans quote that response;
  - a malformed record is omitted with a diagnostic.
- **P1/P2:** accepted comparisons never become prerequisite or history
  evidence. They are excluded exactly as award receipts are, so P1, P2 and P6
  results are unchanged.

### WBS

- **Capability and component:** required capability
  `accepted-perspective-comparison-v1`; canonical component
  `study/accepted_perspective_comparisons.json`; count key
  `accepted_perspective_comparisons`.
- **Export:** rows keep their exact stored bytes, in ASCII ID order, taken in
  one snapshot. Receipt closure must hold or the export is refused. Excluded
  participants remain archivable.
- **Restore:**
  - validates the capability, manifest entry, hash, count, exact row shape,
    canonical payload and record integrity;
  - installs rows after the receipts, in the same atomic transaction, and
    validates closure against the restored receipts;
  - on any failure installs nothing.
- **Coverage:** older bundles without the component report coverage
  `unsupported`, never zero accepted comparisons.

### Verification and replay

`verify_accepted_comparison(conn, id)` is read-only and makes no provider call.

| Dimension | States |
| --- | --- |
| `record_integrity` | `valid`, `invalid`: codec, ID, strict structure validity, derived relations recomputed equal, candidate ID recomputed |
| `receipt_closure` | `verified`, `missing_receipt`, `receipt_mismatch`, `span_mismatch` |
| `layer1_replay` | `verified`, `participants_not_eligible`, `mismatch` (the recomputed Layer 1 digest) |
| `candidate_replay` | `verified`, `mismatch`, `not_applicable` (steward-authored): regenerate the prompt from Layer 1 and the canonical unit texts, re-normalize the preserved raw output, and compare both with the stored values |
| `model_output` | always `preserved_not_replayed`. The exact nondeterministic output is kept; the model is never called again |

Reconstructability means one thing: from the receipts and the stored
candidate and accepted structures, Hermeneia can recompute Layer 1, the prompt,
the normalized candidate and every relation, and check all of them.

## 6. API

| Route | Behavior |
| --- | --- |
| `POST /api/perspective/comparison/candidates` `{"receipt_ids": [...], "model": "..."}` | Layer 1 in a read-only snapshot, then the governing-question snapshot, prompt, local provider call, parse and normalize. Returns 201 with the candidate and `canonical_status: "not_persisted"`. Layer 1 refusals pass through (400/409). Provider failure returns 502. Refused output returns 422 with its code and the transient raw output. Nothing is written |
| `POST /api/perspective/comparison/candidates/<candidate_id>/accept` | §4. Returns 201 with the record, or 200 on repeat |
| `POST /api/perspective/comparison/candidates/<candidate_id>/discard` | §4 |
| `GET /api/perspective/comparison/accepted/<id>` | read-only, `no-store`. A Lineage-omitted record answers 404, the same as an unknown one |

The provider path is the existing local-only Perspective path.

## 7. Option (b) — steward-authored comparisons

The record schema already admits `origin.kind = steward_authored` with
`candidate: null` and `decision: author`. The structure is validated by the
same strict validator. A domain constructor exists so tests can show the
convergence. No authoring route or UI is added in P7.

## 8. Option (c) — recorded as a future direction only

A future Perspective receipt version (`perspective-run/v2`) could ask the
model for structured, citation-bearing output at run time. Nothing in P7
changes the `perspective-run/v1` contract, E(r) or any receipt. Historical
free-prose receipts remain valid and comparable under Layers 1 and 2.

## 9. Evaluation

The corpus is `tests/fixtures/perspective_comparison/v1/candidate_cases.json`.
It reuses the frozen Layer 1 cases and reference annotations unchanged. Only
in-process scripted fake providers are used. **Scripted output measures the
governed pipeline, not a model's extraction quality.** Establishing real
extraction quality requires a live model and separate owner authorization.

1. **Faithful scripts.** For each of the 13 compared Layer 1 cases, the frozen
   reference annotation is rendered in the wire format. The candidate's
   derived relations must reproduce the reference exactly: agreement,
   disagreement, minority, unresolved and unclassifiable.
2. **Adversarial scripts**, each tempting one failure:
   - manufacturing an assumption;
   - inferring reliance from supply;
   - calling a paraphrase a disagreement;
   - erasing a 1-vs-2 minority (by `does_not_address`, and by omission);
   - turning majority into truth;
   - attributing a claim to the wrong participant;
   - unparseable output.

   Each freezes its **governance outcome**: refusal code, normalized stances,
   untraceable kinds and derived relations. It also freezes the **extraction
   score deviations** a reviewer would see.
3. **Layer 1 refusals** pass through unchanged (N1, N2).
4. **Steward acceptance**, measured separately:
   - exact accept;
   - edit-and-accept that repairs an adversarial candidate back to the
     reference;
   - discard;
   - stale refusal (governing question changed; participant excluded);
   - candidate mismatch;
   - an untraceable edit;
   - repeat acceptance;
   - exclusion after acceptance;
   - export and restore with replay verification.

### Extraction score

Computed in the evaluation harness only, never in production.

- **Matching.** A candidate proposition matches a reference proposition when,
  for some participant, both have span-bearing positions whose character
  intervals overlap in that participant's response. Matching is one-to-one
  and greedy, in reference order.
- **Score object.** Each adversarial case freezes the complete score object
  before implementation:

| Measure | Definition |
| --- | --- |
| `propositions` | `{matched, reference, candidate}` counts |
| `stance` | `{agree, total}` over matched pairs × all participants; a candidate `unknown` never agrees |
| `reliance` | `{tp, fp, fn}` over matched pairs × all participants, comparing the candidate reliance set (empty without a span) with the reference cited set |
| `assumptions` | `{tp, fp, fn}`; one-to-one match on the same participant with overlapping spans |
| `agreement` | `{tp, fp, fn}` over `(proposition, stance, participant set)`. Candidate propositions map to their matched reference proposition; an unmatched candidate relation is a false positive |
| `disagreement` | `{tp, fp, fn}` over `(proposition, asserting set, denying set)` |
| `minority_preserved` | every reference minority participant is a `minority_participants` member of the matched candidate disagreement; true when the reference has none |
| `unknown_preserved` | every reference `unclassifiable` position is `unclassifiable` or `unknown` on the matched candidate proposition; true when the reference has none |
| `untraceable` | count by kind |

## 10. Completion gate (owner)

P7 closes only when:

1. Layer 1 is intact;
2. the candidate structure is versioned and provenance-bound;
3. exact accept, edit and discard semantics work;
4. an accepted comparison is reconstructable from its receipts and stored
   structures;
5. export and restore preserve an accepted synthetic comparison;
6. the frozen corpus demonstrates agreement, disagreement, evidence, minority
   and unknown behavior without consensus becoming truth.

P8 is not started.
