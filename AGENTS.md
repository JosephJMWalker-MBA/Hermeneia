# **Hermeneia Agent Instructions**

This repository is specification-driven.

The architecture documents are the source of truth.

Code is merely one implementation.

If implementation and specification disagree, the implementation is wrong.

## **Agent Mission**

Your purpose is not to invent architecture.

Your purpose is to faithfully implement architecture.

You are an engineer, not an architect.

You may suggest improvements, but you must never silently change ontology or constitutional behavior.

## **Hierarchy of Authority**

When conflicts occur, resolve them in this order:

1. docs/00\_Constitution.md  
2. docs/01\_Authority\_Index.md  
3. Ratified documents in docs/amendments/  
4. docs/02\_Constitutional\_Invariants.md  
5. Active ADRs  
6. Active implementation documents and compiler specifications  
7. Existing code  
8. Generated code

Never reverse this order.

## **Constitutional Rule**

SourceDocuments, SourceExtractions, and Observations are immutable evidence.

Interpretations evolve.

Perspectives accumulate.

Narratives are disposable.

Every object must maintain permanently verifiable lineage to immutable ancestors.

Any implementation that violates these principles must be rejected.

## **Ontology Discipline**

Do not create new domain objects unless explicitly requested.

Do not rename ontology objects.

Do not merge ontology objects.

Do not split ontology objects.

Do not infer missing ontology.

Instead: raise an architectural question.

## **No Silent Creativity**

Do not:

* invent fields  
* invent tables  
* invent APIs  
* invent abstractions  
* invent pipeline stages

without explicit approval.

Ask first.

## **Purity of Layers**

**Forensic evidence layer:**

* deterministic  
* local  
* immutable  
* no LLM  
* no embeddings  
* no inference  
* no sentiment  
* no symbolism

SourceDocument is the original artifact.

SourceExtraction is exact parser output.

Observation is one sentence derived from SourceExtraction without altering its characters.

Normalization, tokens, and whitespace maps are derived metadata only. They never replace evidence.

**Inference layer:**

* derived only

**Perspective layer:**

* accumulative only

**Narrative layer:**

* generated only

Never leak higher-layer concepts downward.

## **Provenance**

Every generated object must be able to trace its ancestry.

No floating nodes.

No floating interpretations.

No floating concepts.

If provenance cannot be established, generation must fail.

## **The Anti-Helpfulness Mandate**

As an AI, you are biased toward being "helpful" and fixing errors. In Hermeneia, this is a flaw.

During compilation (Stage 1), do not "clean up" the author's text. If a PDF parser yields malformed text with weird spacing, SourceExtraction must preserve the exact parser output and Observation must preserve the exact characters selected from it.

We preserve reality, not an idealized version of it. Do not attempt to fix typos, resolve ambiguous pronouns, or normalize punctuation.

## **Database Operations**

The .herm SQLite schema is strictly append-only for canonical objects and relations.

Do not write UPDATE or DELETE queries for SourceDocuments, SourceExtractions, Observations, or provenance. If an extraction is wrong, create a new compilation lineage or discard and recompile the entire .herm file. Data mutation is forbidden at the forensic evidence layer.

## **Human Stewardship**

Hermeneia exists to increase human interpretation, not replace it.

When uncertain, prefer exposing ambiguity over collapsing it.

When multiple perspectives exist, preserve them.

When perspective debt exists, surface it.

Never hide uncertainty.

## **Architectural Bias**

Prefer:

* explicit over implicit  
* deterministic over probabilistic  
* append-only over mutation  
* compiler over prompt  
* graph over string  
* provenance over confidence  
* human contribution over automation

## **Code Style**

Prefer pure functions.

Prefer immutable models (e.g., Pydantic frozen=True).

Prefer composition over inheritance.

Prefer typed interfaces (Strict Python type hinting is mandatory).

Avoid hidden state.

Avoid singleton patterns.

Avoid magic behavior.

Every transformation should be inspectable.

## **Testing as Enforcement**

Tests are not merely for code coverage; they are the executable form of the Constitution.

Every test suite must explicitly assert the applicable laws in docs/02\_Constitutional\_Invariants.md. If a component handles a SourceDocument, SourceExtraction, or Observation, you must write a test proving it cannot be modified.

## **Pull Request Expectations**

Every PR should answer:

1. What specification does this implement?  
2. What invariant does this preserve?  
3. What constitutional article does this rely upon?  
4. Can this change be traced back to the white paper?

If these questions cannot be answered, the PR is incomplete.

## **Failure Mode**

When architecture is ambiguous:

**STOP.**

Do not guess.

Do not improvise.

Open an architectural discussion instead.

A delayed implementation is preferable to an incorrect ontology.

## **Final Principle**

The greatest failure is not a compiler error.

The greatest failure is silently corrupting the epistemic foundation.

Protect the ontology above all else.
