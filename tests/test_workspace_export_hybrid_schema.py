"""Frozen negative witness: WBS export over a hybrid older workspace.

Real-study validation (docs/verification/2026-10-04-real-study-wbs-roundtrip.md)
found an older workspace whose ordinary web startup migration
(``ensure_profile_tables``) had added the current P3 receipt and award tables
while its ``perspectives`` table kept the pre-ADR-0045 shape. Export then failed
on the absent ``identity_scheme`` column before writing any bundle file.

Synthetic schema only; no real-study content or identifiers.
"""
from __future__ import annotations

import sqlite3

import pytest

from hermeneia.storage.sqlite import SQLiteStore, ensure_profile_tables
from hermeneia.workspace import export_workspace_bundle

TIME = "2026-10-04T12:00:00+00:00"

# The perspectives table as created before c2c55b3 (ADR-0045, schema 17).
LEGACY_PERSPECTIVES_DDL = """
CREATE TABLE perspectives (
    id          TEXT PRIMARY KEY,   -- sha256(lower(name))
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
)
"""


class KnownHybridSchemaExportFailure(AssertionError):
    """Only the exact observed missing-column export failure is expected here."""


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _hybrid_workspace(tmp_path):
    """Older perspectives shape plus the P3/award tables ordinary startup adds."""
    path = tmp_path / "workspace.db"
    SQLiteStore(path).close()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        for table in ("achievement_awards", "perspective_execution_receipts", "perspectives"):
            conn.execute(f"DROP TABLE {table}")
        conn.execute(LEGACY_PERSPECTIVES_DDL)
        conn.commit()
        # The web app's startup migration, not full SQLiteStore initialization.
        ensure_profile_tables(conn)
        conn.commit()
        assert _columns(conn, "perspectives") == ["id", "name", "description", "created_at"]
        assert "id" in _columns(conn, "perspective_execution_receipts")
        assert "receipt_json" in _columns(conn, "achievement_awards")
    finally:
        conn.close()
    return path


@pytest.mark.xfail(strict=True, raises=KnownHybridSchemaExportFailure,
                   reason="Export assumes the ADR-0045 perspectives columns; repair requires its own packet")
def test_export_completes_for_older_perspectives_table_after_startup_migration(tmp_path):
    path = _hybrid_workspace(tmp_path)
    try:
        export_workspace_bundle(path, tmp_path / "bundle", generated_at=TIME, workspace_id="synthetic")
    except sqlite3.OperationalError as exc:
        if "identity_scheme" in str(exc):
            raise KnownHybridSchemaExportFailure(str(exc)) from exc
        raise
