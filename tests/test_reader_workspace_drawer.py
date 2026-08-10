"""Workspace drawer / progressive disclosure (issue #56 slice 4).

An additive grouping of the older pipeline surfaces behind one clear
"Workspace" entry point in the shell header. Reader stays the primary surface;
the existing top-level nav buttons remain in place and reachable. Every drawer
entry reuses the existing e10Go() navigation.

These tests guard the additive scope: the drawer exists with the expected
pipeline entries, the existing nav buttons still exist, Reader is still the
primary reading surface, and nothing from the discarded stash (old Field Notes
side panel) or a later slice (actionable observations) leaks in.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

INDEX_HTML = (
    Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
)


def _index() -> str:
    return INDEX_HTML.read_text()


def _extract_function(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    i = brace
    while i < len(source):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces extracting {signature!r}")


# ── Drawer markup + entries ────────────────────────────────────────────────


def test_workspace_drawer_markup_exists():
    index = _index()
    assert 'id="workspace-drawer"' in index
    assert 'id="workspace-menu-btn"' in index
    assert 'id="runtime-workspace-chip"' in index
    assert 'id="runtime-workspace-name"' in index
    assert "toggleWorkspaceMenu()" in index
    assert 'aria-controls="workspace-drawer"' in index
    assert "Workspace" in index
    assert (
        "Reader is your primary surface." in index
    ), "workspace intent copy missing"


def test_workspace_drawer_includes_expected_pipeline_entries():
    index = _index()
    for stage in ("corpus", "lab", "review", "architect", "reports", "critic", "lineage"):
        assert f"_wsGo('{stage}')" in index, stage
    for label in ("Corpus", "Lab", "Review", "Architect", "Reports", "Critic", "Lineage"):
        assert label in index, label


def test_workspace_drawer_includes_read_only_catalog_without_switching():
    index = _index()
    assert 'id="workspace-catalog"' in index
    assert 'id="workspace-create-form"' in index
    assert 'id="workspace-create-name"' in index
    assert 'id="workspace-create-submit"' in index
    assert "+ New workspace" in index
    assert "Known Workspaces" in index
    assert "/api/runtime/workspace" in index
    assert "/api/workspaces" in index
    assert "workspace-catalog-badge" in index
    assert "Switch workspace" not in index
    assert "_wsSwitch" not in index
    assert "_wsOpenWorkspace" not in index


def test_workspace_create_flow_does_not_reframe_current_upload_or_navigation():
    index = _index()
    drawer = index[
        index.index('<div class="workspace-drawer"') : index.index(
            '<input type="file" id="ws-import-file"'
        )
    ]
    create_fn = _extract_function(index, "async function _wsCreateWorkspace(")
    assert '_wsCloseMenu();obOpenUploadArea()' in drawer
    assert "Add document to this workspace" in index
    assert "Open workspace" not in drawer
    assert "Switch" not in drawer
    assert "obOpenUploadArea" not in create_fn
    assert "e10Go(" not in create_fn


def test_workspace_drawer_entries_reuse_existing_navigation():
    """_wsGo must route through the existing e10Go() handler."""
    index = _index()
    fn = _extract_function(index, "function _wsGo(")
    assert "e10Go(stage)" in fn


# ── Existing navigation stays intact ───────────────────────────────────────


def test_existing_top_level_nav_buttons_still_exist():
    index = _index()
    for nav in (
        "e10Go('corpus')",
        "e10Go('reader')",
        "e10Go('lab')",
        "e10Go('review')",
        "e10Go('architect')",
        "e10Go('reports')",
        "e10Go('critic')",
        "e10Go('lineage')",
    ):
        assert nav in index, nav
    for step in (
        'id="navstep-corpus"',
        'id="navstep-reader"',
        'id="navstep-lab"',
        'id="navstep-review"',
        'id="navstep-architect"',
        'id="navstep-reports"',
        'id="navstep-critic"',
    ):
        assert step in index, step


def test_reader_remains_primary_reading_surface():
    """Reader-first boot (slice 1) and the Reader shell remain intact — the
    drawer does not become the primary routing system."""
    index = _index()
    assert "function _bootDestination(h)" in index
    boot = _extract_function(index, "function _bootDestination(h)")
    # An existing corpus still boots into the reader, not the drawer.
    assert "return 'reader'" in boot
    assert "workspace-drawer" not in boot
    assert 'id="reader"' in index
    assert 'id="reader-workspace"' in index


# ── Scope guards ───────────────────────────────────────────────────────────


def test_no_old_field_notes_side_panel_restored():
    index = _index()
    assert 'id="cr-fieldnotes-panel"' not in index
    assert 'id="cr-fln-tray"' in index


def test_no_actionable_observation_scope_introduced():
    index = _index()
    for token in ("_crOpenObservation", "_crSetObservationStatus", "Interpret in Lab"):
        assert token not in index, token


# ── Behavior: execute the toggle under Node ────────────────────────────────


def test_workspace_drawer_toggle_opens_and_closes():
    if shutil.which("node") is None:  # pragma: no cover - environment guard
        pytest.skip("node runtime not available")
    src = _index()
    toggle = _extract_function(src, "function toggleWorkspaceMenu(")
    harness = f"""
    const _state = {{ drawer: {{ dataset: {{ open: '0' }}, hidden: true }},
                      btn: {{ _a: 'false', setAttribute(k, v) {{ this._a = v; }} }} }};
    const document = {{
      getElementById(id) {{
        if (id === 'workspace-drawer') return _state.drawer;
        if (id === 'workspace-menu-btn') return _state.btn;
        return null;
      }},
    }};
    function _wsRefreshWorkspaceCatalog() {{}}
    {toggle}
    toggleWorkspaceMenu();
    const opened = _state.drawer.dataset.open === '1' && _state.drawer.hidden === false
                   && _state.btn._a === 'true';
    toggleWorkspaceMenu();
    const closed = _state.drawer.dataset.open === '0' && _state.drawer.hidden === true
                   && _state.btn._a === 'false';
    console.log(JSON.stringify({{ opened, closed }}));
    """
    result = subprocess.run(
        ["node", "-e", harness], capture_output=True, text=True, check=True
    )
    import json

    out = json.loads(result.stdout)
    assert out["opened"] is True
    assert out["closed"] is True
