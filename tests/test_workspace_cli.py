"""CLI-facing workspace lifecycle behavior."""
from __future__ import annotations

from pathlib import Path

import pytest

from hermeneia.cli.workspace_cmd import (
    cmd_workspace_create,
    cmd_workspace_inspect,
    cmd_workspace_list,
    resolve_cli_serve_db,
)
from hermeneia.workspace import WorkspaceLifecycleError


def test_workspace_create_and_list_output(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    cmd_workspace_create("The Second Sale")
    created = capsys.readouterr().out
    assert "Created workspace" in created
    assert "Name: The Second Sale" in created
    assert "Slug: the-second-sale" in created
    assert "Serve: herm serve --workspace the-second-sale" in created

    cmd_workspace_list()
    listed = capsys.readouterr().out
    assert "managed" in listed
    assert "the-second-sale" in listed
    assert "The Second Sale" in listed
    assert "workspaces/the-second-sale/hermeneia.db" in listed


def test_workspace_inspect_output(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    cmd_workspace_create("The Second Sale")
    capsys.readouterr()

    cmd_workspace_inspect("The Second Sale")
    inspected = capsys.readouterr().out
    assert "Name: The Second Sale" in inspected
    assert "Kind: managed" in inspected
    assert "Documents: 0" in inspected
    assert "Database: workspaces/the-second-sale/hermeneia.db" in inspected


def test_workspace_create_errors_on_collision(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd_workspace_create("The Second Sale")

    with pytest.raises(SystemExit, match="workspace already exists"):
        cmd_workspace_create("The Second Sale")


def test_cli_serve_resolution_rejects_global_and_command_db_together():
    with pytest.raises(
        WorkspaceLifecycleError,
        match="provide --db either before or after serve",
    ):
        resolve_cli_serve_db(
            global_db="build/hermeneia.db",
            command_db="other.db",
            workspace_selector=None,
        )


def test_cli_serve_resolution_accepts_named_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd_workspace_create("The Second Sale")

    assert resolve_cli_serve_db(
        global_db=None,
        command_db=None,
        workspace_selector="The Second Sale",
    ) == Path("workspaces/the-second-sale/hermeneia.db")
