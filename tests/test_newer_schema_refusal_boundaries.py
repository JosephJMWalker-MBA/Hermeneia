"""ADR-0048 boundaries found while verifying #264 against current main.

The ratified evidence stays in test_newer_schema_refusal.py. These pin what the integration review measured:
- the CLI probed a folder named by ``--db`` instead of its database;
- the probe took a ``schema_version`` view for no marker at all, so a workspace the store itself reads as newer was
  migrated and opened;
- a newer build that migrated the workspace after the probe, before or during initialization, still had its
  supersession triggers replaced and older DDL run over it.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest

import synthetic_study_lab as lab
from hermeneia.cli import main as cli_main
from hermeneia.storage import sqlite as storage
from hermeneia.storage.schema_guard import NewerSchemaError
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore
from hermeneia.web.app import create_app
from test_newer_schema_refusal import _mark, _snapshot, workspace  # noqa: F401  (workspace is a fixture)


def test_the_cli_probes_the_database_inside_a_folder_named_by_db(workspace, monkeypatch):
    """``--db`` may name a workspace folder or bundle (cli/target.py); it means that folder's hermeneia.db."""
    folder = workspace.parent
    monkeypatch.setattr(sys, "argv", ["herm", "--db", str(folder), "stats", str(folder)])
    cli_main.main()  # a supported folder opens, as on main
    _mark(workspace, SCHEMA_VERSION + 1)
    before = _snapshot(workspace)
    with pytest.raises(SystemExit) as exited:
        cli_main.main()
    assert "newer than this build supports" in str(exited.value)
    assert _snapshot(workspace) == before


def test_a_schema_version_view_is_read_as_the_marker(workspace):
    conn = sqlite3.connect(workspace)
    conn.executescript("DROP TABLE schema_version;"
                       f"CREATE VIEW schema_version AS SELECT {SCHEMA_VERSION + 1} AS version, 't' AS applied_at;")
    conn.close()
    before = _snapshot(workspace)
    with pytest.raises(NewerSchemaError, match=f"schema {SCHEMA_VERSION + 1} is newer"):
        SQLiteStore(workspace)
    assert _snapshot(workspace) == before


# ── A newer build migrates the workspace while this one initializes it ──────

def _migrate_as_newer_build(db: Path) -> None:
    """Another process running a newer build: new DDL and a raised marker, committed. It never waits for a lock."""
    conn = sqlite3.connect(db, timeout=0)
    try:
        conn.execute("CREATE TABLE future_records (id TEXT PRIMARY KEY)")
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION + 1,))
        conn.commit()
    finally:
        conn.close()


def _state(db: Path) -> tuple:
    """The schema cookie, the marker and the logical content.

    SQLite bumps the cookie on every schema change, so it shows DDL and trigger replacement even when the replaced
    triggers come back identical and the logical dump does not change.
    """
    conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return (conn.execute("PRAGMA schema_version").fetchone()[0],
                [r[0] for r in conn.execute("SELECT version FROM schema_version")],
                hashlib.sha256("\n".join(conn.iterdump()).encode()).hexdigest())
    finally:
        conn.close()


def test_a_newer_migration_between_the_probe_and_initialization_is_refused_without_writing(workspace):
    observed = []

    class RacedOpen(SQLiteStore):
        def _apply_schema(self):
            _migrate_as_newer_build(workspace)  # after the probe in __init__, before anything initializes
            observed.append(_state(workspace))
            super()._apply_schema()

    with pytest.raises(NewerSchemaError):
        RacedOpen(workspace)
    assert observed[0][1] == [SCHEMA_VERSION + 1]
    assert _state(workspace) == observed[0]  # no trigger replacement, DDL or other write after the newer migration


def _open_interleaved(db: Path, at: int | None, observed: list) -> int:
    """Open a store on ``db``; a newer build migrates at the ``at``-th point where initialization holds no transaction.

    Those points are where another process can commit: just before each statement that starts outside a transaction.
    Returns how many there were.
    """
    points = [0]

    class Interleaved(SQLiteStore):
        def _apply_schema(self):
            def trace(_sql):
                if not self._conn.in_transaction:
                    if points[0] == at:
                        _migrate_as_newer_build(db)
                        observed.append(_state(db))
                    points[0] += 1

            self._conn.set_trace_callback(trace)
            try:
                super()._apply_schema()
            finally:
                self._conn.set_trace_callback(None)

    Interleaved(db).close()
    return points[0]


def test_a_newer_migration_at_any_point_of_initialization_stops_every_later_write(tmp_path):
    """Initialization commits many times, and executescript() commits before it runs, so no single lock spans it.

    Wherever a newer build commits its migration in between, this build refuses before its next write.
    """
    template = tmp_path / "template.db"
    SQLiteStore(template).close()

    def copy(name: str) -> Path:
        (tmp_path / name).mkdir()
        return Path(shutil.copyfile(template, tmp_path / name / "hermeneia.db"))

    points = _open_interleaved(copy("dry-run"), None, [])
    assert points > 1
    for point in range(points):
        db, observed = copy(f"at-{point}"), []
        with pytest.raises(NewerSchemaError):
            _open_interleaved(db, point, observed)
        assert len(observed) == 1, point
        assert _state(db) == observed[0], point


def test_a_newer_migration_after_the_startup_probe_is_refused_before_the_startup_migration(workspace, monkeypatch):
    migrate = storage.ensure_profile_tables
    observed = []

    def raced(conn):
        _migrate_as_newer_build(workspace)  # after create_app's probe, before its startup migration
        observed.append(_state(workspace))
        migrate(conn)

    monkeypatch.setattr(storage, "ensure_profile_tables", raced)
    with pytest.raises(NewerSchemaError):
        create_app(db_path=workspace, credential_store=lab._NoCredentials())
    assert _state(workspace) == observed[0]
