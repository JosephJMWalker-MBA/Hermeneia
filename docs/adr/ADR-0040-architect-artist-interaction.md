# ADR-0040: Architect and Artist Interaction Protocol

> **Supersession notice (2026-06-19):** Partially superseded by
> [`CA-0003`](../amendments/CA-0003-architect-plan-contract.md). The Artist
> consumes ArchitectPlan under ExpressionProfile constraints rather than
> receiving NarrativeBlueprint as its direct contract.

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P4-004 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

ADR-0003 accepts the two-writer model. ADR-0036 defines the NarrativeBlueprint. ADR-0037 and ADR-0038 define the semantic invariants and the Critic's validation taxonomy. Q-P4-004 asks how the Architect and Artist actually interact: sequential or iterative? Can the Artist request clarification? Does the Artist have access to the Field directly?

---

## Decision

**The Architect and Artist are strictly decoupled. The pipeline is sequential, not iterative.**

The Artist's sole input is the ratified NarrativeBlueprint. The Artist does not have access to:
- The Hermeneutic Field
- The source Observations (only what the Blueprint references via `cited_observation_ids`)
- The ReaderModel
- The Transformation Planner's session plan
- Any information not encoded in the Blueprint

This constraint is constitutional. If the Artist could access the Field directly, it could introduce unsupported claims by drawing on Field data not authorized by the Architect.

---

### Sequential Pipeline

```
ReaderModel + Field
      ↓
  [Architect]
      ↓
NarrativeBlueprint (AI-generated)
      ↓
  [Steward ratification] ← Human-only (ADR-0010)
      ↓
Ratified NarrativeBlueprint
      ↓
   [Artist]
      ↓
Rendering (prose output)
      ↓
   [Critic]
      ↓
CriticReport + NarrativeScore
      ↓
  [Steward review if NF < 1.0] ← Human-only (ADR-0010)
      ↓
Delivered Rendering
```

Each stage completes before the next begins. There is no feedback loop between Artist and Architect within a single rendering cycle.

---

### Can the Artist Request Clarification from the Architect?

**No.** The Artist cannot request Blueprint clarification at render time. This is a strict architectural constraint.

**Rationale:** If the Artist discovers during rendering that the Blueprint is ambiguous or incomplete, the correct response is to flag the ambiguity as an advisory violation in the Critic's pass and allow the steward to address it. The steward may commission a revised Blueprint (a new Architect invocation), but the Artist does not initiate this.

This prevents two failure modes:
1. **The Artist interpreting ambiguity in its own favor** — adding content not in the Blueprint to fill a gap.
2. **Iterative drift** — each Artist-Architect exchange introduces a new opportunity for semantic creep.

---

### Can the Artist Reject a Blueprint?

**Not unilaterally.** If the Artist's rendering attempt produces NF below the delivery threshold across multiple attempts, this is surfaced to the steward as a `low_fidelity_blueprint` flag. The steward may then decide to revise the Blueprint (a human-only decision, ADR-0010).

The Artist does NOT have the authority to judge whether a Blueprint is "rhetorically unrealizable." A Blueprint is always realizable in some form; the Artist's task is to find the best realization within the semantic constraints. If the result is poor prose, that is an advisory violation for the steward to evaluate — not grounds for Artist refusal.

---

### What the Artist Receives

The Artist receives exactly:
1. The ratified `NarrativeBlueprint` object (full schema, ADR-0036)
2. The verbatim text of all Observations in `cited_observation_ids` — because the Artist may need to quote from them, but this text is provided by the Blueprint delivery system, not retrieved by the Artist from the Field

The Artist does NOT receive:
- The Hermeneutic Field graph
- The ReaderModel
- Any FieldContradiction objects beyond their IDs listed in `field_contradiction_ids`
- Any Perspective objects beyond their IDs in `required_perspective_ids`

---

### Rendering Attempts and the Critic Loop

The Artist may make up to N rendering attempts before the steward is notified of a persistent low-NF result. N is a configurable system parameter (default: 3).

```
Attempt 1 → CriticReport → NF ≥ 0.85? → deliver
                          → NF < 0.85?  → Attempt 2
Attempt 2 → CriticReport → NF ≥ 0.85? → deliver
                          → NF < 0.85?  → Attempt 3
Attempt 3 → CriticReport → NF ≥ 0.85? → deliver
                          → NF < 0.85?  → flag steward: persistent_low_fidelity
```

After N failed attempts, the steward reviews the Blueprint and the Critic reports and decides whether to revise the Blueprint or approve delivery with the best NF achieved.

---

### AI Provenance for Both Writers

Both the Architect and Artist are AI components. Their outputs carry mandatory AI Provenance (ADR-0009):

- **Architect output (Blueprint):** `ai_provenance_id` in the Blueprint schema (ADR-0036).
- **Artist output (Rendering):** A `rendering_ai_provenance_id` stored alongside the rendering.

Both are staged before delivery; both require steward ratification (Blueprint) or steward review (Rendering) before reaching the reader. The steward's approval is recorded as a human provenance event.

---

### The Critic Is Not a Writer

The Critic is a validation component, not a third writer. It reads the Blueprint and the Rendering and produces a `CriticReport`. It does not modify the Rendering, suggest revisions, or interact with the Artist. The CriticReport is delivered to the steward and, if the NF score is below the delivery threshold, to the Artist for use in the next rendering attempt.

The Artist may use the CriticReport's `violations` list to identify which claims failed validation in the previous attempt. It does not receive feedback beyond what the CriticReport contains.

---

## Constitutional Alignment

- **ADR-0003** (Two-writer model): This ADR provides the concrete interaction protocol that ADR-0003 established as a model but did not specify.
- **ADR-0036** (NarrativeBlueprint): The Blueprint's schema determines what the Artist receives.
- **ADR-0037** (Style/semantics separation): The strict decoupling here enforces the separation: the Artist cannot access Field data, so it cannot introduce unsupported content.
- **ADR-0010** (Human-only decisions): Blueprint revision, steward delivery approval, and persistent low-NF resolution are all human-only decisions.
- **ADR-0009** (AI Provenance): Both Architect and Artist outputs carry mandatory AI Provenance.
- **Invariant 4** (Architectural Decoupling): The pipeline is data-driven; no component queries the LLM for architectural decisions.
