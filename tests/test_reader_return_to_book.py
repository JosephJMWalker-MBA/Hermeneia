"""Reader workstation chrome should always offer a clear path back to the book."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_fn(html: str, name: str) -> str:
    match = re.search(
        r"\n(?:async\s+)?function " + re.escape(name) + r"\(.*?\n\}\n",
        html,
        re.S,
    )
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader return-to-book behavior test")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _harness() -> str:
    html = INDEX.read_text()
    functions = [
        "_crSyncBottomWorkstationState",
        "_crToggleBottomWorkstation",
        "_crOpenBottomWorkstation",
        "_crCloseBottomWorkstation",
        "_crBindBottomWorkstationControls",
        "_dockOpenPanel",
        "_dockClosePanel",
        "_crNodeElement",
        "_crSelectionInsideReader",
        "_crRankLabel",
        "_crRankOptions",
        "_crAnnotationMetaHtml",
        "_crReaderHasActiveNativeSelection",
        "_crOpenHighlightInspectorById",
        "_crShowHighlightDetail",
        "_crHandlePersistedHighlightClick",
        "_crCloseTransientReaderChrome",
        "_crHandleReaderEscape",
    ]
    return (
        "const Node={ELEMENT_NODE:1};\n"
        "const _CR_RANK_LABELS={1:'Speculative',2:'Minor',3:'Useful',4:'Strong',5:'Foundational'};\n"
        "const _DOCK_PANEL_META={guide:{id:'dock-guide-panel',title:'Guide'},question:{id:'cr-question-panel',title:'Question'},"
        "inspector:{id:'cr-capture-panel',title:'Highlight Inspector'},trail:{id:'cr-trail-panel',title:'Reading Trail'},"
        "highlights:{id:'cr-highlights-panel',title:'Saved Highlights'},observations:{id:'cr-related-panel',title:'Machine Observations'},"
        "tools:{id:'dock-tools-panel',title:'Reading tools'}};\n"
        "function x(s){return String(s==null?'':s)"
        ".replace(/&/g,'&amp;').replace(/</g,'&lt;')"
        ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');}\n"
        "function matches(el,sel){if(!el)return false;return sel.split(',').some(raw=>{const s=raw.trim();"
        "if(s.startsWith('#'))return el.id===s.slice(1);"
        "if(s.startsWith('.'))return el.classes&&el.classes.has(s.slice(1));"
        "if(s==='[data-highlight-id]')return !!(el.dataset&&el.dataset.highlightId);"
        "if(s==='[data-workstation-mode]')return !!(el.dataset&&el.dataset.workstationMode);"
        "return false;});}\n"
        "function makeEl(opts={}){const el={nodeType:1,id:opts.id||'',dataset:opts.dataset||{},"
        "classes:new Set(opts.classes||[]),parentElement:null,children:[],style:{},hidden:!!opts.hidden,"
        "innerHTML:opts.innerHTML||'',textContent:opts.textContent||'',value:opts.value||'',onclick:opts.onclick||null,"
        "attrs:{...(opts.attrs||{})},"
        "getAttribute(name){if(name==='role')return this.attrs.role||'';if(name==='data-highlight-id')return this.dataset.highlightId||'';return this.attrs[name]||'';},"
        "setAttribute(name,value){this.attrs[name]=String(value);},"
        "contains(node){let cur=node&&node.nodeType===3?node.parentElement:node;while(cur){if(cur===el)return true;cur=cur.parentElement;}return false;},"
        "closest(sel){let cur=el;while(cur){if(matches(cur,sel))return cur;cur=cur.parentElement;}return null;},"
        "querySelector(){return null;},querySelectorAll(){return [];},scrollIntoView(){globalThis.scrollCalls=(globalThis.scrollCalls||0)+1;},"
        "classList:{add(c){el.classes.add(c);},remove(c){el.classes.delete(c);},toggle(c,on){on?el.classes.add(c):el.classes.delete(c);},contains(c){return el.classes.has(c);}},"
        "remove(){this.removed=true;}};return el;}\n"
        "const elements={};function put(el){elements[el.id]=el;return el;}\n"
        "const bodyClasses=new Set();"
        "const document={body:{classList:{toggle(c,on){on?bodyClasses.add(c):bodyClasses.delete(c);},contains(c){return bodyClasses.has(c);}}},"
        "getElementById(id){return elements[id]||null;},"
        "querySelectorAll(sel){if(sel==='[data-workstation-mode]')return modeButtons;"
        "if(sel==='.dock-rail-btn')return dockButtons;if(sel==='.cr-bottom-workstation-close, .corpus-search-close, .attn-close')return [];"
        "return [];}};\n"
        "const window={getSelection(){return {rangeCount:0,isCollapsed:true};},CSS:{highlights:{delete(){}}}};\n"
        "put(makeEl({id:'cr-bottom-workstation',hidden:true}));"
        "put(makeEl({id:'cr-bottom-collapse-handle',hidden:true}));"
        "['corpus-search','attn-timeline','cr-fln-tray','cr-blueprint-draft','cr-render-preview','cr-critic-audit','cr-voice-profile','cr-artist-draft','cr-record-ledger']"
        ".forEach(id=>put(makeEl({id,hidden:true})));\n"
        "const fieldDraft=makeEl({id:'field-draft',value:'working note'});fieldDraft.parentElement=elements['cr-fln-tray'];"
        "elements['cr-fln-tray'].children.push(fieldDraft);\n"
        "const modeButtons=['search','timeline','fieldnotes','blueprint','render','critic','voice','draft','record'].map(mode=>"
        "put(makeEl({id:'cr-bottom-tab-'+mode,dataset:{workstationMode:mode},attrs:{role:'tab'}})));\n"
        "put(makeEl({id:'a11y-dock-panel',hidden:true}));put(makeEl({id:'a11y-dock-panel-title'}));"
        "Object.values(_DOCK_PANEL_META).forEach(meta=>put(makeEl({id:meta.id,hidden:true})));"
        "const dockButtons=Object.keys(_DOCK_PANEL_META).map(key=>makeEl({id:'dock-'+key,dataset:{panel:key},classes:['dock-rail-btn']}));\n"
        "const form=put(makeEl({id:'cr-sel-form'}));const prompt=put(makeEl({id:'cr-sel-prompt'}));"
        "const pageView=put(makeEl({id:'cr-page-view'}));const textEl=makeEl({classes:['cr-page-text']});"
        "textEl.parentElement=pageView;pageView.children.push(textEl);"
        "const mark=makeEl({dataset:{highlightId:'hl-1'}});mark.parentElement=textEl;textEl.children.push(mark);\n"
        "let _crBottomMode='';let _dockPanelKey='';let _crDocId='doc-1';let _crCaptureOpen=false;let _crSelToolbar=null;"
        "let _crHighlights=[{id:'hl-1',page:3,selected_text:'saved text',note_text:'persisted note',question_text:'saved question',relevance:'supports',status:'saved_highlight',rank:3,theme_bucket:'return',tags:['tag:reader']}];"
        "let _crRelevance='unclear';let cancelCalls=0;let tipDismissCalls=0;let navCalls=0;"
        "let loads={timeline:0,fieldnotes:0,blueprint:0,render:0,critic:0,voice:0,draft:0,record:0,highlights:0};"
        "function _crBottomPanels(){return {search:elements['corpus-search'],timeline:elements['attn-timeline'],fieldnotes:elements['cr-fln-tray'],"
        "blueprint:elements['cr-blueprint-draft'],render:elements['cr-render-preview'],critic:elements['cr-critic-audit'],voice:elements['cr-voice-profile'],"
        "draft:elements['cr-artist-draft'],record:elements['cr-record-ledger']};}"
        "function _crHighlightTags(h){return Array.isArray(h&&h.tags)?h.tags:[];}"
        "function cmpMarkOnboardingStep(){}function _cmpRenderOnboarding(){}function _crToggleRelated(){}"
        "async function _attnLoad(){loads.timeline++;}function _flnLoadEntries(){loads.fieldnotes++;}"
        "function _crLoadBlueprintDraft(){loads.blueprint++;}function _crLoadRenderPreview(){loads.render++;}"
        "function _crLoadCriticAudit(){loads.critic++;}function _crLoadVoiceProfile(){loads.voice++;}"
        "function _crLoadArtistDraft(){loads.draft++;}function _crLoadRecordLedger(){loads.record++;}"
        "async function _crLoadHighlightList(){loads.highlights++;}"
        "function _crCancelHighlight(){cancelCalls++;_crCaptureOpen=false;if(_crSelToolbar){_crSelToolbar.remove();_crSelToolbar=null;}}"
        "function _crHideToolbar(){if(_crSelToolbar){_crSelToolbar.remove();_crSelToolbar=null;}}"
        "function a11yDismissTip(){tipDismissCalls++;}"
        "let appErrors=[];function showAppError(message){appErrors.push(message);}function e10Go(){navCalls++;}\n"
        + "".join(_extract_fn(html, name) for name in functions)
    )


def test_workstation_tabs_toggle_switch_and_preserve_field_note_dom_state() -> None:
    script = _harness() + r"""
_crBindBottomWorkstationControls();
const searchButton = elements['cr-bottom-tab-search'];
const timelineButton = elements['cr-bottom-tab-timeline'];
const fieldButton = elements['cr-bottom-tab-fieldnotes'];
const click = (button) => button.onclick({preventDefault(){}});

await click(searchButton);
const openedSearch = {
  mode: _crBottomMode,
  shellHidden: elements['cr-bottom-workstation'].hidden,
  searchHidden: elements['corpus-search'].hidden,
  handleHidden: elements['cr-bottom-collapse-handle'].hidden,
  bodyInset: bodyClasses.has('has-bottom-workstation'),
  tabActive: searchButton.classes.has('active'),
};
await click(searchButton);
const collapsedSearch = {
  mode: _crBottomMode,
  shellHidden: elements['cr-bottom-workstation'].hidden,
  searchHidden: elements['corpus-search'].hidden,
  handleHidden: elements['cr-bottom-collapse-handle'].hidden,
  bodyInset: bodyClasses.has('has-bottom-workstation'),
  tabActive: searchButton.classes.has('active'),
};
await click(fieldButton);
fieldDraft.value = 'field note draft survives';
await click(timelineButton);
const switchedTimeline = {
  mode: _crBottomMode,
  timelineHidden: elements['attn-timeline'].hidden,
  fieldHidden: elements['cr-fln-tray'].hidden,
  timelineActive: timelineButton.classes.has('active'),
  fieldActive: fieldButton.classes.has('active'),
};
await click(fieldButton);
_crCloseBottomWorkstation();
await _crOpenBottomWorkstation('fieldnotes');
const reopenedFieldNotes = {
  mode: _crBottomMode,
  fieldHidden: elements['cr-fln-tray'].hidden,
  draftValue: fieldDraft.value,
  fieldLoads: loads.fieldnotes,
};
process.stdout.write(JSON.stringify({openedSearch, collapsedSearch, switchedTimeline, reopenedFieldNotes}));
"""
    behavior = _run_node(script)

    assert behavior["openedSearch"] == {
        "mode": "search",
        "shellHidden": False,
        "searchHidden": False,
        "handleHidden": False,
        "bodyInset": True,
        "tabActive": True,
    }
    assert behavior["collapsedSearch"] == {
        "mode": "",
        "shellHidden": True,
        "searchHidden": True,
        "handleHidden": True,
        "bodyInset": False,
        "tabActive": False,
    }
    assert behavior["switchedTimeline"] == {
        "mode": "timeline",
        "timelineHidden": False,
        "fieldHidden": True,
        "timelineActive": True,
        "fieldActive": False,
    }
    assert behavior["reopenedFieldNotes"]["mode"] == "fieldnotes"
    assert behavior["reopenedFieldNotes"]["fieldHidden"] is False
    assert behavior["reopenedFieldNotes"]["draftValue"] == "field note draft survives"
    assert behavior["reopenedFieldNotes"]["fieldLoads"] >= 1


def test_collapse_handle_escape_and_persisted_highlight_keep_reader_recoverable() -> None:
    script = _harness() + r"""
await _crOpenBottomWorkstation('fieldnotes');
_dockOpenPanel('inspector');
const beforeHandle = {
  bottomMode: _crBottomMode,
  handleHidden: elements['cr-bottom-collapse-handle'].hidden,
  dockKey: _dockPanelKey,
  dockHidden: elements['a11y-dock-panel'].hidden,
};
_crCloseBottomWorkstation();
const afterHandle = {
  bottomMode: _crBottomMode,
  handleHidden: elements['cr-bottom-collapse-handle'].hidden,
  dockKey: _dockPanelKey,
  dockHidden: elements['a11y-dock-panel'].hidden,
};

await _crOpenBottomWorkstation('fieldnotes');
_dockOpenPanel('inspector');
_crCaptureOpen = true;
_crSelToolbar = makeEl({id:'cr-sel-toolbar'});
function esc(){const e={key:'Escape',prevented:0,preventDefault(){this.prevented++;}};_crHandleReaderEscape(e);return {prevented:e.prevented,bottomMode:_crBottomMode,dockKey:_dockPanelKey,captureOpen:_crCaptureOpen,toolbar:!!_crSelToolbar,cancelCalls,navCalls};}
const firstEscape = esc();
const secondEscape = esc();
const thirdEscape = esc();
const fourthEscape = esc();

const event = {target: mark, prevented:false, stopped:false, preventDefault(){this.prevented=true;}, stopPropagation(){this.stopped=true;}};
_crHandlePersistedHighlightClick(event);
await new Promise(resolve => setTimeout(resolve, 0));
const persistedClick = {
  prevented: event.prevented,
  stopped: event.stopped,
  dockKey: _dockPanelKey,
  note: form.innerHTML.includes('persisted note'),
  passage: form.innerHTML.includes('saved text'),
  bottomMode: _crBottomMode,
  loadCalls: loads.highlights,
  appErrors,
};
process.stdout.write(JSON.stringify({beforeHandle, afterHandle, firstEscape, secondEscape, thirdEscape, fourthEscape, persistedClick}));
"""
    behavior = _run_node(script)

    assert behavior["beforeHandle"] == {
        "bottomMode": "fieldnotes",
        "handleHidden": False,
        "dockKey": "inspector",
        "dockHidden": False,
    }
    assert behavior["afterHandle"] == {
        "bottomMode": "",
        "handleHidden": True,
        "dockKey": "inspector",
        "dockHidden": False,
    }
    assert behavior["firstEscape"]["prevented"] == 1
    assert behavior["firstEscape"]["captureOpen"] is False
    assert behavior["firstEscape"]["toolbar"] is False
    assert behavior["firstEscape"]["dockKey"] == "inspector"
    assert behavior["firstEscape"]["bottomMode"] == "fieldnotes"
    assert behavior["secondEscape"]["prevented"] == 1
    assert behavior["secondEscape"]["dockKey"] == ""
    assert behavior["secondEscape"]["bottomMode"] == "fieldnotes"
    assert behavior["thirdEscape"]["prevented"] == 1
    assert behavior["thirdEscape"]["bottomMode"] == ""
    assert behavior["fourthEscape"]["prevented"] == 0
    assert behavior["fourthEscape"]["bottomMode"] == ""
    assert behavior["fourthEscape"]["navCalls"] == 0
    assert behavior["persistedClick"]["appErrors"] == []
    assert behavior["persistedClick"] == {
        "prevented": True,
        "stopped": True,
        "dockKey": "inspector",
        "note": True,
        "passage": True,
        "bottomMode": "",
        "loadCalls": 0,
        "appErrors": [],
    }
