# ADR-0043: Interpretive Divergence Classification

**Status:** DRAFT  
**Version:** 0.1  
**Date:** 2026-06-22  
**Supersedes:** None  
**Constitutional Cost of Error:** High - incorrect classification could duplicate
Interpretation, turn a score into authority, or confuse expressive variation with
epistemic divergence.

---

## Context

Hermeneia can preserve multiple Interpretations grounded in different
Perspectives and trace them to shared or distinct Observations. A user comparing
two readings should be able to answer:

- What stayed the same?
- What changed?
- Which evidence changed?
- Which assumptions or frames explain the change?
- Did claims converge, diverge, or contradict?

The desired human-facing output may include:

- Shared Claims;
- Distinct Claims;
- Contradictory Claims;
- Evidence Differences;
- Perspective Differences;
- Confidence Differences; and
- an optional non-authoritative distance summary.

The classification question is whether this output should initially be:

1. a Projection;
2. a Derived Artifact;
3. a new Canonical Object; or
4. the output of an Evaluation Function.

This ADR addresses classification only. It does not authorize implementation,
schema changes, a new pipeline stage, a new API, or a new scoring formula.

---

## Governing Distinctions

### Interpretation is already the canonical claim

ADR-0011 establishes that Claim is not a separate ontology object.
Interpretation already records the propositional content of a reading.

ADR-0015 establishes:

```text
Perspective
    |
    +-- Interpretation
            |
            +-- source Observations
```

Therefore, an interpretive comparison must begin with canonical
Interpretations, their Perspectives, and their Observation ancestry. It must not
create a second claim ontology merely to compare claims.

### Perspective is not ExpressionProfile

A Perspective is an epistemic frame. An ExpressionProfile is a constraint on
how established semantic obligations are expressed.

Examples such as `executive-en` and `literary-zh` name ExpressionProfiles, not
Perspectives. Comparing narratives rendered under those profiles primarily
measures **expressive divergence** unless the narratives descend from distinct
canonical Interpretations or distinct Perspective-grounded contracts.

The system must not report a stylistic, linguistic, or rhetorical difference as
an interpretive difference.

### Comparison does not determine correctness

Cross-Perspective Interpretations coexist. Divergence analysis may surface
differences, but it may not:

- rank Perspectives;
- declare one Interpretation correct;
- collapse contradiction into consensus;
- treat provider identity as epistemic authority; or
- authorize mutation or suppression of any compared object.

---

## Options Considered

### Option A - Pure Projection

```text
Interpretation A + Perspective A + Observation ancestry
Interpretation B + Perspective B + Observation ancestry
    |
    v
Interpretive Divergence Projection
```

The projection arranges existing canonical facts for inspection. It may expose
shared and distinct Interpretation references, shared and distinct evidence,
Perspective metadata, evidential-status differences, and explicit
contradictions already represented in canonical data.

**Strengths:**

- follows the Regeneration Principle;
- introduces no duplicate ontology;
- remains read-only and disposable;
- preserves direct access to canonical constituents;
- can evolve without migrating canonical history; and
- fits the existing comparison and inspection-surface patterns.

**Limitations:**

- it can only report distinctions supported by canonical inputs or explicitly
authorized deterministic derivations;
- semantic claim alignment is not automatically lossless when Interpretations
use different wording;
- deleting the projection deletes no knowledge, including no historical record
of a particular comparison run; and
- nondeterministic alignment cannot be presented as canonical fact.

**Constitutional fit:** Strong.

---

### Option B - Disposable Derived Artifact

```text
Canonical comparison inputs
    |
    v
Versioned claim-alignment or similarity metadata
```

A derived artifact would store regenerable computational conveniences such as
normalized claim text, token sets, deterministic alignment indexes, or cached
pairwise similarity results.

**Strengths:**

- suitable for expensive but reproducible computation;
- may record derivation version;
- may be deleted and rebuilt; and
- can support a Projection without becoming its authority.

**Limitations:**

- it is not the user-facing classification of the divergence report itself;
- it must not replace Interpretation content or evidence;
- a heuristic or LLM-produced alignment may not be reproducible enough to
qualify as safely disposable deterministic metadata; and
- persistence can tempt callers to treat a cache as epistemic history.

**Constitutional fit:** Strong as optional infrastructure beneath a Projection,
but incomplete as the classification of the feature.

---

### Option C - New Canonical Object

A canonical `InterpretiveDivergence`, `DeltaAnalysis`, or equivalent object
would possess stable identity, immutable lineage, append-only history, and an
epistemic class.

**Strengths:**

- preserves the exact historical output of a comparison;
- supports citation, witnessing, supersession, and independent stewardship; and
- could preserve genuinely irreducible machine or human judgments that cannot
be regenerated from their inputs.

**Limitations:**

- duplicates differences already computable from Interpretations,
Perspectives, and Observations;
- requires a new ontology object, identity formula, provenance contract,
epistemic class, storage schema, and amendment analysis;
- risks making aggregate scores or model-dependent alignments authoritative;
- risks reintroducing Claim under another name; and
- creates ambiguity about whether the object records facts, machine judgments,
or human conclusions.

The current proposal does not establish an irreducible object whose deletion
would erase constitutional history. It establishes a way to inspect existing
history.

**Constitutional fit:** Weak for the initial capability. Not authorized.

---

### Option D - Evaluation Function

An Evaluation Function maps canonical inputs to immutable Findings within
exactly one orthogonal evaluation dimension.

Potential dimensions might include:

- evidence-set overlap;
- evidential-status difference;
- contradiction under a ratified rule; or
- contract-preservation differences between RenderedNarratives.

**Strengths:**

- appropriate for bounded, deterministic, auditable machine observations;
- can produce durable Findings when a dimension and operation vocabulary are
separately authorized; and
- keeps computation distinct from preserved epistemic output.

**Limitations:**

- the requested report aggregates multiple dimensions;
- claim alignment and cultural-prior attribution are not presently authorized
orthogonal Evaluation Functions;
- an Interpretive Distance score is an aggregate analytical view, not a
Finding;
- Evaluation Functions evaluate obligations or bounded dimensions; they do not
create dashboards or comparison reports as durable outputs; and
- nondeterministic explanations such as "different cultural priors were
invoked" require explicit provenance and likely human stewardship.

**Constitutional fit:** Possible for future bounded sub-analyses, but incorrect
as the initial classification of the aggregate capability.

---

## Decision

### Initial classification: read-only Projection

Interpretive Divergence is initially classified as a **Pure Projection**
delivered through an **Inspection Surface**.

Its authoritative inputs are existing canonical objects and relations:

- Interpretation;
- Perspective;
- Observation;
- Interpretation-to-Observation lineage;
- evidential status where canonically present;
- supersession relations; and
- ratified contradiction records or Findings where available.

The projection has:

- no independent canonical identity;
- no epistemic class;
- no authority to rewrite or rank its inputs;
- no supersession lifecycle;
- no role as a parent in canonical lineage; and
- no requirement to be persisted.

Deleting or regenerating it changes no constitutional history.

### Derived artifacts are permitted only as disposable support

Deterministic, versioned computational support may be classified as Disposable
Derived metadata when it can be rebuilt from canonical inputs. Examples may
include:

- normalized comparison text;
- deterministic evidence-overlap sets;
- token indexes;
- exact-match claim indexes; and
- cached pairwise calculations.

Such artifacts must reference their canonical ancestors and derivation version.
They must never become the authoritative source for an Interpretation,
Perspective, contradiction, or Finding.

### Evaluation Functions require separate authorization

Future work may define one or more orthogonal Evaluation Functions for bounded
comparative dimensions. Each function requires:

- a named constitutional dimension;
- explicit canonical inputs;
- deterministic or explicitly audited behavior;
- a controlled operation and status vocabulary;
- a completeness rule;
- Finding provenance; and
- separate ADR authorization.

Any aggregate display over resulting Findings remains a Projection.

### No new canonical divergence object is authorized

This ADR does not authorize `InterpretiveDivergence`, `DeltaAnalysis`,
`ClaimAlignment`, or any equivalent canonical ontology object.

Canonical promotion may be reconsidered only if a future proposal identifies an
irreducible, independently citable epistemic event that:

1. cannot be losslessly regenerated from existing canonical objects and
ratified Findings;
2. must survive changes to comparison implementations;
3. requires witnessing, stewardship, or supersession in its own right; and
4. cannot be represented as an Interpretation, Finding, Dialogue, or existing
relation.

---

## Required Projection Semantics

An eventual implementation must distinguish three domains.

### 1. Interpretive divergence

Compares canonical Interpretations under distinct Perspectives.

Permitted sections include:

- Shared Interpretations or aligned claims;
- Perspective-A-only Interpretations;
- Perspective-B-only Interpretations;
- shared and distinct Observation support;
- evidential-status differences; and
- canonical contradictions.

### 2. Expressive divergence

Compares RenderedNarratives produced under different ExpressionProfiles,
providers, or languages while holding the underlying contract or
Interpretations stable.

Permitted sections include:

- differences in emphasis;
- ordering;
- register;
- metaphor;
- language;
- accessibility; and
- contract-preservation Findings.

Expressive divergence must not be labeled interpretive divergence merely
because the prose differs.

### 3. Analytical inference

Explanations such as:

- "different cultural priors were invoked";
- "different metaphor systems were activated"; or
- "the same Observation was interpreted differently"

must identify their basis.

The projection must distinguish:

- directly computed facts;
- ratified Findings;
- machine-proposed explanations; and
- steward-authored conclusions.

Machine-proposed explanations have no canonical standing merely because they
appear in the projection.

---

## Score Policy

An Interpretive Distance score may be displayed only as non-authoritative
analytical metadata.

The score must:

- disclose its formula and version;
- expose its constituent counts;
- remain reproducible from the same inputs;
- never rank Perspective quality or truth;
- never determine canonical identity, stewardship status, or suppression; and
- be labeled `not_computed` when required inputs are absent.

The score is a Projection value or Disposable Derived value, not a canonical
field and not a Finding.

Initial visibility should prefer explicit counts and sets:

```text
Shared
Distinct to A
Distinct to B
Contradictory
Evidence overlap
```

over a single compressed number.

---

## Claim Alignment Constraint

Exact identity and explicit canonical relations should be used before semantic
inference.

An initial alignment hierarchy should be:

1. identical Interpretation IDs;
2. explicit canonical relation or shared supersession ancestry;
3. deterministic exact or normalized content match as disposable derivation;
4. ratified deterministic comparison rule;
5. machine-proposed semantic alignment, clearly labeled non-canonical; and
6. steward-confirmed alignment, represented through an already authorized
human-contribution mechanism or future authority.

This ADR does not authorize storing extracted narrative claims as new canonical
objects. ADR-0011 remains controlling: a meaning-bearing claim belongs in
Interpretation.

---

## Consequences

### Positive

- Hermeneia can expose convergence and divergence without expanding ontology.
- Users can inspect what stayed the same, what changed, and why the system
believes it changed.
- Tiny divergence remains a visible result rather than a product failure.
- Interpretive and expressive variation remain constitutionally distinct.
- Future Evaluation Functions can be added one bounded dimension at a time.
- The initial capability can evolve without canonical migrations.

### Negative

- A Projection cannot preserve a historical comparison run as epistemic
history.
- Semantic alignment quality may initially be limited.
- Cultural-prior and metaphor attribution cannot be treated as fact without
additional authority.
- A single distance score cannot carry the full meaning of divergence.
- Comparing ExpressionProfiles alone may reveal expression differences while
showing no interpretive divergence.

---

## Alternatives Rejected

### Canonical object from the outset

Rejected because the proposed output is currently regenerable and aggregate.
No irreducible epistemic object has been demonstrated.

### Aggregate Evaluation Function

Rejected because the report crosses multiple dimensions and includes a
presentation score. Evaluation Functions are orthogonal computations whose
durable outputs are Findings, not multidimensional dashboards.

### Derived artifact as the complete classification

Rejected because derived artifacts describe computational support, not the
human-facing inspection surface. Derived metadata may support the Projection.

### Claim extraction from RenderedNarrative as a new canonical layer

Rejected because Claim is already Interpretation. Extracted narrative claims
may be temporary analytical data or future Findings, but they may not silently
become a parallel claim ontology.

---

## Constitutional Alignment

- **Constitution Article VII:** Perspective and Interpretation retain their
distinct epistemic classes.
- **Constitution Article VIII:** No new pipeline stage is inserted.
- **CA-0002:** Frame, Claim, Constraint, Expression, and Evaluation remain
distinct.
- **CI-016:** Regenerable comparison metadata remains disposable.
- **ADR-0011:** Claim remains represented by Interpretation.
- **ADR-0015:** Perspective-grounded Interpretations are the proper inputs to
interpretive comparison.
- **ADR-0037 and ADR-0038:** Expressive variation is evaluated separately from
semantic change.
- **ADR-0041 and ADR-0042:** Evaluation Functions remain orthogonal and produce
Findings; aggregate views remain projections.

---

## Implementation Gate

This DRAFT ADR authorizes no implementation.

Before implementation, ratification must resolve:

1. whether the first release compares Interpretations, RenderedNarratives, or
both in explicitly separate modes;
2. the minimum deterministic alignment rules;
3. whether machine-proposed semantic alignment is permitted;
4. how proposed explanations are attributed and reviewed;
5. the exact non-authoritative score formula, if any;
6. whether any new comparative Evaluation Function is authorized; and
7. which existing human-contribution mechanism records steward-confirmed
alignment or causal explanation.

