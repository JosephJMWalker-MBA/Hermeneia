"""M0: actual Reader context navigation under deterministic deferred responses.

Only DOM construction and unrelated Reader panels are stubbed. The production
route, context dispatch, document/highlight loads, page rendering, and progress
request code run together; no provider, server, or workspace database is used.
"""
from __future__ import annotations

import json
from pathlib import Path
import runpy

from test_evidence_board_ui import _extract_function, _run_node

INDEX = Path(__file__).parents[1] / "hermeneia/web/static/index.html"


def _script(scenario: str) -> str:
    source = INDEX.read_text()
    signatures = [
        "function _studyLineageKey(", "function _studyLineageContextKey(",
        "async function _studyLineageOpenContext(", "function _attnOpen(",
        "function e10Go(", "async function e10LoadCloseReader(",
        "async function _crOpenDoc(", "async function _crLoadHighlightList(",
        "function _crGoToPage(", "function _crRenderPage(",
        "function _crNextPage(", "function _crPrevPage(",
        "function _wsApplyCurrentWorkspace(",
    ]
    functions = "\n".join(_extract_function(source, signature) for signature in signatures)
    return r"""
const noop = () => {};
const x = value => String(value ?? '');
const setTimeout = callback => { callback(); return 1; }; // Cosmetic flash only.
let _expert = false, _register = 'simple', _crReaderLoadSeq = 0;
let _crDocId = 'doc-a', _crPage = 62, _crTotalPages = 85;
let _crDocs = [{id:'doc-a',source_role:'primary',last_page:62},
               {id:'doc-b',source_role:'secondary',last_page:19}];
let _crPages = [{page:1,extractions:[]},{page:62,extractions:[]}];
let _crHighlights = [], _crCurrentExtractions = [];
let _wsCurrentWorkspace = {id:'workspace-a'};
let _studyLineageData = null;
const elements = {}, detachedWrites = [], renders = [], progress = [], requests = [];
let route = 'reader';
function classList() {
  const values = new Set();
  return {add:value=>values.add(value),remove:value=>values.delete(value),
    contains:value=>values.has(value),toggle(value,enabled){
      if (enabled) values.add(value); else values.delete(value);
    }};
}
function makeElement(id) {
  let html = '';
  const element = {id,removed:false,classList:classList(),offsetTop:120,
    textContent:'',hidden:false,style:{},dataset:{},scrollIntoView:noop};
  Object.defineProperty(element,'innerHTML',{
    get:()=>html,
    set(value){
      if (element.removed) detachedWrites.push(id);
      html = value;
      if (id === 'cr-page-view' && /cr-page-header|No extracted text/.test(value)) {
        renders.push({document_id:_crDocId,page:_crPage});
      }
    },
  });
  return element;
}
const workspace = makeElement('reader-workspace');
let workspaceHtml = '';
Object.defineProperty(workspace,'content',{get:()=>workspaceHtml});
const readerWorkspace = {
  get innerHTML(){return workspaceHtml;},
  set innerHTML(value){
    workspaceHtml = value;
    for (const [id, element] of Object.entries(elements)) {
      element.removed = true;
      delete elements[id];
    }
  },
};
function installReaderDom() {
  for (const id of ['cr-page-view','cr-highlight-list','cr-hl-count']) {
    if (elements[id]) elements[id].removed = true;
    elements[id] = makeElement(id);
  }
}
installReaderDom();
const document = {
  body:{classList:classList()},querySelectorAll:()=>[],
  getElementById:id=>id === 'reader-workspace' ? readerWorkspace : elements[id] || null,
};
const window = {scrollTo:noop};
const _e10ShouldRecoverMissingWorkspace = () => false;
const _e10ApplyRouteChrome = id => {route=id;document.body.classList.toggle('reader-active',id==='reader');};
const _crRenderDocPicker = installReaderDom;
const _crMaybeShowReaderBanner = noop, _crRenderQuestionCard = noop;
const _crResetReaderTransientSelectionForContext = noop;
const _flnRender = noop, _cmpRender = noop, _fsApply = noop;
const _crSyncPageSpeechControls = noop, _crLoadRelated = noop;
const _crRefreshTrail = noop, _cmpRenderOnboarding = noop, cmpMarkOnboardingStep = noop;
const _crHighlightTags = () => [], _crAnnotationMetaHtml = () => '';
const _runtimeApplyWorkspaceDraftScope = noop, _wsRenderWorkspaceCatalog = noop;
const _wsWorkspaceMatches = (a,b) => a.id === b.id;
function runtimeApiFetch(url, options) {
  if (url !== '/api/reader/progress' || options.method !== 'POST') {
    throw Error('Unexpected write: ' + url);
  }
  progress.push(JSON.parse(options.body));
  return Promise.resolve({});
}
function get(url) {
  let resolve, reject;
  const promise = new Promise((yes,no) => {resolve=yes;reject=no;});
  requests.push({url,resolve,reject,settled:false});
  return promise;
}
const tick = () => new Promise(resolve => setImmediate(resolve));
function pending(url) {return requests.filter(request=>request.url===url && !request.settled);}
async function respond(url, payload, index=0, error=null) {
  const request = pending(url)[index];
  if (!request) throw Error('No pending request: ' + url);
  request.settled = true;
  if (error) request.reject(error); else request.resolve(payload);
  await tick();
}
const documentsUrl = '/api/reader/documents';
const pagesUrl = id => `/api/reader/documents/${id}/pages`;
const highlightsUrl = id => `/api/reader/documents/${id}/highlights`;
const docs = () => ({documents:[{id:'doc-a',source_role:'primary',last_page:62},
                              {id:'doc-b',source_role:'secondary',last_page:19}]});
const pages = () => ({pages:Array.from({length:85},(_,i)=>({page:i+1,extractions:[]})),total_pages:85});
async function finishDocument(id, highlights=[]) {
  await respond(pagesUrl(id),pages());
  if (pending(highlightsUrl(id)).length) await respond(highlightsUrl(id),{highlights});
}
function snapshot(extra={}) {
  return {doc:_crDocId,page:_crPage,route,renders,progress,detachedWrites,
    highlights:_crHighlights.map(row=>row.id),
    visible:elements['cr-page-view']?.innerHTML || '',workspaceHtml,
    requests:requests.map(row=>row.url),...extra};
}
function lineagedTarget(docId,page) {
  const context = {kind:'reader',document_id:docId,page,highlight_id:'real-mark'};
  const item = {record:{table:'reader_highlights',key:{id:'real-mark'}},
    event:'current_snapshot',authorship:'unknown',contexts:[context]};
  _studyLineageData = {schema:'hermeneia.study-lineage/v1',items:[item]};
  return {item,context};
}
""" + functions + "\n(async () => {\n" + scenario + r"""
})().catch(error => {console.error(error.stack);process.exitCode=1;});
"""


def _run(scenario: str) -> dict:
    return _run_node(_script(scenario))


def test_preserved_real_workspace_context_witness():
    witness = INDEX.parents[3] / "docs/verification/fixtures/study-lineage-v1-real-workspace/reader_context_witness.py"
    runpy.run_path(str(witness))["test_recorded_reader_context_reaches_its_recorded_page"]()


def test_lineage_same_document_waits_for_dom_and_explicit_page_beats_progress():
    result = _run(r"""
const {item,context} = lineagedTarget('doc-a',1);
const before = JSON.stringify(_studyLineageData);
let error = null, settled = false;
const opening = _studyLineageOpenContext(_studyLineageKey(item),_studyLineageContextKey(context))
  .then(()=>{settled=true;}).catch(e=>{error=e.message;});
await tick();
const whileLoading = {settled,hasPage:!!elements['cr-page-view'],renders:renders.length};
await respond(documentsUrl,docs());
await finishDocument('doc-a');
await opening;
process.stdout.write(JSON.stringify(snapshot({error,whileLoading,unchanged:before===JSON.stringify(_studyLineageData)})));
""")
    assert result["error"] is None
    assert result["whileLoading"] == {"settled": False, "hasPage": False, "renders": 0}
    assert result["page"] == 1
    assert result["renders"] == result["progress"] == [{"document_id": "doc-a", "page": 1}]
    assert result["unchanged"] is True
    assert result["detachedWrites"] == []


def test_cross_document_context_loads_requested_document_without_primary_restore():
    result = _run(r"""
const opening = _attnOpen('doc-b',7);
await respond(documentsUrl,docs());
await finishDocument('doc-b');
await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["doc"], result["page"]) == ("doc-b", 7)
    assert "/api/reader/documents/doc-a/pages" not in result["requests"]
    assert result["renders"] == result["progress"] == [{"document_id": "doc-b", "page": 7}]
    assert result["detachedWrites"] == []


def test_explicit_context_can_open_initially_unloaded_reader():
    result = _run(r"""
readerWorkspace.innerHTML = '';
_crDocId = null; _crPages = []; _crDocs = []; route = 'other';
const opening = _attnOpen('doc-b',4);
await respond(documentsUrl,docs());
await finishDocument('doc-b');
await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["route"], result["doc"], result["page"]) == ("reader", "doc-b", 4)
    assert result["renders"] == result["progress"] == [{"document_id": "doc-b", "page": 4}]
    assert result["detachedWrites"] == []


def test_ordinary_reader_open_restores_saved_progress():
    result = _run(r"""
const opening = e10Go('reader');
await respond(documentsUrl,docs());
await finishDocument('doc-a');
await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["doc"], result["page"]) == ("doc-a", 62)
    assert result["renders"] == result["progress"] == [{"document_id": "doc-a", "page": 62}]
    assert result["detachedWrites"] == []


def test_document_picker_still_restores_saved_progress():
    result = _run(r"""
const opening = _crOpenDoc('doc-b');
await finishDocument('doc-b');
await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["doc"], result["page"]) == ("doc-b", 19)
    assert result["renders"] == result["progress"] == [{"document_id": "doc-b", "page": 19}]
    assert result["detachedWrites"] == []


def test_document_open_without_reader_dom_does_not_cancel_active_reader_load():
    result = _run(r"""
const opening = e10Go('reader');
const premature = await _crOpenDoc('doc-b');
await respond(documentsUrl,docs());
await finishDocument('doc-a');
await opening;
process.stdout.write(JSON.stringify(snapshot({premature})));
""")
    assert result["premature"] is False
    assert (result["doc"], result["page"]) == ("doc-a", 62)
    assert result["renders"] == result["progress"] == [{"document_id": "doc-a", "page": 62}]
    assert result["detachedWrites"] == []


def test_normal_page_navigation_after_explicit_target_keeps_progress_updates():
    result = _run(r"""
const opening = _attnOpen('doc-a',1);
await respond(documentsUrl,docs());
await finishDocument('doc-a');
await opening;
_crNextPage();
_crPrevPage();
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["page"] == 1
    assert result["renders"] == result["progress"] == [
        {"document_id": "doc-a", "page": 1}, {"document_id": "doc-a", "page": 2},
        {"document_id": "doc-a", "page": 1},
    ]
    assert result["detachedWrites"] == []


def test_newest_context_wins_when_document_lists_complete_in_reverse_order():
    result = _run(r"""
const first = _attnOpen('doc-a',1);
const second = _attnOpen('doc-b',7);
await respond(documentsUrl,docs(),1);
await finishDocument('doc-b');
await second;
await respond(documentsUrl,docs());
await first;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["doc"], result["page"]) == ("doc-b", 7)
    assert "/api/reader/documents/doc-a/pages" not in result["requests"]
    assert result["renders"] == result["progress"] == [{"document_id": "doc-b", "page": 7}]
    assert result["detachedWrites"] == []


def test_same_document_newest_context_wins_over_late_page_response():
    result = _run(r"""
const first = _attnOpen('doc-a',1);
await respond(documentsUrl,docs());
const second = _attnOpen('doc-a',9);
await respond(documentsUrl,docs());
await respond(pagesUrl('doc-a'),pages(),1);
await respond(highlightsUrl('doc-a'),{highlights:[]});
await second;
await respond(pagesUrl('doc-a'),pages());
await first;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["page"] == 9
    assert result["requests"].count("/api/reader/documents/doc-a/highlights") == 1
    assert result["renders"] == result["progress"] == [{"document_id": "doc-a", "page": 9}]
    assert result["detachedWrites"] == []


def test_late_highlights_cannot_replace_new_document_or_render_removed_dom():
    result = _run(r"""
const first = _attnOpen('doc-a',1);
await respond(documentsUrl,docs());
await respond(pagesUrl('doc-a'),pages());
const second = _attnOpen('doc-b',7);
await respond(documentsUrl,docs());
await finishDocument('doc-b',[{id:'b-mark',page:7}]);
await second;
await respond(highlightsUrl('doc-a'),{highlights:[{id:'stale-a-mark',page:1}]});
await first;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["doc"], result["page"], result["highlights"]) == ("doc-b", 7, ["b-mark"])
    assert result["renders"] == result["progress"] == [{"document_id": "doc-b", "page": 7}]
    assert result["detachedWrites"] == []


def test_late_document_error_cannot_replace_new_success():
    result = _run(r"""
const first = _attnOpen('doc-a',1);
await respond(documentsUrl,docs());
const second = _attnOpen('doc-b',7);
await respond(documentsUrl,docs());
await finishDocument('doc-b');
await second;
await respond(pagesUrl('doc-a'),null,0,Error('old load failed'));
await first;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["doc"], result["page"]) == ("doc-b", 7)
    assert "Page 7 of 85" in result["visible"]
    assert "old load failed" not in result["workspaceHtml"]
    assert result["detachedWrites"] == []


def test_normal_open_supersedes_pending_explicit_context_and_restores_progress():
    result = _run(r"""
const explicit = _attnOpen('doc-b',7);
await respond(documentsUrl,docs());
const normal = e10Go('reader');
await respond(documentsUrl,docs());
await finishDocument('doc-a');
await normal;
await respond(pagesUrl('doc-b'),pages());
await explicit;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["doc"], result["page"]) == ("doc-a", 62)
    assert result["renders"] == result["progress"] == [{"document_id": "doc-a", "page": 62}]
    assert result["detachedWrites"] == []


def test_leaving_reader_cancels_pending_document_load_without_progress():
    result = _run(r"""
const opening = _attnOpen('doc-a',1);
await respond(documentsUrl,docs());
e10Go('unloaded-other-route');
await respond(pagesUrl('doc-a'),pages());
await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["route"] == "unloaded-other-route"
    assert result["renders"] == result["progress"] == []
    assert result["detachedWrites"] == []


def test_workspace_change_cancels_pending_reader_load_without_progress():
    result = _run(r"""
const opening = _attnOpen('doc-a',1);
await respond(documentsUrl,docs());
_wsApplyCurrentWorkspace({id:'workspace-b'});
await respond(pagesUrl('doc-a'),pages());
await opening;
process.stdout.write(JSON.stringify(snapshot({workspace:_wsCurrentWorkspace.id})));
""")
    assert result["workspace"] == "workspace-b"
    assert result["renders"] == result["progress"] == []
    assert result["detachedWrites"] == []


def test_unavailable_explicit_document_does_not_fall_back_to_primary():
    result = _run(r"""
const opening = _attnOpen('missing-doc',1);
await respond(documentsUrl,docs());
await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["renders"] == result["progress"] == []
    assert result["requests"] == ["/api/reader/documents"]
    assert result["workspaceHtml"]
    assert result["detachedWrites"] == []


def test_ordinary_next_during_highlight_load_keeps_user_page_over_saved_restore():
    result = _run(r"""
const opening = e10Go('reader');
await respond(documentsUrl,docs());
await respond(pagesUrl('doc-a'),pages());
_crNextPage();
await respond(highlightsUrl('doc-a'),{highlights:[]});
await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert (result["doc"], result["page"]) == ("doc-a", 63)
    assert result["renders"] == result["progress"] == [
        {"document_id": "doc-a", "page": 63}, {"document_id": "doc-a", "page": 63},
    ]
    assert result["detachedWrites"] == []
