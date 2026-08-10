"""Read-only runtime workspace identity and catalog (issue #125 Slice A)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import (
    RESERVED_WORKSPACE_SELECTORS,
    create_workspace,
    set_workspace_name,
)


def _identity_rows(db_path: Path) -> list[tuple[str, str | None]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT workspace_id, workspace_name FROM workspace_identity"
        ).fetchall()
    finally:
        conn.close()


def _assert_sanitized(payload: dict) -> None:
    text = json.dumps(payload)
    for forbidden in ("hermeneia.db", "workspaces/", "uploads", "build/"):
        assert forbidden not in text
    for key in ("db_path", "root_path", "uploads_path", "build_path"):
        assert key not in text


def _assert_runtime_scope_safe(workspace: dict) -> None:
    for key in ("runtime_scope", "draft_migration_scope"):
        assert key in workspace
    text = json.dumps({
        "runtime_scope": workspace["runtime_scope"],
        "draft_migration_scope": workspace["draft_migration_scope"],
    })
    for forbidden in ("/private", "/home", "hermeneia.db", "uploads", "build/"):
        assert forbidden not in text
    assert "/" not in workspace["runtime_scope"]


def test_runtime_workspace_reports_managed_backend_truth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    record = create_workspace("The Second Sale")
    client = create_app(db_path=record.db_path).test_client()

    body = client.get("/api/runtime/workspace").get_json()

    assert body["workspace"]["id"] == record.workspace_id
    assert body["workspace"]["name"] == "The Second Sale"
    assert body["workspace"]["slug"] == "the-second-sale"
    assert body["workspace"]["kind"] == "managed"
    assert body["workspace"]["managed"] is True
    assert body["workspace"]["runtime_scope"] == f"managed:{record.workspace_id}"
    _assert_runtime_scope_safe(body["workspace"])
    _assert_sanitized(body)


def test_runtime_workspace_scope_is_stable_for_same_managed_workspace_and_distinct(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    second = create_workspace("Research Notes")

    first_scope = create_app(db_path=first.db_path).test_client().get(
        "/api/runtime/workspace"
    ).get_json()["workspace"]["runtime_scope"]
    first_reload_scope = create_app(db_path=first.db_path).test_client().get(
        "/api/runtime/workspace"
    ).get_json()["workspace"]["runtime_scope"]
    second_scope = create_app(db_path=second.db_path).test_client().get(
        "/api/runtime/workspace"
    ).get_json()["workspace"]["runtime_scope"]

    assert first_scope == f"managed:{first.workspace_id}"
    assert first_reload_scope == first_scope
    assert second_scope == f"managed:{second.workspace_id}"
    assert second_scope != first_scope


def test_runtime_workspace_reports_legacy_gatsby_without_mutating_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "build" / "hermeneia.db"
    SQLiteStore(legacy).close()
    assert _identity_rows(legacy) == []
    client = create_app(db_path=Path("build/hermeneia.db")).test_client()

    body = client.get("/api/runtime/workspace").get_json()
    second = client.get("/api/runtime/workspace").get_json()
    catalog = client.get("/api/workspaces").get_json()
    second_catalog = client.get("/api/workspaces").get_json()

    assert body["workspace"]["id"] is None
    assert body["workspace"]["name"] == "Gatsby"
    assert body["workspace"]["slug"] == "gatsby"
    assert body["workspace"]["kind"] == "legacy"
    assert body["workspace"]["managed"] is False
    assert body["workspace"]["runtime_scope"] == "legacy:gatsby"
    _assert_runtime_scope_safe(body["workspace"])
    assert second == body
    assert second_catalog == catalog
    assert _identity_rows(legacy) == []
    _assert_sanitized(body)
    _assert_sanitized(catalog)


def test_runtime_workspace_legacy_scope_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "build" / "hermeneia.db"
    SQLiteStore(legacy).close()

    first = create_app(db_path=Path("build/hermeneia.db")).test_client().get(
        "/api/runtime/workspace"
    ).get_json()
    second = create_app(db_path=Path("build/hermeneia.db")).test_client().get(
        "/api/runtime/workspace"
    ).get_json()

    assert first["workspace"]["runtime_scope"] == "legacy:gatsby"
    assert second["workspace"]["runtime_scope"] == "legacy:gatsby"
    _assert_runtime_scope_safe(first["workspace"])


def test_runtime_workspace_reports_custom_db_without_path_leak(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_workspace("The Second Sale")
    custom = tmp_path / "custom" / "outside.db"
    SQLiteStore(custom).close()
    client = create_app(db_path=custom).test_client()

    current = client.get("/api/runtime/workspace").get_json()
    catalog = client.get("/api/workspaces").get_json()

    assert current["workspace"]["id"] is None
    assert current["workspace"]["name"] == "Custom workspace"
    assert current["workspace"]["slug"] is None
    assert current["workspace"]["kind"] == "custom"
    assert current["workspace"]["managed"] is False
    assert current["workspace"]["runtime_scope"].startswith("custom:")
    _assert_runtime_scope_safe(current["workspace"])
    assert all(workspace["is_active"] is False for workspace in catalog["workspaces"])
    assert all("runtime_scope" not in workspace for workspace in catalog["workspaces"])
    _assert_sanitized(current)
    _assert_sanitized(catalog)


def test_custom_runtime_scope_without_identity_is_safe_stable_and_path_opaque(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    first_custom = tmp_path / "custom" / "outside.db"
    second_custom = tmp_path / "custom" / "other.db"
    SQLiteStore(first_custom).close()
    SQLiteStore(second_custom).close()

    first = create_app(db_path=first_custom).test_client().get(
        "/api/runtime/workspace"
    ).get_json()["workspace"]
    first_reload = create_app(db_path=first_custom).test_client().get(
        "/api/runtime/workspace"
    ).get_json()["workspace"]
    second = create_app(db_path=second_custom).test_client().get(
        "/api/runtime/workspace"
    ).get_json()["workspace"]

    assert first["runtime_scope"].startswith("custom:")
    assert first_reload["runtime_scope"] == first["runtime_scope"]
    assert second["runtime_scope"].startswith("custom:")
    assert second["runtime_scope"] != first["runtime_scope"]
    _assert_runtime_scope_safe(first)
    _assert_runtime_scope_safe(second)


def test_runtime_workspace_uses_custom_durable_identity_when_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom" / "outside.db"
    SQLiteStore(custom).close()
    conn = sqlite3.connect(custom)
    try:
        identity = set_workspace_name(conn, "Research Notes")
    finally:
        conn.close()
    client = create_app(db_path=custom).test_client()

    body = client.get("/api/runtime/workspace").get_json()

    assert body["workspace"]["id"] == identity["workspace_id"]
    assert body["workspace"]["name"] == "Research Notes"
    assert body["workspace"]["slug"] is None
    assert body["workspace"]["kind"] == "custom"
    assert body["workspace"]["managed"] is False
    assert body["workspace"]["runtime_scope"] == f"custom:{identity['workspace_id']}"
    _assert_runtime_scope_safe(body["workspace"])
    _assert_sanitized(body)


def test_workspace_catalog_is_sanitized_and_marks_only_actual_active(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "build" / "hermeneia.db"
    SQLiteStore(legacy).close()
    active = create_workspace("The Second Sale")
    create_workspace("Research Notes")
    client = create_app(db_path=active.db_path).test_client()

    body = client.get("/api/workspaces").get_json()
    rows = body["workspaces"]

    assert [row["slug"] for row in rows] == ["gatsby", "research-notes", "the-second-sale"]
    assert [row["is_active"] for row in rows] == [False, False, True]
    assert all("document_count" not in row for row in rows)
    assert all("runtime_scope" not in row for row in rows)
    assert all("draft_migration_scope" not in row for row in rows)
    assert rows[0]["managed"] is False
    assert rows[-1]["managed"] is True
    _assert_sanitized(body)


def test_workspace_post_creates_managed_workspace_without_switching(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    active = create_workspace("The Second Sale")
    client = create_app(db_path=active.db_path).test_client()

    created = client.post("/api/workspaces", json={"name": "Research Notes"})
    runtime = client.get("/api/runtime/workspace").get_json()
    catalog = client.get("/api/workspaces").get_json()

    assert created.status_code == 201
    body = created.get_json()
    assert body["workspace"]["name"] == "Research Notes"
    assert body["workspace"]["slug"] == "research-notes"
    assert body["workspace"]["kind"] == "managed"
    assert body["workspace"]["managed"] is True
    assert body["workspace"]["is_active"] is False
    assert (tmp_path / "workspaces/research-notes/hermeneia.db").exists()

    assert runtime["workspace"]["name"] == "The Second Sale"
    assert runtime["workspace"]["slug"] == "the-second-sale"
    rows = {row["slug"]: row for row in catalog["workspaces"]}
    assert rows["the-second-sale"]["is_active"] is True
    assert rows["research-notes"]["is_active"] is False
    _assert_sanitized(body)
    _assert_sanitized(runtime)
    _assert_sanitized(catalog)


def test_workspace_post_does_not_change_active_runtime_draft_scope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    active = create_workspace("The Second Sale")
    client = create_app(db_path=active.db_path).test_client()

    before = client.get("/api/runtime/workspace").get_json()["workspace"]
    created = client.post("/api/workspaces", json={"name": "Research Notes"})
    after = client.get("/api/runtime/workspace").get_json()["workspace"]

    assert created.status_code == 201
    assert "runtime_scope" not in created.get_json()["workspace"]
    assert before["runtime_scope"] == f"managed:{active.workspace_id}"
    assert after["runtime_scope"] == before["runtime_scope"]
    assert after["name"] == "The Second Sale"


def test_workspace_post_duplicate_returns_conflict_with_sanitized_identity(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    active = create_workspace("The Second Sale")
    existing = create_workspace("Research Notes")
    client = create_app(db_path=active.db_path).test_client()

    response = client.post("/api/workspaces", json={"name": "Research Notes"})

    assert response.status_code == 409
    body = response.get_json()
    assert body["error"] == "workspace already exists: research-notes"
    assert body["workspace"]["id"] == existing.workspace_id
    assert body["workspace"]["name"] == "Research Notes"
    assert body["workspace"]["slug"] == "research-notes"
    assert body["workspace"]["is_active"] is False
    assert client.get("/api/runtime/workspace").get_json()["workspace"]["slug"] == "the-second-sale"
    _assert_sanitized(body)


@pytest.mark.parametrize("name", ["", "   ", "***"])
def test_workspace_post_rejects_blank_or_invalid_name(tmp_path, monkeypatch, name):
    monkeypatch.chdir(tmp_path)
    active = create_workspace("The Second Sale")
    client = create_app(db_path=active.db_path).test_client()

    response = client.post("/api/workspaces", json={"name": name})

    assert response.status_code == 400
    assert "workspace name must contain letters or numbers" in response.get_json()["error"]
    assert client.get("/api/runtime/workspace").get_json()["workspace"]["slug"] == "the-second-sale"
    _assert_sanitized(response.get_json())


@pytest.mark.parametrize(
    "name",
    sorted(RESERVED_WORKSPACE_SELECTORS)
    + [" Gatsby ", "LEGACY", "Current", "default", "../gatsby"],
)
def test_workspace_post_rejects_reserved_selector_aliases(tmp_path, monkeypatch, name):
    monkeypatch.chdir(tmp_path)
    active = create_workspace("The Second Sale")
    client = create_app(db_path=active.db_path).test_client()

    response = client.post("/api/workspaces", json={"name": name})

    assert response.status_code == 400
    assert "workspace name is reserved" in response.get_json()["error"]
    assert client.get("/api/runtime/workspace").get_json()["workspace"]["slug"] == "the-second-sale"
    _assert_sanitized(response.get_json())


@pytest.mark.parametrize(
    ("name", "expected_slug", "expected_status"),
    [
        ("../../outside", "outside", 201),
        ("../gatsby", None, 400),
        ("/tmp/foo", "tmp-foo", 201),
    ],
)
def test_workspace_post_traversal_like_names_never_escape_workspace_root(
    tmp_path,
    monkeypatch,
    name,
    expected_slug,
    expected_status,
):
    monkeypatch.chdir(tmp_path)
    active = create_workspace("The Second Sale")
    client = create_app(db_path=active.db_path).test_client()

    response = client.post("/api/workspaces", json={"name": name})

    assert response.status_code == expected_status
    body = response.get_json()
    if expected_status == 201:
        assert body["workspace"]["slug"] == expected_slug
        assert body["workspace"]["is_active"] is False
        assert (tmp_path / f"workspaces/{expected_slug}/hermeneia.db").exists()
        assert not (tmp_path / "outside").exists()
    else:
        assert "workspace name is reserved" in body["error"]
    assert client.get("/api/runtime/workspace").get_json()["workspace"]["slug"] == "the-second-sale"
    _assert_sanitized(body)
