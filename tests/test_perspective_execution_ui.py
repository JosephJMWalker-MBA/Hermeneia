"""Actual bounded Keep/Discard and read-only retained-context UI functions."""
from __future__ import annotations

import json

from test_perspective_room_ui_state import _extract_function, _index, _run_perspective_node


def _script(extra):
    source = _index()
    functions = "\n".join(_extract_function(source, signature) for signature in (
        "function _crRenderPerspectiveRetentionControls(",
        "function _crRenderRetainedPerspectiveExecution(",
        "async function _crDecidePerspectiveExecution(",
        "async function _crRunPerspective(",
        "function _crResetPerspectiveRoomStateForWorkspaceChange(",
        "function _studyLineageKey(", "function _studyLineageContextKey(",
        "async function _studyLineageOpenContext(",
    ))
    return r'''
    function element(value = '') { return {value, innerHTML:'',textContent:'',disabled:false,focus(){}}; }
    const elements = {
      'cr-perspective-run-btn': element(), 'cr-perspective-output': element(),
      'cr-perspective-status': element(), 'cr-perspective-retention': element(),
      'cr-perspective-select': element('close-reader'), 'cr-perspective-saved-select': element(),
      'cr-perspective-model': element('synthetic-model'),
      'cr-perspective-question': element('Original question?'),
      'study-lineage-context': element(),
    };
    const document = { getElementById(id) {return elements[id] || null;} };
    function x(value) {return String(value ?? '').replace(/[&<>"']/g,ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
    let calls = [], getCalls = [], errors = [], guideRefreshes = 0;
    const run = {
      run_id:'run/original ?',operation:'perspective_run',canonical_status:'not_persisted',
      perspective:{id:'close-reader',version:'1',label:'Close Reader'},
      question:'Original question?',scope_receipt:{primary:{text:'Original selected evidence'}},
      execution:{provider_id:'synthetic-stub',model_id:'synthetic-model'},response:'Exact model output',
      retention:{supported:true,state:'transient'},
    };
    const retained = {schema:'hermeneia.perspective-execution-receipt/v1',id:'receipt/original ?',
      run:{...run,created_at:'2026-09-30T10:00:00Z',completed_at:'2026-09-30T10:00:01Z',
        perspective:{id:'close-reader',version:'1',definition:{label:'Close Reader'}},
        prompt_sha256:'sha256:prompt',scope_sha256:'sha256:scope',response_sha256:'sha256:output'},
      retention:{decision:'retain',actor:'local_steward',actor_identity:'unknown',retained_at:'2026-09-30T10:00:02Z'}};
    async function post(url,payload) {calls.push([url,payload]);return url.endsWith('/discard') ? {state:'discarded'} : retained;}
    async function get(url) {getCalls.push(url);return retained;}
    function showAppError(message) {errors.push(message);}
    function _cmpRenderOnboarding() {guideRefreshes++;}
    function _crRenderPerspectiveScopeReceipt(scope) {return x(JSON.stringify(scope));}
    function _crRenderPerspectiveDefinitionReceipt() {return '';}
    function _crRenderPerspectiveRoom() {return 'Room remains transient';}
    function _crPerspectiveRenderScope() {}
    function _crRoomParticipantsPayload() {return null;}
    let _crPerspectiveWorkspaceEpoch = 0;
    let _crPerspectiveLastReceipt = structuredClone(run);
    let _crPerspectiveScope = {workspace_epoch:0,primary:{text:'Original selected evidence'}};
    let _crPerspectiveMode = 'single', _crPerspectiveKind = 'built-in';
    let _crPerspectiveDraftActive = null, _crPerspectiveDraftDirty = false;
    let _crPerspectiveRoomRoster = [], _crPerspectiveRoomRosterDirty = false;
    function _crPerspectiveScopeFromSelection() {return _crPerspectiveScope;}
    let _evidenceBoardEpoch = 0, _studyLineageContextSeq = 0, _evidenceBoardView = 'lineage';
    const item = {record:{table:'perspective_execution_receipts',key:{id:retained.id}},event:'recorded',
      contexts:[{kind:'perspective_execution',receipt_id:retained.id}]};
    let _studyLineageData = {items:[item]};
    function lineageHTML(value) {return JSON.stringify(value);}
    function _attnOpen() {throw new Error('Not a source-navigation operation');}
    ''' + functions + "\n" + extra


def _run(extra):
    return _run_perspective_node(_script(extra))


def test_transient_controls_have_two_explicit_decisions_and_no_achievement_claim():
    result = _run("process.stdout.write(JSON.stringify({html:_crRenderPerspectiveRetentionControls(run,0),calls}));")
    assert "Keep in study" in result["html"] and "Discard" in result["html"]
    assert "not retained in study" in result["html"]
    assert "does not mean agreement" in result["html"]
    assert "achievement" not in result["html"].lower()
    assert result["calls"] == []


def test_custom_and_room_receipts_cannot_gain_keep_controls():
    result = _run("""process.stdout.write(JSON.stringify({
      custom:_crRenderPerspectiveRetentionControls({...run,retention:{supported:false}},0),
      room:_crRenderPerspectiveRetentionControls({operation:'perspective_room'},0)}));""")
    assert result == {"custom": "", "room": ""}


def test_run_render_does_not_automatically_retain_provider_output():
    result = _run("""
    post = async(url,payload) => {calls.push([url,payload]);return structuredClone(run);};
    _crRunPerspective().then(() => process.stdout.write(JSON.stringify({calls,
      output:elements['cr-perspective-output'].innerHTML,last:_crPerspectiveLastReceipt})));
    """)
    assert len(result["calls"]) == 1 and result["calls"][0][0] == "/api/perspective/run"
    assert "Keep in study" in result["output"]
    assert result["last"]["canonical_status"] == "not_persisted"


def test_keep_uses_original_token_not_mutable_frame_scope_question_or_output_controls():
    result = _run("""
    elements['cr-perspective-question'].value = 'Later question';
    elements['cr-perspective-select'].value = 'skeptical-reader';
    _crPerspectiveScope = {workspace_epoch:0,primary:{text:'Later evidence'}};
    _crDecidePerspectiveExecution(run.run_id,0,'retain').then(() => process.stdout.write(JSON.stringify({
      calls,last:_crPerspectiveLastReceipt,guideRefreshes,output:elements['cr-perspective-output'].innerHTML})));
    """)
    assert result["calls"] == [["/api/perspective/executions/run%2Foriginal%20%3F/retain", {"decision": "retain"}]]
    assert result["last"]["retention"]["state"] == "retained"
    assert result["guideRefreshes"] == 1
    assert "Exact model output" in result["output"] and "Original question?" in result["output"]
    assert "Later question" not in result["output"] and "Later evidence" not in result["output"]


def test_discard_is_explicit_and_does_not_record_fake_rejection_or_negative_history():
    result = _run("""
    _crDecidePerspectiveExecution(run.run_id,0,'discard').then(() => process.stdout.write(JSON.stringify({
      calls,last:_crPerspectiveLastReceipt,output:elements['cr-perspective-output'].innerHTML,guideRefreshes})));
    """)
    assert result["calls"] == [["/api/perspective/executions/run%2Foriginal%20%3F/discard", {"decision": "discard"}]]
    assert result["last"] is None
    assert "No study execution receipt was created" in result["output"]
    assert "rejected" not in result["output"].lower() and result["guideRefreshes"] == 0


def test_stale_workspace_or_nonmatching_run_token_cannot_dispatch_a_decision():
    result = _run("""
    (async() => {
      await _crDecidePerspectiveExecution(run.run_id,1,'retain');
      await _crDecidePerspectiveExecution('another run',0,'retain');
      await _crDecidePerspectiveExecution(run.run_id,0,'accept');
      process.stdout.write(JSON.stringify({calls,last:_crPerspectiveLastReceipt}));
    })();
    """)
    assert result["calls"] == []
    assert result["last"]["retention"]["state"] == "transient"


def test_stale_keep_response_cannot_mark_another_workspace_as_retained():
    result = _run("""
    let finish;
    post = async(url,payload) => {calls.push([url,payload]);return new Promise(resolve => {finish=resolve});};
    const pending = _crDecidePerspectiveExecution(run.run_id,0,'retain');
    _crPerspectiveWorkspaceEpoch = 1; _crPerspectiveLastReceipt = null;
    elements['cr-perspective-output'].innerHTML = 'Another workspace';
    finish(retained);
    pending.then(() => process.stdout.write(JSON.stringify({calls,last:_crPerspectiveLastReceipt,
      output:elements['cr-perspective-output'].innerHTML,guideRefreshes})));
    """)
    assert len(result["calls"]) == 1
    assert result["last"] is None and result["output"] == "Another workspace"
    assert result["guideRefreshes"] == 0


def test_pending_keep_prevents_duplicate_ui_dispatch():
    result = _run("""
    let finish;
    post = async(url,payload) => {calls.push([url,payload]);return new Promise(resolve => {finish=resolve});};
    const pending = _crDecidePerspectiveExecution(run.run_id,0,'retain');
    const repeat = _crDecidePerspectiveExecution(run.run_id,0,'retain');
    finish(retained);
    Promise.all([pending,repeat]).then(() => process.stdout.write(JSON.stringify({calls})));
    """)
    assert len(result["calls"]) == 1


def test_failed_keep_leaves_result_transient_and_allows_exact_retry():
    result = _run("""
    let failed = false;
    post = async(url,payload) => {calls.push([url,payload]);if(!failed){failed=true;throw new Error('Write refused');}return retained;};
    (async() => {
      await _crDecidePerspectiveExecution(run.run_id,0,'retain');
      const failure = structuredClone(_crPerspectiveLastReceipt);
      await _crDecidePerspectiveExecution(run.run_id,0,'retain');
      process.stdout.write(JSON.stringify({calls,failure,last:_crPerspectiveLastReceipt,errors}));
    })();
    """)
    assert len(result["calls"]) == 2
    assert result["failure"]["retention"] == {"supported": True, "state": "transient", "pending": False}
    assert result["last"]["retention"]["state"] == "retained"
    assert result["errors"] == ["Write refused"]


def test_retained_context_fetches_exact_receipt_read_only_and_preserves_authorship_distinction():
    result = _run("""
    _studyLineageOpenContext(_studyLineageKey(item),_studyLineageContextKey(item.contexts[0])).then(() =>
      process.stdout.write(JSON.stringify({getCalls,calls,html:elements['study-lineage-context'].innerHTML})));
    """)
    assert result["getCalls"] == ["/api/perspective/executions/receipt%2Foriginal%20%3F"]
    assert result["calls"] == []
    assert "Model-generated output · explicitly human-retained" in result["html"]
    assert "individual identity unknown" in result["html"]
    assert "not mean agreement" in result["html"]
    assert "Keep in study" not in result["html"]


def test_retained_context_response_after_workspace_switch_is_ignored():
    result = _run("""
    let finish;
    get = async(url) => {getCalls.push(url);return new Promise(resolve => {finish=resolve});};
    const pending = _studyLineageOpenContext(_studyLineageKey(item),_studyLineageContextKey(item.contexts[0]));
    _evidenceBoardEpoch = 1;
    elements['study-lineage-context'].innerHTML = 'New workspace';
    finish(retained);
    pending.then(() => process.stdout.write(JSON.stringify({getCalls,calls,html:elements['study-lineage-context'].innerHTML})));
    """)
    assert result["html"] == "New workspace" and result["calls"] == []


def test_separate_saved_profile_context_is_not_offered_as_a_read_only_receipt_link():
    result = _run("""
    item.contexts = [{kind:'perspective',perspective_id:'perspective-frame-v2:historical'}];
    get = async(url) => {getCalls.push(url);return {id:'perspective-frame-v2:historical',label:'Historical frame',is_current_leaf:false};};
    _studyLineageOpenContext(_studyLineageKey(item),_studyLineageContextKey(item.contexts[0])).then(() =>
      process.stdout.write(JSON.stringify({getCalls,calls,html:elements['study-lineage-context'].innerHTML})));
    """)
    assert result["getCalls"] == result["calls"] == []
    assert result["html"] == ""


def test_retained_renderer_escapes_model_output_question_and_provenance():
    hostile = "<img src=x onerror=alert(1)>"
    result = _run(f"""
    retained.run.response = {json.dumps(hostile)};
    retained.run.question = {json.dumps(hostile)};
    retained.run.execution.model_id = {json.dumps(hostile)};
    process.stdout.write(JSON.stringify({{html:_crRenderRetainedPerspectiveExecution(retained)}}));
    """)
    assert "<img" not in result["html"] and "&lt;img" in result["html"]


def test_workspace_switch_clears_old_keepable_display_without_sending_discard():
    result = _run("""
    elements['cr-perspective-output'].innerHTML = 'Old Keep control';
    _crResetPerspectiveRoomStateForWorkspaceChange();
    process.stdout.write(JSON.stringify({epoch:_crPerspectiveWorkspaceEpoch,last:_crPerspectiveLastReceipt,
      output:elements['cr-perspective-output'].innerHTML,calls}));
    """)
    assert result == {"epoch": 1, "last": None, "output": "", "calls": []}
