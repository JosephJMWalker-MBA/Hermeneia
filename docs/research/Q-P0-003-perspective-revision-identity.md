# Q-P0-003 Amendment Brief: Perspective Revision Identity

**Status:** Research / ADR Proposal Support
**Date:** 2026-08-22
**Related authority:** ADR-0015, ADR-0021, ADR-0024, CA-0002, CA-0004
**Related issues:** #156, #157, #158, #159

---

## Question

How should Hermeneia reconcile ADR-0015's durable Perspective identity model
with richer user-authored Perspective definitions introduced by recent
Perspective Run and Perspective Builder work?

This brief does not reopen the ratified distinction between Interpretation and
Perspective. It surveys a narrower conflict: whether a durable Perspective's
identity should remain effectively label-derived when the executable frame now
has explicit semantic fields.

---

## Existing Authority

ADR-0015 establishes:

- Perspective is the interpretive frame.
- Interpretation is a claim or readout produced within one Perspective.
- Perspective is canonical, permanent, append-only, named, human-declared, and
  global.
- Perspective is distinct from provider/model execution.
- Interpretation references exactly one Perspective.
- Perspective refinement is additive, not deletion.

CA-0002 classifies Perspective as a Frame and Interpretation as a Claim. It
also prohibits collapsing Perspective, expression constraints, synthesis,
contracts, and evaluation into claims.

CA-0004 requires nondeterministic outputs to preserve complete execution inputs
and requires monotonic governance: new objects and relations are appended rather
than mutating prior objects.

docs/15_Storage.md requires append-only evidence and lineage discipline. It
also names Perspective as part of the required lineage from RenderedNarrative
back to SourceDocument.

---

## Current Implementation

The current canonical Perspective registry remains label-centered:

- `hermeneia/ontology/perspective.py` documents the current ID as
  `sha256(lower(name))`.
- `hermeneia/storage/sqlite.py` stores `perspectives(id, name, description,
  created_at)`, with `name` unique.
- `register_perspective()` uses `INSERT OR IGNORE`; the same name converges to
  the same registry row.
- `tests/test_perspective.py` asserts case-insensitive, whitespace-stripped
  label identity.

Recent Perspective Run work adds a richer transient execution frame:

- `label`
- `purpose`
- `questions[]`
- `challenges[]`
- `limitations[]`

`hermeneia/perspective_runs.py` fingerprints those frame semantics with stable
canonical JSON and SHA-256. The fingerprint deliberately excludes:

- Scope
- Question
- provider
- model
- inference configuration
- audience
- tone
- voice
- language
- style

This is currently transient execution metadata, not durable canonical storage.

---

## Collision

The user-facing command "Save this Perspective" now has two plausible
meanings:

1. Save a named label, compatible with ADR-0015's original label-derived
   registry.
2. Save an exact rich interpretive frame definition, compatible with #171's
   executable frame semantics and #158's need to analyze Perspective versions
   without contaminating model/configuration identity.

Those meanings collide when the same label carries changed semantic content.

Example:

```text
Institutional Trust Reader
purpose: Examine how institutions gain legitimacy.
questions: Who is expected to trust whom?
challenges: Challenge borrowed authority.
limitations: May overemphasize institutions.
```

Later:

```text
Institutional Trust Reader
purpose: Examine how institutions gain, borrow, or lose legitimacy.
questions: Who is expected to trust whom?
questions: What institution is missing from the scene?
challenges: Challenge borrowed authority.
limitations: May underread personal trust.
```

The label is intentionally the same human concept, but the executable frame is
not identical. If historical runs and future Model Observatory analysis only
know the label-derived Perspective ID, they cannot determine which frame
actually governed the run.

---

## Candidate A: Keep Label-Derived Identity

Under this model, Perspective identity remains derived only from normalized
canonical label. Any semantic refinement requires a new label.

Example:

```text
Institutional Trust Reader
Institutional Trust Reader v2
Institutional Trust Reader revised
```

### Benefits

- Preserves the existing implementation and tests.
- Preserves old ADR-0015 wording most directly.
- Keeps uniqueness simple.

### Problems

- Forces labels to carry too much ontological identity.
- Encourages artificial labels where the human-facing concept did not really
  change.
- Makes exact historical frame reconstruction depend on prose conventions.
- Makes #158-style performance analysis fragile because "Perspective version"
  is not a durable semantic identity.
- Does not align with #171's exact frame fingerprint.

### Constitutional Assessment

Constitutionally viable for the old implementation, but insufficient for
auditable rich-frame use. It preserves append-only storage by pushing semantic
change into labels, which is a weak identity boundary.

---

## Candidate B: Stable Perspective ID With Mutable Versions Underneath

Under this model, one durable Perspective keeps a stable ID and carries mutable
or versioned definition rows underneath it.

Example:

```text
perspective_id = institutional-trust-reader
definition_version = 1
definition_version = 2
```

### Benefits

- Matches common product language: one Perspective with revisions.
- Lets the UI show a simple library object.
- Avoids label proliferation.

### Problems

- Risks making the canonical Perspective a mutable conceptual container rather
  than one exact frame.
- Historical runs can become ambiguous if a run cites only the parent
  Perspective ID.
- Encourages `current_version_id`, `active_revision`, or `latest_version`
  fields that can drift toward in-place mutation.
- Requires careful additional identity to avoid treating all revisions as the
  same analytic object in #158.

### Constitutional Assessment

Risky. It can be made append-only with separate immutable definition rows, but
then the actual governing frame is the definition identity, not the parent
label container. Creating a second canonical object merely to solve library UX
would require additional authority.

---

## Candidate C: Each Durable Semantic Revision Is a Perspective

Under this model, a durable Perspective is one exact immutable interpretive
frame definition. Semantic identity is content-derived from normalized frame
semantics. Revision lineage is represented by append-only SupersessionRelation
edges between Perspective objects.

Example:

```text
P1 = Institutional Trust Reader, frame hash A
P2 = Institutional Trust Reader, frame hash B

SupersessionRelation(P1 -> P2)
```

### Benefits

- Preserves append-only history.
- Preserves exact historical execution identity.
- Aligns with #171's transient semantic fingerprint.
- Keeps provider/model/configuration outside Perspective identity.
- Supports #158 analysis by exact Perspective revision identity.
- Allows the same human-facing label across revisions without erasing the
  former frame.
- Uses the existing constitutional SupersessionRelation concept instead of
  inventing mutable "current" fields.

### Problems

- Partially supersedes ADR-0015's uniqueness rule for canonical labels.
- Requires explicit legacy compatibility because existing label-derived IDs
  remain valid forever.
- UI must explain that "revision" is human-facing language while each saved
  revision is a distinct canonical Perspective.

### Constitutional Assessment

Preferred. This model best satisfies Article III, CA-0004 monotonic governance,
and #158's need for exact run identity. It modifies only the identity and
revision mechanics of ADR-0015; it preserves the core Interpretation/Perspective
distinction.

---

## Preferred Identity Model

For newly saved rich Perspectives after ratification and implementation:

```text
semantic_definition = {
  label,
  purpose,
  questions[],
  challenges[],
  limitations[]
}

definition_fingerprint = sha256(canonical_json(semantic_definition))
perspective_id = deterministic id derived from identity scheme + fingerprint
```

The canonical JSON encoding should use stable field order or sorted keys,
stable separators, UTF-8 bytes, and the same normalized semantic fields already
used by the transient Perspective Builder wherever possible.

The ID model should distinguish:

- canonical object ID: the authoritative object identity used in lineage;
- definition fingerprint: content identity for exact frame semantics;
- display label: human-facing name, not unique by itself;
- lineage/display ordinal: optional UI projection such as `v2`, never
  authoritative identity.

---

## Legacy Compatibility

Existing Perspectives keep their existing IDs and semantics:

```text
identity_scheme = perspective-label-v1
```

New rich saved Perspectives should use a new scheme after ratification:

```text
identity_scheme = perspective-frame-v2
```

The exact names may change during implementation, but the compatibility
boundary must be explicit.

No migration may:

- rewrite existing Perspective IDs;
- rewrite historical Interpretation references;
- rewrite SupersessionRelation endpoints;
- rewrite existing `.herm` bundles;
- delete or update legacy canonical Perspective rows.

Legacy label-derived records remain executable and inspectable under their
original authority. Rich v2 records add exact frame identity for future use.

---

## Revision Semantics

The proposed revision flow is:

```text
Save transient draft
-> create immutable Perspective A

Edit A
-> produce transient edited draft

Explicit Save new revision
-> create immutable Perspective B
-> append SupersessionRelation A -> B
```

Never:

```sql
UPDATE perspectives SET ...
```

Historical A remains inspectable and executable by exact identity where the
runtime supports it. B does not erase A. "Current" is a projection over the
supersession graph.

---

## Branching

Ordinary "Revise Perspective" should target a current leaf of a lineage. If the
selected parent is already superseded, the implementation should reject the
ordinary revision or require explicit acknowledgement.

Intentional divergent refinement may later be represented as an explicit fork
or new Perspective lineage:

```text
P1
|-- P2
`-- P3
```

This brief does not propose a fork system. It only requires future
implementation to surface branching rather than silently choosing one leaf.

---

## Built-In Perspective Definitions

The built-in code-defined frames:

- `close-reader`
- `contextual-reader`
- `skeptical-reader`

are implementation-provided execution frames. They should not automatically
become canonical database Perspectives merely because they exist in code.

A future human adoption path may allow a steward to save/adopt a built-in
definition as a canonical Perspective. That action would be human declaration.

---

## Dependency-Graph Assessment

This refinement does not invalidate downstream decisions that depend on
Q-P0-003 because it preserves the fundamental distinction:

```text
Perspective = Frame
Interpretation = Claim/readout under one frame
```

It refines the identity mechanics of the Frame object. It does not change:

- whether Perspective is canonical;
- whether Interpretation references Perspective;
- whether Perspective is global;
- whether multi-Perspective Interpretation requires synthetic Perspective
  handling under ADR-0021;
- whether Perspective Debt measures missing or accumulated frames.

The affected implementation work is future additive storage/runtime work, not
an immediate change to already-landed transient Perspective Runs.
