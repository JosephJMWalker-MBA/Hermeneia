# Critic Ecology

**Status:** CONSTITUTIONAL REVIEW DOCUMENT
**Scope:** Findings substrate only
**Implementation status:** NOT IMPLEMENTED
**Constitutional authority:** [`00_Constitution.md`](00_Constitution.md), [`01_Authority_Index.md`](01_Authority_Index.md), [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)
**Related implementation guide:** [`Architecture_Patterns.md`](Architecture_Patterns.md)

---

## Purpose

Critic Ecology names the future evaluation ecology around
`RenderedNarrative`, `ArchitectPlan`, `ExpressionProfile`, lineage, provenance,
accessibility, and human stewardship.

This document does not implement Critic Ecology.

It defines the substrate question that must be settled before implementation:

```text
What is the durable object of audit?
```

The constitutional answer is:

```text
Individual Finding = durable audit unit
Audit Vector = disposable projection over Findings
```

This document does not create schema, provider behavior, UI behavior, tests, or
new persistence. It records the constitutional review needed before a future
ADR, storage specification, and implementation can proceed.

---

## Constitutional Review

### Governing Constitutional Articles

The governing articles are:

- **Article I - Immutable Ancestry:** every Hermeneia object must preserve
  permanently verifiable lineage to immutable ancestors.
- **Article II - Auditability Over Determinism:** deterministic results must be
  reproducible; nondeterministic results must preserve complete audit records.
- **Article VI - Provenance and Chain of Custody:** every generated object must
  identify its direct parent or parents; generation fails when provenance cannot
  be established.
- **Article VII - Epistemic Classes:** `CriticReport` is the ratified
  Evaluation class; an object may not acquire authority to rewrite ancestors.
- **Article VIII - Canonical Pipeline:** Critic follows `RenderedNarrative` and
  precedes Stewardship. Stages may not be added, removed, merged, renamed, or
  reordered without amendment.
- **Article IX - Synthesis, Contract, and Expression:** the Critic evaluates a
  `RenderedNarrative` against its referenced `ArchitectPlan`; the Artist does
  not create the contract it is evaluated against.
- **Article X - Monotonic Knowledge:** each Critic invocation creates a new
  `CriticReport`; prior reports remain inspectable.
- **Article XI - Human Stewardship:** ambiguity is exposed rather than
  collapsed; human stewardship retains final authority over ratification,
  supersession, and release.
- **Article XII - Read-Only Integrity:** audit queries and inspection views must
  not mutate storage.
- **Article XIII - Singular Storage Authority:** future persistence must conform
  to the active `.herm` storage specification.
- **Article XIV - Executable Constitutional Law:** any future implementation
  must be enforced by executable invariant tests.

### Governing Invariants

The governing invariants are:

- **CI-005 - Immutable Persistence:** immutable objects and append-only
  downstream objects may not be rewritten in place.
- **CI-006 - Strict Ancestry:** generated objects must have all required
  parents and complete lineage.
- **CI-007 - Downward Non-Interference:** evaluation cannot modify evidence.
- **CI-009 - Contract Dominance:** a Critic evaluates the
  `RenderedNarrative` against the referenced `ArchitectPlan` and does not
  evaluate a contract created by the evaluated Artist.
- **CI-010 - Deterministic Reproduction:** deterministic audit logic must
  reproduce identical results from identical ancestors, implementation version,
  and configuration.
- **CI-011 - Nondeterministic Audit Record:** nondeterministic audit invocations
  must preserve input, parents, provider and model identity where applicable,
  request payload, execution metadata, raw output, canonical result identity,
  and provenance.
- **CI-012 - Side-Effect-Free Reads:** read paths cannot create audit objects,
  seed profiles, update timestamps, or otherwise mutate state.
- **CI-013 - Singular Portable Format:** no competing authoritative audit bundle
  format may exist.
- **CI-014 - Monotonic Supersession:** authority changes preserve historical
  artifacts and append authority relations.
- **CI-015 - Anti-Helpfulness Compliance:** downstream audit cannot obscure
  ancestors, rewrite evidence, or hide missing provenance.
- **CI-016 - Derived Artifact Disposability:** derived projections and
  computational conveniences may be regenerated and cannot replace canonical
  history.
- **INV-XI - Critic Authority Boundary:** Critic output is information only; it
  does not modify the artifact it evaluates.
- **INV-XIII - Steward Context Shall Not Determine Semantic Standing:** steward
  credentials, reputation, identity, or social status cannot determine semantic
  standing.
- **INV-XIV - Artist Provider Interchangeability:** provider identity belongs in
  audit records but does not determine semantic fidelity.

### Governing Architecture Patterns

The applicable patterns from [`Architecture_Patterns.md`](Architecture_Patterns.md)
are:

- **Pure Projection:** an Audit Vector is a temporary arrangement of existing
  Findings for attention and inspection.
- **Disposable Derived:** aggregate summaries, domain counts, badges, or
  vector-like groupings are regenerable from canonical Findings.
- **Contract-Constrained Expression:** Findings in the semantic domain evaluate
  a `RenderedNarrative` against a precompiled `ArchitectPlan` under an
  `ExpressionProfile`.
- **Inspection Surface:** Workspace Projection, Trust Card, semantic-contract
  inspection, and future Critic Ecology views expose authoritative audit facts
  without constructing ontology in the interface.

### Classification

Findings are not currently ratified as an independent top-level ontology class.
The ratified ontology class is `CriticReport`, whose epistemic class is
Evaluation.

For future implementation, the constitutionally correct durable audit substrate
is an **Individual Finding**, not a monolithic Audit Vector.

Until ratified by the appropriate authority, a Finding is a proposed canonical
evaluation unit within the Critic layer. It must not be persisted, migrated,
or treated as a schema object by implementation alone.

An Audit Vector is a **projection** over Findings. It is not canonical
ontology. It is not durable history. It is an inspection arrangement.

No constitutional ambiguity blocks this documentation sprint because the
document does not implement a new ontology object. A future implementation that
persists Findings must still receive schema and ontology authority before code
is written.

---

## Relationship To Steward

The Steward does not become a Critic provider and does not delegate final
judgment to an Audit Vector.

Findings surface bounded evaluation facts. They may be blocking, advisory, or
informational according to future ratified rules, but they do not ratify,
supersede, release, or suppress artifacts by themselves.

The Steward reads Findings, evaluates unresolved ambiguity, and performs any
human-only governance act. This preserves Article XI: the system reports;
human stewardship decides where constitutional authority requires judgment.

Steward credentials may be recorded as provenance where future authority
permits, but they must not alter a Finding's semantic standing or ordering.

---

## Relationship To Witness

This document uses **Witness** as a human inspection role, not as a new
canonical ontology object.

A Witness verifies that a claim, lineage, contract obligation, or rendered
expression remains inspectable. A Witness may use Trust Card, Workspace
Projection, Lineage Explorer, Semantic Contract Inspector, or future Critic
Ecology inspection surfaces.

Witness activity does not create audit truth by viewing it. A Witness may
prompt Steward action, but the act of inspection is not itself ratification,
supersession, or canonical evaluation unless a future authority explicitly
creates such an object.

---

## Relationship To Ratification

Ratification is a human governance act. Findings may support ratification by
making defects, omissions, contradictions, provenance gaps, or contract
failures explicit.

Findings do not ratify anything.

An Audit Vector does not ratify anything.

If a future Steward ratifies a release, supersession, or acceptance decision
after reviewing Findings, that ratification must be represented through the
governing authority and storage mechanisms for the ratified object. The
projection that helped the Steward decide remains disposable.

---

## Relationship To Workspace Projection

Workspace Projection is a Pure Projection over canonical references.

Critic Ecology should follow the same rule:

```text
focus canonical object
    +
related canonical Findings
    +
available inspection surfaces
    =
workspace-ready projection
```

The Workspace may display Findings and may group them by audit domain. It must
not create Findings, infer missing Findings, assign a durable Audit Vector ID,
or persist the arrangement as knowledge.

---

## Relationship To Trust Card

The Trust Card is a Pure Projection over persisted lineage, execution,
contract, and Critic facts.

Future Trust Cards may include Finding summaries only by reading canonical
Findings or canonical `CriticReport` content. The Trust Card must not compute
trust from provider identity, steward credential, aggregate confidence, or
hidden dashboard state.

The Trust Card may say:

```text
3 blocking Findings exist.
2 provenance Findings are unresolved.
No accessibility Findings have been evaluated.
```

It must not say:

```text
Trust score: 87
```

unless a future ratified specification defines exactly what that number means,
what canonical Findings it derives from, and why the compression does not
collapse orthogonal audit domains.

---

## Orthogonal Audit Pattern

### Intent

Evaluate one artifact across multiple independent audit domains without
collapsing those domains into a single opaque standing.

Each domain asks a different constitutional question. The correct unit of
durable record is the answer to one bounded question: a Finding.

### Properties

- each Finding belongs to one audit domain;
- each Finding has explicit parents;
- each Finding identifies the evaluated object;
- each Finding identifies the rule, obligation, invariant, or check it applies;
- each Finding records status without mutating the evaluated object;
- each Finding remains append-only after creation;
- each Finding can coexist with other Findings from other domains;
- Findings may contradict, supersede, or refine only through append-only
  relations authorized by future storage specification;
- aggregate views are regenerated from Findings; and
- no aggregate view may rewrite, suppress, or normalize away individual
  Findings.

### Known Uses

Existing implementation surfaces already approximate this pattern without
ratifying a separate Findings schema:

- Validation report findings such as missing required terms, unsupported
  claims, omitted observations, omitted interpretations, semantic drift, and
  warnings.
- Trust Summary checks such as evidence preservation, lineage completeness,
  constitutional profile recording, semantic contract satisfaction, and Critic
  approval.
- Semantic Contract Inspector obligations that report satisfied, missing,
  prohibited, or not evaluated outcomes.
- Provider Matrix records that preserve each realization without ranking
  providers into a winner.

### Anti-Patterns

- merging multiple audit domains into one score;
- replacing individual Findings with a status badge;
- storing a dashboard layout as audit truth;
- letting a frontend infer missing Findings;
- treating unevaluated domains as partial success;
- letting provider identity or steward credential determine standing;
- rewriting Artist output after a Finding is created; and
- synthesizing across orthogonal audit domains without preserving the original
  Findings.

### Constitutional Basis

The pattern follows:

- Article I, because each Finding preserves lineage rather than obscuring
  ancestors;
- Article II, because auditability requires inspectable inputs and outputs;
- Article VI, because every generated audit object requires provenance;
- Article IX, because semantic evaluation must use the referenced
  `ArchitectPlan`;
- Article X, because new Critic output appends rather than overwrites;
- Article XI, because ambiguity remains visible to the Steward;
- CI-006, because no Finding may float without parents;
- CI-009, because contract evaluation must remain contract-bound;
- CI-011, because nondeterministic audit requires complete audit metadata;
- CI-012, because projections over Findings are read-only; and
- CI-016, because aggregate projections are disposable.

---

## Finding

### Current Constitutional Status

`Finding` is not currently ratified as an independent top-level ontology class.
The existing ratified evaluation object is `CriticReport`.

The future implementation path should treat a Finding as the candidate durable
unit inside the Critic layer. It requires ratification before schema or storage
work.

### If Ratified As Canonical

If a future authority ratifies Finding as canonical, it must have the following
properties.

### Identity

A Finding identity must be deterministic when the audit check is deterministic.
The identity must derive from canonical inputs such as:

- evaluated object ID;
- evaluated object class;
- audit domain;
- audit rule or obligation ID;
- direct parent report or invocation ID, if required by the future schema;
- normalized status vocabulary, if part of the rule definition;
- rule version or implementation version; and
- exact evidence references used by the Finding.

For nondeterministic audit, identity must still be stable for the persisted
result and the record must preserve the full audit payload required by CI-011.

Finding identity must not derive from:

- provider reputation;
- steward credential;
- UI position;
- dashboard grouping;
- aggregate vector score;
- generated label text;
- timestamp alone; or
- any field not needed to establish the Finding's audit claim.

### Immutability

A canonical Finding is immutable after insertion.

If a later audit changes the result, it creates a new Finding or a new
`CriticReport` lineage. It does not edit the earlier Finding.

### Lineage

A canonical Finding must trace to all required parents for its domain.

At minimum, a Finding must reference:

- the evaluated object;
- the audit domain;
- the audit rule, obligation, invariant, or check;
- the Critic invocation or `CriticReport` lineage that produced it; and
- any canonical evidence, contract, expression profile, execution record, or
  provenance record needed to independently verify the result.

No Finding may exist as a floating node.

### Provenance

A Finding must preserve:

- producing implementation or provider identity;
- implementation version or model identity where applicable;
- configuration;
- direct input IDs;
- raw audit input when nondeterministic;
- raw audit output when nondeterministic;
- creation timestamp;
- constitutional profile or rule profile where required; and
- enough references to reproduce or independently audit the result.

### Append-Only Behavior

A Finding is append-only.

Later Findings may coexist with earlier Findings. A future supersession relation
may mark one Finding as superseded by another only if a ratified storage
specification authorizes that relation. The original Finding remains
inspectable.

### Constitutional Status

If ratified, Finding belongs in the Critic layer as Evaluation. It does not add
a pipeline stage. It refines the internal structure of Critic output.

It may be modeled as:

- a child record of `CriticReport`; or
- a canonical evaluation object directly associated with a Critic invocation.

This document does not choose a schema form. That choice requires a future
storage specification or ADR.

### Scope

A Finding answers one bounded audit question.

Examples of possible domains:

- semantic contract;
- provenance;
- lineage completeness;
- execution audit;
- accessibility;
- constitutional profile;
- provider interchangeability;
- side-effect-free read verification; and
- stewardship review state.

The domain list is not implemented by this document. Future domains require
their own ratified rule definitions before persistence.

### Required References

A Finding must reference only canonical objects and authorized rule definitions.
Depending on domain, required references may include:

- `RenderedNarrative`;
- `ArchitectPlan`;
- `ExpressionProfile`;
- `NarrativeBlueprint`;
- `Interpretation`;
- `Perspective`;
- `Observation`;
- `SourceExtraction`;
- `SourceDocument`;
- `CriticReport`;
- `ValidationReport`, where current implementation uses that name;
- provider execution configuration;
- constitutional invariant ID;
- audit rule ID; and
- Steward ratification record, if the Finding concerns a human-only decision.

---

## Audit Vector

### Classification

An Audit Vector is a projection.

It is not canonical ontology.

It is not a derived artifact that should be persisted for computation.

It is a Pure Projection and Inspection Surface over canonical Findings and
related canonical objects.

### Required Projection Properties

An Audit Vector possesses:

- no identity;
- no authority;
- no provenance;
- no supersession;
- no constitutional profile;
- no independent storage lifecycle;
- no standing apart from the Findings it arranges; and
- no power to suppress, rewrite, or merge Findings.

It is fully regenerable from canonical Findings and canonical ancestors.

Deleting or discarding an Audit Vector changes no knowledge.

### Permitted Contents

An Audit Vector may contain:

- grouped Finding references;
- counts by domain;
- status rollups that preserve access to individual Findings;
- `not_evaluated` markers for missing domains;
- links to Lineage Explorer, Trust Card, Workspace Projection, or Semantic
  Contract Inspector; and
- display ordering that is explicitly non-authoritative.

### Forbidden Contents

An Audit Vector must not contain:

- a durable vector ID;
- a persisted authority state;
- a hidden score that replaces Findings;
- a supersession relation;
- generated provenance;
- inferred ancestry;
- provider ranking;
- steward credential weighting; or
- any status that cannot be regenerated from individual Findings.

---

## Cross-Check Against Existing Patterns

### Workspace Projection

Workspace Projection is a Pure Projection and Inspection Surface. Audit Vector
matches this pattern because it arranges canonical references for attention.

Workspace Projection does not persist a workspace object. Audit Vector must not
persist an audit-vector object.

### ObservationDerived

ObservationDerived is Disposable Derived metadata. Finding is not like
ObservationDerived because a Finding, if ratified, is audit history rather than
computational cache.

Aggregate counts, grouped domain summaries, or vector-style badges derived from
Findings may follow the Disposable Derived pattern if future implementation
needs caching. The Findings themselves must not be treated as disposable.

### Trust Card

Trust Card is a Pure Projection over persisted lineage, execution, contract,
and Critic facts.

Audit Vector matches Trust Card more closely than it matches ontology. It is a
human-facing arrangement of canonical audit facts, not a new source of truth.

### Pattern Decision

Findings instantiate the existing Critic Evaluation responsibility.

Audit Vector instantiates the existing Pure Projection and Inspection Surface
patterns.

No new architecture pattern is needed.

No new ontology class is authorized by this document alone.

---

## Misuse Analysis

### Monolithic Critic Score

A monolithic score collapses orthogonal audit domains into one number. It hides
which constitutional question failed, whether the failure was semantic,
provenance-related, accessibility-related, or unevaluated, and whether the
Steward must decide an ambiguity.

It violates the Orthogonal Audit Pattern by replacing Findings with aggregate
standing.

### Opaque Confidence Number

An opaque confidence number is not auditability. It does not identify the rule,
parent objects, inputs, output, provider behavior, or provenance necessary for
independent review.

If confidence exists in a future domain, it must be a Finding attribute with
explicit rule semantics, not a substitute for the Finding.

### Persistent Audit Dashboard

A persistent audit dashboard turns a view into history. It risks assigning
identity, authority, and lifecycle to an arrangement that should be regenerated
from canonical Findings.

Dashboard state may be UI preference. It is not audit truth.

### Storing Projections As Ontology

Storing a projection as ontology creates a second source of authority. Once the
projection drifts from its source Findings, the system must choose between the
projection and the canonical audit record.

Article XIII forbids competing authoritative formats, and CI-016 requires
derived conveniences to remain disposable.

### Rewriting Artist Output

A Finding may report a defect in Artist output. It must not repair the
`RenderedNarrative`.

Correction requires a new Artist invocation, new `RenderedNarrative`, new
Critic invocation, or Steward action authorized by existing governance. The
old output and old Finding remain inspectable.

### Synthesizing Across Orthogonal Audit Domains

Synthesizing across domains can be useful for attention, but it is dangerous
when it hides the underlying Findings.

For example, a semantic pass cannot cancel a provenance failure. An
accessibility pass cannot cancel an unsupported claim. A provider audit record
cannot substitute for contract satisfaction.

Cross-domain synthesis must remain a projection that links back to individual
Findings.

---

## Future Implementation Guidance

### What Implementation Is Now Constitutionally Authorized

This documentation authorizes future planning work only:

- draft an ADR or storage specification for canonical Findings;
- define bounded audit domains and rule IDs;
- map existing `CriticReport` or `validation_reports` output to candidate
  Finding records on paper;
- design read-only Audit Vector projections over hypothetical Findings;
- design tests that would enforce Finding immutability, ancestry, and
  read-only projection behavior; and
- review whether Findings should be child records of `CriticReport` or a
  separately named canonical evaluation object.

No runtime implementation is authorized by this document alone.

### What Implementation Remains Constitutionally Forbidden

The following remain forbidden until ratified authority exists:

- implementing Critic Ecology runtime behavior;
- implementing `SemanticCritic`, `ProvenanceCritic`, `AccessibilityCritic`, or
  any new audit logic;
- creating a Findings table or schema migration;
- adding provider behavior;
- adding UI surfaces;
- persisting Audit Vectors;
- assigning Audit Vectors IDs, provenance, authority, supersession, or
  constitutional profiles;
- adding a monolithic critic score;
- letting a dashboard create audit truth;
- rewriting Artist output from audit results;
- allowing reads to create Findings; and
- treating this document as a constitutional amendment.

---

## Conclusion

The correct durable artifact of future Critic Ecology is the individual
Finding, subject to future ratification and storage specification.

The Audit Vector is a disposable Pure Projection and Inspection Surface over
Findings. It has no independent identity, authority, provenance, supersession,
or constitutional profile.

This preserves orthogonal audit domains, keeps Steward judgment explicit, and
avoids creating a second source of audit truth.
