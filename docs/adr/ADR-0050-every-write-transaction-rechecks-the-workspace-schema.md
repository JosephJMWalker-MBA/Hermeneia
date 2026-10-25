# ADR-0050: Every Write Transaction Re-checks the Workspace Schema

**Status:** RATIFIED (decisions 1–6, with explicit verification stipulations)
**Version:** 1.0
**Date:** 2026-10-24
**Ratified by:** Primary Human Steward
**Ratified proposal HEAD:** `af4d1555bbb1ca4dbff3691ef085abcb8d7736a5`
**Implementation status:** Not implemented; no writer guard, schema-22 activation, migration or release authorized by recording this ratification.
**Extends:** [ADR-0048](ADR-0048-newer-workspace-schemas-are-refused.md), ratified 2026-10-23. **Supersedes:** nothing.
ADR-0048's text stays as ratified. ADRs are immutable records (`ADR_README.md`; Constitution Art. XV), so this
extension is a separate ADR rather than an edit.
**Scope:**
- once a workspace is open, every transaction that writes it re-reads the schema marker inside that transaction;
- migration DDL outside the store's initialization runs through ADR-0048's guarded initialization;
- a schema migration requires a quiesced workspace.

**Relies on:**
- ADR-0048: the probe, the refusal classes and monotonic markers;
- Constitution Art. XIII: the storage specification defines migration rules;
- CA-0001: the forensic evidence chain, which the measured races reach;
- CA-0004: monotonic knowledge and auditable governance.

**Ratified additional precondition for:** ADR-0046's `unverifiable` activation (schema 22), in addition to ADR-0048's schema-21 refusal release. This ratification does **not** itself authorize schema-22 activation.

---

## Context

**Evidence:** [`docs/verification/2026-10-24-adr0048-post-open-write-races.md`](../verification/2026-10-24-adr0048-post-open-write-races.md)
and `tests/test_adr0048_post_open_write_races.py`, measured on `main` `6e62a4d`.

**What ADR-0048 and #264 already guard:**
- ADR-0048 probes the marker before a workspace is opened, migrated or written, and at each request write connection.
- #264 also re-checks it under every write lock that the store's *initialization* takes.

**What is left.** Writes after that run unguarded. A newer build that commits its migration in the window receives
this build's writes, until the next open or connection refuses. Five witnesses fail on `main` at the first transaction
after the open:

| Witness | Writes that land in the schema-22 workspace |
| --- | --- |
| A request write connection (`ratify-blueprint`) | a Blueprint and an Architect plan |
| A request store (upload) | a SourceDocument, SourceExtraction, Observation and provenance |
| A CLI raw connection (`profile create`, after its prompts) | an Expression Profile |
| Restore | the restored records |
| `/api/setup/init`'s second migration, against a newer schema that moved a table | the table recreated and 9 rows seeded |

**The windows are long:**
- a request write connection is probed before provider calls run;
- an interactive CLI command is probed before its prompts.

**Rows from an older build can't be identified afterwards.** `compiler_version` is a static `0.1.0`.

**The risk under the planned schema 22** (inferred from unmerged #266) is an older Critic still in flight. It would
write immutable `findings` that it can never mark `unverifiable`.

**What SQLite guarantees (measured):**
- Reading the marker inside the write transaction is sufficient. An IMMEDIATE transaction holds the marker fixed until
  it commits.
- A deferred transaction that has read the marker cannot write from a stale snapshot in WAL mode. It fails as
  `database is locked`.
- One check costs about 10.6 µs.

## Decision (ratified, with the verification stipulations below)

1. **Every write transaction re-checks.** This covers every transaction that writes a workspace, whether DML or DDL:
   - through the store;
   - through a request connection;
   - from the CLI;
   - in restore, workspace lifecycle or authoring.

   Each one reads the schema marker inside that transaction, before its first write. It refuses ADR-0048's classes
   (newer, ambiguous, malformed) with nothing written:
   - The refusal is explicit, with ADR-0048's errors, not a lock error.
   - Read-only transactions are unaffected and take no write lock.
2. **Slow work stays outside write transactions.** A write transaction begins after provider calls, model generation
   and human input, never around them. That way no write lock is held through a generation or an interactive session,
   and the check sits immediately before the write it protects.
3. **Migration DDL outside initialization is guarded initialization.** It runs through ADR-0048's guarded
   initialization, the mechanism #264 introduced. This covers:
   - the `ensure_*` helpers, when they run on request or CLI connections;
   - `/api/setup/init`'s second migration.

   This clarifies and extends ADR-0048 Decision 1's initialization/migration coverage.
   The Primary Human Steward ratified this requirement together with decisions 1 and 2.
4. **A migration requires a quiesced workspace.** A schema migration (schema 22 and later) runs only after two
   conditions hold:
   - every Hermeneia process using the workspace (servers, supervised runtimes, CLI commands) has stopped;
   - a verified backup exists.

   This is an operational precondition. Decisions 1–3 protect the workspace if it is violated.
5. **Witnesses and tripwire.**
   - The strict-xfail witnesses in `tests/test_adr0048_post_open_write_races.py` become passing regressions, and
     none may be removed.
   - ADR-0048's write-site tripwire extends from connection sites to their write transactions. A new writing site
     fails until it is shown to be guarded.
6. **Storage specification.** The ADR-0048 section of `docs/15_Storage.md` incorporates the
   ratified transaction-level rule and the quiesced-migration precondition.

## Ratification stipulations — mandatory implementation acceptance criteria (2026-10-24)

The Primary Human Steward ratified decisions 1–6 in full **with two binding verification stipulations**:

**V1. Governed refusal, not merely non-mutation after any error.** Every race regression must prove that a newer
schema migration actually committed at the intended seam, that the older writer committed no DML, DDL or
canonical record, **and** that the operation returned or raised an explicit, governed ADR-0048 refusal
(`NewerSchemaError`, `SchemaMarkerError`, or a deliberately specified equivalent at the HTTP/CLI boundary).
An unrelated exception, generic HTTP 500, `database is locked`, silently suppressed error, or unreached seam
cannot count as passing the requirement. The existing witnesses currently suppress operation exceptions and
primarily assert no mutation: they are **baseline evidence**, not sufficient final acceptance tests, until these
outcome assertions are added. Existing passing control and append-only fixtures remain.

**V2. Exhaustive write-path inventory and future-proof enforcement.** The implementation must identify **every**
workspace DML/DDL writer (store methods including `atomic()` and `_own_transaction()`, request write connections,
CLI writers, `ensure_*` migrations, `/api/setup/init`, restore, lifecycle, authoring and any other discovered
paths) and demonstrate the schema re-check occurs **inside each write transaction before its first write**.
Read-only transactions must remain non-writing and need no write lock. The regression harness samples at most
eight transaction points in long operations, so those samples alone do not prove exhaustive coverage. Pin the
full inventory and its guard at an executable write-site/transaction tripwire that fails on any newly introduced
unguarded writer, and add focused tests for the uncovered categories and race interleavings. Confirm slow provider
and interactive work remains outside write locks. Re-run focused tests and the full suite against an isolated,
current-main baseline before merging implementation.

Neither stipulation changes the substantive storage rule; both are conditions of implementation validation.
They do **not** ratify writer-version metadata, database-side fence mechanisms, or policies for sidecar files.

---

## Consequences

**What changes:**
- Writers start their transactions through a guarded path:
  - the store's implicit-transaction writers, `atomic()` and `_own_transaction()`;
  - the 27 `_conn_rw` call sites;
  - the 10 writing CLI modules;
  - restore, lifecycle and authoring.
- Writers that today open a transaction before slow work must move it after that work.
- `GuardedInitialization` guards reads as well, so request connections need a write-only variant.

**What it costs:**
- A measured schema-marker probe was about 10.6 µs in the recorded synthetic benchmark. This is
  not a guarantee of negligible lock acquisition time or end-to-end latency.
- Decision 2 avoids holding write locks throughout provider calls or human input;
  actual contention and timing must be verified during implementation.

**Behavior:**
- A schema-21 build that meets a migrated workspace mid-operation fails that operation explicitly.
- It never adds records to the newer workspace.

## Alternatives considered

- **Quiescing alone (decision 4 without 1–3):** it depends on the operator, and it cannot detect an unknown
  concurrent process.
- **A database-side write fence installed by the newer migration (Option C of the evidence record):** deferred.
  - It would also stop pre-ADR-0048 builds from writing rows or lowering the marker.
  - But it does not stop their DDL, it adds a per-table trigger and a per-connection function, and it ships inside
    schema 22's own migration.
  - It needs its own ADR, ordered with #266.
- **Accepting the risk (Option D):** rejected for schema-22 activation. It leaves the possibility of permanently
  incorrect Findings.
- **Holding a write lock for a whole request or command:** rejected. It blocks every writer through provider calls and
  human input.
- **Keeping ADR-0048's connection-level check alone:** this is what the witnesses measure as insufficient.

## Not decided here

- **Writer identity:** whether rows record the writing build's schema level. `compiler_version` is static today, and
  this bears on the release-identity question (package `0.1.0`, tag `v0.6.0`).
- **Files beside the database:** files written next to the workspace (uploads and compile output) are not covered by
  the schema marker. Whether a refused write must leave none is open.
- **ADR-0048's residual risks** stand: a forged lower marker, and builds that predate ADR-0048.

## Evidence

- **The record:** `docs/verification/2026-10-24-adr0048-post-open-write-races.md`. It holds six witnesses and five
  SQLite checks, measured on `main` `6e62a4d`.
- **The tests:** `tests/test_adr0048_post_open_write_races.py`.
  - **On `main`:** five witnesses are strict xfails. Each fails only by assertion, at the first transaction after
    the open.
  - **Also in the file:** a control that passes where the build already refuses, and the append-only `setup/init`
    case, which passes.
  - **Under a scratch prototype of decision 3**, the `setup/init` witness XPASSes. That prototype is not on any
    branch.

---

## Ratification record

To be completed **only** by the Primary Human Steward.

| Field | Value |
| --- | --- |
| Decision | **RATIFIED IN FULL, WITH VERIFICATION STIPULATIONS** |
| Decisions ratified (1–6, in full or in part) | **1, 2, 3, 4, 5, 6 — all** |
| Ratified by | **Primary Human Steward** |
| Date | **2026-10-24** |
| Ratified proposal HEAD | **`af4d1555bbb1ca4dbff3691ef085abcb8d7736a5`** |
| Amendments at ratification | **V1 explicit governed refusal outcomes, not incidental exceptions; V2 exhaustive write-path coverage with executable tripwire, not merely sampled seams. No other scope added.** |
| Activation boundary | **No runtime activation, schema-22 migration, real-workspace migration, release, or change to another ADR authorized here.** |
