# Evaluation Function Specification

**Status:** RATIFIED (Structural EF) — see [ADR-0041](../adr/ADR-0041-finding-and-evaluation-function.md)
**Implementation status:** AUTHORIZED — Sprint E1
**Constitutional authority:** [`../00_Constitution.md`](../00_Constitution.md), [`../01_Authority_Index.md`](../01_Authority_Index.md), [`../02_Constitutional_Invariants.md`](../02_Constitutional_Invariants.md)
**Pattern authority:** [`../Architecture_Patterns.md`](../Architecture_Patterns.md)
**Related specifications:** [`finding.spec.md`](finding.spec.md), [`../Critic_Ecology.md`](../Critic_Ecology.md)

---

## Purpose

This specification defines Evaluation Function as a computational architectural
pattern.

It does not implement Evaluation Functions.

It does not ratify Finding.

It does not replace `CriticReport`.

It does not authorize code, schemas, tests, providers, APIs, UI, or
persistence.

The purpose is to make the Critic layer precise before implementation:

```text
Evaluation Function
    ↓
Finding[]
```

The function is computational.

The Finding is epistemic.

The function is reproducible infrastructure.

The Finding is the preserved object.

---

## 1. Canonical Definition

An Evaluation Function is a constitutionally constrained computation that maps
canonical inputs to immutable Findings within exactly one orthogonal evaluation
dimension.

More formally:

```text
f_dimension(
    canonical_inputs
) -> Finding[]
```

An Evaluation Function is not a canonical object. It is method, not history.

The durable output of an Evaluation Function is the set of Findings it
produces, subject to future Finding ratification.

An Evaluation Function is not:

- a Critic agent;
- a provider;
- a dashboard;
- a score generator;
- a recommendation engine;
- a governance mechanism;
- a writer;
- a rewriter; or
- a summarizer.

It is a constrained mapping from canonical facts to bounded evaluation results.

---

## 2. Inputs

Evaluation Function inputs must be explicit and canonical.

For Semantic Contract Fulfillment, the primary inputs are:

- `ArchitectPlan`;
- `RenderedNarrative`;
- canonical lineage from `RenderedNarrative` back to immutable ancestors; and
- `ExpressionProfile`, where applicable.

Depending on dimension, inputs may also include:

- `NarrativeBlueprint`;
- `Interpretation`;
- `Perspective`;
- `Observation`;
- `SourceExtraction`;
- `SourceDocument`;
- provider execution configuration already preserved on the evaluated artifact;
- constitutional profile;
- invariant profile;
- evaluation rule specification; and
- implementation version.

The following are forbidden as hidden inputs:

- hidden process memory;
- unstated external context;
- previous conversation state;
- provider reputation;
- steward credential;
- UI state;
- dashboard state;
- ranking state;
- cache contents that cannot be regenerated;
- unstated model preference; and
- any input not represented in the Finding's traceable provenance.

No hidden state.

No memory.

No provider authority.

If a future implementation uses a model provider as part of an Evaluation
Function, the provider supplies computation only. It does not gain
constitutional authority, does not determine semantic standing from reputation,
and must satisfy nondeterministic audit requirements.

---

## 3. Outputs

The only epistemic output of an Evaluation Function is:

```text
Finding[]
```

An Evaluation Function never outputs canonical scores.

It never outputs recommendations.

It never outputs rewritten text.

It never outputs governance.

It never mutates the artifact it evaluates.

It never creates a projection as its preserved result.

A function may produce an empty Finding set only when the relevant dimension
and rule specification define what absence of Findings means. Absence must not
be silently treated as success unless the rule explicitly states that the
function is complete and no deltas were observed.

If a dimension was not evaluated, the output must preserve that fact through an
authorized `not_evaluated` Finding or equivalent future ratified mechanism. It
must not disappear into silence.

---

## 4. Determinism

Evaluation Functions require three distinctions.

### Implementation Determinism

Implementation determinism means one implementation, running with the same
runtime, version, configuration, and canonical inputs, produces the same
Finding set.

This is the minimum requirement for deterministic Evaluation Functions.

### Functional Determinism

Functional determinism means the function's behavior is specified well enough
that different conforming implementations produce the same Finding set from the
same canonical inputs.

This is the target for constitutional dimensions that can be evaluated by pure
computation.

### Constitutional Reproducibility

Constitutional reproducibility means a future Steward, Witness, or auditor can
verify how the Finding set was produced.

For deterministic functions, this should support reproduction from immutable
parents and configuration.

For nondeterministic functions, byte-for-byte reproduction may be impossible,
but CI-011 still requires complete auditability: inputs, provider identity,
model identity, configuration, request payload, execution metadata, raw output,
resulting object identity, and provenance.

### Required Direction

Identical canonical inputs should produce identical Finding sets regardless of
implementation technology when the dimension is declared deterministic.

If two conforming deterministic implementations produce different Findings
from identical canonical inputs, one of the following is true:

- the function is underspecified;
- one implementation is nonconforming;
- the inputs were not actually identical; or
- the dimension cannot be constitutionally deterministic and must be
  reclassified before implementation.

---

## 5. Orthogonality

One Evaluation Function evaluates exactly one constitutional dimension.

Orthogonality prevents one domain from masking another. A semantic pass cannot
cancel a provenance failure. An accessibility pass cannot cancel an unsupported
claim. Provider audit metadata cannot substitute for contract satisfaction.

Candidate dimensions include:

- semantic;
- structural;
- provenance;
- accessibility;
- constitutional;
- lineage;
- execution audit;
- provider interchangeability; and
- read-only integrity.

Each dimension must define:

- its canonical inputs;
- its rule vocabulary;
- its Finding operation vocabulary;
- its permitted statuses;
- its determinism class;
- its required provenance; and
- its failure behavior.

An aggregate view over multiple dimensions is a projection, not an Evaluation
Function.

---

## 6. Forbidden Behavior

An Evaluation Function must not:

- rewrite `RenderedNarrative`;
- rewrite `ArchitectPlan`;
- rewrite evidence;
- summarize evaluated objects as its preserved result;
- synthesize across dimensions;
- rank providers;
- rank stewards;
- aggregate Findings into a canonical score;
- emit confidence theater;
- hide `not_evaluated`;
- turn missing lineage into partial success;
- make recommendations;
- perform governance;
- approve release;
- suppress artifacts;
- create projections as durable outputs;
- mutate storage during read-only inspection; or
- treat provider reputation as evidence.

Confidence theater means a number or label that appears quantitative but lacks
ratified semantics, traceable evidence, and bounded rule meaning.

---

## 7. Relationship To Findings

Evaluation Functions are computational.

Findings are epistemic.

Functions are not preserved as canonical objects.

Findings are preserved, if ratified, because they are the machine-generated
epistemic deltas that can be witnessed, traced, cited, superseded, and audited.

The function's identity, version, rule set, and configuration belong in
Finding provenance or equivalent audit metadata. They do not become the
preserved object.

Changing a function does not rewrite old Findings.

Re-running a function produces a new Finding set or the same deterministic
Finding identities according to the future ratified identity rule. Existing
Findings remain inspectable.

---

## 8. Relationship To Projections

The following are regenerated from Findings and other canonical objects:

- Audit Vector;
- Trust Card;
- Dashboard;
- report view;
- matrix cell;
- release checklist;
- summary score; and
- research metrics.

They are projections under the Regeneration Principle in
[`../Architecture_Patterns.md`](../Architecture_Patterns.md).

They possess:

- no independent identity;
- no authority;
- no provenance of their own;
- no supersession of their own;
- no constitutional profile of their own; and
- no power to rewrite Findings.

An Evaluation Function does not emit these projections as preserved objects.
Projection construction happens after Findings exist.

---

## 9. Relationship To Research

The following research tools may inform implementation design or post-hoc
analysis:

- Shannon entropy;
- mutual information;
- Kolmogorov complexity;
- Minimum Description Length;
- compression metrics;
- Bayesian analysis;
- category theory;
- semantic mutual information; and
- other scientific models of transmission.

They SHALL NOT define constitutional behavior.

They SHALL NOT become hidden inputs.

They SHALL NOT become required Finding fields.

They SHALL NOT replace the operation taxonomy.

They SHALL NOT produce canonical scores unless separately ratified by future
authority.

This separation preserves constitutional stability. The engineering substrate
can remain valid while the science of understanding evolves.

---

## 10. Future Implementation Guidance

This specification authorizes future planning, not implementation.

After this specification, the following work is constitutionally reasonable as
documentation or design only:

- define candidate deterministic Evaluation Functions on paper;
- define one candidate dimension, such as structural evaluation, on paper;
- map each function output to conceptual Finding fields;
- define proposed conformance tests as documentation;
- identify which future ADR or amendment must ratify Finding and Evaluation
  Function behavior;
- analyze how existing `validation_reports` would map to Findings; and
- analyze whether `CriticReport` remains canonical or becomes projection.

Implementation remains forbidden until ratified authority exists for Findings
and any replacement or reclassification of `CriticReport`.

Forbidden implementation includes:

- writing Evaluation Function code;
- creating `SemanticCritic`;
- creating `ProvenanceCritic`;
- creating `AccessibilityCritic`;
- creating tables or schemas;
- creating APIs;
- creating UI;
- changing providers;
- changing tests;
- emitting Findings at runtime;
- persisting projections; and
- replacing `CriticReport`.

---

## Constitutional Review

No constitutional ambiguity blocks this documentation sprint because the
document does not implement or ratify anything.

Future implementation requires at least an ADR because Evaluation Functions
would define the computational method that creates durable machine-generated
evaluation artifacts.

A constitutional amendment may be required if the future implementation
replaces or reclassifies `CriticReport`, because current constitutional
authority explicitly names `CriticReport` and states that a new Critic
invocation creates one.

The future ADR or amendment must answer:

- Which Evaluation Functions are authorized?
- Which dimensions are orthogonal?
- Which dimensions are deterministic?
- What canonical inputs are required for each function?
- What Finding operations and statuses may each function emit?
- What provenance must be preserved?
- How does the implementation prove no hidden state?
- How are nondeterministic Evaluation Functions audited?
- How are existing `validation_reports` interpreted?
- Does `CriticReport` remain canonical?

---

## Provisional Conclusion

Evaluation Function is the Critic layer's computational substrate.

It is not an AI role.

It is not an agent.

It is not an ecology.

It is a constitutionally constrained mapping:

```text
canonical inputs
    ↓
one orthogonal dimension
    ↓
Finding[]
```

This makes the Critic layer independent of any particular provider. Frontier
models may later implement sophisticated evaluation functions, but the
architecture does not depend on them.
