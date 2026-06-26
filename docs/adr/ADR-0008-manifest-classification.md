# ADR-0008: Manifest — Not a Canonical Ontology Object

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P1-007 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Medium

---

## Context

The `.herm` bundle format requires a manifest file to describe the package itself: its version, schema version, checksums, dependencies, and compiler metadata. The question is whether this manifest is an epistemic object — something that belongs in the Hermeneia ontology — or a storage artifact that belongs in the storage layer.

This ADR closes Q-P1-007 from `EPISTEMIC_BACKLOG.md`.

---

## Decision

**The Manifest is NOT a canonical ontology object.**

The Manifest is a storage artifact. It belongs in the storage layer. It describes a `.herm` package, not a piece of epistemic content about a source corpus.

### Reasoning

The Hermeneia ontology represents knowledge *about* source documents: what was observed, how it was interpreted, what entities were identified, how they relate. The Manifest represents knowledge *about the bundle itself* — not about the content the bundle contains.

This is a category distinction, not a hierarchy distinction. The Manifest is not a lower-priority ontology object. It is a different kind of thing: infrastructure metadata, not epistemic content.

Formally: a Manifest answers *"What is in this package and how was it produced?"*  
The ontology answers *"What do we know about this corpus?"*

These are different questions with different authorities: the storage layer is authoritative for the first; the ontology is authoritative for the second.

### What the Manifest Contains

A Manifest is a JSON file (`manifest.json`) at the root of the `.herm` bundle. It contains:

| Field | Type | Purpose |
|---|---|---|
| `hermeneia_version` | SemVer string | The Hermeneia compiler version that produced this bundle |
| `schema_version` | SemVer string | The ontology schema version against which this bundle is valid |
| `bundle_id` | UUID | A unique identifier for this specific bundle instance |
| `created_at` | ISO 8601 datetime | When the bundle was created |
| `source_documents` | List[String] | Filenames of the source documents compiled into this bundle |
| `source_checksums` | Dict[String, String] | SHA-256 checksums of each source document at compile time |
| `db_checksum` | String | SHA-256 checksum of `hermeneia.db` at bundle creation |
| `context_checksum` | String | SHA-256 checksum of `context.json` at bundle creation |
| `compiler_metadata` | Object | Arbitrary compiler-reported metadata (sentence splitter version, OCR engine, etc.) |
| `adr_versions` | Dict[String, String] | Which ADR version governed each ontology object type at compile time |

---

## Inclusion Criteria

The following **do** belong in the Manifest:

1. Version information about the producing system.
2. Integrity checksums for bundle contents.
3. References to source documents (filenames and checksums).
4. Compiler pipeline metadata (versions, flags, settings used at compile time).
5. Bundle-level provenance (when produced, by which version of which system).

---

## Exclusion Criteria

The following **do not** belong in the Manifest:

1. Observations (belong in `hermeneia.db`).
2. Interpretations, Concepts, Relationships, or any other epistemic objects (belong in `hermeneia.db`).
3. ContinuityNodes (belong in `hermeneia.db`).
4. AI provenance records (belong in `hermeneia.db`, linked to the objects they describe).
5. Steward identities or stewardship decisions (belong in `hermeneia.db`).
6. Any object that participates in the epistemic provenance chain.

The Manifest is infrastructure. It does not participate in the epistemic provenance chain and must never be treated as if it does.

---

## Architectural Placement

```
.herm bundle (uncompressed ZIP)
├── manifest.json          ← storage layer (this ADR)
├── context.json           ← storage layer (human-readable corpus description)
└── hermeneia.db           ← SQLite: all ontology objects and provenance records
```

The Manifest is part of the ZIP container structure. It is read by the bundle reader before the database is opened. It is written by the compiler after the database is closed and checksummed. It has no tables in `hermeneia.db`.

---

## Serialization Rules

The Manifest is always:
- A UTF-8 encoded JSON file.
- Named exactly `manifest.json`.
- Located at the root of the `.herm` ZIP structure (not in a subdirectory).
- Written atomically as the last step of bundle creation (after all database writes are complete and checksummed).

The Manifest is never:
- Written incrementally during compilation.
- Updated after the bundle is sealed.
- Imported into the SQLite database.

---

## Provenance Implications

The Manifest is itself a provenance artifact at the bundle level: it records which compiler produced the bundle and which source documents it was derived from. However, it is **not** a Provenance record in the ontological sense. It does not participate in the chain from Observation to Interpretation. It is bundle metadata, not epistemic metadata.

If a bundle reader needs to verify the integrity of a bundle before opening its database, it uses the checksums in the Manifest. This is a storage-layer operation, not an ontology-layer operation.

---

## Validation Rules

At bundle-open time, a conforming reader must verify:

```python
assert manifest["hermeneia_version"] is not None
assert manifest["schema_version"] is not None
assert sha256(bundle["hermeneia.db"]) == manifest["db_checksum"]
assert sha256(bundle["context.json"]) == manifest["context_checksum"]
for doc in manifest["source_documents"]:
    assert sha256(source_file(doc)) == manifest["source_checksums"][doc]
```

A bundle whose checksums do not verify must be treated as corrupted. It must not be opened or modified. The failure must be reported to the steward.

---

## Migration Policy

If the Manifest schema changes (new fields required, old fields renamed):

1. Bundles produced under the old Manifest schema remain valid for reading if the checksums still verify.
2. A `schema_version` field identifies which Manifest schema the bundle uses.
3. Bundle migration tools may update the Manifest schema without touching `hermeneia.db`. Manifest-only changes are not ontological changes and do not require an ontology ADR.
4. If a field is removed from the Manifest schema, readers must fail gracefully when encountering bundles that still contain the removed field (ignore unknown fields, do not reject the bundle).

---

## Constitutional Alignment

- **Architectural Decoupling principle**: The storage layer and ontology layer are distinct. The Manifest is unambiguously storage layer. It does not belong in the ontology.
- **Article II** (Provenance mandatory): The Manifest provides bundle-level provenance (which compiler, which sources). This satisfies the storage layer's provenance requirement without conflating it with the epistemic provenance chain in `hermeneia.db`.

---

## Consequences

**Positive:**
- The ontology layer is not polluted with infrastructure metadata. Queries against the ontology are not accidentally including Manifest records.
- The storage layer has a clear responsibility: integrity verification and bundle-level provenance.
- The Manifest can evolve independently of the ontology schema. A Manifest schema change does not require an ontology migration.

**Negative:**
- Bundle-level metadata (which ADR versions governed the compile) lives in the Manifest, not in the database. A query that asks "which objects in this database were produced under ADR-0006 version 1.0?" must cross-reference the Manifest, not query the database directly. This is a minor architectural friction; the `adr_versions` field in the Manifest is the intended resolution.

---

## Alternatives Considered

**Alternative: Manifest as a canonical ontology object stored in `hermeneia.db`**  
Rejected. The Manifest describes the bundle; the bundle contains the database. If the Manifest is inside the database, reading it requires opening the database — but the Manifest is supposed to allow bundle integrity verification *before* the database is opened. This creates a circular dependency.

**Alternative: No Manifest; embed all metadata in `context.json`**  
Rejected. `context.json` is a human-readable corpus description — a steward-authored document explaining what the corpus is about. Mixing bundle infrastructure metadata (checksums, compiler versions) into a human-authored document conflates two different audiences and two different authorities.
