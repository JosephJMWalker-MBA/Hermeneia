# ADR-0048 post-open write races — 2026-10-24

**Status:** evidence for a Steward decision. Measured on `main` `6e62a4d`, which includes #264.

- No code was changed.
- Nothing here is proposed for activation.
- ADR-0048 is ratified and unchanged. This record does not amend it.

**Decision requested.** ADR-0048 guards a workspace at open and at each request write connection. Should that
protection reach every write, and if so how, before schema 22 activates?

**Result.**
- **The gap.** Once a probe has passed and initialization has finished, this build's writes run unguarded.
- **What it allows.** A newer build that commits its migration in that window receives this build's writes:
  - Blueprints and Architect plans;
  - SourceDocuments, SourceExtractions, Observations and provenance;
  - Expression Profiles;
  - restored records.
- **The bound.** Exposure is limited to operations already in flight. Every later open or connection is refused.
- **Classification:** a **specification gap**, not an implementation defect. ADR-0048 guards at connection
  granularity, and the implementation conforms to it.

## What #264 already closed

`SQLiteStore` and the app's startup migration initialize through `GuardedInitialization`
(`hermeneia/storage/schema_guard.py`). Every transaction that initialization opens takes the write lock and re-reads
the marker before its first statement. A newer migration that commits at any of the 27 points where initialization
holds no transaction is therefore refused before this build writes again. That is pinned in
`tests/test_newer_schema_refusal_boundaries.py`.

This record covers what happens **after** that.

## Where the window is

| Path | Where the probe runs | What runs between the probe and the write |
| --- | --- | --- |
| Request write connection `_conn_rw` (`app.py:613`) | Once, at connect | The whole request. There are 27 call sites: 26 in routes, some of them GETs, and one helper (`app.py:633`). `run-artist` probes at `app.py:7705` and writes after the provider has generated (`render_for_plan` / `render_for_observation`). `architect/generate` (`app.py:6702`) and `run-critic` (`app.py:7980`) have the same shape. |
| Request store `_store()` (`app.py:673`) | At store open, then guarded initialization | Every write after the open. There are 12 call sites, among them upload (`app.py:7289`), E10 generate/discover and the E10 Critic (`app.py:6230`). |
| CLI raw connections (13 sites in `hermeneia/cli/`) | `main()` and `resolve_db_target` | The whole command, including interactive prompts, so the window is as long as the person takes: `profile create` (`profile_cmd.py:121`) and `interpret create` (`interpreter.py:195`). **10 of the 13 modules write**; `comparer`, `inspector` and `health` only read. |
| Store-then-raw writers | Store open | Restore (`restore.py:559` → `561`), workspace creation (`lifecycle.py:130` → `131`) and the authoring service (`authoring/service.py:205`) each close a guarded store, then write on a new raw connection. |
| `/api/setup/init` (`app.py:3351`) | Store open at `3358` | `ensure_profile_tables` on a raw connection (`3360`, `3363`). |

**Migration DDL also runs on unguarded connections, outside initialization.** These are the `ensure_*` helpers.
`ensure_artist_tables` is an alias of `ensure_profile_tables` (`sqlite.py:1218`), and `ensure_critic_tables` calls it.

- **Web request connections:** `app.py:910`, `1179`, `6865`, `7997`, `10296`.
- **CLI:** `architect_cmd.py:57`, `artist_cmd.py:71`, `bootstrap_cmd.py:164`, `critic_cmd.py:56`, `profile_cmd.py:127`,
  and `theme_cmd.py:44`, `75` and `100`.

## Witnesses (measured, deterministic)

**Method.** Each witness:
1. builds a real synthetic workspace (one uploaded PDF, two Observations);
2. lets a second connection commit a "newer build" migration (marker 21 → 22, plus a new table) at one named seam after
   the probe has passed;
3. compares the workspace after the operation with the workspace right after the newer migration.

Changes are measured as:
- the SQLite schema cookie, which moves on any DDL;
- per-table row counts;
- the marker.

| # | Operation and seam | Outcome | Written into the schema-22 workspace | Schema changes |
| --- | --- | --- | --- | --- |
| W1 | `POST /api/pipeline/ratify-blueprint`; newer migration right after `_conn_rw`'s probe | **201** | `narrative_blueprints` 1, `blueprint_observation_links` 2, `architect_plans` 1, `architect_plan_paragraphs` 1 | 0 |
| W1′ | The next request, same app | **500**, `NewerSchemaError` | nothing | 0 |
| W2 | `POST /api/upload`; newer migration right after the request store's guarded open | **200** | `source_documents` 1, `source_extractions` 1, `observations` 1, `provenance` 1, `observation_derived` 1, `observation_terms` 3, `terms` 3 | 0 |
| W3 | `herm --db … profile create`; newer migration while the command waits at its first prompt | **completed** | `expression_profiles` 1 | 0 |
| W4 | `restore_workspace` into a fresh target; newer migration right after its guarded store closes | **completed** | the whole bundle: `source_documents` 1, `source_extractions` 2, `observations` 2, `provenance` 2, plus derived rows | 0 |
| W5a | `POST /api/setup/init`; newer migration before its second `ensure_profile_tables`; newer shape **append-only** (adds a table) | **200** | nothing | **0** |
| W5b | The same, newer shape **renames** `expression_profiles` | **200** | recreated `expression_profiles` and seeded **9** rows | **1** |

**What the witnesses show:**
- **Bounded exposure.** The race affects operations in flight. W1′: the next connection is refused.
- **Under append-only evolution**, older builds wrote rows but changed no schema (W1–W4, W5a). The `ensure_*` DDL
  changes a newer workspace only if the newer schema moved a table it creates (W5b).
- **The forensic evidence chain is reachable.** W2 and W4 created SourceDocument → SourceExtraction → Observation
  records, with their provenance, from a build that cannot know the newer storage rules.
- **Rows from an older build can't be identified afterward.** `provenance.compiler_version` and
  `source_documents.compiler_version` record the constant `0.1.0` (`compiler/observation_compiler.py:17`), not the
  writer's schema level. This is the same release-identity question as package `0.1.0` against tag `v0.6.0`.

## Severity against the planned schema 22 (inferred from code, not measured)

The planned schema 22 is #266's `hermeneia/storage/findings_vocabulary.py` on `provenance-unverifiable-ready` `2ac296d`,
which is unmerged and unratified. It rebuilds only `findings`, so that its CHECK vocabulary admits `unverifiable`, and
it keeps the table name.

- **Older `ensure_*` DDL:** a no-op against it, consistent with W5a.
- **Older writes to every other table:** valid under schema 22.
- **The substantive risk is an older Critic still in flight.** Three paths write findings:
  - `run-critic` (`insert_findings_batch`, `app.py:8060`);
  - the E10 Critic (`app.py:6230`);
  - `herm critic`.

  Their findings pass the widened CHECK, but such a build can never record `unverifiable`. Findings are immutable, so
  a misclassified finding stays until it is superseded (compare ADR-0049 research, #270).
- **Older reads in flight** of `unverifiable` rows fail with the `KeyError` that ADR-0046 measured. Those are read
  failures, not writes.

## Candidate remedies: what SQLite actually does

These were measured on `6e62a4d` with a scratch prototype. No repository code was changed.

| # | Check | Result |
| --- | --- | --- |
| T1 | `BEGIN` (deferred), probe, newer commit, then write | **refused**: `database is locked`, 0 rows. In WAL mode a stale snapshot cannot write. |
| T2 | Probe outside any transaction (today's `_conn_rw`), newer commit, then write | **written**: 1 row |
| T3 | A request connection wrapped in `GuardedInitialization`, newer commit, then write | **refused**: `NewerSchemaError`, 0 rows |
| T4a | A fence trigger whose body calls a function that is not registered | creation allowed |
| T4b | An older connection's INSERT, and its marker downgrade, on fenced tables | **both refused**: `no such function` |
| T4c, T4e | An older connection's reads; a supporting connection that registers the function | reads unaffected; supporting writes succeed |
| T4d | An older connection's DDL (`DROP TRIGGER`) | **not fenced** |
| T5 | Cost of one marker probe | **10.6 µs** (20,000 runs) |

## Options for the Steward

None of these is activated or recommended here. They differ in where the protection lives (procedure, code or
database) and in what it would need ratified.

**A. Procedure: stop everything before migrating.**
- **What:** make "stop every Hermeneia process on the workspace, verify a backup, then migrate" a condition of
  schema-22 activation. #266 already carries a verified-backup R2 procedure.
- **What it closes:** the window, for a single-operator deployment, with no code.
- **Limits:** it depends on the operator, and it cannot detect an unknown concurrent process.
- **Class:** configuration or procedure.

**B. Re-probe at the start of every write transaction**, extending #264's rule from initialization to all writes.
- **Why it works:** T1–T3 show that a probe at the start of each write transaction is enough.
- **Costs:**
  - Every writer must start its transactions through a guarded path:
    - the store's implicit-transaction writers (`_commit()`), `atomic()` and `_own_transaction()`;
    - the 27 `_conn_rw` call sites;
    - the 10 writing CLI modules;
    - restore, lifecycle and authoring.
  - A **write-only** variant is needed. `GuardedInitialization` also guards reads, so on the GET routes that use
    `_conn_rw` it would take the write lock for SELECTs.
  - Deferred transactions fail as `database is locked` rather than with an explicit refusal, unless they are begun
    IMMEDIATE.
- **Class:** function. It changes ADR-0048's rule from "every request write connection" to "every write
  transaction", so it needs an amendment or a successor ADR.

**C. A database-side write fence, installed by the newer migration itself.**
- **What:** triggers that call a function only supporting builds register. T4 shows that this refuses any older
  connection's DML and its marker downgrade.
- **Unique benefit:** it is the only option that also stops **pre-ADR-0048 builds** from writing rows or lowering the
  marker, which is part of ADR-0048's second residual risk.
- **Limits:** it does not stop their DDL, including the supersession-trigger replacement (T4d).
- **Costs:**
  - a fence trigger on every table, with a tripwire;
  - the function registered on every write connection of supporting builds, which means a central connection helper
    for the 27 connection sites the tripwire pins;
  - external tools such as the `sqlite3` shell can no longer write.
- **Class:** a new storage mechanism that would ship inside schema 22's own migration, so it needs its own ADR and
  ordering with #266.

**D. Accept and record as a residual.**
- **Why it might be enough:** exposure is limited to operations in flight, and under monotonic schema evolution
  (CA-0004) older rows stay valid.
- **What it leaves:** the in-flight Critic risk for `findings` above.
- **What to record:** the risk, in the schema-22 activation criteria.

Narrower than all four: `/api/setup/init` and the `ensure_*` calls on request and CLI connections are migration DDL.
Routing them through the existing `GuardedInitialization` would follow ADR-0048 Decision 1 ("every entry point that
would initialize, migrate or write ... reads its schema marker first") with the mechanism #264 already uses. It could
be treated as an implementation correction under the existing ratification, if the Steward agrees it falls within
that decision.

## Questions for the Steward

1. Is the post-open window within ADR-0048, as an amendment, or a new decision?
2. Which of A–D must hold before schema 22 activates?
3. Should rows record the writer's schema level? Today `compiler_version` is a static `0.1.0`, which also bears on the
   release-identity question.
4. May the `ensure_*` and `/api/setup/init` migrations be guarded now, as an implementation correction under the
   ratified Decision 1?

## Limits of this evidence

- **Workspace:** a synthetic workspace (two Observations), not the private real study.
- **Seams:** injection is deterministic, through named seams (monkeypatched `check_schema_marker` caller,
  `SQLiteStore.__init__` / `close`, the CLI prompt, `ensure_profile_tables`), not timing-based.
- **Provider calls:** their durations were not measured. The window's length is argued from code order.
- **Schema-22 severity:** inferred from unmerged, unratified #266 code.
- **CLI witness:** W3 uses `profile create`, because `bootstrap` needs the Gatsby corpus (`OBS-19`) and exits on a
  synthetic workspace before writing.
- **Pinning:** the witnesses are now pinned as strict xfails in `tests/test_adr0048_post_open_write_races.py`. They
  replay each operation with the newer migration committed before its transactions, so they do not depend on where
  the probe lives. The proposed rule is drafted as `docs/adr/ADR-0050-every-write-transaction-rechecks-the-workspace-schema.md`,
  which is unratified.
