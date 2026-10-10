# #215 P8 natural-language Blueprint proposal — governance packet — 2026-10-08

**Result.** The governed path passes every frozen synthetic expectation:

| Group | Passed |
| --- | --- |
| Frozen cases | 15/15 |
| Further checks | 4/4 |

Scripted in-process providers only. These results show **governance**, not
model competence. No live model was called. Work stops at the live-model
boundary (§6).

- **Base:** merged `main` `d2d6ef2`.
- **Contract frozen first:** `aa4a2a5`. It holds
  `docs/design/blueprint-proposal-v1.md` and these fixtures:
  - the prompt policy;
  - the candidate and receipt schemas;
  - the 15-case corpus.
- **Implementation:** `9967255`.

## 1. The P8 product path

```text
natural-language intent ──► POST /api/blueprint/proposals            (gated; read-only basis; local provider; nothing written)
                             │  Lineage-eligible Observations + Interpretations (authorship-labelled), governing-question snapshot,
                             │  predecessor (revise) → exact prompt → adapter-reported execution → raw output → strict parse
                             ▼
                       server-held candidate (binds intent, exposed records + digests, predecessor + successors, prompt, execution, output)
                             │
     steward ──► POST …/<candidate_id>/accept {accept | edit_and_accept, candidate_id, reason (revise)}     POST …/discard
                             │  one BEGIN IMMEDIATE: stale check over bound inputs only →
                             │  create: _persist_exact_blueprint_and_compile(source=proposal-accepted|proposal-edited)
                             │  revise: _revision_preflight + _revise_blueprint_in_transaction(source=…, steward reason)
                             │  → append-only acceptance receipt → Lineage must project it → commit
                             ▼
                 canonical Blueprint (or successor + SupersessionRelation) + ArchitectPlan + receipt — atomic
```

Two more routes complete it:

- `GET /api/blueprint/proposals/acceptances/<id>`: read-only, `no-store`,
  Lineage-gated.
- `verify_blueprint_proposal_acceptance`, implemented as `verify_receipt`:
  independent verification.

## 2. Was a new durable record necessary? Yes

Existing Blueprint rows (`title`, `thesis`, `sections`, `source`, `created_at`)
and SupersessionRelation rows (`reason`, `ratified_at`) cannot prove:

- which candidate was reviewed;
- what the model proposed (prompt, adapter, raw output);
- what the steward accepted;
- whether it was edited.

#214 Decision 3 requires those distinctions. A small append-only receipt
(`blueprint_proposal_acceptances`, schema 21) links the resulting Blueprint
without adding any field to the Blueprint ontology.

- **Exact model acceptance:** `accepted_model`.
- **Edit:** `human`, with the model proposal preserved.

New Blueprint rows carry `source` `proposal-accepted` or `proposal-edited`.
Lineage grants them authorship **only** from a valid linked receipt. A
forged `proposal-accepted` row without one projects as `unknown` (tested).

### Portability, declared and not exported

WBS 1.x exports none of these:

- Blueprints and their links;
- ArchitectPlans;
- Blueprint supersession edges;
- Interpretations.

A receipt therefore cannot be restored with its closure. Per #214
("missing portable coverage = unsupported evidence") and #215, P8 declares
coverage and P10 round-trips it:

- receipts are not exported;
- `read_bundle` and `preview_restore` report
  `blueprint_proposal_acceptances: unsupported`, with the reason;
- restore creates none (P15).

**Owner decision.** Should Blueprint and Interpretation WBS coverage move from
P10 into an earlier packet?

## 3. Legacy `/api/architect/generate`: disposition reported, not changed

It persists model output directly (`source="ai-generated"`). It also silently
drops unresolvable references and commits the Blueprint before compiling the
plan. It is not a P8 path.

It is left **unchanged**:

- the Reader UI calls it from `index.html`, which holds unrelated uncommitted
  owner edits;
- disabling or delegating it would change a live product contract without
  authority.

`/api/pipeline/extract-blueprint` with `save:true` likewise stays unchanged.

**Recommendation.** When a P8 Reader surface exists, replace the UI's
architect-generate call with propose-and-review. Then default-disable both
legacy routes for the product flow, keeping them internal.

`extract_blueprint_from_text` is not reused: its `_call_provider` falls back
silently to a canned Blueprint, and it cites no evidence.

`/api/pipeline/ratify-blueprint` and `/api/pipeline/revise-blueprint` are
unchanged. The revise route still writes `steward-authored` successors after
the behavior-preserving helper refactor (F4).

## 4. Synthetic results (`research/blueprint_proposal/v1/`)

| Case | Outcome |
| --- | --- |
| P01 simple goal | 201. References resolve to the exposed Observations A:1, A:2, A:5. Generation wrote nothing |
| P02 grounded in Interpretations | 201. Cites I1, I2 and M1. The prompt labels I1 and I2 "steward-authored" and M1 "accepted model contribution" |
| P03 invented `O99` | 422 `PROPOSAL_REFERENCE_UNKNOWN`; no candidate |
| P04 excluded B Observation ID | 422 `PROPOSAL_REFERENCE_EXCLUDED`. B's text never appears in the prompt |
| P05 exact accept | 201. Source `proposal-accepted`, plan compiled, receipt `model_proposed_steward_accepted`. Lineage `accepted_model` for both the Blueprint and the receipt. Verification: `valid` / `verified` / `verified` / `preserved_not_replayed` |
| P06 edit and accept | 201. Source `proposal-edited`, receipt `model_proposed_steward_edited`, `edited: true`, proposal preserved. Lineage `human` |
| P07 discard | 200. No Blueprint and no receipt; a later accept is 404 `UNKNOWN_CANDIDATE`; workspace unchanged |
| P08 source excluded after generation | 409 `STALE_CANDIDATE`; nothing written |
| P09 predecessor revised through the legacy route | 409 `STALE_CANDIDATE`. The legacy successor is still `steward-authored` |
| P10 revise with a new Interpretation | 422 `REASON_REQUIRED` without a reason, then 201. The successor cites INEW, the edge reason is the steward's, the predecessor is unchanged, plan compiled. Verification passes |
| P11 model change_summary ≠ steward reason | The edge reason is exactly the steward's text. The receipt keeps the model's explanation separately |
| P12 model not installed | 409, no provider call, nothing written |
| P13 `thesis: null`, and prose | 422 `PROPOSAL_OUTPUT_INVALID`; 422 `PROPOSAL_OUTPUT_UNPARSEABLE` |
| P14 repeat accept, and repeat edit | 201, then 200 with the same receipt for both. One receipt, one Blueprint |
| P15 export and restore | No receipt component; coverage `unsupported` with the P10 reason; restore creates no receipt |
| F1 client substitution | 409 `CANDIDATE_MISMATCH`. Posting a Blueprint with `accept` is 400; nothing recorded |
| F2 edit cites excluded evidence the model never saw | 403, the existing scope refusal; nothing recorded |
| F3 default app | 403 `BLUEPRINT_PROPOSAL_DISABLED`, no provider call |
| F4 legacy revise parity | The legacy successor is still `steward-authored` |

### Laboratory correction during implementation

F2 first excluded document B **after** generation. That correctly produced 409
`STALE_CANDIDATE`, because B was exposed and therefore bound. The lab was
fixed to exclude B **before** generation, so it tests the frozen scenario: a
steward edit citing excluded evidence that was never exposed. No expectation
changed.

### Tests (`tests/test_blueprint_proposals.py`, 7)

- the dataset is reproduced;
- the production prompt equals the frozen policy;
- receipts are append-only and tamper-evident (Lineage diagnostic,
  verification `invalid`);
- a receipt leaves Lineage, and GET returns 404, when an exposed source is
  excluded, while the row is preserved;
- a source with no receipt projects as `unknown`;
- receipts are never P1 evidence and P1 decisions don't depend on them;
- the gate defaults to disabled.

**Test correction.** That P1 test first compared complete results with the
receipt table dropped. That also drops the **proof** of the Blueprint's
`accepted_model` label, so only that label differed: every availability,
status, reason and prerequisite was identical. It was restated to assert the
real invariant.

Six schema-20 pins were advanced to 21, as P3, P4 and P7 did.

### Full suite and dataset reproduction

- Full suite on a clean detached worktree of `9967255`: 2885 passed, 21
  skipped, 6 failed. The six failures are exactly the inherited Reader
  failures:
  - `test_reader_accessibility` ×2;
  - `test_reader_blueprint_workstation`;
  - `test_reader_record_view` ×2;
  - `test_reader_voice_profile`.

  The P7 closeout had 2878 passed. The 7 extra passes are the new P8 tests.
  No new failure was introduced.
- On the same worktree, all six datasets reproduce exactly:
  - P8 Blueprint proposal;
  - P7 steward-authored comparison;
  - P7 Layer 2;
  - P7 Layer 1;
  - P6 companion coach;
  - P5 synthetic study laboratory.
- The owner's uncommitted Reader changes (`hermeneia/web/static/index.html`,
  `tests/test_reader_context_navigation.py`) were never staged.

## 5. What P8 v1 does not demonstrate

- **Model competence.** Every output was scripted.
- **A Reader surface.** The API exists; the UI does not.
- **Portability.** Receipts are declared unsupported (§2).
- **Excluded inputs.** Proposals from Perspective receipts, accepted
  comparisons or field notes are not exposed in basis v1.
- **Basis size.** The basis is capped at 200 Observations and 100
  Interpretations. Larger studies are refused `BASIS_TOO_LARGE` rather than
  sampled.

## 6. Proposed frozen live-model evaluation protocol (not run; needs authorization)

### Freeze before any call

- **Admissible support sets.** For each live case (the P01, P02, P05 and P10
  intents, plus two new intents over the same corpus), freeze the records a
  proposal may cite for that intent, and the **required** records. For
  example, P10 must cite INEW.
- **Required successor content** for revise cases.
- **Thresholds**, below.
- **The harness**, which reuses `tests/blueprint_proposal_lab.py` setup with the
  production route and the gate enabled for evaluation only.

### Run

- local models only;
- `hermeneia-phi4-mini:latest` first; a larger model only with a separate
  download authorization;
- loopback only, synthetic workspaces, **no acceptance**;
- 3 samples per case, because the production path sets no temperature;
- every raw output preserved.

### Measures

| Measure | Definition |
| --- | --- |
| Structural refusal rate | unparseable or invalid outputs |
| Reference refusal rate | unknown or excluded references; governance catches these |
| Grounding coverage | sections citing at least one exposed record |
| Reference precision | cited records within the admissible set |
| Required-evidence recall | revise cases include their required new evidence |
| Authorship fidelity | claims do not present an accepted model contribution as the steward's own reasoning; checked against the frozen required labelling |
| Admitted but wrong | traceable proposals that pass governance but cite outside the admissible set or omit required evidence |
| Run-to-run variability | across the 3 samples |

### Proposed gate for enabling generation

All of the following, across all samples:

- structural refusal at most 0.10;
- reference refusal at most 0.10;
- grounding coverage at least 0.90;
- reference precision at least 0.80;
- required-evidence recall at least 0.80;
- admitted-but-wrong at most 0.15.

Otherwise generation stays disabled. Steward authoring and ratification are
unaffected.

P9 has not been started.
