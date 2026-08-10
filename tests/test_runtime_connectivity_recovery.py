from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_runtime_region(html: str) -> str:
    start = "// ── Runtime connectivity and local authored drafts"
    end = "// ── Accessibility Dock"
    assert start in html and end in html
    start_at = html.index(start)
    end_at = html.index(end, start_at)
    return html[start_at:end_at]


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
        pytest.skip("node not available for runtime connectivity UI tests")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _js_dom_prelude() -> str:
    return r"""
function x(value){return String(value==null?'':value)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function makeClassList(){return {items:[],add(c){this.items.push(c);},remove(c){this.items=this.items.filter(x=>x!==c);},toggle(c,on){on?this.add(c):this.remove(c);}};}
const statusHost={hidden:false,className:'runtime-connection-status',innerHTML:''};
const appError={textContent:'',style:{},classList:makeClassList(),removeAttribute(name){delete this[name];}};
const readerPage={innerHTML:'Reader page content remains visible.'};
const document={
  body:{dataset:{}},
  getElementById(id){
    if(id==='runtime-connection-status')return statusHost;
    if(id==='app-error')return appError;
    if(id==='cr-page-view')return readerPage;
    return null;
  },
  querySelectorAll(){return [];}
};
const window={location:{origin:'http://hermeneia.local',pathname:'/'},addEventListener(){}};
const localStorage={data:{},getItem(k){return this.data[k]||null;},setItem(k,v){this.data[k]=String(v);},removeItem(k){delete this.data[k];}};
let timerQueue=[];
function setTimeout(fn,ms){timerQueue.push({fn,ms});return timerQueue.length;}
function clearTimeout(){}
"""


def test_runtime_connectivity_distinguishes_endpoint_loss_from_http_errors() -> None:
    html = INDEX.read_text()
    script = (
        _js_dom_prelude()
        + _extract_runtime_region(html)
        + _extract_fn(html, "showAppError")
        + _extract_fn(html, "clearAppError")
        + _extract_fn(html, "requestJSON")
        + r"""
let mode='network';
let calls=[];
async function fetch(url, options={}){
  calls.push({url:String(url),method:options.method||'GET',body:options.body||''});
  if(mode==='network')throw new TypeError('Failed to fetch');
  if(mode==='http')return {ok:false,status:422,json:async()=>({error:'validation failed'})};
  return {ok:true,status:200,json:async()=>({ok:true})};
}
(async()=>{
  let networkName='';
  try{await requestJSON('/api/reader/highlights',{method:'POST',body:{note_text:'draft'}});}
  catch(e){networkName=e.name;}
  const firstTimerCount=timerQueue.length;
  try{await requestJSON('/api/reader/highlights',{method:'POST',body:{note_text:'draft'}});}
  catch(e){}
  const repeatedTimerCount=timerQueue.length;
  const lostState={
    networkName,
    state:_runtimeConnectionState,
    bannerHidden:statusHost.hidden,
    banner:statusHost.innerHTML,
    firstTimerCount,
    repeatedTimerCount,
    readerPage:readerPage.innerHTML,
    postCalls:calls.filter(c=>c.method==='POST').length,
  };

  _runtimeConnectionState='connected';
  _runtimeReconnectTimer=null;
  timerQueue=[];
  calls=[];
  statusHost.hidden=true;
  statusHost.innerHTML='';
  mode='http';
  let httpName='';
  try{await requestJSON('/api/reader/highlights',{method:'POST',body:{note_text:'draft'}});}
  catch(e){httpName=e.name;}
  const httpState={
    httpName,
    state:_runtimeConnectionState,
    bannerHidden:statusHost.hidden,
    appError:appError.textContent,
  };

  _runtimeConnectionState='connected';
  _runtimeReconnectTimer=null;
  timerQueue=[];
  calls=[];
  mode='network';
  try{await requestJSON('/api/reader/highlights',{method:'POST',body:{note_text:'draft'}});}
  catch(e){}
  const beforeRecoveryPosts=calls.filter(c=>c.method==='POST').length;
  mode='ok';
  await timerQueue[0].fn();
  const recoveryState={
    state:_runtimeConnectionState,
    banner:statusHost.innerHTML,
    beforeRecoveryPosts,
    afterRecoveryPosts:calls.filter(c=>c.method==='POST').length,
    healthCalls:calls.filter(c=>c.url==='/api/health').length,
  };

  process.stdout.write(JSON.stringify({lostState,httpState,recoveryState}));
})();
"""
    )

    result = _run_node(script)

    assert result["lostState"]["networkName"] == "RuntimeEndpointError"
    assert result["lostState"]["state"] == "unreachable"
    assert result["lostState"]["bannerHidden"] is False
    assert "Connection to Hermeneia lost" in result["lostState"]["banner"]
    assert "unsaved text is preserved" in result["lostState"]["banner"]
    assert result["lostState"]["firstTimerCount"] == 1
    assert result["lostState"]["repeatedTimerCount"] == 1
    assert result["lostState"]["readerPage"] == "Reader page content remains visible."
    assert result["lostState"]["postCalls"] == 2

    assert result["httpState"] == {
        "httpName": "RuntimeHttpError",
        "state": "connected",
        "bannerHidden": True,
        "appError": "validation failed",
    }

    assert result["recoveryState"]["state"] == "reconnected"
    assert "Reconnected to Hermeneia" in result["recoveryState"]["banner"]
    assert result["recoveryState"]["beforeRecoveryPosts"] == 1
    assert result["recoveryState"]["afterRecoveryPosts"] == 1
    assert result["recoveryState"]["healthCalls"] == 1


def test_highlight_drafts_survive_failed_save_and_clear_after_ack() -> None:
    html = INDEX.read_text()
    script = (
        _js_dom_prelude()
        + r"""
function makeInput(value=''){return {value,checked:false,style:{},dataset:{},textContent:'',listeners:{},addEventListener(type,fn){this.listeners[type]=fn;},classList:makeClassList(),focus(){}};}
const elements={
  'cr-note-input':makeInput('unsaved reader note'),
  'cr-q-input':makeInput(''),
  'cr-important-input':makeInput(''),
  'cr-tags-input':makeInput(''),
  'cr-rank-input':makeInput(''),
  'cr-theme-input':makeInput(''),
  'cr-concept-input':makeInput(''),
  'cr-capture-msg':makeInput(''),
  'cr-sel-prompt':{style:{},innerHTML:''},
  'cr-page-view':readerPage,
};
const baseGetElementById=document.getElementById.bind(document);
document.getElementById=function(id){return elements[id]||baseGetElementById(id);};
let _crDocId='doc-1';
let _crPage=4;
let _crSelText='Selected passage';
let _crRelevance='unclear';
let _crConcept='';
let _crSelectionRect=null;
let _crReaderSelectionState={text:'Selected passage'};
let _crHighlights=[];
let loadCalls=0;
let renderedPage='';
function _crGetReaderSelection(){return {text:'Selected passage'};}
function _crPageReadingText(){return 'Before Selected passage After';}
function _crEncodeReaderSpanLocator(){return 'p4:block1';}
function _crParseTypedTags(){return [];}
function _crReadRankValue(){return null;}
function _crReadOptionalText(){return null;}
function _crUniqueTags(tags){return Array.from(new Set((tags||[]).filter(Boolean)));}
async function _crLoadHighlightList(){loadCalls++;}
function _crRenderPage(){renderedPage=readerPage.innerHTML;}
function _crRefreshTrail(){}
function _crHideToolbar(){}
function _crClearPending(){}
function _flnActivityTick(){}
function _crShowHighlightDetail(){}
function cmpMarkOnboardingStep(){}
"""
        + _extract_runtime_region(html)
        + _extract_fn(html, "showAppError")
        + _extract_fn(html, "clearAppError")
        + _extract_fn(html, "requestJSON")
        + _extract_fn(html, "_crSaveHighlight")
        + r"""
let mode='network';
let calls=[];
async function fetch(url, options={}){
  calls.push({url:String(url),method:options.method||'GET',body:options.body||''});
  if(mode==='network')throw new TypeError('Failed to fetch');
  return {ok:true,status:201,json:async()=>({id:'hl-1'})};
}
(async()=>{
  await _crSaveHighlight(false);
  const failedDraftRaw=Object.values(localStorage.data)[0]||'';
  const failedDraft=failedDraftRaw?JSON.parse(failedDraftRaw):null;
  const failedSave={
    draft:failedDraft,
    message:elements['cr-capture-msg'].textContent,
    banner:statusHost.innerHTML,
    readerPage:readerPage.innerHTML,
    callCount:calls.length,
  };

  localStorage.data={};
  calls=[];
  mode='network';
  elements['cr-note-input'].value='';
  elements['cr-q-input'].value='';
  await _crSaveHighlight(false);
  const blankPayload=JSON.parse(calls[0].body);
  const blankSave={
    noteText:blankPayload.note_text,
    storedKeys:Object.keys(localStorage.data),
    serializedDrafts:JSON.stringify(localStorage.data),
  };

  calls=[];
  mode='ok';
  elements['cr-note-input'].value='acknowledged reader note';
  await _crSaveHighlight(false);
  const ackSave={
    storedKeys:Object.keys(localStorage.data),
    loadCalls,
    renderedPage,
  };
  process.stdout.write(JSON.stringify({failedSave,blankSave,ackSave}));
})();
"""
    )

    result = _run_node(script)

    assert result["failedSave"]["draft"]["fields"]["note_text"] == "unsaved reader note"
    assert result["failedSave"]["message"].startswith("Connection to Hermeneia lost")
    assert "Connection to Hermeneia lost" in result["failedSave"]["banner"]
    assert result["failedSave"]["readerPage"] == "Reader page content remains visible."
    assert result["failedSave"]["callCount"] == 1

    assert result["blankSave"]["noteText"] is None
    assert result["blankSave"]["storedKeys"] == []
    assert "Candidate for observation" not in result["blankSave"]["serializedDrafts"]

    assert result["ackSave"]["storedKeys"] == []
    assert result["ackSave"]["loadCalls"] == 1
    assert result["ackSave"]["renderedPage"] == "Reader page content remains visible."


def test_existing_highlight_edit_recovers_only_matching_browser_draft() -> None:
    html = INDEX.read_text()
    script = (
        _js_dom_prelude()
        + r"""
function makeInput(value=''){return {value,checked:false,style:{},dataset:{},textContent:'',listeners:{},addEventListener(type,fn){this.listeners[type]=fn;},classList:makeClassList()};}
const elements={
  'cr-edit-important':makeInput(''),
  'cr-edit-tags':makeInput(''),
  'cr-edit-rank':makeInput(''),
  'cr-edit-theme':makeInput(''),
  'cr-edit-note':makeInput('saved note'),
  'cr-edit-q':makeInput('saved question'),
  'cr-edit-msg':makeInput(''),
};
const baseGetElementById=document.getElementById.bind(document);
document.getElementById=function(id){return elements[id]||baseGetElementById(id);};
document.querySelectorAll=function(){return [];};
let _crDocId='doc-1';
let _crPage=7;
let _crRelevance='supports';
function _crHighlightTags(h){return Array.isArray(h&&h.tags)?h.tags:[];}
"""
        + _extract_runtime_region(html)
        + r"""
const h={id:'hl-1',source_document_id:'doc-1',page:7,note_text:'saved note',question_text:'saved question',relevance:'supports',tags:[]};
const noDraftNote=elements['cr-edit-note'].value;
const key=_crHighlightEditDraftKey(h);
_authoredDraftSave(key,{
  form_type:'reader-highlight-edit',
  document_id:'doc-1',
  page:7,
  record_id:'hl-1',
  base:_crHighlightEditBase(h),
  fields:{
    important:false,
    tags:'',
    rank:'',
    theme_bucket:'',
    note_text:'unsaved edited note',
    question_text:'saved question',
    relevance:'supports',
  },
});
const applied=_crApplyHighlightEditDraft(h,_authoredDraftLoad(key));
const restoredNote=elements['cr-edit-note'].value;
const restoredMsg=elements['cr-edit-msg'].textContent;

const changed={...h,note_text:'server changed note'};
elements['cr-edit-note'].value='server changed note';
elements['cr-edit-msg'].textContent='';
const conflictApplied=_crApplyHighlightEditDraft(changed,_authoredDraftLoad(key));
process.stdout.write(JSON.stringify({noDraftNote,applied,restoredNote,restoredMsg,conflictApplied,conflictMsg:elements['cr-edit-msg'].textContent}));
"""
    )

    result = _run_node(script)

    assert result["noDraftNote"] == "saved note"
    assert result["applied"] is True
    assert result["restoredNote"] == "unsaved edited note"
    assert "Recovered unsaved highlight text" in result["restoredMsg"]
    assert result["conflictApplied"] is False
    assert "saved highlight changed" in result["conflictMsg"]


def test_field_notes_initial_lane_sync_restores_without_erasing_draft() -> None:
    html = INDEX.read_text()
    script = (
        _js_dom_prelude()
        + r"""
function makeInput(value=''){return {value,style:{},dataset:{},textContent:'',listeners:{},addEventListener(type,fn){this.listeners[type]=fn;},classList:makeClassList()};}
const elements={
  'fln-understanding':makeInput(''),
  'fln-questions':makeInput(''),
};
const laneButtons=[
  {dataset:{lane:'corpus'},classList:makeClassList()},
  {dataset:{lane:'instrument'},classList:makeClassList()},
];
const baseGetElementById=document.getElementById.bind(document);
document.getElementById=function(id){return elements[id]||baseGetElementById(id);};
document.querySelectorAll=function(sel){return sel==='.fln-lane'?laneButtons:[];};
let _crDocId='doc-1';
let _crPage=5;
let _flnLane='corpus';
"""
        + _extract_runtime_region(html)
        + _extract_fn(html, "flnSetLane")
        + r"""
const key=_flnDraftKey('corpus');
_authoredDraftSave(key,{
  form_type:'field-notes',
  document_id:'doc-1',
  page:5,
  record_id:'corpus',
  fields:{understanding:'preserved field note',pressing_questions:'what next?'},
});
flnSetLane('corpus',{skipPersist:true});
const restored={
  understanding:elements['fln-understanding'].value,
  questions:elements['fln-questions'].value,
  draftStillPresent:!!localStorage.getItem(key),
};
elements['fln-understanding'].value='changed corpus note';
elements['fln-questions'].value='';
flnSetLane('instrument');
const corpusDraft=JSON.parse(localStorage.getItem(key));
process.stdout.write(JSON.stringify({restored,afterSwitch:{lane:_flnLane,understanding:elements['fln-understanding'].value,corpusDraft}}));
"""
    )

    result = _run_node(script)

    assert result["restored"] == {
        "understanding": "preserved field note",
        "questions": "what next?",
        "draftStillPresent": True,
    }
    assert result["afterSwitch"]["lane"] == "instrument"
    assert result["afterSwitch"]["understanding"] == ""
    assert result["afterSwitch"]["corpusDraft"]["fields"]["understanding"] == "changed corpus note"


def test_health_success_reports_runtime_endpoint_and_database(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime_health.db"
    SQLiteStore(db_path).close()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            "a" * 64,
            "gatsby.pdf",
            "a" * 64,
            1,
            datetime.now(timezone.utc).isoformat(),
            "test",
            "primary",
            0,
        ),
    )
    conn.commit()
    conn.close()

    body = create_app(db_path=db_path).test_client().get("/api/health").get_json()

    assert body["runtime"]["endpoint_reachable"] is True
    assert body["runtime"]["database_available"] is True
    assert body["runtime"]["workspace"] == {
        "id": None,
        "name": "Custom workspace",
        "slug": None,
        "kind": "custom",
        "managed": False,
    }
    assert body["db_path"] == str(db_path)
