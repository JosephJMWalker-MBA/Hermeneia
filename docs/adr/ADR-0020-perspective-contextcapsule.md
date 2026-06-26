# ADR-0020: Perspective and ContextCapsule Are Independent

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P1-002 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

`ContextCapsule` captures document-level or corpus-level context: historical period, political context, biographical background, institutional setting. `Perspective` (ADR-0015) is a declared methodological frame for interpretation.

Some Perspectives are historically situated and contain context-like information (a "1920s American reader" Perspective carries historical context). Some ContextCapsules contain things that look like Perspectives (a document's "ideological framing" field reads like a Perspective).

The question is whether Perspective should inherit from ContextCapsule, be scoped to it, or be independent.

---

## Decision

**Perspective and ContextCapsule are independent objects. Neither inherits from the other. A Perspective is not scoped to any single ContextCapsule.**

### Why They Are Orthogonal

A **ContextCapsule** answers: *"What is the historical, political, and biographical context surrounding this source document?"*

A **Perspective** answers: *"From what methodological or epistemic vantage point is this reading being made?"*

These are different questions with different authors, different scopes, and different lifetimes:

| Property | ContextCapsule | Perspective |
|---|---|---|
| Authored by | Human steward or AI-assisted | Human steward (ADR-0015) |
| Scope | Bound to one source document (or corpus) | Global — applicable to any set of Observations in any document |
| Lifetime | Attached to a document registration | Independent of any document |
| Content type | Descriptive facts about context | Methodological stance or epistemic frame |
| Example | "Published during the Jazz Age (1920s), after WWI, during Prohibition" | "Marxist reading" |

A Marxist Perspective is not scoped to *The Great Gatsby*. It can be applied to Observations from *The Great Gatsby*, from *Ulysses*, from a political manifesto, and from a legal case simultaneously. It is a cross-document, cross-corpus epistemic frame.

A ContextCapsule for *The Great Gatsby* (1925 Scribner edition) describes the conditions surrounding that specific document. It is not transferable to another document.

### Can One Perspective Be Applied to Multiple ContextCapsules?

Yes. This is a constitutionally correct reading.

A "post-colonial feminist" Perspective may be applied to Observations from:
- *The Great Gatsby* (ContextCapsule: 1920s American literary culture)
- *Heart of Darkness* (ContextCapsule: late-19th-century British colonial literature)
- A court case (ContextCapsule: US federal judicial system, 1960s)

The Perspective is the same object. The ContextCapsules are different. The Interpretations produced from each application are different (they reference different source Observations). But the Perspective's identity is document-independent.

---

## Relationship Between Perspective and ContextCapsule

They interact indirectly:

- An Interpretation references a Perspective (`perspective_id`) and source Observations (`source_observation_ids`).
- The source Observations are part of a source document.
- The source document is described by a ContextCapsule.
- Therefore: a given Interpretation can be understood as "Perspective X applied to Observations from a document with ContextCapsule Y."

This cross-reference is computable through the provenance chain without any direct Perspective-to-ContextCapsule link. No foreign key between Perspective and ContextCapsule is required or permitted.

---

## ContextCapsule Schema (Normative Fields)

A ContextCapsule is a structured description of a source document's surrounding context. It is not an Observation (it is not extracted verbatim from the document) and not an Interpretation (it is not a reading). It is steward-authored contextual metadata.

| Field | Type | Requirement |
|---|---|---|
| `id` | String (deterministic hash) | Required |
| `source_document_id` | String | Required. Foreign key to `source_documents` table (ADR-0013). |
| `historical_period` | String or null | Optional. Human-readable period description. |
| `political_context` | String or null | Optional. |
| `biographical_context` | String or null | Optional. Notes on the author's life circumstances. |
| `publication_context` | String or null | Optional. Original publication setting. |
| `genre` | String or null | Optional. |
| `language` | String | Required. Primary language of the source document. |
| `notes` | String or null | Optional. Free-text steward notes. |
| `authored_by` | String (steward ID) | Required. |
| `authored_date` | ISO 8601 datetime | Required. |

---

## Validation Rules

```python
# A Perspective must NOT carry a source_document_id field
assert not hasattr(perspective, 'source_document_id')

# A ContextCapsule must NOT carry a perspective_id field
assert not hasattr(context_capsule, 'perspective_id')

# One ContextCapsule per source document (one-to-one)
assert count(context_capsules WHERE source_document_id = X) <= 1
```

---

## Constitutional Alignment

- **Axiom 5** (Separation of concerns): ContextCapsule (document context) and Perspective (epistemic frame) are distinct concerns. Merging them would conflate "what is the world around this text" with "what lens am I reading it through."
- **ADR-0015** (Perspective definition): Perspective scope is global, not document-local. This ADR confirms that independence.

---

## Consequences

**Positive:**
- A Perspective defined once can be applied consistently across an unlimited corpus without duplication or scoping conflicts.
- ContextCapsule provides historical grounding for a source document without constraining the Perspectives that may be applied to it.
- The separation prevents a common modeling error: conflating "reading something from a historically-situated viewpoint" with "reading something knowing the historical context." Both are valid epistemic acts; they are different acts.

**Negative:**
- There is no direct link from a Perspective to the documents it has been applied to. Such a link must be computed via `interpretations WHERE perspective_id = X → source_observation_ids → source_documents`. This is a three-join query, but it is computationally straightforward.

---

## Alternatives Considered

**Alternative: Perspective as a subclass of ContextCapsule**  
Rejected. ContextCapsule describes an object's context; Perspective is a reading lens. A lens is not a context. Inheritance would conflate them structurally.

**Alternative: Perspective scoped to a single ContextCapsule**  
Rejected. This would require creating a new Perspective for every new document it is applied to, even if the Perspective is the same. "Marxist reading of Gatsby" and "Marxist reading of Ulysses" would be two separate Perspective objects with no shared identity. Perspective Debt would become unmeasurable across corpora.
