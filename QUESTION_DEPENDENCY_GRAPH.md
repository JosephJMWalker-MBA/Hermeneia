# QUESTION DEPENDENCY GRAPH
### Hermeneia Ratification Roadmap

**Purpose:** This document analyzes every open question in `EPISTEMIC_BACKLOG.md`, identifies prerequisite relationships, determines which questions can be answered independently, and proposes the smallest sequence of ratification milestones that enables implementation to begin while minimizing future ontology drift.

**This document does not answer any question.** It maps the terrain. The answers belong to ADRs.

**Authority:** Same hierarchy as `EPISTEMIC_BACKLOG.md`. Research literature is cited where it illuminates dependency structure. It is never cited as a resolution.

**How to read this document:**
- A question in Milestone N cannot be ratified until all questions in Milestones 0 through N-1 that it depends on are ratified.
- Questions within the same milestone have no dependency on each other and can be ratified in parallel or in any order.
- A milestone is complete when all questions in it have a ratified ADR.
- Implementation corresponding to a milestone may begin only after the milestone is complete.

---

## Analysis: Prerequisite Relationships

The full dependency graph was derived by reading `EPISTEMIC_BACKLOG.md` and tracing every `Dependencies:` field transitively. The result is reproduced here as a structured analysis rather than a visual graph, because dependency graphs degrade badly in ASCII and are better expressed as tables with clear prose.

### Questions with no upstream dependencies

These questions can be answered before anything else. They are the natural starting point for a ratification session.

| Question | Why it is independent |
|---|---|
| **Q-P0-001** — What constitutes an Observation? | The foundational question. No question can be ratified until this is ratified. It has no prerequisites itself. |
| **Q-P0-008** — What is ContinuityNode? | A binary classification: does this object have a definition or should it be removed? Requires no ontology knowledge. |
| **Q-P1-007** — Is Manifest a canonical ontology object? | An administrative/architectural classification question. Independent of all semantic questions. |
| **Q-P5-003** — Should provenance be tracked for AI-generated objects? | A constitutional policy question. Can be answered from Article VI alone, before any schema is defined. |
| **Q-P6-001** — What decisions must always remain human? | A constitutional enumeration question. Can be answered directly from the Philosophy, Axioms, and Constitution. Requires no ontology. |

These five questions constitute the **first ratification session**. They should be addressed by the architect and primary steward before any engineering begins.

---

## Ratification Milestones

### Milestone R0 — The Foundation ✅ COMPLETE (2026-06-18)

**Complete before any other milestone begins.**

| Question | ADR | Status |
|---|---|---|
| Q-P0-001: What constitutes an Observation? | [ADR-0006](docs/adr/ADR-0006-observation-definition.md) | **Ratified** 2026-06-18 |
| Q-P0-008: What is ContinuityNode? | [ADR-0007](docs/adr/ADR-0007-continuity-node.md) | **Ratified** 2026-06-18 |
| Q-P1-007: Is Manifest a canonical ontology object? | [ADR-0008](docs/adr/ADR-0008-manifest-classification.md) | **Ratified** 2026-06-18 |
| Q-P5-003: Should provenance be tracked for AI-generated objects? | [ADR-0009](docs/adr/ADR-0009-ai-provenance-policy.md) | **Ratified** 2026-06-18 |
| Q-P6-001: What decisions must always remain human? | [ADR-0010](docs/adr/ADR-0010-human-only-decisions.md) | **Ratified** 2026-06-18 |

**Implementation unlocked by R0:** The `ontology/base.py` `HermeneiaObject` class. The `storage/` schema initialization. The `validation/constitution.py` skeleton. **Milestone R1 may now begin.**

**All five R0 questions were answered in Session 001 (2026-06-18).** The Observation boundary was resolved with full precision: malformed sentences are valid Observations, sentences spanning paragraph breaks produce one Observation, footnotes produce independent Observations with separate Provenance. See ADR-0006 Edge Cases section.

---

### Milestone R1 — Provenance and Claim Primitives ✅ COMPLETE (2026-06-18)

**Begins after R0 is complete.**

| Question | ADR | Status |
|---|---|---|
| Q-P0-002: What is the relationship between Observation and Claim? | [ADR-0011](docs/adr/ADR-0011-claim-is-not-first-class.md) | **Ratified** 2026-06-18 |
| Q-P5-001: What is the atomic provenance unit? | [ADR-0012](docs/adr/ADR-0012-atomic-provenance-unit.md) | **Ratified** 2026-06-18 |
| Q-P5-002: What level of provenance granularity best balances reproducibility and practicality? | [ADR-0013](docs/adr/ADR-0013-provenance-granularity.md) | **Ratified** 2026-06-18 |
| Q-P1-005: What is the smallest epistemic object? | [ADR-0014](docs/adr/ADR-0014-smallest-epistemic-object.md) | **Ratified** 2026-06-18 |

**Key decisions made in R1:**
- Claim is NOT a first-class ontology object. Interpretation serves this role.
- Q-P1-001 (Should Claim exist independently?) is closed by ADR-0011.
- Atomic provenance unit: the sentence. One Observation = one Provenance record.
- Normative Provenance fields: `source_document_hash + page + paragraph + sentence`.
- Source documents must be registered with a SHA-256 hash before compilation.
- Mutable sources require a frozen snapshot at compile time.
- The sentence is the smallest epistemic object. Observations carry read-only adjacency references (`preceding_observation_id`, `following_observation_id`) for field-layer navigation.

**Implementation unlocked by R1:** The `Observation` class fields. The `Provenance` class fields. The complete `.herm` SQLite schema for `observations`, `provenance`, and `source_documents` tables. The `storage/repository.py` append-only insert methods. The `compiler/observation_compiler.py` structural skeleton (no LLM imports). **Milestone R2 may now begin.**

---

### Milestone R2 — Interpretation and Perspective Primitives

**Begins after R1 is complete.**

| Question | Why now | Depends on |
|---|---|---|
| Q-P0-003: What distinguishes Interpretation from Perspective? | This is the second most foundational question in the backlog after Q-P0-001. Until Interpretation and Perspective are distinguished, the Hermeneutic Field cannot be designed, Perspective Debt cannot be formulated, and the Accumulation axiom (Axiom 3) cannot be enforced computationally. | Q-P0-001, Q-P0-002 |
| Q-P1-001: Should Claim exist independently from Observation? | The answer directly determines whether `Interpretation` objects contain embedded Claims or reference them externally. Must be ratified before Interpretation schema is designed. | Q-P0-001, Q-P0-002 |

**Note on sequencing within R2:** Q-P0-003 and Q-P1-001 are mutually reinforcing. They should ideally be ratified in the same session, because the answer to one constrains the answer to the other. If Claim is a first-class object (Q-P1-001 = yes), Interpretation becomes a container for Claims with a declared Perspective. If Claim is not a first-class object (Q-P1-001 = no), Interpretation must carry more internal structure to preserve provenance granularity.

**Implementation unlocked by R2:** `Concept` class fields (Concepts are derived from Observations and grouped by emerging Interpretations). `Relationship` class fields. `field/` package structural skeleton.

---

### Milestone R3 — Reflection, Dialogue, and Canonical Object List

**Begins after R2 is complete.**

| Question | Why now | Depends on |
|---|---|---|
| Q-P0-004: What is Reflection? | Reflection sits between Dialogue and Narrative in the epistemology chain. Until it is defined or ruled out as a system object, the epistemology chain has a gap. | Q-P0-003 |
| Q-P0-005: What is Dialogue? | Dialogue is how human stewardship enters the Field. Until its structure is defined (temporal vs. relational, resolution states, Question relationship), the Field cannot accept human contributions. | Q-P0-003, Q-P0-004 |
| Q-P1-004: Is Dialogue temporal or relational? | A direct sub-question of Q-P0-005. Should be ratified in the same session. | Q-P0-005 |
| Q-P1-006: Is Question a type of Dialogue? | The other direct sub-question of Q-P0-005. Must be ratified to determine whether the `question.py` stub is independent or subsumed. | Q-P0-005, Q-P1-004 |
| Q-P1-002: Should Perspective inherit from ContextCapsule or be independent? | Determines whether Perspectives are corpus-scoped or cross-corpus. Needed before Perspective schema is written. | Q-P0-003 |
| Q-P1-003: Should Interpretation reference multiple Perspectives? | Determines whether Interpretation has a `perspective_id: str` or `perspective_ids: list[str]`. Needed before Interpretation schema is written. | Q-P0-003, Q-P1-002 |
| Q-P6-002: What constitutes meaningful human contribution? | A policy companion to Q-P6-001. Must be ratified before the Field accepts any human-attributed object. | Q-P6-001 |
| Q-P6-003: How should contradictory perspectives coexist? | Determines whether Relationship predicates are Perspective-relative (which affects schema design significantly). Must be ratified before Relationship schema is finalized. | Q-P0-003, Q-P6-001 |
| **Q-P1-008: What is the full canonical ontology object list?** | This question can only be ratified once all P0 questions are resolved and the P1 classification questions have produced a definitive answer. R3 is the first milestone at which this is possible. | All P0, Q-P1-001 through Q-P1-007 |

**Implementation unlocked by R3:** `Perspective` class fields. `Interpretation` class fields. `Dialogue` class fields (with or without a separate `Question` class). `Reflection` class fields or stub removal. A finalized, numbered canonical ontology object list. All package schemas for the above objects. The complete `.herm` SQLite schema including all canonical object tables.

**This is the most important milestone after R0.** Completing R3 closes the ontology specification gap. From R3 onward, engineers have a complete, ratified canonical object list and can implement field definitions without risk of ontology drift.

---

### Milestone R4 — Hermeneutic Field Metrics

**Begins after R3 is complete.**

| Question | Why now | Depends on |
|---|---|---|
| Q-P2-001: What is Meaning Pressure? | The first field metric. Must be defined before the field graph can be analyzed or the planner can operate. | Q-P1-001, Q-P1-005 |
| Q-P2-002: What is Perspective Debt? | Extends Q-P2-001. Requires Perspective to be fully defined (completed in R3) and Meaning Pressure to be established. ADR-0005 moves from Proposed to Accepted here. | Q-P0-003, Q-P2-001 |
| Q-P2-003: What is Coverage? | Depends on both Perspective Debt and the canonical object list. Can only be defined once what it "covers" is known. | Q-P2-002 |
| Q-P2-004: What is Interpretive Density? | A derivative metric of Meaning Pressure and Coverage. Lower cost of error; can be ratified informally within R4. | Q-P2-001, Q-P2-003 |
| Q-P2-005: What is a Semantic Neighborhood? | A derivative metric. Low cost of error; can be ratified informally within R4. | Q-P2-001 |
| Q-P6-004: How should disagreement be preserved? | Requires Dialogue to be defined (R3) and the contradiction model from Q-P6-003 (R3). Ratified here to unblock the Planner. | Q-P6-003, Q-P0-005 |

**Implementation unlocked by R4:** `field/` package graph construction. `field/coverage.py`. `field/perspective_debt.py`. `field/meaning_pressure.py`. `herm inspect` CLI command. `herm stats` CLI command.

---

### Milestone R5 — Reader Transformation and Planning Primitives ✅ COMPLETE (2026-06-18)

**Began after R4 was complete.**

| Question | ADR | Status |
|---|---|---|
| Q-P0-006: What is Reader Transformation? | [ADR-0030](docs/adr/ADR-0030-reader-transformation.md) | **Ratified** 2026-06-18 |
| Q-P3-001: What is Understanding? | [ADR-0031](docs/adr/ADR-0031-understanding.md) | **Ratified** 2026-06-18 |
| Q-P3-002: What is Semantic Gain? | [ADR-0032](docs/adr/ADR-0032-semantic-gain.md) | **Ratified** 2026-06-18 |
| Q-P3-003: How should ReaderModel evolve? | [ADR-0033](docs/adr/ADR-0033-readermodel-evolution.md) | **Ratified** 2026-06-18 |
| Q-P3-004: How is Curiosity represented? | [ADR-0034](docs/adr/ADR-0034-curiosity.md) | **Ratified** 2026-06-18 |
| Q-P3-005: Can understanding be operationalized without invasive testing? | [ADR-0035](docs/adr/ADR-0035-operationalizing-understanding.md) | **Ratified** 2026-06-18 |

**Key decisions made in R5:**
- ReaderModel is an epistemic exposure tracker, NOT a cognitive state model. It records what the reader has encountered; it does not record what they remember or believe.
- Understanding = navigability of the Hermeneutic Field. Defined as a 4-vector: `(Field_Coverage, Perspective_Breadth, Dialogue_Depth, Horizon_Awareness)`. Not a scalar. Never reduced to a comprehension score.
- Semantic Gain formula ratified: `SG = 0.4×ConceptualBreadth + 0.5×PerspectivalDiversity + 0.1×DialogueContribution`. Weights are calibration parameters, not constitutional commitments.
- ReaderModel evolution is append-only. Lists monotonically grow. No regression mechanism exists or should exist.
- Curiosity is a Planner heuristic: `Curiosity(C, R, F) = MP(C, F) × gap(C, F) × unexplored(C, R)`. Not stored; computed on demand. Routing is constrained to the reader's Semantic Neighborhood.
- Understanding is operationalized through behavioral proxies (traversal evidence, contribution evidence, density evidence). No invasive testing required. System reports the 4-vector; stewards interpret it.

**Implementation unlocked by R5:** `planner/` package structural skeleton. `ReaderModel` class fields. `TransformationPlan` class fields. `planner/curiosity_engine.py`. `planner/journey_sequencer.py`. `herm plan` CLI command. **Milestone R6 may now begin.**

---

### Milestone R6 — Narrative and the Two-Writer Contract ✅ COMPLETE (2026-06-18)

**Began after R5 was complete.**

| Question | ADR | Status |
|---|---|---|
| Q-P0-007: What is NarrativeBlueprint? | [ADR-0036](docs/adr/ADR-0036-narrative-blueprint.md) | **Ratified** 2026-06-18 |
| Q-P4-003: Can style be separated from semantics? | [ADR-0037](docs/adr/ADR-0037-style-semantics-separation.md) | **Ratified** 2026-06-18 |
| Q-P4-001: Which transformations preserve meaning and which alter it? | [ADR-0038](docs/adr/ADR-0038-meaning-preserving-transformations.md) | **Ratified** 2026-06-18 |
| Q-P4-002: What is Narrative Fidelity? | [ADR-0039](docs/adr/ADR-0039-narrative-fidelity.md) | **Ratified** 2026-06-18 |
| Q-P4-004: How should Architect and Artist interact? | [ADR-0040](docs/adr/ADR-0040-architect-artist-interaction.md) | **Ratified** 2026-06-18 |

**Key decisions made in R6:**
- NarrativeBlueprint is the semantic contract for a rendering. Schema includes: closed `cited_observation_ids`, `required_perspective_ids`, structured `claims` list (each with `evidential_status`, `perspective_id`, `source_observation_ids`, `depends_on_claim_ids`), and `forbidden_inferences`.
- ADR-0003 (two-writer model) is confirmed — NOT invalidated. Style/semantics partial separation is constitutionally sufficient when the Critic validates against four semantic invariants: truth conditions, entailments, evidential status, uncertainty attribution.
- Critic taxonomy: two-category classification (meaning-preserving vs. meaning-altering) with three-pass algorithm. Produces `CriticReport` with per-claim violations.
- Narrative Fidelity: continuous score [0.0, 1.0]. Delivery threshold: NF ≥ 0.85. High-fidelity rendering can still be poor prose — NF measures semantic compliance, not quality.
- Artist receives Blueprint only (no Field access). Sequential pipeline: Architect → Steward ratification → Artist → Critic → (Steward if needed) → Reader. No iterative Architect/Artist loop.

**Implementation unlocked by R6:** `narrative/` package. `NarrativeBlueprint` class fields. `narrative/architect.py`. `narrative/artist.py`. `narrative/critic.py`. `herm render` CLI command.

---

## Summary: Ratification Sequence

```
R0 — Foundation ✅ COMPLETE 2026-06-18
├── Q-P0-001  Observation boundary              [Existential] → ADR-0006
├── Q-P0-008  ContinuityNode                    [High]       → ADR-0007
├── Q-P1-007  Manifest classification           [Medium]     → ADR-0008
├── Q-P5-003  AI provenance policy              [High]       → ADR-0009
└── Q-P6-001  Human-only decisions              [Existential] → ADR-0010

R1 — Provenance and Claim Primitives ✅ COMPLETE 2026-06-18
├── Q-P0-002  Observation/Claim relationship    [Existential] → ADR-0011
├── Q-P1-001  Claim independence                [High]        → ADR-0011 (co-resolved)
├── Q-P5-001  Atomic provenance unit            [High]        → ADR-0012
├── Q-P5-002  Provenance granularity            [High]        → ADR-0013
└── Q-P1-005  Smallest epistemic object         [High]        → ADR-0014

R2 — Interpretation and Perspective Primitives ✅ COMPLETE 2026-06-18
├── Q-P0-003  Interpretation vs. Perspective    [Existential] → ADR-0015
└── Q-P1-001  Claim independence                [High]        → ADR-0011 (complete in R1)

R3 — Reflection, Dialogue, and Canonical Object List ✅ COMPLETE 2026-06-18
├── Q-P0-004  Reflection                        [High]        → ADR-0016
├── Q-P0-005  Dialogue                          [High]        → ADR-0017
├── Q-P1-004  Dialogue: temporal or relational  [Medium]      → ADR-0018
├── Q-P1-006  Question vs. Dialogue             [Medium]      → ADR-0019
├── Q-P1-002  Perspective/ContextCapsule        [Medium]      → ADR-0020
├── Q-P1-003  Interpretation/Perspectives       [Medium]      → ADR-0021
├── Q-P6-002  Meaningful human contribution     [High]        → ADR-0022
├── Q-P6-003  Contradictory perspectives        [High]        → ADR-0023
├── Q-P6-004  Disagreement preservation         [High]        → ADR-0023 (co-resolved)
└── Q-P1-008  Canonical object list             [Existential] → ADR-0024 ← ontology definition CLOSED

R4 — Hermeneutic Field Metrics ✅ COMPLETE 2026-06-18
├── Q-P2-001  Meaning Pressure                  [Medium]  → ADR-0025
├── Q-P2-002  Perspective Debt (ADR-0005)       [High]    → ADR-0026 (supersedes ADR-0005)
├── Q-P2-003  Coverage                          [Medium]  → ADR-0027
├── Q-P2-004  Interpretive Density              [Low]     → ADR-0028
├── Q-P2-005  Semantic Neighborhood             [Low]     → ADR-0029
└── Q-P6-004  Preserving disagreement           [High]    → ADR-0023 (complete in R3)

R5 — Reader Transformation and Planning Primitives ✅ COMPLETE 2026-06-18
├── Q-P0-006  Reader Transformation             [High]    → ADR-0030
├── Q-P3-001  Understanding                     [High]    → ADR-0031
├── Q-P3-002  Semantic Gain                     [High]    → ADR-0032
├── Q-P3-003  ReaderModel evolution             [Medium]  → ADR-0033
├── Q-P3-004  Curiosity                         [Medium]  → ADR-0034
└── Q-P3-005  Understanding without testing     [Medium]  → ADR-0035

R6 — Narrative and the Two-Writer Contract ✅ COMPLETE 2026-06-18
├── Q-P0-007  NarrativeBlueprint                [High]        → ADR-0036
├── Q-P4-003  Style vs. semantics               [Existential] → ADR-0037 (ADR-0003 CONFIRMED)
├── Q-P4-001  Meaning-preserving transforms     [High]        → ADR-0038
├── Q-P4-002  Narrative Fidelity                [High]        → ADR-0039
└── Q-P4-004  Architect/Artist interaction      [Medium]      → ADR-0040

R7 — Research Program (non-blocking)
├── Q-P7-001  Hermeneutic Field as math object  [Low]
├── Q-P7-002  Meaning Pressure convergence      [Low]
├── Q-P7-003  Perspective Debt cross-cultural   [Low]
├── Q-P7-004  Layer separation vs. hallucination[Low]
├── Q-P7-005  Semantic Gain as info theory      [Low]
├── Q-P7-006  Perspective Debt / epistemic justice [Low]
└── Q-P7-007  Longitudinal reader transformation[Low]
```

---

## Implementation Unlocked Per Milestone

| Milestone | Implementation it permits |
|---|---|
| R0 complete ✅ | `ontology/base.py` (HermeneiaObject only). `validation/constitution.py` skeleton. Storage schema initialization (tables only, no Observation fields). |
| R1 complete ✅ | `Observation` class fields. `Provenance` class fields. SQLite schema for `observations`, `provenance`, `source_documents`. Append-only repository insert methods. `observation_compiler.py` structural skeleton. |
| R2 complete ✅ | `Perspective` class fields. `Interpretation` class fields (with `source_observation_ids`, `perspective_id`, `derivation_type`, `superseded_by`). `field/` package structural skeleton. |
| R3 complete ✅ | `Dialogue` class fields. `FieldQuestion` class (replaces `question.py`). `FieldContradiction` class. `ContextCapsule` class fields. `reflection.py` deleted. `manifest.py` moved to storage. Canonical object list (16 objects) closed. Full `.herm` SQLite schema finalized for all ratified objects. |
| R4 complete ✅ | `field/graph.py`. `field/coverage.py`. `field/perspective_debt.py`. `field/meaning_pressure.py`. `field/interpretive_density.py`. `field/neighborhood.py`. `herm inspect`. `herm stats`. ADR-0005 superseded by ADR-0026. |
| R5 complete ✅ | `ReaderModel` class fields. `TransformationPlan` class fields. `planner/` package. `planner/curiosity_engine.py`. `planner/journey_sequencer.py`. `herm plan`. |
| R6 complete ✅ | `NarrativeBlueprint` class fields. `narrative/architect.py`. `narrative/artist.py`. `narrative/critic.py`. `herm render`. |

---

## Critical Path

The critical path is the sequence of questions whose ratification must happen in strict serial order, because each one blocks the next. This is the minimum-time path from zero to a fully implementable system.

```
Q-P0-001 → Q-P0-002 → Q-P0-003 → Q-P0-005 → Q-P1-008 → Q-P2-001 → Q-P2-002 → Q-P3-001 → Q-P3-002 → Q-P0-007 → Q-P4-003
```

Every other question can be parallelized around this critical path. If the architect can ratify one question per session, and one session per week, the critical path has eleven steps — eleven weeks minimum to a fully ratified architecture. The actual timeline depends on how many questions can be ratified in parallel.

---

## Minimum Ratification to Begin Compiler Implementation

The compiler is the first meaningful implementation milestone. The following and only the following questions need to be ratified before a single line of compiler code may be written:

1. **Q-P0-001** — What constitutes an Observation?
2. **Q-P5-001** — What is the atomic provenance unit?
3. **Q-P5-002** — What level of provenance granularity best balances reproducibility and practicality?
4. **Q-P1-005** — What is the smallest epistemic object in Hermeneia?
5. **Q-P0-008** — What is ContinuityNode? *(to clean the ontology package before implementation)*
6. **Q-P1-007** — Is Manifest a canonical ontology object? *(to know where manifest.py belongs)*

These six questions, combined with the two policy questions (Q-P6-001 and Q-P5-003) which should be ratified at R0 regardless, constitute the minimum viable ratification for compiler work.

**All six must be resolved. No substitutions. No workarounds.**

---

## Anti-Patterns to Avoid

The following are implementation choices that appear pragmatic but will introduce unrecoverable ontology drift. They are prohibited.

| Anti-pattern | Why it is dangerous |
|---|---|
| Defining Observation boundary in code rather than ADR | Makes the boundary implicit. Two engineers will interpret it differently. Violates Invariant 2 (determinism). |
| Using `uuid4()` for Observation IDs as a "temporary" measure | Temporary IDs become permanent. Any corpus compiled with UUID IDs cannot be merged with one compiled with deterministic IDs. Append-only constraint prevents correction. |
| Implementing Claim as a field on Interpretation before Q-P1-001 is ratified | If Claim is later ratified as a first-class object, all existing Interpretations in the database become structurally incorrect — but the append-only constraint prevents correcting them. |
| Implementing Perspective before Q-P0-003 is ratified | If Perspective is later distinguished more finely from Interpretation, the `.herm` schema cannot be migrated without violating append-only. |
| Implementing any narrative layer before Q-P4-003 is ratified | If style and semantics cannot be separated, ADR-0003 must be reconsidered. Implementing Architect and Artist before this question is answered builds on a possibly invalid foundation. |
| Treating research literature recommendations as architectural answers | The research literature describes what others have done. It does not answer what Hermeneia should do. Every adoption from the literature requires an explicit constitutional compatibility check. |

---

*End of QUESTION_DEPENDENCY_GRAPH.md*

*This document is a planning artifact, not a constitutional document. It should be updated whenever questions are ratified (moved to Closed) or new questions are discovered and added to `EPISTEMIC_BACKLOG.md`.*
