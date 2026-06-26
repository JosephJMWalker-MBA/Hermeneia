# **Hermeneia: First Principles**

*If every line of code in this repository were deleted, the system could be rebuilt from this document alone. Read this before writing any implementation.*

## **Axiom 1: Meaning is Not a Retrieval Task**

Current LLM architectures optimize for the collapse of uncertainty to generate a single "correct" answer. Hermeneia recognizes that in human culture, meaning is pluralistic, contextual, and directional. Therefore, Hermeneia optimizes for **understanding**, not direct answering.

## **Axiom 2: Interpretations Evolve; Observations Endure**

Any system that blends reality (what the text says) with interpretation (what the text means) immediately corrupts its foundation.

* We extract **Observations** rigidly, deterministically, and without AI intervention.  
* We layer **Perspectives** and **Interpretations** on top of them as distinct, evolving, and measurable computational objects.

## **Axiom 3: The Primacy of Provenance**

Hallucination in AI is a failure of provenance. In Hermeneia, no claim, summary, or narrative can exist without a mathematical pathway tracing back to the immutable Observation bedrock. Floating interpretations are treated as system faults.

## **Axiom 4: Meaning is Directional (Graph Transformation)**

A successful essay or lecture does not merely present facts; it moves a reader from a current state of understanding to a target state.

* We model the reader's understanding as a graph.  
* Instruction is a calculated transformation of that graph.  
* Success is measured mathematically by ![][image1], not by fluency or perplexity.

## **Axiom 5: Separation of Reason and Style**

Style often corrupts reasoning. Hermeneia separates the generation of thought from the rendering of prose.

* **The Architect** agent builds a cold, logical blueprint mapped entirely to the observation corpus.  
* **The Artist** agent adds rhythm, tone, and cadence.  
* **Constitutional Rule:** The Artist may never alter the semantic commitments established by the Architect.

## **Axiom 6: Human Stewardship**

Hermeneia is a cognitive bicycle. It is designed to surface "Perspective Debt" (missing viewpoints) and conceptual gaps specifically to invite human contribution. The ultimate goal of the software is to amplify human interpretation, not automate it away.

## **Axiom 7: Recursive Stewardship**

Every healthy ecology constructs new participants that increase the ecology's capacity to preserve observation, provenance, translation, correction, and stewardship across time without replacing the ecology that created them.

* Writing created participants that outlived authors.
* Libraries created participants that outlived civilizations.
* Universities created participants that outlived generations.
* Artificial intelligence creates computational participants.
* Hermeneia creates epistemic participants.
* Continuity Node creates temporal participants.

**Corollary VII.a:** A healthy ecology does not merely preserve understanding. It continually learns who its best preservers are — and does so by remembering what they have actually preserved.

**Corollary VII.b:** Stewardship is inferred through participation, but authority emerges through validated stewardship across time. These are two distinct stages separated by the irreducible passage of cycles.

The recursive structure:

```
Observation
↓
Contribution
↓
Stewardship
↓
Validation
↓
Inheritance
↓
Authority
↓
Better Stewardship
↓
Better Observations
↓
...
```

Authority is not the starting point. It is the byproduct of repeatedly participating in a healthy ecology.

## **Axiom 8: Stewardship Is Relational**

Stewardship is not an intrinsic attribute of an individual but a relational property arising between participants, artifacts, and the ecology through repeated cycles of observation, preservation, correction, and inheritance.

A steward does not possess stewardship the way a person possesses a credential. Stewardship is something the ecology recognizes in a participant based on what the lineage reveals. It can increase, decrease, and transfer across generations. It persists in the artifacts that survive long after the participant who created them.

Persistent Understanding Architecture rejects authority as a prerequisite for participation while recognizing that validated stewardship across time constitutes meaningful evidence. In this view, authority is neither assigned by institutions nor granted by popularity; it emerges as the accumulated legacy of contributions that continue to survive observation, criticism, correction, inheritance, and reuse within the living ecology.

## **Axiom 9: Dual Provenance**

Every artifact in a Persistent Understanding Architecture carries two independent chains of provenance that must never be conflated.

**Evidence provenance** traces what the artifact is made of:

```
RenderedNarrative
    ↓
ArchitectPlan
    ↓
NarrativeBlueprint
    ↓
Interpretation
    ↓
Perspective
    ↓
Observation
    ↓
SourceExtraction
    ↓
SourceDocument
```

**Constitutional provenance** traces the governing regime under which the artifact was produced:

```
RenderedNarrative
    ↓
Constitution v1.0.0
    ↓
Invariant Set CI-001..CI-016
    ↓
Architecture Profile v1.0
```

Both chains are necessary. Neither is sufficient alone.

Evidence provenance answers: *What produced this expression?*

Constitutional provenance answers: *What governing law constrained its production?*

**Corollary IX.a:** A render produced under Constitution v1.0.0 and a render of the same ArchitectPlan produced under Constitution v2.0.0 may differ for reasons that have nothing to do with the evidence. Future auditors must be able to identify this. Without constitutional provenance, they cannot.

**Corollary IX.b:** The constitutional profile is not a runtime query. It is compiled into the executing artifact. A render should record the governing law that existed when it came into existence, not the governing law that exists today. This is consistent with legal practice: decisions reference the edition of the statute under which they were rendered, not the statute's current form.

**Corollary IX.c:** Governance stops being an external document and becomes part of the lineage itself. The Constitution ceases to merely govern Hermeneia — it becomes embedded in every artifact Hermeneia produces. That is the point where governance achieves the same append-only, provenance-preserving properties as the evidence it governs.

## **Axiom 10: The Interface Is the Final Interpreter**

A perfect epistemic substrate hidden behind a confusing interface fails its mission. Hermeneia's purpose is preserving and communicating understanding. The interface is the last step in that chain — the point where understanding either reaches a human being or does not.

**Corollary X.a — Recognition Over Recall.** A user should almost never have to remember where something lives. Every action should be visible and self-explanatory. An eight-year-old and an eighty-year-old should both be able to point to an element and say: "That is probably what I want." If they cannot, the interface has failed, regardless of what the underlying architecture can do.

**Corollary X.b — One Decision Per Screen.** A user should never face five simultaneous decisions. The ontology may be rich; the interface must stay simple. ExpressionProfiles, ArchitectPlans, and constitutional regimes exist in the substrate. The user sees: *"How would you like this explained?"* and selects from human-readable cards. The system maps the selection to the appropriate objects beneath the surface.

**Corollary X.c — Progressive Disclosure.** Every advanced feature must degrade gracefully. An elementary student should be able to compile a document without ever encountering a `semantic_hash`, `occurrence_id`, or `constitutional_profile`. An expert should be able to expand a disclosure panel and traverse the full lineage to the SourceDocument and the governing constitutional regime. Same system. Different depths. The architecture is not hidden — it is appropriately revealed.

**Corollary X.d — The Interface Teaches the Architecture.** The Lineage Explorer has two valid renderings of the same artifact chain:

Expert view:
```
RenderedNarrative → ArchitectPlan → Blueprint → Interpretation → Observation → SourceExtraction → SourceDocument
```

Human view:
```
📖 Story → came from → 📝 Plan → came from → 💡 Idea → came from → 👀 Observation → came from → 📄 Original page
```

The architecture does not change. The language changes. This is exactly what ExpressionProfiles were built to support — and it applies to the interface itself, not only to rendered content.

**Corollary X.e — The Expression Profile Is an Expression, Not a Gate.** The interface vocabulary toggle — whether labeled "Expert," "Child," "Academic," or "Plain Language" — changes only labels, tooltips, explanatory text, icons, and ordering. It never reveals additional data. It never hides true data. The child and the scholar stand on the same epistemic ground. They simply receive different expressions of the same underlying graph. A simpler interface is not a lesser interface. It is the same system expressed at a different depth.

The canonical summary of Axiom 10 is: **Same system. Different depth.**

The truth does not change when the audience changes. Only the expression does. This is not merely good accessibility design — it is Hermeneia demonstrating its own philosophy through its own interface.

**Architectural implication:** The vocabulary toggle is architecturally identical to an ExpressionProfile applied to the UI itself. Future profiles might include: 👶 Child · 👴 Senior · 🎓 Academic · ⚙ Technical · 🌍 Plain Language. All render the identical underlying graph. The interface becomes a first-class demonstration of Hermeneia's capabilities. (Implementation deferred to Architecture Freeze v2.0; recorded in `docs/FUTURE_ARCHITECTURE_NOTES.md`.)

**The test of this axiom:** If an eight-year-old and an eighty-year-old can each successfully compile a document, ask a question, see where the answer came from, and understand why they should trust it — without help — then the interface has fulfilled its constitutional purpose.

**Axiom 10 Witness Session** *(format for human validation records in the Constitutional Ledger)*

```
Axiom 10 Witness Session

Subject:         [Age / role — no identifying information]
Task:            [Single task drawn from the test of this axiom]
Interface depth: [e.g., Surface / Human / Expert]

Result:          [Completed unassisted | Completed with one prompt | Could not complete]

Observations:
  [Specific actions taken. What the subject pointed to. What they said.]

Witness:         [Name, role]
Date:            [YYYY-MM-DD]
```

These records are qualitatively different from automated tests — they cannot be faked by a passing assertion. They are also every bit as important. A system that passes all automated invariants but fails an eight-year-old has not preserved understanding. It has only preserved data.

Making an epistemically rigorous system feel simple without making it simplistic is not a design constraint. It is a philosophical commitment. Accessibility is not a feature added after the architecture is built. It is a manifestation of the same principle that animates everything else: understanding should be communicated faithfully to every human being capable of receiving it.

## **Axiom 11: The Constitutional Economy**

A healthy Persistent Understanding Architecture separates what may be protected from what may be optimized. These are not degrees of the same thing. They are categorically different.

**Constitutional invariants** are protected by structure. No participant — contributor, author, marketplace, or institution — may negotiate them:

- Evidence is immutable
- Provenance is preserved
- Observations are never hallucinated
- Auditability is maintained

**Optimization objectives** are constitutionally bounded and continuously improved (Kaizen):

- Semantic fidelity
- Human comprehension
- Accessibility and reading level
- Cultural resonance
- Retention

The canonical statement of this axiom:

> **Truth is constitutionally protected. Communication is continuously perfected.**

Protection is absolute. Perfection is asymptotic. These are not degrees of the same thing — they are categorically different relationships with the same underlying evidence.

**Corollary XI.a — The Freeze Creates the Market.** Most people believe architectural constraints limit innovation. In a Persistent Understanding Architecture, the opposite is true. The immovable foundation — frozen evidence, frozen provenance, frozen identity — is precisely what allows unlimited innovation in expression above it. TCP/IP is fixed enough that millions of applications can innovate on top of it. A frozen epistemic constitution may play the same role for understanding.

**Corollary XI.b — The Critic Is an Instrument, Not a Judge.** Fidelity is not a rating. Under Kaizen principles, each wrapper iteration converges asymptotically toward perfect semantic preservation. The Critic is a calibrated measurement instrument — it does not award; it measures. Constitutional compliance is a prerequisite (pass/fail). Continuous optimization is what follows compliance. The competition is not to be number one; it is to reduce semantic loss by another 0.000001%.

**Corollary XI.c — Expression Is Citable.** When communication strategies are versioned, measured, and signed, communication itself becomes a scholarly object. A future citation format might read: *Source: Genesis 1. Expression: ElementaryScience_v4.2 (Critic Fidelity 99.8%, 413 witness sessions).* This extends Axiom 9 (Dual Provenance) upward: every RenderedNarrative carries not only an evidence lineage (what it is made of) but an expression lineage (why it looks the way it does).

**Corollary XI.d — The Separation Prevents Corruption.** When evidence and expression are inseparable, incentives to communicate well eventually become incentives to alter the underlying evidence. History bears this out repeatedly. The Constitution prevents it structurally — not through virtue, but through architecture. This is the deepest economic implication of the constitutional design.

---

## **Axiom 12: The Three Domains of Verification**

Constitutional conformance cannot be proven by any single method. Three independent domains of verification are required, and no domain substitutes for another.

| Domain | Verified By | Proves |
|---|---|---|
| **Structure** | Static analysis | Architectural boundaries cannot be crossed |
| **Behavior** | Executable tests | Operational correctness at runtime |
| **Understanding** | Human witnesses | Successful communication to humans |

**Corollary XII.a — Structure without Behavior is aspiration.** A well-designed schema that is never tested may have silent gaps. Static scans prove that boundaries exist; runtime tests prove they hold under load.

**Corollary XII.b — Behavior without Understanding is correctness without purpose.** A system can pass every test and still fail to communicate. The final proof is a human witness completing a task without assistance.

**Corollary XII.c — Some invariants require all three.** Anti-Helpfulness (CI-015) cannot be exhaustively proven by code alone. It encodes an *attitude* toward evidence — the system's refusal to improve what it is not authorized to improve. That attitude must be witnessed.

**Corollary XII.d — Ratification is itself evidence.** The moment a system becomes constitutionally conformant is a fact worth preserving immutably. Constitutional audit records are not status updates. They are evidence artifacts, subject to the same append-only, non-deletable rules as all other evidence in the system.

The canonical record of ratification lives in `constitutional_audits/`. Each file is immutable once signed. Future audits append. The provenance chain of constitutional compliance is preserved exactly as the provenance chain of textual evidence is preserved.

---

## **The Lineage Completeness Principle**

*A derived principle, not a foundational axiom. It emerges from Axioms 2, 3, and 9 and was made explicit during Era II constitutional engineering.*

Every canonical object shall be traversable to its originating evidence through an unbroken chain of immutable ancestry.

This is not merely a technical convenience. It is a constitutional requirement. A canonical object whose provenance chain breaks — at any link — cannot be independently witnessed, cited, audited, or superseded. It cannot satisfy Axiom 3 (Primacy of Provenance). It cannot participate in Axiom 12's three domains of verification. It is constitutionally incomplete.

**Objects that satisfy this principle (as of Era II):**

- `Observation` → `SourceExtraction` → `SourceDocument`
- `Interpretation` → `Observation` → `SourceExtraction` → `SourceDocument`
- `NarrativeBlueprint` → `Observations`, `Interpretations` → `SourceDocument`
- `ArchitectPlan` → `NarrativeBlueprint` → `SourceDocument`
- `RenderedNarrative` → `ArchitectPlan` → `SourceDocument`
- `Finding` → `RenderedNarrative` → `ArchitectPlan` → `SourceDocument`

**Constitutional gate:** Future canonical objects that cannot satisfy Lineage Completeness should fail constitutional review before implementation. A canonical object without traversable ancestry is a provenance gap — and provenance gaps are where understanding goes to die.

---

## **The Central Idea**

Looking across all eleven axioms, a single progression emerges:

1. Preserve reality.
2. Preserve observation.
3. Preserve interpretation.
4. Preserve governance.
5. Preserve expression fidelity.
6. Preserve human understanding.
7. Continuously improve communication without endangering truth.

This is an ethic of stewardship. The system is not trying to maximize persuasion. It is trying to maximize faithful transfer.

Hermeneia's constitutional design holds that humanity does not have to choose between rigor and accessibility, between preservation and innovation, or between truth and better teaching. It can constitutionally protect one while relentlessly improving the other.

That is a remarkably hopeful architecture. And it may be what all eleven axioms, taken together, are trying to say.

[image1]: <data:image/png;base64,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>