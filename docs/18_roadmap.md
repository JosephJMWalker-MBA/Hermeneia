# Development Roadmap v2.0

**Status:** ACTIVE IMPLEMENTATION GUIDE  
**Constitutional authority:** [`00_Constitution.md`](00_Constitution.md), [`01_Authority_Index.md`](01_Authority_Index.md), [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)  
**Implementation status:** Era II — Constitutional Engineering in progress

---

## Development Gate

Before any implementation sprint, answer:

1. Is this a **Canonical Object**?
2. Is this a **Function**?
3. Is this a **Projection**?
4. Is this a **Derived Artifact**?
5. Is this **Human Judgment**?

If none apply, stop. Perform constitutional review before implementation.

The roadmap governs implementation order, not constitutional authority. Constitutional authority remains defined by the Constitution, Authority Index, and ratified amendments.

No implementation may introduce ontology not already authorized.

Engineering priorities should be ordered by **proof value**, not by UI appeal.

## Parallel Infrastructure Lane

Build, preservation, release, and packaging work may proceed in parallel when
it does not introduce ontology, storage authority, or pipeline stages.

The non-authoritative work plan is
[`Infrastructure_Engineering_Track.md`](Infrastructure_Engineering_Track.md).

This lane supports constitutional execution. It does not define constitutional
truth.

---

## Era I — Constitutional Foundation ✅

**Goal:** Define what Hermeneia is.

**Exit criterion:** The architecture exhibits closure under its current principles.

**Completed:**

- Constitution
- Authority Index
- Constitutional Invariants
- First Principles
- Architecture Patterns
- Architecture Proofs
- What Hermeneia Is
- Finding Specification
- Evaluation Function Specification
- Provider Ecology Foundation
- Workspace Projection Pattern
- Regeneration Principle
- Conservation of Ontology

---

## Era II — Constitutional Engineering ✅

**Goal:** Execute the Constitution without expanding it.

**Rule:** No implementation may introduce ontology not already authorized.

This era is not discovery. It is proof. The architecture is known. The task is to demonstrate that it can execute itself.

### Sprint E1 — First Evaluation Function

Build the first deterministic Evaluation Function with zero LLM dependency.

**Example: Structural Evaluation Function**

```
Input:  ArchitectPlan, RenderedNarrative
Output: Finding[]
```

This proves that the Critic layer is computational infrastructure, not another conversational agent.

**Milestone:** First canonical `Finding[]`.

### Sprint E2 — Finding Persistence

After ADR review:

- Ratify `Finding` (or retain `CriticReport` if appropriate)
- Add immutable storage
- Add lineage
- Add supersession behavior
- Add executable invariants

**Milestone:** First durable machine-generated evaluation object.

### Sprint E3 — Evaluation Function Ecology

Implement independent functions:

- Semantic
- Structural
- Provenance
- Accessibility
- Constitutional

Each function must be:

- orthogonal
- deterministic
- read-only
- bounded

No aggregation. No scoring. No recommendations.

### Sprint E4 — Projection Layer

Regenerate from canonical Findings:

- Audit Dashboard
- Trust Card
- Semantic Inspector

Nothing persisted. Everything disposable.

### Sprint E5 — Stewardship Layer

Introduce human governance:

- Steward decisions
- Review workflows
- Acceptance / rejection
- Human rationale

Machine evaluation ends. Human authority begins.

### Sprint E6 — Witness Layer

Formalize human understanding verification:

- Did the intended understanding reach the audience?
- Can an 8-year-old complete the task without assistance?
- Can an 80-year-old complete the task without assistance?

This is intentionally not reducible to computation.

### Sprint E7 — Ratification

Immutable governance artifacts:

- Ratification records
- Constitutional audit snapshots
- Human witness sessions
- Steward signatures

This completes the epistemic lifecycle.

---

## Era III — Investigation

**Goal:** Make Hermeneia useful for investigators who do not begin with a complete Blueprint.

This era recognizes that Hermeneia has crossed a threshold: the constitutional infrastructure
is sufficient, and the highest-leverage remaining work is lowering the barrier to inquiry.

**Central claim being proved:** An investigator can begin with an existing report, a loose
hypothesis, or raw observations, and Hermeneia will help them reconstruct, structure, and
audit their understanding — not assuming the Blueprint exists, but helping to build it.

**The missing cognitive role:**

```
Corpus
    │
    ▼
Explorer      ← Era III primary focus
    │
Candidate Interpretations
    ▼
Architect
    │
Blueprint
    ▼
Artist  →  Critic
```

Explorer is the role that produces candidate interpretations from evidence.
It does not make judgments. It surfaces possibilities for Steward review.

### Sprint E-III-1 — Explorer Phase 1 (Constitutionally Minimal)

**Requirements:**
- Input: observations, linked evidence, perspectives
- Output: candidate Interpretation rows with `evidential_status='speculative'`
- Prompt engineering only — no new tables, no schema changes
- Generate multiple candidate interpretations rather than a single best
- Include supporting observations and confidence estimate in output
- Present in existing Steward review UI: accept, amend, merge, reject, defer
- Preserve all constitutional invariants and provenance

**Success criteria:**
- No ontology changes
- No ADR required
- Existing interpretation review becomes useful for unexplored observations
- Explorer accelerates discovery while leaving judgment entirely with the human steward

### The Onboarding Horizon

The "Start From Existing Work" path (implemented in Era II) extracts Intent.
The Explorer (Era III) extracts Candidate Interpretations.
These are complementary. Together they produce:

```
Upload Report
    ↓
I think you're trying to establish: ...
I found these candidate interpretations: ...
I found these unresolved tensions: ...
Continue Investigation →
```

That is the eventual onboarding experience.

### Two Tracks

Era III divides naturally into two parallel tracks:

**Track A — Product**

Everything an investigator can use today:
- Explorer
- Better onboarding
- Existing-work workflow
- Improved UI
- Research notebook

**Track B — Research**

Everything that might become publications:
- Computational role prompting methodology
- Kernel hypothesis (the minimal understanding atom)
- Layer 4 — Purpose
- Cross-domain recurrence
- World-model reconstruction from corpora

These tracks should remain separate. Mixing them slows both.

---

## Era IV — Scientific Research

**Not implementation. Research.**

Possible directions:

- Shannon mutual information
- Kolmogorov complexity
- Minimum Description Length
- Semantic entropy
- Cognitive biodiversity metrics
- Artist ecology analysis
- Transmission fidelity studies

**Constraint:** These SHALL remain analytical projections unless explicitly elevated through constitutional process.

---

## Era IV — Ecological Expansion

Bring Your Own Provider.  
Bring Your Own Model.  
Bring Your Own Critic implementation.  
Bring Your Own Artist.  
Bring Your Own Steward tooling.

More precisely: Bring Your Own Participant. A Provider may represent a cloud service, an on-device runtime, a local model, a specialized execution environment, or a human. GPT, Claude, Gemini, Apple Intelligence, a local Llama, a human translator, a specialized medical model — they are all implementations of the same constitutional role. The Constitution doesn't care. The ecology simply gains another species.

The constitutional runtime asks only three questions:

- Do I have an ArchitectPlan?
- Do I have a RenderedNarrative?
- Can Evaluation Functions evaluate it?

Everything else is ecology.

The Constitution remains unchanged. The ecology grows around it.

---

## Legacy milestone mapping

The P0-A1, P0-A2, and P1 milestones from Roadmap v1.0 map as follows:

| v1.0 | v2.0 |
|---|---|
| P0-A1 — Specification Conformance | Era I — Constitutional Foundation ✅ |
| P0-A2 — Implementation Conformance | Era II, Sprints E1–E2 |
| P1 — Semantic Communication | Era II, Sprints E3–E7 |
