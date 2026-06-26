# Hermeneia Preservation Layer Design

**Status:** Draft preservation baseline  
**Authority:** Non-authoritative proposal  
**Scope:** Preservation, export, verification, restore, and multi-copy storage of
Hermeneia corpora and adjacent build artifacts

## Purpose

The Preservation Layer protects against loss of an evolving investigation.

The risk is not merely losing a rendered document. The risk is losing the
lineage that makes later understanding intelligible:

- source evidence;
- exact extractions;
- observations;
- interpretations;
- perspectives;
- blueprints;
- architect plans;
- expression profiles;
- rendered narratives;
- critic and evaluation records;
- stewardship decisions;
- ratification records;
- compile recipes;
- coverage reports;
- release candidate history; and
- release decisions.

The preservation goal is reconstructability. A future steward should be able to
answer:

- What was preserved?
- What was generated?
- What was ratified?
- What was superseded?
- What warning remained?
- Why did the steward approve, reject, or defer?
- Which immutable ancestors support this result?

Hermeneia does not preserve understanding as a private mental state.
It preserves the evidence, lineage, rationale, and audit trail required for a
future steward to reconstruct how understanding evolved.

That distinction matters. A restored `.herm` archive does not make a later
reader inherit the original steward's mind. It gives that reader the notebooks,
experiments, drafts, revisions, criticisms, decisions, and limitations needed to
continue the investigation responsibly.

## Authority Boundary

This design does not ratify a new ontology object, pipeline stage, storage
format, table, API, or CLI command.

It is subordinate to:

1. [`00_Constitution.md`](00_Constitution.md);
2. [`01_Authority_Index.md`](01_Authority_Index.md);
3. ratified amendments in [`amendments/`](amendments/);
4. [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md);
5. active ADRs; and
6. active implementation specifications.

Before implementation, the storage and CLI implications in this document must
be ratified or incorporated into the appropriate active specifications.

## Baseline Position

This document is the preservation design baseline. It ratifies nothing.

The next ratification question is:

> Should original source bytes live inside `.herm`, or should source-byte
> preservation remain an explicit envelope obligation?

Until that question is answered, Hermeneia may promise Corpus-Complete and
Build-Complete preservation when those checks pass. It must not promise
Source-Complete preservation.

## Constitutional Basis

The Preservation Layer derives from existing authority:

- Article I: every object has permanently verifiable lineage to immutable
  ancestors.
- Article II: deterministic objects are reproducible; nondeterministic objects
  preserve full audit records.
- Article VI: generated objects without required provenance must fail.
- Article X: knowledge accumulates monotonically.
- Article XII: read operations have zero side effects.
- Article XIII: Hermeneia has one authoritative portable storage format.
- CI-005: immutable forensic and provenance rows reject mutation.
- CI-006: canonical objects require strict ancestry.
- CI-011: nondeterministic invocations require audit records.
- CI-012: inspection and verification must not mutate storage.
- CI-013: no competing authoritative bundle format is allowed.
- CI-014: supersession preserves historical artifacts.
- CI-016: derived artifacts are disposable and regenerable.

## Design Classification

The Preservation Layer is operational infrastructure over the active `.herm`
format.

It is not:

- a canonical object;
- an epistemic class;
- a pipeline stage;
- a Project object;
- a Workspace object;
- a replacement for Git;
- a cloud sync system;
- an alternate authoritative export format; or
- a database migration mechanism.

The active `.herm` corpus remains the only authoritative portable artifact.
Preservation sidecars and transport wrappers are verification aids, not sources
of epistemic authority.

## Layering Model

Preservation is infrastructure, not a cognitive responsibility.

It sits beside identity, lineage, provenance, and authority. It supports every
cognitive responsibility without becoming another stage in the constitutional
pipeline.

```text
Infrastructure
    Identity
    Lineage
    Provenance
    Preservation
    Authority

Cognitive Responsibilities
    Witness
    Explorer
    Architect
    Artist
    Critic
    Steward

Artifacts
    SourceDocuments
    SourceExtractions
    Observations
    Interpretations
    NarrativeBlueprints
    ArchitectPlans
    RenderedNarratives
    CriticReports
    RatificationRecords
```

The Preservation Layer must therefore remain orthogonal. It preserves and
verifies the corpus; it does not generate evidence, produce interpretations,
write narratives, evaluate claims, ratify decisions, or add a pipeline stage.

## Core Principle

```text
Preserve irreducible truth.
Verify copied bytes.
Regenerate disposable projections.
Never make a backup target authoritative.
```

The Preservation Layer should behave like a LOCKSS-style redundancy discipline:
many independent copies reduce loss, but no storage target gains authority over
the corpus.

The relevant LOCKSS preservation principle is decentralized custody: many
copies are useful only when no single participant, platform, organization, or
administrator controls all copies. Hermeneia adopts that posture as an
operational preservation discipline, not as a new source of architectural
authority. See the [LOCKSS Preservation Principles](https://www.lockss.org/about/preservation-principles).

## Candidate Future Invariant

The design principle:

```text
Never make a backup target authoritative.
```

may generalize into a future constitutional invariant:

```text
Authority derives from constitutional lineage, never from storage location.
```

This statement is not ratified here. It is recorded as a preservation-derived
candidate because it protects the same boundary across all storage media:

- SQLite;
- Git;
- S3-compatible object storage;
- GitHub Releases;
- cloud folders;
- external drives;
- institutional archives; and
- public preservation services.

The storage medium has no epistemic authority. Only the constitutional chain
can establish authority.

## Archive Unit

The minimal preservation unit is the active `.herm` corpus:

```text
bundle.herm/
    context.json
    hermeneia.db
```

This follows the active storage specification. A preservation export may wrap
this bundle for transport:

```text
INV-001-preservation/
    corpus/
        bundle.herm/
            context.json
            hermeneia.db
    preservation/
        checksums.sha256
        verification.json
        README.md
    adjacent_artifacts/
        builds/
        papers/
        research/
```

Only `bundle.herm` is authoritative. The outer directory is a transport
envelope. The `preservation/` files are derived metadata. The
`adjacent_artifacts/` files are included for reconstructability and human audit
when they exist outside the database.

The envelope must not be treated as a second `.herm` format. It may be zipped,
tarred, copied to a drive, placed in a Git repository, or uploaded to a storage
target without changing the authoritative corpus.

## Completeness Levels

An export should report its completeness explicitly.

### Corpus-Complete

The archive contains a valid `.herm` corpus with:

- `context.json`;
- `hermeneia.db`;
- expected schema version;
- SQLite integrity check passing;
- foreign-key check passing;
- immutable triggers present;
- all required parent rows present; and
- a deterministic hash tree over the copied files.

### Source-Complete

The archive contains the original source artifact bytes for every
`SourceDocument`, or a ratified storage specification proves those bytes are
embedded inside `.herm`.

If only source hashes and exact parser output are present, the archive may
preserve evidence and lineage, but it cannot claim complete restoration of the
original source artifact.

### Build-Complete

The archive contains the adjacent build artifacts needed to reconstruct a
publication or release cycle, such as:

- compile recipe;
- coverage report;
- release candidate log;
- release decision;
- rendered artifact;
- blueprint;
- methodological provenance; and
- research notes used by the build.

These files are preserved as project artifacts unless and until a ratified
storage specification makes them canonical database records.

### Target-Replicated

The archive has been copied to more than one independent storage target, and
each target copy verifies against the same hash tree.

## SourceDocument Preservation Gap

Current authority names `SourceDocument` as the original artifact and gives it
an identity derived from raw source bytes. Current implementation stores source
identity and metadata in `source_documents`, while the active bundle shape names
only `context.json` and `hermeneia.db`.

This leaves an architectural question:

> Where do the original source bytes live inside the authoritative portable
> artifact?

Until this is ratified, Preservation Layer implementation must not claim
Source-Complete restore unless it can verify that the original bytes are present
inside the archive or are included as explicitly labeled adjacent artifacts with
matching hashes.

Recommended ratification question:

> Should the active `.herm` storage specification include original source bytes
> inside the authoritative bundle, or should source-byte preservation be an
> explicit preservation-envelope obligation outside `.herm`?

This question affects restore semantics and must be resolved before promising
decades-long independent recovery.

## Investigation Identity Boundary

The user-facing language may say "investigation", but current authority does
not ratify a Project or Investigation object.

Until such an object is ratified, an export target must be one of:

- a `.herm` bundle path;
- a `hermeneia.db` path that can be written into a `.herm` bundle; or
- an explicitly supplied directory of adjacent artifacts.

Future commands may accept `INV-001` only after the system has a ratified way to
resolve that identifier without inventing a Project object.

## Proposed Command Surface

These commands are proposed, not implementation-authorized.

### Export

```text
herm preserve export <bundle.herm | hermeneia.db> --out <archive-dir>
```

Responsibilities:

- copy the authoritative `.herm` corpus without mutation;
- optionally include user-selected adjacent artifacts;
- compute checksums over every exported file;
- record export tool version and timestamp as non-authoritative metadata;
- report completeness level; and
- fail if required corpus files are missing.

Future user-facing alias, after investigation identity is ratified:

```text
herm export investigation INV-001
```

### Verify

```text
herm preserve verify <archive-dir | bundle.herm>
```

Responsibilities:

- read only;
- verify checksums;
- run SQLite `integrity_check`;
- run SQLite `foreign_key_check`;
- verify expected constitutional triggers exist;
- verify required parent relationships;
- verify `.herm` shape;
- report completeness level; and
- fail closed on mismatch, absence, or ambiguity.

`verify` must not create schemas, migrate databases, seed defaults, update
timestamps, or write repair files.

### Restore

```text
herm preserve restore <archive-dir | bundle.herm> --to <destination>
```

Responsibilities:

- verify before restore;
- copy the `.herm` corpus byte-for-byte when possible;
- preserve canonical object IDs unchanged;
- never rewrite source, evidence, provenance, or canonical rows;
- refuse restore if the archive is corrupt or incomplete for the requested
  level; and
- report whether restoration is Corpus-Complete, Source-Complete, or
  Build-Complete.

Restore is a write path because it creates files at the destination. It must not
mutate the source archive.

### Replicate

```text
herm preserve replicate <archive-dir | bundle.herm> --target <target>
```

Target support should be additive:

- local folder;
- external drive;
- user-managed cloud folder;
- Git repository;
- S3-compatible object storage;
- GitHub Release;
- institutional archive; and
- public preservation service.

Each target driver copies the same archive bytes and verifies them after copy.
No target driver may transform the archive, rewrite history, add canonical
metadata, or become the source of truth.

## Content Addressing and Integrity

Every preservation export should compute a deterministic hash tree:

```text
sha256(relative_path + NUL + file_bytes)
```

Paths must be sorted bytewise. Path separators must be normalized to `/`.

The result should include:

- per-file SHA-256;
- root archive digest;
- `.herm` database digest;
- `context.json` digest;
- source artifact digests when present;
- adjacent artifact digests when included;
- export tool version;
- export timestamp; and
- schema version detected from the database.

These records are verification metadata. They are not provenance parents for
canonical objects.

## Build Artifact Preservation

The white paper build convention already demonstrates the minimum
publication-preservation set:

| Artifact | Preservation role |
|---|---|
| Compile recipe | What was built from what |
| Coverage report | Whether the output fulfilled its Blueprint |
| RC log | How the compilation matured |
| Release decision | Human authorization and known limitations |

A preservation export should include this set when preserving a publication or
release cycle.

The design rule is:

```text
Rendered artifact alone is not enough.
Preserve the recipe, measurements, history, and decision that made it legible.
```

## Edition Continuity

The preservation concern that motivates this design is the "edition 34"
problem: a later steward should not be forced to begin from finished prose after
the prior steward is gone.

An edition should be inheritable with the state of understanding that produced
it:

```text
Edition 33
    Blueprint
    Evidence
    Critic findings
    Rejected interpretations
    Accepted revisions
    Known limitations
    Release decision

        |
        v

Edition 34
```

Edition 34 does not start from the final wording of Edition 33. It starts from
the evidence trail, obligations, critiques, decisions, and open questions that
made Edition 33 intellectually accountable.

The successor steward does not have to treat the prior steward as infallible.
They can inspect what was established, what was contested, what was
speculative, what was rejected, and what remained unknown. Preservation should
therefore support disciplined continuation rather than frozen inheritance.

Preservation begins before succession. The first beneficiary of a preserved
investigation is usually the original investigator returning with fresh
perspective. Only later does that same evidence trail become an inheritance for
other stewards.

```text
Today
    |
    v
Tomorrow's Me
    |
    v
My Team
    |
    v
My Successor
    |
    v
Future Researchers
```

The evidence trail is the continuity mechanism in each case. It protects the
difference between:

```text
I think differently now.
```

and:

```text
Here is the evidence that caused me to think differently.
```

Hermeneia is designed for the second statement.

## Storage, Preservation, Stewardship

The Preservation Layer separates three concerns that are often conflated:

| Concern | Question | Authority |
|---|---|---|
| Storage | Where do the bytes exist? | None |
| Preservation | Can the bytes survive and verify? | Operational only |
| Stewardship | Can the investigation continue responsibly? | Human judgment under constitutional lineage |

Storage location does not make a corpus authoritative. Preservation checks make
copies inspectable and durable. Stewardship decides what continuation means.

This mirrors Hermeneia's broader architecture: separate responsibilities so
each can be evaluated independently.

## Storage Targets

The Preservation Layer should separate archive validity from storage location.

Supported targets should implement the same interface:

```text
write archive bytes
read archive bytes
verify archive digest
report target metadata
```

Target metadata may record:

- target type;
- target location;
- copied_at timestamp;
- archive digest;
- verification status; and
- provider-specific object ID or URL when available.

Target metadata is operational. It shall not affect canonical object identity,
authority, confidence, evidential status, or lineage.

## UI Principle

Preservation status should be visible without turning infrastructure into
ontology.

Useful user-facing statements:

- "This corpus has been exported."
- "This export verifies."
- "Source bytes are included."
- "Build artifacts are included."
- "Copies exist in 3 targets."
- "Last verification failed on external drive copy."

Unsafe statements:

- "This target is authoritative."
- "GitHub is the source of truth."
- "Cloud backup makes this interpretation more reliable."
- "A verified copy is a ratified claim."

## Failure Modes

The Preservation Layer must fail closed.

| Failure | Required behavior |
|---|---|
| Missing `context.json` | Not a valid `.herm` corpus |
| Missing `hermeneia.db` | Not a valid `.herm` corpus |
| SQLite integrity failure | Verification fails |
| Foreign-key failure | Verification fails |
| Checksum mismatch | Verification fails |
| Missing source bytes | Source-Complete restore unavailable |
| Missing build artifacts | Build-Complete restore unavailable |
| Unknown schema version | Read-only inspection only unless migration is ratified |
| Broken lineage | Verification fails; no repair |
| Target upload failure | Archive remains valid locally; target not counted |

## Implementation Constraints

Future implementation should observe these constraints:

- Use pure functions for hash-tree construction and verification.
- Use read-only SQLite connections for verification.
- Never run migrations during verification.
- Never use `UPDATE` or `DELETE` on canonical tables.
- Never create a second authoritative export format.
- Never repair missing lineage.
- Never infer project identity from filenames.
- Never treat storage target metadata as epistemic evidence.
- Keep every storage target adapter replaceable.

## Test Obligations

An implementation would need tests proving:

- CI-013: export does not emit a competing authoritative `.herm` shape.
- CI-012: verify is side-effect-free.
- CI-005: export and restore do not mutate immutable evidence tables.
- CI-006: verify detects missing required parents.
- CI-011: nondeterministic audit records survive export and restore.
- CI-016: disposable derived artifacts can be absent without corrupting
  canonical history.
- Checksum mismatch causes failure.
- Byte-for-byte restored corpus preserves canonical object IDs.
- Missing source bytes prevents Source-Complete status.
- Missing build artifacts prevents Build-Complete status.
- Storage target copies verify against the same root digest.

## Ratification Path

Before code, resolve these architectural questions:

1. Where are original source bytes preserved inside or beside `.herm`?
2. Is the preservation envelope allowed as a non-authoritative transport
   wrapper?
3. Which sidecar names are permitted so they do not conflict with legacy
   `manifest.json` semantics?
4. Should CLI commands live under `herm preserve ...`, or should `export`,
   `verify`, and `restore` become top-level verbs?
5. How should user-facing "investigation" IDs resolve before Project is
   ratified?
6. Which build artifacts are required for Build-Complete status?
7. Which storage targets belong in v1, and which remain future adapters?

## Promise

The product promise should eventually be:

> Your understanding is yours. Hermeneia does not preserve your mind; it
> preserves the evidence, decisions, and rationale that allow future stewards,
> including your future self, to responsibly reconstruct and continue your
> investigation.

That promise is only true if preservation remains open, inspectable,
content-addressed, provider-independent, and faithful to the existing
constitutional storage authority.
