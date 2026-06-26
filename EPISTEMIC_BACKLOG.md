# EPISTEMIC BACKLOG
### Hermeneia Constitutional Question Registry

**Status:** Living document. Questions are added when discovered. They are closed only by ratified ADR or constitutional amendment, never by implementation assumption.

**Authority:** This document operates under the Hierarchy of Authority:
Philosophy → Project Axioms → Constitution → Invariants → Ontology → Architecture → Specifications → Implementation → Research Literature.

Research literature is cited where it illuminates a question. It is never cited as a resolution.

**How to close a question:**
A question moves from `Open` to `Ratified` only when an ADR is accepted that explicitly answers it and the answer is confirmed consistent with the Constitution and Invariants. A question may move to `Research` if it is determined to be outside current implementation scope and worth pursuing as academic work. Questions may not be silently resolved by implementation.

**Constitutional Cost of Error scale:**

| Level | Meaning |
|---|---|
| **Existential** | An incorrect answer corrupts the ontological foundation irreversibly. Recovery requires violating the append-only constraint or discarding the corpus. |
| **High** | An incorrect answer causes significant architectural rework across multiple packages. Recovery is possible but expensive. |
| **Medium** | An incorrect answer causes localized rework within one or two packages. |
| **Low** | An incorrect answer can be corrected without violating any constitutional invariant. |

**Principle:** The quality of Hermeneia depends more on asking the right questions than on prematurely answering them. Interpretations evolve. Observations endure.

---

## P0 — Constitutional Questions

> These questions must be answered before any implementation in the relevant package proceeds. They are not engineering preferences. They are load-bearing semantic commitments. An incorrect answer will introduce ontology drift that cannot be repaired without violating the append-only constraint.

---

### Q-P0-001: What constitutes an Observation?

**Priority:** P0  
**Status:** Ratified  
**ADR:** [ADR-0006](docs/adr/ADR-0006-observation-definition.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Existential  
**Dependencies:** None. All other questions depend on this one.

> ✅ **COMPILER IMPLEMENTATION IS NOW PERMITTED.** Q-P0-001 was ratified on 2026-06-18 by [ADR-0006](docs/adr/ADR-0006-observation-definition.md). Compiler implementation may proceed in strict conformance with the definition in ADR-0006.

**The question:**
The architecture defines an Observation as "one sentence = one Observation." The Constitution (Article I) declares Observations immutable. The Invariants require verbatim text with no normalization. But what precisely is the boundary of an Observation?

- Is a sentence a syntactic unit (terminated by `.`, `?`, `!`) or a semantic unit (a complete proposition)?
- What happens when a sentence is syntactically malformed but semantically complete?
- What happens when a sentence spans a paragraph boundary in the source?
- What happens when a source document is a dialogue and one speaker's turn spans multiple typographic sentences?
- Is a footnote a separate Observation or an annotation on an existing Observation?
- Is a block quote within a sentence part of the parent Observation or a child Observation?
- What happens when a sentence contains an embedded list?

**Why it matters:**
Every downstream object — Concept, Relationship, Perspective, Interpretation, Dialogue, NarrativeBlueprint — traces its provenance to at least one Observation. If the boundary of an Observation is ambiguous, the provenance chain is ambiguous. Two compilers given identical input must produce identical Observations (Invariant 2). They cannot without a fully deterministic boundary definition.

**Which packages depend on it:**
`compiler`, `storage`, `field`, `validation`, all packages through provenance chain.

**Risks of answering incorrectly:**
- Too small (sub-sentence): provenance fragments; semantic continuity is lost.
- Too large (paragraph): the verbatim constraint is violated.
- Ambiguous: two engineers compiling the same document produce different Observation IDs, destroying `.herm` portability.

**Suggested validation method:** Compile the same edge-case document on two separate machines with two separate implementations and compare observation table hashes byte-for-byte.

**Empirical research required:** No. This is a definitional commitment. Edge-case corpus testing is necessary to confirm robustness of the chosen definition.

---

### Q-P0-002: What is the relationship between Observation and Claim?

**Priority:** P0  
**Status:** Ratified  
**ADR:** [ADR-0011](docs/adr/ADR-0011-claim-is-not-first-class.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Existential  
**Dependencies:** Q-P0-001

**The question:**
The research literature consistently distinguishes between "observation assertions" (verbatim data) and "interpretational assertions" (claims derived from data). Hermeneia uses the term "Observation" for verbatim text but does not formally define a "Claim" object.

- Does Hermeneia require a separate `Claim` object, or is the Hermeneutic Field the layer where Observation-to-Claim transformation is made explicit?
- If a Claim is derived from one or more Observations through a declared Perspective, should it be a first-class ontology object with its own ID and provenance?
- If Claims exist, do they belong in the `field` package, the `ontology` package, or both?
- Can a Claim exist without a Perspective? If so, what perspective is it implicitly adopting?

**Why it matters:**
If Claims are not first-class objects, every derived statement is attributed to the Observation rather than to the interpretive act that produced it. This violates Article II (Provenance) and Article III (Accumulation of Perspectives) — the provenance chain cannot distinguish "this text says X" from "this reading of this text says X."

**Which packages depend on it:**
`ontology`, `field`, `planner`, `narrative`, `validation`.

**Risks of answering incorrectly:**
- Not defining Claim forces all interpretation into the Observation layer (constitutional violation) or collapses it into Interpretation (loss of granularity).
- Over-defining Claim before its schema is clear produces stub objects that block the field layer.

**Suggested validation method:** Write a test case: "The green light in Gatsby symbolizes hope." Is this an Observation? An Interpretation? A Claim? The answer must be derivable from the ontology alone, without ambiguity.

**Empirical research required:** No.

---

### Q-P0-003: What distinguishes Interpretation from Perspective?

**Priority:** P0  
**Status:** Ratified  
**ADR:** [ADR-0015](docs/adr/ADR-0015-interpretation-vs-perspective.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Existential  
**Dependencies:** Q-P0-001, Q-P0-002

**The question:**
The ontology spec names both `Interpretation` and `Perspective` as canonical objects. Their relationship is not formally defined.

- Is a Perspective the *frame* (e.g. "Marxist reading") and an Interpretation the *claim made within that frame*?
- Or is an Interpretation a higher-order synthesis of multiple Perspectives?
- Can an Interpretation exist without a declared Perspective?
- Can a single Perspective produce multiple Interpretations of the same Observation?
- Are Perspectives declared by humans or inferred by the system?
- What happens when a Perspective is found to be factually wrong? Article III says Perspectives accumulate and cannot be deleted — but what is the difference between a wrong Perspective and a different one?

**Why it matters:**
Article III states "Adding a new Perspective to the field must append, not replace." If Perspective and Interpretation are conflated, every new Interpretation must accumulate infinitely without correction. If properly separated, Interpretations can be versioned and superseded while Perspectives remain as permanent epistemic stances.

**Which packages depend on it:**
`ontology`, `field`, `planner`, `narrative`.

**Risks of answering incorrectly:**
- Conflating the two makes Perspective Debt unmeasurable.
- Separating them incorrectly forces an infinite append of contradictory claims with no way to indicate which Interpretation is current within a given Perspective.

**Suggested validation method:** Model the following using only the ontology: (a) "From a feminist perspective, Daisy represents the imprisoning of female agency." (b) "From a post-colonial perspective, Daisy represents an idealization of whiteness." Both must be representable without modifying their source Observations. Their distinctness must be computable.

**Empirical research required:** No. Consultation with domain experts in hermeneutics is warranted.

---

### Q-P0-004: What is Reflection?

**Priority:** P0  
**Status:** Ratified  
**ADR:** [ADR-0016](docs/adr/ADR-0016-reflection-not-canonical.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-003

**The question:**
`Reflection` appears in `docs/08_epistemology.md` between Dialogue and Narrative in the epistemology chain. It exists as a class stub in `hermeneia/ontology/reflection.py`. It does not appear in `docs/06_Ontology.md` or `docs/specs/ontology.spec.md`.

- What is Reflection? Is it a human act of second-order self-scrutiny?
- Is it a system-generated synthesis across multiple Perspectives?
- Is it the epistemic act of noticing a gap (Perspective Debt)?
- Is it equivalent to what the research literature calls "metacognition"?
- Is it a private cognitive act (not storable), or a documented epistemic contribution (a first-class object)?

**Why it matters:**
If Reflection is a first-class object, it needs a schema, a provenance chain, and a place in the `.herm` database. If it is a human cognitive act, it should not be modeled as a system object at all — and the class stub should be removed.

**Which packages depend on it:**
`ontology`, `field`, `narrative`, `planner`.

**Risks of answering incorrectly:**
- Modeling Reflection as system-generated introduces AI inference into the Reflection layer, potentially violating Article I and Article V.
- Not modeling it leaves a gap in the epistemology chain between Dialogue and Narrative.

**Suggested validation method:** Describe one concrete example of a Reflection in a Gatsby reading. That example must fit the ontology's constraints without contradiction.

**Empirical research required:** Potentially. The constitutional question is whether Reflection is a computational artifact or a human one.

---

### Q-P0-005: What is Dialogue?

**Priority:** P0  
**Status:** Ratified  
**ADR:** [ADR-0017](docs/adr/ADR-0017-dialogue-definition.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-003, Q-P0-004

**The question:**
`Dialogue` appears in the epistemology chain and the canonical ontology spec. Article VI of the Constitution establishes human stewardship. The architecture names Dialogue as a formal human contribution to the field.

- Is Dialogue always human-originated, or can it be AI-generated?
- Is a Dialogue a response to a specific Observation, Interpretation, or Perspective — or can it be free-floating?
- Is Dialogue temporal (a sequence of turns) or relational (a set of attributed claims in conversation)?
- Can one Dialogue reference another (threading)?
- Does a Dialogue have a resolution state (open, answered, closed)?
- Is a Question a type of Dialogue, or a separate object?

**Why it matters:**
Dialogue is how human stewardship enters the Hermeneutic Field (Article VI). If Dialogue can be AI-generated, the constitutional protection of human contribution is weakened.

**Which packages depend on it:**
`ontology`, `field`, `narrative`, `validation`.

**Risks of answering incorrectly:**
- Allowing AI to create Dialogue objects violates the Human Stewardship principle.
- Not distinguishing Question from Dialogue leaves both stubs undefined.

**Suggested validation method:** A Dialogue object should be constructable from a real scholarly exchange about a source text. The structure must capture attribution, the object being addressed, and the epistemic stance — without flattening these into free text.

**Empirical research required:** No.

---

### Q-P0-006: What is Reader Transformation?

**Priority:** P0  
**Status:** Ratified  
**ADR:** [ADR-0030](docs/adr/ADR-0030-reader-transformation.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-001, Q-P0-003

**The question:**
The Transformation Planner's goal is to move a reader from their current state of understanding to a target state, maximizing Semantic Gain. But the architecture does not define what a "state of understanding" is, how it is represented, or how transformation is measured.

- Is a reader's understanding represented as a graph (nodes they know, edges they can traverse)?
- Is it represented as a set of Perspectives they have been exposed to?
- Is it represented as a calibrated confidence vector over claims?
- Who defines the target state — the human, the system, or the corpus?
- Can Reader Transformation be measured without invasive testing?

**Why it matters:**
The Semantic Gain metric, the Transformation Planner, and the entire Narrative layer depend on a computable model of reader understanding.

**Which packages depend on it:**
`planner`, `narrative`, `field`, `ontology` (if ReaderModel is an ontology object).

**Risks of answering incorrectly:**
- If modeled too behavioristically (clicks, dwell time), it optimizes for engagement not understanding — directly contradicting the project philosophy.
- If modeled too abstractly, it is impossible to compute.

**Suggested validation method:** Define a pre/post Reader Model for a reader engaging with Gatsby. The model must be representable as a data structure (not a free-text description). The difference between pre and post must be computable and ordered.

**Empirical research required:** Partially. Measuring actual reader transformation requires empirical study. Representing it as a data structure is a design question.

---

### Q-P0-007: What is NarrativeBlueprint?

**Priority:** P0  
**Status:** Ratified  
**ADR:** [ADR-0036](docs/adr/ADR-0036-narrative-blueprint.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-002, Q-P0-003, Q-P0-006

**The question:**
The NarrativeBlueprint is the Architect's output and the Artist's sole input. It is the constitutional boundary between the reasoning layer and the style layer (Article V). But its structure is undefined.

- What fields does a NarrativeBlueprint contain?
- Does it contain a sequence of Observation IDs to cite?
- Does it contain the logical structure of the argument (premises, conclusions)?
- Does it contain allowed Perspectives?
- Does it contain forbidden rhetorical moves (semantic no-fly zones)?
- Does it contain uncertainty bounds and evidential status markers?
- Is it a single flat structure or a hierarchical document plan?

**Why it matters:**
This is the most critical handoff boundary in the system. The Critic validates that the Artist's output does not exceed the Blueprint's semantic commitments (Invariant 6). The Critic cannot exist without a defined Blueprint schema.

**Which packages depend on it:**
`planner`, `narrative` (Architect and Artist), `validation` (Critic), `cli`.

**Risks of answering incorrectly:**
- Under-specified Blueprint allows the Artist to introduce unsupported claims (Article V violation).
- Over-specified Blueprint removes the Artist's ability to optimize communication.

**Suggested validation method:** Given five Observations from Gatsby and one declared Perspective, produce a NarrativeBlueprint. Then produce two prose renderings — one compliant, one violating. The Critic must detect the violation from the Blueprint alone without reading the prose.

**Empirical research required:** No.

---

### Q-P0-008: What is ContinuityNode?

**Priority:** P0  
**Status:** Ratified  
**ADR:** [ADR-0007](docs/adr/ADR-0007-continuity-node.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-001

**The question:**
`ContinuityNode` exists as a class stub in the codebase. It does not appear in any document — not in `06_Ontology.md`, not in `ontology.spec.md`, not in any ADR.

- What is a ContinuityNode?
- Should this class be removed?
- If it should exist, what ADR authorizes it?

**Why it matters:**
AGENTS.md: "No new ontology objects without an ADR." A class stub with no definition is an ontology ghost — it invites incorrect use.

**Which packages depend on it:**
`ontology`, potentially `field`.

**Risks of answering incorrectly:**
- Keeping it without definition allows engineers to use it in undefined ways, creating silent ontology drift.
- Removing it if it served a real function creates an implementation gap.

**Suggested validation method:** Either produce an ADR ratifying ContinuityNode with a defined schema, or remove the class and document the removal.

**Empirical research required:** No.

---

## P1 — Ontology Questions

> Questions concerning the structure and responsibilities of individual ontology objects and their relationships. These are architectural but not immediately constitutional. Implementation of the relevant objects should not proceed until the relevant P1 questions are resolved.

---

### Q-P1-001: Should Claim exist independently from Observation?

**Priority:** P1  
**Status:** Ratified  
**ADR:** [ADR-0011](docs/adr/ADR-0011-claim-is-not-first-class.md) (resolved as part of Q-P0-002)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-001, Q-P0-002

**The question:**
Research literature consistently identifies Claim as the atomic unit of epistemic assertion. Hermeneia's current ontology does not include Claim as a named canonical object. Interpretations, Perspectives, and Concepts each partially instantiate what the literature means by Claim.

- Does the absence of a Claim object force Claims to live implicitly inside Interpretation fields?
- If so, does this prevent the system from representing that an Interpretation contains multiple distinct Claims?
- Should each Claim within an Interpretation carry independent provenance?

**Why it matters:**
If Claims are compressed into Interpretations, the provenance chain cannot trace individual propositions back to individual Observations.

**Which packages depend on it:** `ontology`, `field`, `planner`.

**Blocked implementation:** Interpretation schema, Perspective schema, field graph traversal.

**Suggested validation method:** Can the system answer "which specific sentences in the source document support the claim that the green light symbolizes hope?" If not, a Claim object may be necessary.

**Empirical research required:** No.

---

### Q-P1-002: Should Perspective inherit from ContextCapsule or be independent?

**Priority:** P1  
**Status:** Ratified  
**ADR:** [ADR-0020](docs/adr/ADR-0020-perspective-contextcapsule.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P0-003

**The question:**
ContextCapsule captures document-level context (historical period, political context, etc.). Perspective captures a declared interpretive viewpoint. Some Perspectives are historically situated and overlap with ContextCapsule fields.

- Is a Perspective a viewpoint applied *to* a ContextCapsule, or is it independent of it?
- Can a Perspective exist across multiple documents with different ContextCapsules?

**Why it matters:**
If Perspective is scoped to a single document, it cannot be applied across a corpus. The Hermeneutic Field model suggests perspectives can traverse documents.

**Which packages depend on it:** `ontology`, `field`.

**Blocked implementation:** Perspective schema.

**Suggested validation method:** Can one Perspective object be associated with two different ContextCapsules without duplication or inconsistency?

**Empirical research required:** No.

---

### Q-P1-003: Should Interpretation reference multiple Perspectives?

**Priority:** P1  
**Status:** Ratified  
**ADR:** [ADR-0021](docs/adr/ADR-0021-interpretation-single-perspective.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P0-003, Q-P1-002

**The question:**
An Interpretation may synthesize multiple Perspectives (e.g. a reading that is simultaneously feminist and post-colonial).

- Should an Interpretation reference exactly one Perspective, or can it reference many?
- If many, is it still attributable to a single epistemic agent?
- How does multi-perspective Interpretation interact with the Accumulation axiom (Axiom 3)?

**Why it matters:**
If Interpretation is constrained to one Perspective, cross-Perspective synthesis must happen elsewhere (NarrativeBlueprint? Dialogue?). If it references multiple Perspectives, the provenance chain must independently trace each.

**Which packages depend on it:** `ontology`, `field`, `planner`, `narrative`.

**Blocked implementation:** Interpretation schema, field graph topology.

**Suggested validation method:** Produce an Interpretation that synthesizes two Perspectives without flattening either. The provenance of each Perspective must remain traceable independently.

**Empirical research required:** No.

---

### Q-P1-004: Is Dialogue temporal or relational?

**Priority:** P1  
**Status:** Ratified  
**ADR:** [ADR-0018](docs/adr/ADR-0018-dialogue-temporal-and-relational.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P0-005

**The question:**
A Dialogue might be modeled as:
- A **temporal sequence** of turns, where each turn has a timestamp and a speaker.
- A **relational graph** of attributed claims, where each claim cites what it is responding to.
- Both simultaneously.

**Why it matters:**
The Hermeneutic Field model suggests Dialogue expands the field (Axiom 8) — it is not merely a record of conversation, it is an epistemic contribution. A purely temporal model cannot represent the semantic relationship between a claim and its target.

**Which packages depend on it:** `ontology`, `field`.

**Blocked implementation:** Dialogue schema.

**Suggested validation method:** Model a real scholarly exchange about one Observation from Gatsby. The model must capture who said what, in response to what, and what epistemic stance was taken.

**Empirical research required:** No.

---

### Q-P1-005: What is the smallest epistemic object in Hermeneia?

**Priority:** P1  
**Status:** Ratified  
**ADR:** [ADR-0014](docs/adr/ADR-0014-smallest-epistemic-object.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-001, Q-P0-002

**The question:**
The architecture says "one sentence = one Observation." But is a sentence the smallest epistemic object, or is it a sub-sentential unit (clause, token) or a supra-sentential unit (paragraph, section)?

- What is the atomic unit of meaning in Hermeneia?
- Is meaning preserved at the sentence level, or does it require context (prior and following sentences)?
- Can an Observation carry a `context` field linking to adjacent Observations without violating verbatim immutability?

**Why it matters:**
This is foundational to the Hermeneutic Field's granularity. If the smallest object is too large, Claims cannot be traced to specific textual evidence.

**Which packages depend on it:** `compiler`, `ontology`, `field`, `storage`.

**Blocked implementation:** Observation ID algorithm, paragraph splitter, sentence splitter.

**Suggested validation method:** Take a complex sentence from Gatsby that contains two distinct propositions. Can one Observation adequately represent both? Should it be split?

**Empirical research required:** No.

---

### Q-P1-006: Is Question a type of Dialogue, or a separate ontology object?

**Priority:** P1  
**Status:** Ratified  
**ADR:** [ADR-0019](docs/adr/ADR-0019-question-vs-dialogue.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P0-005, Q-P1-004

**The question:**
`question.py` exists as a class stub. `Question` appears in the field spec. `Dialogue` appears in the canonical ontology spec. Are they the same type of object with a `type` field, or categorically different?

- A Question may be system-generated (from coverage analysis or perspective debt) — but a Dialogue is human-generated.
- Should Questions be subsumed into Dialogue, or should they be first-class objects?

**Why it matters:**
If Question and Dialogue are conflated, system-generated questions (surfacing Perspective Debt) would be ontologically indistinguishable from human epistemic contributions — a constitutional violation.

**Which packages depend on it:** `ontology`, `field`, `planner`.

**Blocked implementation:** Dialogue schema, Question schema, field coverage analysis.

**Suggested validation method:** Generate a Question from a coverage gap in the field. Generate a Dialogue from a human contribution. The two must be distinguishable in the database without reading their text content.

**Empirical research required:** No.

---

### Q-P1-007: Is Manifest a canonical ontology object?

**Priority:** P1  
**Status:** Ratified  
**ADR:** [ADR-0008](docs/adr/ADR-0008-manifest-classification.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** None

**The question:**
`manifest.py` exists in `hermeneia/ontology/`. `Manifest` does not appear in `ontology.spec.md`. The architecture describes `manifest.json` as part of the `.herm` bundle format.

- Is Manifest an administrative/infrastructure object or a semantic ontology object?
- Should it live in `ontology/` or in `storage/`?
- Should it extend `HermeneiaObject` (frozen, immutable) or be a mutable build artifact?

**Why it matters:**
If Manifest extends HermeneiaObject, it inherits `frozen=True`. If Manifest fields must be written incrementally during compilation (e.g. checksums written after content), it cannot be frozen.

**Which packages depend on it:** `ontology`, `storage`, `compiler`, `cli`.

**Blocked implementation:** `.herm` bundle serialization, Manifest schema.

**Suggested validation method:** Determine whether any field of a Manifest must change after the object is initially created. If yes, it cannot extend HermeneiaObject in its current form.

**Empirical research required:** No.

---

### Q-P1-008: What is the full canonical ontology object list?

**Priority:** P1  
**Status:** Ratified  
**ADR:** [ADR-0024](docs/adr/ADR-0024-canonical-object-list.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Existential  
**Dependencies:** All P0 and P1 questions above

**The question:**
There is a three-way inconsistency:
- `docs/06_Ontology.md`: 5 objects with fields (Observation, Provenance, ContextCapsule, Concept, Relationship)
- `docs/specs/ontology.spec.md`: 9 canonical objects (adds Perspective, Interpretation, Dialogue, Reflection, NarrativeBlueprint)
- `hermeneia/ontology/` directory: 14 class stubs (adds Manifest, ReaderModel, TransformationPlan, Question, ContinuityNode)

The canonical list must be definitively established before any schema implementation proceeds.

**Why it matters:**
An extra object that is not canonical introduces unauthorized ontology. A missing canonical object that is needed creates an implementation gap. The authoritative list cannot be derived from the code — the code is a stub, not a specification.

**Which packages depend on it:** All packages.

**Blocked implementation:** Everything.

**Suggested validation method:** Produce a single, numbered, ratified list of canonical ontology objects. Every object in that list must have a ratified ADR. Every class stub in the codebase must correspond exactly to one entry on that list.

**Empirical research required:** No.

---

## P2 — Hermeneutic Field Questions

> Questions concerning the computational properties of the Hermeneutic Field. These questions do not block early milestone implementation (Observations, Compiler, Storage) but must be resolved before Milestone 4 (Field) begins.

---

### Q-P2-001: What is Meaning Pressure?

**Priority:** P2  
**Status:** Ratified  
**ADR:** [ADR-0025](docs/adr/ADR-0025-meaning-pressure.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P1-001, Q-P1-005

**The question:**
The architecture defines Meaning Pressure qualitatively as "the density of connections radiating from a conceptual node over its historical documentation coverage." It is referenced in `docs/05_Architecture.md` but given no formula.

- Is Meaning Pressure a ratio? A sum? A graph-theoretic measure (e.g. degree centrality, betweenness centrality)?
- What counts as a "connection"? Only Relationship edges? Or also Perspective references and Dialogue annotations?
- What counts as "historical documentation coverage"?
- Does Meaning Pressure change as new Perspectives are added?

**Candidate formulations (not commitments):**
- Degree centrality: `MP(node) = edges(node) / total_nodes`
- Weighted centrality: `MP(node) = Σ relationship_strength(edge) / coverage(node)`
- Pressure differential: Meaning Pressure as the difference between a node's in-field connectivity and its expected connectivity given corpus size.

**Why it matters:**
Meaning Pressure is a metric the Transformation Planner uses to sequence concepts. Without a formula, the Planner cannot compute traversal order.

**Which packages depend on it:** `field`, `planner`.

**Blocked implementation:** Field graph analysis, Transformation Planner, Semantic Gain calculation.

**Suggested validation method:** Compute Meaning Pressure for the concept "green-light" in a Gatsby corpus. The result must correspond to a human expert's intuition that it is a heavily connected, symbolically dense concept.

**Empirical research required:** Yes. The formula must be validated against human expert judgments of symbolic density.

---

### Q-P2-002: What is Perspective Debt?

**Priority:** P2  
**Status:** Ratified  
**ADR:** [ADR-0026](docs/adr/ADR-0026-perspective-debt.md) (supersedes ADR-0005)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-003, Q-P2-001

**The question:**
ADR-0005 introduces Perspective Debt as a proposed concept. It is not yet accepted. Perspective Debt is described as "a measurable gap between evaluated viewpoints on a concept."

- How is the gap measured?
- Who defines which Perspectives are relevant?
- Can Perspective Debt be negative (too many perspectives, creating noise)?
- Does Perspective Debt apply to individual Concepts, or to the Field as a whole?
- Is Perspective Debt an absolute measure or a comparative one?

**Candidate formulations (not commitments):**
- `PD(concept) = expected_perspectives - observed_perspectives`
- `PD(concept) = 1 - (observed_perspectives / reference_perspectives)`
- A weighted version where historically marginalized perspectives carry higher debt when absent.

**Why it matters:**
Perspective Debt is the machine-readable representation of epistemic incompleteness within a corpus. Without a formula, it is a philosophical principle without computational teeth.

**Which packages depend on it:** `field`, `planner`, `cli` (herm stats).

**Blocked implementation:** Perspective accumulation engine, Coverage Analyzer, Perspective Debt reporting.

**Suggested validation method:** Given a corpus containing only dominant-culture readings of a text, Perspective Debt should return a high positive value and identify the underrepresented perspective type. The mechanism for generating expected perspectives is itself an open question.

**Empirical research required:** Yes. Determining which perspectives are "expected" for a given text likely requires cultural and scholarly input.

---

### Q-P2-003: What is Coverage?

**Priority:** P2  
**Status:** Ratified  
**ADR:** [ADR-0027](docs/adr/ADR-0027-coverage.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P2-002

**The question:**
The architecture refers to a `HermeneuticCoverageIndex` and a Coverage Analyzer. But the field spec does not define what coverage measures.

- Coverage of what? The proportion of Observations that have been interpreted?
- The proportion of Concepts that have at least one Relationship?
- The proportion of Concepts that have been viewed through more than one Perspective?

**Why it matters:**
Coverage is the metric that tells a user how complete their reading of a text is. Without defining what it covers, the metric is meaningless.

**Which packages depend on it:** `field`, `planner`, `cli`.

**Blocked implementation:** Coverage analysis, Perspective Debt calculation, `herm stats`.

**Suggested validation method:** After compiling Gatsby and building the field from 10 Perspectives, Coverage should return a value that a literary scholar would recognize as intuitively reasonable.

**Empirical research required:** Partially. The formula is a design choice; calibration against expert judgment is empirical.

---

### Q-P2-004: What is Interpretive Density?

**Priority:** P2  
**Status:** Ratified  
**ADR:** [ADR-0028](docs/adr/ADR-0028-interpretive-density.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Low  
**Dependencies:** Q-P2-001, Q-P2-003

**The question:**
The field architecture implies that some regions of the Hermeneutic Field are more densely interpreted than others. Interpretive Density is not formally named in the architecture but is implied by Meaning Pressure and Coverage.

- Is Interpretive Density a property of individual Concepts, or of regions (clusters)?
- Is it distinct from Meaning Pressure?
- Is it a useful standalone metric, or should it be subsumed into Coverage?

**Why it matters:**
A Transformation Planner that can identify low-density regions can route a reader through underexplored parts of the field. Without this concept, the planner defaults to routing through familiar, well-explored regions.

**Which packages depend on it:** `field`, `planner`.

**Blocked implementation:** Curiosity engine, journey sequencer.

**Suggested validation method:** Identify the least interpretively dense section of a Gatsby corpus. A literary scholar should find that region plausible as underexplored.

**Empirical research required:** No (for the formula); Yes (for calibration).

---

### Q-P2-005: What is a Semantic Neighborhood?

**Priority:** P2  
**Status:** Ratified  
**ADR:** [ADR-0029](docs/adr/ADR-0029-semantic-neighborhood.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Low  
**Dependencies:** Q-P2-001

**The question:**
The field spec implies that Concepts exist in "semantic neighborhoods" — clusters of related Concepts connected by Relationships. But a neighborhood is not formally defined.

- Is a Semantic Neighborhood defined by graph distance (all Concepts within N hops)?
- By Relationship type?
- By Perspective?
- By Meaning Pressure threshold?

**Why it matters:**
The Transformation Planner uses the Field to sequence concepts for a reader. If Semantic Neighborhoods are not defined, the Planner cannot reason about which concepts can be introduced together vs. in sequence.

**Which packages depend on it:** `field`, `planner`.

**Blocked implementation:** Journey sequencer, TransformationPlan generation.

**Suggested validation method:** Define a Semantic Neighborhood around "green-light" in a Gatsby corpus. A literary scholar should recognize the returned neighborhood as semantically coherent.

**Empirical research required:** No.

---

## P3 — Transformation Planning Questions

> Questions about Reader Transformation, Semantic Gain, and the Planner's cognitive model. Must be resolved before Milestone 6 (Transformation Planner) begins.

---

### Q-P3-001: What is Understanding?

**Priority:** P3  
**Status:** Ratified  
**ADR:** [ADR-0031](docs/adr/ADR-0031-understanding.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-006

**The question:**
Hermeneia's architecture states that the goal of the Transformation Planner is to move a reader toward Understanding. But Understanding is not defined in the architecture.

**Constitutional independence note:** The research literature on educational psychology treats Understanding as a multi-dimensional proxy measure. Hermeneia must not simply adopt a cognitive-science definition. Hermeneia's definition of Understanding must be consistent with its own philosophy: "the goal is not answers, but questions well-posed." Understanding in Hermeneia may mean epistemic humility and awareness of Perspective Debt, not mastery of a fixed body of knowledge.

**Candidate constitutional definitions (not commitments):**
- Understanding as **increased navigability of the Hermeneutic Field**.
- Understanding as **expanded epistemic horizon** (awareness of perspectives not yet encountered).
- Understanding as **reduced Perspective Debt**.
- Understanding as **durable conceptual reorganization**.

**Why it matters:**
The Semantic Gain formula cannot be defined until Understanding is defined.

**Which packages depend on it:** `planner`, `narrative`, `field`.

**Blocked implementation:** ReaderModel, TransformationPlan, Semantic Gain formula.

**Suggested validation method:** Define Understanding for a reader of Gatsby. Determine whether two readers with different concept maps but equal "time spent" can have different Understanding scores.

**Empirical research required:** Yes, for calibration. But the constitutional definition must come first.

---

### Q-P3-002: What is Semantic Gain?

**Priority:** P3  
**Status:** Ratified  
**ADR:** [ADR-0032](docs/adr/ADR-0032-semantic-gain.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P3-001, Q-P2-001, Q-P0-006

**The question:**
The architecture references Semantic Gain as the metric the Transformation Planner maximizes. It references a formula that appears as a broken image in `docs/05_Architecture.md`. No other document defines it.

- Is Semantic Gain a measure of Reader Model change (before vs. after)?
- Is it a measure of field traversal (how many new Concepts, Relationships, or Perspectives were encountered)?
- Is it normalized (0.0–1.0) or unbounded?
- Is it per-session or cumulative?
- Does it account for Perspective Debt reduction?

**Candidate formulations (not commitments):**
- `SG = |concepts_activated_new| / |concepts_in_field|`
- `SG = Δ(reader_coverage) / Δ(time)`
- `SG = Σ Meaning_Pressure(concept) × was_encountered(concept)`
- A formula that weights newly encountered diverse Perspectives more heavily than reinforcement of known ones.

**Why it matters:**
Semantic Gain is the primary optimization target of the system. It must be a real formula — not a placeholder.

**Which packages depend on it:** `planner`, `field`, `narrative`.

**Blocked implementation:** Entire Transformation Planner, curiosity engine.

**Suggested validation method:** Two Transformation Plans applied to the same ReaderModel — one maximizing Semantic Gain, one minimizing it (a simple linear reading). The maximizing plan should be recognized by a human expert as a richer reading experience.

**Empirical research required:** Yes. The formula should be validated against human judgments of reading value.

---

### Q-P3-003: How should ReaderModel evolve?

**Priority:** P3  
**Status:** Ratified  
**ADR:** [ADR-0033](docs/adr/ADR-0033-readermodel-evolution.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P3-001, Q-P3-002

**The question:**
The ReaderModel represents a reader's current epistemic state. It must change as the reader engages with the text.

- Is evolution append-only (consistent with Axiom 1) or can prior states be replaced?
- How is evolution triggered?
- Can a ReaderModel regress?
- Is ReaderModel evolution tracked in provenance?

**Why it matters:**
The Planner must read the current ReaderModel to generate the next TransformationPlan segment. Without evolution tracking, the Planner cannot know whether its prior plan succeeded.

**Which packages depend on it:** `planner`, `field`, `storage`.

**Blocked implementation:** ReaderModel schema, TransformationPlan, journey sequencer.

**Suggested validation method:** A ReaderModel after engaging with 10 Observations should differ measurably from the initial state. The difference should be representable as a versioned, provenance-linked delta.

**Empirical research required:** No (for the data structure); Yes (for calibration against actual reader behavior).

---

### Q-P3-004: How is Curiosity represented?

**Priority:** P3  
**Status:** Ratified  
**ADR:** [ADR-0034](docs/adr/ADR-0034-curiosity.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P3-001, Q-P2-004

**The question:**
The field spec references a "Curiosity Engine." Curiosity in this context likely means the system's drive to route a reader toward high-Meaning-Pressure, low-visited regions of the field.

- Is Curiosity a property of the ReaderModel, the Field, or a planning heuristic?
- Can Curiosity be satisfied (and if so, does it disappear or transform)?
- Is Curiosity related to Perspective Debt?

**Why it matters:**
Without curiosity modeling, the Transformation Plan will always follow the path of least resistance — the most documented, most connected parts of the field.

**Which packages depend on it:** `field`, `planner`.

**Blocked implementation:** Curiosity engine, journey sequencer.

**Suggested validation method:** A Curiosity Engine should route two identical ReaderModels to different parts of the field based on Perspective Debt. The routes should differ measurably.

**Empirical research required:** Partially.

---

### Q-P3-005: Can understanding be operationalized without invasive testing?

**Priority:** P3  
**Status:** Ratified  
**ADR:** [ADR-0035](docs/adr/ADR-0035-operationalizing-understanding.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P3-001, Q-P3-002

**The question:**
The research literature is consistent: measuring understanding requires behavioral evidence (transfer tasks, delayed recall, self-explanation). These require active testing of the reader.

- Can Hermeneia measure Semantic Gain passively?
- If active measurement is required, what is the measurement protocol?
- Is passive measurement (time on node, traversal patterns, Dialogue submissions) a valid proxy?

**Constitutional note:** The philosophy states that humans are essential (Axiom 5). A fully automated Semantic Gain measurement that bypasses human judgment may be philosophically incompatible with the system's premises.

**Why it matters:**
If understanding can only be measured invasively, the real-time Transformation Planner cannot adjust its plan based on current reader understanding.

**Which packages depend on it:** `planner`, `narrative`, `cli`.

**Blocked implementation:** Real-time plan adjustment, Semantic Gain feedback loop.

**Suggested validation method:** Determine whether a reader who has submitted a substantive Dialogue entry demonstrably "understands" a Concept more than a reader who has not. The answer must be computationally verifiable.

**Empirical research required:** Yes.

---

## P4 — Narrative Questions

> Questions concerning the Narrative Compiler, the two-writer model, and the relationship between semantic structure and rhetorical expression.

---

### Q-P4-001: Which transformations preserve meaning and which alter it?

**Priority:** P4  
**Status:** Ratified  
**ADR:** [ADR-0038](docs/adr/ADR-0038-meaning-preserving-transformations.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-007, Q-P3-001

**The question:**
The Critic must validate that the Artist's output does not alter the NarrativeBlueprint's semantic commitments. But the criteria for "altering meaning" are not defined.

Known safe transformations (candidates): synonym substitution within the same semantic field; reordering of paragraphs if logical structure is preserved; adding illustrative analogies flagged as analogies.

Known dangerous transformations (candidates): adding causal claims not in the Blueprint; omitting uncertainty markers; changing the scope of a claim; converting interpretive claims to observational claims.

**Why it matters:**
The Critic cannot function without a taxonomy of meaning-preserving vs. meaning-altering transformations.

**Which packages depend on it:** `narrative` (Critic, Architect), `validation`.

**Blocked implementation:** Critic logic, Blueprint fidelity validation.

**Suggested validation method:** Given a NarrativeBlueprint and two prose renderings (one compliant, one violating), the Critic must correctly classify each without reading free text — only by comparing against the Blueprint's semantic constraints.

**Empirical research required:** Partially.

---

### Q-P4-002: What is Narrative Fidelity?

**Priority:** P4  
**Status:** Ratified  
**ADR:** [ADR-0039](docs/adr/ADR-0039-narrative-fidelity.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P4-001, Q-P0-007

**The question:**
Narrative Fidelity would measure the degree to which a prose rendering faithfully represents the NarrativeBlueprint.

- Is Narrative Fidelity a binary property (compliant / not compliant) or a continuous score?
- Is it measured claim-by-claim or holistically?
- Can a high-fidelity narrative be rhetorically poor?

**Why it matters:**
The Critic must return a structured result — not a judgment in natural language. Narrative Fidelity must be computable.

**Which packages depend on it:** `narrative`, `validation`.

**Blocked implementation:** Critic implementation, `herm validate` narrative mode.

**Suggested validation method:** A prose rendering identical to the NarrativeBlueprint (verbatim) should return Narrative Fidelity = 1.0. A prose rendering that inverts a claim should return a measurably low fidelity score.

**Empirical research required:** No.

---

### Q-P4-003: Can style be separated from semantics?

**Priority:** P4  
**Status:** Ratified  
**ADR:** [ADR-0037](docs/adr/ADR-0037-style-semantics-separation.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Existential  
**Dependencies:** Q-P4-001

**The question:**
The two-writer model (ADR-0003) depends on the premise that style and semantics can be separated. But the research literature consistently warns that rhetorical choices — framing, ordering, emphasis, omission, metaphor, pronoun choice — can alter meaning even when propositions are preserved.

**Constitutional independence note:** The research literature does not resolve this question; it identifies it as unresolved. Hermeneia must take a position. The options are:
1. Accept that partial separation is sufficient and design guardrails (the Critic) to catch violations.
2. Reject the separation as impossible and replace the Architect/Artist model with a different mechanism.
3. Define style operationally as "transformations that do not alter the Blueprint's truth conditions, entailments, uncertainty markers, or evidential status" — and enforce this algorithmically.

If the answer is (2), ADR-0003 must be reconsidered. That is an existential cost.

**Why it matters:**
The entire two-writer model depends on this. If style cannot be separated from semantics, ADR-0003 must be reconsidered.

**Which packages depend on it:** `narrative` (entire package).

**Blocked implementation:** Artist implementation, Critic implementation.

**Suggested validation method:** Apply three different stylistic transformations (register, order, analogy) to the same Blueprint and test whether a human reader reaches the same epistemic conclusions from each. If yes, the separation is sufficient.

**Empirical research required:** Yes.

---

### Q-P4-004: How should Architect and Artist interact?

**Priority:** P4  
**Status:** Ratified  
**ADR:** [ADR-0040](docs/adr/ADR-0040-architect-artist-interaction.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Medium  
**Dependencies:** Q-P0-007, Q-P4-001, Q-P4-003

**The question:**
ADR-0003 accepts the two-writer model but does not specify the interaction protocol.

- Does the Architect produce the entire Blueprint before the Artist begins?
- Or does the Artist produce a section, which the Architect reviews before releasing the next section?
- Can the Artist request Blueprint clarification from the Architect?
- Does the Artist have access to the Hermeneutic Field directly, or only to the Blueprint?
- Can the Artist reject a Blueprint as rhetorically unrealizable?

**Why it matters:**
The interaction protocol determines whether the two writers are fully decoupled (sequential pipeline) or tightly coupled (iterative negotiation).

**Which packages depend on it:** `narrative`, `planner`.

**Blocked implementation:** Narrative Compiler pipeline, Architect class, Artist class.

**Suggested validation method:** Execute the two-writer model on a single NarrativeBlueprint. For every paragraph in the output, identify which Blueprint element it is expressing. The trace must be complete.

**Empirical research required:** No.

---

## P5 — Provenance Questions

> Questions about the granularity, structure, and implementation of the provenance layer.

---

### Q-P5-001: What is the atomic provenance unit?

**Priority:** P5  
**Status:** Ratified  
**ADR:** [ADR-0012](docs/adr/ADR-0012-atomic-provenance-unit.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-001

**The question:**
The current architecture assigns one Provenance record per Observation. Each Observation is one sentence. Is the sentence the correct granularity?

Candidate atomic units:
- **Token** (highest granularity): impractical for large corpora.
- **Clause** (sub-sentential semantic units): requires a clause splitter.
- **Sentence** (current design): natural unit of meaning; matches one Observation.
- **Paragraph**: loses sentence-level precision.
- **Page**: coarse; adequate for page-image OCR only.
- **OCR Region**: relevant when source is a scan.
- **Embedding region**: raises constitutional concerns (embeddings are inferences, not observations).

**Why it matters:**
If the provenance unit is too coarse, two sentences from the same paragraph cannot be distinguished. If too fine, the provenance database grows exponentially.

**Which packages depend on it:** `compiler`, `storage`, `ontology`.

**Blocked implementation:** Provenance schema, observation compiler pipeline.

**Suggested validation method:** For a given Observation, the Provenance record must uniquely identify the exact text passage in the source document — no other passage should produce the same Provenance record.

**Empirical research required:** No.

---

### Q-P5-002: What level of provenance granularity best balances reproducibility and practicality?

**Priority:** P5  
**Status:** Ratified  
**ADR:** [ADR-0013](docs/adr/ADR-0013-provenance-granularity.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P5-001

**The question:**
Given that the sentence is the current candidate atomic unit:

- For PDF documents: is page + paragraph + sentence sufficient, or are character offsets required?
- For OCR documents: should bounding-box coordinates be stored as a Provenance field?
- For versioned source documents: should Provenance include a document hash to distinguish version 1.0 from 1.1 of the same document?
- For sources that change (web pages, revised editions): how is Provenance preserved when the source changes?

**Why it matters:**
A `.herm` bundle claiming to represent "The Great Gatsby (Scribner, 1925)" must be distinguishable from one representing "The Great Gatsby (Penguin, 1990)." The Provenance record is the mechanism that makes this distinction.

**Which packages depend on it:** `compiler`, `storage`, `cli`.

**Blocked implementation:** Provenance schema, `.herm` bundle format finalization.

**Suggested validation method:** Compile the same paragraph from two different editions of the same book. The Provenance records must differ in a way that makes the edition distinguishable without reading the Observation text.

**Empirical research required:** No.

---

### Q-P5-003: Should provenance be tracked for AI-generated objects?

**Priority:** P5  
**Status:** Ratified  
**ADR:** [ADR-0009](docs/adr/ADR-0009-ai-provenance-policy.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P5-001, Q-P0-003

**The question:**
Observations are created deterministically without AI. But Concepts, Relationships, Interpretations, and NarrativeBlueprints may involve AI-assisted generation.

- Should every AI-generated object carry a Provenance record identifying which model, which version, which prompt template, and which context was used?
- Is AI provenance a constitutional requirement or an optional field?
- If an Interpretation is generated by an LLM and later revised by a human, how is the hybrid provenance represented?

**Constitutional note:** Article VI (Human Stewardship) implies that human and AI contributions must be distinguishable. This is only possible if AI-generated objects carry provenance that identifies them as AI-generated.

**Why it matters:**
If AI-generated objects carry no provenance distinguishing them from human contributions, Article VI is unenforceable in practice.

**Which packages depend on it:** `field`, `planner`, `narrative`, `storage`.

**Blocked implementation:** Field node creation, Interpretation schema, NarrativeBlueprint generation.

**Suggested validation method:** Given a `.herm` bundle, it should be possible to query "which objects were generated by AI and which by humans?" without reading the text content of any object.

**Empirical research required:** No.

---

## P6 — Human Stewardship Questions

> Questions about the role of human judgment in the system and how human contributions are preserved, attributed, and protected.

---

### Q-P6-001: What decisions must always remain human?

**Priority:** P6  
**Status:** Ratified  
**ADR:** [ADR-0010](docs/adr/ADR-0010-human-only-decisions.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** Existential  
**Dependencies:** None

**The question:**
Article VI of the Constitution establishes Human Stewardship, but it does not enumerate which decisions are categorically human. Without an explicit list, implementation engineers will make these decisions silently — in code, not in architecture documents. This is the most common form of ontology drift.

Candidate human-only decisions:
- Accepting or rejecting a new Concept
- Accepting or rejecting a new Perspective
- Adjudicating between contradictory Interpretations
- Defining the target ReaderModel
- Approving a NarrativeBlueprint before Artist rendering
- Closing or archiving a Dialogue thread
- Marking a Question as answered

**Why it matters:**
Without an enumerated list, the distinction between "AI-assisted" and "AI-decided" disappears in implementation.

**Which packages depend on it:** All packages with AI-generated content.

**Blocked implementation:** All AI-assisted generation flows.

**Suggested validation method:** Every human-only decision must produce a traceable human action in the provenance graph. If a decision can be made without a human provenance record, it is not human-only by the system's enforcement.

**Empirical research required:** No.

---

### Q-P6-002: What constitutes meaningful human contribution?

**Priority:** P6  
**Status:** Ratified  
**ADR:** [ADR-0022](docs/adr/ADR-0022-meaningful-human-contribution.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P6-001

**The question:**
Human contributions include Dialogue entries, Perspective declarations, Interpretation revisions, and ReaderModel definitions. But what makes a contribution "meaningful" vs. trivial?

- Is accepting an AI-generated Concept a meaningful human contribution?
- Is typing a one-word response in a Dialogue thread a meaningful contribution?
- Is a human who reviews and approves AI output without modifying it a meaningful contributor?

**Why it matters:**
Hermeneia must define what it values in human contribution — not what the research literature values.

**Which packages depend on it:** `narrative`, `field`, `cli`.

**Blocked implementation:** Human stewardship metrics, audit trail design.

**Suggested validation method:** Define a minimum threshold for meaningful human contribution in the context of a Dialogue. The threshold must be computable.

**Empirical research required:** No (for definition); Potentially yes (for calibration).

---

### Q-P6-003: How should contradictory perspectives coexist?

**Priority:** P6  
**Status:** Ratified  
**ADR:** [ADR-0023](docs/adr/ADR-0023-contradiction-preservation.md)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P0-003, Q-P6-001

**The question:**
Axiom 3 states that Perspectives accumulate — they do not overwrite each other. But coexistence without structure is just accumulation of noise.

- How does the Field represent that two Perspectives are contradictory without resolving the contradiction?
- Can a Concept have a Relationship of type "symbolizes" in one Perspective and "conceals" in another — and both be valid simultaneously?
- Who marks two Perspectives as contradictory — a human, the system, or both?

**Why it matters:**
A Hermeneutic Field that represents only harmony is not epistemically honest. Contradiction is a first-class epistemic state, not an error condition.

**Which packages depend on it:** `ontology`, `field`, `planner`, `narrative`.

**Blocked implementation:** Relationship schema (if predicates are Perspective-relative), Field contradiction representation.

**Suggested validation method:** Two Perspectives applied to the same Concept produce contradictory Relationships. Both must be representable in the Field simultaneously. Neither must be marked as "correct." A query for "all Relationships for Concept X" must return both.

**Empirical research required:** No.

---

### Q-P6-004: How should disagreement be preserved?

**Priority:** P6  
**Status:** Ratified  
**ADR:** [ADR-0023](docs/adr/ADR-0023-contradiction-preservation.md) (co-resolved with Q-P6-003)  
**Ratified:** 2026-06-18  
**Constitutional Cost of Error:** High  
**Dependencies:** Q-P6-003, Q-P0-005

**The question:**
Dialogue objects represent human contributions including disagreements. But "disagreement" in Hermeneia is not the same as contradiction between Perspectives — it may be a scholar disputing another scholar's Interpretation within the same Perspective.

- Is disagreement within a Perspective a Dialogue object, or a separate Interpretation with a `disputes` relationship?
- Can disagreement be resolved? If so, what happens to the losing position?
- Should unresolved disagreements be surfaced to the Transformation Planner?

**Why it matters:**
A system that buries disagreement in the database but presents a unified narrative to the reader is epistemically dishonest.

**Which packages depend on it:** `ontology`, `field`, `planner`, `narrative`.

**Blocked implementation:** Dialogue schema, Planner (disagreement handling), Artist (how to express open disagreement in prose).

**Suggested validation method:** Two scholars disagree about whether the green light symbolizes hope or futility. Both disagreements are stored. The Transformation Planner must decide whether to present both, choose one, or explicitly flag the disagreement to the reader. The decision must be traceable.

**Empirical research required:** No.

---

## P7 — Research Questions

> These questions are not blocking implementation. They are opportunities for future academic contribution. Hermeneia's engineering can proceed without resolving them, but the system's theoretical foundations would be strengthened by addressing them.

---

### Q-P7-001: What is a Hermeneutic Field as a mathematical object?

**Priority:** P7  
**Status:** Research  
**Constitutional Cost of Error:** Low

**The question:**
The Hermeneutic Field is described architecturally as a directed graph where nodes are ontology objects and edges are typed Relationships. But a mathematical formalization might provide stronger tools for analysis.

Possible formalizations: hypergraph, weighted directed graph, RDF/OWL-compatible knowledge graph, context graph, or a sheaf (a structure assigning local data to each open set of a topological space — potentially useful for modeling how Perspectives "cover" the field).

**Potential publication:**
"Hermeneutic Fields: A Graph-Theoretic Model for Multi-Perspective Literary Analysis"

---

### Q-P7-002: Can Meaning Pressure be formally proven to converge?

**Priority:** P7  
**Status:** Research  
**Constitutional Cost of Error:** Low  
**Dependencies:** Q-P2-001, Q-P7-001

**The question:**
As more Perspectives are added to the Field, Meaning Pressure may increase (more connections → higher pressure) or stabilize (the Field becomes saturated). Is there a proof that Meaning Pressure converges?

---

### Q-P7-003: Is Perspective Debt measurable across languages and cultures?

**Priority:** P7  
**Status:** Research  
**Constitutional Cost of Error:** Low  
**Dependencies:** Q-P2-002

**The question:**
Perspective Debt is defined relative to "expected perspectives" for a given text. But "expected perspectives" may differ across linguistic and cultural traditions. Is Perspective Debt culture-invariant, or does it require culture-specific calibration?

---

### Q-P7-004: Does epistemic operating system architecture reduce hallucination in AI-generated interpretation?

**Priority:** P7  
**Status:** Research  
**Constitutional Cost of Error:** Low

**The question:**
Hermeneia maintains Observation, Inference, and Interpretation as separate layers. Does this separation measurably reduce interpretive hallucination compared to standard RAG or LLM-based literary analysis?

**Potential publication:**
"Epistemic Layer Separation as a Hallucination Reduction Mechanism in AI-Assisted Literary Analysis"

---

### Q-P7-005: What is Semantic Gain as an information-theoretic quantity?

**Priority:** P7  
**Status:** Research  
**Constitutional Cost of Error:** Low  
**Dependencies:** Q-P3-002

**The question:**
Can Semantic Gain be expressed as mutual information between a ReaderModel before and after engagement, or as the KL divergence between the reader's prior distribution over concept weights and the posterior distribution after engaging with a Narrative?

---

### Q-P7-006: What is the relationship between Perspective Debt and epistemic justice?

**Priority:** P7  
**Status:** Research  
**Constitutional Cost of Error:** Low

**The question:**
Is Perspective Debt a computational operationalization of Miranda Fricker's concept of epistemic injustice? If yes, Hermeneia makes a contribution to computational humanities: a system that actively surfaces the absence of marginalized voices.

**Potential publication:**
"Perspective Debt: A Computational Operationalization of Epistemic Injustice in Literary Corpora"

---

### Q-P7-007: Can Reader Transformation be measured longitudinally?

**Priority:** P7  
**Status:** Research  
**Constitutional Cost of Error:** Low  
**Dependencies:** Q-P3-001, Q-P3-002

**The question:**
Can a Hermeneia-based system track Reader Transformation across sessions, months, and years? If yes, Hermeneia would be one of the first systems to operationalize longitudinal epistemic transformation as a computational artifact with full provenance.

---

## Appendix A: Question Status Registry

| ID | Title | Priority | Cost of Error | Status |
|---|---|---|---|---|
| Q-P0-001 | What constitutes an Observation? | P0 | Existential | **Ratified** (ADR-0006, 2026-06-18) |
| Q-P0-002 | Observation/Claim relationship? | P0 | Existential | **Ratified** (ADR-0011, 2026-06-18) |
| Q-P0-003 | Interpretation vs. Perspective? | P0 | Existential | **Ratified** (ADR-0015, 2026-06-18) |
| Q-P0-004 | What is Reflection? | P0 | High | **Ratified** (ADR-0016, 2026-06-18) |
| Q-P0-005 | What is Dialogue? | P0 | High | **Ratified** (ADR-0017, 2026-06-18) |
| Q-P0-006 | What is Reader Transformation? | P0 | High | **Ratified** (ADR-0030, 2026-06-18) |
| Q-P0-007 | What is NarrativeBlueprint? | P0 | High | **Ratified** (ADR-0036, 2026-06-18) |
| Q-P0-008 | What is ContinuityNode? | P0 | High | **Ratified** (ADR-0007, 2026-06-18) |
| Q-P1-001 | Should Claim exist independently? | P1 | High | **Ratified** (ADR-0011, 2026-06-18) |
| Q-P1-002 | Perspective/ContextCapsule relationship? | P1 | Medium | **Ratified** (ADR-0020, 2026-06-18) |
| Q-P1-003 | Interpretation → multiple Perspectives? | P1 | Medium | **Ratified** (ADR-0021, 2026-06-18) |
| Q-P1-004 | Is Dialogue temporal or relational? | P1 | Medium | **Ratified** (ADR-0018, 2026-06-18) |
| Q-P1-005 | What is the smallest epistemic object? | P1 | High | **Ratified** (ADR-0014, 2026-06-18) |
| Q-P1-006 | Is Question a type of Dialogue? | P1 | Medium | **Ratified** (ADR-0019, 2026-06-18) |
| Q-P1-007 | Is Manifest a canonical ontology object? | P1 | Medium | **Ratified** (ADR-0008, 2026-06-18) |
| Q-P1-008 | What is the full canonical object list? | P1 | Existential | **Ratified** (ADR-0024, 2026-06-18) |
| Q-P2-001 | What is Meaning Pressure? | P2 | Medium | **Ratified** (ADR-0025, 2026-06-18) |
| Q-P2-002 | What is Perspective Debt? | P2 | High | **Ratified** (ADR-0026, 2026-06-18) |
| Q-P2-003 | What is Coverage? | P2 | Medium | **Ratified** (ADR-0027, 2026-06-18) |
| Q-P2-004 | What is Interpretive Density? | P2 | Low | **Ratified** (ADR-0028, 2026-06-18) |
| Q-P2-005 | What is a Semantic Neighborhood? | P2 | Low | **Ratified** (ADR-0029, 2026-06-18) |
| Q-P3-001 | What is Understanding? | P3 | High | **Ratified** (ADR-0031, 2026-06-18) |
| Q-P3-002 | What is Semantic Gain? | P3 | High | **Ratified** (ADR-0032, 2026-06-18) |
| Q-P3-003 | How should ReaderModel evolve? | P3 | Medium | **Ratified** (ADR-0033, 2026-06-18) |
| Q-P3-004 | How is Curiosity represented? | P3 | Medium | **Ratified** (ADR-0034, 2026-06-18) |
| Q-P3-005 | Understanding without invasive testing? | P3 | Medium | **Ratified** (ADR-0035, 2026-06-18) |
| Q-P4-001 | Which transformations preserve meaning? | P4 | High | **Ratified** (ADR-0038, 2026-06-18) |
| Q-P4-002 | What is Narrative Fidelity? | P4 | High | **Ratified** (ADR-0039, 2026-06-18) |
| Q-P4-003 | Can style be separated from semantics? | P4 | Existential | **Ratified** (ADR-0037, 2026-06-18) |
| Q-P4-004 | How should Architect and Artist interact? | P4 | Medium | **Ratified** (ADR-0040, 2026-06-18) |
| Q-P5-001 | What is the atomic provenance unit? | P5 | High | **Ratified** (ADR-0012, 2026-06-18) |
| Q-P5-002 | Granularity vs. reproducibility balance? | P5 | High | **Ratified** (ADR-0013, 2026-06-18) |
| Q-P5-003 | Should AI-generated objects carry provenance? | P5 | High | **Ratified** (ADR-0009, 2026-06-18) |
| Q-P6-001 | What decisions must always remain human? | P6 | Existential | **Ratified** (ADR-0010, 2026-06-18) |
| Q-P6-002 | What constitutes meaningful human contribution? | P6 | High | **Ratified** (ADR-0022, 2026-06-18) |
| Q-P6-003 | How should contradictory perspectives coexist? | P6 | High | **Ratified** (ADR-0023, 2026-06-18) |
| Q-P6-004 | How should disagreement be preserved? | P6 | High | **Ratified** (ADR-0023, 2026-06-18) |
| Q-P7-001 | Hermeneutic Field as a mathematical object? | P7 | Low | Research |
| Q-P7-002 | Can Meaning Pressure be proven to converge? | P7 | Low | Research |
| Q-P7-003 | Is Perspective Debt cross-culturally measurable? | P7 | Low | Research |
| Q-P7-004 | Does layer separation reduce hallucination? | P7 | Low | Research |
| Q-P7-005 | Semantic Gain as information-theoretic quantity? | P7 | Low | Research |
| Q-P7-006 | Perspective Debt and epistemic justice? | P7 | Low | Research |
| Q-P7-007 | Can Reader Transformation be measured longitudinally? | P7 | Low | Research |

---

## Appendix B: Implementation Gates

The following implementation milestones are blocked until the listed questions are resolved.

| Milestone | Blocked until |
|---|---|
| M0: Ontology Fields | Q-P0-001, Q-P0-004, Q-P0-005, Q-P1-008 |
| M1: Storage Foundation | Q-P0-001, Q-P5-001, Q-P1-007 |
| M2: Observation Compiler | ~~Q-P0-001~~ *(ratified 2026-06-18)*, Q-P5-001, Q-P5-002 |
| M3: Validation Layer | Q-P0-001, Q-P0-002, Q-P6-003 |
| M4: Hermeneutic Field | Q-P0-003, Q-P1-001, Q-P1-002, Q-P1-003, Q-P1-004, Q-P2-001, Q-P2-003 |
| M5: Perspective Engine | Q-P0-003, Q-P2-002, Q-P6-003, Q-P6-004 |
| M6: Transformation Planner | Q-P0-006, Q-P3-001, Q-P3-002, Q-P3-003, Q-P3-004 |
| M7: Narrative Compiler | Q-P0-007, Q-P4-001, Q-P4-002, Q-P4-003, Q-P4-004, Q-P6-001 |

---

## Appendix C: Dependency Graph of Open Questions

The graph below shows the prerequisite relationships between questions. A question cannot be ratified before its upstream dependencies are ratified. Reading the graph from top to bottom gives the minimum-cost ratification sequence.

```
Q-P0-001: Observation
          │
          ├────────────────────────────────────────┐
          │                                        │
          ▼                                        ▼
Q-P0-002: Claim                          Q-P5-001: Atomic Provenance Unit
          │                                        │
          ├──────────────────┐                     ▼
          │                  │            Q-P5-002: Provenance Granularity
          ▼                  ▼
Q-P1-001: Claim Independent  Q-P1-005: Smallest Epistemic Object
          │
          └────────────────────────────┐
                                       │
Q-P0-003: Interpretation vs Perspective◄┘
          │
          ├────────────────────────────────────────────────┐
          │                                                │
          ├──────────────────────────┐                     │
          ▼                          ▼                     ▼
Q-P1-002: Perspective/Context  Q-P0-004: Reflection  Q-P0-005: Dialogue
          │                                                │
          │                                                ├───────────────┐
          ▼                                                ▼               ▼
Q-P1-003: Interp/Perspectives               Q-P1-004: Dialogue Shape  Q-P1-006: Question
          │
          ▼
Q-P1-008: Canonical Object List ◄─── (requires all P0 questions ratified)
          │
          ├────────────────────────────────┐
          ▼                                ▼
Q-P2-001: Meaning Pressure       Q-P2-002: Perspective Debt
          │                                │
          ├─────────────┐                  │
          ▼             ▼                  ▼
Q-P2-003: Coverage  Q-P2-005: Neighborhood  Q-P6-003: Contradictory Perspectives
          │                                          │
          ▼                                          ▼
Q-P2-004: Interpretive Density            Q-P6-004: Preserving Disagreement
          │
          └──────────────────────────────┐
                                         ▼
Q-P0-006: Reader Transformation ─────► Q-P3-001: Understanding
                                         │
                                         ▼
                                Q-P3-002: Semantic Gain
                                         │
                                         ├──────────────────┐
                                         ▼                  ▼
                                Q-P3-003: ReaderModel  Q-P3-004: Curiosity
                                         │
                                         ▼
                                Q-P3-005: Understanding Without Testing
                                         │
                                         ▼
Q-P0-007: NarrativeBlueprint ──────► Q-P4-003: Style vs Semantics
                                         │
                                         ▼
                                  Q-P4-001: Meaning-Preserving Transforms
                                         │
                                         ▼
                                  Q-P4-002: Narrative Fidelity
                                         │
                                         ▼
                                  Q-P4-004: Architect/Artist Interaction
```

**Questions with no upstream dependencies (can be ratified immediately):**

| Question | Why it can proceed independently |
|---|---|
| Q-P0-001: Observation | The foundational question. No prerequisites exist. |
| Q-P1-007: Manifest | An administrative question about package placement. Independent of ontology. |
| Q-P6-001: Human-only decisions | A policy question. Does not require ontology to be defined. |
| Q-P5-003: AI provenance | A policy question. Can be answered alongside Q-P6-001. |
| Q-P0-008: ContinuityNode | A classification question: does this object exist or not? |

**Questions that unlock the most downstream work when ratified:**

| Question | Questions it unblocks |
|---|---|
| Q-P0-001: Observation | All other questions in the backlog |
| Q-P0-003: Interpretation vs Perspective | Q-P1-002, Q-P1-003, Q-P2-002, Q-P6-003, Q-P6-004, Q-P1-008 |
| Q-P1-008: Canonical object list | All package schema implementations |
| Q-P3-001: Understanding | Q-P3-002, Q-P3-003, Q-P3-004, Q-P3-005, Q-P4-003 |
| Q-P0-007: NarrativeBlueprint | All of Q-P4-* |

---

*End of EPISTEMIC_BACKLOG.md*

*This document is a living registry. Questions are added when discovered; they are closed only by ratified ADR or constitutional amendment. The goal of this document is not to constrain Hermeneia's development — it is to ensure that every architectural decision is made consciously, not by default.*
