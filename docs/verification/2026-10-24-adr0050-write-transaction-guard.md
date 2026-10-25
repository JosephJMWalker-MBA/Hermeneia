# ADR-0050 write-transaction guard: implementation verification — 2026-10-24

**Status:** implementation on #273, branch `claude/hermeneia-adr-0048-verify-merge-138b06`:
- commits `b6c8736` (guard) and `3ccb4e8` (tests);
- review fixes in `20e1b83` (see [Review revisions](#review-revisions-2026-10-24-20e1b83));
- the journal-mode revision in `66663ae` (see [Journal-mode revision](#journal-mode-revision-2026-10-24-66663ae)).

It is verified against an isolated current-`main` baseline, but **not merged**.

- Nothing activates schema 22, migrates a real workspace or cuts a release.
- No writer-version field, database-side fence or sidecar-file policy is added. ADR-0050 left all three undecided.

**Result.**
- **The guard is in place.** Every connection that may write a workspace is a `GuardedConnection`. Each write
  transaction re-reads the marker inside the transaction, before its first write.
- **Refusals are governed.** After a newer build has migrated the workspace, every writer category refuses with
  ADR-0048's governed refusal and writes nothing.
- **Coverage is complete:**
  - every transaction start of every witnessed operation is checked (V1, V2);
  - the full writer inventory is pinned by an executable tripwire (V2);
  - no write lock is held through provider generation or prompts (decision 2).

## Mechanism (`hermeneia/storage/schema_guard.py`)

- **`connect_workspace()`** opens a `GuardedConnection`. Its `execute`, `executemany`, `executescript` and cursors run
  every statement through one guard. Connection-level `execute` bypasses an overridden `cursor()` in CPython 3.13,
  so the connection methods are overridden too.
- **How transactions are guarded:**
  - A **write outside a transaction** opens `BEGIN IMMEDIATE` and reads the marker under that lock before running.
  - An explicit **`BEGIN` or `SAVEPOINT`** that opens a transaction reads the marker at once.
  - A deferred transaction whose snapshot went stale fails its write as `database is locked`; that error is reported
    as the `NewerSchemaError` behind it.
- **Classification:** every statement counts as a write, so an unrecognised one fails safe, except these:
  - transaction control;
  - `SELECT`, `VALUES` and `EXPLAIN`;
  - a `WITH` statement that SQLite compiles without a write transaction (`EXPLAIN` shows `OP_Transaction` with
    P2 = 0);
  - a PRAGMA that is a known setting or introspection, or that reads a stored value without setting it.

  Reads open no transaction and take no write lock.
- **Journal mode.** SQLite cannot change the journal mode inside a transaction, so this is held to the rule by a
  lock instead:
  - WAL is the only mode a guarded connection may set. Any other target raises `UnsupportedJournalModeError` before
    anything runs.
  - A workspace already in WAL is only read; the assignment is never executed.
  - Any other workspace is converted on a connection of its own. In exclusive locking mode, its `BEGIN EXCLUSIVE`
    lock outlives the transaction, so the marker is read under the lock and the lock is held until the mode has
    changed.

  No exception to the rule is claimed. See the interpretive point under [Limits](#limits).
- **Refusal:** a refused transaction is rolled back, so nothing is written and no lock is held. A write in a
  transaction whose marker was never read raises `UnguardedWriteError`, so a writer cannot get around the guard.
- **Commit behavior is unchanged:**
  - DDL, and any statement on an autocommit connection, commit at once as before;
  - DML leaves its transaction to the caller, as the `sqlite3` module does;
  - a failed statement leaves no transaction behind.
- **Decision 3:** `ensure_architect_tables`, `ensure_profile_tables` (with its `ensure_artist_tables` alias) and
  `ensure_critic_tables` run as guarded initialization wherever they are called. That includes `/api/setup/init`'s
  second migration. Inside the store's own initialization they join it.

### Governed refusal at each boundary (V1)

| Boundary | Governed refusal |
| --- | --- |
| HTTP | **503** with `{"error": <ADR-0048 message>, "error_type": "NewerSchemaError" \| "SchemaMarkerError", "refusal": "workspace_schema"}`, for any refusal raised while serving the request.<br>If a route caught the refusal and answered itself, its answer is kept as `route_response: {status, body}`, so nothing it reported is lost.<br>The E10 routes add #272's disclosure: `created_count`, `partial`, `failures`, and the committed `proposal_ids`.<br>503 keeps ADR-0048's ratified write-route test valid. |
| CLI | `DatabaseTargetError` (a `SystemExit`) carrying ADR-0048's message. This also holds when a command caught the refusal and returned or exited. |
| Library (restore, lifecycle, store) | `NewerSchemaError` / `SchemaMarkerError` raised |

## Writer inventory (V2)

`tests/test_adr0050_write_transaction_guard.py::test_every_workspace_writer_is_guarded_and_inventoried` derives the
inventory from the code's syntax tree and pins it exactly. A new writer, guarded or not, fails until it is reviewed and
added. `test_every_inventoried_category_names_tests_that_exist` checks that each entry's covering tests exist.

| Write-capable connection | Category | Exercised by |
| --- | --- | --- |
| `SQLiteStore.__init__` | the store: 27 writer methods, `atomic()`, `_own_transaction()`, all through `self._conn` | store-style tests; W2 (`_commit()` writers end to end); W9 (`atomic()`) |
| `create_app` | app startup migration | `test_newer_schema_refusal_boundaries` |
| `create_app._conn_rw` | request write connections (27 call sites) | W1, W7, W8 |
| `create_app.api_setup_init` | `/api/setup/init` | W5 (append and rename) |
| `create_workspace` | workspace lifecycle | W6 |
| `restore_workspace`; `preview_restore` | restore; its preview, which only reads | W4; the guard tests |
| `authoring.service._conn_rw` | authoring | W10 |
| 13 CLI connections (`_open_db` ×12, `cmd_explorer_discover`) | CLI | W3; `test_every_cli_connection_is_guarded` |

**The only raw connections left that may write** are pinned with their reasons:
- the guarded factory itself;
- ADR-0048's read-only probe;
- `SQLiteStore.backup_to`'s destination. The backup API copies pages into a fresh file, so no SQL writes a workspace.

Every other `sqlite3.connect` is a `mode=ro` URI opened with `uri=True`, or `:memory:`. No code builds a `Connection`
or `Cursor` around the guard.

## Witnesses (V1, V2): every transaction start, governed refusal

`tests/test_adr0048_post_open_write_races.py` replays each operation once per transaction start after its
initialization. Each replay commits a newer migration exactly before that start and asserts three things:
1. the migration committed;
2. nothing was written after it (schema cookie, marker and logical dump);
3. the outcome was the governed refusal for that exact newer schema.

Operation exceptions are inspected, never suppressed. A witness that reaches no transaction raises `SeamNotReached`.

| Witness | Operation | Points checked | Governed refusal |
| --- | --- | --- | --- |
| W1 | `POST /api/pipeline/ratify-blueprint` (request write connection) | 2 | HTTP 503 |
| W2 | `POST /api/upload` (request store, `_commit()` writers) | 1 | HTTP 503 |
| W3 | `herm profile create` (CLI raw connection, guarded `ensure_*`) | 14 | `DatabaseTargetError` |
| W4 | `restore_workspace` | 1 | `NewerSchemaError` |
| W5 | `POST /api/setup/init`, append-only newer schema / renaming newer schema | 13 / 13 | HTTP 503 |
| W6 | `create_workspace` | 2 | `NewerSchemaError` |
| W7 | `POST /api/pipeline/run-artist` (the route catches every exception) | 1 | HTTP 503 |
| W8 | `POST /api/pipeline/run-critic` (findings) | 15 | HTTP 503 |
| W9 | `POST /api/e10/interpretations/generate` (`atomic()` staging) | 2 | HTTP 503 |
| W10 | an authoring write connection | 1 | `NewerSchemaError` |

That is 65 replays, all refused with nothing written. Upload, restore, the Artist and the authoring write each write
in a single transaction, so each has one point. The store's own initialization has 18 more points, all refused; they
are exercised by the passing control and pinned by `test_newer_schema_refusal_boundaries.py`.

The harness has two controls:
- it **passes** where the build already refuses (every point of a store open, initialization included);
- it **fails** a write on a raw connection.

## Decision 2: slow work holds no write lock

`test_no_write_lock_is_held_while_a_provider_generates_or_a_person_answers` probes for the workspace write lock at
three moments: while the Artist provider renders, while the E10 Explorer provider generates, and at each CLI prompt
of `profile create`. The lock was free every time.

The other surfaces were checked by reading:

| Surface | Why it holds no write lock |
| --- | --- |
| Architect generation | The provider call precedes its writes, which follow an `ensure_*` that commits. |
| Blueprint extraction | The provider is called before the write connection opens. |
| E10 discovery | Each bucket is generated before its staging write, and each proposal commits. |
| Perspective execution | It reads on a read-only connection, closed before the provider, and writes only on `/retain`. |
| CLI interactive commands | `blueprint`, `interpret`, `theme`, `extract` and `profile` prompt before their writes or after a commit. |

## Review revisions (2026-10-24, `20e1b83`)

Three code-review findings on `012ef68` were fixed. Each new regression **fails on `012ef68`**: 19 tests in all,
while the tests that pin unchanged behavior pass there too.

1. **#272 partial-commit truthfulness under a refusal.**
   - **What went wrong:** a refusal at participant 2's staging is not a `StagingError`, so it escaped the E10 loop.
     The plain 503 then hid participant 1's committed proposal.
   - **The fix:** both E10 routes now return the governed 503 at a staging refusal, with `created_count`, `partial`,
     `failures` and the committed `proposal_ids`, and stop. They give IDs only, because a build that refused the
     workspace does not read it back.
   - **The hook:** it no longer overwrites a governed response. When it replaces a route's own response, it keeps
     that report as `route_response`.
   - **Tests:** `test_an_e10_refusal_between_participants_discloses_what_it_committed` runs for generate and
     discover. Participant 1 commits, a newer migration commits while participant 2 generates, and participant 2 is
     refused. The test asserts:
     - the governed 503 carries exactly the stored proposal ID, with `created_count` 1 and `partial` true;
     - no later participant is generated;
     - the workspace is unchanged since the migration;
     - the next request is refused unwritten.

     `test_a_refusal_a_route_caught_keeps_the_route_report` pins the hook.
2. **Read-only `WITH RECURSIVE` queries took the write lock.**
   - **What went wrong:** every `WITH` was classified as a write. The search for CTEs before `012ef68` only matched
     single-line strings, so it missed the four multi-line recursive queries.
   - **The fix:** `WITH` statements are now classified by SQLite's own compiled program.
   - **Tests:** `test_every_recursive_query_in_hermeneia_reads_without_the_write_lock` extracts every `WITH`
     literal in `hermeneia/` and pins the four. They are the store's `_perspective_path_exists` and
     `supersession_descendants`, the app's `_blueprint_path_exists`, and restore's `_perspective_path_exists`. Each
     runs on a guarded connection with `timeout=0` while another connection holds the write lock.
     `test_the_recursive_store_and_restore_methods_take_no_write_lock` calls the real methods the same way. A
     writable CTE is still a guarded write: it is refused on a newer workspace and waits for the write lock.
3. **PRAGMAs that write the database file were unguarded.**
   - **The audit:** `user_version`, `application_id` and `schema_version` assignments changed the file. `page_size`,
     `auto_vacuum`, `optimize`, `incremental_vacuum` and `wal_checkpoint` can write in other circumstances. All of
     them, and any PRAGMA not known to be a setting or introspection, are now guarded writes.
   - **Tests:**
     - `test_no_pragma_can_change_a_newer_workspace` refuses twelve mutating forms on a newer workspace and leaves
       every stored value unchanged.
     - PRAGMA reads and settings take no write lock.
     - A stored PRAGMA still sets a supported workspace.
     - A PRAGMA tripwire covers every PRAGMA in `hermeneia/`'s SQL.
   - The unlocked journal-mode exception this revision introduced was itself found unsafe, and is replaced below.

## Journal-mode revision (2026-10-24, `66663ae`)

**The finding.** The unlocked journal-mode exception let a newer build migrate between the marker check and
`PRAGMA journal_mode`. Both directions were reproduced on `0f1db85`:
- a schema-21 workspace in **DELETE** mode passed the check, a second connection migrated it to schema 22, and the
  first connection's `PRAGMA journal_mode=WAL` changed the newer database's mode and bytes;
- a schema-21 workspace in **WAL** mode, after the same migration, was changed by `PRAGMA journal_mode=DELETE`.

**The design.** It needs no exception to the ratified rule:
- **WAL only.** A guarded connection may set only WAL. DELETE, TRUNCATE, PERSIST, MEMORY, OFF or an unknown mode
  raises `UnsupportedJournalModeError`, and nothing runs. Hermeneia sets no other mode.
- **WAL on WAL** only reads: the assignment is never executed, and a newer workspace is still refused.
- **Any other workspace** is converted by `GuardedConnection._convert_to_wal` on a connection of its own:
  1. `PRAGMA locking_mode=EXCLUSIVE`, then `BEGIN EXCLUSIVE`;
  2. the marker read;
  3. `COMMIT`, after which the lock is kept in exclusive locking mode;
  4. `PRAGMA journal_mode=WAL`;
  5. close.

  From the marker read to the mode change, no other connection can commit. A connection opened before the
  conversion takes up WAL at its next transaction.

**Tests**, all in `tests/test_adr0050_write_transaction_guard.py`:
- `test_a_newer_migration_at_any_point_of_a_wal_conversion_is_refused_or_locked_out` is the DELETE → WAL race. A
  newer build tries to migrate at each of the conversion's 11 seams: after every marker check, and before every
  statement on any connection to the workspace.
  - **4 seams:** it commits while the workspace is still DELETE, and the conversion is refused with
    `NewerSchemaError`. The marker, logical data, journal mode, file bytes and sidecars are unchanged since.
  - **5 seams:** it is locked out (`database is locked`), and the conversion completes on schema 21.
  - **2 seams:** it commits after the conversion has finished, and nothing is written after it.
- `test_a_newer_migration_after_a_passed_check_leaves_a_journal_mode_change_refused` covers the WAL → DELETE race,
  refused before anything runs, and DELETE → WAL after a caller's check, refused under the lock. Both leave all five
  properties unchanged.
- `test_a_store_refuses_to_convert_a_non_wal_workspace_a_newer_build_migrated_after_its_probe`.
- `test_no_newer_build_can_migrate_while_a_workspace_is_converted_to_wal`: a migration attempted at the mode change
  cannot commit.
- Six non-WAL targets are refused before anything runs.
- A supported conversion persists and is then written in WAL.
- WAL on WAL only reads, and takes no write lock.

The writer inventory and ADR-0048's tripwire count the conversion's connection. The PRAGMA tripwire names its two
PRAGMAs.

**On `0f1db85`**, 10 of these regressions fail. Both races are among them:
- WAL → DELETE fails the passed-check test;
- DELETE → WAL fails the every-seam test at seam 2.

The E10, CTE, PRAGMA, V1 and V2 regressions are kept.

**Environment.** 68 tracked files in the session's own worktree were iCloud placeholders ("dataless": the disk was
99% full), and reading one blocked. Every test was therefore run in fresh scratch worktrees under `/private/tmp`, and
each full suite ran behind a free-disk watchdog.

## Mutation checks

Each mutation was applied to one file, run against the tests that should catch it, and then restored byte for byte
(hash-verified). These are not in the suite.

| Mutation | Caught by |
| --- | --- |
| A CLI connection reverts to raw `sqlite3.connect` | the inventory tripwire |
| A new writer is added without review | the inventory tripwire |
| The guard stops reading the marker on its own `BEGIN IMMEDIATE` | the guard tests and the witnesses |
| The HTTP boundary stops reporting a refusal a route caught | W7: `run-artist` caught it into a generic 500 |
| The Artist holds a write transaction through its provider call | the decision-2 test: the lock was held while the Artist rendered |
| The CLI drops a refusal a command swallowed | the CLI swallow test |

## Behavior changes

- **HTTP refusals:** a refusal is now always the 503 contract above. Before, it was a generic 500 or a route's own
  error.
- **CLI refusals:** a refusal mid-command now ends as `DatabaseTargetError` with ADR-0048's message, not a traceback.
- **E10 refusals:** a refusal partway through an E10 request is the governed 503 with #272's disclosure, not a
  plain 503. A route's own answer that the hook replaces survives as `route_response`.
- **Read-only `WITH` queries and PRAGMA reads or settings** never take the write lock. Mutating PRAGMAs are
  guarded writes that commit at once, as before.
- **Lock acquisition:** a write outside a transaction acquires the write lock at `BEGIN IMMEDIATE`, one statement
  earlier than a deferred implicit transaction's first write. The lock and its holder are the same.
- **Failed statements:** a failed statement in a transaction the guard opened leaves none open. Before, a failed DML
  left the implicit transaction open.
- **Explicit transactions:** a transaction opened explicitly reads the marker at once.
- **Test seam:** the #237 lock-release regression injected its failing commit through `webapp.sqlite3`. It now
  injects through `connect_workspace`, with its assertion unchanged. The six other tests that patch the global
  `sqlite3.connect` still intercept every connection, because `connect_workspace` calls it.

## Full suites (isolated worktrees, current `main`)

| Tree | Passed | Skipped | xfailed | Failed | Time |
| --- | --- | --- | --- | --- | --- |
| clean `main` `6e62a4d` (tree `97cce2e`) | 3122 | 21 | 7 | 0 | 3:27 |
| `main` + `66663ae` (merge `738c50b`, tree `b665d8d`, identical to the head's tree) | **3215** | 21 | 7 | 0 | 3:23 (4 chunks) |

**How the integration run was done.** The tree was run in four sequential chunks by file: the full collected set of
3243 tests, each chunk with its own `--basetemp` and `TMPDIR`, deleted before the next. A single run was stopped by
the free-disk watchdog at 200 MB free, and produced no result. The clean-`main` row is a single run.

The added tests are the 13 witnesses and the 80 guard tests. The five former strict xfails are among the witnesses,
now passing.

The focused files all pass at `66663ae`: 203 tests. They are ADR-0048's evidence and boundaries, the witnesses, the
guard tests, #237, #261, #267, #271, #272 and the Critic ledger.

Earlier measurements against the same baseline: `3ccb4e8` 3170 passed, `20e1b83` 3204. The repository has no CI
checks, so these are local runs.

## Limits

- **Interpretive point for the Steward: no exception is claimed.** ADR-0050 says the marker is re-read "inside
  that transaction and before its first write".
  - SQLite cannot change the journal mode inside any transaction. So the conversion reads the marker inside an
    exclusive transaction, commits it, and changes the mode under the same exclusive lock, which it keeps.
  - The guarantee is the same: no newer build can commit between the read and the write.
  - If decision 1 is read to require the change itself to sit inside that SQL transaction, journal-mode
    initialization would need a governing decision. This revision does not add one.
- **A conversion briefly blocks other connections.** Its exclusive lock blocks readers as well as writers, but only
  while a non-WAL workspace is converted, which happens once. WAL workspaces are never converted.
- **`executemany` of a `WITH` statement** is treated as a write without asking SQLite: the parameter sets are an
  iterator. Hermeneia has no such call.
- **Files beside the database** (uploads, compile output) are not covered by the schema marker. ADR-0050 leaves that
  undecided.
- **The witnesses use a synthetic workspace**, not the private real study. Contention and latency beyond the suite
  were not measured.
- **ADR-0048's residual risks stand:** a forged lower marker, and builds older than ADR-0048.
