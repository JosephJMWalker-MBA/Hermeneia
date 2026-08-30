"""Reader return-to-book orchestration (#126)."""
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
    match = re.search(r"(?:^|\n)(?:async\s+)?function " + re.escape(name) + r"\(", html)
    assert match, f"could not find function {name}"
    start = match.start()
    if html[start] == "\n":
        start += 1
    brace = html.find("{", start)
    assert brace >= 0
    depth = 0
    for pos in range(brace, len(html)):
        char = html[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[start : pos + 1] + "\n"
    raise AssertionError(f"could not extract function {name}")


def _run_node(script: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader return-to-book UI test")
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_activity_driven_field_notes_reflection_is_disabled() -> None:
    html = _index()
    render_page = _extract_fn(html, "_crRenderPage")
    save_highlight = _extract_fn(html, "_crSaveHighlight")
    activity_tick = _extract_fn(html, "_flnActivityTick")

    assert "_flnActivityTick();" not in render_page
    assert "_flnActivityTick();" not in save_highlight
    assert "let _flnActivity" not in html
    assert "_FLN_ACTIVITY_THRESHOLD" not in html
    assert "_FLN_MIN_INTERVAL_MS" not in html
    assert "_flnLastMark" not in html
    assert "Automatic Field Notes reflection is disabled for now." in html
    assert "return;" in activity_tick


def test_forward_backward_navigation_does_not_auto_prompt() -> None:
    html = _index()
    script = (
        "let _crPage=1;let _crTotalPages=12;let renders=0;let promptCalls=0;let scrollCalls=0;"
        "function _crRenderPage(){renders++;}"
        "function cmpMarkOnboardingStep(){}"
        "const window={scrollTo(){scrollCalls++;}};"
        "const document={getElementById(id){return id==='cr-page-view'?{offsetTop:120}:null;}};"
        "function _flnShowPrompt(){promptCalls++;}"
        + _extract_fn(html, "_flnActivityTick")
        + _extract_fn(html, "_crNextPage")
        + _extract_fn(html, "_crPrevPage")
        + """
for (let i = 0; i < 9; i++) _crNextPage();
for (let i = 0; i < 8; i++) _crPrevPage();
for (let i = 0; i < 20; i++) _flnActivityTick();
process.stdout.write(JSON.stringify({page:_crPage,renders,promptCalls,scrollCalls}));
"""
    )
    assert _run_node(script) == {"page": 2, "renders": 17, "promptCalls": 0, "scrollCalls": 17}


def test_highlight_save_path_does_not_trigger_field_notes_prompt() -> None:
    html = _index()
    save_highlight = _extract_fn(html, "_crSaveHighlight")

    assert "method: 'POST'" in save_highlight
    assert "'/api/reader/highlights'" in save_highlight
    assert "_flnActivityTick()" not in save_highlight
    assert "_flnShowPrompt()" not in save_highlight


def _workstation_harness(mode: str = "") -> str:
    html = _index()
    return (
        f"let _crBottomMode={json.dumps(mode)};let opened=[];let loaded=[];\n"
        "const elements={};\n"
        "function makeEl(id){return elements[id]={id,hidden:false,dataset:{},attrs:{},"
        "classList:{classes:new Set(),toggle(n,on){on?this.classes.add(n):this.classes.delete(n);},remove(n){this.classes.delete(n);}},"
        "getAttribute(n){return this.attrs[n];},setAttribute(n,v){this.attrs[n]=String(v);}};}\n"
        "['cr-bottom-workstation','cr-bottom-collapse-handle','corpus-search','attn-timeline','cr-fln-tray',"
        "'cr-perspective-run','cr-blueprint-draft','cr-render-preview','cr-critic-audit','cr-voice-profile',"
        "'cr-artist-draft','cr-record-ledger','cr-blueprint-subtabs','cr-expression-subtabs'].forEach(makeEl);\n"
        "elements['cr-bottom-workstation'].hidden = " + ("false" if mode else "true") + ";\n"
        "const resourceBtns=['search','timeline','notes','perspective','blueprint','expression','record'].map(r=>({dataset:{workstationResource:r},attrs:{role:'tab'},classList:{classes:new Set(),toggle(n,on){on?this.classes.add(n):this.classes.delete(n);}},getAttribute(n){return this.attrs[n];},setAttribute(n,v){this.attrs[n]=String(v);}}));\n"
        "const subBtns=['blueprint','render','critic','voice','draft'].map(m=>({dataset:{workstationSubmode:m},attrs:{role:'tab'},classList:{classes:new Set(),toggle(n,on){on?this.classes.add(n):this.classes.delete(n);}},getAttribute(n){return this.attrs[n];},setAttribute(n,v){this.attrs[n]=String(v);}}));\n"
        "const document={body:{classList:{state:{},toggle(n,on){this.state[n]=!!on;}}},getElementById(id){return elements[id]||null;},querySelectorAll(sel){if(sel==='[data-workstation-resource]')return resourceBtns;if(sel==='[data-workstation-submode]')return subBtns;return [];},addEventListener(){}};\n"
        "function cmpMarkOnboardingStep(){};function _attnLoad(){loaded.push('timeline');}"
        "function _flnLoadEntries(){loaded.push('fieldnotes');}function _crLoadPerspectiveRun(){loaded.push('perspective');}"
        "function _crLoadBlueprintDraft(){loaded.push('blueprint');}function _crLoadRenderPreview(){loaded.push('render');}"
        "function _crLoadCriticAudit(){loaded.push('critic');}function _crLoadVoiceProfile(){loaded.push('voice');}"
        "function _crLoadArtistDraft(){loaded.push('draft');}function _crLoadRecordLedger(){loaded.push('record');}\n"
        + _extract_fn(html, "_crBottomPanels")
        + _extract_fn(html, "_crWorkstationResourceForMode")
        + _extract_fn(html, "_crSyncBottomWorkstationState")
        + _extract_fn(html, "_crToggleBottomWorkstationResource")
        + _extract_fn(html, "_crOpenBottomWorkstation")
        + _extract_fn(html, "_crCloseBottomWorkstation")
    )


def test_active_top_level_resource_click_collapses_workstation() -> None:
    script = (
        _workstation_harness("search")
        + """
_crSyncBottomWorkstationState();
const before = {hidden: elements['cr-bottom-workstation'].hidden, mode:_crBottomMode, handleHidden:elements['cr-bottom-collapse-handle'].hidden};
_crToggleBottomWorkstationResource('search');
const afterSearch = {hidden: elements['cr-bottom-workstation'].hidden, mode:_crBottomMode, handleHidden:elements['cr-bottom-collapse-handle'].hidden};
_crOpenBottomWorkstation('render');
const renderOpen = {resource:elements['cr-bottom-workstation'].dataset.resource, active:!elements['cr-bottom-workstation'].hidden};
_crToggleBottomWorkstationResource('blueprint');
const afterBlueprint = {hidden: elements['cr-bottom-workstation'].hidden, mode:_crBottomMode};
_crOpenBottomWorkstation('draft');
const draftOpen = {resource:elements['cr-bottom-workstation'].dataset.resource, active:!elements['cr-bottom-workstation'].hidden};
_crToggleBottomWorkstationResource('voice');
const afterExpression = {hidden: elements['cr-bottom-workstation'].hidden, mode:_crBottomMode};
process.stdout.write(JSON.stringify({before,afterSearch,renderOpen,afterBlueprint,draftOpen,afterExpression}));
"""
    )
    assert _run_node(script) == {
        "before": {"hidden": False, "mode": "search", "handleHidden": False},
        "afterSearch": {"hidden": True, "mode": "", "handleHidden": True},
        "renderOpen": {"resource": "blueprint", "active": True},
        "afterBlueprint": {"hidden": True, "mode": ""},
        "draftOpen": {"resource": "expression", "active": True},
        "afterExpression": {"hidden": True, "mode": ""},
    }


def test_active_nested_subtab_is_idempotent_not_collapse() -> None:
    script = (
        _workstation_harness("render")
        + """
_crSyncBottomWorkstationState();
_crOpenBottomWorkstation('render');
const structure = {hidden: elements['cr-bottom-workstation'].hidden, mode:_crBottomMode, resource:elements['cr-bottom-workstation'].dataset.resource};
_crOpenBottomWorkstation('draft');
_crOpenBottomWorkstation('draft');
const draft = {hidden: elements['cr-bottom-workstation'].hidden, mode:_crBottomMode, resource:elements['cr-bottom-workstation'].dataset.resource};
process.stdout.write(JSON.stringify({structure,draft}));
"""
    )
    assert _run_node(script) == {
        "structure": {"hidden": False, "mode": "render", "resource": "blueprint"},
        "draft": {"hidden": False, "mode": "draft", "resource": "expression"},
    }


def test_center_handle_state_and_click_contract_are_present() -> None:
    html = _index()

    assert 'id="cr-bottom-collapse-handle"' in html
    assert 'hidden aria-controls="cr-bottom-workstation"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-label="Collapse bottom workstation"' in html
    assert 'onclick="_crCloseBottomWorkstation()"' in html
    assert 'class="cr-bottom-workstation-close"' not in html
    assert "handle.hidden = !open" in html
    assert "handle.setAttribute('aria-expanded', String(open))" in html


def _escape_harness() -> str:
    html = _index()
    return (
        "let _crCaptureOpen=true;let _crSelToolbar=null;let _dockPanelKey='inspector';let _crBottomMode='fieldnotes';"
        "let cancelCalls=0;let dockCloseCalls=0;let bottomCloseCalls=0;let workspaceCloseCalls=0;let searchClears=0;"
        "const elements={};"
        "const workspace={dataset:{open:'0'},hidden:true};"
        "const corpusMeta={textContent:'x'};const corpusResults={innerHTML:'x'};"
        "const document={getElementById(id){"
        "if(id==='workspace-drawer')return workspace;"
        "if(id==='corpus-search-meta')return corpusMeta;"
        "if(id==='corpus-search-results')return corpusResults;"
        "return elements[id]||null;},querySelectorAll(){return [];},addEventListener(){}};"
        "function _wsCloseMenu(){workspace.dataset.open='0';workspace.hidden=true;workspaceCloseCalls++;}"
        "function _crCancelHighlight(){_crCaptureOpen=false;cancelCalls++;}"
        "function _dockClosePanel(){_dockPanelKey='';dockCloseCalls++;}"
        "function _crCloseBottomWorkstation(){_crBottomMode='';bottomCloseCalls++;}"
        "function _corpusRunSearch(q){searchClears++;}"
        "function ev(target){return {key:'Escape',target:target||{},defaultPrevented:false,prevented:false,preventDefault(){this.prevented=true;this.defaultPrevented=true;}};}"
        + _extract_fn(html, "_wsMenuIsOpen")
        + _extract_fn(html, "_crHandleLocalEscape")
        + _extract_fn(html, "_crCloseTransientReaderChrome")
        + _extract_fn(html, "_crReturnTowardBook")
    )


def test_escape_staircase_closes_one_layer_toward_book() -> None:
    script = (
        _escape_harness()
        + """
const states=[];
let e1=ev();_crReturnTowardBook(e1);states.push({capture:_crCaptureOpen,dock:_dockPanelKey,bottom:_crBottomMode,cancelCalls,dockCloseCalls,bottomCloseCalls,prevented:e1.prevented});
let e2=ev();_crReturnTowardBook(e2);states.push({capture:_crCaptureOpen,dock:_dockPanelKey,bottom:_crBottomMode,cancelCalls,dockCloseCalls,bottomCloseCalls,prevented:e2.prevented});
let e3=ev();_crReturnTowardBook(e3);states.push({capture:_crCaptureOpen,dock:_dockPanelKey,bottom:_crBottomMode,cancelCalls,dockCloseCalls,bottomCloseCalls,prevented:e3.prevented});
let e4=ev();const handled4=_crReturnTowardBook(e4);states.push({handled4,capture:_crCaptureOpen,dock:_dockPanelKey,bottom:_crBottomMode,cancelCalls,dockCloseCalls,bottomCloseCalls,prevented:e4.prevented});
process.stdout.write(JSON.stringify(states));
"""
    )
    assert _run_node(script) == [
        {"capture": False, "dock": "inspector", "bottom": "fieldnotes", "cancelCalls": 1, "dockCloseCalls": 0, "bottomCloseCalls": 0, "prevented": True},
        {"capture": False, "dock": "", "bottom": "fieldnotes", "cancelCalls": 1, "dockCloseCalls": 1, "bottomCloseCalls": 0, "prevented": True},
        {"capture": False, "dock": "", "bottom": "", "cancelCalls": 1, "dockCloseCalls": 1, "bottomCloseCalls": 1, "prevented": True},
        {"handled4": False, "capture": False, "dock": "", "bottom": "", "cancelCalls": 1, "dockCloseCalls": 1, "bottomCloseCalls": 1, "prevented": False},
    ]


def test_workspace_drawer_escape_consumes_one_step_before_reader_layers() -> None:
    script = (
        _escape_harness()
        + """
_crCaptureOpen=false;workspace.dataset.open='1';workspace.hidden=false;
let e=ev();_crReturnTowardBook(e);
process.stdout.write(JSON.stringify({workspaceOpen:workspace.dataset.open,dock:_dockPanelKey,bottom:_crBottomMode,workspaceCloseCalls,dockCloseCalls,bottomCloseCalls,prevented:e.prevented}));
"""
    )
    assert _run_node(script) == {
        "workspaceOpen": "0",
        "dock": "inspector",
        "bottom": "fieldnotes",
        "workspaceCloseCalls": 1,
        "dockCloseCalls": 0,
        "bottomCloseCalls": 0,
        "prevented": True,
    }


def test_corpus_search_escape_clears_local_query_before_collapsing_workstation() -> None:
    script = (
        _escape_harness()
        + """
_crCaptureOpen=false;_dockPanelKey='';_crBottomMode='search';
const input={id:'corpus-search-input',value:'green light'};
let e=ev(input);_crReturnTowardBook(e);
process.stdout.write(JSON.stringify({value:input.value,searchClears,bottom:_crBottomMode,bottomCloseCalls,prevented:e.prevented}));
"""
    )
    assert _run_node(script) == {
        "value": "",
        "searchClears": 1,
        "bottom": "search",
        "bottomCloseCalls": 0,
        "prevented": True,
    }
