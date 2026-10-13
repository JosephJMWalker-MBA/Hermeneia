# P8 disposition — portability, legacy risk, live diagnostic

**Status:** owner decisions of 2026-10-10 on PR #250 (#215 P8). This record
governs how P8 may be exposed. It amends neither the frozen contract
(`docs/design/blueprint-proposal-v1.md`) nor its corpus.

## 0. Closeout disposition (owner, 2026-10-10)

```text
GOVERNANCE_COMPLETE / GENERATION_NOT_READY / RELEASE_GATED
```

**Demonstrated:**
- exact proposal binding;
- steward acceptance;
- revision provenance;
- local durability;
- fail-closed behavior.

**Not demonstrated:** trustworthy natural-language Blueprint generation.

PR #250 merges as **gated implementation infrastructure**, not as a released
natural-language Blueprint assistant. Generation remains disabled by default.

**Key finding.** In the 18-call live evaluation, which is preserved unchanged,
structurally valid citations did not establish semantic support:
- pooled reference precision was 1.0;
- only 2 of 16 graded claims were supported;
- every admitted proposal flattened an open matter.

**Release blockers.** All must clear before generation is enabled for
ordinary use:

| Blocker | State |
| --- | --- |
| Model competence | Not demonstrated (§3) |
| P10 portability | Deferred (§1) |
| Reader review UI | Absent |
| Legacy direct-write remediation | Open: R-P8-LEGACY-1, #251 (§2) |
| Steward authorization to enable | Not given |

**Prompt v1.1 is not run.** The observed copying of `I1`/`I2` from the prompt
example is a specific design hypothesis. Removing that example would not
establish semantic competence. Any future experiment needs:
- a separately frozen policy;
- an appropriately independent evaluation set, not the six cases used here.

## 1. Portability: deferred to P10, gated before normal exposure

**Decision.** The complete Blueprint dependency chain is deferred to P10, as
planned in #215, and the obligation is recorded on #215. The chain is:

- Interpretations;
- Blueprints;
- ArchitectPlans;
- Blueprint supersessions;
- Blueprint proposal acceptance receipts.

P8 must not be exposed for normal use before a **portability gate** passes:
the chain round-trips through WBS with its closure intact.

| Obligation until the gate passes | Where it holds |
| --- | --- |
| Blueprint proposal acceptance history is explicitly declared **unsupported** by WBS | `read_bundle` and `preview_restore` coverage report `blueprint_proposal_acceptances: {"status": "unsupported", "reason": …P10…}` (`hermeneia/workspace/restore.py`, `PORTABILITY_REASON`). WBS spec §6.2 |
| Nothing implies that export/restore preserves that history | Receipts are never written to a bundle; restore never creates one (P15). P8 has no UI surface that could claim otherwise. WBS spec §6.2 corrects the §6 mapping row for `interpretations`, which the WBS 1.x exporter does not implement |
| P8 generation stays disabled by default | `BLUEPRINT_PROPOSAL_GENERATION` defaults to `disabled`. Only `HERMENEIA_BLUEPRINT_PROPOSALS=experimental` or explicit config enables it (tested) |
| Local durability is not portable recoverability | See below |

**Local durability is not portable recoverability.** An accepted proposal is
durable in its local `workspace.db`:

- append-only;
- tamper-evident;
- Lineage-projected;
- independently verifiable.

None of that survives export. A workspace restored from a bundle has no
receipts, and none of the Blueprints, plans, supersessions or Interpretations
those receipts close over. So a receipt proves provenance only inside the
database that recorded it. Backing up or moving a study through WBS **loses**
that provenance.

**Preserved spec discrepancy.** The WBS spec's §6 table maps `interpretations`
to `reports/interpretations.json`, but the WBS 1.x exporter never wrote them.
This predates P8. It is recorded in WBS spec §6.2 and stays part of the P10
obligation until export coverage matches the spec, or the spec is corrected by
decision.

## 2. Legacy model-direct write paths: a separate compatibility and governance risk

**Decision.** This packet changes neither legacy route nor the existing Reader
UI. Their behavior is recorded as risk **R-P8-LEGACY-1**, tracked in **#251**.
#251 has:
- callers and line references;
- a reproduction on synthetic workspaces;
- authority violations;
- compatibility implications;
- migration options;
- closure criteria.

Recording the risk does not resolve it.

Hermeneia **is not free of model-direct canonical writes** while these routes
stay accessible. #215's P8 gate ("No provider/model path can directly mutate
canonical Blueprint state") holds for the **P8 routes only**.

### `/api/architect/generate`

Called by the Reader Architect panel's "Generate Blueprint →" button
(`e10GenerateBlueprint()` in `index.html`).

- **Model-to-canonical write.** It inserts the model's Blueprint directly
  (`source="ai-generated"`), with links and an ArchitectPlan, and no steward
  review.
- **Unresolved references are dropped or misresolved.** Each observation
  reference is reduced to its first digit run (`re.search(r"(\d+)")`):
  - an out-of-range number (`O99`) is silently dropped;
  - a reference of the wrong kind can resolve to an unrelated Observation
    (`I3` in `obs_refs` becomes Observation 3).

  Interpretation references are matched by an 8-character ID prefix and
  otherwise dropped.
- **Unshown records can be bound.** An in-range number the model was never
  shown binds a real Observation. `OBS-n` is positional across all documents,
  and the prompt samples at most 40 Observations.
- **Not atomic.** The Blueprint and links commit before the plan is compiled.
  A compile failure leaves a Blueprint without a plan (reproduced: HTTP 500,
  Blueprint kept, no plan).
- **Evidence selection** filters `excluded_from_analysis` directly rather than
  using the Lineage eligibility projection that P8 uses.

### `/api/pipeline/extract-blueprint` with `save:true`

The Reader calls this route in two steps:
- "Extract Intent Hypothesis" calls `obExtractBlueprint(false)`, a preview;
- "Ratify & Save Blueprint →" calls `obExtractBlueprint(true)`.

- **`save:true` re-runs the extraction.** It persists that new output as
  `source="extracted"` through `_persist_exact_blueprint_and_compile`, so the
  steward's ratification commits a model output the steward never saw
  (reproduced).
- **A canned Blueprint can be committed with no model run.**
  `extract_blueprint_from_text` returns it for the `null` provider (the UI
  default) and for any client interface it does not recognize, with no signal
  that no model ran.

  *Correction:* earlier P8 records, including this one before 2026-10-10,
  described this as a fallback "when the provider fails". That wording was
  inaccurate and is corrected here; the historical records are left as
  written.

### Boundary with P8

- The P8 routes do not call either legacy route, its inline persistence,
  `extract_blueprint_from_text` or `_call_provider` (tested).
- P8 commits only through `_persist_exact_blueprint_and_compile` and
  `_revise_blueprint_in_transaction`. Both run inside one `BEGIN IMMEDIATE`
  transaction, together with the receipt and a Lineage check.
- The first of those helpers is the canonical ratification helper, also used
  by steward ratification and by the legacy `extract-blueprint save:true`. It
  is a persistence seam, not a model path.

**Recommended remediation (separate decision).**
1. Replace the Reader's architect-generate and `extract-blueprint save:true`
   calls with P8 propose-and-review, once a P8 Reader surface exists.
2. Then default-disable both legacy write modes for the product flow.

Until then, R-P8-LEGACY-1 (#251) stays open. Its migration options and
closure criteria are in the issue.

## 3. Live diagnostic

Owner-authorized on 2026-10-10:

- one bounded diagnostic with installed `hermeneia-phi4-mini:latest`;
- six cases, three samples each;
- synthetic workspaces, no acceptance.

It runs under the frozen protocol
`tests/fixtures/blueprint_proposal/v1/live_evaluation_protocol.json`, which is
committed before any model call. This supersedes, for that run only, contract
§10's "no live model runs in P8 v1".

**Passing the diagnostic does not authorize enabling generation for ordinary
users.** That still requires:
- the portability gate;
- a Reader surface;
- the owner's decision.

**Verdict (2026-10-10): `P8_GOVERNANCE_READY_GENERATION_NOT_READY`.** On all
18 runs:
- no governance defect occurred;
- nothing was written;
- every refusal reproduced.

All five generation criteria failed:
- only 4 of 18 outputs were admitted;
- 7 runs invented I-labels, all in cases with no exposed Interpretations;
- no admitted sample passed its per-sample criteria;
- every admitted sample flattened an open matter;
- two admitted samples carried severe errors.

Generation stays disabled; the gate is unchanged. The evidence is
`docs/verification/2026-10-10-p8-live-diagnostic.md` and
`research/blueprint_proposal_live/phi4-mini/`.

## 4. Correction: acceptance atomicity (2026-10-10, found under #251)

P8 contract invariant 8 says the Blueprint, ArchitectPlan, edge and receipt
commit atomically, or nothing commits. **It did not hold at merge (`09b72cc`)
for create-mode acceptance.**

`_persist_exact_blueprint_and_compile` called `ensure_architect_tables()`
after writing the Blueprint and its links, and that function commits through
`executescript()`. With a failure injected in `store_receipt` or plan
compilation, the accept route answered 500 but left a committed
`proposal-accepted` Blueprint with no plan and no receipt. Lineage would
project that Blueprint as `unknown`. The revise path was unaffected.

- **Coverage gap.** The P8 corpus never injected a failure after persistence,
  which is why the tests missed it.
- **Witnesses:** `tests/test_r251_legacy_blueprint_witnesses.py`
  (`test_r3_p8_acceptance_commits_blueprint_plan_and_receipt_together`).
- **Repair:** commit `7a403db` on branch `r251-legacy-blueprint-remediation`,
  not yet merged. The table check now runs before the first write and never
  inside a caller-owned transaction.
- **Merge state.** Until that repair merges, `main` carries the defect. P8
  generation is disabled by default, so acceptances can only occur where it
  has been explicitly enabled.

The historical records (contract, 2026-10-08 verification) are left as
written.
