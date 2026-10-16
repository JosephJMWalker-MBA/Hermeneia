"""ADR-0046 U: the `findings` vocabulary migration for schema 22. Implementation-ready; never run on open until the
activation step (ADR-0046 ratified, ADR-0048 released first).

SQLite cannot alter a CHECK constraint, so the canonical `findings` table is rebuilt in one transaction. Every row is
copied and verified before commit, the immutability and supersession guards are recreated and still enforce, and any
failure rolls back everything. The rename runs in legacy mode because the supersession guards name `findings`; without
it SQLite refuses the rename.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

from .schema_guard import check_schema_marker

UNVERIFIABLE = "unverifiable"
TARGET_SCHEMA_VERSION = 22
_OPERATIONS = "'preservation','omission','transformation','injection','not_evaluated'"
_STATUSES = "'preserved','omitted','transformed','injected','not_evaluated'"


class FindingsMigrationError(RuntimeError):
    """The findings vocabulary migration could not be proven exact; nothing was changed."""


def admits_unverifiable(conn: sqlite3.Connection) -> bool:
    (sql,) = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'findings'").fetchone()
    return f"'{UNVERIFIABLE}'" in sql


def _ledger(conn: sqlite3.Connection) -> tuple[int, str]:
    digest, count = hashlib.sha256(), 0
    for row in conn.execute("SELECT * FROM findings ORDER BY id"):
        digest.update(repr(tuple(row)).encode("utf-8"))
        count += 1
    return count, digest.hexdigest()


def migrate_findings_vocabulary(db_path: str | Path) -> dict:
    """Admit `unverifiable` in the findings vocabulary. Idempotent: an already migrated ledger is left as it is."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        check_schema_marker(conn, TARGET_SCHEMA_VERSION)  # ADR-0048: never touch a workspace newer than the target
        if admits_unverifiable(conn):
            # Also the case after a build older than ADR-0048 lowered the schema marker of a migrated workspace.
            return {"status": "already_migrated"}
        objects = conn.execute("SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'findings' AND sql IS NOT NULL "
                               "ORDER BY type, name").fetchall()
        (table_sql,) = [sql for kind, _name, sql in objects if kind == "table"]
        rebuilt = (table_sql.replace("CREATE TABLE findings", "CREATE TABLE findings__v22", 1)
                   .replace(f"({_OPERATIONS})", f"({_OPERATIONS},'{UNVERIFIABLE}')", 1)
                   .replace(f"({_STATUSES})", f"({_STATUSES},'{UNVERIFIABLE}')", 1))
        if rebuilt.count(f"'{UNVERIFIABLE}'") != 2 or "findings__v22" not in rebuilt:
            raise FindingsMigrationError("the findings schema is not the one this migration knows; nothing was changed")
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA legacy_alter_table=ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                before = _ledger(conn)
                conn.execute(rebuilt)
                conn.execute("INSERT INTO findings__v22 SELECT * FROM findings")
                conn.execute("DROP TABLE findings")
                conn.execute("ALTER TABLE findings__v22 RENAME TO findings")
                for kind, _name, sql in objects:
                    if kind in ("index", "trigger"):
                        conn.execute(sql)
                if _ledger(conn) != before:
                    raise FindingsMigrationError("the rebuilt ledger differs from the original; rolled back")
                if conn.execute("PRAGMA foreign_key_check").fetchall():
                    raise FindingsMigrationError("a reference into the ledger broke; rolled back")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.execute("PRAGMA legacy_alter_table=OFF")
            conn.execute("PRAGMA foreign_keys=ON")
        return {"status": "migrated", "findings": before[0]}
    finally:
        conn.close()
