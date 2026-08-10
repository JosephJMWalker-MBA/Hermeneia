from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_fn(source: str, name: str) -> str:
    match = re.search(
        r"\n(?:async\s+)?function " + re.escape(name) + r"\(.*?\n\}\n",
        source,
        re.S,
    )
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


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
    focus(opts){this.focused=true;this.focusOpts=opts||{};},
    scrollIntoView(opts){this.scrolled=true;this.scrollOpts=opts||{};},
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
      elements['ob-upload-wayfinding']=makeEl('ob-upload-wayfinding');
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
"""


def test_first_run_upload_opens_existing_upload_area() -> None:
    html = INDEX.read_text()

    assert "Upload your own PDF" in html
    assert 'onclick="obOpenUploadArea()"' in html

    script = (
        _dom_harness()
        + r"""
let _obUploadFocusPending=false;
let _obCanUploadDocuments=true;
let _register='universal';
let goCalls=[];
let pendingLoad=null;
function e10Go(id){goCalls.push(id);if(id==='onboarding')pendingLoad=e10LoadOnboarding();}
function buildCycleDiagram(){return '<div class="ob-cycle-wrap"></div>';}
function invLoad(){return null;}
function sttMakeBtn(){return '';}
function updateNavCycle(){}
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
        + _extract_fn(html, "obOpenUploadArea")
        + _extract_fn(html, "_obMaybeFocusUploadArea")
        + _extract_fn(html, "_obFocusUploadArea")
        + _extract_fn(html, "e10LoadOnboarding")
        + r"""
(async()=>{
  obOpenUploadArea();
  await pendingLoad;
  const zone=elements['ob-upload-zone'];
  const area=elements['ob-upload-area'];
  process.stdout.write(JSON.stringify({
    goCalls,
    uploadAreaVisible:host.innerHTML.includes('id="ob-upload-area"'),
    uploadLabelVisible:host.innerHTML.includes('Upload a document to begin'),
    backToStartVisible:host.innerHTML.includes('Back to start'),
    focused:zone.focused,
    focusPreventScroll:zone.focusOpts.preventScroll,
    tabindex:zone.attrs.tabindex,
    highlighted:zone.classList.items.includes('wayfinding-focus'),
    scrolled:area.scrolled,
  }));
})();
"""
    )

    behavior = _run_node(script)

    assert behavior == {
        "goCalls": ["onboarding"],
        "uploadAreaVisible": True,
        "uploadLabelVisible": True,
        "backToStartVisible": True,
        "focused": True,
        "focusPreventScroll": True,
        "tabindex": "0",
        "highlighted": True,
        "scrolled": True,
    }


def test_cancelled_file_picker_keeps_upload_retry_visible() -> None:
    html = INDEX.read_text()
    script = (
        _dom_harness()
        + r"""
elements['ob-upload-area']=makeEl('ob-upload-area');
elements['ob-upload-zone']=makeEl('ob-upload-zone');
let uploadCalls=0;
function obUploadFile(){uploadCalls++;}
"""
        + _extract_fn(html, "_obFocusUploadArea")
        + _extract_fn(html, "obHandleFileSelect")
        + r"""
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


def test_existing_workspace_add_document_uses_same_upload_route() -> None:
    html = INDEX.read_text()

    assert 'id="add-document-btn"' in html
    assert "Add document" in html
    assert "upload a PDF to this workspace" in html

    script = (
        _dom_harness()
        + r"""
let _obUploadFocusPending=false;
let _obCanUploadDocuments=true;
let goCalls=[];
function e10Go(id){goCalls.push(id);}
"""
        + _extract_fn(html, "obOpenUploadArea")
        + r"""
obOpenUploadArea();
process.stdout.write(JSON.stringify({goCalls,pending:_obUploadFocusPending}));
"""
    )

    assert _run_node(script) == {
        "goCalls": ["onboarding"],
        "pending": True,
    }


def test_upload_submission_reuses_existing_backend_endpoint_and_payload() -> None:
    html = INDEX.read_text()
    script = (
        _dom_harness()
        + r"""
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
        + _extract_fn(html, "obUploadFile")
        + r"""
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


def test_failed_upload_uses_runtime_error_message_and_requires_retry() -> None:
    html = INDEX.read_text()
    script = (
        _dom_harness()
        + r"""
const statusEl=makeEl('ob-upload-status');
const zoneEl=makeEl('ob-upload-zone');
statusEl.style={display:'none'};
zoneEl.style={display:''};
elements['ob-upload-status']=statusEl;
elements['ob-upload-zone']=zoneEl;
class FormData { constructor(){this.entries=[];} append(k,v){this.entries.push([k,v]);} }
async function runtimeApiFetch(){throw new Error('Connection to Hermeneia lost. Your unsaved text is preserved in this browser.');}
function e10LoadOnboarding(){throw new Error('must not auto-reload after failed upload');}
"""
        + _extract_fn(html, "obUploadFile")
        + r"""
(async()=>{
  await obUploadFile({name:'failed.pdf'});
  process.stdout.write(JSON.stringify({
    zoneDisplay:zoneEl.style.display,
    status:statusEl.innerHTML,
  }));
})();
"""
    )

    behavior = _run_node(script)

    assert behavior["zoneDisplay"] == ""
    assert "Connection to Hermeneia lost" in behavior["status"]


def test_no_workspace_switching_ui_was_added() -> None:
    html = INDEX.read_text().lower()

    assert "workspace dropdown" not in html
    assert "switch workspace" not in html
    assert "workspace list" not in html
