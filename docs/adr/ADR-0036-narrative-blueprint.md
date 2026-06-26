# ADR-0036: NarrativeBlueprint — Schema and Constitutional Role

> **Supersession notice (2026-06-19):** Partially superseded by
> [`CA-0003`](../amendments/CA-0003-architect-plan-contract.md).
> NarrativeBlueprint is no longer the direct Artist contract. ArchitectPlan is
> the canonical compiled semantic contract.

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P0-007 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

NarrativeBlueprint is the Architect's output and the Artist's sole input. ADR-0003 establishes the two-writer model. The Critic validates that the Artist's prose does not exceed the Blueprint's semantic commitments.

Q-P0-007 asks what fields a NarrativeBlueprint contains. This cannot be left unspecified: the Critic must validate against the Blueprint without reading the prose's free text, which is only possible if the Blueprint's semantic constraints are machine-readable.

---

## Decision

### Constitutional Role

The NarrativeBlueprint is the **semantic contract** for a narrative rendering. It contains:
1. The Observations that may be cited (an exhaustive, closed set)
2. The Perspectives the rendering must represent
3. The logical structure of the argument (claims, sequence, dependency)
4. Uncertainty and evidential status markers for each claim
5. Semantic no-fly zones (forbidden inferences the Architect has explicitly excluded)

The Artist's task is to render the Blueprint in natural language without adding to, removing from, or distorting any of these five commitments.

---

### NarrativeBlueprint Schema

| Field | Type | Requirement | Description |
|---|---|---|---|
| `id` | String (hash) | Required | SHA-256 of `(corpus_id, reader_id, session_id, created_at)` |
| `corpus_id` | String | Required | The `.herm` bundle this Blueprint is for. |
| `reader_id` | String | Required | The ReaderModel this Blueprint targets. |
| `session_id` | String | Required | The reading session this Blueprint was generated for. |
| `created_by` | String | Required | `"architect"` always. AI Provenance required. |
| `ai_provenance_id` | String | Required | FK to `ai_provenance` table (ADR-0009). |
| `ratified_by` | String | Required | Steward ID who approved this Blueprint. Human-only (ADR-0010). |
| `ratified_date` | ISO 8601 datetime | Required | When the steward approved. |
| `cited_observation_ids` | List[String] | Required | The closed set of Observation IDs the Artist may cite. No others. |
| `required_perspective_ids` | List[String] | Required | Perspectives that MUST appear in the rendering. |
| `permitted_perspective_ids` | List[String] | Required | Perspectives the Artist may include if useful. Must be a superset of `required_perspective_ids`. |
| `claims` | List[BlueprintClaim] | Required | See below. Ordered; order is the recommended presentation sequence. |
| `forbidden_inferences` | List[String] | Required | Natural-language statements of propositions the Artist must NOT assert. Machine-validated by the Critic. |
| `target_register` | Enum | Required | `academic`, `accessible`, `expository`, `dialogue`. Informs the Artist's stylistic choices. |
| `active` | Boolean | Required | `true` until superseded by a new Blueprint for the same (reader, session). |
| `superseded_by` | String | Conditional | ID of the Blueprint that replaces this one. Null if active. |

### BlueprintClaim Schema

Each claim in the `claims` list is a machine-readable semantic unit.

| Field | Type | Requirement | Description |
|---|---|---|---|
| `claim_id` | String | Required | Unique within this Blueprint. |
| `proposition` | String | Required | A single declarative statement. No hedges embedded; hedges go in `evidential_status`. |
| `source_observation_ids` | List[String] | Required | Observations that support this claim. Must be a subset of `cited_observation_ids`. |
| `perspective_id` | String | Required | The single Perspective from which this claim is made (ADR-0021). |
| `evidential_status` | Enum | Required | `established`, `contested`, `speculative`, `uncertain`. |
| `depends_on_claim_ids` | List[String] | Optional | Claims that must be established before this claim can be introduced. Defines logical sequence. |
| `field_contradiction_ids` | List[String] | Optional | FieldContradictions this claim is aware of. The Artist must acknowledge the contradiction if these IDs are non-empty. |

---

### What the Blueprint Is NOT

- It is NOT the narrative text. It is the semantic specification.
- It is NOT a free-text prompt to an LLM. Every field is structured.
- It is NOT mutable after ratification. If the steward needs changes, a new Blueprint is created.
- It does NOT contain allowed stylistic moves. Style is entirely the Artist's domain.
- It does NOT specify the length or format of the output. These are stylistic decisions.

---

### Deferred Objects

NarrativeBlueprint depends on objects still deferred:
- **Concept** (deferred in ADR-0024) — the Blueprint references Observations and Perspectives, not Concepts directly, to avoid dependency on the deferred Concept schema.
- **ReaderModel** (ratified ADR-0030) — the Blueprint is reader-specific and cites the reader's current snapshot.

The Blueprint schema is designed to be Concept-independent. If/when Concept is ratified, a `conceptual_scope` field may be added by amendment.

---

### Append-Only and Provenance

NarrativeBlueprints are append-only after ratification. They are stored in the `narrative_blueprints` table with full AI Provenance (ADR-0009) because the Architect is an AI component. The steward's ratification is recorded in `ratified_by` and `ratified_date`.

If a Blueprint is found to contain an error after ratification, a new Blueprint is created with `superseded_by` pointing to the new one. The original Blueprint is never deleted or modified.

---

## Validation Test

Q-P0-007 proposed: *"Given five Observations from Gatsby and one declared Perspective, produce a NarrativeBlueprint. Then produce two prose renderings — one compliant, one violating. The Critic must detect the violation from the Blueprint alone without reading the prose."*

**Compliant rendering:** Cites only `cited_observation_ids`. Acknowledges the `evidential_status` of each claim. Does not assert any proposition in `forbidden_inferences`. Uses language consistent with `target_register`.

**Violating rendering:** Asserts a causal claim not present in any `claims[*].proposition`. The Critic detects the violation by checking: "Is this claim's proposition in `claims`? Is it supported by `source_observation_ids` that are in `cited_observation_ids`?" If no, the Critic flags a fidelity violation.

---

## Constitutional Alignment

- **ADR-0003** (Two-writer model): This ADR provides the formal schema that ADR-0003 required but did not specify.
- **ADR-0010** (Human-only decisions): Blueprint ratification is constitutionally reserved for human stewards.
- **ADR-0009** (AI Provenance): The Architect is an AI component; its output carries mandatory AI Provenance.
- **ADR-0021** (Single Perspective per Interpretation): Each BlueprintClaim carries exactly one `perspective_id`.
- **Invariant 4** (Architectural Decoupling): The Blueprint's structure is machine-readable data, not a free-text prompt. The Critic validates it arithmetically.
