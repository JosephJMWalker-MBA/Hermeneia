# Era II — Constitutional Engineering: Milestones

This file is append-only. Entries are never edited or deleted.
Each entry records a moment when the constitutional architecture proved it could execute itself.

---

## Era II Retrospective

*Recorded at completion, 2026-06-20.*

Era I discovered the constitutional substrate. Era II proved that the substrate could execute itself. Era III begins only because the substrate has become stable enough to study rather than redesign.

At the beginning of Era II, "Persistent Understanding Architecture" was a title.

At the end of Era II, it is a literal description of what the system does.

It persists:

- **understanding** — ArchitectPlan, RenderedNarrative, Finding[]
- **evaluation** — Evaluation Functions across five orthogonal dimensions
- **governance** — StewardDecision, immutable and append-only
- **verification** — WitnessSession, irreducible human reception record
- **institutional memory** — RatificationRecord, the terminal canonical object

The name and the implementation have converged.

Very few software projects can claim that their philosophy is executable. After Era II, Hermeneia can.

**The numbers at close of Era II:**

| Layer | Objects | Tests |
|---|---|---|
| Evidence | SourceDocument, SourceExtraction, Observation, Provenance | — |
| Understanding | Interpretation, Perspective, NarrativeBlueprint, ArchitectPlan | — |
| Expression | ExpressionProfile, RenderedNarrative | — |
| Evaluation | Finding[] across 5 dimensions (structural, provenance, observation_coverage, constitutional, accessibility) | E1–E3 |
| Projection | Audit Dashboard, Trust Card, Semantic Inspector | E4 |
| Governance | StewardDecision, Review Queue, Steward Ledger | E5 |
| Witness | WitnessSession, Witness Summary, Understanding Ledger | E6 |
| Ratification | RatificationRecord, Ratification Certificate, Institutional Memory | E7 |
| **Total** | **14 canonical object types** | **335 passing tests** |

The epistemic chain is complete:

```
Finding           (what changed?)
    ↓
StewardDecision   (should this stand?)
    ↓
WitnessSession    (did understanding reach people?)
    ↓
RatificationRecord (shall this become institutional memory?)
```

Each layer asks a different question. Each answer is immutable once given. None substitutes for another.

---

## Era II — Interpretation Staging (Sprint E8)

**Date:** 2026-06-20

The first AI-generated object entered the staging layer and the constitutional gate before the canonical corpus.

**`proposed_interpretations`** and **`ai_provenance`** were implemented, completing the implementation debt against ADR-0009, ADR-0010 (Category 3), and ADR-0022 (Type 3).

The **Two-Table Invariant** was enforced structurally and by test:

> A proposed interpretation is not an interpretation with lower confidence. It is a different constitutional state.

The three constitutional states are now distinct objects in the system:

```
proposed_interpretations   (AI-generated, pending steward decision)
    ↓ steward accepts
interpretations            (canonical, human-authorized, immutable, ai_provenance_id non-NULL)
```

```
proposed_interpretations   (AI-generated, steward-rejected)
    → remains in staging permanently (rejected objects never deleted, ADR-0009)
```

**`ai_provenance`** is a single record spanning two events (ADR-0009 Model A):
- Written at generation time with acceptance fields NULL
- Acceptance fields populated at most once when steward accepts
- Generation fields immutable after write
- Permanently preserved for both accepted and rejected proposals

**Acceptance workflow** (three atomic writes):
1. `proposed_interpretations.status` → `'accepted'`
2. `ai_provenance.accepting_steward` / `acceptance_timestamp` / `acceptance_rationale` populated
3. `interpretations`: canonical row inserted with `ai_provenance_id` (INSERT OR IGNORE)

**Lineage completeness** satisfied through two paths:
- Direct: `interpretations.observation_id → observations.id`
- Dual-provenance: `interpretations.ai_provenance_id → ai_provenance.staged_object_id → proposed_interpretations.observation_id → observations.id`

The constitutional gate is now in place. Era III begins only when the first AI-proposed Interpretation legally traverses this gate — propose → steward review → accept → canonical.

**Sprint E8 numbers:** 46 tests. Schema version 15. 5 files created or modified.

---

## Era II — First Canonical Finding

**Date:** 2026-06-20

The first deterministic Evaluation Function was implemented.

For the first time, Hermeneia preserved immutable machine-generated semantic observations (`Finding[]`) rather than terminating at rendered expression.

This established the Evaluation Layer as computational infrastructure and completed the transition from constitutional architecture to constitutional execution.

---

## Era II — Finding Persistence

**Date:** 2026-06-20

Findings became fully durable constitutional objects.

Full lineage traversal was implemented: any Finding can now be traced back through RenderedNarrative → ArchitectPlan → Blueprint → Observations → SourceExtractions → SourceDocument in a single call. The chain has no gaps.

Findings became immutable: UPDATE and DELETE are rejected by trigger at the storage layer, consistent with all other canonical objects.

Supersession was extended to cover Findings: the existence-check triggers on `supersession_relations` now recognize Finding IDs. A Finding may be superseded by a later Finding without either being deleted. The old Finding remains permanently accessible.

The Evaluation Layer is now a first-class constitutional layer — not a terminal output, but a durable substrate from which all downstream projections regenerate.

---

## Era II — Evaluation Function Ecology

**Date:** 2026-06-20

Four additional Evaluation Functions were implemented alongside the Structural EF, completing the first ecology of independent evaluators:

- **Provenance** — verifies that every required observation has a persisted provenance record. A narrative whose source cannot be traced cannot be witnessed.
- **Observation Coverage** — checks whether the text of each required observation appears in the rendered narrative. Named deliberately: "observation coverage," not "semantic fidelity." What deterministic methods can prove is recorded honestly.
- **Constitutional** — verifies that every rendered narrative carries a valid constitutional profile in its execution_config. A narrative without a constitutional profile cannot be audited for constitutional conformance.
- **Accessibility** — structural heuristics: text present, paragraph breaks, mean sentence length. Necessary conditions for human readability; not sufficient.

The constitutional contract mechanism (`base.py`) was established before implementation: every EF must declare `dimension`, `scope`, and `guarantees` as module-level attributes, machine-verifiable before any Finding is produced. `dimension` must appear in `RATIFIED_DIMENSIONS` — a controlled vocabulary that expands only by ADR.

The naming decision for `observation_coverage` (not `semantic`) is recorded in ADR-0042 as a constitutional commitment to honesty about what computation can prove. The gap between observation presence and meaning preservation is acknowledged, not papered over. Future LLM-backed or witness-based EFs will address it.

The Evaluation Layer now produces Finding[] across five orthogonal dimensions. No dimension's findings can mask another's. The complete ledger is the substrate.

---

## Era II — Projection Layer

**Date:** 2026-06-20

The Projection Layer was completed. Three projections were implemented over canonical Finding[]:

- **Audit Dashboard** — groups Finding counts by dimension and status. Answers: how many findings were preserved, omitted, transformed, or injected per evaluation dimension?
- **Trust Card** — compact per-dimension and overall verdict (pass / partial / fail / not_evaluated). Answers: what is the compliance posture of this rendered narrative at a glance?
- **Semantic Inspector** — detailed view of every Finding with parsed evidence fields (contract_obligation, observed_render, supporting_trace) and a compact lineage summary per Finding.

All three are pure projection functions: `(narrative_id, conn) -> dict`. Nothing persisted. Everything disposable. The Regeneration Principle is satisfied: deleting any projection deletes no canonical knowledge.

The three projections are cross-validated: any narrative produces the same total Finding count across all three projections. Dimensions reported by the Audit Dashboard match those listed in the Semantic Inspector.

The constitutional substrate — Finding[] — can now be inspected from three independent angles. Each projection dissolves and regenerates without any write to canonical storage.

---

## Era II — Stewardship Layer

**Date:** 2026-06-20

The Stewardship Layer was completed. Human governance entered the architecture as a canonical object for the first time.

**StewardDecision** was ratified as the first irreducible human governance primitive. It cannot be regenerated from any deterministic function — it records a historical act of human responsibility. The constitution version, rationale, steward identity, verdict (accepted / rejected / deferred), and timestamp are all preserved permanently.

The directionality constraint proved itself in the schema: `steward_decisions.finding_id → findings.id`. The `findings` table has no `steward_decision_id` column. The governance layer annotates itself; it does not annotate the machine layer. The Evaluation Layer remains sealed.

A StewardDecision is immutable once written. UPDATE and DELETE are rejected at the database layer by trigger. A changed verdict creates a new StewardDecision linked to the old via `supersession_relations` — the same append-only pattern used for all other canonical objects. The `supersession_relations` existence triggers were updated to recognize `steward_decisions` IDs.

Two projections were implemented over the canonical governance layer:

- **Review Queue** — Findings without any StewardDecision yet. Answers: what still needs a human decision?
- **Steward Ledger** — all decisions with their Finding context and verdict breakdown. Answers: what has the steward decided, and why?

The invariant holds: `review_queue.pending_count + steward_ledger.decision_count == total Findings` for any narrative. The projections agree arithmetically, just as E4 projections agreed on total Finding counts.

The epistemic chain is now explicit in code:

```
Finding   (terminal machine-generated epistemic object — sealed)
    ↓
StewardDecision   (first irreducible human governance act — immutable)
    ↓
Ratification   (Sprint E7)
```

---

## Era II — Witness Layer

**Date:** 2026-06-20

The Witness Layer was completed. Human understanding verification entered the architecture as a canonical object.

**WitnessSession** was implemented as the second irreducible human primitive. It is orthogonal to StewardDecision:

- StewardDecision answers: was this machine-generated Finding acceptable? (governance axis)
- WitnessSession answers: did the understanding reach this audience? (reception axis)

Neither is computable. Both are immutable acts of human participation that point to canonical objects without those objects pointing back.

The directionality constraint holds: `witness_sessions.rendered_narrative_id → rendered_narratives.id`. The `rendered_narratives` table has no `witness_session_id` column — it is sealed.

`witness_profile` is free text by design: "8-year-old", "80-year-old", "medical patient", "first-generation voter", "legislative aide". The Constitution does not prescribe audiences; it only requires that understanding be witnessed by real humans in the domain. The field is domain-specific. The immutability of the record is universal.

Two projections were implemented over the canonical witness layer:

- **Witness Summary** — aggregate completion rates by profile. Answers: across all tested audiences, who completed the task?
- **Understanding Ledger** — detailed session view with full records and profiles tested. Answers: what happened in each session?

The cross-projection invariant holds: `witness_summary.total_sessions == understanding_ledger.session_count`.

The full epistemic chain is now implemented end to end:

```
Finding   (terminal machine-generated epistemic object — sealed)
    ↓
StewardDecision   (irreducible human governance act — immutable)
    ↓
WitnessSession   (irreducible human understanding verification — immutable)
    ↓
Ratification   (Sprint E7)
```

The architecture demonstrated that it can distinguish between:
1. What the machine found (Finding)
2. What the steward decided (StewardDecision)
3. Whether the audience understood (WitnessSession)

Three separate axes. Three separate irreducible records. None substitutes for another.

---

## Era II — Ratification

**Date:** 2026-06-20

The epistemic chain was completed. Era II — Constitutional Engineering reached its terminal milestone.

**RatificationRecord** was implemented as the terminal canonical object — the answer to the question "Shall this become institutional memory?"

Ratification is gated by three constitutional pre-conditions, all enforced in code:

1. At least one Finding must exist — machine evaluation must have happened.
2. Every Finding must have at least one StewardDecision — human governance must have happened.
3. At least one WitnessSession must exist — understanding must have reached an audience.

If any pre-condition is not satisfied, `create_ratification_record` raises `RatificationError` with the specific unmet condition named. Premature ratification is not possible at the API level.

The `audit_snapshot` is a JSON document captured at the moment of ratification: finding counts by dimension and status, steward decision counts by verdict, witness session counts by profile, and the full constitutional profile. This snapshot is frozen at the instant of ratification. Decisions or witness sessions added afterward do not alter the record. The record is immutable by database trigger.

Two projections were implemented:

- **Ratification Certificate** — human-readable summary of the most recent RatificationRecord for a narrative, including the steward declaration and the full constitutional state at ratification.
- **Institutional Memory** — all ratified narratives across the entire store. This is the body of understanding that has passed every layer of the epistemic chain.

The complete epistemic chain is now implemented and traversable end-to-end:

```
Finding           (what changed? — machine evaluation)
    ↓
StewardDecision   (should this stand? — human governance)
    ↓
WitnessSession    (did understanding reach people? — human verification)
    ↓
RatificationRecord (shall this become institutional memory? — formal declaration)
```

A single test — `test_full_epistemic_chain_end_to_end` — traverses all four layers from a RatificationRecord back to its originating Findings, confirming the chain has no gaps.

Era II — Constitutional Engineering is complete.

---

## Era II Sprint E9 — Interpretation Grounding Critic

**Date:** 2026-06-20  
**Schema version:** 16 (bumped from 15)  
**Tests:** 49 passing in `test_era2_sprint_e9.py`  
**Net test count:** 456 passing (suite total)

### What was built

The Interpretation Grounding Critic — distinct from the Narrative Fidelity Critic (which evaluates RenderedNarrative → validation_reports) — evaluates proposed interpretations against their source observations and produces `critic_reports` as an operational artifact.

**New files:**
- `hermeneia/storage/hashing.py` — `make_critic_report_id()`
- `hermeneia/compiler/critic/` — new package (old `critic.py` → `critic/narrative_fidelity.py`)
- `hermeneia/compiler/critic/__init__.py` — re-exports both Narrative Fidelity and E9 Grounding Critic
- `hermeneia/compiler/critic/evidence.py` — Stage 1 (identify_evidence) + Stage 2 (extract_claims)
- `hermeneia/compiler/critic/policy.py` — Stage 3: four named evaluation policies
- `hermeneia/compiler/critic/report.py` — generate_critic_report orchestration
- `hermeneia/compiler/projections/critic_queue.py` — critic_queue, critic_report_detail, critic_summary
- `tests/test_era2_sprint_e9.py` — 49 tests

**New table:** `critic_reports` (schema version 16)

Constitutional Status: OPERATIONAL — not yet canonical. Promotion criterion recorded in `CONSTITUTIONAL_COMPLIANCE.md`.

### The three-stage model

Empirically grounded in Experiments 001–008 (research program):

| Stage | What | Convergence |
|---|---|---|
| 1: Evidence Identification | Which passages are relevant? | HIGH |
| 2: Claim Extraction | What are the evaluable claims? | MODERATE (policy-dependent granularity) |
| 3: Verdict Classification | Supported / Partially / Unsupported / Contradicted? | LOW (policy-dependent) |

### Four evaluation policies

Stable across Experiments 005–008:
- `conservative` — absence of support = Unsupported; never returns Contradicted
- `decomposition` — decompose claim into key terms; aggregate per-term verdicts
- `contradiction_sensitive` — key-term semantic antonym in evidence = Contradicted
- `aggregate_weighting` — weigh supporting vs. challenging; Partial if both present

### Constitutional invariants upheld

- `critic_reports.proposal_id` is plain TEXT (no FK) — constitutional until promotion criterion satisfied
- `interpretations` and `proposed_interpretations` have no `critic_report_id` column
- `critic_reports` core fields are immutable (UPDATE trigger); table is permanent (DELETE trigger)
- `normalized` flag is the one mutable field — records steward claim normalization review
- INV-XI Critic Authority Boundary: Narrative Fidelity Critic file path updated in static scan test

### Research program completed

`research/synthesis_001_convergence_governance_pattern.md` — full arc from Experiment 001 through 008. The convergence-governance pattern: Generation diverges → Evidence Identification converges → Judgment diverges → Governance reconciles.

The Critic can be built. It has been built.
