# ADR-0031: Understanding — Constitutional Definition

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P3-001 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

The Transformation Planner's optimization target is to move a reader toward Understanding. The research literature treats Understanding as a cognitive science construct requiring behavioral evidence. Hermeneia's philosophy explicitly prohibits adopting the research literature as authoritative. A Hermeneia-specific definition is required.

---

## Decision

### Constitutional Rejection of Comprehension as Understanding

Hermeneia does not define Understanding as mastery, recall, or the ability to reproduce the text's "meaning." These definitions presuppose a correct answer to hermeneutic questions — a presupposition the project philosophy explicitly rejects.

**Understanding in Hermeneia is navigability of the Hermeneutic Field.**

A reader understands a corpus to the degree that:

1. They can locate Concepts in the Field and trace their Relationships.
2. They are aware of multiple Perspectives and their differences.
3. They can articulate Perspective Debt — the gaps in what has been explored.
4. They can pose well-formed epistemic questions (Dialogue entries) about unresolved tensions.
5. They have encountered the field's contradictions without needing to resolve them.

Understanding, in this model, is **not a destination** — it is a capacity for continued inquiry. A reader who understands *The Great Gatsby* is not one who has "figured it out." It is one who can move through the Hermeneutic Field for that corpus with increasing fluency — noticing connections, recognizing frames, asking richer questions.

---

### Operational Definition

**Understanding(reader R, corpus C)** = a vector:

```
U(R, C) = (
    Field_Coverage(R, C),      # proportion of Field the reader has explored
    Perspective_Breadth(R, C), # proportion of active Perspectives encountered
    Dialogue_Depth(R, C),      # mean quality-proxy of reader's Dialogue entries
    Horizon_Awareness(R, C),   # reader's exposure to the Field's unresolved edge
)
```

Where:
- **Field_Coverage** = `|R.known_concept_ids| / |concepts in C|`
- **Perspective_Breadth** = `|R.encountered_perspective_ids| / |active_perspectives in C|`
- **Dialogue_Depth** = `|R.dialogue_ids| / |concepts in R.known_concept_ids|` (Dialogue per Concept encountered, capped at 1.0)
- **Horizon_Awareness** = proportion of the reader's `traversal_history` that includes Concepts at the frontier of their Semantic Neighborhood (depth = max depth encountered)

Understanding is multi-dimensional. A single scalar score is not produced. The Planner uses the vector, not a flattened sum.

---

### The "Not Answers, But Questions Well-Posed" Test

Q-P3-001 proposed: *"Two readers with different concept maps but equal 'time spent' can have different Understanding scores."*

Under this ADR: Yes. A reader who has spent time circling the same familiar Concepts has low Field_Coverage and low Horizon_Awareness despite high time-in-session. A reader who has navigated broadly and submitted Dialogue entries has higher Understanding across all dimensions. Time spent is not in the formula. Epistemic exposure and contribution are.

---

## Constitutional Alignment

- **Project Philosophy** ("The goal is not answers, but questions well-posed"): Understanding is defined as the capacity for continued inquiry, not as having reached correct answers.
- **ADR-0030** (ReaderModel): All Understanding dimensions are computed from ReaderModel fields — no new data required.
- **ADR-0017** (Dialogue): Dialogue_Depth uses the reader's Dialogue contribution as the most direct evidence of engaged understanding.
