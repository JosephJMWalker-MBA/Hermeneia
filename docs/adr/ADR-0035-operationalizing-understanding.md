# ADR-0035: Operationalizing Understanding Without Invasive Testing

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P3-005 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

ADR-0031 defines Understanding as navigability of the Hermeneutic Field — a 4-vector. Q-P3-005 asks how this can be operationalized without requiring invasive testing (comprehension tests, recall quizzes, performance evaluations).

The project philosophy prohibits comprehension as an optimization target. Any operationalization must remain consistent with the constitutional rejection of "answers" as the goal. The system must measure something — but what, and how?

---

## Decision

**Understanding is operationalized through behavioral proxies that are constitutionally defensible: evidence of epistemic engagement, not evidence of comprehension.**

The system reports **engagement metrics**, not understanding scores. The distinction is constitutional.

---

### The Three Permitted Proxy Families

**Family 1: Traversal Evidence**  
What parts of the Field has this reader navigated?

- `Field_Coverage(R, C)` = proportion of Field Concepts in R.known_concept_ids
- `Perspective_Breadth(R, C)` = proportion of active Perspectives in R.encountered_perspective_ids
- `Horizon_Awareness(R, C)` = traversal at the semantic frontier (see ADR-0031)

These are read directly from the ReaderModel. No inference required. No test required.

**Family 2: Contribution Evidence**  
Has this reader asked questions or disputed interpretations?

- `Dialogue_Depth(R, C)` = reader's Dialogue entries relative to Concepts encountered
- Dialogue `dialogue_type: question` — did the reader pose a well-formed question?
- Dialogue `dialogue_type: dispute` — did the reader engage with a FieldContradiction?

The project philosophy's test — "questions well-posed" — is operationalized here. A reader who poses well-formed questions demonstrates navigational fluency: they know enough to know what they don't know.

**Family 3: Density Evidence**  
Has the reader encountered structurally significant parts of the Field?

- MP-weighted traversal: proportion of the reader's traversal that covers high-MP Concepts
- Gap exposure: proportion of traversal over high-gap Concepts (important but under-interpreted)

A reader who has navigated the Field's highest-MP, highest-gap Concepts has encountered the parts where the most interpretive work remains to be done. This is the strongest evidence of frontier engagement.

---

### What the System Reports

The system reports the Understanding 4-vector (ADR-0031):

```
U(R, C) = (Field_Coverage, Perspective_Breadth, Dialogue_Depth, Horizon_Awareness)
```

Each component is a ratio in [0.0, 1.0]. The system does NOT:
- Sum these into a single score
- Assert that any value is "good enough"
- Compare readers against each other
- Use thresholds to certify understanding

The Planner uses the vector to identify which dimension has the most room to improve and designs TransformationPlans accordingly. The steward interprets the vector; the system does not interpret it for them.

---

### What Is Constitutionally Forbidden

The following operationalizations are prohibited:

| Prohibited Measure | Reason |
|---|---|
| Quiz or recall test | Treats comprehension as the goal. Violates project philosophy. |
| Time-in-session | Correlates with exposure but can be gamed and does not measure epistemic engagement. |
| Click-through rate | Behaviorist proxy. Tracks compliance, not inquiry. |
| LLM-scored "understanding" | AI-generated judgment of reader state. Violates human-only decision-making (ADR-0010). |
| Scalar "understanding score" | Collapses the 4-vector into a reductive judgment. |

---

### The "Questions Well-Posed" Test

The project philosophy states: "The goal is not answers, but questions well-posed."

This is the constitutional test for operationalizing Understanding. A measure of Understanding is valid if and only if it correlates with the reader's capacity to pose increasingly well-formed epistemic questions.

**Behavioral proxy:** `Dialogue_Depth` with `dialogue_type: question`. A reader who asks richer questions over successive sessions (deeper traversal_history, higher MP of Concepts in the question's `target_object_id`, engagement with FieldContradictions) demonstrates the kind of Understanding this system aims to develop.

The system surfaces FieldQuestions as prompts. It records whether the reader engaged with them. It does not score the reader's response. Human stewards review the Dialogue and form their own interpretive judgment.

---

### Addressing Q-P3-005 Directly

**Q-P3-005:** *"Can Understanding be operationalized without invasive testing? If so, how?"*

**Answer: Yes, through behavioral proxies grounded in the ReaderModel, all of which are constitutionally defensible because they measure epistemic engagement rather than cognitive state.**

The four components of the Understanding vector are computable from ReaderModel fields without any test, quiz, or assessment:

| Component | Source |
|---|---|
| Field_Coverage | R.known_concept_ids / Field.concepts |
| Perspective_Breadth | R.encountered_perspective_ids / Field.active_perspectives |
| Dialogue_Depth | R.dialogue_ids / R.known_concept_ids |
| Horizon_Awareness | Frontier traversal in R.traversal_history |

The system can produce this vector after every session with zero invasive interaction.

---

## Constitutional Alignment

- **Project Philosophy** ("Questions well-posed"): Dialogue_Depth with `dialogue_type: question` is the primary operationalization of this commitment.
- **ADR-0031** (Understanding as navigability): The 4-vector is defined there; this ADR specifies how each component is computed from observable data.
- **ADR-0030** (ReaderModel): All proxy measures are read from ReaderModel fields.
- **ADR-0010** (Human-only decisions): The system reports; stewards interpret. No LLM-scored understanding.
- **Invariant 4** (Architectural Decoupling): The computation is purely arithmetic over ReaderModel state and Field metrics.
