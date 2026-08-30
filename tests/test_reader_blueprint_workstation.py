"""Thesis → Blueprint workflow (PR 6).

A forward path from the reader's governing question + captured evidence to a
proposed Intent Hypothesis, living under the Blueprint resource in the shared
bottom workstation. It reuses the existing
extract-blueprint endpoint — no new route, no schema change. These tests guard
the markup, the resource/mode wiring, endpoint reuse, and the seed sources.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
INDEX = ROOT / "hermeneia" / "web" / "static" / "index.html"
APP = ROOT / "hermeneia" / "web" / "app.py"


def _index() -> str:
    return INDEX.read_text()


def test_blueprint_tab_and_panel_present():
    index = _index()
    assert 'id="cr-bottom-resource-blueprint"' in index
    assert 'data-workstation-resource="blueprint"' in index
    assert 'aria-controls="cr-blueprint-draft cr-render-preview cr-critic-audit"' in index
    assert 'id="cr-blueprint-subtab-build"' in index
    assert 'data-workstation-submode="blueprint"' in index
    assert "_crOpenBottomWorkstation('blueprint')" in index
    # Panel exists and starts hidden.
    assert 'id="cr-blueprint-draft"' in index
    assert 'id="cr-blueprint-draft" hidden' in index


def test_blueprint_is_a_workstation_mode_not_a_separate_drawer():
    index = _index()
    # Registered in the mutually-exclusive panel map, the open branch, and the
    # resource bindings — so _crSyncBottomWorkstationState shows only one at a time.
    assert "blueprint: document.getElementById('cr-blueprint-draft')" in index
    assert "else if (mode === 'blueprint')" in index
    assert "['cr-bottom-resource-blueprint', () => _crToggleBottomWorkstationResource('blueprint')]" in index
    assert "if (mode === 'render' || mode === 'critic') return 'blueprint';" in index


def test_blueprint_reuses_existing_endpoint_without_a_new_route():
    index = _index()
    assert "'/api/pipeline/extract-blueprint'" in index
    # No new Flask route: the endpoint is defined exactly once, in app.py.
    app = APP.read_text()
    assert app.count('@app.route("/api/pipeline/extract-blueprint"') == 1


def test_blueprint_seeds_from_question_and_captured_evidence():
    index = _index()
    assert "function _crAssembleBlueprintSeed" in index
    assert "invLoad()?.thesis" in index          # governing question
    assert "/api/investigation-log" in index      # field notes
    assert "/api/e10/observations" in index       # observations
    assert "_crHighlights" in index               # saved highlights


def test_blueprint_draft_and_load_are_exposed():
    index = _index()
    assert "window._crLoadBlueprintDraft = _crLoadBlueprintDraft;" in index
    assert "window._crDraftBlueprint = _crDraftBlueprint;" in index
