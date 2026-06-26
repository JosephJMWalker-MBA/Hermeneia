# Finding Specification

**Status:** RATIFIED — see [ADR-0041](../adr/ADR-0041-finding-and-evaluation-function.md)
**Implementation status:** AUTHORIZED — Sprint E1
**Constitutional authority:** [`../00_Constitution.md`](../00_Constitution.md), [`../01_Authority_Index.md`](../01_Authority_Index.md), [`../02_Constitutional_Invariants.md`](../02_Constitutional_Invariants.md)
**Pattern authority:** [`../Architecture_Patterns.md`](../Architecture_Patterns.md)
**Related review:** [`../Critic_Ecology.md`](../Critic_Ecology.md)

---

## Purpose

This specification answers one constitutional question at the specification
level:

```text
Is a Finding the smallest independently ratifiable
machine-generated epistemic object?
```

The provisional answer is yes.

This document does not ratify Finding as ontology. It does not amend the
Constitution. It does not replace `CriticReport`. It does not authorize code,
tables, schemas, APIs, UI, providers, tests, or persistence.

Its purpose is to define Finding precisely enough that a future ADR or
constitutional amendment can ratify, revise, or reject it without
implementation guessing.

---

## 1. Definition

A Finding is an immutable, traceable record of a constitutionally observable
semantic transformation between an `ArchitectPlan` and a `RenderedNarrative`
within exactly one orthogonal evaluation dimension.

More generally:

```text
Finding = one bounded machine-observable epistemic delta
```

A Finding records how one contractual obligation, lineage obligation,
provenance obligation, accessibility obligation, or other ratified evaluation
dimension survived or failed during transmission from intended understanding to
rendered expression.

A Finding is not:

- a dashboard;
- a report view;
- a score;
- a recommendation;
- a governance act;
- a human witness statement;
- a provider judgment;
- a UI grouping; or
- an aggregate audit vector.

For Semantic Contract Fulfillment, the shape is:

```text
ArchitectPlan
    +
RenderedNarrative
    +
canonical lineage
    +
evaluation dimension
    =
Finding[]
```

The `ArchitectPlan` states what must be communicated. The
`RenderedNarrative` is what was transmitted. A Finding records one observable
semantic delta between them under a single evaluation dimension.

---

## 2. Constitutional Position

### Current Authority

Current constitutional authority names `CriticReport` as the Evaluation object:

```text
CriticReport | Evaluation | Assessment of expression against contract
```

Article X also states that a new Critic invocation creates a new
`CriticReport`.

Therefore, Finding cannot be implemented as a replacement for `CriticReport`
without future ratified authority.

### Provisional Classification

Finding is provisionally classified as a candidate canonical ontology object in
the Evaluation class.

It is not a derived artifact because it is not merely computational
convenience. If ratified, deleting a Finding would delete audit history.

It is not a projection because it cannot be losslessly regenerated from an
aggregate view. The aggregate view is regenerated from Findings, not the other
way around.

It is not an implementation detail because its identity, lineage, immutability,
and witnessability affect constitutional audit.

The provisional constitutional relationship is:

```text
Evaluation Function
    ↓
Finding[]
    ↓
Projections
    ↓
Stewardship
```

Under this model, `CriticReport` is a constitutional tension. It may be:

- retained as the canonical container for Findings;
- reclassified as a projection over Findings;
- retired after migration; or
- superseded by Finding as the canonical Evaluation object.

That choice requires a future ADR or amendment.

### Governing Articles And Invariants

The governing constitutional articles are Article I, Article II, Article VI,
Article VII, Article VIII, Article IX, Article X, Article XI, Article XII,
Article XIII, and Article XIV.

The governing invariants are CI-005, CI-006, CI-007, CI-009, CI-010, CI-011,
CI-012, CI-013, CI-014, CI-015, CI-016, INV-XI, INV-XIII, and INV-XIV.

---

## 3. Smallest Epistemic Unit

A Finding appears to be the smallest machine-generated object that can be
independently:

- witnessed;
- traced;
- cited;
- superseded;
- audited.

### Witnessed

A Witness can inspect one Finding and ask:

```text
What exact semantic delta did the machine observe?
Which contractual or constitutional obligation does it concern?
Which ancestors support the claim?
```

An Audit Vector, Trust Card, dashboard, or summary score cannot be witnessed
without decomposing it into constituent Findings.

### Traced

A Finding can trace directly to:

- the evaluated `RenderedNarrative`;
- the relevant `ArchitectPlan` clause or other obligation;
- the supporting canonical lineage;
- the evaluation dimension;
- the evaluation method; and
- the constitutional profile under which evaluation occurred.

### Cited

A Finding can be cited as the reason a Steward should inspect a specific
semantic, provenance, lineage, accessibility, or constitutional issue.

An aggregate report can only cite many issues at once unless it links to its
constituent Findings.

### Superseded

A Finding can be superseded by a later Finding if future authority permits an
append-only supersession relation. The old Finding remains inspectable.

Superseding an aggregate view is weaker because it obscures which underlying
semantic delta changed.

### Audited

A Finding can be audited by replaying or inspecting one evaluation method over
one dimension and one set of parents.

If a smaller machine-generated object exists, it would need to be a subclaim
inside a Finding. This specification finds no current need for that smaller
object. If one is discovered, implementation must stop and the ontology
question must be reopened.

---

## 4. Conceptual Fields

This section defines conceptual fields only. It does not define SQL, storage,
serialization, API response shape, or implementation names.

### `finding_id`

Constitutional.

If Finding is canonical, it requires stable identity. The identity formula must
be ratified before implementation. It must not derive from UI position,
projection ID, dashboard ID, provider reputation, steward credential, or
aggregate score.

Open identity question:

```text
Should deterministic Findings from identical canonical inputs collapse to the
same ID across invocations, or should evaluation invocation identity be part of
the Finding identity?
```

### `dimension`

Constitutional.

Every Finding belongs to exactly one orthogonal evaluation dimension. Examples
may include semantic contract, provenance, lineage, accessibility,
constitutional profile, execution audit, or provider interchangeability.

The dimension prevents synthesis across domains from hiding the underlying
audit claim.

### `operation`

Constitutional if the operation taxonomy is ratified.

The operation records what kind of semantic transformation was observed:
preservation, omission, transformation, injection, or another future ratified
operation.

### `status`

Constitutional if status affects audit, blocking, release, or Steward review.

Status must be a controlled vocabulary. It must not be a vague confidence
number. It must not silently collapse `not_evaluated` into success.

### `contract_clause`

Constitutional for Semantic Contract Fulfillment.

The Finding must identify the specific `ArchitectPlan` obligation, paragraph,
required term, required observation, forbidden claim, or equivalent contract
clause that was evaluated.

For non-semantic dimensions, this may be replaced by an equivalent rule or
obligation reference.

### `canonical_subject`

Constitutional.

The Finding must identify the canonical object it evaluates. For Semantic
Contract Fulfillment, the subject is normally a `RenderedNarrative` under a
specific `ArchitectPlan` and `ExpressionProfile`.

### `supporting_objects`

Constitutional.

The Finding must reference the canonical parents needed to verify it. These may
include `ArchitectPlan`, `ExpressionProfile`, `RenderedNarrative`,
`NarrativeBlueprint`, `Interpretation`, `Perspective`, `Observation`,
`SourceExtraction`, `SourceDocument`, execution records, or prior Findings.

### `evidence`

Constitutional when necessary for independent audit.

Evidence is the bounded material used by the evaluation method to support the
Finding. It may include canonical IDs, excerpts from canonical objects,
structural locations, rule identifiers, or raw nondeterministic audit output.

Evidence must not rewrite source evidence.

### `traceable`

Constitutional as a property; implementation-specific as a field.

Every Finding must be traceable. A boolean field may be useful in an
implementation, but the constitutional requirement is stronger: generation
must fail if required lineage cannot be established.

### `constitution_version`

Constitutional.

A Finding must identify the constitutional profile under which it was created,
including the Constitution, authority index, invariant profile, and relevant
architecture or rule profile.

### `evaluation_method`

Constitutional.

The Finding must identify the function, rule set, implementation version,
provider, model, configuration, or other method that produced it. Deterministic
methods must be reproducible. Nondeterministic methods must satisfy CI-011.

### `created_at`

Implementation concern with constitutional implications.

Timestamping is required for audit sequencing and custody, but timestamp alone
must not determine Finding identity or authority.

---

## 5. Operations Taxonomy

The provisional semantic operations are:

| Operation | Meaning |
|---|---|
| `preservation` | The rendered artifact preserves the evaluated obligation's generative structure. |
| `omission` | The rendered artifact fails to transmit a required obligation. |
| `transformation` | The rendered artifact transmits a changed generative structure. |
| `injection` | The rendered artifact introduces unsupported semantic material. |

These four operations are provisionally exhaustive for Semantic Contract
Fulfillment because every evaluated contractual obligation can be classified as
preserved, omitted, transformed, or accompanied by unsupported addition.

However, exhaustiveness is domain-specific. Provenance, accessibility, or
execution audit may require other operations or statuses. Those operations must
be ratified by domain specification before implementation.

### Obligation State

Every evaluated contractual obligation should end in exactly one primary state
within a given evaluation dimension.

Allowed primary states for Semantic Contract Fulfillment are provisionally:

- `preserved`;
- `omitted`;
- `transformed`;
- `injected`;
- `not_evaluated`.

`not_evaluated` is not a success state. It records that no authoritative
evaluation exists.

One obligation may also produce multiple Findings if distinct deltas are
observed. For example, a required concept may be partially preserved while an
unsupported metaphor injects a new causal model. A future domain specification
must decide whether that is represented as one compound Finding or multiple
atomic Findings.

---

## 6. Relationship To Evaluation Functions

The Evaluation Function is computational.

The Finding is epistemic.

```text
Evaluation Function
    ↓
Finding[]
```

The function is not preserved as a canonical object because it is executable
method, not epistemic result. Its identity, version, configuration, and
execution metadata are preserved as Finding provenance or audit metadata.

The Finding is preserved because it is the machine-generated epistemic claim:

```text
Under this dimension, this obligation transformed in this way.
```

The function may be replaced, upgraded, audited, or re-run. Earlier Findings
remain inspectable. A later function produces new Findings rather than editing
old ones.

---

## 7. Relationship To Projections

Audit Vector, Trust Card, Dashboard, report view, matrix cell, release
checklist, summary score, and similar views are projections regenerated from
Findings and other canonical objects.

They follow the Regeneration Principle in
[`../Architecture_Patterns.md`](../Architecture_Patterns.md):

```text
If an artifact can be losslessly regenerated from immutable canonical
constituents, it should be implemented as a disposable projection or derived
artifact rather than a canonical object.
```

Therefore, these projections possess:

- no independent identity;
- no authority;
- no provenance of their own;
- no supersession of their own;
- no constitutional profile of their own;
- no persistence requirement; and
- no power to suppress or rewrite Findings.

They may group, count, sort, expose, link, or summarize Findings for human
attention. They must always preserve access to the underlying Findings.

---

## 8. Relationship To Steward

Findings contain no governance.

They recommend nothing.

They decide nothing.

They do not approve, reject, release, ratify, suppress, certify, or supersede.

A Finding preserves an observable semantic transformation. Stewardship begins
after Findings exist.

The Steward may inspect Findings, request a new render, ratify a release,
record a governance decision, supersede an authority, or decline to act. Those
acts belong to human governance and require their own authority and provenance.

Steward identity, credential, reputation, institutional status, or social
status must not determine Finding status or semantic standing.

---

## 9. Relationship To Witness

Findings establish machine-observable semantic deltas.

Witnesses establish human understanding.

These are distinct constitutional domains.

A Witness may inspect a Finding and verify that:

- the Finding is traceable;
- the cited parents exist;
- the evidence is inspectable;
- the stated operation is understandable; and
- the projected view did not hide the underlying Finding.

The Witness does not become the Finding. A human statement about whether
understanding survived belongs to a future human governance or witness object,
not to the machine-generated Finding itself.

This boundary prevents machine evaluation from being confused with human
ratification.

---

## 10. Future Analytical Layer

The following belong to the research layer:

- Shannon entropy;
- mutual information;
- Kolmogorov complexity;
- Minimum Description Length;
- compression metrics;
- Bayesian analysis;
- category-theoretic analysis;
- semantic mutual information estimates; and
- other scientific models of transmission, compression, or inference.

They may be computed over Findings as analytical projections.

They SHALL NOT become canonical Finding fields.

They SHALL NOT determine Finding identity.

They SHALL NOT replace the operation taxonomy.

They SHALL NOT become constitutional vocabulary unless separately ratified.

This separation preserves constitutional stability. The engineering substrate
can remain correct even when the scientific explanation evolves.

---

## Relationship To CriticReport

Current authority names `CriticReport`. This specification does not change
that.

The Finding analysis creates a future ratification question:

```text
Is CriticReport an aggregate projection over Findings rather than an
irreducible Evaluation object?
```

If yes, a future ADR or amendment must define whether `CriticReport` is
retained, retired, reclassified, or superseded. Existing implementation must
not silently rename or remove it.

---

## Implementation Authorization

This specification authorizes no implementation.

Authorized next steps:

- constitutional discussion;
- ADR drafting;
- amendment analysis;
- schema impact analysis on paper;
- migration analysis on paper;
- operation-taxonomy review;
- mapping existing validation report fields to candidate Findings on paper;
- defining proposed executable invariants as documentation.

Forbidden until ratification:

- creating Finding storage;
- creating tables or schemas;
- creating APIs;
- creating UI;
- changing providers;
- changing tests;
- changing ontology;
- changing persistence;
- emitting runtime Findings;
- persisting Audit Vectors;
- replacing `CriticReport`; and
- treating this specification as ratified authority.

---

## Future ADR Or Amendment Requirement

Implementation requires future ratified authority.

At minimum, an ADR is required before implementation because Finding would
define a durable machine-generated Evaluation unit with identity, lineage,
immutability, and potential supersession behavior.

A constitutional amendment may be required if Finding replaces or reclassifies
`CriticReport`, because the current Constitution explicitly names
`CriticReport` and states that a new Critic invocation creates one.

The ADR or amendment must answer:

- Is Finding ratified as canonical ontology?
- Does Finding supersede `CriticReport`?
- What is the identity formula?
- What fields are constitutionally required?
- What fields are implementation concerns?
- What operations are exhaustive for each dimension?
- What statuses are permitted?
- What provenance is required?
- How does Finding supersession work?
- How are existing `validation_reports` interpreted?
- What tests enforce the invariant?

---

## Provisional Conclusion

Finding appears to be the smallest independently ratifiable
machine-generated epistemic object.

It is the candidate durable boundary between:

```text
machine evaluation
```

and:

```text
human stewardship, witness, and ratification
```

That conclusion remains provisional until ratified by the governing process.
