# ADR-0011: Claim Is Not a First-Class Ontology Object

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P0-002 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Existential

---

## Context

The research literature (OWL annotation properties, RDF reification, CIDOC CRM, SKOS) routinely treats "claims" as first-class objects: an entity with its own ID, subject, predicate, object, and provenance. This pattern is called propositional reification.

Hermeneia uses the term "Observation" for verbatim text extracted from source documents. But no canonical object currently accounts for the layer between observation and full interpretation — the propositional content of a reading. The question is whether "Claim" names a missing first-class object, or whether the existing Interpretation object already occupies that role.

This ADR is prerequisite for the Provenance schema (Q-P5-001, Q-P5-002), the storage schema, and the `field` package design.

---

## Decision

**Claim is not a first-class ontology object in Hermeneia.**

The role that the research literature assigns to "Claim" — a propositional statement derived from evidence and grounded in an epistemic stance — is performed in Hermeneia by the **Interpretation** object.

An Interpretation is a Claim. Every Interpretation is implicitly a claim: it asserts a propositional statement about one or more Observations, from within a declared Perspective, with traceability back to its source evidence.

Introducing a separate `Claim` class would duplicate the Interpretation layer without adding epistemic precision. It would require two separate provenance chains for what is constitutionally a single act: the act of deriving a meaning-bearing statement from textual evidence.

---

## The Epistemic Layers

The relationship between the relevant layers is as follows:

```
Source Document
    ↓ (deterministic extraction — ADR-0006)
Observation          ← "What is present in the source?"
    ↓ (interpretive act, grounded in Perspective)
Interpretation       ← "What does this mean, from this epistemic stance?"
    ↓ (synthetic act)
NarrativeBlueprint   ← "What story can be told from these interpretations?"
```

There is no constitutionally necessary layer between Observation and Interpretation. The leap from "what is present" to "what does this mean" is the constitutive interpretive act of humanistic scholarship. That act is the Interpretation.

The distinction the question was trying to capture — "this text says X" vs. "this reading says X" — is already enforced structurally:

- **"This text says X"** → Observation (the verbatim record, from the source document)
- **"This reading says X"** → Interpretation (the derived statement, from a Perspective)

No third object is needed to make this distinction computable. The distinction is computable from the object type alone: if it is an Observation, it is verbatim. If it is an Interpretation, it is derived.

---

## The Validation Test

The question proposed a test case: *"The green light in Gatsby symbolizes hope."* — Is this an Observation? An Interpretation? A Claim?

**Answer:**

- It is not an Observation. It is not a verbatim extraction from the text. The word "symbolizes" introduces interpretive content.
- It is not a separate Claim object. No such object exists.
- **It is an Interpretation.** Specifically, it is an Interpretation that:
  - References at least one Observation (the passage describing the green light across the bay)
  - Is grounded in a declared Perspective (e.g. "Symbolist literary reading")
  - Has human or AI provenance depending on who produced it
  - Is subject to steward acceptance before entering the canonical corpus (per ADR-0009/ADR-0010)

The ontology can answer this question unambiguously from the object type alone. No Claim object is required.

---

## What Interpretation Must Carry

This decision places increased responsibility on the Interpretation object. For Interpretation to serve the role of Claim, it must carry:

| Field | Purpose |
|---|---|
| `source_observations` | List[Observation IDs] — the textual evidence this Interpretation derives from |
| `perspective_id` | The declared Perspective from which this reading is made |
| `content` | The propositional statement being asserted |
| `confidence` | Optional. A steward-assigned or AI-assigned confidence level |
| `derivation_type` | How the Interpretation was produced: `direct_reading`, `synthesis`, `contrast`, `inference` |

The `source_observations` field is the mechanism that makes the provenance chain computable. Every Interpretation must reference the Observations it was derived from. An Interpretation with no `source_observations` is constitutionally suspect — it is making a claim with no traceable textual evidence.

The formal definition and full schema of Interpretation is the subject of Q-P0-003 (Milestone R2). This ADR establishes only that Interpretation serves the role of Claim, not the complete field schema.

---

## Consequence for Q-P1-001

Q-P1-001 asks "Should Claim exist as an independent canonical object?" This ADR answers that question: No. Q-P1-001 is closed by this ADR without requiring its own separate ADR. The EPISTEMIC_BACKLOG.md entry for Q-P1-001 should be updated to reflect resolution by ADR-0011.

---

## Inclusion Criteria

The following are valid Interpretations (in the role of claims):

1. A propositional statement about the meaning of one or more Observations, grounded in an explicitly declared Perspective.
2. A synthetic claim that integrates multiple Observations into a single reading.
3. A contrastive claim that identifies how two Observations are in tension within a declared Perspective.
4. An inferential claim that draws a conclusion not explicitly stated in any Observation, with source_observations identifying the evidence for the inference.

---

## Exclusion Criteria

The following are not Interpretations:

1. A verbatim transcription of source text (that is an Observation).
2. A paraphrase of a source sentence without added interpretive content (also an Observation, though an invalid one by ADR-0006 — paraphrase is excluded from Observation inclusion criteria).
3. A NarrativeBlueprint — that is a synthetic structure above the Interpretation layer.
4. A Perspective itself — a Perspective is a frame, not a propositional claim.

---

## Constitutional Alignment

- **Article I** (Reality precedes interpretation): The Observation/Interpretation boundary is the constitutional line between "what is present" and "what it means." This ADR does not blur that line — it clarifies that Interpretation is where derived meaning lives.
- **Article II** (Provenance mandatory): Interpretations carry `source_observations` pointing back to their Observation evidence. The provenance chain is unbroken.
- **Article V** (Observations remain distinct from conclusions): The distinction is enforced by object type, not by a separate Claim layer.

---

## Consequences

**Positive:**
- The ontology is simpler. One fewer class to define, schema, and validate.
- The Observation → Interpretation boundary is computationally crisp: everything in `interpretations` is derived; everything in `observations` is verbatim.
- The `source_observations` field on Interpretation provides the same traceability that a Claim object would have provided.

**Negative:**
- Interpretation must carry more structural weight. The `source_observations` field is now mandatory, not optional. An Interpretation without evidence is constitutionally suspect.
- The distinction between "a claim derived from one Observation" and "a claim synthesizing fifty Observations" is not encoded structurally — both are Interpretations. The `derivation_type` field partially addresses this but does not make it fully computable. This may need refinement in a future ADR.

---

## Alternatives Considered

**Alternative: Introduce Claim as a first-class object between Observation and Interpretation**  
Rejected. This requires: (a) a separate schema, (b) a separate provenance chain, (c) a definition of what distinguishes a Claim from an Interpretation — which the existing literature cannot agree on. The cost is high; the benefit is nil if Interpretation already captures what Claim would capture.

**Alternative: Use RDF reification pattern (Subject-Predicate-Object triples as named graphs)**  
Considered. Rejected. RDF reification is a storage pattern for knowledge graphs. Hermeneia is not a triple store. Importing a triple-store ontology pattern into a document-centric system would constitute the adoption of foreign ontology without constitutional compatibility analysis. The research literature describes what RDF systems do; it is not authoritative for Hermeneia's architecture.
