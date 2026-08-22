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

Under this model, a durable Perspective is one exact immutable
human-declared revision occurrence. The semantic fingerprint is
content-derived from normalized frame semantics, but it is not the canonical
object identity by itself. Revision lineage is represented by append-only
SupersessionRelation edges between Perspective objects.

Example:

```text
P1 = Institutional Trust Reader, frame hash A
P2 = Institutional Trust Reader, frame hash B

SupersessionRelation(P1 -> P2)
```

### Benefits

- Preserves append-only history.
- Preserves exact historical execution identity and declaration occurrence
  identity.
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
```

`definition_fingerprint` is exact semantic-content identity for the normalized
frame. It remains compatible with the transient #171 fingerprint.

`perspective_id` identifies one immutable human-declared Perspective
occurrence/revision. It is deterministic, but it is not only the semantic
fingerprint.

Conceptually:

```text
root perspective_id =
  H(identity_scheme, definition_fingerprint, declared_by, ROOT)

revision perspective_id =
  H(identity_scheme, predecessor_perspective_id, definition_fingerprint, declared_by)
```

`declared_date` remains required provenance, but it must not participate in
object identity. A retry of the same declaration operation should remain
idempotent.

The canonical JSON encoding is:

```python
json.dumps(
    semantic_definition,
    sort_keys=True,
    ensure_ascii=True,
    separators=(",", ":"),
)
```

The JSON string is UTF-8 encoded and hashed with SHA-256. The durable
fingerprint representation is `sha256:<lowercase-hex>`, matching #171.

No Unicode normalization such as NFC or NFKC is applied in frame-v2 because
#171 does not apply it. Compatibility with current transient fingerprints takes
precedence over introducing new normalization in this proposed amendment.

Frame-v2 normalization:

- semantic keys are exactly `label`, `purpose`, `questions`, `challenges`, and
  `limitations`;
- `label` and `purpose` trim leading/trailing whitespace, preserve case, and
  preserve internal whitespace;
- list items trim leading/trailing whitespace;
- empty list items are discarded;
- duplicate non-empty list items are preserved;
- list order is semantically significant;
- `questions` requires at least one item;
- `challenges` and `limitations` may be empty.

The ID model should distinguish:

- canonical object ID: the authoritative declared-object identity used in
  lineage;
- definition fingerprint: semantic equivalence identity for exact frame
  content;
- display label: human-facing name, not unique by itself;
- lineage/display ordinal: optional UI projection such as `v2`, never
  authoritative identity.

Idempotency is bounded:

```text
same normalized definition
+ same declaration context
-> same Perspective object
```

Identical semantic frames declared in different contexts need not collapse to
one canonical object. Their semantic equivalence is represented by equal
`definition_fingerprint`.

Reversion must not reuse ancestor IDs:

```text
P1 = frame A / fingerprint X
P2 = frame B / fingerprint Y
P3 = frame A / fingerprint X

P1 -> P2 -> P3
```

P3 has the same `definition_fingerprint` as P1, but a different
`perspective_id`, because P3 is a later declaration/revision occurrence. This
prevents cycle-producing reuse such as `P1 -> P2 -> P1`.

Two stewards may declare semantically identical root Perspectives without
creating the same canonical Perspective object if their declaration contexts
differ. Equal fingerprints mark semantic equivalence; they do not erase
declaration provenance.

---

## ADR-0015 Field Mapping

| ADR-0015 field | rich-frame v2 rule |
|---|---|
| `id` | New declared-object identity: root uses identity scheme, definition fingerprint, `declared_by`, and root marker; revision uses identity scheme, predecessor Perspective ID, definition fingerprint, and `declared_by`. |
| `canonical_label` | Becomes `label`; no longer unique by itself under frame-v2. |
| `tradition` | Legacy-only/deferred for rich v2. It is not in #171 and is not part of the v2 fingerprint. Future support requires an explicit append-only mechanism. |
| `description` | `purpose` is the v2 semantic successor. |
| `declared_by` | Required, immutable declaration provenance. |
| `declared_date` | Required, immutable declaration provenance; excluded from object identity for retry idempotency. |
| `superseded_by` | Replaced by append-only SupersessionRelation edges. |
| `active` | Replaced by graph-derived projection over SupersessionRelation leaves. |

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
- re-identify a legacy Perspective under frame-v2.

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

For Perspective revision, a future operation must validate:

- `old_id` is a Perspective;
- `new_id` is a Perspective;
- `old_id != new_id`;
- adding the edge cannot create a cycle;
- ordinary revision starts from a current leaf;
- hidden branching is prohibited.

`ratified_at` on the generic SupersessionRelation is truthful for this use:
the explicit human "Save new revision" action is the steward's declaration of
the successor Perspective and the supersession edge.

---

## Additional Counterexamples

The preferred model rejects:

- using a display ordinal such as `v2` as durable identity;
- changing Scope and calling it a Perspective revision;
- changing the user Question and calling it a Perspective revision;
- re-identifying a legacy Perspective under frame-v2;
- automatically canonicalizing built-in PerspectiveDefinitions;
- collapsing distinct human declarations solely because their frame
  fingerprints match;
- reusing an ancestor Perspective ID to represent a later reversion;
- creating a Perspective supersession cycle.

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
