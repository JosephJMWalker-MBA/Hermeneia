# ADR-0014: The Sentence Is the Smallest Epistemic Object

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P1-005 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

ADR-0006 established that an Observation is a single sentence. ADR-0012 established that the atomic provenance unit is also the sentence. This ADR addresses the remaining question: is the sentence also the smallest *epistemic* object — the unit at which meaning is independently evaluable — or is it merely a convenient extraction boundary?

This matters because:

1. If meaning requires more than one sentence to be evaluable, then a lone Observation may be meaningless without its neighbors. This has implications for how the field layer interprets Observations and how the compiler should expose adjacency information.

2. If meaning can be extracted from sub-sentential units, then the compiler should split further — but ADR-0006 already rejected this, requiring justification.

3. The field layer (Concept extraction, Relationship identification) must know what unit it is operating on.

---

## Decision

**The sentence is the smallest epistemic object in Hermeneia.**

A sub-sentential unit (a token, clause, or phrase) is not an independently evaluable epistemic unit. It may participate in meaning, but it does not carry meaning on its own. It cannot be the subject of an Interpretation. It cannot anchor a ContinuityNode reference. It cannot ground a Claim (ADR-0011).

A sentence — a complete proposition, as defined in ADR-0006 — is the minimum unit that:
- Can be evaluated as true or false (or meaningless, or ambiguous) in isolation.
- Can be the subject of an Interpretation without requiring the addition of non-present text.
- Can ground a provenance record pointing to a verifiable source location.

---

## The Meaning-Context Problem

The question asked whether meaning requires adjacent context: *"Does a sentence require its neighboring sentences to be meaningful?"*

The answer is: **yes, for full contextual interpretation; no, for epistemic evaluation.**

A sentence like "He was careless" from *The Great Gatsby* is grammatically complete and semantically evaluable in isolation. An Interpretation can be made of it. A Perspective can be applied to it. Its epistemic content — a character is being described as careless — is accessible without the surrounding paragraph.

However, to fully interpret *whose* carelessness is being named, the reader benefits from context. This is a reading concern, not a storage concern. The field layer addresses it through **adjacency references**, not by changing the observation unit.

---

## The Adjacency Mechanism

An Observation's meaning is occasionally underdetermined without its neighbors. This is addressed by allowing Observations to carry read-only adjacency references — not additional content:

| Field | Type | Purpose |
|---|---|---|
| `preceding_observation_id` | String or null | The Observation immediately before this one in the source (same paragraph) |
| `following_observation_id` | String or null | The Observation immediately after this one in the source (same paragraph) |

These are **navigation fields, not content fields**. They are IDs pointing to sibling Observations, not text. They do not modify the Observation's `text` field. They do not violate immutability — the `text` remains the verbatim extraction; the adjacency fields merely allow the reader to walk to neighboring Observations.

Adjacency references cross paragraph boundaries only at the steward's explicit request (a future configuration option). By default, adjacency is within-paragraph only: the first sentence in a new paragraph has `preceding_observation_id: null`.

---

## Sub-Sentential Units Are Not Epistemic Objects

The question raised whether a clause or phrase (sub-sentential unit) might carry independent meaning. The answer is: **in linguistic analysis, yes; in Hermeneia's ontology, no.**

Hermeneia is not a linguistic annotation tool. It is an epistemic operating system for humanistic scholarship. The relevant epistemic unit for humanistic scholarship is the proposition — the minimal unit that can be interpreted, debated, contested, and attributed to a perspective. The proposition maps to the sentence.

A clause ("the green light") is not independently interpretable as an epistemic object. It is a referring expression. Referring expressions participate in propositions but do not constitute them. They are not stored as first-class objects in Hermeneia.

A phrase ("careless people") is a noun phrase. It refers to a type. The fact that it refers to a type may be extracted as a Concept (the concept "careless people" as a sociological type). But the Concept is derived from the Observation containing the phrase, not from the phrase itself. The phrase is not the unit of extraction — the sentence is.

---

## The Complex Sentence Test

Q-P1-005 proposed: *"Take a complex sentence from Gatsby that contains two distinct propositions. Can one Observation adequately represent both? Should it be split?"*

**Test case:**  
*"They were careless people, Tom and Daisy — they smashed up things and creatures and then retreated back into their money or their vast carelessness, and let other people clean up the mess they had made."*

This is a compound-complex sentence with three grammatically embedded propositions:
1. Tom and Daisy are careless people.
2. They smashed up things and creatures.
3. They retreated into their money and carelessness and let others clean up.

**Answer:** One Observation, three Interpretations.

The sentence is grammatically one unit. The Observation records it as one verbatim string. Its complexity does not require splitting — it requires richer Interpretations. Three separate Interpretations may be derived from this single Observation, each focusing on a different embedded proposition. Each Interpretation references the same `source_observations` list containing this single Observation's ID.

This is the correct layering. The Observation layer captures the sentence. The Interpretation layer unpacks its semantic complexity. The sentence boundary is not determined by propositional count; it is determined by the source document's typographic sentence terminator, as defined in ADR-0006.

**When should a sentence be split?**  
Never by the compiler. Splitting is a form of normalization, which ADR-0006 forbids. If a typographic sentence contains multiple propositions, the compiler records it as one Observation. The field layer extracts multiple Interpretations from it.

---

## Implications for the Compiler

The compiler's sentence-splitter must:

1. Split on sentence terminators as defined in ADR-0006, not on clause boundaries.
2. Populate `preceding_observation_id` and `following_observation_id` for each Observation within a paragraph.
3. Set `preceding_observation_id: null` for the first sentence in a paragraph.
4. Set `following_observation_id: null` for the last sentence in a paragraph.
5. Cross-paragraph adjacency: null by default.

---

## Implications for the Field Layer

The `field` package may use `preceding_observation_id` and `following_observation_id` to:

- Retrieve context when generating Interpretations (providing adjacent Observations as reading context to the Architect agent).
- Build concept co-occurrence graphs (concepts appearing in adjacent Observations are more likely to be semantically related).
- Identify dialogue structure in sources that are themselves dialogues (speaker turns as sequences of adjacent Observations).

The field layer must not treat adjacency as semantic content. Adjacency is a navigation aid. It does not modify the epistemic content of the Observation.

---

## Formal Statement

**The smallest epistemic object in Hermeneia is the Observation, which corresponds to one sentence.**

Corollaries:
- Sub-sentential units are not epistemic objects. They are linguistic subunits that participate in Observations.
- Observations may carry read-only adjacency references for navigation.
- Complex sentences containing multiple propositions produce one Observation and multiple Interpretations.
- The compiler never splits a typographic sentence into multiple Observations.

---

## Serialization Rules

The `preceding_observation_id` and `following_observation_id` fields on the Observation record:

- Are populated at extraction time, in the same compiler pass that creates the Observation.
- Are `null` for the first and last sentences in a paragraph respectively.
- Point to valid Observation IDs in the same compilation run (same `source_document_hash`).
- Are immutable after creation (consistent with the append-only constraint on Observations).
- Are not included in the Observation's own ID hash. They are relational fields, not identity fields.

---

## Validation Rules

```python
# Adjacency references must point to valid Observation IDs if non-null
if observation.preceding_observation_id is not None:
    assert observation_exists(observation.preceding_observation_id)
if observation.following_observation_id is not None:
    assert observation_exists(observation.following_observation_id)

# Adjacency references must be bidirectional within a paragraph
if observation.following_observation_id is not None:
    next_obs = get_observation(observation.following_observation_id)
    assert next_obs.preceding_observation_id == observation.id

# The first sentence in a paragraph has no preceding reference
if observation.sentence == 1:
    assert observation.preceding_observation_id is None
```

---

## Migration Policy

1. Observations compiled without adjacency references (pre-ADR-0014) remain valid. Their `preceding_observation_id` and `following_observation_id` fields will be null.
2. Adjacency references may be added to existing compilations by a recompilation pass that walks the sentence sequence and populates the null fields. This is an UPDATE on existing Observation records — which is constitutionally prohibited.
3. **Therefore:** adjacency references must be computed and stored at first-compilation time. There is no migration path for adding them to existing Observations. Compilations done after this ADR is ratified include adjacency references; compilations done before do not. Both remain valid.
4. The field layer must handle null adjacency references gracefully (no context walking available for pre-ADR-0014 Observations).

---

## Constitutional Alignment

- **Article I** (Reality precedes interpretation): The sentence is the unit at which the "reality" of the source document is captured. Sub-sentential splitting would involve the compiler making interpretation decisions about clause boundaries — a constitutional violation.
- **Article V** (Observations remain distinct from conclusions): Adjacency references are navigation fields, not interpretive additions. The Observation's `text` field remains verbatim.
- **Invariant 4** (Architectural Decoupling): The adjacency reference fields are populated by the deterministic compiler, not by any LLM. The field layer reads them but does not compute them.

---

## Consequences

**Positive:**
- The sentence boundary is the same across all layers: Observation, Provenance, smallest epistemic unit. There is no cross-layer ambiguity.
- The adjacency mechanism allows context-sensitive reading without changing the unit of storage.
- The decision that complex sentences produce one Observation and multiple Interpretations is architecturally clean: complexity lives in the Interpretation layer, not the Observation layer.

**Negative:**
- Adjacency references cannot be added to existing Observations after initial compilation (immutability constraint). This is an upfront cost: the compiler must populate them in the first run, or they are permanently missing for that corpus.
- A complex sentence with three embedded propositions produces one Observation with potentially three Interpretations, all referencing the same source Observation. This creates a one-to-many relationship between Observations and Interpretations that the field layer must handle. The field query `"which Observations support this Interpretation?"` returns one item; the query `"which Interpretations derive from this Observation?"` may return many.

---

## Alternatives Considered

**Alternative: Clause as the smallest epistemic object**  
Rejected. Clause splitting requires a dependency parser (spaCy, Stanford CoreNLP). These are statistical, not deterministic — violating Invariant 2. Different parser versions produce different clause boundaries. Two compilers on the same sentence produce different Observation IDs. The `.herm` portability guarantee breaks.

**Alternative: Paragraph as the smallest epistemic object**  
Rejected by ADR-0006. Repeating the reasoning here: a paragraph may contain multiple independent propositions. A paragraph-level Observation cannot be uniquely associated with a single Interpretation derived from one of its sentences. The provenance chain loses granularity.

**Alternative: Token as the smallest epistemic object**  
Rejected. Tokens are not independently evaluable. The token "careless" does not constitute an independently evaluable epistemic claim. The Observation database would grow by two to three orders of magnitude. No meaningful Interpretation can be produced from a single token.
