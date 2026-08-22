# ADR-0045: Perspective Definition Revisions

**Status:** PROPOSED
**Version:** 0.1
**Date:** 2026-08-22
**Supersedes:** ADR-0015 in part, IF RATIFIED
**Related question:** Q-P0-003
**Related issues:** #156, #157, #158, #159

---

## Context

ADR-0015 ratified the formal distinction between Perspective and
Interpretation. That distinction remains correct:

```text
Perspective     = interpretive frame
Interpretation  = claim/readout produced within a frame
```

Recent product work added local-first Perspective Runs, Ask the Room, explicit
Scope, and a transient Perspective Builder. The transient Builder now defines
an executable frame with richer semantics:

- label
- purpose
- questions
- challenges
- limitations

It also produces a deterministic semantic fingerprint over exactly those frame
semantics while excluding Scope, Question, provider, model, configuration,
audience, tone, language, voice, style, and response text.

The user now needs to save and later revise such a frame. ADR-0015's older
identity model ties Perspective identity to `canonical_label` and requires
canonical labels to be unique. That is too narrow for exact rich-frame
revision identity.

This ADR proposes a narrow amendment. It does not reopen whether Perspective is
a canonical object or whether Interpretation is distinct from Perspective.

---

## Existing Authority Preserved

This ADR preserves the following ADR-0015 conclusions:

- Perspective is the declared interpretive frame.
- Interpretation is the propositional claim/readout produced within a frame.
- One Perspective may produce many Interpretations.
- One Interpretation references exactly one Perspective.
- Perspective is canonical.
- Perspective is human-declared.
- Perspective is permanent and append-only.
- Perspective is global rather than tied to one Observation.
- Perspective is distinct from provider/model execution.
- Perspective is distinct from ExpressionProfile and style constraints.
- AI may propose a Perspective, but steward acceptance/declaration is required
  before it becomes canonical.
- Interpretations generated under a historical Perspective remain traceable to
  that exact Perspective.

---

## Conflict Being Resolved

ADR-0015 also states:

- no two Perspectives may share the same `canonical_label`;
- Perspective ID is a deterministic hash of `canonical_label`;
- a refined Perspective is represented as another Perspective but the old
  schema expresses supersession with `superseded_by` and `active` fields.

Those rules are insufficient once a Perspective's executable semantic
definition is richer than a label.

The narrow conflict is:

```text
old identity ~= normalized label
new execution identity = exact frame semantics
```

This ADR proposes that newly saved rich Perspectives use exact frame semantics
as durable identity while preserving all legacy label-derived Perspective
records.

---

## Decision Drivers

- Exact historical auditability: a run must identify the exact frame used.
- Append-only governance: semantic revision must append rather than mutate.
- Human-facing continuity: a steward may refine "Institutional Trust Reader"
  without inventing artificial labels.
- Model separation: provider, model, and inference configuration must remain
  outside Perspective identity.
- Expression separation: audience, tone, voice, language, and style must remain
  outside Perspective identity.
- Legacy compatibility: existing Perspective IDs and Interpretation references
  remain valid forever.
- Model Observatory compatibility: performance analysis must be able to
  separate Perspective revision identity from model/configuration identity.

---

## Options Considered

### Option A: Keep Label-Derived Identity

Any semantic refinement requires a new canonical label.

This preserves the existing implementation but makes the label carry too much
ontological identity. It also makes historical frame reconstruction dependent
on naming conventions.

### Option B: Stable ID With Mutable Definition Versions

One Perspective keeps a stable ID while versions mutate or accumulate beneath
it.

This is convenient for a library UI, but it risks making the canonical
Perspective a mutable container. Historical runs become ambiguous unless every
run also records an exact definition identity. At that point the exact
definition identity is the real governing identity.

### Option C: Each Durable Semantic Revision Is a Perspective

Each saved rich frame revision is a distinct immutable canonical Perspective.
Semantic identity is content-derived. Revision lineage is append-only through
SupersessionRelation.

This is the proposed decision.

---

## Proposed Decision

A durable Perspective is one exact immutable interpretive frame definition.

Human-facing language may describe a saved successor as a "revision" of an
earlier Perspective. Ontologically, each durable revision is itself a
Perspective.

Do not introduce a second canonical ontology object named `PerspectiveProfile`,
`SavedPerspective`, or `PerspectiveRevision` merely to support the UX.

---

## Formal Definition

For newly saved rich Perspectives after ratification and implementation, the
semantic definition of a Perspective is:

```text
label
purpose
questions[]
challenges[]
limitations[]
```

These fields define the declared interpretive frame: from where the material is
being examined, what the frame tends to ask, what it challenges, and what limits
the steward acknowledges.

Canonical storage may include additional required provenance/identity fields
such as creator, declared timestamp, identity scheme, and lineage metadata.
Those fields do not replace semantic frame identity.

---

## Field-Level Semantics

### Included In Semantic Identity

| Field | Meaning |
|---|---|
| `label` | Human-facing name of the declared standpoint. |
| `purpose` | What the frame is for and what it attends to. |
| `questions[]` | Questions the frame tends to ask of material. |
| `challenges[]` | Assumptions, overclaims, or habits the frame resists. |
| `limitations[]` | Known limits or risks of the frame. |

### Excluded From Semantic Identity

The following are not Perspective semantics:

- Scope
- Question
- provider
- model
- model version
- inference configuration
- temperature
- audience
- output language
- tone
- voice
- style
- rhetorical constraints
- response or output text

These may appear in execution receipts, Scope receipts, ExpressionProfiles, or
other authorized records. They must not be baked into Perspective identity.

---

## Identity Rules

The proposed rich identity scheme is:

```text
semantic_definition = {
  "label": ...,
  "purpose": ...,
  "questions": [...],
  "challenges": [...],
  "limitations": [...]
}

definition_fingerprint = sha256(canonical_json(semantic_definition))
perspective_id = deterministic_id(identity_scheme, definition_fingerprint)
```

The exact prefix and ID string format are implementation details, but they must
be deterministic and must distinguish the rich-frame scheme from legacy
label-derived identity.

The system must distinguish:

- `perspective_id`: authoritative canonical object ID;
- `definition_fingerprint`: exact semantic frame content hash;
- `display_label`: human-facing label;
- lineage/display ordinal: optional UI projection such as `v2`.

The ordinal is never sufficient identity.

---

## Normalization And Serialization Rules

The canonical definition serialization should reuse the transient Perspective
Builder's semantics wherever possible:

- normalize fields according to the existing builder rules;
- include only frame semantic fields;
- encode canonical JSON with stable separators and deterministic key ordering;
- encode bytes as UTF-8;
- compute SHA-256 over those bytes.

If a transient frame is saved without semantic change, its transient
definition fingerprint should equal the saved canonical definition fingerprint.

Saving the same normalized rich frame twice converges to the same canonical
Perspective identity. Saving a semantically changed frame creates a different
Perspective identity.

---

## Human Declaration Boundary

Models may propose a Perspective draft.

Companion may help formulate a Perspective draft.

Explorer or future agents may suggest a Perspective draft.

Only explicit human action may declare and save a canonical Perspective.

Saving a Perspective is an act of human declaration. A model-generated draft
must not silently become canonical.

---

## Revision And Supersession Rules

The revision flow is:

```text
Save transient draft
-> create immutable Perspective A

Edit A
-> produce transient edited draft

Explicit Save new revision
-> create immutable Perspective B
-> append SupersessionRelation A -> B
```

The system must not mutate Perspective A.

The system must not store `current_version_id`, `active_revision`, or
`latest_version` as mutable authority on Perspective A merely to support a UI.

"Current" is a projection over the append-only supersession graph:

```text
P1 -> P2 -> P3
```

In that lineage, P3 is the current leaf for ordinary UI purposes. P1 and P2
remain inspectable and executable by exact identity where allowed.

---

## Same-Label Revisions

The same display label may appear on multiple rich-frame Perspectives if the
semantic definitions differ.

Example:

```text
Institutional Trust Reader, frame A
Institutional Trust Reader, frame B
```

This partially supersedes ADR-0015's rule that no two Perspectives may share a
canonical label, but only for the new rich-frame identity scheme. Legacy
label-derived records retain their original uniqueness behavior.

The label remains part of semantic identity. Changing only the label changes
the frame fingerprint and therefore creates a new Perspective object.

Tradeoff: this treats a rename as semantic revision rather than mutable display
metadata. The choice favors auditability over convenience because labels such
as "Close Reader", "Young Reader", and "Institutional Trust Reader" communicate
the standpoint being declared.

---

## Branching Rule

Ordinary "Revise Perspective" should target a current leaf of a lineage.

If the user attempts ordinary revision from a non-leaf historical Perspective,
the implementation should reject the action or surface that it would create a
branch.

Intentional divergent refinement may be supported later as an explicit fork or
new lineage operation:

```text
P1
|-- P2
`-- P3
```

This ADR does not design a fork UI. It requires that branching never be hidden
or silently collapsed.

---

## Legacy Identity Compatibility

Existing canonical Perspective records remain valid forever.

Conceptual identity schemes:

```text
perspective-label-v1
perspective-frame-v2
```

Implementation may choose exact names, but it must preserve the distinction.

Legacy records keep:

- existing IDs;
- existing Interpretation references;
- existing SupersessionRelation endpoints;
- existing `.herm` bundle meaning.

No migration may use UPDATE or DELETE to rewrite old canonical Perspective
objects or historical Interpretation references.

New rich Perspective persistence, once implemented, should be additive.

---

## Built-In Frame Treatment

Code-defined built-in PerspectiveDefinitions such as:

- `close-reader`
- `contextual-reader`
- `skeptical-reader`

are implementation-provided execution frames.

They are not automatically canonical database Perspectives merely because they
exist in code.

A future explicit human adoption path may save/adopt one of these definitions
as a canonical Perspective. That adoption must be recorded as human declaration
and must follow this ADR's identity and lineage rules.

---

## Inclusion Criteria

A saved object qualifies as a rich canonical Perspective when:

- a human explicitly declares/saves it;
- it contains the required semantic frame fields;
- it excludes execution and expression controls from semantic identity;
- it receives deterministic identity from the normalized semantic frame;
- it preserves creator/declaration provenance required by storage authority;
- any revision relationship is appended as SupersessionRelation.

---

## Exclusion Criteria

The following are not canonical Perspective definitions:

- a transient draft that has not been saved by a human;
- a model response or proposed reading;
- an execution configuration;
- a model/provider assignment;
- an ExpressionProfile;
- a Scope receipt;
- a Question;
- a UI label without frame semantics;
- a style, language, tone, or audience preference.

---

## Examples

### Example 1: Save A Transient Draft

The user authors:

```text
label: Institutional Trust Reader
purpose: Examine how institutions gain, borrow, or lose legitimacy.
questions:
  - Who is expected to trust whom?
challenges:
  - Challenge unsupported legitimacy claims.
limitations:
  - May overemphasize institutions.
```

The user clicks Save Perspective.

Hermeneia creates immutable Perspective P1 with a deterministic rich-frame ID
and definition fingerprint.

### Example 2: Save A New Revision

The user edits P1's limitations:

```text
limitations:
  - May overemphasize institutions.
  - May underread private forms of trust.
```

The user explicitly saves a new revision.

Hermeneia creates Perspective P2 and appends:

```text
SupersessionRelation(P1, P2, reason, ratified_at)
```

P1 is not updated.

### Example 3: Idempotent Duplicate Save

The user saves the exact same normalized rich frame twice.

Both saves resolve to the same canonical Perspective identity. No duplicate
semantic object is created.

### Example 4: Historical Revision Execution

P1 has been superseded by P2.

A historical run receipt that references P1 remains meaningful. The run used
P1's exact frame, not P2's successor frame.

### Example 5: Model Changed, Perspective Unchanged

The user runs the same Perspective with `qwen2.5:0.5b` and later with another
model.

The Perspective ID and definition fingerprint remain unchanged. The execution
receipt records the different provider/model/configuration identity.

---

## Counterexamples

### Counterexample 1: Edit In Place

```sql
UPDATE perspectives SET purpose = ...
```

Rejected. Canonical Perspective semantics are immutable.

### Counterexample 2: Model As Perspective Identity

```text
Close Reader with Qwen
Close Reader with Claude
```

Rejected as a Perspective identity distinction. Model identity belongs in
execution configuration and audit receipts.

### Counterexample 3: Tone In Perspective

```text
Close Reader, warm tone, written for teenagers
```

Rejected as Perspective semantics. Tone and audience belong to
ExpressionProfile or other authorized expression constraints.

### Counterexample 4: Silent AI Save

A model proposes a useful new frame and the system saves it automatically.

Rejected. Canonical Perspective declaration requires explicit human action.

---

## Edge Cases

### Rename

Changing only `label` changes semantic identity because label is part of the
declared standpoint. The rename creates a new Perspective and may be linked by
SupersessionRelation if the steward declares it as revision.

### Reordered Lists

The implementation must decide whether list order is semantically significant.
Until otherwise ratified, questions, challenges, and limitations should be
treated as ordered lists because ordering is part of how the steward expresses
the frame.

### Empty Optional Lists

`questions[]` must contain at least one item. `challenges[]` and
`limitations[]` may be empty if the implementation allows that state and the
human declaration boundary remains explicit.

### Branching

If two successors are declared from one parent, both edges remain visible. UI
must not pretend there is one current successor unless a projection rule is
explicitly selected.

---

## Migration Strategy

No destructive migration is authorized.

Future implementation should:

1. Preserve existing `perspective-label-v1` records exactly.
2. Add support for `perspective-frame-v2` records through additive schema or
   compatible storage.
3. Preserve old Interpretation references to old Perspective IDs.
4. Preserve export/restore of both identity schemes.
5. Preserve old `.herm` bundles as readable and meaningful.
6. Avoid UPDATE/DELETE of canonical Perspective rows, Interpretation
   references, SupersessionRelation rows, or forensic evidence.

If additive schema is required, it must be reviewed in a later implementation
PR. This ADR does not implement storage.

---

## Backwards Compatibility Analysis

### Existing Perspectives

Preserved. Their IDs and labels keep their original meaning.

### Existing Interpretations

Preserved. Historical `perspective_id` references remain valid.

### Existing SupersessionRelation Rows

Preserved. Endpoints remain exact object IDs.

### Existing Tests

Tests for legacy label identity remain valid for legacy identity. Future tests
must add rich-frame identity and same-label revision coverage without
rewriting the legacy contract.

### Existing Transient Perspective Runs

Preserved. The transient fingerprint becomes the natural input to a future save
path, but no runtime behavior changes in this ADR.

### Existing Built-In PerspectiveDefinitions

Preserved as implementation-provided execution frames. They are not seeded
into canonical storage by this ADR.

---

## Provenance Impact Assessment

This proposal strengthens provenance. A run or Interpretation that references
a rich Perspective can identify the exact immutable frame definition that
governed it.

The minimum durable provenance for model-backed Perspective execution should
include:

- `perspective_id`
- `definition_fingerprint`
- exact definition or a resolvable immutable definition reference
- Scope receipt
- Question
- provider/model/configuration execution identity

This ADR does not alter SourceDocument, SourceExtraction, Observation, or
forensic provenance semantics.

---

## Ontology Impact Assessment

This ADR does not add, remove, rename, split, or merge canonical ontology
objects.

Perspective remains the canonical object. "Revision" is human-facing language
for an append-only relationship between Perspective objects.

The ADR partially changes the field-level identity semantics of Perspective for
new rich-frame records only. It does not create `PerspectiveRevision` or any
other new canonical object.

---

## Dependency Impact

### ADR-0015

Partially superseded if ratified. See "Exact Partial Supersession Scope."

### ADR-0021

Preserved. Interpretation still references exactly one Perspective. Synthetic
Perspectives remain the mechanism for multi-frame readings.

### ADR-0024 / CA-0002

Preserved. Perspective remains a canonical Frame.

### #156

Supported. Perspective remains separate from Blueprint, ArchitectPlan,
ExpressionProfile, and provider/model execution.

### #157

Supported. Scope remains an operation boundary and receipt input, not
Perspective identity.

### #158

Supported. Model Observatory can condition metrics on exact Perspective
revision identity and exact model/configuration identity.

### #159

Supported. Connections/model configuration remains outside Perspective
semantics.

---

## Future Implementation Validation Rules

Future implementation should add tests proving:

- legacy label-derived Perspective IDs remain valid;
- rich-frame Perspectives derive identity from semantic frame fields;
- provider/model/configuration changes do not change Perspective identity;
- Scope/Question changes do not change Perspective identity;
- tone/audience/language/style are rejected as Perspective semantic fields;
- same normalized rich frame saves idempotently;
- same label with changed semantic definition creates a distinct Perspective;
- explicit revision appends SupersessionRelation and does not update the prior
  Perspective;
- historical revisions remain inspectable and executable by exact identity
  where allowed;
- built-in PerspectiveDefinitions are not automatically canonical rows;
- export/restore preserves identity scheme and exact definition fingerprint.

---

## Consequences

### Positive

- Exact frame identity is auditable.
- Same-label revision becomes representable without artificial naming.
- Historical Perspective runs remain interpretable after later revision.
- Model Observatory analysis can distinguish Perspective revision effects from
  model/configuration effects.
- Append-only supersession becomes the governing revision mechanism.

### Negative

- The implementation must support two identity schemes.
- UI must explain that "v2" is a display projection, not identity.
- Searching by label may return multiple durable Perspectives.
- Rename becomes a new object rather than mutable label cleanup.

---

## Exact Partial Supersession Scope Of ADR-0015

If ratified, this ADR supersedes only these ADR-0015 rules for newly saved
rich-frame Perspectives:

- Perspective identity is only a deterministic hash of `canonical_label`.
- No two Perspectives may share the same `canonical_label`.
- Label uniqueness alone is sufficient to identify a durable Perspective.
- `superseded_by` and `active` fields on the old Perspective are the preferred
  revision mechanism.
- A mutable or label-only "Perspective + version" notion is sufficient for
  exact historical audit.

This ADR explicitly preserves ADR-0015's broader conclusions about the
Interpretation/Perspective distinction, human declaration, permanence,
append-only accumulation, global scope, and provider/model separation.

---

## Non-Goals

This ADR does not:

- implement durable Perspective storage;
- change SQLite schema;
- change Perspective Run runtime behavior;
- change the Reader Perspective Builder;
- change Ask the Room;
- add saved custom Room membership;
- add Perspective/model assignments;
- add Model Observatory analytics;
- ratify itself;
- edit ADR-0015;
- update the Authority Index supersession register before ratification.
