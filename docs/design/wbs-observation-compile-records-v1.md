# WBS Observation compile records v1: repair provenance and index loss on restore (contract)

**Status:** frozen 2026-10-15, before implementation, on branch
`wbs-observation-provenance`. It is stacked on #255
(`p10-blueprint-chain-portability` `37883e5`).

**Defect.** The G2 private-copy validation of `study-d88c4a642956`
(`docs/verification/2026-10-13-g2-real-study-portability.md`) restored
2,369 Observations with **0** of their 2,369 `provenance` rows and 0 of
21,536 derived-index rows. It is pinned by two strict-xfail witnesses in
`tests/test_wbs_coverage_declarations.py`.

> A successful database restore is not necessarily a successful restoration
> of understanding (owner, 2026-10-15). This is an evidence-preservation
> defect, not missing optional metadata.

## 1. Investigation (observed at `37883e5`)

### `provenance`

- **Writer.** `compiler.compile_observations` writes one row per
  Observation. It is persisted in the compile transaction
  (`compiler.py` step 5).
- **Immutability.** The `provenance_no_update` and `provenance_no_delete`
  triggers refuse UPDATE and DELETE.
- **Contents:**
  - `id` = Observation ID (ADR-0012);
  - source document and extraction IDs, document hash;
  - page, paragraph, sentence;
  - `verbatim_text`;
  - `location_precision`;
  - character offsets;
  - bounding box (`bbox_*`, from the parser's paragraph layout);
  - `created_at`, `compiler_version`, `compilation_run_id` (a random UUID).
- **Not reproducible from retained evidence.** The run ID is random, the
  timestamps are compile-time, and the bounding box is paragraph layout that
  `source_extractions` does not store per paragraph. **It must be preserved
  verbatim.**
- **Consumers:**
  - Study Lineage attaches each provenance row to its Observation item;
  - the Critic provenance evaluation (ADR-0042) treats a missing row as
    `operation=transformation`, `status=transformed` ("a degraded state");
  - narrative trust summaries compare `verbatim_text` with `raw_text`;
  - the Reader's related-observations projection reads character offsets;
  - the CLI inspector and trace.

### `observation_derived`

- **Writer.** The same compile step: `normalize_sentence(raw_text)`, with
  token and whitespace maps written as `"[]"`, `derivation_version` =
  `COMPILER_VERSION` (`0.1.0`), and `derived_at` = compile time.
- **Classification.** CI-016 names `ObservationDerived` as a disposable
  derived artifact that may be regenerated from immutable ancestors with its
  derivation version recorded.
- **Reproducibility.** Content is a pure function of `raw_text` under the
  derivation version; `derived_at` is not reproducible.
- **Consumers:** `/api/search` (normalized text, falling back to raw text),
  `/api/trace`, `/api/e10/observations`, Blueprint detail, Field.

### `terms` and `observation_terms`

- **Writer.** `field.index.build_term_index`, over **all** Observations, at
  every compile (`INSERT OR IGNORE`).
- **Content.** Term IDs are SHA-256 of the term, extracted deterministically
  from `normalized_text` (or `raw_text`).
- **Classification.** A field index under CI-016.
- **Consumers:** upload statistics, `herm health` and the CLI inspector.

### Verified on a synthetic study

Rebuilding `observation_derived` content and both term tables from the
restored Observations with the current code reproduces the compile-time
rows exactly, apart from `derived_at`. The test text included ligatures,
irregular whitespace, dashes and apostrophes. This is re-measured on the
real study during this packet's validation.

## 2. Repair: one all-or-nothing component, `observation-compile-records-v1`

| Runtime table | Bundle file | Role | Row order |
| --- | --- | --- | --- |
| `provenance` | `corpus/provenance.json` | canonical | `id` |
| `observation_derived` | `corpus/observation_derived.json` | derived | `observation_id` |
| `terms` | `corpus/terms.json` | derived | `id` |
| `observation_terms` | `corpus/observation_terms.json` | derived | `observation_id, term_id` |

- **Rows.** Exact `SELECT *` rows, with each table's columns **equal** to the
  frozen schema-21 set. Encoding is the existing deterministic `_dumps`.
- **Manifest.** The `required_capabilities` include the component, and
  `counts` holds the row count of every table.
- **Gate.** The component is exported by default. This is the repair, and it
  is not gated, unlike the Blueprint chain, which has P8 authority behind its
  gate.

**Compatibility consequence (owner decision R1).** Default bundles now
declare a required capability that earlier restorers do not know. Earlier
Hermeneia therefore refuses to restore new bundles. It does not silently drop
provenance. This follows the P3/P4/P7 doctrine ("older restorers must refuse
the declared capability rather than silently drop it"). Bundles from earlier
exporters still restore (§4).

## 3. Export: closure or declared unsupported

Inside the existing read snapshot, any of the following failures means
**no** component file and **no** capability, and records
`declared_unsupported["observation-compile-records-v1"] = {reason_code,
reason}`. Everything else exports as before.

| Code | Condition |
| --- | --- |
| `COMPILE_RECORDS_SCHEMA_INCOMPLETE` | a table is missing, or its columns differ from the frozen set |
| `COMPILE_RECORDS_INTEGRITY_INVALID` | a provenance `id` differs from its `observation_id` (ADR-0012) |
| `COMPILE_RECORDS_CLOSURE_INCOMPLETE` | a provenance row's Observation, source document or source extraction is missing; a derived row's Observation is missing; an `observation_terms` row's Observation or term is missing |

**No repair, no fabrication.**
- An Observation that has no provenance row in the source stays without one.
- Export reports the count as `manifest.counts.observations_without_provenance`
  and does not manufacture a row.
- A `verbatim_text` that differs from its Observation's `raw_text` is carried
  as stored. Detecting that difference is the Critic's and trust summary's
  job.

## 4. Restore

| Bundle | Behavior | Coverage `observation_compile_records` |
| --- | --- | --- |
| Carries the component | Validate every file before writing: listed once, role as in §2, hash, path inside the root, exact columns, unique keys in key order, counts. Insert verbatim in one restore transaction after Observations, in order: provenance, `observation_derived`, `terms`, `observation_terms`. Re-check §3 closure against the target; any failure rolls back everything | `covered` |
| Component declared unsupported by its exporter | Provenance is **not** reconstructed. Derived indexes are **rebuilt** (below) | `provenance: unsupported` (with the exported reason), `derived_indexes: rebuilt` |
| From an earlier exporter (no component, no declaration) | Same as above | `provenance: unsupported`, `derived_indexes: rebuilt` |

Contradictions refuse: chain files without the capability, the capability
without its files, or a declaration together with files.

**Rebuild, under CI-016.** Only the derived indexes are rebuilt, and only
when the bundle lacks them:

- inside the restore transaction;
- from the restored Observations;
- with the current `normalize_sentence` and `build_term_index`;
- recording `derivation_version` = the current compiler version and
  `derived_at` = the restore time.

It never touches Observations, extractions, documents or provenance. It is
declared in coverage, never silent.

**`coverage.not_carried`.**
- When the component is covered, the `observation_provenance` and
  `derived_indexes` entries are removed.
- When it is not covered, `observation_provenance` remains `unsupported`.
  `derived_indexes` then carries `status: "rebuilt"`, with the derivation
  version.

**Earlier bundles.** Their restored Observations still have no provenance.
Under ADR-0042 the Critic will report them `transformed`. That is the
ADR's current definition of a missing row, and this packet does not change
it (§6).

## 5. Witnesses and tests

**Witnesses.** `RestoredProvenanceLost` and
`RestoredObservationLooksTransformed` must show **strict unexpected passes**
(`XPASS(strict)`) after the repair. Only then are their markers removed. The
two tests keep their assertions and become passing regressions.

**New tests:**

| Area | Test |
| --- | --- |
| Round trip | export → fresh restore gives provenance, `observation_derived`, `terms` and `observation_terms` rows **identical** to the source |
| Behavior before and after | `evaluate_provenance` findings on a seeded narrative; `_trust_summary` verbatim check; `/api/reader/documents/<doc>/related-observations` (offsets); `/api/search`; Study Lineage Observation items (each with its provenance record) are all equal |
| Earlier bundle | provenance stays absent (not manufactured); derived indexes are rebuilt and equal the source's content (all but `derived_at`); coverage says `rebuilt` |
| Export negatives | missing table; changed columns; ADR-0012 identity break; dangling Observation; dangling term — each declared unsupported with its code, writing no component file |
| Restore negatives | edited without rehash; rehashed with a dangling provenance Observation (refused at closure, target unchanged); capability without file; file without capability; count mismatch; duplicate key; unknown column; declaration plus files |
| Compatibility | a default bundle from the earlier exporter (`origin/main` code) restores under this code. This code's default bundle is refused by `origin/main`'s restorer with an unknown-capability error, never restored with silent loss. Run with the actual older code |

## 6. Not changed

- **Critic semantics.** ADR-0042's classification of a missing provenance
  row as "transformation"/"transformed" is unchanged; the authority question
  is reported.
- Observations, extractions and documents are not touched.
- Blueprint chain export stays gated, the `proposal` default is unchanged,
  and P8 generation stays gated.
- Inquiry notes, reviews, reports, governance and reading progress remain
  declared not carried, outside this packet.

## 7. Validation

- **Real study.** One fresh private copy of `study-d88c4a642956`, under the
  G2 safeguards:
  - original files hashed before and after;
  - no SQLite connection to the original;
  - sockets blocked; no provider;
  - counts and booleans only.

  It is migrated by the product startup initializer, exported, and restored
  into a fresh target, and must show:
  - identical provenance (2,369), derived rows (2,369), terms (3,320) and
    term pairs (15,847);
  - Lineage Observation items identical;
  - Reader related-observations and search results identical for fixed
    probes;
  - every Observation still has provenance.

  It also re-measures the exactness of the rebuild on all 2,369 rows.
- **Datasets and suite.** P5–P10 datasets reproduce, and the full suite is
  compared with the inherited baseline.
