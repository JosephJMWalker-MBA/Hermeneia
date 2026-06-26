# ADR-0029: Semantic Neighborhood — Formal Definition

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P2-005 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Low

---

## Context

The Transformation Planner sequences Concept visits for a reader. To do this, it needs to reason about which Concepts can be introduced together and which should come in sequence. The Semantic Neighborhood defines the local graph context of a Concept — the other Concepts reachable from it within a bounded number of Relationship traversals.

---

## Decision

### Formal Definition

The **Semantic Neighborhood** of Concept C at depth D under Perspective P in Field F is the set of all Concepts reachable from C by traversing at most D directed Relationship edges whose `perspective_id` matches P.

```
N(C, D, P, F) = {C' | ∃ path (C = C_0, C_1, ..., C_k = C') in R(P, F) where k ≤ D}
```

where `R(P, F)` is the subgraph of the Relationship graph containing only Relationships with `perspective_id = P.id`.

For a cross-Perspective neighborhood (all Perspectives):

```
N(C, D, *, F) = {C' | ∃ path (C = C_0, ..., C_k = C') in R(F) where k ≤ D}
```

where `R(F)` is the full Relationship graph regardless of Perspective.

C is always a member of its own neighborhood: `C ∈ N(C, D, P, F)` for all D ≥ 0.

---

## Default Parameters

| Parameter | Default | Rationale |
|---|---|---|
| Depth D | 2 | Depth 1 gives only directly connected Concepts. Depth 2 adds one layer of context — Concepts connected through a single intermediary. Depth 3+ grows exponentially in dense graphs and loses semantic coherence. |
| Perspective P | `*` (all Perspectives) | The Planner may request a single-Perspective neighborhood for targeted traversal or a cross-Perspective neighborhood for discovery. |

---

## Relationship Graph Properties

The Relationship graph is a directed graph where:
- **Nodes** are Concepts.
- **Edges** are Relationships with type predicate and optional `perspective_id`.
- **Traversal** for N(C, D, P) follows edges in either direction (undirected traversal by default), because "A symbolizes B" and "B is symbolized by A" both indicate semantic proximity.

Directed traversal (follow only outgoing or only incoming edges) is available as a query option but is not the default.

---

## Uses in the Transformation Planner

The Semantic Neighborhood is used by the Planner for:

1. **Concept grouping:** Concepts in the same Neighborhood at depth 1 can be introduced together in a single narrative segment without disorienting jumps.

2. **Sequencing:** To move from Concept A to Concept B, the Planner finds the shortest path through the Relationship graph. The intermediate Concepts on that path form the natural reading sequence.

3. **Curiosity routing:** Concepts at the edge of a Neighborhood (at depth D but not at depth D-1) are "just beyond the reader's current horizon" — they are the natural next step.

4. **Isolation detection:** A Concept with `|N(C, 1, *, F)| = 1` (only itself) is isolated — it has no Relationships. It cannot be introduced through contextual connection. The Planner must introduce it directly from its source Observations.

---

## Validation Test

**Test:** In a *Gatsby* corpus under a Symbolist Perspective, compute N(`green_light`, 2, Symbolist, F).

**Expected result** might include:
- Depth 1: `American Dream`, `Daisy`, `Gatsby's desire`
- Depth 2: `Old Money`, `social class`, `unattainable ideal`, `Tom Buchanan`

A literary scholar should recognize this as a semantically coherent cluster. The Planner can route a reader through this neighborhood as a thematic unit.

**Failure condition:** If `Valley of Ashes` appears at depth 1 under the Symbolist Perspective (when it is structurally more connected under a Marxist Perspective), the Perspective-filtering is broken.

---

## Validation Rules

```python
neighborhood = compute_neighborhood(concept_C, depth=2, perspective="*", field=F)
assert concept_C in neighborhood  # C is always in its own neighborhood
assert len(neighborhood) >= 1     # at least C itself

# Depth 0 neighborhood is just C
depth_0 = compute_neighborhood(concept_C, depth=0, perspective="*", field=F)
assert depth_0 == {concept_C}

# Depth N neighborhood is a superset of depth N-1
for d in range(1, 4):
    assert compute_neighborhood(C, d-1, "*", F).issubset(compute_neighborhood(C, d, "*", F))
```

---

## Constitutional Alignment

- **Invariant 4** (Architectural Decoupling): Neighborhood computation is a graph traversal algorithm — no LLM involvement.
- **ADR-0023** (Contradiction preservation): Cross-Perspective neighborhoods include Concepts connected through contradictory Relationships. The neighborhood does not resolve contradictions; it surfaces the full relational context.
