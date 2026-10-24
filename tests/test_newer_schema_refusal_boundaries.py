"""ADR-0048 boundaries found while verifying #264 against current main.

The ratified evidence stays in test_newer_schema_refusal.py; these pin two defects the integration review measured:
the CLI probed a folder named by ``--db`` instead of its database, and the probe took a ``schema_version`` view for
no marker at all, so a workspace the store itself reads as newer was migrated and opened.
"""
from __future__ import annotations

import sqlite3
import sys

import pytest

from hermeneia.cli import main as cli_main
from hermeneia.storage.schema_guard import NewerSchemaError
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore
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
