"""Runtime workspace lifecycle.

These tests enforce the narrow product slice: managed workspaces isolate DB,
uploads, calibration, and durable identity, while the legacy Gatsby DB remains
the default runtime path and is never moved or rewritten by listing.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.workspace import (
    WorkspaceLifecycleError,
    create_workspace,
    inspect_workspace,
    list_workspaces,
    resolve_serve_db,
    resolve_workspace_db,
    slugify_workspace_name,
)


def _identity_rows(db_path: Path) -> list[tuple[str, str | None]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT workspace_id, workspace_name FROM workspace_identity"
        ).fetchall()
    finally:
        conn.close()


def test_create_workspace_builds_isolated_runtime_container(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    record = create_workspace("The Second Sale")

    assert record.kind == "managed"
    assert record.slug == "the-second-sale"
    assert record.name == "The Second Sale"
    assert record.db_path == Path("workspaces/the-second-sale/hermeneia.db")
    assert record.db_path.exists()
    assert (tmp_path / "workspaces/the-second-sale/uploads").is_dir()

    calibration = json.loads(
        (tmp_path / "workspaces/the-second-sale/calibration.json").read_text()
    )
    assert calibration == {"calibration_schema": "1.0", "records": {}}

    rows = _identity_rows(record.db_path)
    assert len(rows) == 1
    assert rows[0][0] == record.workspace_id
    assert rows[0][1] == "The Second Sale"


def test_list_and_resolve_include_legacy_gatsby_without_mutating_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy_db = tmp_path / "build/hermeneia.db"
    legacy_db.parent.mkdir()
    SQLiteStore(legacy_db).close()

    before = _identity_rows(legacy_db)
    assert before == []

    records = list_workspaces()
    assert [(r.kind, r.slug, r.name, r.db_path) for r in records] == [
        ("legacy", "gatsby", "Gatsby", Path("build/hermeneia.db"))
    ]
    assert inspect_workspace("Gatsby").db_path == Path("build/hermeneia.db")
    assert inspect_workspace("legacy").db_path == Path("build/hermeneia.db")
    assert resolve_workspace_db("current") == Path("build/hermeneia.db")

    after = _identity_rows(legacy_db)
    assert after == [], "listing legacy Gatsby must not create or rewrite identity"


def test_list_and_resolve_by_name_slug_and_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    created = create_workspace("The Second Sale")

    records = list_workspaces()
    assert [r.slug for r in records] == ["the-second-sale"]
    assert inspect_workspace("the-second-sale") == created
    assert inspect_workspace("The Second Sale") == created
    assert inspect_workspace(created.workspace_id or "") == created


def test_create_refuses_colliding_workspace_slug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_workspace("The Second Sale")

    with pytest.raises(WorkspaceLifecycleError, match="already exists"):
        create_workspace("The Second Sale")


def test_serve_resolution_preserves_db_default_and_rejects_ambiguity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    created = create_workspace("The Second Sale")

    assert resolve_serve_db() == Path("build/hermeneia.db")
    assert resolve_serve_db(db_arg="custom/hermeneia.db") == Path("custom/hermeneia.db")
    assert resolve_serve_db(workspace_selector="The Second Sale") == created.db_path

    with pytest.raises(WorkspaceLifecycleError, match="either --db or --workspace"):
        resolve_serve_db(
            db_arg="custom/hermeneia.db",
            workspace_selector="The Second Sale",
        )


def test_workspace_slug_is_stable_and_strict():
    assert slugify_workspace_name("The Second Sale") == "the-second-sale"
    with pytest.raises(WorkspaceLifecycleError):
        slugify_workspace_name("   ")
