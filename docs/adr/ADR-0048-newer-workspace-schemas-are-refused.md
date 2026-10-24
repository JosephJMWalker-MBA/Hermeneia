# ADR-0048: Newer Workspace Schemas Are Refused

**Status:** RATIFIED
**Version:** 1.0
**Date:** 2026-10-16
**Ratified:** 2026-10-23
**Ratified by:** Primary Human Steward
**Ratified proposal HEAD:** `642983431d81a479b0900e97f34db7a05f5462df`
**Scope:** Newer, ambiguous or malformed workspace schema markers are refused before initialization, migration or writing; schema markers never decrease.

**Relies on:**
- Constitution Art. XIII: the storage specification defines migration rules;
- CA-0004: monotonic knowledge;
- the R1 direction: fail closed rather than discard silently.

**Precondition for:** ADR-0046's `unverifiable` activation (its P2). That
activation must follow a release containing this ADR.

**Steward recommendation, 2026-10-16:** authorize P2. That engineering
brief did not confer authority. The Primary Human Steward ratified this ADR
in full on 2026-10-23, as recorded below. Implementation and release remain
subject to their separate integration and validation gates.

---

## Context (measured on `main`, `09b72cc`)

- **`SQLiteStore` writes before it reads the marker.** It runs its DDL,
  supersession triggers and column migrations, and only then reads
  `schema_version`. A newer marker is then **rewritten down** to the build's
  own version, silently.
- **An ambiguous marker is read arbitrarily.** The marker is read with
  `fetchone()`, so if a workspace carries more than one row, whichever comes
  first wins.
- **App startup migrates without checking.** `create_app` runs
  `ensure_profile_tables` on an existing workspace with no check at all.
- **An older exporter would misdescribe a newer workspace.** It would describe
  the workspace's coverage without knowing what that workspace holds.

So an older build opening a newer workspace would:
- initialize and migrate it;
- downgrade its marker;
- then fail, or misreport, wherever newer records appear. ADR-0046 measured
  `KeyError` in the trust card and audit dashboard.

## Decision (ratified)

1. **Probe first.** Every entry point that would initialize, migrate or write
   a workspace reads its schema marker first, without writing:
   - `SQLiteStore`;
   - app startup, before its migration;
   - every request write connection, because a newer build may migrate the
     workspace while this one runs;
   - the CLI: its global `--db`, `resolve_db_target`, and `explorer`;
   - WBS export.
2. **Refusal classes.**

   | Marker | Outcome |
   | --- | --- |
   | Version greater than supported | **refused**: `NewerSchemaError` |
   | More than one row (ambiguous) | **refused** |
   | Not an integer (malformed) | **refused** |
   | No marker (a new or pre-versioning workspace) | proceeds as today |

3. **Nothing is written by a refused open.** Tested: the database file's bytes,
   its sidecar files and its logical dump are unchanged.
4. **The marker never decreases.** A failed migration leaves it unchanged. A
   later successful open completes the migration.
5. **Every writable connection site in `hermeneia/` has been reviewed** and is
   pinned by a tripwire test. A new site fails the test until it is
   classified.
6. **Storage specification.** The active storage specification carries this
   ratified migration-compatibility rule. The implementation must conform.

## Residual risks (recorded, not solved)

- **Forged lower marker.** Newer content behind a current-looking marker opens
  normally; tested and pinned. Detecting it would need a schema fingerprint
  recorded with the marker, which is a separate decision.
- **Builds that predate this ADR** cannot be protected. They downgrade the
  marker as before. That is why ADR-0046 requires this ADR in a release
  **before** any schema-22 migration.

## Evidence

`tests/test_newer_schema_refusal.py`: 13 tests, covering:
- refusal at the store, app startup, a write route after a concurrent
  migration, the CLI and export;
- ambiguous markers (a newer row or a lower row beside the current one) and
  malformed markers;
- the forged-lower-marker residual risk;
- monotonicity;
- a failed migration;
- new workspaces;
- the tripwire.

---

## Ratification record

To be completed **only** by the Primary Human Steward.

| Field | Value |
| --- | --- |
| Decision | **RATIFIED IN FULL** |
| Ratified by | **Primary Human Steward** |
| Date | **2026-10-23** |
| Ratified proposal HEAD | **`642983431d81a479b0900e97f34db7a05f5462df`** |
| Amendments at ratification | **None; accepted as written** |
| Activation boundary | **Schema 21 only; schema-22 activation and any real-workspace migration require separate authorization and verified release order** |
