# Architecture Proofs

**Status:** DERIVATION REVIEW
**Implementation status:** DOCUMENTATION ONLY
**Constitutional authority:** [`00_Constitution.md`](00_Constitution.md), [`01_Authority_Index.md`](01_Authority_Index.md), [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)
**Pattern reference:** [`Architecture_Patterns.md`](Architecture_Patterns.md)

---

## Purpose

This document demonstrates whether major Hermeneia constructs derive from the
Constitution, invariants, and existing architecture patterns.

It does not create code, schema, tests, UI, ADRs, constitutional amendments, or
ontology.

The review question is:

```text
Can each construct be derived from existing principles,
or did it require independent invention?
```

Where a construct is provisional, this document says so.

---

## Proof Method

For each construct, this document asks:

1. What constitutional article authorizes it?
2. What invariant constrains it?
3. What architecture pattern generates it?
4. Could it have been derived instead of invented?
5. Does it introduce new ontology?
6. Does it violate the Regeneration Principle?
7. Could it disappear tomorrow without harming canonical knowledge?

The relevant architecture patterns are:

- Regeneration Principle;
- Pure Projection;
- Disposable Derived;
- Contract-Constrained Expression; and
- Inspection Surface.

---

## Workspace Projection

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article I, Article VI, Article XI, Article XII |
| Invariant | CI-006, CI-012, CI-015, CI-016 |
| Pattern | Pure Projection + Inspection Surface |
| Derived or invented | Derived |
| New ontology | No |
| Regeneration Principle | Satisfies it |
| Can disappear without harming canonical knowledge | Yes |

Workspace Projection begins with a canonical class and ID, gathers related
canonical references, and exposes available inspection surfaces. It has no
workspace identity, no lineage of its own, no provenance of its own, and no
authority.

It is derivable from:

```text
Canonical object
    ↓
read-only arrangement of related canonical references
    ↓
human inspection
```

Therefore Workspace Projection is not ontology. It is attention management over
ontology.

---

## Trust Card

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article I, Article II, Article VI, Article XI, Article XII |
| Invariant | CI-006, CI-009, CI-011, CI-012, CI-015 |
| Pattern | Pure Projection + Inspection Surface |
| Derived or invented | Derived |
| New ontology | No |
| Regeneration Principle | Satisfies it |
| Can disappear without harming canonical knowledge | Yes |

Trust Card is a compact projection over persisted lineage, execution,
contract, and evaluation facts.

It does not compute trust from provider identity. It does not create a
confidence score. It does not become the thing trusted. It shows the canonical
facts that allow a human to inspect why trust may or may not be warranted.

The Trust Card derives from:

```text
canonical lineage + execution audit + contract facts + evaluation facts
    ↓
read-only projection
    ↓
human inspection
```

Deleting the Trust Card deletes no canonical knowledge.

---

## ObservationDerived

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article III, Article IV, Article V |
| Invariant | CI-002, CI-003, CI-004, CI-015, CI-016 |
| Pattern | Disposable Derived |
| Derived or invented | Derived |
| New ontology | Already active as derived metadata, not evidence |
| Regeneration Principle | Satisfies it |
| Can disappear without harming canonical knowledge | Yes |

ObservationDerived exists because evidence must remain exact while computation
still needs normalized text, tokens, whitespace maps, and indexes.

It derives from the constitutional evidence boundary:

```text
Observation.raw_text
    ↓
derived computational convenience
```

It never replaces `SourceExtraction.raw_text` or `Observation.raw_text`. Its
deletion leaves canonical evidence intact.

---

## Audit Vector

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article I, Article VI, Article XI, Article XII |
| Invariant | CI-006, CI-012, CI-015, CI-016, INV-XI |
| Pattern | Regeneration Principle + Pure Projection + Inspection Surface |
| Derived or invented | Derived |
| New ontology | No |
| Regeneration Principle | Satisfies it |
| Can disappear without harming canonical knowledge | Yes |

Audit Vector is a regenerated arrangement of Findings across orthogonal audit
dimensions.

It possesses:

- no identity;
- no authority;
- no provenance of its own;
- no supersession of its own;
- no constitutional profile of its own; and
- no independent lifecycle.

It derives from:

```text
Finding[]
    ↓
grouped projection by dimension/status
    ↓
inspection surface
```

Persisting Audit Vector as ontology would violate the Regeneration Principle.

---

## Finding

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article I, Article II, Article VI, Article VII, Article IX, Article X, Article XI |
| Invariant | CI-005, CI-006, CI-009, CI-010, CI-011, CI-014, CI-015, INV-XI |
| Pattern | Contract-Constrained Expression + Orthogonal Audit as documented in `Critic_Ecology.md` |
| Derived or invented | Derived as a candidate; not yet ratified |
| New ontology | Not by this document; future ratification required |
| Regeneration Principle | Does not violate it because Finding is proposed as irreducible |
| Can disappear without harming canonical knowledge | No, if ratified; yes today because it is not implemented |

Finding is provisionally defined in [`specs/finding.spec.md`](specs/finding.spec.md)
as the smallest independently ratifiable machine-generated epistemic object.

It derives from the need to preserve individual evaluation deltas rather than
aggregate reports:

```text
ArchitectPlan
    +
RenderedNarrative
    +
canonical lineage
    +
one evaluation dimension
    ↓
Finding
```

Finding is not a projection because an aggregate view cannot reconstruct the
irreducible audit claim unless the Finding already exists. Finding is therefore
the candidate durable object; Audit Vector, Trust Card, dashboards, and scores
are projections over it.

Current authority still names `CriticReport`. Finding remains a candidate for
future constitutional work until ratified.

---

## Evaluation Function

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article II, Article VI, Article IX, Article X, Article XII, Article XIV |
| Invariant | CI-006, CI-009, CI-010, CI-011, CI-012, INV-XI, INV-XIV |
| Pattern | Contract-Constrained Expression + computational method under Finding |
| Derived or invented | Derived |
| New ontology | No |
| Regeneration Principle | Satisfies it because the function is not canonical |
| Can disappear without harming canonical knowledge | Yes, if Findings and provenance remain |

Evaluation Function is defined in
[`specs/evaluation_function.spec.md`](specs/evaluation_function.spec.md) as a
constitutionally constrained computation:

```text
canonical inputs
    ↓
one orthogonal dimension
    ↓
Finding[]
```

The function is computational infrastructure. It is not preserved as ontology.
Its identity, version, and configuration belong in Finding provenance or audit
metadata.

The preserved object is the Finding, not the function.

---

## Provider Registry

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article II, Article IX, Article X |
| Invariant | CI-009, CI-011, INV-XIV |
| Pattern | Contract-Constrained Expression infrastructure |
| Derived or invented | Derived |
| New ontology | No |
| Regeneration Principle | Satisfies it; registry state is configuration, not epistemic content |
| Can disappear without harming canonical knowledge | Yes, if persisted RenderedNarratives retain execution audit records |

Provider Registry is configuration infrastructure for interchangeable
ArtistProviders. It exists because the Artist provider is replaceable while the
contract and ancestry are not.

It derives from:

```text
ArchitectPlan + ExpressionProfile
    ↓
replaceable ArtistProvider
    ↓
RenderedNarrative with execution audit
```

Provider Registry is not evidence, not interpretation, not evaluation, and not
governance. It supplies adapters. It does not determine semantic standing.

---

## Provider Ecology

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article II, Article IX, Article XII |
| Invariant | CI-011, CI-012, INV-XIII, INV-XIV |
| Pattern | Pure Projection + Inspection Surface over Provider Registry |
| Derived or invented | Derived |
| New ontology | No |
| Regeneration Principle | Satisfies it |
| Can disappear without harming canonical knowledge | Yes |

Provider Ecology is a read-only projection of provider registration and
configuration state.

It is not a ranking system. It is not provider authority. It does not produce
semantic standing. It helps inspect which adapters are available or configured.

A Provider may represent a cloud service, an on-device runtime, a local model, a specialized execution environment, or any future expression mechanism capable of realizing an ArchitectPlan. Provider identity is ecological rather than constitutional.

It derives from:

```text
Provider Registry configuration
    ↓
read-only provider ecology projection
```

Deleting Provider Ecology removes an inspection convenience, not canonical
knowledge.

---

## Lineage Explorer

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article I, Article VI, Article XI, Article XII |
| Invariant | CI-006, CI-012, CI-015 |
| Pattern | Inspection Surface + Pure Projection |
| Derived or invented | Derived |
| New ontology | No |
| Regeneration Principle | Satisfies it |
| Can disappear without harming canonical knowledge | Yes |

Lineage Explorer makes existing ancestry visible.

It does not create lineage. It does not repair missing lineage. It does not
translate interface vocabulary into ontology. It renders the canonical graph
for inspection.

It derives from:

```text
canonical object ID
    ↓
canonical ancestry graph
    ↓
human inspection surface
```

The explorer can disappear without affecting the lineage it displays.

---

## Semantic Contract Inspector

### Derivation

| Question | Answer |
|---|---|
| Constitutional article | Article IX, Article XI, Article XII, Article XIV |
| Invariant | CI-009, CI-010, CI-012, CI-015, INV-XI |
| Pattern | Inspection Surface over Contract-Constrained Expression |
| Derived or invented | Derived |
| New ontology | No |
| Regeneration Principle | Satisfies it |
| Can disappear without harming canonical knowledge | Yes |

Semantic Contract Inspector exposes the relationship between:

```text
ArchitectPlan obligations
    ↓
RenderedNarrative
    ↓
Critic facts / future Findings
```

It does not evaluate by itself. It does not rewrite the narrative. It does not
invent contract obligations. It surfaces what has been measured, what is
missing, and what remains not evaluated.

It is an inspection surface, not ontology.

---

## Terminal Machine-Generated Epistemic Object

If Finding is ratified, it is the terminal machine-generated epistemic object.

The proof is:

1. `RenderedNarrative` is the final generated expression in the
   Contract-Constrained Expression chain.
2. Evaluation must not rewrite that expression.
3. Evaluation must produce information only.
4. Aggregate reports, dashboards, vectors, trust cards, and scores are
   regenerable from smaller evaluation facts.
5. The smallest independently witnessable evaluation fact is Finding.
6. Therefore the final durable machine-generated epistemic object is Finding.

The boundary is:

```text
Machine evaluation
    ↓
Finding
    ↓
Human stewardship, witness, and ratification
```

Everything after Finding is governance or witness work, not machine
epistemology, unless future authority ratifies otherwise.

This proof remains provisional because Finding is not yet ratified and current
authority still names `CriticReport`.

---

## Classification Summary

| Construct | Classification |
|---|---|
| proposed_interpretations | Staging object — pre-canonical, pre-human-authorization, not an interpretation |
| interpretations | Canonical object — human-authorized, immutable, provenance-complete |
| Finding | Candidate canonical Evaluation object; not yet ratified |
| Evaluation Function | Computational infrastructure |
| Workspace Projection | Pure Projection |
| Trust Card | Pure Projection + Inspection Surface |
| Audit Vector | Pure Projection + Inspection Surface over Findings |
| ObservationDerived | Disposable Derived |
| Provider Registry | Configuration infrastructure |
| Provider Ecology | Infrastructure projection |
| Lineage Explorer | Inspection Surface |
| Semantic Contract Inspector | Inspection Surface |

---

## Underived Concepts

The examined constructs derive cleanly from current constitutional principles
and existing architecture patterns.

The remaining underived or unresolved concepts are not the constructs
themselves, but their future constitutional status:

- whether Finding supersedes, refines, or coexists with `CriticReport`;
- whether `CriticReport` becomes projection, legacy aggregate, or remains
  canonical Evaluation object;
- whether StewardDecision, WitnessRecord, and RatificationRecord become
  canonical governance objects;
- whether Finding supersession receives a ratified relation model;
- which Evaluation Function dimensions are authorized; and
- which operation vocabularies are exhaustive per dimension.

These are candidates for future constitutional work. They must not be resolved
by implementation.

---

## Staging Constitutional Principle

**Statement:**

> A proposed interpretation is not an interpretation with lower confidence.
> It is a different constitutional state.

**Derivation:**

ADR-0009 defines the staging protocol: AI-generated objects write to a staging
table (`proposed_interpretations`), a human steward accepts or rejects, and
only accepted objects move to canonical tables. Rejected objects are never
deleted.

This structure defines three distinct constitutional states:

```text
proposed_interpretations   (AI-generated, awaiting steward decision)
    ↓ steward acceptance
interpretations            (canonical, human-authorized, immutable)
```

A rejected proposal never becomes an interpretation. An accepted proposal
becomes a new constitutional object — it does not become the same object with a
changed status field.

**The collapse error:**

The temptation is to model this as a single object:

```text
interpretations
    status = proposed | accepted | rejected
```

This collapses three distinct constitutional states into one table with a
mutable flag. The collapse is a constitutional error because:

1. A proposed interpretation has no human provenance. A canonical interpretation
   must have an `accepting_steward`. These are different objects, not one
   object at different lifecycle stages.
2. Rejected proposals must be permanently preserved as a record of what was
   generated and why it was not accepted (ADR-0009). If proposal and
   interpretation share a table, rejected rows pollute the canonical corpus.
3. The AI provenance record spans two events — generation and acceptance.
   These events belong to different objects in different tables. Collapsing
   them into one table collapses the provenance model.

**Corollary — The Two-Table Invariant:**

E8 must always maintain two separate tables: `proposed_interpretations` and
`interpretations`. No status field on a shared table is constitutionally
equivalent to this separation.

---

## Projection Sufficiency Theorem

**Statement:**

> Any interface artifact derivable solely from canonical Findings SHALL be
> implemented as a disposable projection rather than a persisted object.

**Proof (constructive):**

Sprint E4 demonstrated that Audit Dashboard, Trust Card, and Semantic Inspector
are each derivable from `Finding[]` alone via pure read-only functions. No
information was lost by discarding any projection. No canonical knowledge
required the projection to persist in order to survive.

The proof is constructive: the projections exist, they run, and their deletion
would destroy no epistemic content.

**Corollary — The Irreducibility Test:**

A proposed object passes the Irreducibility Test if and only if it cannot be
regenerated from existing canonical objects by any deterministic function.

Objects that fail this test are projections. Objects that pass it are candidates
for canonical status — subject to constitutional review, ADR, and ratification.

**Corollary — The Governance Primitive:**

Human Steward Decisions fail the Irreducibility Test in the correct direction:
they cannot be regenerated because they record a historical act of human
responsibility, not a computation. A StewardDecision is therefore a canonical
governance primitive, not a projection.

The chain of custody is:

```text
Canonical Object
    ↓
Finding   (terminal machine-generated epistemic object)
    ↓
StewardDecision   (first irreducible human governance act)
    ↓
Ratification   (immutable record of human authority)
```

**Directionality constraint:**

StewardDecision shall point to Finding. Finding shall not point to
StewardDecision. The Finding is immutable; it is not annotated by governance.
Governance annotates itself, by carrying a reference to the Finding it
governs. This preserves the Finding as a pure machine-generated epistemic
object and prevents the governance layer from contaminating the evaluation
layer.

Violating this constraint would make the Evaluation Layer downstream of the
Stewardship Layer, which would violate CI-016 and INV-XI.

This proof does not ratify StewardDecision. It derives the directionality
constraint from the Projection Sufficiency Theorem and the constitutional
authority boundary. Future ratification requires an ADR.

---

## Architectural Closure

No examined architectural construct required independent ontological
introduction.

Each was derivable from the Constitution, Constitutional Invariants, and
Architecture Patterns.

The system therefore exhibits architectural closure under its current
principles for the reviewed constructs.

Hermeneia's complexity grows by derivation rather than accumulation when new
constructs are forced through this proof discipline.

---

## Constitutional Review

This document creates no implementation authority.

It does not change ontology.

It does not amend the Constitution.

It does not ratify Finding, Evaluation Function, StewardDecision,
WitnessRecord, or RatificationRecord.

Future implementation still requires the relevant ADR or amendment wherever a
construct would become canonical, persisted, or constitutionally authoritative.
