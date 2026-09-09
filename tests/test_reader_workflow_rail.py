"""Reader workstation rail.

The persistent bottom strip is a Reader-anchored resource switcher, not a
second page-navigation system. Resource clicks keep/return the Reader as the
main canvas and open one bottom-workstation mode at a time.
"""
from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


def _rail(index: str) -> str:
    match = re.search(
        r'<nav class="workflow-rail" id="workflow-rail".*?</nav>',
        index,
        re.S,
    )
    assert match
    return match.group(0)


def test_workflow_rail_markup_present():
    index = _index()
    rail = _rail(index)
    assert 'aria-label="Reader workstation"' in rail
    assert "_wfGo(" in rail
    assert "_renderWorkflowRail" in index


def test_workflow_rail_exposes_read_plus_eight_human_resources():
    rail = _rail(_index())
    assert ">Read</button>" in rail

    resources = re.findall(
        r'<button class="wf-step" id="(cr-bottom-resource-[^"]+)" '
        r'data-workstation-resource="([^"]+)".*?>(.*?)</button>',
        rail,
    )
    assert resources == [
        ("cr-bottom-resource-search", "search", "Search"),
        ("cr-bottom-resource-timeline", "timeline", "Timeline"),
        ("cr-bottom-resource-evidence", "evidence", "Evidence"),
        ("cr-bottom-resource-notes", "notes", "Notes"),
        ("cr-bottom-resource-perspective", "perspective", "Perspective"),
        ("cr-bottom-resource-blueprint", "blueprint", "Blueprint"),
        ("cr-bottom-resource-expression", "expression", "Expression"),
        ("cr-bottom-resource-record", "record", "Record"),
    ]


def test_workflow_rail_no_longer_routes_to_legacy_pipeline_pages():
    rail = _rail(_index())
    for legacy_stage in (
        "corpus",
        "lab",
        "review",
        "architect",
        "reports",
        "critic",
        "lineage",
    ):
        assert f"_wfGo('{legacy_stage}')" not in rail


def test_wf_go_returns_to_reader_then_opens_workstation_resource():
    index = _index()
    assert "function _wfGo(target)" in index
    assert "if (target === 'reader')" in index
    assert "if (_currentStageId !== 'reader') e10Go('reader');" in index
    assert "_crCloseBottomWorkstation();" in index
    assert "target === 'notes' ? 'fieldnotes'" in index
    assert "target === 'expression' ? 'voice'" in index
    assert "return _crToggleBottomWorkstationResource(mode);" in index


def test_leaving_reader_collapses_the_workstation():
    index = _index()
    assert "if (id !== 'reader' && _crBottomMode) _crCloseBottomWorkstation();" in index


def test_read_active_state_yields_to_an_open_workstation_resource():
    index = _index()
    assert "_currentStageId === 'reader' && !open" in index
    assert "activeId === 'reader' && !_crBottomMode" in index


def test_old_prev_next_stepper_is_superseded():
    assert ".stage-nav-bar { display: none; }" in _index()


def test_rail_shown_only_once_a_workspace_exists():
    index = _index()
    assert 'id="workflow-rail" hidden' in index
    assert "getElementById('workflow-rail')?.removeAttribute('hidden')" in index
    assert "has-workflow-rail" in index
