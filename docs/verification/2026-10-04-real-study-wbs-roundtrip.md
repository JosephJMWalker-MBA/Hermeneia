# Real-study WBS round-trip — 2026-10-04

**Result:** The round trip could not start. WBS export of the real study that
holds the only retained P3 receipt raised before writing any bundle file, so
restore never ran and no post-restore capture (B) exists. This is a real-data
portability defect on the export side. It is not the immutable-row drift
hypothesis the experiment was designed to test; that hypothesis remains untested.

- **Commit tested:** `bdf280a1c9f770548443cde0b46d8b75e2b39d2a`
- **Safe study alias:** `study-d88c4a642956`
- **Packet:** [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215)
  P3/P4 beta gate, WBS round-trip half, under
  [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214)
- **Frozen witness:** `tests/test_workspace_export_hybrid_schema.py`

## Planned experiment

Capture the Perspective Explorer assessment on a private copy (A), export that
copy with `export_workspace_bundle`, restore into a fresh database with
`restore_workspace`, capture again (B), and compare status, `evidence_sha256`,
dependency `record_sha256`/basis, receipt bytes and the Lineage item. Exact
equivalence would demonstrate real legacy portability for Explorer; an
`immutable_reference` digest change or loss of `earned` would be the failure
witness; `source_documents`-only drift would be the disclosed replay limitation;
restore refusal would be a real-data portability defect.

## Safety boundary

The workspace's seven regular files (database, WAL, SHM, calibration file,
source upload, and the older portable copy's two files) were hashed and copied
with filesystem reads only. The copy was verified byte-identical before any
database access. No SQLite connection was opened on the original. The local
server left running by the 2026-10-03 packet was not contacted or stopped.

All captures used `mode=ro` plus `PRAGMA query_only=ON` on the private copy.
Outbound sockets were blocked in-process. No award was issued, no provider or
model was called, and nothing was repaired. Afterward all seven original files
were byte-identical to the copy with unchanged modification times, and the
copy's database bytes and logical dump were unchanged by every read.

The first harness run did not handle the export exception, so it exited before
printing A. A was re-captured read-only from the same unchanged copy.

## Identity confirmation

The copy reproduces the 2026-10-03 state exactly:

- receipt `perspective-execution-receipt:sha256:5870a94e4c6717bd8d71f2c1e1b982f45c2570630f25fac7363f3ac3c3c0c45e`;
- run `9314a4a3-69d6-4c55-92c3-3644f698b5f6`;
- Explorer approval package digest
  `sha256:5ad385a0263ab96678fc405a7c9fea33c87e7ce751e27ad29d53fc946f047c71`,
  computed read-only with `prepare_perspective_achievement_award`;
- safe alias derivation matches.

## Capture A (private copy, before export)

| Field | Value |
| --- | --- |
| Perspective Explorer | `earned`, `SUPPORTED_RETAINED_WITNESS`, rule `1.0.0` |
| Second Opinion | `not_earned` |
| `evidence_sha256` | `sha256:2f308c23310e6f74f5f9306443b4791c3a5a88f5a734977dc77b5b83a547198f` |
| `rules_sha256` | `sha256:6b0065fac155c40fc25ce5cc62c53a7c250c0595dd4e49554669bab55e56197c` |
| Coverage | `covered`; 1 extant, 1 eligible; historical completeness `unknown` |
| Receipt bytes | 12,301; `sha256:481054bd01e701e7780e2e2e09bec447f4372432eb3f630100cb106360dba93f` |
| Lineage item | `retained_perspective_execution`, `recorded`, `model`, `retention.retained_at` `2026-10-03T18:26:50.120715+00:00`; canonical item `sha256:bfc4a2f4c6f8ecb822efc8c57d044d35145ac53b25ffa5369aa49c701ce2437f` |
| Dependencies | 5: one `source_documents` row (`evaluation_snapshot`) and four `source_extractions` rows (`immutable_reference`) |

Dependency record IDs and row digests are retained privately; `evidence_sha256`
commits to them.

## Failure

```text
sqlite3.OperationalError: no such column: identity_scheme
  hermeneia/workspace/export.py:80   _rows
  hermeneia/workspace/export.py:318  SELECT * FROM perspectives
                                     ORDER BY identity_scheme, name, created_at, id
```

No bundle directory or restore target was created. B was not produced.

## Structural cause

Read-only structure of the private copy:

- `perspectives` keeps its pre-ADR-0045 definition: `id`, `name` (`UNIQUE`),
  `description`, `created_at`; zero rows;
- `perspective_execution_receipts` exists with one row; `achievement_awards`
  exists with zero rows; 35 tables in total;
- `schema_version` still records `16`.

Ordinary web startup runs only `ensure_profile_tables`
([app.py:205-213](../../hermeneia/web/app.py)), which adds the receipt and award
tables ([sqlite.py:1199-1202](../../hermeneia/storage/sqlite.py)). Full
`SQLiteStore` initialization, which rebuilds `perspectives` for ADR-0045
(`_apply_perspective_schema_migration`, sqlite.py:1288 and 1313-1317) and records
the schema version, runs only on routes that call `_store()` (app.py:604-605).
The 2026-10-03 packet deliberately avoided storage-initializing routes. Startup
alone therefore produces this hybrid shape.

The web export route calls `build_workspace_zip` without store initialization
and maps only `PerspectiveExecutionExportError` and `PublicationExportError`
to a refusal (app.py:8790-8810). Exporting this study from the UI would
therefore be expected to fail the same way; that path was inferred, not
executed, because it would touch the original workspace.

The frozen witness reproduces the shape synthetically: a fresh store, the
legacy `perspectives` definition, then `ensure_profile_tables`. Export raises
the same error. It is a strict expected failure until a separately justified
repair.

## Gate consequence

At `bdf280a` the WBS exporter cannot export the only real workspace holding a
retained receipt, so the P3/P4 portability beta sub-gate is **failed** on real
data. Receipt codecs, restore and the award verifier were not reached and are
neither supported nor contradicted by this run.

## Not done

No export or restore of the original, no repair, no schema initialization of
any real or copied workspace, no award issuance, no provider call, no
broadening of the experiment. Raw source text, question, prompt, response,
private paths and workspace identity remain outside this note.
