# ADR-0007: ContinuityNode — Ratification as Canonical Ontology Object

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P0-008 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

Observations are records of what was said in a source document. But scholarship is not merely about statements — it is about the things that statements are about. A person, a nation, an institution, a scientific theory — these entities persist through time, accumulate changing records, and maintain identity across contradiction.

Without a canonical mechanism for identity persistence, the Hermeneutic Field becomes a flat collection of statements with no mechanism for answering the question "what is all of this *about*?" The ContinuityNode is the answer to that question.

This ADR closes Q-P0-008 from `EPISTEMIC_BACKLOG.md`.

---

## Decision

### Formal Definition

A **ContinuityNode** is an identity anchor that persists across time while accumulating changing observations, interpretations, and relationships.

A ContinuityNode is **referential, not descriptive**.

It answers: *"What enduring thing are these evolving records about?"*  
It does not answer: *"What do these records say about that thing?"*

A ContinuityNode is the anchor point to which Observations, Interpretations, Concepts, Perspectives, and Relationships may be attached. It has no semantic content of its own — it is a stable identifier, not a description. Its content accumulates through the objects that point to it.

### Validity Criteria

A ContinuityNode must satisfy all four of the following simultaneously:

1. **Identity-stable** — A ContinuityNode's ID never changes. It may accumulate new objects, but it cannot be renumbered, renamed (in the ID field), or merged with another ContinuityNode without a human ratification decision.
2. **Content-empty** — A ContinuityNode carries only the minimum required for identity: an ID, a type, a canonical label (mutable by steward decision), and temporal scope if known. It is not a description. Descriptions live in Observations and Interpretations that point to the ContinuityNode.
3. **Relation-accumulating** — All epistemic content about the entity accumulates in objects that reference the ContinuityNode. The ContinuityNode itself is the stable spine on which these objects hang.
4. **Steward-created** — ContinuityNodes are created by human stewards, not by the compiler. The Observation Compiler may propose candidate ContinuityNodes based on named entity recognition, but no candidate becomes a canonical ContinuityNode until a human steward ratifies it.

---

## Canonical Examples

The following entity types are ContinuityNodes:

| Entity type | Example |
|---|---|
| Specific person | F. Scott Fitzgerald (not "a writer") |
| Specific book | *The Great Gatsby* (1925 first edition) |
| Nation-state | The United States of America |
| Organization | Princeton University |
| Scientific theory | The theory of general relativity |
| Legal case | *Marbury v. Madison* (1803) |
| Physical object | The Elgin Marbles |
| Historical event | The French Revolution |
| Artistic work (non-book) | Beethoven's Symphony No. 9 in D minor, Op. 125 |

---

## Inclusion Criteria

The following **do** constitute valid ContinuityNodes:

1. Any entity that can be meaningfully described as "the same thing" across multiple source documents or across time.
2. Any entity whose changing state is a subject of scholarly inquiry (a person who held multiple positions, a theory that was revised, a nation whose borders changed).
3. Any entity that has an identity independent of any particular description of it (F. Scott Fitzgerald exists as an entity separate from any Observation about him).
4. Any entity that can be a meaningful anchor point for Interpretations that conflict with each other (multiple Perspectives on the same entity are a canonical use case of the Hermeneutic Field).
5. Abstract entities with stable identities over time, such as scientific theories, legal doctrines, or philosophical frameworks.

---

## Exclusion Criteria

The following **do not** constitute valid ContinuityNodes:

1. A generic type or category (not "a writer" — only "F. Scott Fitzgerald"). ContinuityNodes are instances, not classes.
2. A property or attribute (not "wealth" — only "Jay Gatsby's wealth as described in Chapter 5"). Properties attach to ContinuityNodes; they are not ContinuityNodes themselves.
3. A statement or claim (the content of Observations and Interpretations, not the anchor). "The green light represents the American Dream" is not a ContinuityNode.
4. A transient event with no enduring identity (not "the act of reading a sentence"). Events with scholarly significance may be ContinuityNodes if they are historically identified (e.g. "The bombing of Hiroshima, August 6, 1945").
5. A compiler artifact, metadata field, or storage entity (not a `.herm` bundle, not a Provenance record, not an Observation ID).
6. An AI-proposed entity that has not been ratified by a human steward.

---

## Edge Cases

**Two names, one entity**  
→ One ContinuityNode. If sources refer to both "Jay Gatz" and "Jay Gatsby" as the same person within the novel, the ContinuityNode has a canonical label (chosen by steward), an alias list, and Observations attached from both naming conventions.

**Same name, two entities**  
→ Two ContinuityNodes. "Tom" in *The Great Gatsby* is Tom Buchanan; "Tom" in another novel is a different entity. Disambiguation is a steward decision. The steward creates two ContinuityNodes with distinct IDs and documents the disambiguation rationale.

**An entity that changes its name**  
→ One ContinuityNode. The ContinuityNode tracks the canonical label and a history of used names. Name changes do not create new ContinuityNodes. ContinuityNode ID stability supersedes label stability.

**A nation that ceases to exist**  
→ One ContinuityNode with temporal scope including its end date. The Austro-Hungarian Empire existed from 1867 to 1918. ContinuityNode does not get deleted; it accumulates an end-date and its subsequent mentions are handled through Relationship objects.

**A concept that evolves significantly over time**  
→ A steward decision. If a scientific theory is amended so significantly that the pre- and post-amendment versions are treated as distinct entities in the scholarly literature, the steward may create two ContinuityNodes with a "superseded by" Relationship. If the literature treats it as continuous evolution, one ContinuityNode accumulates both sets of Observations.

**A proposed entity from entity recognition that the steward disagrees with**  
→ Rejected. The compiler proposal is discarded. No ContinuityNode is created. If the named entity appears again in the corpus, a new proposal will be generated; the steward may reconsider at that point.

---

## Serialization Rules

A ContinuityNode record must contain:

| Field | Type | Requirement |
|---|---|---|
| `id` | String (deterministic hash) | Required. Immutable after creation. |
| `type` | Enum | Required. One of: `person`, `place`, `organization`, `work`, `event`, `concept`, `legal`, `object`, `other`. |
| `canonical_label` | String | Required. Human-readable primary identifier. Mutable by steward. |
| `aliases` | List[String] | Optional. Additional names used in sources. Mutable by steward. |
| `temporal_scope_start` | Date or null | Optional. |
| `temporal_scope_end` | Date or null | Optional. |
| `ratified_by` | String | Required. Steward ID who ratified this node. |
| `ratified_date` | ISO 8601 datetime | Required. |
| `notes` | String | Optional. Steward notes on disambiguation decisions. |

The `id` field uses a deterministic hash of `(canonical_label, type, temporal_scope_start)` to reduce accidental duplicates, but the hash is advisory at creation time only. Once created, the `id` is fixed regardless of subsequent canonical_label edits.

---

## Provenance Implications

ContinuityNode creation is a steward action, not a compilation action. Its provenance record is therefore a steward provenance record (human provenance), not a compiler provenance record.

Required steward provenance for ContinuityNode creation:

| Field | Requirement |
|---|---|
| `steward_id` | Identifier of the human who created the node |
| `creation_timestamp` | ISO 8601 datetime |
| `rationale` | Brief statement of why this entity warrants a ContinuityNode |
| `source_observations` | List of Observation IDs that motivated the creation |
| `disambiguation_notes` | Any notes on how this entity was distinguished from similar entities |

If the ContinuityNode was proposed by an AI system, AI provenance is also required (see ADR-0009). The steward provenance records the human acceptance decision; the AI provenance records the proposal.

---

## Validation Rules

```python
assert continuity_node.id is not None
assert continuity_node.canonical_label is not None and len(continuity_node.canonical_label) > 0
assert continuity_node.type in VALID_CONTINUITY_NODE_TYPES
assert continuity_node.ratified_by is not None
assert continuity_node.ratified_date is not None
assert steward_provenance_exists(continuity_node.id)
```

Additionally:

- Two ContinuityNodes may not share the same `(canonical_label, type, temporal_scope_start)` tuple without explicit steward disambiguation documentation.
- AI-proposed entities that have not been ratified may not appear in the `continuity_nodes` table — they may exist only in a `proposed_continuity_nodes` staging table.
- The `canonical_label` field may be updated by stewards. Updates are versioned in a `continuity_node_label_history` table, never overwritten.

---

## Migration Policy

1. If this definition is amended, existing ContinuityNodes created under ADR-0007 remain valid.
2. If the `type` enum is expanded or renamed, existing nodes retain their original type value unless a steward explicitly migrates them.
3. No ContinuityNode may be deleted — only deactivated with a `deprecated: true` flag and a deprecation rationale, and only by a human steward.
4. If two ContinuityNodes are determined to represent the same entity (a merge is needed), the merge is a new steward action: the surviving node is annotated with `merged_from` references, and the deprecated node is marked with `merged_into`. Both remain in the database. Existing Relationships and Observations referencing the deprecated node are not rewritten; a query layer handles the alias resolution.

---

## Constitutional Alignment

- **Article I** (Reality precedes interpretation): ContinuityNodes are identity anchors, not interpretations. They don't describe; they point.
- **Article II** (Provenance mandatory): Steward provenance is required for every ContinuityNode. AI proposals require AI provenance per ADR-0009.
- **Article V** (Observations remain distinct from conclusions): ContinuityNodes have no semantic content. The content accumulates in separately tracked objects.

---

## Consequences

**Positive:**
- The Hermeneutic Field can represent "multiple contradictory things said about the same entity" — the canonical use case of humanistic scholarship.
- Identity persistence through name changes, conceptual revisions, and temporal gaps is representable without ontology drift.
- Steward ratification requirement prevents AI hallucinations from polluting the canonical entity graph.

**Negative:**
- Steward ratification requirement creates a bottleneck. Large corpora with many named entities will require significant human annotation effort.
- The merge/alias resolution strategy adds complexity to the query layer.
- The boundary between "same entity" and "related but distinct entities" (e.g. a theory before and after a major revision) will require ongoing steward judgment. This cannot be fully automated.

---

## Alternatives Considered

**Alternative: Use URIs from external authority files (VIAF, Wikidata, Library of Congress Name Authority)**  
Not rejected — but deferred. External authority alignment is a future enrichment layer, not the foundation. The ContinuityNode provides stable internal identity; external authority URIs may be added as optional alias fields in a future ADR without changing the foundational definition.

**Alternative: Let the compiler create ContinuityNodes automatically**  
Rejected. Automated entity resolution produces false merges (same name, different entity) and false splits (different names, same entity). These errors in the ContinuityNode layer corrupt every Relationship and Interpretation that depends on correct entity identity. Steward ratification is required.

**Alternative: No ContinuityNode; attach everything directly to Observations**  
Rejected. This prevents cross-document and cross-temporal entity tracking. It reduces the system to a flat document store with no capacity to accumulate a model of any entity over time. It defeats the core purpose of the Hermeneutic Field.
