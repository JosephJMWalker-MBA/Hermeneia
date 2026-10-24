"""Refuse a workspace written by a newer schema before anything initializes, migrates or mutates it (ADR-0048).

The probe only reads. It runs on the connection that would otherwise write, or on its own connection, before any
DDL, migration or write. An ambiguous or malformed marker is refused too: the build cannot know which
schema it is looking at, so it fails closed rather than guessing.

ADR-0050 extends this to every write transaction: a workspace connection that may write is a GuardedConnection,
which re-reads the marker inside each write transaction before its first write. A refusal is recorded for the
boundary in progress (an HTTP request, a CLI command), so the boundary reports it even where a caller caught it.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import re
import sqlite3


class SchemaMarkerError(RuntimeError):
    """The workspace's schema marker cannot be trusted by this build; nothing was initialized or written."""


class NewerSchemaError(SchemaMarkerError):
    """The workspace was written by a newer schema than this build supports; nothing was initialized or written."""


class UnguardedWriteError(RuntimeError):
    """A write reached a transaction whose schema marker was never read (ADR-0050); nothing was written."""


_REFUSALS: ContextVar[list | None] = ContextVar("hermeneia_schema_refusals", default=None)


def _refused(error: SchemaMarkerError) -> SchemaMarkerError:
    refusals = _REFUSALS.get()
    if refusals is not None:
        refusals.append(error)
    return error


def start_recording_refusals():
    """Begin collecting the refusals raised at this boundary. Returns the token stop_recording_refusals() takes."""
    return _REFUSALS.set([])


def recorded_refusals() -> list[SchemaMarkerError]:
    return list(_REFUSALS.get() or [])


def stop_recording_refusals(token) -> None:
    _REFUSALS.reset(token)


@contextmanager
def recording_refusals():
    token = start_recording_refusals()
    try:
        yield _REFUSALS.get()
    finally:
        stop_recording_refusals(token)


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
        raise _refused(SchemaMarkerError(
            f"workspace schema marker is ambiguous ({len(versions)} versions recorded); refusing to open it"))
    version = versions[0]
    if type(version) is not int:
        raise _refused(SchemaMarkerError(f"workspace schema marker is malformed ({version!r}); refusing to open it"))
    if version > supported:
        raise _refused(NewerSchemaError(f"workspace schema {version} is newer than this build supports ({supported}); "
                                        "open it with a newer Hermeneia. Nothing was changed."))
    return version


# Statements that open no write transaction of their own: connection settings, and explicit transaction control.
_UNGUARDED = {"PRAGMA", "BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}
# A GuardedConnection treats every other statement as a write unless it is one of these reads.
_READS = {"SELECT", "VALUES", "EXPLAIN", "PRAGMA"}
_DML = {"INSERT", "UPDATE", "DELETE", "REPLACE"}
_LEADING_COMMENTS = re.compile(r"(?:\s|--[^\n]*|/\*.*?\*/)*", re.S)


def _keyword(sql: str) -> str:
    words = sql[_LEADING_COMMENTS.match(sql).end():].split(None, 1)
    return words[0].rstrip(";").upper() if words else ""


def _statements(script: str):
    """The statements of a script, as executescript() would run them."""
    start = end = 0
    while end := script.find(";", end) + 1:
        if sqlite3.complete_statement(script[start:end]):
            if _keyword(script[start:end]):
                yield script[start:end]
            start = end
    if _keyword(script[start:]):
        yield script[start:]


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
        for statement in _statements(script):
            self.execute(statement)
        self._conn.commit()

    def _guard(self, sql: str) -> None:
        keyword = _keyword(sql)
        if keyword and keyword not in _UNGUARDED and not self._conn.in_transaction:
            self._conn.execute("BEGIN IMMEDIATE")
            check_schema_marker(self._conn, self._supported)


@contextmanager
def guarded_initialization(conn, supported: int):
    """Run migration DDL through GuardedInitialization and commit at the end (ADR-0050 decision 3).

    Inside an initialization already guarded, it joins that one, which commits.
    """
    if isinstance(conn, GuardedInitialization):
        yield conn
        return
    guarded = GuardedInitialization(conn, supported)
    try:
        yield guarded
    except BaseException:
        conn.rollback()
        raise
    conn.commit()


def _supported() -> int:
    from .sqlite import SCHEMA_VERSION
    return SCHEMA_VERSION


class GuardedCursor(sqlite3.Cursor):
    """Every statement goes through its connection's write-transaction guard."""

    def execute(self, sql, parameters=()):
        return self.connection._guarded(self, sqlite3.Cursor.execute, sql, parameters)

    def executemany(self, sql, parameters):
        return self.connection._guarded(self, sqlite3.Cursor.executemany, sql, parameters)

    def executescript(self, script):
        """Commit first and commit at the end, as executescript() does, but run each statement through the guard."""
        self.connection.commit()
        for statement in _statements(script):
            self.execute(statement)
        self.connection.commit()
        return self


class GuardedConnection(sqlite3.Connection):
    """A workspace connection on which every write transaction re-reads the schema marker before its first write.

    ADR-0050:
    - A write outside a transaction opens one with BEGIN IMMEDIATE and reads the marker under that lock.
    - An explicit BEGIN or SAVEPOINT that opens a transaction reads it at once. A deferred one cannot write from a
      stale snapshot in WAL mode, and that lock error is reported as the refusal it is.
    - Every statement that is not a read or transaction control counts as a write. Reads never take the write lock.
    - A refused transaction is rolled back, so nothing is written and no lock is held. The refusal is ADR-0048's own
      error.
    - A write in a transaction whose marker was never read raises UnguardedWriteError, so no writer reaches the
      workspace around the guard.

    Commits stay where they were: DDL, and any statement on an autocommit connection, commit at once as before;
    DML leaves its transaction open for the caller, as the sqlite3 module does.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._marker_read = False

    def cursor(self, factory=GuardedCursor):
        return super().cursor(factory)

    def execute(self, sql, parameters=()):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql, parameters):
        return self.cursor().executemany(sql, parameters)

    def executescript(self, script):
        return self.cursor().executescript(script)

    # Each transaction reads the marker afresh: whatever ends one forgets the last read.
    def commit(self):
        self._marker_read = False
        super().commit()

    def rollback(self):
        self._marker_read = False
        super().rollback()

    def __exit__(self, *exc_info):
        self._marker_read = False
        return super().__exit__(*exc_info)

    def _guarded(self, cursor, run, sql, parameters):
        keyword = _keyword(sql)
        writes = bool(keyword) and keyword not in _READS and keyword not in _UNGUARDED
        if not self.in_transaction:
            self._marker_read = False
        opened = False
        try:
            if writes and not self.in_transaction:
                sqlite3.Cursor.execute(cursor, "BEGIN IMMEDIATE")
                opened = True
                self._read_marker()
            elif writes and not self._marker_read:
                raise UnguardedWriteError(f"a {keyword} reached a transaction whose schema marker was never read; "
                                          "ADR-0050 requires every write transaction to read it first")
            run(cursor, sql, parameters)
        except sqlite3.OperationalError as exc:
            refusal = self._refusal_behind(exc) if writes or keyword in ("BEGIN", "SAVEPOINT") else None
            if refusal is not None:
                self.rollback()
                raise refusal from exc
            if opened and self.in_transaction:  # it held only this statement, which failed
                self.rollback()
            raise
        except BaseException:
            if opened and self.in_transaction:
                self.rollback()
            raise
        if not self.in_transaction:
            self._marker_read = False
        elif keyword in ("BEGIN", "SAVEPOINT") and not self._marker_read:
            self._read_marker()
        if opened and (keyword not in _DML or self.isolation_level is None):
            self.commit()
        return cursor

    def _read_marker(self) -> None:
        try:
            check_schema_marker(self, _supported())
        except BaseException:
            self.rollback()
            raise
        self._marker_read = True

    def _refusal_behind(self, exc: sqlite3.OperationalError) -> SchemaMarkerError | None:
        """A lock error on a write is a refusal when a newer build has since migrated the workspace."""
        if getattr(exc, "sqlite_errorcode", 0) & 0xFF != sqlite3.SQLITE_BUSY:
            return None
        path = next((row[2] for row in sqlite3.Cursor(self).execute("PRAGMA database_list") if row[1] == "main"), "")
        if not path:
            return None
        try:
            require_supported_schema(path, _supported())
        except SchemaMarkerError as refusal:
            return refusal
        return None


def connect_workspace(database, **kwargs) -> GuardedConnection:
    """Open a connection that may write a workspace: every write transaction on it reads the marker first (ADR-0050).

    A connection that only reads uses a ``mode=ro`` URI with sqlite3.connect instead.
    """
    return sqlite3.connect(database, factory=GuardedConnection, **kwargs)


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
