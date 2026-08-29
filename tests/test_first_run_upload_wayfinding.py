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


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for first-run upload wayfinding tests")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _dom_harness() -> str:
    return r"""
function x(value){return String(value==null?'':value)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function makeClassList(){return {items:[],add(c){if(!this.items.includes(c))this.items.push(c);},remove(c){this.items=this.items.filter(x=>x!==c);},toggle(c,on){on?this.add(c):this.remove(c);}};}
function makeEl(id){
  return {id,style:{},attrs:{},focused:false,scrolled:false,classList:makeClassList(),
    setAttribute(k,v){this.attrs[k]=String(v);},
    getAttribute(k){return this.attrs[k];},
    focus(opts){this.focused=true;this.focusOpts=opts||{};},
    scrollIntoView(opts){this.scrolled=true;this.scrollOpts=opts||{};},
    addEventListener(){},
    removeAttribute(k){delete this.attrs[k];},
  };
}
const elements={};
const host=makeEl('onboarding-panel');
Object.defineProperty(host,'innerHTML',{
  get(){return this._html||'';},
  set(value){
    this._html=String(value);
    if(this._html.includes('id="ob-upload-area"')){
      elements['ob-upload-area']=makeEl('ob-upload-area');
      elements['ob-upload-zone']=makeEl('ob-upload-zone');
      elements['ob-upload-status']=makeEl('ob-upload-status');
      elements['ob-file-input']=makeEl('ob-file-input');
    }
  }
});
host.querySelector=function(sel){
  if(sel==='.ob-cycle-wrap')return {classList:makeClassList(),offsetWidth:1,addEventListener(){}};
  return null;
};
elements['onboarding-panel']=host;
const document={getElementById(id){return elements[id]||null;}};
let timers=[];
function setTimeout(fn,ms){timers.push({fn,ms});return timers.length;}
const localStorage={getItem(){return null;},setItem(){},removeItem(){}};
let _register='universal';
function buildCycleDiagram(){return '<div class="ob-cycle-wrap"></div>';}
function invLoad(){return null;}
function sttMakeBtn(){return '';}
function updateNavCycle(){}
"""


def test_first_run_upload_action_uses_canonical_upload_helper_not_corpus() -> None:
    html = _index()
    first_run = _extract_function(html, "async function e10LoadFirstRun(")

    assert "Upload your own PDF" in first_run
    assert 'onclick="obOpenUploadArea()"' in first_run
    upload_button = first_run[
        first_run.index("Upload your own PDF") - 140 : first_run.index("Upload your own PDF") + 80
    ]
    assert "e10Go('corpus')" not in upload_button


def test_upload_helper_routes_to_first_run_when_workspace_is_not_ready() -> None:
    html = _index()
    script = (
        "let _obCanUploadDocuments=false;let _obUploadFocusPending=false;let goCalls=[];"
        "function e10Go(id){goCalls.push(id);}"
        + _extract_function(html, "function obOpenUploadArea(")
        + """
obOpenUploadArea();
process.stdout.write(JSON.stringify({goCalls,pending:_obUploadFocusPending}));
"""
    )

    assert _run_node(script) == {"goCalls": ["firstrun"], "pending": False}


def test_existing_workspace_add_document_converges_on_same_upload_helper() -> None:
    html = _index()
    drawer = html[
        html.index('<div class="workspace-drawer"') : html.index(
            '<input type="file" id="ws-import-file"'
        )
    ]

    assert "Add document" in drawer
    assert "upload a PDF to this workspace" in drawer
    assert 'onclick="_wsCloseMenu();obOpenUploadArea()"' in drawer

    script = (
        "let _obCanUploadDocuments=true;let _obUploadFocusPending=false;let goCalls=[];"
        "function e10Go(id){goCalls.push(id);}"
        + _extract_function(html, "function obOpenUploadArea(")
        + """
obOpenUploadArea();
process.stdout.write(JSON.stringify({goCalls,pending:_obUploadFocusPending}));
"""
    )

    assert _run_node(script) == {"goCalls": ["onboarding"], "pending": True}


def test_upload_helper_focuses_existing_onboarding_upload_area_after_render() -> None:
    html = _index()
    script = (
        _dom_harness()
        + """
let _obUploadFocusPending=false;
let _obCanUploadDocuments=true;
let goCalls=[];
let pendingLoad=null;
function e10Go(id){goCalls.push(id);if(id==='onboarding')pendingLoad=e10LoadOnboarding();}
async function fetch(url){
  if(url==='/api/project/summary')return {json:async()=>({
    pipeline:[{key:'observations',label:'Observe',description:'Extract evidence from source documents',count:0,status:'current',nav_target:'corpus'}],
    counts:{},
    document:{filename:null},
  })};
  if(url==='/api/documents')return {json:async()=>({documents:[]})};
  throw new Error(url);
}
"""
        + _extract_function(html, "function obOpenUploadArea(")
        + _extract_function(html, "function _obMaybeFocusUploadArea(")
        + _extract_function(html, "function _obFocusUploadArea(")
        + _extract_function(html, "async function e10LoadOnboarding(")
        + """
(async()=>{
  obOpenUploadArea();
  await pendingLoad;
  const zone=elements['ob-upload-zone'];
  const area=elements['ob-upload-area'];
  process.stdout.write(JSON.stringify({
    goCalls,
    uploadAreaVisible:host.innerHTML.includes('id="ob-upload-area"'),
    wayfindingVisible:host.innerHTML.includes('Add document to this workspace'),
    backToStartVisible:host.innerHTML.includes('Back to start'),
    focused:zone.focused,
    preventScroll:zone.focusOpts.preventScroll,
    tabindex:zone.attrs.tabindex,
    highlighted:zone.classList.items.includes('wayfinding-focus'),
    scrolled:area.scrolled,
    pending:_obUploadFocusPending,
  }));
})();
"""
    )

    assert _run_node(script) == {
        "goCalls": ["onboarding"],
        "uploadAreaVisible": True,
        "wayfindingVisible": True,
        "backToStartVisible": True,
        "focused": True,
        "preventScroll": True,
        "tabindex": "0",
        "highlighted": True,
        "scrolled": True,
        "pending": False,
    }


def test_back_to_start_control_routes_to_first_run_surface() -> None:
    html = _index()
    match = re.search(
        r'<button class="btn-trace" onclick="([^"]+)">Back to start</button>',
        html,
    )
    assert match
    back_handler = match.group(1)
    script = (
        _dom_harness()
        + """
let _obUploadFocusPending=false;
let goCalls=[];
let pendingFirstRun=null;
const buttonHandler=__BACK_HANDLER__;
elements['firstrun-panel']=makeEl('firstrun-panel');
function e10Go(id){goCalls.push(id);if(id==='firstrun')pendingFirstRun=e10LoadFirstRun();}
async function get(url){
  if(url==='/api/setup/state')return {
    database_exists:true,
    document_count:0,
    demo_available:false,
    db_path:'/tmp/hermeneia.db',
    runtime:{workspace:{runtime_scope:'managed:test'}},
  };
  throw new Error(url);
}
function _runtimeApplyWorkspaceDraftScope(){}
function _cmpOnboardingHtml(){return '';}
function _setWorkspaceDatabaseAvailable(available){}
""".replace("__BACK_HANDLER__", json.dumps(back_handler))
        + _extract_function(html, "async function e10LoadFirstRun(")
        + """
(async()=>{
  eval(buttonHandler);
  await pendingFirstRun;
  process.stdout.write(JSON.stringify({
    backHandler: buttonHandler,
    goCalls,
    firstRunRendered: !!elements['firstrun-panel'].innerHTML.includes('Bring a source worth investigating'),
  }));
})();
"""
    )

    assert _run_node(script) == {
        "backHandler": "e10Go('firstrun')",
        "goCalls": ["firstrun"],
        "firstRunRendered": True,
    }


def test_cancelled_file_picker_keeps_upload_retry_visible() -> None:
    html = _index()
    script = (
        _dom_harness()
        + """
elements['ob-upload-area']=makeEl('ob-upload-area');
elements['ob-upload-zone']=makeEl('ob-upload-zone');
let uploadCalls=0;
function obUploadFile(){uploadCalls++;}
"""
        + _extract_function(html, "function _obFocusUploadArea(")
        + _extract_function(html, "function obHandleFileSelect(")
        + """
obHandleFileSelect({files:[]});
const zone=elements['ob-upload-zone'];
const area=elements['ob-upload-area'];
process.stdout.write(JSON.stringify({
  uploadCalls,
  focused:zone.focused,
  highlighted:zone.classList.items.includes('wayfinding-focus'),
  scrolled:area.scrolled,
}));
"""
    )

    assert _run_node(script) == {
        "uploadCalls": 0,
        "focused": True,
        "highlighted": True,
        "scrolled": True,
    }


def test_failed_upload_restores_retry_target_without_navigation() -> None:
    html = _index()
    script = (
        _dom_harness()
        + """
const statusEl=makeEl('ob-upload-status');
const zoneEl=makeEl('ob-upload-zone');
const areaEl=makeEl('ob-upload-area');
statusEl.style={display:'none'};
zoneEl.style={display:''};
elements['ob-upload-status']=statusEl;
elements['ob-upload-zone']=zoneEl;
elements['ob-upload-area']=areaEl;
class FormData { constructor(){this.entries=[];} append(k,v){this.entries.push([k,v]);} }
async function runtimeApiFetch(){throw new Error('Connection to Hermeneia lost. Your unsaved text is preserved in this browser.');}
function e10LoadOnboarding(){throw new Error('must not auto-reload after failed upload');}
"""
        + _extract_function(html, "function _obFocusUploadArea(")
        + _extract_function(html, "async function obUploadFile(")
        + """
(async()=>{
  await obUploadFile({name:'failed.pdf'});
  process.stdout.write(JSON.stringify({
    zoneDisplay:zoneEl.style.display,
    status:statusEl.innerHTML,
    focused:zoneEl.focused,
    scrolled:areaEl.scrolled,
  }));
})();
"""
    )

    behavior = _run_node(script)

    assert behavior["zoneDisplay"] == ""
    assert "Connection to Hermeneia lost" in behavior["status"]
    assert behavior["focused"] is True
    assert behavior["scrolled"] is True


def test_successful_upload_preserves_endpoint_payload_and_existing_reload() -> None:
    html = _index()
    script = (
        _dom_harness()
        + """
const statusEl=makeEl('ob-upload-status');
const zoneEl=makeEl('ob-upload-zone');
statusEl.style={display:'none'};
zoneEl.style={display:''};
elements['ob-upload-status']=statusEl;
elements['ob-upload-zone']=zoneEl;
class FormData {
  constructor(){this.entries=[];}
  append(k,v){this.entries.push([k,v&&v.name?v.name:v]);}
}
let calls=[];
async function runtimeApiFetch(url, options){
  calls.push({url,method:options.method,entries:options.body.entries});
  return {ok:true,json:async()=>({filename:'treatise.pdf',observation_count:2,term_count:3,total_pages:1})};
}
function e10LoadOnboarding(){calls.push({url:'reload-start'});}
"""
        + _extract_function(html, "async function obUploadFile(")
        + """
(async()=>{
  await obUploadFile({name:'treatise.pdf'});
  process.stdout.write(JSON.stringify({
    calls,
    zoneDisplay:zoneEl.style.display,
    statusDisplay:statusEl.style.display,
    status:statusEl.innerHTML,
  }));
})();
"""
    )

    behavior = _run_node(script)

    assert behavior["calls"][0] == {
        "url": "/api/upload",
        "method": "POST",
        "entries": [["file", "treatise.pdf"]],
    }
    assert behavior["calls"][1] == {"url": "reload-start"}
    assert behavior["zoneDisplay"] == "none"
    assert behavior["statusDisplay"] == "block"
    assert "2 observations extracted" in behavior["status"]
    assert "3 terms indexed" in behavior["status"]


def test_no_second_primary_upload_form_or_backend_route_added() -> None:
    html = _index()

    assert html.count('id="ob-file-input"') == 1
    assert html.count('function obUploadFile(') == 1
    assert html.count('@app.route("/api/upload"') == 0
