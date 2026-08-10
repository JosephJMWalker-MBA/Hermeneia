"""Reader Render Preview (Blueprint → evidence-backed essay skeleton).

A fifth tab in the Reader's bottom workstation turns the saved Blueprint into a
structured skeleton — title, thesis, claim sequence, the evidence linked under
each claim, and honest warnings where a claim has none. It is NOT an essay
generator: no Artist call, no generated prose. It reuses the read-only
architect-blueprints endpoints, so no new route and no schema change. These
tests guard the markup, the workstation-mode wiring, endpoint reuse, and that
lineage + gaps are surfaced.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
INDEX = ROOT / "hermeneia" / "web" / "static" / "index.html"
APP = ROOT / "hermeneia" / "web" / "app.py"


def _index() -> str:
    return INDEX.read_text()


def test_render_tab_and_panel_present():
    index = _index()
    assert 'id="cr-bottom-tab-render"' in index
    assert 'data-workstation-mode="render"' in index
    assert 'aria-controls="cr-render-preview"' in index
    assert "_crToggleBottomWorkstation('render')" in index
    assert 'id="cr-render-preview"' in index
    assert 'id="cr-render-preview" hidden' in index


def test_render_is_a_workstation_mode_not_a_separate_drawer():
    index = _index()
    assert "render: document.getElementById('cr-render-preview')" in index
    assert "else if (mode === 'render')" in index
    assert "['cr-bottom-tab-render', () => _crToggleBottomWorkstation('render')]" in index


def test_render_reuses_existing_endpoints_without_new_routes():
    index = _index()
    assert "'/api/architect/blueprints'" in index
    assert "/api/architect/blueprints/" in index
    # No new Flask route: the two architect-blueprints routes are unchanged.
    app = APP.read_text()
    assert app.count('@app.route("/api/architect/blueprints"') == 1
    assert app.count('@app.route("/api/architect/blueprints/<blueprint_id>"') == 1


def test_render_surfaces_lineage_and_gaps():
    index = _index()
    assert "function _crRenderBlueprintSkeleton" in index
    # Evidence lineage comes from the blueprint's linked observations/interps.
    assert "supporting_observations" in index
    assert "obs_texts" in index
    # Unsupported claims are flagged honestly, not hidden.
    assert "No evidence linked yet" in index


def test_render_is_not_an_essay_generator():
    index = _index()
    fn_start = index.index("function _crRenderBlueprintSkeleton")
    fn_region = index[fn_start:fn_start + 4000]
    # The preview reads a Blueprint; it never invokes the Artist / render pipeline.
    assert "/api/architect/generate" not in fn_region
    assert "artist" not in fn_region.lower()


def test_render_copy_and_load_are_exposed():
    index = _index()
    assert "window._crLoadRenderPreview = _crLoadRenderPreview;" in index
    assert "window._crRenderBlueprintSkeleton = _crRenderBlueprintSkeleton;" in index
    assert "window._crCopyRenderSkeleton = _crCopyRenderSkeleton;" in index
