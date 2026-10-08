# P8 — Natural-language Blueprint proposal v1 (contract)

Date: 2026-10-08. This contract was frozen before any P8 production code, on
`p8-blueprint-proposal` from merged `main` `d2d6ef2` (P7 merged via PR #249).
It implements P8 of
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215) under
[#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214) Decision 3
and [#212](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/212) §5. P7's
candidate and acceptance pattern is prior art, adapted rather than copied.

> **Natural language is the interaction layer; the structured Blueprint
> remains the governed substrate.** A model may draft a Blueprint or a
> successor. It may never write, accept or revise canonical Blueprint state.

```text
natural-language study intent
→ deterministic evidence basis (eligible records only)
→ structured Blueprint proposal (server-held candidate; nothing canonical written)
→ steward review
→ accept | edit-and-accept | discard
→ canonical Blueprint (create) or Blueprint successor + SupersessionRelation (revise),
  with ArchitectPlan compiled atomically, and an append-only acceptance receipt
```

## 1. Audit of the existing seams

| Seam | What it does today | P8 disposition |
| --- | --- | --- |
| `_normalize_blueprint_candidate` | Strict shape normalization (`null` means not given, #243) | **Reused** unchanged for exact and edited Blueprints |
| `_validate_blueprint_references` | Every Observation and Interpretation ID must exist; excluded evidence is a scope refusal | **Reused** unchanged at acceptance |
| `_persist_exact_blueprint_and_compile` | Content-derived `make_blueprint_id`; `INSERT OR IGNORE` of the Blueprint, its links and the ArchitectPlan with paragraphs; runs in the caller's transaction; `source` is a parameter | **Reused** unchanged, inside a P8-owned `BEGIN IMMEDIATE` that also writes the receipt |
| `_persist_blueprint_revision_and_compile` | Owns its transaction (`commit`, then `BEGIN IMMEDIATE`, then commit); successor `source` hard-coded `steward-authored`; refuses cycles; requires the steward reason (#241); writes an append-only successor, plan and `SupersessionRelation`; no leaf or staleness check | **Behavior-preserving refactor:** the in-transaction writes move into an inner helper that takes a `source` argument. The legacy wrapper keeps the identical transaction behavior and `steward-authored`. P8 calls the inner helper inside its own transaction, so the successor, plan, edge and receipt commit together. Exact model acceptance is never labelled `steward-authored` |
| `/api/pipeline/ratify-blueprint` | Persists whatever candidate the client posts (`source="extracted"`); no provider | **Unchanged** (direct steward ratification). Not a P8 acceptance path: it cannot prove which model proposal was reviewed |
| `/api/pipeline/revise-blueprint` | Persists a client-posted successor and the steward reason | **Unchanged.** It is also the stale-predecessor trigger used in case P09 |
| `/api/pipeline/extract-blueprint` (`save:false` / `save:true`) | Document-text extraction. `save:true` generates **and** persists in one call | **Unchanged and not reused** by P8 (#215 forbids the combined route as the approval contract) |
| `extract_blueprint_from_text` | One provider call; sections carry no evidence references; `_call_provider` **silently falls back** to a canned Blueprint for an unknown provider | **Not reused:** P8 forbids fallback providers and requires evidence-grounded references |
| `/api/architect/generate` | Builds a prompt from eligible Interpretations and sampled Observations, calls a provider, **persists immediately** (`source="ai-generated"`), silently drops unresolvable references, and commits the Blueprint before compiling the plan (not atomic). Called by the Reader UI | **Unchanged; reported, not changed** (§9) |
| NarrativeBlueprint and ArchitectPlan identity | Blueprint ID is content-derived; rows are immutable; revision is an append-only successor plus a SupersessionRelation `(old_id, new_id, reason, ratified_at)` | **Preserved.** P8 adds no Blueprint field |

**The smallest P8 boundary.** P8 adds one domain module (basis, prompt,
strict parsing, candidate) and four routes: propose, accept, discard and
read-receipt. Persistence goes through the existing helpers plus one
append-only receipt. There is no second Blueprint implementation.

## 2. Evidence basis (`blueprint-proposal-basis/v1`)

Generation sees only **eligible** records, as decided by Study Lineage. Lineage
is the eligibility authority; nothing excluded is ever exposed.

| Exposed to the model | Label | Identity bound in the candidate |
| --- | --- | --- |
| Canonical Observations (source evidence) | `O1…On`, ordered by (document, page, paragraph, sentence, id) | ID and SHA-256 of `{id, source_document_id, source_extraction_id, page, paragraph, sentence, raw_text}` |
| Canonical Interpretations from the `interpretations` table | `I1…Im`, ordered by (created_at, id) | ID, SHA-256 of the exact row, and the **Lineage authorship** label (`human` = steward-authored, `accepted_model` = accepted model contribution, `unknown` = authorship not recorded) |
| The governing question, when one is present | — | A `{status: captured, text, sha256}` snapshot, labelled in the prompt as the steward's current question (context, not evidence) |
| The predecessor Blueprint (revise only) | — | ID, SHA-256 of `{id, title, thesis, sections}`, and its successor IDs at generation |

**Not exposed in v1:**

- unaccepted model proposals (`proposed_interpretations`);
- retained Perspective executions;
- accepted Perspective comparisons;
- Reader marks;
- field notes.

Blueprint sections can cite only Observations and Interpretations. Model-origin
material is never presented as steward reasoning, and accepted-model
Interpretations stay labelled as model contributions.

**Bound.** At most 200 Observations and 100 Interpretations. A larger basis is
refused with `BASIS_TOO_LARGE`; nothing is sampled silently. Scope selection
is future work.

## 3. Candidate — `hermeneia.blueprint-proposal-candidate/v1`

| Field | Content |
| --- | --- |
| `candidate_id` | `blueprint-proposal-candidate:sha256:<hex>` over `"hermeneia.blueprint-proposal-candidate/v1\0"` ‖ C(candidate without `candidate_id`); C is the P3 canonical codec |
| `mode` | `create` or `revise` |
| `binding.intent` | the exact intent text and its SHA-256 |
| `binding.governing_question` | the captured snapshot, or `{status: absent, text: null, sha256: null}` |
| `binding.basis` | `policy_version`, plus the exposed `observations` and `interpretations` as label, ID and SHA-256 (and authorship for Interpretations) |
| `binding.predecessor` | `null` for create. For revise: `{id, sha256, successors_at_generation}` |
| `extraction` | `policy_version` `1.0.0`, `prompt_version` `blueprint-proposal/v1`, the exact prompt and its SHA-256, the recorded **adapter-reported** `execution` (`provider_id`, `model_id`, `runtime_host`, adapter class), `created_at`, `completed_at`, the exact raw output and its SHA-256 |
| `proposal.blueprint` | the normalized proposed Blueprint: title, thesis, sections with real record IDs. For revise this is the **complete successor** |
| `proposal.model_explanation` | revise only: the model's `change_summary`, model-authored. It is **never** the canonical rationale |

**Server-held.** Candidates live only in server memory, bounded to 100 per app.
Eviction or restart means the steward regenerates; v1 accepts that.

**Generation writes nothing canonical.** The workspace logical digest is
unchanged by every generation.

### Model output (`hermeneia.blueprint-proposal-output/v1`)

The output is one JSON object, optionally inside one fenced block:

```json
{"title": "…", "thesis": "…", "sections": [{"claim": "…", "observations": ["O1"], "interpretations": ["I1"]}]}
```

Revise adds `"change_summary": "…"`. There must be 1–12 sections, every field
is required, `[]` means no support, and there are no other keys.

| Refusal (no candidate is held) | Condition |
| --- | --- |
| `PROPOSAL_OUTPUT_UNPARSEABLE` | not one JSON object, or a duplicate key |
| `PROPOSAL_OUTPUT_INVALID` | a missing, null or blank required field; an unknown key; a wrong type; a section count outside 1–12 |
| `PROPOSAL_REFERENCE_EXCLUDED` | a reference equals the ID of an existing but **ineligible** (for example, excluded) Observation or Interpretation |
| `PROPOSAL_REFERENCE_UNKNOWN` | any other reference that is not an exposed label: invented, or not shown to the model |

The model cannot invent record IDs: only exposed labels resolve. Missing support
stays missing — a section with `[]` is kept with no support, and nothing is
inferred.

## 4. Steward decisions

| Route | Body | Effect |
| --- | --- | --- |
| `POST /api/blueprint/proposals/<candidate_id>/accept` | `{"decision": "accept", "candidate_id", "reason"?}` | Commits `proposal.blueprint` byte for byte |
| (same) | `{"decision": "edit_and_accept", "candidate_id", "blueprint": {title, thesis, sections}, "reason"?}` | Commits the steward's edited Blueprint, validated by the existing normalizer and reference validator. The steward may cite any eligible evidence; the model's proposal is preserved in the receipt |
| `POST /api/blueprint/proposals/<candidate_id>/discard` | `{"decision": "discard", "candidate_id"}` | Removes the transient candidate. No canonical negative-history event |

### Acceptance rules

All of these run inside one `BEGIN IMMEDIATE`:

1. The body ID equals the URL ID and the held candidate. Otherwise:
   - 409 `CANDIDATE_MISMATCH` if they differ;
   - 404 `UNKNOWN_CANDIDATE` for an unknown, discarded or evicted candidate.
2. **Revise only.** `reason` is the steward-authored canonical rationale and is
   required: absent, null or blank refuses with 422 `REASON_REQUIRED`.
   - For create, `reason` must be absent.
   - The model's `change_summary` never becomes the reason.
3. **Stale check, over bound inputs only.** Any of the following refuses with
   409 `STALE_CANDIDATE` and writes nothing:
   - an exposed Observation or Interpretation is missing, has a different
     digest, or is no longer Lineage-eligible;
   - a captured governing question changed;
   - the predecessor is ineligible, has a different digest, or gained a
     successor after generation.

   New records the candidate never saw (new uploads, Interpretations, marks
   or Perspective runs) do **not** make a candidate stale.
4. **Persistence.**
   - **Create:** `_persist_exact_blueprint_and_compile(source=…)`.
   - **Revise:** the in-transaction revision helper with `source=…` and the
     steward reason. It enforces the existing append-only successor rules,
     cycle refusal and atomic ArchitectPlan compilation.
   - **Then:** the receipt is written, and Lineage must project it. All of it
     commits together.
5. **Idempotence.** A repeat decision on an accepted candidate returns the same
   receipt with 200.

### Blueprint row `source` values for new rows

The vocabulary of the existing `source` attribute gains two values:

- `proposal-accepted`: an exact acceptance of a model proposal;
- `proposal-edited`: a steward edit of a model proposal.

Lineage authorship for those rows comes **only** from a valid linked receipt:

- `proposal-accepted` → `accepted_model`;
- `proposal-edited` → `human`;
- with no valid receipt → `unknown`.

If identical content already exists, the content-derived ID resolves to the
existing row unchanged. The receipt then records `blueprint_preexisted: true`
and does not relabel it. Exact model acceptance is never called human-authored.

## 5. New durable record — the acceptance receipt

**Why it is necessary.** Existing Blueprint rows store only title, thesis,
sections, `source` and `created_at`; SupersessionRelation stores only the
reason and time. Neither can prove:

- which candidate was reviewed;
- what the model proposed (prompt, execution, raw output);
- what the steward accepted;
- whether the steward edited it.

#214 requires that distinction. A small append-only receipt linked to the
resulting Blueprint is preferred over adding fields to the Blueprint ontology.

`hermeneia.blueprint-proposal-acceptance/v1` is stored in table
`blueprint_proposal_acceptances(id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL
UNIQUE, receipt_json TEXT NOT NULL)`, added as schema 21 through the existing
startup initializer.

| Aspect | Definition |
| --- | --- |
| **Identity** | `blueprint-proposal-acceptance:sha256:<hex>` over `"hermeneia.blueprint-proposal-acceptance/v1\0"` ‖ C(receipt without `id`); stored bytes are exactly C(receipt) |
| **Owner** | the local steward's explicit decision (`actor: local_steward`, `actor_identity: unknown`) |
| **Origin** | `{kind: model_proposed_steward_accepted | model_proposed_steward_edited}`, consistent with `decision: accept | edit_and_accept` (the same vocabulary as P7; one schema) |
| **Candidate provenance** | the complete candidate (binding, extraction, proposal) and its `candidate_id`, recomputable |
| **Steward decision** | the decision, `accepted_at`, `reviewed_candidate_id`, the accepted Blueprint (canonical content), `edited` (bool), the steward `rationale` (revise) or `null`, and a fixed `meaning` |
| **Result** | `resulting_blueprint_id`, `plan_id`, `blueprint_preexisted`, `mode`, `predecessor_id` (revise), and the exact `supersession` row `{old_id, new_id, reason, ratified_at}` (revise) |
| **Meaning** | "The steward accepted this Blueprint (as proposed, or as edited) from this exact model proposal. It does not establish that the Blueprint's claims are true or that the model's explanation is the steward's rationale." |
| **Immutability** | triggers refuse UPDATE, DELETE and REPLACE by `id` or `candidate_id`; one candidate yields at most one receipt |
| **Lineage** | record type `blueprint_proposal_acceptance`, event `recorded`. Authorship is `accepted_model` (accept) or `human` (edit). The timestamp is `accepted_at`. The context links to the resulting Blueprint. The safe summary has no prompt or evidence text. The **whole receipt is omitted** if the resulting Blueprint, the predecessor, or any exposed record becomes ineligible, because its prompt quotes them. A malformed receipt is omitted with a diagnostic. It is excluded from P1/P2 evidence and coverage, like awards and accepted comparisons |
| **Independent verification** | `verify_blueprint_proposal_acceptance(conn, id)` is read-only and reports `record_integrity`, `candidate_replay` (prompt rebuilt from bound records; raw output re-parsed to the same proposal), `result_closure` (the resulting Blueprint content equals the accepted Blueprint; plan present; for revise, the supersession row and predecessor present) and `model_output: preserved_not_replayed` |
| **Export/restore** | see below |

### Export/restore coverage: declared unsupported

WBS 1.x exports none of the following:

- `narrative_blueprints` and their links;
- `architect_plans` and their paragraphs;
- Blueprint supersession edges;
- `interpretations`.

A receipt's closure (its resulting Blueprint, plan, edge and cited
Interpretations) therefore cannot be restored. Exporting receipts would create
dangling records.

Per #214's portability rule ("missing portable coverage = unsupported
evidence") and #215, P8 must *declare* coverage and P10 owns the
"round-trips … any new Blueprint proposal provenance". So in P8 v1:

- receipts are **not exported**;
- `read_bundle` and `preview_restore` coverage report
  `blueprint_proposal_acceptances: unsupported`, with that reason;
- restore never creates receipts;
- nothing claims portable completeness.

This is reported to the owner as architectural pressure, because pulling
Blueprint and Interpretation WBS coverage forward from P10 is a separate
decision.

## 6. Provider behavior

- **Local only.** Generation uses the existing local provider path, the same
  as Perspective runs and P7: `_local_perspective_execution_context` and the
  provider registry. **No fallback provider.**
- **Unavailable model:** a missing model, offline runtime or provider error
  answers 409 or 502 visibly, with no candidate and no write.
- **Execution record:** what is recorded is the adapter-reported execution
  configuration plus the provider ID, model ID, runtime host and adapter class
  that actually executed.
- **Gate.** Like P7's disposition, generation is behind a configuration gate,
  `BLUEPRINT_PROPOSAL_GENERATION`, disabled by default. It is enabled with
  `"experimental"` or `HERMENEIA_BLUEPRINT_PROPOSALS=experimental`. When
  disabled, the route answers 403 `BLUEPRINT_PROPOSAL_DISABLED` before any read
  or provider call.

  Model competence for this task is not yet demonstrated (§10). Acceptance,
  discard and receipt reads are not gated.

## 7. Invariants (tested)

1. Generation writes nothing canonical.
2. A candidate binds exactly the state used: intent, governing question,
   exposed records, predecessor, prompt, execution and raw output.
3. Acceptance commits only the held candidate's proposal, or the steward's
   explicitly edited Blueprint. No client substitution of the proposal is
   possible.
4. Stale, excluded or invented references never reach canonical state.
5. Exact acceptance is `accepted_model`, never human-authored. An edit is
   `human`, with the model proposal preserved.
6. The canonical revision rationale is always the steward's. The model's
   explanation stays model-authored.
7. Revision is append-only: the predecessor is untouched, the successor and
   edge are new, and cycles are refused.
8. The Blueprint, ArchitectPlan, edge and receipt commit atomically, or
   nothing commits.
9. Discard leaves no history.
10. P1 through P7 behavior is unchanged.

## 8. Frozen synthetic corpus

The corpus is `tests/fixtures/blueprint_proposal/v1/cases.json`, frozen with
this contract before the generator exists. It uses:

- **Scripted in-process providers** that return case-local labels
  (`A:n` → `O`-label, `I:key` → `I`-label), so the scripts are independent of
  run-time IDs;
- **Structural expectations only:**
  - refusal codes;
  - stances on records;
  - sources, authorship and origins;
  - rationale equality;
  - row counts;
  - digests unchanged.

No prose wording is judged except where wording **is** the invariant: the
canonical rationale must equal the steward's text and differ from the model's.

| Case | Scenario | Expected structural outcome |
| --- | --- | --- |
| P01 | simple goal, Observations only, create | candidate; references resolve to the exposed Observations; generation writes nothing |
| P02 | goal grounded in three Interpretations: two steward-authored and one accepted model contribution | candidate cites them; the prompt labels each Interpretation with its Lineage authorship |
| P03 | output cites `O99` (not exposed) | 422 `PROPOSAL_REFERENCE_UNKNOWN`; no candidate |
| P04 | document B excluded; output cites a real B Observation ID | 422 `PROPOSAL_REFERENCE_EXCLUDED`; B's text never appears in the prompt |
| P05 | exact accept of P01 | 201; Blueprint `source=proposal-accepted`; plan compiled; receipt origin `model_proposed_steward_accepted`; Lineage Blueprint and receipt both `accepted_model` |
| P06 | edit-and-accept (title changed, one section removed) | 201; Blueprint is the steward's edit, `source=proposal-edited`; receipt `model_proposed_steward_edited`, `edited: true`, model proposal preserved; Lineage `human` |
| P07 | discard | 200; no Blueprint, plan or receipt; a later accept answers 404 |
| P08 | document A excluded after generation | accept answers 409 `STALE_CANDIDATE`; nothing written |
| P09 | the predecessor is revised through the legacy route after a revise candidate was generated | accept answers 409 `STALE_CANDIDATE`; no P8 successor or receipt |
| P10 | revise using a new Interpretation recorded after the predecessor | 201; the successor cites it; a new edge with the steward reason; the predecessor unchanged; plan compiled |
| P11 | the model's `change_summary` differs from the steward reason | the edge reason equals the steward's exact text and differs from the model's; the receipt keeps `model_explanation` separately |
| P12 | the selected model is not installed | 409, no provider call, no candidate, no write |
| P13 | `thesis: null`; separately, prose output | 422 `PROPOSAL_OUTPUT_INVALID`; 422 `PROPOSAL_OUTPUT_UNPARSEABLE` |
| P14 | the accepted candidate is accepted again | 200, the same receipt; still exactly one receipt and one Blueprint |
| P15 | export, then restore, of a workspace with a receipt | no receipt component in the bundle; read and preview coverage report `blueprint_proposal_acceptances: unsupported` with the reason; restore creates no receipt |

Further frozen checks:

- revise without a reason answers 422 `REASON_REQUIRED`;
- an accept naming a different candidate ID answers 409 `CANDIDATE_MISMATCH`;
- an edit citing an excluded Observation answers 403, the existing scope refusal;
- on a default app, generation answers 403 `BLUEPRINT_PROPOSAL_DISABLED`;
- each receipt verifies `valid`, `verified`, `verified` and
  `preserved_not_replayed`;
- the legacy `/api/pipeline/revise-blueprint` still writes
  `source=steward-authored` (refactor parity);
- the P5, P6 and P7 datasets reproduce.

## 9. Legacy `/api/architect/generate`: disposition reported, not changed

It persists model output directly, so it is not a P8 path. It stays
**unchanged** in this packet because:

- disabling it would break the current Reader UI call (`index.html`, which
  also holds unrelated uncommitted owner edits);
- delegating would change its response contract;
- neither move is authorized by existing authority.

**Recommendation for the owner:** once a P8 Reader surface exists, default-
disable the route for the product flow (keep it internal or legacy), or
replace its UI call with the P8 propose-and-review flow. The same applies to
`/api/pipeline/extract-blueprint` with `save:true`.

## 10. Live-model boundary

This packet uses scripted providers only. After the governance implementation
and the frozen corpus pass, work stops and a frozen live-evaluation protocol
is proposed. No live model runs in P8 v1.
