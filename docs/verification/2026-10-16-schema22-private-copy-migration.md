# Schema-22 candidate migration on private copies of the real study (2026-10-16)

**Status:** pre-activation readiness evidence.
- U is **not** activated, and no real workspace was migrated.
- The original study was not opened.
- This was a rehearsal of the R2 procedure in
  `docs/design/release-sequence-2026-10-16.md`, using the product code of the
  integrated scratch stack.

## Safeguards

- **The original** (`study-d88c4a642956`, 7 files) was copied by filesystem
  copy only. No SQLite connection was ever made to it, and its files were
  byte-identical before and after.
- **Isolation:** sockets were blocked and no provider was used.
- **The copies were deleted afterwards.** This note holds counts and booleans
  only.
- **Packaged SQLite:** Hermeneia ships no SQLite of its own, so the runtime's
  is used. Here that is SQLite **3.49.1** (Python 3.13.5).

## History created on the copy (product routes)

The copy was first initialized at schema 21 by the product's own startup.
- **The Blueprint.** A probe Blueprint citing all 2,369 Observations was
  ratified through the route. A null narrative was added and the Critic route
  run (201).
- **The ledger:** 4,770 Findings, including 2,369 provenance Findings, all
  `preserved`.
- **Relationships:** 3 steward decisions and 1 supersession relation between
  Findings.

## Results

| Check | Result |
| --- | --- |
| R2 procedure (`migrate_with_verified_backup`) | migrated |
| Finding ledger (4,770 rows) | **identical** |
| Steward decisions and supersession relations | **identical** (3 and 1) |
| Findings still immutable; supersession guard still enforced | yes, yes |
| `integrity_check`, `foreign_key_check` | ok, clean |
| Backup equals the pre-migration state (logical dump) and keeps the old vocabulary | yes, yes |
| Marked 22 and opened by this (schema-21) build | **refused** (ADR-0048); files unchanged |
| Restore drill: the backup reopened as a workspace | ledger and relations identical |
| **Failure injection:** a failed check after the destructive steps | refused; rolled back in place; backup kept |
| **Failure injection:** a conflicting object (`findings__v22`) | refused before any change |
| **Failure injection:** a read-only workspace file | refused; nothing changed |
| **Failure injection:** process killed (`SIGKILL`) inside the migration transaction | on reopen: integrity ok, ledger and relations identical, vocabulary unchanged |

## History from an earlier-exporter restore

A second copy was exported, stripped of compile records (an earlier
exporter's bundle) and restored. The same probe history was then created on
it.

| Check | Result |
| --- | --- |
| Provenance Findings under v1.0 | 2,369 `transformed` |
| R2 migration | migrated; ledger and relations identical |
| v1.1, computed explicitly (dormant path) | 2,369 `unverifiable`; `blueprint_link_exists` true for all |
| Re-evaluation written with `unverifiable` admitted (simulated activation, this run only) | **refused by D-3: `divergent_result` × 2,369** |

**The last row** is the historical re-evaluation problem on real data. After
activation, the 2,369 historical `transformed` Findings stay as recorded, and
the corrected determinations cannot be recorded until ADR-0049 (or another
authority) provides a lawful path.

## Not covered

- **Other SQLite builds.** Only the runtime's 3.49.1 was tested. The rename
  relies on `legacy_alter_table`; re-verify on any other runtime that ships.
- **Disk full during the rebuild.** That was not injected. A read-only file
  and a killed process were.
- **The actual R2 activation step,** which is not prepared.
