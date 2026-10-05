"""Promoted regression from the frozen hybrid-schema export witness.

Real-study validation (docs/verification/2026-10-04-real-study-wbs-roundtrip.md)
found an older workspace whose ordinary web startup migration
(``ensure_profile_tables``) had added the current P3 receipt and award tables
while its ``perspectives`` table kept the pre-ADR-0045 shape. Export then failed
on the absent ``identity_scheme`` column before writing any bundle file.
Commit c4d4f27 preserves the negative version; the repair demonstrated a strict
unexpected pass before the expected failure was removed.

Synthetic schema only; no real-study content or identifiers.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3

from hermeneia.storage.sqlite import SQLiteStore, ensure_profile_tables
from hermeneia.workspace import export_workspace_bundle, restore_workspace

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


def _legacy_row(name: str, created_at: str) -> dict:
    return {"id": hashlib.sha256(name.lower().encode("utf-8")).hexdigest(),
            "name": name, "description": f"Synthetic {name} description.",
            "created_at": created_at}


def _hybrid_workspace(tmp_path, legacy_rows=()):
    """Older perspectives shape plus the P3/award tables ordinary startup adds."""
    path = tmp_path / "workspace.db"
    SQLiteStore(path).close()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        for table in ("achievement_awards", "perspective_execution_receipts", "perspectives"):
            conn.execute(f"DROP TABLE {table}")
        conn.execute(LEGACY_PERSPECTIVES_DDL)
        for row in legacy_rows:
            conn.execute("INSERT INTO perspectives (id, name, description, created_at) "
                         "VALUES (:id, :name, :description, :created_at)", row)
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


def test_export_completes_for_older_perspectives_table_after_startup_migration(tmp_path):
    path = _hybrid_workspace(tmp_path)
    try:
        export_workspace_bundle(path, tmp_path / "bundle", generated_at=TIME, workspace_id="synthetic")
    except sqlite3.OperationalError as exc:
        if "identity_scheme" in str(exc):
            raise KnownHybridSchemaExportFailure(str(exc)) from exc
        raise


def _perspective_rows(path) -> list[dict]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM perspectives ORDER BY id")]
    finally:
        conn.close()


def test_older_perspective_rows_export_verbatim_read_only_and_restore_as_label_v1(tmp_path):
    rows = [_legacy_row("Zeta lens", "2026-07-02T10:00:00+00:00"),
            _legacy_row("Alpha lens", "2026-07-01T10:00:00+00:00")]
    source = _hybrid_workspace(tmp_path / "source", rows)
    before = source.read_bytes()

    manifest = export_workspace_bundle(source, tmp_path / "bundle", generated_at=TIME, workspace_id="synthetic")
    export_workspace_bundle(source, tmp_path / "repeat", generated_at=TIME, workspace_id="synthetic")

    # Read-only over the older workspace: no migration, no identity column added.
    assert source.read_bytes() == before
    assert list(_perspective_rows(source)[0]) == ["id", "name", "description", "created_at"]
    # Verbatim stored rows, label-v1 order (name, created_at, id), deterministic bytes.
    exported = json.loads((tmp_path / "bundle/study/perspectives.json").read_bytes())
    assert exported == sorted(rows, key=lambda row: (row["name"], row["created_at"], row["id"]))
    assert manifest["counts"]["perspectives"] == 2
    for name in ("study/perspectives.json", "manifest.json"):
        assert (tmp_path / "bundle" / name).read_bytes() == (tmp_path / "repeat" / name).read_bytes()

    # Restore adds only scheme metadata, exactly as the ratified ADR-0045
    # migration does in place; no declaration provenance is fabricated.
    restore_workspace(tmp_path / "restored/workspace.db", tmp_path / "bundle")
    migrated = tmp_path / "migrated/workspace.db"
    migrated.parent.mkdir()
    shutil.copyfile(source, migrated)
    SQLiteStore(migrated).close()
    restored_rows = _perspective_rows(tmp_path / "restored/workspace.db")
    assert restored_rows == _perspective_rows(migrated)
    legacy = {row["id"]: row for row in rows}
    for row in restored_rows:
        assert {key: row[key] for key in legacy[row["id"]]} == legacy[row["id"]]
        assert row["identity_scheme"] == "perspective-label-v1"
        assert all(row[key] is None for key in row if key not in legacy[row["id"]] and key != "identity_scheme")
