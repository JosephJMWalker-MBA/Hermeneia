"""Refuse a workspace written by a newer schema before anything initializes, migrates or mutates it (ADR-0048).

The probe only reads. It runs on the connection that would otherwise write, or on its own connection, before any
DDL, migration or write. An ambiguous or malformed marker is refused too: the build cannot know which
schema it is looking at, so it fails closed rather than guessing.
"""
from __future__ import annotations

from pathlib import Path
import re
import sqlite3


class SchemaMarkerError(RuntimeError):
    """The workspace's schema marker cannot be trusted by this build; nothing was initialized or written."""


class NewerSchemaError(SchemaMarkerError):
    """The workspace was written by a newer schema than this build supports; nothing was initialized or written."""


def check_schema_marker(conn: sqlite3.Connection, supported: int) -> int | None:
    """Read the schema marker without writing. Returns the recorded version, or None when there is none yet."""
    # A view of that name is read by the store like the table, so it is a marker too, not its absence.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') "
                    "AND name = 'schema_version'").fetchone() is None:
        return None
    versions = [row[0] for row in conn.execute("SELECT version FROM schema_version")]
    if not versions:
        return None
    if len(versions) != 1:
        raise SchemaMarkerError(f"workspace schema marker is ambiguous ({len(versions)} versions recorded); refusing to open it")
    version = versions[0]
    if type(version) is not int:
        raise SchemaMarkerError(f"workspace schema marker is malformed ({version!r}); refusing to open it")
    if version > supported:
        raise NewerSchemaError(f"workspace schema {version} is newer than this build supports ({supported}); "
                               "open it with a newer Hermeneia. Nothing was changed.")
    return version


# Statements that open no write transaction of their own: connection settings, and explicit transaction control.
_UNGUARDED = {"PRAGMA", "BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}
_LEADING_COMMENTS = re.compile(r"(?:\s|--[^\n]*|/\*.*?\*/)*", re.S)


def _keyword(sql: str) -> str:
    words = sql[_LEADING_COMMENTS.match(sql).end():].split(None, 1)
    return words[0].rstrip(";").upper() if words else ""


class GuardedInitialization:
    """A connection for initialization: every transaction it opens re-reads the marker under the write lock.

    Initialization commits many times, and executescript() commits before it runs, so no one lock can span it, and a
    newer build may commit its migration in any gap, the gap after the first probe included. So each transaction
    starts by taking the write lock and reading the marker. A newer, ambiguous or malformed marker is refused before
    this build writes again, and the lock keeps the marker fixed until that transaction commits. Statements that open
    no transaction (connection settings and schema introspection) run as they are.
    """

    def __init__(self, conn: sqlite3.Connection, supported: int):
        self._conn = conn
        self._supported = supported

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, sql: str, parameters=()):
        self._guard(sql)
        cursor = self._conn.execute(sql, parameters)
        if _keyword(sql) == "BEGIN":
            check_schema_marker(self._conn, self._supported)
        return cursor

    def executemany(self, sql: str, parameters):
        self._guard(sql)
        return self._conn.executemany(sql, parameters)

    def executescript(self, script: str) -> None:
        """Commit first and commit at the end, as executescript() does, but run each statement through execute()."""
        self._conn.commit()
        start = end = 0
        while end := script.find(";", end) + 1:
            if sqlite3.complete_statement(script[start:end]):
                if _keyword(script[start:end]):
                    self.execute(script[start:end])
                start = end
        if _keyword(script[start:]):
            self.execute(script[start:])
        self._conn.commit()

    def _guard(self, sql: str) -> None:
        keyword = _keyword(sql)
        if keyword and keyword not in _UNGUARDED and not self._conn.in_transaction:
            self._conn.execute("BEGIN IMMEDIATE")
            check_schema_marker(self._conn, self._supported)


def require_supported_schema(db_path: str | Path, supported: int) -> int | None:
    """Probe an existing workspace without writing to it. A missing file is not a workspace yet.

    The handle only reads. It is opened read-write because a read-only handle cannot remove the WAL sidecar files
    it creates, so the workspace directory is left exactly as it was found.
    """
    path = Path(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path))
    try:
        return check_schema_marker(conn, supported)
    finally:
        conn.close()
