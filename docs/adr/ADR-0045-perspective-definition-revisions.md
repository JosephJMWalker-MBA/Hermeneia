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

The narrow conflict is a three-way identity distinction:

```text
legacy object identity
= normalized canonical label

frame-v2 semantic identity
= exact normalized frame semantics
= definition_fingerprint

frame-v2 canonical object identity
= immutable human-declared Perspective node
= perspective_id
```

`definition_fingerprint` identifies what the frame means.

`perspective_id` identifies this declaration/revision occurrence in history.

This ADR does not use "execution identity" for Perspective fingerprints.
Execution identity belongs to provider, model, version/snapshot, and inference
configuration.

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

A durable Perspective is one exact immutable human-declared revision
occurrence carrying one exact immutable interpretive frame definition.

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

`declared_by` and `declared_date` remain required immutable declaration
provenance. Canonical storage may include additional identity-scheme and
lineage metadata. Those fields do not replace semantic frame identity.

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

The proposed rich semantic fingerprint is:

```text
semantic_definition = {
  "label": ...,
  "purpose": ...,
  "questions": [...],
  "challenges": [...],
  "limitations": [...]
}

definition_fingerprint = sha256(canonical_json(semantic_definition))
```

`definition_fingerprint` is exact semantic-content identity. It is not the
canonical object identity by itself.

`perspective_id` identifies one immutable human-declared Perspective
occurrence/revision. The preferred conceptual deterministic identity is:

```text
root perspective_id =
  H(identity_scheme, definition_fingerprint, declared_by, ROOT)

revision perspective_id =
  H(identity_scheme, predecessor_perspective_id, definition_fingerprint, declared_by)
```

The exact prefix, hash function label, and string representation remain
implementation details, but the identity must be deterministic and must
distinguish frame-v2 from legacy label-derived identity.

`declared_date` must not participate in `perspective_id`; retries of the same
declaration operation should remain idempotent.

The system must distinguish:

- `perspective_id`: authoritative canonical object ID;
- `definition_fingerprint`: exact semantic frame content hash;
- `display_label`: human-facing label;
- lineage/display ordinal: optional UI projection such as `v2`.

The ordinal is never sufficient identity.

Idempotency is bounded:

```text
same normalized definition
+ same declaration context
-> same Perspective object
```

For frame-v2, declaration context is:

```text
root declaration context
= ROOT + declared_by

revision declaration context
= predecessor_perspective_id + declared_by
```

Together with `identity_scheme` and `definition_fingerprint`, this yields the
deterministic ID formulas above.

Intended consequences:

- same steward + same root frame -> idempotently converges;
- different steward + same root frame -> may be distinct declared Perspective
  nodes;
- same predecessor + same steward + same revised frame -> idempotently
  converges;
- later reversion after another revision -> different predecessor, therefore
  different Perspective ID.

Do not introduce a timestamp or random nonce merely to force object uniqueness.

Hermeneia must not claim that every identical semantic frame everywhere is the
same canonical Perspective object. Semantic equivalence across distinct
Perspective objects is represented by equal `definition_fingerprint`.

---

## Normalization And Serialization Rules

Frame-v2 canonicalization is fixed as follows.

Semantic keys are exactly:

```text
label
purpose
questions
challenges
limitations
```

`label` and `purpose`:

- trim leading/trailing whitespace;
- preserve case;
- preserve internal whitespace.

List fields:

- trim leading/trailing whitespace on each item;
- discard empty items;
- preserve duplicate non-empty items;
- preserve order.

`questions` must contain at least one item.

`challenges` and `limitations` may be empty.

List order is semantically significant under `perspective-frame-v2`.

The canonical serialization is equivalent to:

```python
json.dumps(
    semantic_definition,
    sort_keys=True,
    ensure_ascii=True,
    separators=(",", ":"),
)
```

The JSON string is UTF-8 encoded and hashed with SHA-256.

The durable fingerprint representation is:

```text
sha256:<lowercase-hex>
```

This matches the current transient #171 representation.

No Unicode normalization such as NFC or NFKC is applied in frame-v2. This is
intentional: preserving exact compatibility with #171 takes precedence over
introducing new normalization in this proposed amendment.

If a transient frame is saved without semantic change, its transient
definition fingerprint should equal the saved canonical definition fingerprint.

Saving the same normalized rich frame twice in the same declaration context
converges to the same canonical Perspective identity. Saving a semantically
changed frame creates a different `definition_fingerprint`. Saving an
identical semantic frame in a different declaration context may create a
different canonical Perspective object with the same `definition_fingerprint`.

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

For Perspective revision, a future operation must validate:

- `old_id` is a Perspective;
- `new_id` is a Perspective;
- `old_id != new_id`;
- adding the edge does not create a cycle;
- ordinary revision starts from a current leaf;
- hidden branching is prohibited.

The existing generic SupersessionRelation remains the relation. No
Perspective-specific canonical relation is introduced.

For this use, `ratified_at` means the timestamp of the explicit human "Save
new revision" action. That action is the steward's declaration of the successor
Perspective and of the supersession edge.

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

## Reversion Rule

Reverting to an earlier semantic frame creates a later Perspective occurrence.

Example:

```text
P1 = frame A / fingerprint X
P2 = frame B / fingerprint Y
P3 = frame A / fingerprint X

P1 -> P2 -> P3
```

P3 must have:

```text
P3.definition_fingerprint == P1.definition_fingerprint
P3.perspective_id != P1.perspective_id
```

P3 is a later declaration/revision occurrence. Reusing P1's Perspective ID
would produce a cycle-prone lineage such as:

```text
P1 -> P2 -> P1
```

That is prohibited.

---

## ADR-0015 Field Compatibility

| ADR-0015 field | rich-frame v2 rule |
|---|---|
| `id` | New declared-object identity. Root IDs derive from identity scheme, definition fingerprint, `declared_by`, and root marker. Revision IDs derive from identity scheme, predecessor Perspective ID, definition fingerprint, and `declared_by`. |
| `canonical_label` | Becomes `label`; no longer unique by itself under frame-v2. |
| `tradition` | Legacy-only/deferred for rich v2. It is not in #171 and is not part of the v2 fingerprint. Future support requires an explicit append-only mechanism. |
| `description` | `purpose` is the v2 semantic successor. |
| `declared_by` | Required and immutable. |
| `declared_date` | Required and immutable; excluded from object identity for retry idempotency. |
| `superseded_by` | Replaced by append-only SupersessionRelation edges. |
| `active` | Replaced by graph-derived projection over SupersessionRelation leaves. |

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
- it receives deterministic declared-object identity from the normalized
  semantic frame plus declaration context;
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

The user saves the exact same normalized rich frame twice in the same
declaration context.

Both saves resolve to the same canonical Perspective object identity. No
duplicate declared Perspective object is created.

### Example 4: Historical Revision Execution

P1 has been superseded by P2.

A historical run receipt that references P1 remains meaningful. The run used
P1's exact frame, not P2's successor frame.

### Example 5: Model Changed, Perspective Unchanged

The user runs the same Perspective with `qwen2.5:0.5b` and later with another
model.

The Perspective ID and definition fingerprint remain unchanged. The execution
receipt records the different provider/model/configuration identity.

### Example 6: Reversion Preserves Occurrence Identity

P1 uses frame A with fingerprint X. P2 revises it to frame B with fingerprint
Y. P3 later intentionally reverts to frame A, producing fingerprint X again.

P3 has the same `definition_fingerprint` as P1, but P3 has a different
`perspective_id` because it is a later declaration occurrence.

### Example 7: Multiple Declarers

Two stewards independently declare the same normalized root frame. The two
declarations may produce distinct Perspective objects if their declaration
contexts differ, while equal `definition_fingerprint` records semantic
equivalence.

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

### Counterexample 5: Ordinal As Identity

```text
Institutional Trust Reader v2
```

Rejected as sufficient identity. Display ordinals are projections over exact
Perspective IDs and supersession lineage.

### Counterexample 6: Scope As Revision

The same Perspective is run over a broader evidence Scope and the system calls
that a Perspective revision.

Rejected. Scope belongs to the operation boundary and receipt, not Perspective
semantic identity.

### Counterexample 7: Question As Revision

The same Perspective is run with a different user Question and the system calls
that a Perspective revision.

Rejected. Question belongs to the operation input, not Perspective semantic
identity.

### Counterexample 8: Re-Identifying Legacy Perspective

A legacy `perspective-label-v1` row is recomputed under `perspective-frame-v2`
and assigned a new canonical ID.

Rejected. Legacy Perspective identities remain valid and must not be rewritten
or re-identified.

### Counterexample 9: Automatic Built-In Canonicalization

The code-defined `close-reader` PerspectiveDefinition is automatically inserted
into canonical Perspective storage at startup.

Rejected. Built-ins are implementation-provided execution frames unless a
human explicitly adopts/saves one as canonical.

### Counterexample 10: Collapse Distinct Declarations By Fingerprint

Two different stewards declare the same semantic frame and Hermeneia erases
one declaration because the fingerprints match.

Rejected. Equal `definition_fingerprint` marks semantic equivalence; it does
not erase distinct declaration provenance.

### Counterexample 11: Reuse Ancestor ID For Reversion

```text
P1 -> P2 -> P1
```

Rejected. A later reversion to frame A must create a later Perspective
occurrence with a distinct `perspective_id`.

### Counterexample 12: Supersession Cycle

Any Perspective supersession edge that creates a cycle is rejected.

---

## Edge Cases

### Rename

Changing only `label` changes semantic identity because label is part of the
declared standpoint. The rename creates a new Perspective and may be linked by
SupersessionRelation if the steward declares it as revision.

### Reordered Lists

List order is semantically significant under `perspective-frame-v2`. Reordering
questions, challenges, or limitations changes the definition fingerprint.

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

Current implementation facts:

- `perspectives.name` is globally `UNIQUE`.
- `interpretations.perspective_id` references `perspectives(id)`.
- generic SupersessionRelation endpoint validation recognizes
  `perspectives(id)`.

Therefore same-label frame-v2 Perspectives cannot be implemented by simply
adding rich semantic columns to the current table while leaving global
`UNIQUE(name)` unchanged.

Future implementation should:

1. Preserve existing `perspective-label-v1` records exactly.
2. Allow multiple frame-v2 Perspectives to share a label.
3. Preserve legacy v1 name uniqueness behavior for legacy registrations.
4. Preserve old Interpretation references to old Perspective IDs.
5. Preserve export/restore of both identity schemes.
6. Preserve old `.herm` bundles as readable and meaningful.
7. Avoid semantic UPDATE/DELETE of canonical Perspective rows, Interpretation
   references, SupersessionRelation rows, or forensic evidence.
8. Never re-identify a legacy Perspective under frame-v2.
9. Ensure frame-v2 Perspective IDs participate in the same canonical
   Perspective namespace for Interpretation references and SupersessionRelation
   endpoint validation.

The next implementation PR must choose an explicit storage topology. Likely
implementation families include:

1. Transactional rebuild/evolution of the `perspectives` storage table,
   preserving every legacy row byte-for-field and replacing global name
   uniqueness with scheme-aware uniqueness.
2. Another compatible storage topology that still preserves one canonical
   Perspective namespace for foreign-key and supersession purposes.

This ADR does not select one of those families.

This ADR rules out a disconnected v2 table whose IDs cannot satisfy existing
Interpretation or SupersessionRelation canonical-reference semantics.

"No destructive migration" means no semantic rewriting, deletion, or
re-identification of historical objects. A transactional SQLite schema rebuild
that copies legacy logical rows unchanged is not automatically prohibited,
provided the implementation proves exact legacy identity/content preservation
before commit. This distinction matters because SQLite may require table
reconstruction to alter a UNIQUE constraint.

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
- rich-frame Perspective IDs also include declaration context;
- provider/model/configuration changes do not change Perspective identity;
- Scope/Question changes do not change Perspective identity;
- tone/audience/language/style are rejected as Perspective semantic fields;
- same normalized rich frame + same declaration context saves idempotently;
- identical semantic frames in distinct declaration contexts can remain
  distinct Perspective objects with equal fingerprints;
- same-label frame-v2 rows can coexist;
- legacy v1 label uniqueness remains enforced for v1 registrations;
- legacy Interpretation foreign-key targets remain unchanged;
- frame-v2 IDs are valid Perspective endpoints for SupersessionRelation;
- schema migration round-trip preserves all pre-migration Perspective rows
  exactly;
- same label with changed semantic definition creates a distinct Perspective;
- reversion creates a new Perspective occurrence with equal fingerprint and
  different ID from the ancestor;
- explicit revision appends SupersessionRelation and does not update the prior
  Perspective;
- Perspective supersession rejects non-Perspective endpoints, self-edges,
  cycles, hidden branches, and ordinary revisions from non-leaf nodes;
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

- `Perspective.id` as only a deterministic hash of `canonical_label`.
- `canonical_label` as globally unique for all Perspectives.
- `canonical_label` as the durable identity boundary.
- ADR-0015 Perspective schema field `canonical_label`, which becomes
  frame-v2 `label`.
- ADR-0015 required `description`, which becomes the frame-v2 semantic
  definition: `purpose`, `questions`, `challenges`, and `limitations`.
- ADR-0015 optional `tradition`, which is not carried into the initial
  frame-v2 semantics/storage contract and is deferred.
- ADR-0015 `superseded_by` pointer and `active` boolean, which become
  append-only SupersessionRelation plus graph-derived state for frame-v2.

### Clarified Previously Underspecified Behavior

ADR-0015 did not distinguish semantic equivalence from declaration occurrence
identity. ADR-0045 clarifies that distinction for frame-v2 with
`definition_fingerprint` and `perspective_id`.

ADR-0015 did not specify rich-frame canonicalization. ADR-0045 freezes the
frame-v2 normalization and serialization contract.

ADR-0015 did not define branching/cycle invariants for Perspective
SupersessionRelation usage. ADR-0045 specifies those future validation
requirements for frame-v2 revision operations.

### Preserved ADR-0015 Schema Requirements

This ADR explicitly preserves:

- `declared_by` remains REQUIRED.
- `declared_date` remains REQUIRED.
- Perspective permanence remains.
- Human declaration remains.
- Global Perspective scope remains.
- Interpretation -> exact Perspective reference remains.
- The broader Interpretation/Perspective distinction remains.
- Perspective remains separate from provider/model execution and
  ExpressionProfile constraints.

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
