"""Promoted regression from the frozen real-workspace Lineage witness.

No study is created or modified. The real IDs/page metadata are sanitized;
source text is unnecessary. Actual production navigation functions run against
the minimum DOM/HTTP scheduling needed to reproduce the observed failure.
Commit 5e14463 preserves the negative version; M0 reproduced it before repair
and demonstrated a strict unexpected pass before removing the expected failure.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "tests"))
from test_evidence_board_ui import _extract_function


class KnownReaderContextFailure(AssertionError):
    """Only the exact observed navigation failure is expected here."""


def test_recorded_reader_context_reaches_its_recorded_page():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the frozen production-JavaScript witness")
    evidence = json.loads((HERE / "reader-context-witness.json").read_text())
    html = (ROOT / "hermeneia/web/static/index.html").read_text()
    signatures = [
        "function _studyLineageKey(", "function _studyLineageContextKey(",
        "async function _studyLineageOpenContext(", "function _attnOpen(",
        "function e10Go(", "async function e10LoadCloseReader(",
        "function _crGoToPage(", "function _crRenderPage(", "async function _crOpenDoc(",
    ]
    functions = "\n".join(_extract_function(html, signature) for signature in signatures)
    script = "const evidence = " + json.dumps(evidence) + ";\n" + r"""
const context = evidence.context;
const item = {record:evidence.record, event:'current_snapshot', contexts:[context]};
let _studyLineageData = {items:[item]}, _expert = false;
let _crReaderLoadSeq = 0;
let _crDocId = context.document_id, _crPage = evidence.saved_last_page;
let _crDocs = [{id:_crDocId, source_role:'primary', last_page:_crPage}];
let _crPages = [{page:1,extractions:[]},{page:62,extractions:[]}], _crTotalPages = 85;
let _crHighlights = [], _crCurrentExtractions = [], _register = 'expert';
const noop = () => {};
const element = () => ({innerHTML:'',classList:{add:noop,remove:noop,toggle:noop},offsetTop:0});
let pageView = element();
const workspace = {};
// This is the native DOM consequence of the actual e10LoadCloseReader
// assigning its loading placeholder: the old page child ceases to exist.
Object.defineProperty(workspace,'innerHTML',{set(){pageView = null;}});
const document = {
  body:{classList:{remove:noop}}, querySelectorAll:()=>[],
  getElementById:id => id === 'reader-workspace' ? workspace : id === 'cr-page-view' ? pageView : null,
};
const window = {scrollTo:noop};
const _e10ShouldRecoverMissingWorkspace = () => false;
const _e10ApplyRouteChrome = noop, _crResetReaderTransientSelectionForContext = noop;
const _crMaybeShowReaderBanner = noop, _crRenderQuestionCard = noop;
const _flnRender = noop, _cmpRender = noop, _fsApply = noop;
const _crSyncPageSpeechControls = noop, _crLoadRelated = noop;
const _crRefreshTrail = noop, _cmpRenderOnboarding = noop, cmpMarkOnboardingStep = noop;
const _crLoadHighlightList = async () => {};
const x = String;
const _crRenderDocPicker = () => {pageView = element();};
const runtimeApiFetch = async () => ({}); // No request, provider, or database.
let releaseDocuments;
const documentsPending = new Promise(resolve => {releaseDocuments = resolve;});
const get = async url => url === '/api/reader/documents' ? documentsPending :
  {pages:[{page:1,extractions:[]},{page:62,extractions:[]}],total_pages:85};
""" + functions + r"""
(async () => {
  let error = null;
  const navigation = _studyLineageOpenContext(_studyLineageKey(item), _studyLineageContextKey(context))
    .catch(e => {error = {name:e.name,message:e.message};});
  // Complete the already-started Reader load. No timers or timing assumptions.
  releaseDocuments({documents:_crDocs});
  await navigation;
  await new Promise(resolve => setImmediate(resolve));
  process.stdout.write(JSON.stringify({error,page:_crPage,visible:pageView.innerHTML}));
})();
"""
    completed = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    observed = json.loads(completed.stdout)
    # Retain the exact original failure classification as a regression diagnostic.
    if (observed["error"] == {"name": "TypeError", "message": "Cannot set properties of null (setting 'innerHTML')"}
            and observed["page"] == evidence["saved_last_page"]):
        raise KnownReaderContextFailure({"error": observed["error"], "settled_page": observed["page"],
                                         "requested_page": evidence["context"]["page"]})
    assert observed["error"] is None and observed["page"] == evidence["context"]["page"], observed
