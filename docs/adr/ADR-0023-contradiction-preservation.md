# ADR-0023: Contradictory Perspectives Coexist — Contradiction Is a First-Class Epistemic State

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P6-003 and Q-P6-004 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

Axiom 3 states that Perspectives accumulate — they do not overwrite each other. Q-P6-003 asks how the Field represents two contradictory Perspectives without resolving the contradiction. Q-P6-004 asks how disagreement within a single Perspective is preserved.

Both questions share a common constitutional principle: **contradiction and disagreement are not error conditions. They are first-class epistemic states that must be preserved, not resolved.**

---

## Decision

### Part I: Contradiction Between Perspectives

**Contradiction between Perspectives is represented structurally through Perspective-scoped Relationships.**

Every Relationship in the Hermeneutic Field carries a `perspective_id`. A Relationship is not a universal fact — it is a Perspective-relative assertion: "from Perspective P, Concept A relates to Concept B with predicate R."

**Example:**
- `(green_light) --[symbolizes]--> (American Dream)` under Perspective: `Symbolist reading`
- `(green_light) --[conceals]--> (class_inequality)` under Perspective: `Marxist reading`

Both Relationships coexist in the `relationships` table. Neither supersedes the other. A query for "all Relationships where source = green_light" returns both. The caller is responsible for filtering by Perspective if they want a single-frame view.

**FieldContradiction Object**

When the system detects that two active Relationships connect the same source and target Concepts under different Perspectives with conflicting predicates, it may generate a `FieldContradiction` record. This is a system-generated annotation — not a human judgment — that surfaces the contradiction for steward attention.

| Field | Type | Requirement |
|---|---|---|
| `id` | String (hash) | Required |
| `relationship_a_id` | String | Required. First contradicting Relationship. |
| `relationship_b_id` | String | Required. Second contradicting Relationship. |
| `contradiction_type` | Enum | Required. `opposite_predicate`, `contradictory_assertion`, `incompatible_scope`. |
| `status` | Enum | Required. `open`, `acknowledged`, `resolved_by_dialogue`. |
| `generated_at` | ISO 8601 datetime | Required. |
| `acknowledged_by` | String or null | Steward who has reviewed this contradiction. |
| `resolved_by_dialogue_id` | String or null | Dialogue entry that addresses this contradiction. |

**Critical:** A FieldContradiction is never automatically resolved. The `status: resolved_by_dialogue` means a human has written a Dialogue entry that addresses the contradiction. It does not mean the contradiction has been eliminated. Both contradicting Relationships remain in the database. The `resolved_by_dialogue` status is a pointer to the human discussion, not a deletion of either side.

---

### Part II: Disagreement Within a Perspective

**Disagreement within a Perspective is represented through Dialogue of `dialogue_type: dispute`.**

If a steward disagrees with an Interpretation made under the same Perspective, they author a Dialogue entry with:
- `dialogue_type: dispute`
- `disputes_id`: the Interpretation being disputed
- `content`: the counter-argument

The disputed Interpretation is not deleted. The dispute does not create a new Interpretation (that would require a separate authorship act). The dispute records that a named human steward contested the claim, with their argument on record.

**Can a dispute be resolved?**

A dispute may be "answered" in two ways:
1. The original author responds with a Dialogue entry (`dialogue_type: observation` or `annotation`) explaining or defending their Interpretation.
2. A new Interpretation is produced under the same Perspective that supersedes the disputed one, incorporating the dispute's insight. The new Interpretation carries `superseded_by` backlinks from the old one.

In neither case is the dispute "closed" or the disputed Interpretation deleted. The full record remains.

---

### Part III: Conflict Resolution Is Human-Only

ADR-0010 reserved the "resolution of epistemic conflicts where multiple valid Perspectives exist" as a constitutionally human-only decision. This means:

1. The system may surface contradictions (FieldContradiction) and disagreements (Dialogue disputes).
2. The system may not resolve them.
3. A human steward may address them through Dialogue, through supersession of an Interpretation, or by declining to act.
4. The Field preserves the unresolved state permanently. Unresolved contradiction is a valid, permanent epistemic state.

---

### Part IV: The Field Must Support Querying Contradiction

A query for "all Relationships for Concept X" must return ALL Relationships, regardless of Perspective, including contradictory ones. The query layer must not filter contradictions silently. Contradictions are data, not noise.

However, a query layer may support filtering by Perspective: "all Relationships for Concept X under Perspective P." This is a legitimate, filtered view — as long as the unfiltered view remains accessible.

**The Transformation Planner** must be able to surface active contradictions for a given Concept as part of its planning context. A NarrativeBlueprint that ignores active contradictions about a central Concept is epistemically incomplete.

---

## Validation Rules

```python
# Relationships must carry perspective_id
assert relationship.perspective_id is not None

# FieldContradiction generation: system may flag but not resolve
assert field_contradiction.status != "automatically_resolved"

# Dispute Dialogue must reference the disputed object
if dialogue.dialogue_type == "dispute":
    assert dialogue.disputes_id is not None
    assert object_exists(dialogue.disputes_id)

# No Relationship in the relationships table may be deleted to resolve a contradiction
assert count(DELETE operations on relationships table) == 0
```

---

## Constitutional Alignment

- **Axiom 3** (Perspectives accumulate): Contradictory Perspectives must accumulate, not resolve. This ADR enforces accumulation structurally through Perspective-scoped Relationships.
- **Article III** (Append-only history): FieldContradiction records and Dialogue disputes are append-only. The resolution of a contradiction is a Dialogue entry, not a deletion.
- **ADR-0010** (Human-only decisions): Conflict resolution remains human-only. The system surfaces; it does not resolve.

---

## Consequences

**Positive:**
- The Hermeneutic Field is epistemically honest: it represents the full complexity of scholarly disagreement without forcing false consensus.
- Contradiction is queryable and surfaceable. The Transformation Planner can use FieldContradiction records to generate richer, more nuanced NarrativeBlueprints.
- The dispute mechanism allows scholarly conversation to be preserved in the Field itself, not in external channels.

**Negative:**
- Consumers of the Field must handle contradictory Relationships without the system resolving them. A naive "give me the Relationship between green_light and X" query returns multiple, possibly contradictory results. The UI/query layer must be designed for this.
- FieldContradiction detection requires a comparison pass across Relationships with shared source and target Concepts. This is a compute cost that scales with the density of the relationship graph.

---

## Alternatives Considered

**Alternative: Mark one Perspective as "authoritative" per Concept, allowing its Relationships to supersede others**  
Rejected. This reintroduces the single-correct-reading assumption that the Hermeneutic Field exists to resist. There is no architecturally neutral way to designate authority across Perspectives.

**Alternative: Resolve contradiction through majority voting among stewards**  
Rejected. Democratic resolution of epistemic conflict is not epistemically valid. The fact that more stewards hold one Perspective does not make the minority Perspective wrong. Hermeneia is not a truth-arbitration system; it is an epistemic preservation system.
