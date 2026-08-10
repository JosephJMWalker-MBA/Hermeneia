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
    _assert_sanitized(body)


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

    assert body["workspace"] == {
        "id": None,
        "name": "Gatsby",
        "slug": "gatsby",
        "kind": "legacy",
        "managed": False,
    }
    assert second == body
    assert second_catalog == catalog
    assert _identity_rows(legacy) == []
    _assert_sanitized(body)
    _assert_sanitized(catalog)


def test_runtime_workspace_reports_custom_db_without_path_leak(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_workspace("The Second Sale")
    custom = tmp_path / "custom" / "outside.db"
    SQLiteStore(custom).close()
    client = create_app(db_path=custom).test_client()

    current = client.get("/api/runtime/workspace").get_json()
    catalog = client.get("/api/workspaces").get_json()

    assert current["workspace"] == {
        "id": None,
        "name": "Custom workspace",
        "slug": None,
        "kind": "custom",
        "managed": False,
    }
    assert all(workspace["is_active"] is False for workspace in catalog["workspaces"])
    _assert_sanitized(current)
    _assert_sanitized(catalog)


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
