# CA-0003 — ArchitectPlan as the Canonical Semantic Contract

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-19  
**Ratified by:** Primary Human Steward

---

## Amendment

The canonical expression boundary is:

```text
NarrativeBlueprint
    ↓
ArchitectPlan
    ↓
ExpressionProfile
    ↓
Artist Provider
    ↓
RenderedNarrative
```

The NarrativeBlueprint determines what should be communicated.

The ArchitectPlan compiles the semantic obligations every valid communication
must satisfy.

The ExpressionProfile constrains how the communication may be expressed.

The Artist Provider realizes the contract. It does not create the contract,
alter its ancestry, or evaluate itself.

OpenAI, Anthropic, Gemini, Grok, and future providers shall operate through the
same ArtistProvider abstraction. Provider-specific behavior shall not alter the
pipeline or ontology.

---

## Supersession

ADR-0036 and ADR-0040 are partially superseded:

> NarrativeBlueprint is no longer the direct Artist contract. ArchitectPlan is
> the canonical interface between synthesis and expression.

Their unaffected principles remain active.

