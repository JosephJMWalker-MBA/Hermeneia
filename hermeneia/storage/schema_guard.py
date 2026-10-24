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


class UnsupportedJournalModeError(RuntimeError):
    """A workspace's journal mode may only be set to WAL through a guarded connection (ADR-0050); nothing changed."""


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
_CONTROL = {"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}
_UNGUARDED = {"PRAGMA"} | _CONTROL
# A GuardedConnection treats every other statement as a write unless it is one of these reads, a read-only PRAGMA,
# or a WITH statement whose program SQLite compiles without a write transaction.
_READS = {"SELECT", "VALUES", "EXPLAIN"}
_DML = {"INSERT", "UPDATE", "DELETE", "REPLACE"}
_LEADING_COMMENTS = re.compile(r"(?:\s|--[^\n]*|/\*.*?\*/)*", re.S)

# PRAGMAs that never write the database file, in any form: connection settings and introspection. Any PRAGMA not
# named here or below counts as a write, so an unknown one fails safe.
_PRAGMA_NEVER_WRITE = {
    "analysis_limit", "automatic_index", "busy_timeout", "cache_size", "case_sensitive_like", "cell_size_check",
    "collation_list", "compile_options", "data_version", "database_list", "defer_foreign_keys", "foreign_key_check",
    "foreign_key_list", "foreign_keys", "freelist_count", "function_list", "index_info", "index_list", "index_xinfo",
    "integrity_check", "legacy_alter_table", "mmap_size", "module_list", "page_count", "pragma_list", "query_only",
    "quick_check", "recursive_triggers", "reverse_unordered_selects", "synchronous", "table_info", "table_list",
    "table_xinfo", "temp_store", "threads", "trusted_schema",
}
# PRAGMAs that read a value stored in the database file, and write it there when given one.
_PRAGMA_STORED = {"application_id", "auto_vacuum", "encoding", "journal_mode", "page_size", "schema_version",
                  "user_version"}
_PRAGMA = re.compile(r"PRAGMA\s+(?:\w+\s*\.\s*)?(\w+)\s*(=|\()?", re.I)
_JOURNAL_MODE = re.compile(r"PRAGMA\s+(?:\w+\s*\.\s*)?journal_mode\s*(?:=\s*|\(\s*)['\"]?(\w+)", re.I)


def _keyword(sql: str) -> str:
    words = sql[_LEADING_COMMENTS.match(sql).end():].split(None, 1)
    return words[0].rstrip(";").upper() if words else ""


def _pragma_kind(sql: str) -> str:
    match = _PRAGMA.match(sql[_LEADING_COMMENTS.match(sql).end():])
    if match is None:
        return "write"
    name, given = match.group(1).lower(), match.group(2)
    if name in _PRAGMA_NEVER_WRITE or (name in _PRAGMA_STORED and not given):
        return "read"
    return "journal_mode" if name == "journal_mode" else "write"


def _kind(conn: sqlite3.Connection, keyword: str, sql: str, parameters, many: bool) -> str:
    """Whether a statement is transaction control, a read, a write, or a journal-mode change."""
    if not keyword or keyword in _CONTROL:
        return "control"
    if keyword in _READS:
        return "read"
    if keyword == "PRAGMA":
        return _pragma_kind(sql)
    if keyword == "WITH" and not many:
        # SQLite knows whether a CTE writes: its program opens a write transaction (OP_Transaction, P2 > 0) only then.
        try:
            program = sqlite3.Cursor(conn).execute("EXPLAIN " + sql, parameters).fetchall()
        except sqlite3.Error:
            return "write"
        return "write" if any(op[1] == "Transaction" and op[3] for op in program) else "read"
    return "write"


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
        return self.connection._guarded(self, sqlite3.Cursor.executemany, sql, parameters, many=True)

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
    - Every statement that is not a read or transaction control counts as a write. Reads never take the write lock:
      a WITH statement is a read when SQLite compiles it without a write transaction, and a PRAGMA is a write unless
      it is a known setting or introspection, or reads a stored value without setting it.
    - A journal-mode change, which SQLite cannot make inside a transaction, is held to the same guarantee by a lock
      instead. WAL is the only mode it may set, and any other is refused before anything runs. A workspace already in
      WAL is only read. Any other workspace is converted on a connection of its own, which takes the exclusive lock,
      reads the marker under it and holds the lock until the mode has changed.
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

    def _guarded(self, cursor, run, sql, parameters, many=False):
        keyword = _keyword(sql)
        kind = _kind(self, keyword, sql, parameters, many)
        writes = kind == "write"
        if not self.in_transaction:
            self._marker_read = False
        if kind == "journal_mode":
            return self._journal_mode(cursor, run, sql, parameters)
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

    def _journal_mode(self, cursor, run, sql, parameters):
        target = _JOURNAL_MODE.match(sql[_LEADING_COMMENTS.match(sql).end():])
        if target is None or target.group(1).lower() != "wal":
            raise UnsupportedJournalModeError(f"{sql.strip()!r} would set a journal mode other than WAL, the only "
                                              "mode a workspace may be set to. Nothing was changed.")
        path = self._main_path()
        if self.in_transaction or not path:
            # SQLite refuses a mode change inside a transaction, and a database with no file is no workspace.
            return run(cursor, sql, parameters)
        if sqlite3.Cursor(self).execute("PRAGMA journal_mode").fetchone()[0] == "wal":
            check_schema_marker(self, _supported())  # nothing is written, but a newer workspace is still refused
        else:
            self._convert_to_wal(path)
        sqlite3.Cursor(self).execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()  # take up the new mode
        return sqlite3.Cursor.execute(cursor, "PRAGMA journal_mode")

    @staticmethod
    def _convert_to_wal(path: str) -> None:
        """Change a workspace to WAL with no gap a newer build could migrate in.

        In exclusive locking mode the lock that BEGIN EXCLUSIVE takes outlives its transaction, so it covers both the
        marker read and the mode change. Closing the connection releases it.
        """
        lock = sqlite3.connect(path, isolation_level=None)
        try:
            lock.execute("PRAGMA locking_mode = EXCLUSIVE")
            lock.execute("BEGIN EXCLUSIVE")
            check_schema_marker(lock, _supported())
            lock.execute("COMMIT")
            mode = lock.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        finally:
            lock.close()
        if mode != "wal":
            raise sqlite3.OperationalError(f"the workspace stayed in journal mode {mode!r}")

    def _main_path(self) -> str:
        return next((row[2] for row in sqlite3.Cursor(self).execute("PRAGMA database_list") if row[1] == "main"), "")

    def _refusal_behind(self, exc: sqlite3.OperationalError) -> SchemaMarkerError | None:
        """A lock error on a write is a refusal when a newer build has since migrated the workspace."""
        if getattr(exc, "sqlite_errorcode", 0) & 0xFF != sqlite3.SQLITE_BUSY:
            return None
        path = self._main_path()
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
