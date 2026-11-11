"""First real-use entry: ordinary launch, workspace choice and working mode.

Uses synthetic empty workspaces. No manuscript bytes, publication roots or
database migrations beyond the normal existing workspace create path.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hermeneia.workspace import create_workspace
from hermeneia.workspace.startup import select_initial_workspace
from hermeneia.storage.sqlite import SQLiteStore


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "hermeneia/web/static/index.html"
SCRIPT = ROOT / "hermeneia/web/static/start_screen.js"
STYLES = ROOT / "hermeneia/web/static/start_screen.css"


def test_default_first_launch_creates_one_empty_selectable_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = select_initial_workspace()
    second = select_initial_workspace()
    assert first.kind == "managed"
    assert first.slug == "starter-workspace"
    assert first.db_path == second.db_path
    assert first.db_path.exists()
    assert list((tmp_path / "workspaces").iterdir()) == [tmp_path / "workspaces/starter-workspace"]


def test_standard_launch_prefers_existing_managed_workspace_without_creating_another(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    existing = create_workspace("Toward an Ecology of Intelligence")
    selected = select_initial_workspace()
    assert selected.slug == existing.slug
    assert selected.db_path == existing.db_path
    assert not (tmp_path / "workspaces/starter-workspace").exists()


def test_standard_launch_prefers_legacy_gatsby_only_if_it_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_workspace("First Real Book")
    legacy = tmp_path / "build/hermeneia.db"
    legacy.parent.mkdir(parents=True)
    SQLiteStore(legacy).close()
    chosen = select_initial_workspace()
    assert chosen.kind == "legacy"
    assert chosen.slug == "gatsby"
    assert chosen.db_path.resolve() == legacy.resolve()


def test_start_surface_and_launcher_contracts():
    html = INDEX.read_text()
    script = SCRIPT.read_text()
    css = STYLES.read_text()
    package = (ROOT / "pyproject.toml").read_text()
    cli = (ROOT / "hermeneia/cli/main.py").read_text()
    server = (ROOT / "scripts/herm_server.py").read_text()

    for name in [
        "herm-start-screen",
        "herm-start-workspaces",
        "herm-start-create-form",
        "herm-start-mode",
        "herm-start-continue",
        "herm-start-status",
    ]:
        assert name in html
    assert 'onclick="hermStartOpen()"' in html
    assert 'src="/static/start_screen.js"' in html
    assert 'href="/static/start_screen.css"' in html
    assert 'hermeneia:mounted' in html
    assert "start_screen" in css or "herm-start" in css
    assert "static/*.js" in package and "static/*.css" in package

    assert "if not args.direct" in cli
    assert "if not args.direct" in server
    assert "--direct" in cli and "--direct" in server
    assert "select_initial_workspace()" in cli
    assert "select_initial_workspace()" in server
    assert "workspace_switch" in script
    assert "window.location.reload()" in script
    assert "RETURN_MODE_KEY" in script
    assert "new Function" not in script
    assert "/api/workspaces/" in script
    assert "authorJournalOpen" in script
    assert "Blank manuscript editing and KDP setup are still in development." in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_start_screen_javascript_syntax():
    result = subprocess.run(
        ["node", "--check", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
