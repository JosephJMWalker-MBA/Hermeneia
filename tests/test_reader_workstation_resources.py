"""Reader workstation resources (#154).

The bottom workstation is a human-facing resource tray, not a peer list of
pipeline labels. These tests keep the public IA stable while allowing the
existing internal modes to remain the implementation detail.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name}"
    return match.group(0)


def test_persistent_workstation_rail_has_eight_human_resource_tabs():
    index = _index()
    rail = re.search(
        r'<nav class="workflow-rail" id="workflow-rail".*?</nav>',
        index,
        re.S,
    )
    assert rail
    top_tabs = re.findall(
        r'<button class="wf-step" id="(cr-bottom-resource-[^"]+)" '
        r'data-workstation-resource="([^"]+)".*?>(.*?)</button>',
        rail.group(0),
    )

    assert top_tabs == [
        ("cr-bottom-resource-search", "search", "Search"),
        ("cr-bottom-resource-timeline", "timeline", "Timeline"),
        ("cr-bottom-resource-evidence", "evidence", "Evidence"),
        ("cr-bottom-resource-notes", "notes", "Notes"),
        ("cr-bottom-resource-perspective", "perspective", "Perspective"),
        ("cr-bottom-resource-blueprint", "blueprint", "Blueprint"),
        ("cr-bottom-resource-expression", "expression", "Expression"),
        ("cr-bottom-resource-record", "record", "Record"),
    ]
    for inherited in ("render", "critic", "voice", "draft"):
        assert f'data-workstation-resource="{inherited}"' not in index
        assert f'id="cr-bottom-tab-{inherited}"' not in index

    shell_head = re.search(
        r'<div class="cr-bottom-workstation-head">(?P<body>.*?)</div>\s*'
        r'<div class="cr-bottom-workstation-body">',
        index,
        re.S,
    )
    assert shell_head
    assert "data-workstation-resource" not in shell_head.group("body")


def test_blueprint_and_expression_have_nested_views_not_peer_resource_tabs():
    index = _index()

    assert 'id="cr-blueprint-subtabs"' in index
    assert 'id="cr-blueprint-subtab-build"' in index
    assert 'data-workstation-submode="blueprint"' in index
    assert 'id="cr-blueprint-subtab-structure"' in index
    assert 'data-workstation-submode="render"' in index
    assert 'id="cr-blueprint-subtab-check"' in index
    assert 'data-workstation-submode="critic"' in index

    assert 'id="cr-expression-subtabs"' in index
    assert 'id="cr-expression-subtab-voice"' in index
    assert 'data-workstation-submode="voice"' in index
    assert 'id="cr-expression-subtab-draft"' in index
    assert 'data-workstation-submode="draft"' in index


def test_persistent_rail_stays_scrollable_and_uses_center_collapse_handle():
    index = _index()

    rail_css = re.search(r"\.workflow-rail \{(?P<body>.*?)\n\}", index, re.S)
    step_css = re.search(r"\.wf-step \{(?P<body>.*?)\n\}", index, re.S)
    assert rail_css and step_css
    assert "overflow-x: auto" in rail_css.group("body")
    assert "white-space: nowrap" in step_css.group("body")

    assert 'id="cr-bottom-collapse-handle"' in index
    assert 'aria-label="Collapse bottom workstation"' in index
    assert 'class="cr-bottom-workstation-close"' not in index

    handle_css = re.search(r"\.cr-bottom-collapse-handle \{(?P<body>.*?)\n\}", index, re.S)
    assert handle_css
    assert "position: fixed" in handle_css.group("body")
    assert "left: 50%" in handle_css.group("body")
    assert "transform: translateX(-50%)" in handle_css.group("body")
    assert "z-index: 9702" in handle_css.group("body")


def test_sync_maps_internal_modes_to_public_resources_and_nested_tabs():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for workstation resource state test")

    html = _index()
    script = (
        "let _crBottomMode = 'render';\n"
        "const elements = {};\n"
        "function makeEl(id){ return elements[id] = { id, hidden:false, dataset:{}, attrs:{}, "
        "classList:{classes:new Set(), toggle(name,on){ on ? this.classes.add(name) : this.classes.delete(name);}}, "
        "getAttribute(name){ return this.attrs[name]; }, setAttribute(name,value){ this.attrs[name]=String(value); } }; }\n"
        "['cr-bottom-workstation','corpus-search','attn-timeline','evidence-board','cr-fln-tray','cr-perspective-run',"
        "'cr-blueprint-draft','cr-render-preview','cr-critic-audit','cr-voice-profile','cr-artist-draft',"
        "'cr-record-ledger','cr-blueprint-subtabs','cr-expression-subtabs'].forEach(makeEl);\n"
        "elements['cr-bottom-workstation'].hidden = false;\n"
        "const resourceBtns = ['search','timeline','evidence','notes','perspective','blueprint','expression','record'].map(r => ({"
        "dataset:{workstationResource:r}, attrs:{role:'tab'}, classList:{classes:new Set(), toggle(n,on){ on ? this.classes.add(n) : this.classes.delete(n);}},"
        "getAttribute(n){ return this.attrs[n]; }, setAttribute(n,v){ this.attrs[n]=String(v); }}));\n"
        "const subBtns = ['blueprint','render','critic','voice','draft'].map(m => ({"
        "dataset:{workstationSubmode:m}, attrs:{role:'tab'}, classList:{classes:new Set(), toggle(n,on){ on ? this.classes.add(n) : this.classes.delete(n);}},"
        "getAttribute(n){ return this.attrs[n]; }, setAttribute(n,v){ this.attrs[n]=String(v); }}));\n"
        "global.document = { body:{classList:{state:{}, toggle(n,on){ this.state[n]=!!on; }}}, "
        "getElementById(id){ return elements[id] || null; }, "
        "querySelectorAll(sel){ if(sel==='[data-workstation-resource]') return resourceBtns; if(sel==='[data-workstation-submode]') return subBtns; return []; } };\n"
        + _extract_fn(html, "_crBottomPanels")
        + _extract_fn(html, "_crWorkstationResourceForMode")
        + _extract_fn(html, "_crSyncBottomWorkstationState")
        + "_crSyncBottomWorkstationState();\n"
        + "process.stdout.write(JSON.stringify({"
        "resource: elements['cr-bottom-workstation'].dataset.resource,"
        "renderHidden: elements['cr-render-preview'].hidden,"
        "blueprintTabsHidden: elements['cr-blueprint-subtabs'].hidden,"
        "expressionTabsHidden: elements['cr-expression-subtabs'].hidden,"
        "blueprintResourceActive: resourceBtns.find(b => b.dataset.workstationResource==='blueprint').classList.classes.has('active'),"
        "renderSubtabActive: subBtns.find(b => b.dataset.workstationSubmode==='render').classList.classes.has('active')"
        "}));\n"
    )
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    state = json.loads(result.stdout)

    assert state == {
        "resource": "blueprint",
        "renderHidden": False,
        "blueprintTabsHidden": False,
        "expressionTabsHidden": True,
        "blueprintResourceActive": True,
        "renderSubtabActive": True,
    }


def test_field_notes_shortcut_still_opens_bottom_workstation():
    index = _index()
    rail_go = _extract_fn(index, "_crRailGo")
    fln_toggle = _extract_fn(index, "flnToggleTray")

    assert "if (key === 'fieldnotes')" in rail_go
    assert "flnToggleTray(true)" in rail_go
    assert "_crOpenBottomWorkstation('fieldnotes')" in fln_toggle


def test_newer_workstation_surfaces_share_content_gutter_without_double_padding_notes():
    index = _index()

    for selector in (
        "#cr-perspective-run > .cr-fln-body",
        "#cr-blueprint-draft > .cr-fln-body",
        "#cr-render-preview > .cr-fln-body",
        "#cr-critic-audit > .cr-fln-body",
        "#cr-voice-profile > .cr-fln-body",
        "#cr-artist-draft > .cr-fln-body",
        "#cr-record-ledger > .cr-fln-body",
    ):
        assert selector in index
    assert "padding: 12px 16px 18px;" in index
    assert ".cr-fln-inner { max-width: 900px; margin: 0 auto; padding: 14px 16px 18px; }" in index
