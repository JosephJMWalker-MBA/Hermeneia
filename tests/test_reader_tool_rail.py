"""Reader tool rail + drawer (issue #56 slice 3).

An additive, progressively enhancing access pattern: a compact rail (and an
optional drawer of descriptions) that scrolls to the Reader tools already on
the page. It does NOT move or rewrite any panel, and core reading never
depends on it.

These tests guard the additive scope: the rail/drawer exist with the expected
entries, every existing panel/form is still present in its current location,
and nothing from later slices (workspace drawer, actionable observations) or
the discarded stash (old Field Notes side panel) leaks in.
"""
from __future__ import annotations

from pathlib import Path

INDEX_HTML = (
    Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
)


def _index() -> str:
    return INDEX_HTML.read_text()


# ── Rail + drawer markup ───────────────────────────────────────────────────


def test_tool_rail_markup_exists_in_reader():
    index = _index()
    assert 'id="cr-tool-rail"' in index
    assert "cr-rail-btn" in index
    assert "_crRailGo(" in index
    # The rail sits above the book surface, after the compass.
    assert index.index('id="cr-tool-rail"') < index.index('id="cr-page-view"')
    assert index.index('id="cr-question-compass"') < index.index('id="cr-tool-rail"')


def test_tool_drawer_markup_exists():
    index = _index()
    assert 'id="cr-tool-drawer"' in index
    assert 'id="cr-tool-drawer-btn"' in index
    assert "_crToggleToolDrawer()" in index
    assert 'aria-controls="cr-tool-drawer"' in index


def test_expected_tool_entries_exist():
    index = _index()
    for key in (
        "'question'",
        "'companion'",
        "'capture'",
        "'trail'",
        "'fieldnotes'",
        "'highlights'",
        "'observations'",
    ):
        assert f"_crRailGo({key})" in index, key
    for label in (
        "Question",
        "Companion",
        "Inspector",
        "Trail",
        "Field Notes",
        "Highlights",
        "Observations",
    ):
        assert label in index, label


def test_rail_targets_existing_panels_only():
    """Each rail key resolves to a panel id that already exists in the DOM."""
    index = _index()
    for panel_id in (
        "cr-question-panel",
        "cr-companion-panel",
        "cr-capture-panel",
        "cr-trail-panel",
        "cr-fln-tray",
        "cr-highlights-panel",
        "cr-related-panel",
    ):
        assert f"'{panel_id}'" in index, f"{panel_id} not mapped"
        assert f'id="{panel_id}"' in index, f"{panel_id} panel missing"


# ── Existing surfaces remain intact ────────────────────────────────────────


def test_existing_panels_and_forms_still_exist():
    index = _index()
    for panel_id in (
        'id="cr-question-panel"',
        'id="cr-companion-panel"',
        'id="cr-capture-panel"',
        'id="cr-trail-panel"',
        'id="cr-highlights-panel"',
        'id="cr-related-panel"',
        'id="cr-fln-tray"',
    ):
        assert panel_id in index, panel_id
    # Question form + compass from earlier slices remain.
    assert "_crRenderQuestionCard" in index
    assert "Keep this question" in index
    assert 'id="cr-question-compass"' in index


def test_field_notes_stays_in_footer_tray_not_a_side_panel():
    """The discarded stash's old Field Notes side panel must not return."""
    index = _index()
    assert 'id="cr-fieldnotes-panel"' not in index
    assert 'id="cr-fln-tray"' in index


# ── Out-of-scope guards (later #56 slices) ─────────────────────────────────


def test_no_workspace_drawer_scope_in_this_pr():
    index = _index()
    assert 'id="workspace-drawer"' not in index
    assert "toggleWorkspaceMenu(" not in index


def test_no_actionable_observation_scope_in_this_pr():
    index = _index()
    for token in ("_crOpenObservation", "_crSetObservationStatus", "Interpret in Lab"):
        assert token not in index, token
