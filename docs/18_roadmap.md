# Development Roadmap v3.0

**Status:** ACTIVE IMPLEMENTATION GUIDE  
**Synchronized:** 2026-08-29  
**Constitutional authority:** [`00_Constitution.md`](00_Constitution.md), [`01_Authority_Index.md`](01_Authority_Index.md), [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)  
**Current phase:** Validation through real use

The roadmap governs implementation priority, not constitutional truth. When this file conflicts with higher authority, higher authority controls.

For a dated snapshot of what is already implemented, read [`../IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md). Do not infer current completion from historical era descriptions alone.

---

## Development Gate

Before substantial implementation, classify the proposed work:

1. Is it an existing **Canonical Object**?
2. Is it a **Function** over authorized objects?
3. Is it a **Projection**?
4. Is it a **Derived Artifact**?
5. Is it **Configuration / execution infrastructure**?
6. Is it **Human Judgment / stewardship**?
7. Is it merely a **product/UX surface** over existing authority?

If none apply, stop and perform architectural review before implementation.

No implementation may silently introduce ontology, authority, or a new canonical pipeline stage.

Engineering priorities should be ordered by **proof value and demonstrated user need**, not by novelty or visual appeal.

---

## Completed Foundation

### Era I — Constitutional Foundation ✅

Established the governing architecture:

- Constitution
- Authority Index
- Constitutional Invariants
- First Principles
- architecture patterns and proofs
- evidence identity and provenance
- epistemic classification
- ArchitectPlan semantic-contract boundary
- auditability and monotonic governance
- provider-neutral execution principles
- regeneration / projection principles
- conservation of ontology

### Era II — Constitutional Engineering ✅

Demonstrated that the architecture could execute itself:

- deterministic evaluation functions
- Finding persistence and lineage
- Critic infrastructure
- Steward review and ratification flows
- provider-neutral Artist execution
- Architect compilation
- release/preservation infrastructure
- end-to-end traceability
- Workspace Bundle export/import/restore

### Era III — Investigation / Reader Workbench ✅ foundation, ongoing validation

The investigation layer moved from pipeline-first operation toward a Reader-centered workbench:

- Explorer / candidate interpretation workflows
- Reader-first shell
- Companion
- in-place Corpus Search
- attention timeline / Field Notes
- durable highlights and semantic capture
- governing-question compass
- question-relative Corpus/Lab framing
- Blueprint / Render / Critic workstation
- Draft Preview → Ratify → Record
- voice / ExpressionProfile work
- workspace lifecycle
- Perspective definitions/revisions and governed runs
- accessibility / focus / read-aloud capabilities

Era III is no longer "build Explorer next." Its current job is to prove that the entire investigation method works under sustained use.

---

# Current Phase — Validation Through Real Use

## Governing rule

```text
Use the product first.
Record friction when it appears.
Do not redesign from imagination.
```

The architecture has earned the right to be tested as a working instrument. New work should usually begin with an observed failure, recurring friction, missing bridge, or validation need.

---

## Track V1 — Reader durability and sustained-use quality — P1

Goal: make long reading, annotation, rereading, and manuscript work comfortable enough that the user can stay inside the text.

Current evidence-bearing work includes:

- readable projection of layout-heavy PDFs (#121)
- meaningful Field Notes cadence and reduction of stacked chrome (#126)
- authored chapter/section structure (#129)
- trustworthy source-locator Reader position / boundary crossing (#133)
- coherent bottom workstation behavior (#154)
- continued real-corpus pressure testing (#120)

Success is not "more Reader features." Success is fewer interruptions, clearer intent, and more time spent reading and thinking.

---

## Track V2 — Whole-study synthesis — P1

Goal: make the **whole accumulated study record** the useful unit of synthesis.

Key work:

- study-level synthesis over highlights, notes, questions, observations, buckets, and accepted model contributions (#110)
- Evidence Board and true study lineage (#111)
- visible bucket lenses and multi-bucket thematic reading (#152)
- preserve authorship provenance for model-derived contributions (#109)
- suggest structure without silently assigning it (#108 / #42)

Expected progression:

```text
read
→ capture freely
→ organize / regroup
→ inspect tensions and unused evidence
→ run bounded analyses over selected evidence groups
→ refine working Blueprint
→ commit governed revisions
```

Do not make the user re-enter the same evidence into each downstream stage.

---

## Track V3 — Scope, Perspective, and controlled inquiry — P1/P2

Goal: make the variables of an inquiry explicit enough that comparisons are meaningful.

Accepted conceptual composition:

```text
Scope
+ Question
+ Perspective
+ Model configuration
→ execution
→ evaluation
→ Steward outcome
```

Priorities:

- shared Scope semantics over existing material (#157)
- Perspective / Blueprint / Architect / ExpressionProfile separation (#156)
- governed Perspective runs and Ask the Room evolution (#99)
- preserve actual input boundaries and run identity

Do not create a canonical Scope object merely because the UI needs selection state. Preserve resolved Scope when it becomes causally important to an audited run.

---

## Track V4 — Provider/runtime control plane — P1/P2

Goal: let users deliberately control what executes without confusing runtime configuration with epistemic identity.

Issue #159 is the governing design issue for this track.

Required distinction:

```text
Connection
  ↓
Provider/runtime
  ↓
Model catalog
  ↓
Model configuration
  ↓
Default / assignment / per-run selection
```

Important remaining work includes:

- reconcile saved model configuration work from draft PR #165 onto current main
- complete safe credential persistence choices
- expose installed Ollama models accurately
- support explicit defaults / assignments / per-run override where appropriate
- record the exact configuration that actually executed
- keep secrets out of workspaces, exports, lineage, and research datasets

Do not silently switch models or download local models.

---

## Track V5 — Evaluation quality and deterministic instruments — P2

Goal: improve what Hermeneia can measure without pretending measurement is judgment.

Existing evaluation infrastructure should be expanded only where a bounded measurement contract is defensible.

Relevant work:

- interpretation-quality evaluation harness (#63)
- contradiction boundary design (#68)
- voice/profile adherence (#93)
- deterministic affect/style instruments (#155)

North star:

```text
Deterministic instruments measure.
Perspectives interpret.
Humans decide.
```

---

## Track V6 — Model Observatory / research analytics — P2

Issue #158 defines a future derived analytics surface over trustworthy run lineage.

It may analyze:

- provider/model/configuration identity
- usage, latency, cost, failures
- stewardship outcomes
- Perspective × model behavior
- Scope × model behavior
- matched controlled comparisons
- longitudinal model/version changes

Guardrails:

- no universal "best model" score
- always show denominators
- do not mix naturalistic history with controlled benchmarks without labeling
- aggregate only after granular run identity is preserved
- metrics summarize recorded behavior; they do not become canonical judgments

This track should not outrun the execution receipts and stewardship data it depends on.

---

## Track V7 — Product support and communication — P2

- human Developer/support channel (#160)
- live demonstration video
- pitch / institutional communication materials
- release documentation
- contributor/onboarding clarity

Support infrastructure remains outside the canonical epistemic pipeline.

---

# Release Gate — v1.0 RC

A stable release candidate should not be declared solely because the architecture is complete or the test suite is large.

Before v1.0 RC, demonstrate:

- clean install and first-run recovery
- stable named workspace lifecycle
- sustained Reader use on multiple real corpora
- trustworthy source/annotation provenance
- whole-study movement from accumulated evidence toward synthesis
- Blueprint → Architect → Artist → Critic → Steward execution
- explicit provider/model/runtime boundaries
- workspace export/import/restore confidence
- tests and representative smoke validation
- documentation synchronized with implemented reality

Communication should follow demonstrated capability rather than lead it.

---

# Research Horizon

Scientific and ecological research may continue in parallel when it does not destabilize product validation.

Possible research directions include:

- semantic contract fulfillment
- transmission fidelity
- model/Perspective interactions
- multilingual/cross-cultural stewardship
- deterministic interpretive instruments
- semantic entropy / information-theoretic analysis
- corpus-scale relationship discovery
- longitudinal model behavior

These remain analytical projections or research hypotheses unless explicitly elevated through constitutional process.

---

# Priority Rule

When choosing between a new feature and a recurring failure discovered during serious use, prefer the recurring failure unless the new feature is required to resolve it.

```text
Evidence before expansion.
Use before abstraction.
Small green slices before broad rewrites.
```
