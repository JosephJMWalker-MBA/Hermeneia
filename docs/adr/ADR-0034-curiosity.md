# ADR-0034: Curiosity — A Planner Heuristic, Not a Reader Property

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P3-004 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

The architecture references a "Curiosity Engine." Q-P3-004 asks whether Curiosity is a property of the ReaderModel, the Field, or a planning heuristic.

---

## Decision

**Curiosity is a Planner heuristic, not a stored property of the Reader or the Field.**

Curiosity is a scoring function that the Transformation Planner uses to rank unexplored Concepts when generating the next session's plan. It is computed from the intersection of ReaderModel state (what the reader hasn't seen) and Field metrics (what matters in the Field that hasn't been seen).

---

### Formal Definition

```
Curiosity(C, R, F) = MP(C, F) × gap(C, F) × unexplored(C, R)
```

Where:
- `MP(C, F)` = Meaning Pressure of C (ADR-0025) — how central is this Concept?
- `gap(C, F)` = `MP(C, F) - ID_norm(C, F)` from ADR-0028 — how under-interpreted is this Concept relative to its structural importance?
- `unexplored(C, R)` = 1.0 if C is not in R.known_concept_ids, 0.0 otherwise

Concepts the reader has already seen have Curiosity = 0.0.

The Curiosity ranking for a reader is:
```
CuriosityRanking(R, F) = sorted Concepts by Curiosity(C, R, F) descending
```

This list represents the Field's frontier for this reader: Concepts that are important, under-read, and not yet encountered.

---

### Curiosity and Semantic Neighborhoods

The Planner does not route readers to arbitrary high-Curiosity Concepts. It routes them to high-Curiosity Concepts that are reachable through their current Semantic Neighborhood (ADR-0029).

This prevents disorienting jumps: the reader is guided toward what they don't know yet, but via a path through what they already know.

```
reachable_curiosity(R, F) = [C for C in CuriosityRanking(R, F) 
                              if C ∈ N(last_concept(R), depth=2, "*", F)]
```

---

### Can Curiosity Be Satisfied?

Q-P3-004 asked: *"Can Curiosity be satisfied (and if so, does it disappear or transform)?"*

Curiosity for a specific Concept is satisfied when the reader encounters it: `unexplored(C, R) → 0.0`. The Concept drops to Curiosity = 0.0 and disappears from the ranking.

New Curiosity emerges as the reader's Semantic Neighborhood expands. Encountering Concept C expands the reader's horizon to C's depth-2 neighborhood, surfacing new Concepts in `CuriosityRanking` that were previously too far away to register.

Curiosity is never globally satisfied while there are unexplored Concepts in the Field. It transforms: as one frontier is explored, a new frontier becomes visible.

---

### Relationship to Perspective Debt

High Perspective Debt for a Concept does NOT automatically generate Curiosity. A high-PD Concept that the reader has already encountered (known) has `unexplored = 0.0` and Curiosity = 0.0.

However, a high-PD Concept that the reader has seen through only one Perspective generates partial Curiosity through the `new_pairs` mechanism in ADR-0032's PerspectivalDiversity component. The Planner can route the reader back to a known Concept through a new Perspective — this is represented in the SG formula as a PerspectivalDiversity gain.

---

## Constitutional Alignment

- **Invariant 4** (Architectural Decoupling): Curiosity is arithmetic over ReaderModel state and Field metrics. No LLM involvement.
- **ADR-0030** (ReaderModel): Curiosity reads `known_concept_ids` from the ReaderModel to determine `unexplored`.
- **ADR-0028** (Interpretive Density): Curiosity uses the `gap` measure from Interpretive Density.
