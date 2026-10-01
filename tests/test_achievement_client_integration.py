"""Execute the actual bounded client functions; all study evidence is synthetic."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import select

import pytest

from test_evidence_board_ui import _extract_function, _run_node


INDEX = Path(__file__).parents[1] / "hermeneia/web/static/index.html"
BASE = "/api/achievements/perspective"
EXPLORER = "perspective_explorer"
SECOND = "second_opinion"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def _block():
    source = INDEX.read_text()
    return source[source.index("// Perspective accomplishments are explicit"):
                  source.index("// End Perspective accomplishments")]


def _script(scenario, *, rpc=False):
    transport = r"""
function request(method,url,body){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
  requests.push({method,url,body,resolve,reject,done:false});return promise;}
function get(url){return request('GET',url);}
function post(url,body){return request('POST',url,body);}
function respond(row,body){row.done=true;row.resolve(structuredClone(body));}
function refuse(row,status,reason_code='REFUSED'){row.done=true;row.reject(new RuntimeHttpError(
  'PRIVATE SERVER TRACEBACK MUST NOT ENTER UI',{status},{reason_code,error:'PRIVATE SERVER TRACEBACK MUST NOT ENTER UI'}));}
async function resolveReads(overrides={}){
  for(let iteration=0;iteration<5;iteration++){
    const pending=requests.filter(row=>row.method==='GET'&&!row.done);
    if(!pending.length){await tick();if(!requests.some(row=>row.method==='GET'&&!row.done))return;continue;}
    for(const row of pending){const value=overrides[row.url]??(row.url.endsWith('/assessment')?
      assessment(row.url.includes('/second_opinion/')?'second_opinion':'perspective_explorer'):
      row.url.endsWith('/verification')?verification:
      row.url.includes('/awards/')?{award_id:award.award_id,receipt_representation:'safe_summary',receipt_projection:award}:
      {awards:[],receipt_representation:'safe_summary'});respond(row,value);}
    await tick();
  }
}
"""
    if rpc:
        transport = r"""
const readline=require('readline');const incoming=readline.createInterface({input:process.stdin});
let rpcSeq=0;const rpcPending=new Map();
incoming.on('line',line=>{const reply=JSON.parse(line),pending=rpcPending.get(reply.id);rpcPending.delete(reply.id);
  if(reply.status>=400)pending.reject(new RuntimeHttpError(reply.data.error,{status:reply.status},reply.data));else pending.resolve(reply.data);});
function rpc(method,url,body){const id=++rpcSeq;return new Promise((resolve,reject)=>{
 rpcPending.set(id,{resolve,reject});requests.push({method,url,body});
 process.stdout.write(JSON.stringify({kind:'request',id,method,url,body})+'\n');});}
function get(url){return rpc('GET',url);}
function post(url,body){return rpc('POST',url,body);}
function mutateStudy(){return rpc('MUTATE','study');}
function done(extra={}){process.stdout.write(JSON.stringify({kind:'result',data:snapshot(extra)})+'\n');incoming.close();}
"""
    return r"""
const requests=[],preferences=[],navigation=[],elements={};
function element(id){return elements[id]={id,innerHTML:'',textContent:'',disabled:false,hidden:false,open:false,
 attrs:{},style:{},dataset:{},listeners:{},classList:{add(){},remove(){},toggle(){}},
 focus(){document.activeElement=this;},scrollIntoView(){},setAttribute(k,v){this.attrs[k]=String(v);},
 contains(node){return node===this||!!(node?.id&&this.innerHTML.includes('id="'+node.id+'"'));},
 getAttribute(k){return this.attrs[k];},addEventListener(k,fn){this.listeners[k]=fn;},
 querySelector(){return elements['cmp-accomplishments-detail-title'];},querySelectorAll(){return [];}};}
['cmp-accomplishments-host','cmp-accomplishments-detail','cmp-accomplishments-detail-title',
 'review-invoker','inspect-invoker','cmp-onboarding-host','cmp-onboarding-host-firstrun',
 'cr-perspective-output','cr-perspective-retention','cr-perspective-status'].forEach(element);
const document={activeElement:elements['review-invoker'],listeners:{},getElementById:id=>elements[id]||null,
 querySelector:()=>elements['cmp-accomplishments-detail-title'],querySelectorAll:()=>[],
 addEventListener(k,fn){this.listeners[k]=fn;}};
const window={listeners:{},addEventListener(k,fn){this.listeners[k]=fn;}};
const localStorage={getItem(){return null;},setItem(k,v){preferences.push([k,v]);},removeItem(k){preferences.push([k]);}};
const x=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
class RuntimeHttpError extends Error{constructor(message,response,data){super(message);this.status=response.status;this.data=data;}}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function _dockOpenPanel(key){navigation.push(['dock',key]);}
function _dockClosePanel(){navigation.push(['close']);}
function _cmpRenderOnboarding(){navigation.push(['guide']);}
function showAppError(){throw Error('Accomplishments must not display unbounded server errors');}
function fetch(){throw Error('Do not bypass the local governed API helpers');}
function runtimeApiFetch(){throw Error('Do not bypass the local governed API helpers');}
function provider(){throw Error('No provider required for accomplishment UI');}
const _runtimeIsEndpointError=error=>!!error?.endpointUnreachable;
let _cmpStudyWorkspaceEpoch=0;
function assessment(id='perspective_explorer',status='earned',digest='sha256:'+'a'.repeat(64)){
 const ids=id==='second_opinion'?['receipt-left','receipt-right']:['receipt-left'];
 return {achievement_id:id,rule_id:'achievement.'+id,rule_version:'1.0.0',rule_reference:'achievement.'+id+'.v1.0.0',
 status,reason_code:'SERVER_STATE',reason:'Safe server explanation.',qualifying_receipt_ids:status==='earned'?ids:[],
 evidence_refs:[],coverage:{status:'supported',historical_completeness:'extant_only'},limitations:['Historical limits are retained.'],
 assessment_package_sha256:status==='earned'?digest:null,assessment_package:status==='earned'?{
   profile:'perspective-achievement-evidence-package/v1',assessment:{finding:{qualifying_receipt_ids:ids}},
   adapter_basis:{private:'PRIVATE SOURCE PASSAGE',prompt:'PRIVATE PERSPECTIVE PROMPT',response:'PRIVATE MODEL RESPONSE'}}:null};}
const award={award_id:'achievement-award:sha256:'+'1'.repeat(64),achievement_id:'perspective_explorer',
 rule_id:'achievement.perspective_explorer',rule_version:'1.0.0',earned_at:'2026-09-30T10:01:00+00:00',
 awarded_at:'2026-10-01T11:00:00+00:00',evaluation_status:'earned',issuer:{kind:'hermeneia',authorship:'derived'},
 evidence_refs:[{table:'perspective_execution_receipts',key:{id:'receipt-left'}}],
 coverage:{status:'supported'},verification:{receipt_integrity:'valid',evidence_verification:'not_performed',historical_snapshot_replay:'unsupported'}};
const verification={award_id:award.award_id,receipt_integrity:'valid',evidence_verification:'verified',historical_snapshot_replay:'verified',
 checks:[],limitations:['Historical verification has limits.']};
""" + transport + _block() + r"""
function snapshot(extra={}){return {html:elements['cmp-accomplishments-host'].innerHTML,
 requests:requests.map(({method,url,body})=>({method,url,body})),preferences,navigation,
 state:JSON.parse(JSON.stringify(_cmpAccomplishments)),focused:document.activeElement?.id,...extra};}
(async()=>{
""" + scenario + r"""
})().catch(error=>{console.error(error.stack);if(typeof incoming!=='undefined')incoming.close();process.exitCode=1;});
"""


def _run(scenario):
    return _run_node(_script(scenario))


def _opened(scenario=""):
    return _run("const opening=_cmpAccomplishmentsOpen();await resolveReads();await opening;\n" + scenario)


def _opened_with_history(scenario):
    return _run("const opening=_cmpAccomplishmentsOpen();await resolveReads({['" + BASE +
                "/awards']:{awards:[award],receipt_representation:'safe_summary'}});await opening;\n" + scenario)


def _posts(result):
    return [row for row in result["requests"] if row["method"] == "POST"]


def test_closed_surface_lists_only_two_supported_achievements_and_never_issues():
    result = _run("_cmpRenderAccomplishments();process.stdout.write(JSON.stringify(snapshot()));")
    assert "Study accomplishments" in result["html"]
    assert result["requests"] == [] and result["preferences"] == []
    block = _block()
    for unsupported in ("Multiple Lenses", "Dissent Finder", "Changed My Mind", "Full Cycle", "XP", "confetti"):
        assert unsupported not in block


def test_opening_loads_exact_current_assessments_and_history_without_post():
    result = _opened("process.stdout.write(JSON.stringify(snapshot()));")
    assert {row["url"] for row in result["requests"]} == {
        f"{BASE}/{EXPLORER}/assessment", f"{BASE}/{SECOND}/assessment", f"{BASE}/awards"}
    assert _posts(result) == []
    assert "Perspective Explorer" in result["html"] and "Second Opinion" in result["html"]
    assert "Review and record" in result["html"]


@pytest.mark.parametrize("status,label", [("not_earned", "No qualifying"),
    ("unsupported_due_to_missing_coverage", "History unavailable"), ("invalid_evidence", "Unable to verify")])
def test_non_earned_states_are_distinct_and_cannot_open_approval(status, label):
    result = _run(f"""
const opening=_cmpAccomplishmentsOpen();await resolveReads({{{json.dumps(f'{BASE}/{EXPLORER}/assessment')}:assessment('{EXPLORER}',{json.dumps(status)})}});await opening;
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);
await _cmpAccomplishmentsRecord();process.stdout.write(JSON.stringify(snapshot()));
""")
    assert label in result["html"] and _posts(result) == []
    assert result["state"]["review"] is None
    assert "Badge" not in result["html"]


def test_earned_review_is_read_only_and_captures_server_rule_version_digest():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert _posts(result) == []
    assert "achievement.perspective_explorer" in result["html"] and "1.0.0" in result["html"]
    assert "Record achievement" in result["html"] and "Cancel" in result["html"]
    assert result["state"]["review"] is not None
    assert result["focused"] == "cmp-accomplishments-detail-title"


@pytest.mark.parametrize("marker", ["PRIVATE SOURCE PASSAGE", "PRIVATE PERSPECTIVE PROMPT", "PRIVATE MODEL RESPONSE"])
def test_review_never_renders_full_private_assessment_package(marker):
    result = _opened(f"_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);process.stdout.write(JSON.stringify(snapshot()));")
    assert marker not in result["html"]
    assert "adapter_basis" not in result["html"] and "assessment_package_sha256" not in result["html"]


def test_closing_review_discards_approval_and_restores_invoking_focus():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);_cmpAccomplishmentsClose();
await _cmpAccomplishmentsRecord();process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["state"]["review"] is None and _posts(result) == []
    assert result["focused"] == "review-invoker"


@pytest.mark.parametrize("achievement", [EXPLORER, SECOND])
def test_final_click_posts_only_exact_approved_request(achievement):
    result = _opened(f"""
_cmpAccomplishmentsReview('{achievement}',elements['review-invoker']);const record=_cmpAccomplishmentsRecord();await tick();
const sent=requests.find(row=>row.method==='POST');respond(sent,{{status:'recorded',award_id:award.award_id,receipt_representation:'safe_summary',receipt_projection:award}});
await resolveReads({{{json.dumps(f'{BASE}/awards')}:{{awards:[award],receipt_representation:'safe_summary'}}}});await record;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert _posts(result) == [{"method": "POST", "url": f"{BASE}/{achievement}/award", "body": {
        "rule_id": "achievement." + achievement, "rule_version": "1.0.0", "assessment_package_sha256": DIGEST_A}}]
    assert "Historical" in result["html"] and "Inspect" in result["html"]
    assert result["preferences"] == []


def test_pending_record_disables_approval_and_blocks_rapid_double_click():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);
const first=_cmpAccomplishmentsRecord();const second=_cmpAccomplishmentsRecord();await tick();
const pending=snapshot();const sent=requests.find(row=>row.method==='POST');
respond(sent,{{status:'recorded',award_id:award.award_id,receipt_projection:award,receipt_representation:'safe_summary'}});
await resolveReads();await Promise.all([first,second]);process.stdout.write(JSON.stringify(snapshot({{pending}})));
""")
    assert len(_posts(result)) == 1
    assert result["pending"]["state"]["pending"] is True
    assert "disabled" in result["pending"]["html"]


def test_stale_refusal_does_not_fetch_or_issue_new_intent_automatically():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const record=_cmpAccomplishmentsRecord();await tick();
refuse(requests.find(row=>row.method==='POST'),409,'STALE_ASSESSMENT');await record;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert len(result["requests"]) == 4 and len(_posts(result)) == 1
    assert "study changed" in result["html"].lower()
    assert "Review updated assessment" in result["html"]
    assert result["state"]["review"] is None


def test_stale_updated_review_requires_second_explicit_record_click():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const first=_cmpAccomplishmentsRecord();await tick();
refuse(requests.find(row=>row.method==='POST'),409,'STALE_ASSESSMENT');await first;
const updating=_cmpAccomplishmentsReviewUpdated('{EXPLORER}');await resolveReads({{{json.dumps(f'{BASE}/{EXPLORER}/assessment')}:assessment('{EXPLORER}','earned',{json.dumps(DIGEST_B)})}});await updating;
const reviewed=snapshot();const second=_cmpAccomplishmentsRecord();await tick();const latest=requests.filter(row=>row.method==='POST').at(-1);
respond(latest,{{status:'recorded',award_id:award.award_id,receipt_projection:award,receipt_representation:'safe_summary'}});await resolveReads();await second;
process.stdout.write(JSON.stringify(snapshot({{reviewed}})));
""")
    assert len(_posts(result["reviewed"])) == 1
    assert [row["body"]["assessment_package_sha256"] for row in _posts(result)] == [DIGEST_A, DIGEST_B]


@pytest.mark.parametrize("status", [400, 404, 409, 500])
def test_refused_record_never_displays_raw_server_error_or_optimistic_history(status):
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const record=_cmpAccomplishmentsRecord();await tick();
refuse(requests.find(row=>row.method==='POST'),{status});await record;process.stdout.write(JSON.stringify(snapshot()));
""")
    assert "PRIVATE SERVER TRACEBACK" not in result["html"]
    assert result["state"]["history"] == [] and len(_posts(result)) == 1


def test_lost_record_response_requires_history_reconciliation_before_another_attempt():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const record=_cmpAccomplishmentsRecord();await tick();
const sent=requests.find(row=>row.method==='POST');sent.done=true;sent.reject(new TypeError('PRIVATE NETWORK DETAIL'));await record;
const unknown=snapshot();_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);await _cmpAccomplishmentsRecord();
const blocked=snapshot();const refresh=_cmpAccomplishmentsRefresh();await resolveReads({{{json.dumps(f'{BASE}/awards')}:{{awards:[award],receipt_representation:'safe_summary'}}}});await refresh;
process.stdout.write(JSON.stringify(snapshot({{unknown,blocked}})));
""")
    assert result["unknown"]["state"]["reconcile"] is True
    assert result["unknown"]["state"]["history"] == []
    assert len(_posts(result["blocked"])) == 1 and len(_posts(result)) == 1
    assert "PRIVATE NETWORK DETAIL" not in result["html"]
    assert result["state"]["reconcile"] is False


def test_history_preserves_server_order_and_does_not_recompute_current_eligibility():
    result = _run(f"""
const first={{...award,award_id:'server-first',achievement_id:'second_opinion',awarded_at:'2025-01-01T00:00:00Z'}};
const second={{...award,award_id:'server-second',awarded_at:'2020-01-01T00:00:00Z'}};
const opening=_cmpAccomplishmentsOpen();await resolveReads({{{json.dumps(f'{BASE}/awards')}:{{awards:[first,second],receipt_representation:'safe_summary'}}}});await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert [row["award_id"] for row in result["state"]["history"]] == ["server-first", "server-second"]
    assert _posts(result) == []


def test_zero_history_is_usable_and_never_fabricates_an_award():
    result = _opened("process.stdout.write(JSON.stringify(snapshot()));")
    assert result["state"]["history"] == []
    assert "No" in result["html"] and "Record achievement" not in result["html"]
    assert _posts(result) == []


def test_inspection_loads_detail_and_verification_only_without_evidence_reacharound():
    result = _opened_with_history("""
const inspection=_cmpAccomplishmentsInspect(award.award_id,elements['inspect-invoker']);await resolveReads();await inspection;
process.stdout.write(JSON.stringify(snapshot()));
""")
    urls = [row["url"] for row in result["requests"]][3:]
    assert urls == [f"{BASE}/awards/achievement-award%3Asha256%3A" + "1" * 64,
                    f"{BASE}/awards/achievement-award%3Asha256%3A" + "1" * 64 + "/verification"]
    assert "Receipt integrity" in result["html"] and "Evidence verification" in result["html"]
    assert "Historical replay" in result["html"] and _posts(result) == []


@pytest.mark.parametrize("state,label", [
    ("unverifiable_missing_evidence", "unavailable"), ("unverifiable_missing_coverage", "coverage"),
    ("unverifiable_unsupported_rule", "rule"), ("invalid_evidence", "validation")])
def test_verification_limits_do_not_hide_or_revoke_historical_award(state, label):
    result = _opened_with_history(f"""
const inspecting=_cmpAccomplishmentsInspect(award.award_id,elements['inspect-invoker']);
await resolveReads({{[`{BASE}/awards/${{encodeURIComponent(award.award_id)}}/verification`]:{{...verification,evidence_verification:{json.dumps(state)},historical_snapshot_replay:'unsupported'}}}});
await inspecting;process.stdout.write(JSON.stringify(snapshot()));
""")
    assert "Perspective Explorer" in result["html"]
    assert label in result["html"].lower()
    assert "Historical replay" in result["html"] and "unsupported" in result["html"].lower()
    assert _posts(result) == []


def test_inspection_uses_safe_summary_whitelist_and_escapes_metadata():
    result = _opened_with_history("""
const hostile={...award,rule_id:'<img src=x onerror=alert(1)>',raw_text:'PRIVATE SOURCE PASSAGE',response:'PRIVATE MODEL RESPONSE',prompt:'PRIVATE PERSPECTIVE PROMPT'};
const inspecting=_cmpAccomplishmentsInspect(award.award_id,elements['inspect-invoker']);
await resolveReads({[`${'""" + BASE + """'}/awards/${encodeURIComponent(award.award_id)}`]:{award_id:award.award_id,receipt_representation:'safe_summary',receipt_projection:hostile}});await inspecting;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert "<img" not in result["html"] and "&lt;img" in result["html"]
    for marker in ("PRIVATE SOURCE PASSAGE", "PRIVATE MODEL RESPONSE", "PRIVATE PERSPECTIVE PROMPT"):
        assert marker not in result["html"]


def test_workspace_reset_discards_old_assessment_and_approval():
    result = _run(f"""
const opening=_cmpAccomplishmentsOpen();_cmpAccomplishmentsReset();await resolveReads();await opening;
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);await _cmpAccomplishmentsRecord();
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["state"]["assessments"] == {} and result["state"]["review"] is None
    assert result["state"]["history"] is None and _posts(result) == []


def test_latest_refresh_wins_over_out_of_order_current_assessment_responses():
    result = _run("""
const old=_cmpAccomplishmentsOpen();const oldRequests=[...requests];const fresh=_cmpAccomplishmentsRefresh();
for(const row of requests.filter(row=>!oldRequests.includes(row))){respond(row,row.url.endsWith('/assessment')?assessment(row.url.includes('/second_opinion/')?'second_opinion':'perspective_explorer','earned','sha256:'+'b'.repeat(64)):{awards:[],receipt_representation:'safe_summary'});}
await fresh;for(const row of oldRequests){respond(row,row.url.endsWith('/assessment')?assessment():{awards:[],receipt_representation:'safe_summary'});}await old;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["state"]["assessments"][EXPLORER]["digest"] == DIGEST_B
    assert _posts(result) == []


def test_workspace_change_ignores_late_inspection_response():
    result = _opened_with_history("""
const inspecting=_cmpAccomplishmentsInspect(award.award_id,elements['inspect-invoker']);_cmpAccomplishmentsReset();
await resolveReads();await inspecting;process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["state"]["inspection"] is None
    assert "2026-10-01" not in result["html"] and _posts(result) == []


def test_unknown_earned_shape_cannot_be_recorded():
    result = _run(f"""
const invalid=assessment();delete invalid.assessment_package_sha256;
const opening=_cmpAccomplishmentsOpen();await resolveReads({{{json.dumps(f'{BASE}/{EXPLORER}/assessment')}:invalid}});await opening;
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);await _cmpAccomplishmentsRecord();process.stdout.write(JSON.stringify(snapshot()));
""")
    assert _posts(result) == [] and result["state"]["review"] is None


def test_client_does_not_compute_rules_digests_award_identity_or_save_authority():
    block = _block()
    for forbidden in ("crypto.subtle", "createHash", "SHA256(", "localStorage", "sessionStorage",
                      "qualifying_receipt_ids.length >=", "scope_sha256 ===", "question_sha256 ===",
                      "/api/perspective/run", "/api/perspective/room", "setInterval("):
        assert forbidden not in block
    assert block.count("await post(") == 1


def test_new_surface_is_bounded_adjacent_to_study_cycle_with_accessible_region():
    source = INDEX.read_text()
    assert source.count('id="cmp-accomplishments-host"') == 1
    block = _block()
    assert 'role="region"' in block and 'aria-labelledby="cmp-accomplishments-detail-title"' in block
    assert 'id="cmp-accomplishments-detail-title"' in block and 'tabindex="-1"' in block
    assert 'aria-live="polite"' in block
    assert "Escape" in block


def test_verified_historical_replay_copy_is_distinct_from_current_evidence_verification():
    result = _run("""
process.stdout.write(JSON.stringify({
 evidence:_cmpAccomplishmentsVerificationLabel('evidence_verification','verified'),
 replay:_cmpAccomplishmentsVerificationLabel('historical_snapshot_replay','verified'),
 receipt:_cmpAccomplishmentsVerificationLabel('receipt_integrity','valid'),
 unsupported:_cmpAccomplishmentsVerificationLabel('historical_snapshot_replay','unsupported')
}));
""")
    assert result["evidence"] == "Verified from the currently available canonical evidence."
    assert result["replay"] == "Original historical assessment replayed under its recorded profile."
    assert result["receipt"] == "Valid receipt integrity."
    assert result["unsupported"] == "Historical replay is not available from the evidence currently present."


@pytest.mark.parametrize("action", ["render", "guide", "reset", "lineage"])
def test_existing_navigation_and_page_reset_do_not_issue(action):
    source = INDEX.read_text()
    render = _extract_function(source, "function _cmpRenderOnboarding(")
    opening = _extract_function(source, "function cmpOpenOnboarding(")
    result = _run("""
function _cmpOnboardingHtml(){return 'Existing Study Cycle';}
let _cmpStudyCycleLoading=false;function _cmpLoadStudyCycle(){navigation.push(['GET-guide']);return Promise.resolve();}
function _cmpDefaultOnboardingState(){return {paused:false,dismissed:false};}
function _cmpSaveOnboardingState(value){preferences.push(value);return value;}
""" + render + "\n" + opening + "\n" + {
        "render": "_cmpRenderOnboarding();",
        "guide": "cmpOpenOnboarding();",
        "reset": "_cmpAccomplishmentsReset();_cmpRenderAccomplishments();",
        "lineage": "navigation.push(['lineage']);_cmpRenderAccomplishments();",
    }[action] + "process.stdout.write(JSON.stringify(snapshot()));")
    assert _posts(result) == []
    assert not result["state"]["review"]


def test_existing_perspective_keep_does_not_record_an_achievement():
    source = INDEX.read_text()
    keep = _extract_function(source, "async function _crDecidePerspectiveExecution(")
    result = _run("""
let _crPerspectiveWorkspaceEpoch=0;
let _crPerspectiveLastReceipt={run_id:'synthetic-run',retention:{state:'transient'}};
function _crRenderRetainedPerspectiveExecution(){return 'Existing retained result';}
function _crRenderPerspectiveRetentionControls(){return '';}
post=async(url,body)=>{requests.push({method:'POST',url,body});return {id:'synthetic-p3-receipt'};};
""" + keep + "\nawait _crDecidePerspectiveExecution('synthetic-run',0,'retain');process.stdout.write(JSON.stringify(snapshot()));")
    assert _posts(result) == [{"method": "POST", "url": "/api/perspective/executions/synthetic-run/retain", "body": {"decision": "retain"}}]
    assert not any("/award" in row["url"] for row in result["requests"])


def test_already_recorded_uses_original_server_time_and_one_historical_item():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const record=_cmpAccomplishmentsRecord();await tick();
respond(requests.find(row=>row.method==='POST'),{{status:'already_recorded',award_id:award.award_id,receipt_representation:'safe_summary',receipt_projection:award}});
await resolveReads({{{json.dumps(f'{BASE}/awards')}:{{awards:[award],receipt_representation:'safe_summary'}}}});await record;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert len(result["state"]["history"]) == 1
    assert result["state"]["history"][0]["awarded_at"] == "2026-10-01T11:00:00+00:00"
    assert "earned again" not in result["html"].lower()


def test_assessment_read_failure_is_bounded_and_creates_no_optimistic_history():
    result = _run("""
const opening=_cmpAccomplishmentsOpen();for(const row of requests){refuse(row,500);}await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert "PRIVATE SERVER TRACEBACK" not in result["html"] and _posts(result) == []
    assert not result["state"]["review"]


def test_late_award_response_after_workspace_reset_cannot_enter_new_history():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const record=_cmpAccomplishmentsRecord();await tick();
_cmpAccomplishmentsReset();respond(requests.find(row=>row.method==='POST'),{{status:'recorded',award_id:award.award_id,receipt_projection:award,receipt_representation:'safe_summary'}});
await record;process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["state"]["history"] is None and result["state"]["review"] is None
    assert len(result["requests"]) == 4


def test_user_closing_inspection_restores_focus_without_reissuing():
    result = _opened_with_history("""
const inspecting=_cmpAccomplishmentsInspect(award.award_id,elements['inspect-invoker']);await resolveReads();await inspecting;
_cmpAccomplishmentsClose();process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["state"]["inspection"] is None and result["focused"] == "inspect-invoker"
    assert _posts(result) == []


def test_earned_assessment_rendering_leaves_response_and_evidence_unchanged():
    result = _opened("""
const before=JSON.stringify(_cmpAccomplishments.assessments);_cmpRenderAccomplishments();
process.stdout.write(JSON.stringify(snapshot({unchanged:before===JSON.stringify(_cmpAccomplishments.assessments)})));
""")
    assert result["unchanged"] and _posts(result) == []


def test_current_negative_status_and_historical_award_remain_separate():
    result = _run(f"""
const opening=_cmpAccomplishmentsOpen();await resolveReads({{
 {json.dumps(f'{BASE}/{EXPLORER}/assessment')}:assessment('{EXPLORER}','not_earned'),
 {json.dumps(f'{BASE}/awards')}:{{awards:[award],receipt_representation:'safe_summary'}}}});await opening;
process.stdout.write(JSON.stringify(snapshot()));
""")
    assert "Current assessment" in result["html"] and "Historical" in result["html"]
    assert result["state"]["assessments"][EXPLORER]["status"] == "not_earned"
    assert len(result["state"]["history"]) == 1 and _posts(result) == []


@pytest.mark.parametrize("key,closed", [("Escape", True), ("Enter", False)])
def test_keyboard_escape_closes_inline_review_and_stops_outer_panel_shortcut(key, closed):
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);let prevented=0,stopped=0;
_cmpAccomplishmentsEscape({{key:{json.dumps(key)},preventDefault(){{prevented++;}},stopPropagation(){{stopped++;}}}});
process.stdout.write(JSON.stringify(snapshot({{prevented,stopped}})));
""")
    assert (result["state"]["review"] is None) is closed
    assert result["prevented"] == result["stopped"] == int(closed)
    assert result["focused"] == ("review-invoker" if closed else "cmp-accomplishments-detail-title")
    assert _posts(result) == []


def test_unknown_outcome_overlapping_history_refresh_cannot_leave_full_refresh_loading_forever():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const recording=_cmpAccomplishmentsRecord();await tick();
const sent=requests.find(row=>row.method==='POST');sent.done=true;sent.reject(new TypeError('Lost response'));await recording;
const full=_cmpAccomplishmentsRefresh();const fullRequests=requests.filter(row=>row.method==='GET'&&!row.done);
const history=_cmpAccomplishmentsHistoryRefresh();
for(const row of requests.filter(row=>row.method==='GET'&&!row.done&&!fullRequests.includes(row)))respond(row,{{awards:[],receipt_representation:'safe_summary'}});
await history;for(const row of fullRequests)respond(row,row.url.endsWith('/assessment')?assessment(row.url.includes('/second_opinion/')?'second_opinion':'perspective_explorer'):{{awards:[],receipt_representation:'safe_summary'}});
await full;process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["state"]["loading"] is False
    assert result["state"]["reconcile"] is False
    assert len(_posts(result)) == 1


def test_aborted_workspace_switch_cannot_leave_discarded_refresh_loading_forever():
    result = _run("""
globalThis._wsOpenInFlight=false;const opening=_cmpAccomplishmentsOpen();
globalThis._wsOpenInFlight=true;await resolveReads();await opening;
globalThis._wsOpenInFlight=false;process.stdout.write(JSON.stringify(snapshot()));
""")
    assert result["state"]["loading"] is False
    assert result["state"]["assessments"] == {} and result["state"]["history"] is None
    assert "check" in result["state"]["error"].lower()
    assert _posts(result) == []


def test_old_workspace_updated_review_cannot_open_approval_in_new_workspace():
    result = _opened(f"""
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const recording=_cmpAccomplishmentsRecord();await tick();
refuse(requests.find(row=>row.method==='POST'),409,'STALE_ASSESSMENT');await recording;
const updating=_cmpAccomplishmentsReviewUpdated('{EXPLORER}');const oldRequests=requests.filter(row=>row.method==='GET'&&!row.done);
_cmpAccomplishmentsReset();const fresh=_cmpAccomplishmentsOpen();
for(const row of requests.filter(row=>row.method==='GET'&&!row.done&&!oldRequests.includes(row)))respond(row,row.url.endsWith('/assessment')?assessment(row.url.includes('/second_opinion/')?'second_opinion':'perspective_explorer','earned',{json.dumps(DIGEST_B)}):{{awards:[],receipt_representation:'safe_summary'}});
await fresh;const beforeLate=snapshot();
for(const row of oldRequests)respond(row,row.url.endsWith('/assessment')?assessment(row.url.includes('/second_opinion/')?'second_opinion':'perspective_explorer'):{{awards:[],receipt_representation:'safe_summary'}});
await updating;process.stdout.write(JSON.stringify(snapshot({{beforeLate}})));
""")
    assert result["beforeLate"]["state"]["review"] is None
    assert result["state"]["assessments"][EXPLORER]["digest"] == DIGEST_B
    assert result["state"]["review"] is None
    assert len(_posts(result)) == 1


def _removal_aware_dom():
    """Real innerHTML replacement removes active descendant nodes and their focus."""
    return r"""
document.body=element('test-body');const host=elements['cmp-accomplishments-host'];let html=host.innerHTML;
const dynamicIds=['cmp-accomplishments-detail-title','cmp-accomplishments-status','cmp-accomplishments-record'];
Object.defineProperty(host,'innerHTML',{get(){return html;},set(value){
 html=value;
 if(dynamicIds.includes(document.activeElement?.id))document.activeElement=document.body;
 for(const id of dynamicIds){delete elements[id];if(value.includes('id="'+id+'"'))element(id);}
}});
"""


def test_inspection_completion_retains_focus_after_native_dom_replacement():
    result = _run(_removal_aware_dom() + f"""
const opening=_cmpAccomplishmentsOpen();await resolveReads({{{json.dumps(f'{BASE}/awards')}:{{awards:[award],receipt_representation:'safe_summary'}}}});await opening;
const inspecting=_cmpAccomplishmentsInspect(award.award_id,elements['inspect-invoker']);const initial=snapshot();
await resolveReads();await inspecting;process.stdout.write(JSON.stringify(snapshot({{initial}})));
""")
    assert result["initial"]["focused"] == "cmp-accomplishments-detail-title"
    assert result["focused"] == "cmp-accomplishments-detail-title"


def test_ordinary_companion_render_preserves_focus_in_open_review():
    render = _extract_function(INDEX.read_text(), "function _cmpRenderOnboarding(")
    result = _run(_removal_aware_dom() + f"""
function _cmpOnboardingHtml(){{return 'Existing Study Cycle';}}let _cmpStudyCycleLoading=false;
function _cmpLoadStudyCycle(){{return Promise.resolve();}}
{render}
const opening=_cmpAccomplishmentsOpen();await resolveReads();await opening;
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const initial=snapshot();
_cmpRenderOnboarding(false);process.stdout.write(JSON.stringify(snapshot({{initial}})));
""")
    assert result["initial"]["focused"] == "cmp-accomplishments-detail-title"
    assert result["focused"] == "cmp-accomplishments-detail-title"


def test_closing_pending_review_uses_status_focus_when_invoker_is_disabled():
    result = _opened(f"""
const invoker=element('cmp-accomplishments-review-{EXPLORER}');invoker.focus=function(){{if(!this.disabled)document.activeElement=this;}};
element('cmp-accomplishments-status');_cmpAccomplishmentsReview('{EXPLORER}',invoker);
const recording=_cmpAccomplishmentsRecord();await tick();invoker.disabled=true;_cmpAccomplishmentsClose();const closed=snapshot();
respond(requests.find(row=>row.method==='POST'),{{status:'recorded',award_id:award.award_id,receipt_representation:'safe_summary',receipt_projection:award}});
await resolveReads();await recording;process.stdout.write(JSON.stringify(snapshot({{closed}})));
""")
    assert result["closed"]["state"]["review"] is None
    assert result["closed"]["focused"] == "cmp-accomplishments-status"


def _run_live_api(scenario, study, client):
    """Pipe actual JS requests to Flask, preserving real server/domain writes."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node unavailable for executed client/API integration")
    process = subprocess.Popen([node, "-e", _script(scenario, rpc=True)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    buffered = b""
    server_requests = []
    try:
        for _ in range(40):
            while b"\n" not in buffered:
                assert select.select([process.stdout], [], [], 20)[0], "Client/API bridge stalled"
                chunk = os.read(process.stdout.fileno(), 65536)
                assert chunk, process.stderr.read().decode()
                buffered += chunk
            line, buffered = buffered.split(b"\n", 1)
            event = json.loads(line)
            if event["kind"] == "result":
                process.stdin.close()
                assert process.wait(timeout=15) == 0, process.stderr.read().decode()
                event["data"]["server_requests"] = server_requests
                return event["data"]
            assert event["kind"] == "request"
            rows_before = study.conn.execute("SELECT COUNT(*) FROM achievement_awards").fetchone()[0]
            if event["method"] == "MUTATE":
                study.retained("skeptical-reader")
                status, payload = 200, {"changed": True}
            else:
                response = (client.post(event["url"], json=event.get("body")) if event["method"] == "POST"
                            else client.get(event["url"]))
                status, payload = response.status_code, response.get_json()
            rows_after = study.conn.execute("SELECT COUNT(*) FROM achievement_awards").fetchone()[0]
            server_requests.append({"method": event["method"], "url": event["url"], "status": status,
                                    "award_rows_before": rows_before, "award_rows_after": rows_after})
            process.stdin.write((json.dumps({"id": event["id"], "status": status, "data": payload}) + "\n").encode())
            process.stdin.flush()
        pytest.fail("Unexpected continuous client requests; no polling is permitted")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.parametrize("achievement", [EXPLORER, SECOND])
def test_synthetic_client_api_sequence_records_only_after_explicit_approval_and_inspects_three_dimensions(tmp_path, monkeypatch, achievement):
    import socket
    import sqlite3
    from hermeneia.narrative.provider_registry import ProviderRegistry
    from hermeneia.web.app import create_app
    from test_perspective_achievements import Study
    study = Study(tmp_path / "synthetic-client.db")
    try:
        study.retained("close-reader")
        if achievement == SECOND:
            study.retained("skeptical-reader")
        client = create_app(db_path=study.path).test_client()
        before_p3 = [tuple(row) for row in study.conn.execute("SELECT * FROM perspective_execution_receipts ORDER BY id")]

        def forbidden(*args, **kwargs):
            pytest.fail("Synthetic client flow must not use a model/provider/network")

        monkeypatch.setattr(ProviderRegistry, "create", forbidden)
        monkeypatch.setattr(socket, "create_connection", forbidden)
        monkeypatch.setattr(socket.socket, "connect", forbidden)
        result = _run_live_api(f"""
await _cmpAccomplishmentsOpen();const opened=snapshot();
_cmpAccomplishmentsReview('{achievement}',elements['review-invoker']);const reviewed=snapshot();
await _cmpAccomplishmentsRecord();const recorded=snapshot();
const historical=_cmpAccomplishments.history.find(row=>row.achievement_id==='{achievement}');
await _cmpAccomplishmentsInspect(historical.award_id,elements['inspect-invoker']);
done({{opened,reviewed,recorded}});
""", study, client)
        assert _posts(result["opened"]) == _posts(result["reviewed"]) == []
        assert len(_posts(result)) == 1
        assert _posts(result)[0]["body"]["assessment_package_sha256"] == result["opened"]["state"]["assessments"][achievement]["digest"]
        for event in result["server_requests"]:
            assert event["award_rows_after"] == event["award_rows_before"] + int(event["method"] == "POST")
        assert all(event["award_rows_after"] == 0 for event in result["server_requests"][:3])
        assert "Receipt integrity" in result["html"] and "Evidence verification" in result["html"]
        assert "Historical replay" in result["html"]
        assert len(list(study.conn.execute("SELECT * FROM achievement_awards"))) == 1
        assert [tuple(row) for row in study.conn.execute("SELECT * FROM perspective_execution_receipts ORDER BY id")] == before_p3
    finally:
        study.conn.close()


def test_synthetic_stale_client_api_flow_requires_new_review_and_second_explicit_click(tmp_path):
    from hermeneia.web.app import create_app
    from test_perspective_achievements import Study
    study = Study(tmp_path / "synthetic-stale-client.db")
    try:
        study.retained("close-reader")
        client = create_app(db_path=study.path).test_client()
        result = _run_live_api(f"""
await _cmpAccomplishmentsOpen();_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);const reviewedA=snapshot();
await mutateStudy();await _cmpAccomplishmentsRecord();const stale=snapshot();
await _cmpAccomplishmentsReviewUpdated('{EXPLORER}');const reviewedB=snapshot();
await _cmpAccomplishmentsRecord();done({{reviewedA,stale,reviewedB}});
""", study, client)
        assert len(_posts(result["stale"])) == len(_posts(result["reviewedB"])) == 1
        assert len(_posts(result)) == 2
        first, second = _posts(result)
        assert first["body"]["assessment_package_sha256"] != second["body"]["assessment_package_sha256"]
        assert result["stale"]["state"]["review"] is None
        issued = [event for event in result["server_requests"] if event["method"] == "POST"]
        assert [(event["status"], event["award_rows_before"], event["award_rows_after"]) for event in issued] == [(409, 0, 0), (201, 0, 1)]
        assert len(list(study.conn.execute("SELECT * FROM achievement_awards"))) == 1
        assert len(result["state"]["history"]) == 1
    finally:
        study.conn.close()


def _actual_json_helpers():
    return "\n".join(_extract_function(INDEX.read_text(), signature) for signature in (
        "function get(", "function post(", "async function requestJSON("))


def _run_actual_json_helpers(scenario, message="PRIVATE SQL TRACEBACK SENTINEL"):
    # Helpers must live beside the feature in global scope, not in the scenario
    # function; otherwise the feature would keep calling the transport stub.
    prefix = _actual_json_helpers() + r"""
const globalErrors=[],fetchOptions=[];
function showAppError(message){globalErrors.push(message);}
function clearAppError(){}
async function runtimeApiFetch(url,options){fetchOptions.push(options);return {ok:false,status:500,
 json:async()=>({error:MESSAGE})};}
""".replace("MESSAGE", json.dumps(message))
    script = _script(scenario).replace("// Perspective accomplishments are explicit",
                                      prefix + "\n// Perspective accomplishments are explicit")
    return _run_node(script)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_actual_helper_error_boundary_never_discloses_server_details_for_accomplishments(method):
    action = ("await _cmpAccomplishmentsOpen();" if method == "GET" else f"""
_cmpAccomplishments.open=true;
_cmpAccomplishments.assessments['{EXPLORER}']=_cmpAccomplishmentsAssessment(assessment(),'{EXPLORER}');
_cmpAccomplishmentsReview('{EXPLORER}',elements['review-invoker']);
await _cmpAccomplishmentsRecord();
""")
    result = _run_actual_json_helpers(action + "process.stdout.write(JSON.stringify(snapshot({globalErrors,fetchOptions})));" )
    assert result["globalErrors"] == []
    assert "PRIVATE SQL TRACEBACK SENTINEL" not in result["html"]
    assert result["state"]["error"]
    assert all("reportErrors" not in options for options in result["fetchOptions"])
    assert result["state"]["history"] is None
    if method == "POST":
        assert result["state"]["reconcile"] is True


def test_other_json_helper_callers_keep_existing_error_banner_behavior():
    result = _run_actual_json_helpers(r"""
try{await get('/existing-caller');}catch{}
process.stdout.write(JSON.stringify(snapshot({globalErrors})));
""", "Existing caller diagnostic")
    assert result["globalErrors"] == ["Existing caller diagnostic"]
