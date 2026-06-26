# Witness, Marginalia, and the Authorship Deed

**Date:** 2026-06-25  
**Status:** Architectural synthesis — deferred under Architecture Freeze v1.0  
**See also:** [`docs/FUTURE_ARCHITECTURE_NOTES.md`](../FUTURE_ARCHITECTURE_NOTES.md)

---

## The Convergence

Two separate threads arrived at the same place simultaneously.

**Thread 1 — Marginalia:** A proposal for a human reading and annotation interface where highlights, labels, notes, and reflections become epistemic artifacts rather than comments.

**Thread 2 — Gatsby Experiments:** The discovery that observation and classification remained stable across English and Spanish executions, while question selection diverged. The implication: human attention determines what becomes an investigation before interpretation ever begins.

These are not separate features. They are the same principle at different scales.

The Marginalia interface is what Witness looks like in product form.  
The Gatsby findings are what Witness looks like in research form.  
The Authorship Deed is what Witness produces as an institutional artifact.

---

## The Witness Cognitive Responsibility

Witness is a new cognitive responsibility that precedes Explorer in the pipeline.

```
Witness        ← records human attention before interpretation begins
    ↓
Explorer       ← discovers candidate interpretations
    ↓
Architect      ← reconstructs semantic obligations
    ↓
Artist         ← communicates in expressive form
    ↓
Critic         ← verifies fidelity
    ↓
Governance     ← stewardship, ratification, trust
```

### What Witness Does

Witness records:

> "I saw this. This caught my attention. I don't know why yet."

That is profoundly different from interpretation. Interpretation explains. Witness notices.

### Why Witness Is Architecturally Prior

The Gatsby experiments showed that observations remained stable across executions while questions diverged. But before observations there is something earlier: the act of deciding to look at something. The reader's eye moved to the green light before the analyst decided what it meant. Witness captures that movement.

Highlights are not valuable because they are highlights. They are valuable because they preserve the record of *where human attention went before judgment shaped it*.

This is the earliest observable stage of inquiry. It is also the stage most easily lost.

---

## The Marginalia Interface

Marginalia is the product implementation of the Witness cognitive responsibility.

### Three-Pane Interface

```
Left: Document (PDF, page, chapter)
Center: Reading surface with highlights
Right: Annotation + Reflection panel
```

### Highlight → Label → Bucket

When a reader highlights text or a visual region, a lightweight menu appears:

**Label as:**
- Claim
- Evidence
- Definition
- Question
- Contradiction
- Theme
- Character / Actor
- Timeline
- Method
- Weakness
- Important Quote
- Needs Verification
- Spiritual / Moral Anchor

**Bucket (cognitive role):**
- Attention ← pre-interpretive notice
- Discovery
- Reconstruction
- Communication
- Verification
- Governance

The bucket directly maps the human reading act to Hermeneia's cognitive architecture. The reader does not need to know the architecture. The labels handle the mapping.

### Three Reading Speeds

The interface supports different levels of engagement without forcing structure:

| Mode | Acts |
|---|---|
| Light | Highlight + quick label |
| Study | Highlight + note + bucket |
| Research | Highlight + claim/evidence/verification structure |

Reading naturally first. Depth only when something matters.

### Post-Section Reflection

After each chapter or section, Hermeneia offers a structured reflection prompt:

- What is the central claim?
- What evidence mattered most?
- What confused you?
- What changed your understanding?
- What deserves verification?
- What should be remembered?
- What should be challenged?

The responses are stored as structured reading records, not free-form notes.

### The Critical Feature

> "The AI retrieved page 14 as relevant. You previously highlighted page 16 as the key evidence. These disagree. Review both?"

When machine attention and human attention diverge, Hermeneia can surface the divergence. That is not annotation software. That is disciplined inquiry made visible.

---

## The Authorship Deed

The Authorship Deed is what the Witness layer produces as a portable, author-owned provenance artifact.

### The Title/Deed Metaphor

A deed does not create the house. It establishes rightful relation to the house.

Hermeneia does not create the work. It establishes the author's rightful relation to the work.

### What the Deed Contains

```
Work title
Author name / chosen identity
Creation dates
Source list
Reading sessions
Highlights (text coordinates or bounding boxes for scanned pages)
Labels and buckets
Chapter reflections
Outline evolution
Draft history
Revision history
AI interaction disclosure
Final authorship statement
Document fingerprint / hash
Export timestamp
```

### Selective Disclosure

The author controls what is shared:

```
Private by default.
Author-owned.
Exportable.
Verifiable.
Shareable by choice.
Tamper-evident.
```

A student (or researcher, journalist, lawyer, pastor, analyst) may choose to submit:

- Final paper only
- Final paper + authorship certificate
- Final paper + selected evidence trail
- Full process packet

### The Certificate

```
Authorship Deed

This work was composed through Hermeneia.
The attached provenance record documents the author's reading, annotation,
reflection, drafting, revision, and disclosed tool assistance.

The author retains ownership of the work and controls disclosure of the process record.
```

### What This Is Not

This is not a surveillance tool.  
This is not a cheating detector.  
This is not a teacher dashboard.

The framing is:

> **"Your work deserves a record."**

Not: "Your teacher needs to watch you."

### The Education Framing

The relevant question for education is not:

> "Was this generated by AI?"

It is:

> "How did this student's understanding mature?"

Hermeneia establishes a chain of intellectual custody. For each final claim, the record traces:

```
Final sentence
    ↓
Draft paragraph
    ↓
Outline claim
    ↓
Student note
    ↓
Highlighted evidence
    ↓
Original source page
```

Academic integrity with receipts. But the receipts belong to the student.

### The Broader Claim

The Authorship Deed applies beyond students:

- researchers
- writers
- journalists
- grant applicants
- policy analysts
- lawyers
- consultants
- inventors
- anyone producing serious intellectual work

The constitutional principle: *every understanding has a lineage. Hermeneia makes that lineage inspectable.*

---

## Architectural Notes

### For Scanned Documents

Highlights on scanned pages should not depend on OCR. Store:

```
page number
bounding box coordinates
image path
optional OCR text
human label
human note
```

Even a chart, handwritten note, or image can be faithfully annotated.

### Provenance Chain With Witness

The full chain becomes:

```
SourceDocument
    ↓
SourceExtraction     ← machine extraction
    ↓
HumanWitness         ← human attention (Marginalia highlights, labels, notes)
    ↓
Observation          ← promoted from Witness or machine extraction
    ↓
Interpretation
    ↓
Blueprint
    ↓
ArchitectPlan
    ↓
RenderedNarrative
    ↓
Finding[]
    ↓
AuthorshipDeed       ← portable provenance artifact
```

### Constitutional Classification

| Concept | Status |
|---|---|
| Witness | Cognitive responsibility (candidate — requires practice before canonical status) |
| Marginalia | User interface / interaction surface |
| Authorship Deed | Derived projection / export artifact |
| Highlight | Implementation detail |
| Reflection | Existing or future evidence artifact (to be decided by practice) |

Hermeneia does not create ontology until repeated use proves it deserves to exist. This classification is the correct posture until Witness has been observed in practice.

---

## The Fractal Property

The architecture is fractal.

The same pattern — attention, discovery, reconstruction, communication, verification, governance — appears to repeat at every scale of inquiry:

| Scale | What the pattern governs |
|---|---|
| Idea | What happens to one insight |
| Investigation | What happens to one document analysis |
| Education | What happens to one student's learning process |
| Research program | What happens to one scientific inquiry |

This repetition suggests the architecture may have identified a general organizing principle rather than a workflow specific to literary analysis. If the same structure governs understanding at every scale, the system's applicability extends well beyond text.

This is a hypothesis, not a conclusion. It is stated here as a candidate for systematic investigation.

---

## The Refined Central Claim

This synthesis refines the white paper's central claim from:

> *Hermeneia separates cognitive responsibilities.*

To:

> *Hermeneia preserves the evolution of understanding by separating and governing the cognitive responsibilities through which understanding develops.*

The separation is the mechanism. The preservation of understanding is the goal.

Witness is the earliest stage of that preservation — and therefore its foundation.
