"""ADR-0048: a workspace written by a newer schema is refused before any initialization, migration or mutation.

Each test builds a real workspace, makes it look newer (or tampered), and checks that every writing entry point
refuses it while the database file stays byte-identical and the logical content unchanged.
"""
from __future__ import annotations

import collections
import hashlib
import io
from pathlib import Path
import re
import sqlite3
import sys

import pytest

import synthetic_study_lab as lab
from hermeneia.cli import main as cli_main
from hermeneia.storage.schema_guard import NewerSchemaError, SchemaMarkerError
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import export_workspace_bundle

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path):
    with lab.isolated(tmp_path):
        db = tmp_path / "ws" / "hermeneia.db"
        SQLiteStore(db).close()
        client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
        lab._ok(client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(["The lamp burned all night.",
                                                                                "Nobody asked why."])), "a.pdf")},
                            content_type="multipart/form-data"))
        yield db


def _mark(db: Path, *versions) -> None:
    """Rewrite the schema marker as another build (or an attacker) would."""
    conn = sqlite3.connect(db)
    try:
        conn.execute("DELETE FROM schema_version")
        conn.executemany("INSERT INTO schema_version (version, applied_at) VALUES (?, 't')", [(v,) for v in versions])
        conn.commit()
    finally:
        conn.close()


def _snapshot(db: Path) -> tuple:
    """The main file's bytes, the sidecars present, and the logical content."""
    sidecars = sorted(p.name for p in db.parent.iterdir() if p.name.startswith(db.name + "-"))
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        logical = hashlib.sha256("\n".join(conn.iterdump()).encode()).hexdigest()
    finally:
        conn.close()
    return digest, sidecars, logical


def _marker(db: Path) -> list:
    conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return [r[0] for r in conn.execute("SELECT version FROM schema_version ORDER BY version")]
    finally:
        conn.close()


# ── Newer workspaces are refused at every writing entry point, before any write ─

def test_the_store_refuses_a_newer_workspace_before_writing(workspace):
    _mark(workspace, SCHEMA_VERSION + 1)
    before = _snapshot(workspace)
    with pytest.raises(NewerSchemaError, match=f"schema {SCHEMA_VERSION + 1} is newer"):
        SQLiteStore(workspace)
    assert _snapshot(workspace) == before
    assert _marker(workspace) == [SCHEMA_VERSION + 1]  # never downgraded


def test_the_app_refuses_a_newer_workspace_before_its_startup_migration(workspace):
    _mark(workspace, SCHEMA_VERSION + 1)
    before = _snapshot(workspace)
    with pytest.raises(NewerSchemaError):
        create_app(db_path=workspace, credential_store=lab._NoCredentials())
    assert _snapshot(workspace) == before


def test_a_write_route_refuses_a_workspace_migrated_after_startup(workspace):
    """A newer build may migrate the workspace while this one is running; its next write connection refuses."""
    client = create_app(db_path=workspace, credential_store=lab._NoCredentials()).test_client()
    conn = sqlite3.connect(workspace)
    observations = [r[0] for r in conn.execute("SELECT id FROM observations")]
    conn.close()
    _mark(workspace, SCHEMA_VERSION + 1)
    before = _snapshot(workspace)
    candidate = {"title": "T", "thesis": "T.", "sections": [{"claim": "C.", "supporting_observations": observations,
                                                             "supporting_interpretations": []}]}
    try:
        status = client.post("/api/pipeline/ratify-blueprint", json={"candidate": candidate}).status_code
    except NewerSchemaError:
        status = "raised"
    assert status == "raised" or status >= 500
    assert _snapshot(workspace) == before


def test_the_cli_refuses_a_newer_workspace(workspace, monkeypatch, capsys):
    _mark(workspace, SCHEMA_VERSION + 1)
    before = _snapshot(workspace)
    monkeypatch.setattr(sys, "argv", ["herm", "--db", str(workspace), "stats", str(workspace)])
    with pytest.raises(SystemExit) as exited:
        cli_main.main()
    assert "newer than this build supports" in str(exited.value)
    assert _snapshot(workspace) == before


def test_an_older_exporter_refuses_to_describe_a_newer_workspace(workspace, tmp_path):
    _mark(workspace, SCHEMA_VERSION + 1)
    before = _snapshot(workspace)
    with pytest.raises(NewerSchemaError):
        export_workspace_bundle(workspace, tmp_path / "bundle", generated_at="2026-10-16T00:00:00+00:00")
    assert not (tmp_path / "bundle").exists()
    assert _snapshot(workspace) == before


# ── Downgrade attacks and malformed markers ─────────────────────────────────

@pytest.mark.parametrize("versions", [(SCHEMA_VERSION, SCHEMA_VERSION + 1), (SCHEMA_VERSION - 1, SCHEMA_VERSION)],
                         ids=["newer-row-beside-current", "lower-row-beside-current"])
def test_an_ambiguous_marker_is_refused(workspace, versions):
    """An extra row beside the real one; before ADR-0048, fetchone() picked whichever row came first."""
    _mark(workspace, *versions)
    before = _snapshot(workspace)
    with pytest.raises(SchemaMarkerError, match="ambiguous"):
        SQLiteStore(workspace)
    assert _snapshot(workspace) == before


def test_a_malformed_marker_is_refused(workspace):
    conn = sqlite3.connect(workspace)
    conn.executescript("DROP TABLE schema_version; CREATE TABLE schema_version (version TEXT, applied_at TEXT NOT NULL);"
                       "INSERT INTO schema_version VALUES ('twenty-two', 't');")
    conn.close()
    before = _snapshot(workspace)
    with pytest.raises(SchemaMarkerError, match="malformed"):
        SQLiteStore(workspace)
    assert _snapshot(workspace) == before


def test_a_forged_lower_marker_is_not_detectable_from_the_marker_alone(workspace):
    """Residual risk, recorded in ADR-0048: newer content behind a current marker opens. Not fixed here."""
    conn = sqlite3.connect(workspace)
    conn.execute("CREATE TABLE future_records (id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()
    SQLiteStore(workspace).close()
    assert _marker(workspace) == [SCHEMA_VERSION]


# ── Supported workspaces, migrations and the marker's monotonicity ──────────

def test_supported_workspaces_open_and_the_marker_only_moves_up(workspace):
    SQLiteStore(workspace).close()
    assert _marker(workspace) == [SCHEMA_VERSION]
    _mark(workspace, SCHEMA_VERSION - 1)
    SQLiteStore(workspace).close()
    assert _marker(workspace) == [SCHEMA_VERSION]


def test_a_failed_migration_does_not_advance_the_marker(workspace, monkeypatch):
    _mark(workspace, SCHEMA_VERSION - 1)

    def fail(self):
        raise RuntimeError("migration step failed")

    monkeypatch.setattr(SQLiteStore, "_apply_column_migrations", fail)
    with pytest.raises(RuntimeError, match="migration step failed"):
        SQLiteStore(workspace)
    assert _marker(workspace) == [SCHEMA_VERSION - 1]
    monkeypatch.undo()
    SQLiteStore(workspace).close()
    assert _marker(workspace) == [SCHEMA_VERSION]


def test_a_missing_workspace_is_created_normally(tmp_path):
    db = tmp_path / "new" / "hermeneia.db"
    SQLiteStore(db).close()
    assert _marker(db) == [SCHEMA_VERSION]


# ── Tripwire: every writable connection site has been reviewed ──────────────

# A connection site that is not visibly read-only, with the guard that precedes it. A new site fails this test until
# it is reviewed and added here.
REVIEWED_CONNECTION_SITES = {
    "hermeneia/storage/sqlite.py": 2,       # SQLiteStore (guarded); backup_to() writes a new destination file
    "hermeneia/storage/schema_guard.py": 1,  # the probe itself, which only reads
    "hermeneia/storage/findings_vocabulary.py": 3,  # the schema-22 migration and the R2 procedure's source (both check
                                                    # the marker first; run only at activation), and its new backup file
    "hermeneia/web/app.py": 4,              # startup migration (after the startup guard); _conn (read-only URI);
                                            # _conn_rw (guarded); a new database created through SQLiteStore
    "hermeneia/workspace/export.py": 1,     # read-only URI, after the export guard
    "hermeneia/workspace/restore.py": 2,    # emptiness probe of the target; the target after SQLiteStore (guarded)
    "hermeneia/workspace/lifecycle.py": 3,  # a new workspace after SQLiteStore (guarded); two read-only URIs
    "hermeneia/authoring/service.py": 1,    # after SQLiteStore (guarded)
}
CLI_SITES_AFTER_RESOLVE_DB_TARGET_OR_MAIN = 13


def test_every_writable_connection_site_is_reviewed():
    counts = collections.Counter()
    for path in sorted((ROOT / "hermeneia").rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.search(r"sqlite3\.connect\(", line) and "mode=ro" not in line and ":memory:" not in line:
                counts[str(path.relative_to(ROOT))] += 1
    cli = {path: n for path, n in counts.items() if path.startswith("hermeneia/cli/")}
    assert {path: n for path, n in counts.items() if path not in cli} == REVIEWED_CONNECTION_SITES
    assert sum(cli.values()) == CLI_SITES_AFTER_RESOLVE_DB_TARGET_OR_MAIN, cli
