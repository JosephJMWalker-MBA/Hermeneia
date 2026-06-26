# ADR-0024: The Full Canonical Ontology Object List

> **Supersession notice (2026-06-19):** Partially superseded by
> [`CA-0001`](../amendments/CA-0001-forensic-evidence-and-identity.md) and
> [`CA-0002`](../amendments/CA-0002-epistemic-classification.md). The
> constitutional evidence chain and complete epistemic classification govern
> where this list omits or conflicts with them.

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P1-008 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Existential

---

## Context

Three sources disagree on what belongs in the Hermeneia ontology:

- `docs/06_Ontology.md`: 5 objects (Observation, Provenance, ContextCapsule, Concept, Relationship)
- `docs/specs/ontology.spec.md`: 9 objects (adds Perspective, Interpretation, Dialogue, Reflection, NarrativeBlueprint)
- `hermeneia/ontology/` directory: 14 class stubs (adds Manifest, ReaderModel, TransformationPlan, Question, ContinuityNode)

The canonical list cannot be derived from the code. The code is stubs, not specifications. This ADR produces the definitive, numbered list of canonical ontology objects based on all Milestone R0–R3 ratifications.

Every class stub in the codebase must correspond to exactly one entry on this list. Every entry on this list must either have a ratified ADR or have its schema deferred to a specific future milestone.

---

## The Canonical List

The following 15 objects are canonical ontology objects in Hermeneia version 1.0. They are numbered for reference. Objects are grouped by epistemic layer.

---

### Layer 0 — Source and Registration

**Object 1: SourceDocument**  
A registered source document. The anchor for all Observation provenance.  
Defined by: ADR-0013  
Schema: `source_documents` table  
Status: Ratified

**Object 2: ContextCapsule**  
Steward-authored contextual metadata describing the historical, political, and biographical context surrounding a source document.  
Defined by: ADR-0020  
Schema: `context_capsules` table  
Status: Ratified

---

### Layer 1 — Observation and Provenance

**Object 3: Observation**  
The smallest immutable record of information intentionally extracted from a source document.  
Defined by: ADR-0006  
Schema: `observations` table  
Status: Ratified

**Object 4: Provenance**  
The record that uniquely locates an Observation in its source document.  
Defined by: ADR-0012, ADR-0013  
Schema: `provenance` table  
Status: Ratified

**Object 5: AIProvenance**  
The record documenting the origin of any AI-generated object: model, version, prompt, parent objects, accepting steward.  
Defined by: ADR-0009  
Schema: `ai_provenance` table  
Status: Ratified

---

### Layer 2 — Entity and Concept Graph

**Object 6: ContinuityNode**  
An identity anchor that persists across time while accumulating observations, interpretations, and relationships.  
Defined by: ADR-0007  
Schema: `continuity_nodes` table  
Status: Ratified

**Object 7: Concept**  
A named, reusable semantic unit extracted from Observations and anchored to the Hermeneutic Field. Represents an idea, theme, symbol, or entity type that recurs across the corpus.  
Defined by: ADR deferred to Milestone R4 (Q-P2 series)  
Schema: `concepts` table  
Status: Deferred — schema not yet ratified. Class stub exists. No implementation.

**Object 8: Relationship**  
A Perspective-scoped directed edge between two Concepts, carrying a typed predicate.  
Defined by: ADR-0023 (Perspective-scoping), schema deferred to Milestone R4  
Schema: `relationships` table  
Status: Partially ratified — Perspective-scoping requirement ratified by ADR-0023. Full predicate vocabulary and schema deferred to Milestone R4.

---

### Layer 3 — Interpretation Layer

**Object 9: Perspective**  
A declared epistemic stance or methodological frame from which Observations may be interpreted.  
Defined by: ADR-0015, ADR-0020, ADR-0021  
Schema: `perspectives` table  
Status: Ratified

**Object 10: Interpretation**  
A propositional statement derived from one or more Observations, made from within exactly one declared Perspective.  
Defined by: ADR-0011, ADR-0015, ADR-0021  
Schema: `interpretations` table  
Status: Ratified

---

### Layer 4 — Human Dialogue and Annotation

**Object 11: Dialogue**  
A human-authored epistemic contribution addressed to a specific named object in the Field.  
Defined by: ADR-0017, ADR-0018  
Schema: `dialogues` table  
Status: Ratified

**Object 12: FieldQuestion**  
A system-generated question surfacing a coverage gap, Perspective Debt, or field contradiction for steward attention. Not a human contribution.  
Defined by: ADR-0019  
Schema: `field_questions` table  
Status: Ratified

**Object 13: FieldContradiction**  
A system-generated record flagging contradictory Relationships between the same Concepts under different Perspectives.  
Defined by: ADR-0023  
Schema: `field_contradictions` table  
Status: Ratified

---

### Layer 5 — Planning and Narrative

**Object 14: NarrativeBlueprint**  
A structured plan for transforming a Hermeneutic Field into a narrative artifact, authored by the Architect agent and ratified by a human steward.  
Defined by: ADR deferred to Milestone R6 (Q-P0-007)  
Schema: `narrative_blueprints` table  
Status: Deferred — schema not yet ratified. Class stub exists. No implementation.

**Object 15: ReaderModel**  
A representation of a reader's current knowledge state, learning gaps, and curiosity vectors, used by the Transformation Planner to sequence concepts.  
Defined by: ADR deferred to Milestone R5 (Q-P3 series)  
Schema: `reader_models` table  
Status: Deferred — schema not yet ratified. Class stub exists. No implementation.

**Object 16: TransformationPlan**  
A sequence of epistemic moves — Concept visits, Perspective applications, Dialogue surfacings — generated by the Transformation Planner for a specific ReaderModel and NarrativeBlueprint.  
Defined by: ADR deferred to Milestone R5/R6  
Schema: `transformation_plans` table  
Status: Deferred — schema not yet ratified. Class stub exists. No implementation.

---

## Objects That Are NOT in the Canonical List

The following objects were considered and explicitly excluded:

| Object | Disposition |
|---|---|
| **Manifest** | Storage artifact, not ontology object. Lives in `storage/`, not `ontology/`. ADR-0008. |
| **Reflection** | Human cognitive act, no stored representation. Class stub to be deleted. ADR-0016. |
| **Claim** | Served by Interpretation. No separate class. ADR-0011. |
| **Question** (as originally stubbed) | Split: human questions → `dialogue_type: question` in Dialogue; system questions → FieldQuestion. ADR-0019. |

---

## Codebase Reconciliation

**Stubs to keep and implement (matching canonical list):**
- `observation.py` → Object 3
- `provenance.py` → Object 4
- `continuity_node.py` → Object 6
- `concept.py` → Object 7 (deferred schema)
- `relationship.py` → Object 8 (deferred schema)
- `perspective.py` → Object 9
- `interpretation.py` → Object 10
- `dialogue.py` → Object 11
- `narrative_blueprint.py` → Object 14 (deferred schema)
- `reader_model.py` → Object 15 (deferred schema)
- `transformation_plan.py` → Object 16 (deferred schema)

**New files to create (objects defined by ratifications but not stubbed):**
- `source_document.py` → Object 1 (ADR-0013)
- `context_capsule.py` → Object 2 (ADR-0020)
- `ai_provenance.py` → Object 5 (ADR-0009)
- `field_question.py` → Object 12 (ADR-0019, replaces `question.py`)
- `field_contradiction.py` → Object 13 (ADR-0023)

**Stubs to delete:**
- `reflection.py` (ADR-0016)
- `manifest.py` (ADR-0008 — moved to `storage/manifest.py`)
- `question.py` (ADR-0019 — replaced by `field_question.py`)

---

## Implementation Gates Updated

This ADR closes Q-P1-008, the prerequisite for complete schema implementation. With this ADR ratified:

- All 16 canonical object types are identified and counted.
- 11 of the 16 have ratified schemas (Objects 1–6, 9–13).
- 5 are deferred (Objects 7, 8, 14–16), awaiting R4–R6 ratifications.
- Implementation of the 11 ratified objects may proceed.
- Class stubs for the 5 deferred objects exist but must not be field-implemented until their milestone ratifications are complete.

---

## The Three-Source Reconciliation

| Source | Object count | Objects it included that are not canonical | Objects missing that are canonical |
|---|---|---|---|
| `06_Ontology.md` | 5 | None missing from canonical list, but incomplete | Missing: ContinuityNode, Perspective, Interpretation, Dialogue, FieldQuestion, FieldContradiction, AIProvenance, NarrativeBlueprint, ReaderModel, TransformationPlan, SourceDocument |
| `ontology.spec.md` | 9 | Reflection (not canonical) | Missing: ContinuityNode, FieldQuestion, FieldContradiction, AIProvenance, SourceDocument, TransformationPlan, ReaderModel |
| `hermeneia/ontology/` | 14 stubs | Manifest (moved to storage), Reflection (removed), Question (split) | Missing: AIProvenance, SourceDocument, FieldQuestion, FieldContradiction |

The canonical list (this ADR, 16 objects) supersedes all three sources. `06_Ontology.md` and `ontology.spec.md` should be updated to reference this ADR as the authoritative object list.

---

## Validation Rules

```python
CANONICAL_OBJECTS = {
    "source_document", "context_capsule",
    "observation", "provenance", "ai_provenance",
    "continuity_node", "concept", "relationship",
    "perspective", "interpretation",
    "dialogue", "field_question", "field_contradiction",
    "narrative_blueprint", "reader_model", "transformation_plan"
}

NON_CANONICAL_STUBS_TO_DELETE = {"reflection", "manifest", "question"}

# Every .py file in hermeneia/ontology/ must correspond to a canonical object
for stub in list_ontology_stubs():
    assert stub in CANONICAL_OBJECTS or stub in NON_CANONICAL_STUBS_TO_DELETE

# No canonical object may be unaccounted for
for obj in CANONICAL_OBJECTS:
    assert obj_has_stub_or_implementation(obj)
```

---

## Migration Policy

1. If the canonical list is amended (an object added or removed), a new ADR superseding this one must be written.
2. Objects may be added to the list only if they have a ratified ADR with full schema, inclusion/exclusion criteria, and provenance implications.
3. Objects may be removed from the list only through the Amendment process in RATIFICATION.md Part II, with full backwards compatibility analysis.
4. The object count (currently 16) is informational, not constitutional. The canonical list is authoritative, not the count.

---

## Constitutional Alignment

- **Invariant 5** (Canonical Object List): This ADR is the ratification of Invariant 5. The Canonical Object List is now ratified and must be updated through the amendment process, not through code.
- **Article I** (Reality precedes interpretation): Objects in Layers 0–2 are closer to source reality. Objects in Layers 3–5 are closer to interpretation and narrative.
- **ADR-0008** (Manifest): Manifest is confirmed as non-canonical.
- **ADR-0016** (Reflection): Reflection is confirmed as non-canonical.

---

## Consequences

**Positive:**
- For the first time, the ontology has a single authoritative source of truth. Every engineer, every ADR, and every specification can reference "the canonical object list" without ambiguity.
- The three-source inconsistency is resolved. `06_Ontology.md` and `ontology.spec.md` are now outdated — they should be updated to reference this ADR.
- The Appendix B implementation gates in EPISTEMIC_BACKLOG.md can now be updated with precise object-level granularity.

**Negative:**
- 5 of 16 objects are deferred. The schema for Concept, Relationship, NarrativeBlueprint, ReaderModel, and TransformationPlan cannot be implemented until their milestone ratifications are complete. Engineers working on deferred objects must continue to use stubs only.
