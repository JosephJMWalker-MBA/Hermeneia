# P8 disposition — portability, legacy risk, live diagnostic

**Status:** owner decisions of 2026-10-10 on draft PR #250 (#215 P8). P8 is
**not complete**. This record governs how P8 may be exposed. It amends neither
the frozen contract (`docs/design/blueprint-proposal-v1.md`) nor its corpus.

## 1. Portability: deferred to P10, gated before normal exposure

**Decision.** The complete Blueprint dependency chain is deferred to P10, as
planned in #215. The chain is:

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

## 2. Legacy model-direct write paths: a separate compatibility and governance risk

**Decision.** This packet changes neither `/api/architect/generate` nor the
existing Reader UI. Their behavior is recorded here as risk **R-P8-LEGACY-1**.

Hermeneia **is not free of model-direct canonical writes** while these routes
stay accessible. #215's P8 gate ("No provider/model path can directly mutate
canonical Blueprint state") holds for the **P8 routes only**.

### `/api/architect/generate`

Called by the committed Reader UI (`index.html`, the `fetch('/api/architect/generate'…)` call).

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
- **Not atomic.** The Blueprint and links commit before the plan is compiled.
  A compile failure leaves a Blueprint without a plan.
- **Evidence selection** filters `excluded_from_analysis` directly rather than
  using the Lineage eligibility projection that P8 uses.

### `/api/pipeline/extract-blueprint` with `save:true`

The Reader UI calls this route with a caller-controlled `save` flag.

- It persists the model's extraction as `source="extracted"` without review,
  through the canonical `_persist_exact_blueprint_and_compile` helper.
- `extract_blueprint_from_text` falls back silently to a canned Blueprint when
  the provider fails.

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

Until then, R-P8-LEGACY-1 stays open.

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
