"""P2 presentation consumes server statuses; browser preferences never prove study."""
from __future__ import annotations

import json
import re
from pathlib import Path

from test_evidence_board_ui import _extract_function, _run_node

INDEX = Path(__file__).parents[1] / 'hermeneia/web/static/index.html'
IDS = [
    'governing_question', 'read_source', 'mark_evidence', 'record_observation',
    'preserve_question', 'organize_evidence', 'explore_perspective',
    'form_interpretation', 'challenge_interpretation', 'review_blueprint', 'review_lineage',
]
SURFACES = [
    'question', 'reader', 'capture', 'observations', 'inquiry', 'evidence',
    'perspective', 'interpretation', 'search', 'blueprint', 'lineage',
]


def _projection():
    return {
        'schema': 'hermeneia.guided-study-cycle/v1',
        'workspace': {'name': 'Synthetic study'},
        'registry_version': '1.0.0', 'evaluator_version': '1.0.0',
        'registry_sha256': 'b' * 64,
        'recommended_step_id': IDS[0], 'recommendation_reason': 'A server recommendation.',
        'steps': [
            {'step_id': identifier, 'ordinal': ordinal, 'capability_id': identifier,
             'title': identifier.replace('_', ' '), 'why_it_matters': f'Why {identifier} matters.',
             'status': 'ready', 'capability_status': 'unsupported_due_to_missing_history',
             'availability': 'available', 'status_reason': f'Current basis for {identifier}.',
             'recommended_action': f'Open {surface}', 'target_surface': surface,
             'evidence_or_state_basis': [],
             'history_support': {'status': 'unsupported', 'reason': 'No durable exercise history.'}}
            for ordinal, (identifier, surface) in enumerate(zip(IDS, SURFACES), 1)
        ],
    }


def _script(scenario: str):
    source = INDEX.read_text()
    block = source[source.index('const _CMP_ONBOARDING_KEY ='):source.index('function cmpToggleFlag(')]
    return r'''
const memory = {}, preferences = [], requests = [], navigation = [];
const elements = {};
const x = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;')
  .replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const localStorage = {
  getItem:key=>memory[key] || null,
  setItem(key,value){preferences.push({key,value});memory[key]=value;},
};
function element(id){return elements[id]={innerHTML:'',focused:false,
  scrollIntoView(){navigation.push(['scroll',id]);},focus(){this.focused=true;}};}
['cmp-onboarding-host','cmp-onboarding-host-firstrun','cmp-onboarding',
 'cr-question-input','cr-question-panel','cr-page-view','obs-inquiry-panel'].forEach(element);
const document = {getElementById:id=>elements[id] || null};
let _currentStageId = 'reader', _crPerspectiveKind='', _crPerspectiveMode='';
const _dockClosePanel = () => navigation.push(['dock-close']);
const _dockOpenPanel = key => navigation.push(['dock',key]);
const _crRenderQuestionCard = editing => navigation.push(['question',editing]);
const _crRailGo = key => navigation.push(['rail',key]);
const _crCloseBottomWorkstation = () => navigation.push(['bottom-close']);
const _crOpenBottomWorkstation = async mode => navigation.push(['bottom',mode]);
const _evidenceBoardSetView = async view => navigation.push(['board-view',view]);
let e10Go = async route => {_currentStageId=route;navigation.push(['route',route]);};
const e10SelectObservation = async id => {navigation.push(['observation',id]);_currentStageId='lab';};
function get(url){
  let resolve,reject;
  const promise = new Promise((yes,no)=>{resolve=yes;reject=no;});
  requests.push({url,resolve,reject});return promise;
}
const tick = () => new Promise(resolve=>setImmediate(resolve));
''' + block + '\nconst projection = ' + json.dumps(_projection()) + ';\n' + r'''
function snapshot(extra={}){return {
 html:elements['cmp-onboarding-host'].innerHTML,
 firstRun:elements['cmp-onboarding-host-firstrun'].innerHTML,
 preferences,requests:requests.map(row=>row.url),navigation,
 selected:_cmpSelectedCycleStep,data:_cmpStudyCycle,loading:_cmpStudyCycleLoading,
 error:_cmpStudyCycleError,...extra};}
(async()=>{
''' + scenario + r'''
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
'''


def _run(scenario: str):
    return _run_node(_script(scenario))


def test_server_recommendation_and_statuses_drive_rendering_without_local_rules():
    result = _run(r'''
projection.recommended_step_id='challenge_interpretation';
projection.steps[0].status='currently_supported';
projection.steps[7].status='historically_exercised';
projection.steps[7].history_support={status:'supported',reason:'Exact retained result.'};
projection.steps[8].status='not_ready';
projection.steps[8].status_reason='SERVER_PREREQUISITE';
const before=JSON.stringify(projection);
_cmpStudyCycle=_cmpValidateStudyCycle(projection);
_cmpRenderOnboarding(false);
process.stdout.write(JSON.stringify(snapshot({unchanged:JSON.stringify(projection)===before})));
''')
    assert 'Step 9 of 11' in result['html']
    assert 'SERVER_PREREQUISITE' in result['html']
    assert 'Current material present' in result['html']
    assert 'Supported retained result' in result['html']
    assert 'History unsupported' in result['html']
    assert 'this is not a failure' in result['html']
    assert 'class="cmp-step done' not in result['html']
    assert '✓' not in result['html']
    assert result['unchanged'] is True
    assert result['preferences'] == result['requests'] == []
    assert result['firstRun'] == result['html']


def test_old_completed_finished_flags_never_establish_completion_or_change_recommendation():
    result = _run(r'''
memory[_CMP_ONBOARDING_KEY]=JSON.stringify({completed:Object.fromEntries(projection.steps.map(s=>[s.step_id,true])),finished:true});
_cmpStudyCycle=projection;
_cmpRenderOnboarding(false);
process.stdout.write(JSON.stringify(snapshot({prefs:_cmpLoadOnboardingState()})));
''')
    assert 'Step 1 of 11' in result['html']
    assert 'Study guide hidden' not in result['html']
    assert result['prefs'] == {'paused': False, 'dismissed': False}
    assert result['preferences'] == []


def test_pause_hide_reopen_restart_are_presentation_preferences_only():
    result = _run(r'''
_cmpStudyCycle=projection;
const before=JSON.stringify(projection);
cmpContinueOnboardingLater();const paused=elements['cmp-onboarding-host'].innerHTML;
cmpHideOnboarding();const hidden=elements['cmp-onboarding-host'].innerHTML;
cmpOpenOnboarding();const opened=elements['cmp-onboarding-host'].innerHTML;
cmpSelectStudyStep('review_blueprint');const chosen=elements['cmp-onboarding-host'].innerHTML;
cmpRestartOnboarding();const restarted=elements['cmp-onboarding-host'].innerHTML;
cmpUseWorkbenchFreely();
process.stdout.write(JSON.stringify(snapshot({paused,hidden,opened,chosen,restarted,unchanged:before===JSON.stringify(projection)})));
''')
    assert 'Study guide paused' in result['paused']
    assert 'Study guide hidden' in result['hidden']
    assert 'Study Cycle' in result['opened']
    assert 'Step 10 of 11' in result['chosen']
    assert 'Step 1 of 11' in result['restarted']
    assert result['selected'] == ''
    assert result['unchanged']
    assert result['navigation'][-1] == ['dock-close']
    for pref in result['preferences']:
        assert set(json.loads(pref['value'])) == {'paused', 'dismissed'}


def test_legacy_reader_completion_hooks_only_refresh_the_server_projection():
    result = _run(r'''
cmpMarkOnboardingStep('read',{keepPaused:true});
requests[0].resolve(projection);await tick();
process.stdout.write(JSON.stringify(snapshot()));
''')
    assert result['preferences'] == []
    assert result['requests'] == ['/api/guided-study-cycle']
    assert 'Step 1 of 11' in result['html']
    assert 'Walkthrough complete' not in result['html']


def test_fetch_is_provider_free_and_workspace_reset_discards_stale_response():
    result = _run(r'''
const first=_cmpLoadStudyCycle();
_cmpResetStudyCycle();
const second=_cmpLoadStudyCycle();
const next=JSON.parse(JSON.stringify(projection));next.recommended_step_id='review_lineage';
requests[1].resolve(next);await second;
requests[0].resolve(projection);await first;
process.stdout.write(JSON.stringify(snapshot()));
''')
    assert result['requests'] == ['/api/guided-study-cycle'] * 2
    assert result['data']['recommended_step_id'] == 'review_lineage'
    assert 'Step 11 of 11' in result['html']
    assert result['preferences'] == []
    assert not result['loading']


def test_latest_refresh_wins_and_invalid_projection_does_not_leave_old_success():
    result = _run(r'''
_cmpStudyCycle=projection;
const first=_cmpLoadStudyCycle(),second=_cmpLoadStudyCycle();
requests[1].resolve({...projection,schema:'future'});await second;
requests[0].resolve(projection);await first;
process.stdout.write(JSON.stringify(snapshot()));
''')
    assert result['data'] is None
    assert 'Unsupported Study Cycle projection.' in result['html']
    assert 'Step 1 of 11' not in result['html']
    assert result['preferences'] == []


def test_all_actions_open_existing_surfaces_without_saving_or_provider_execution():
    result = _run(r'''
_cmpStudyCycle=projection;
for(const step of projection.steps) await cmpOnboardingAction(step.step_id);
process.stdout.write(JSON.stringify(snapshot({focused:elements['cr-question-input'].focused})));
''')
    actions = result['navigation']
    for target in [['question', True], ['rail', 'question'], ['bottom-close'],
                   ['rail', 'capture'], ['rail', 'observations'], ['route', 'corpus'],
                   ['bottom', 'evidence'], ['bottom', 'perspective'], ['bottom', 'search'],
                   ['bottom', 'blueprint'], ['board-view', 'lineage']]:
        assert target in actions
    assert result['focused']
    assert result['requests'] == result['preferences'] == []
    assert ['bottom', 'critic'] not in actions  # Blueprint check is a different operation.
    assert ['route', 'critic'] not in actions  # Publication fidelity is a separate audit.
    assert ['bottom', 'lineage'] not in actions
    assert ['bottom', 'interpretation'] not in actions


def test_inquiry_and_interpretation_open_exact_server_supplied_observation_context():
    result = _run(r'''
_cmpStudyCycle=projection;
for(const id of ['preserve_question','form_interpretation']){
 projection.steps.find(s=>s.step_id===id).evidence_or_state_basis=[
  {record:{table:'reader_highlights',key:{id:'same-id'}}},
  {record:{table:'observations',key:{id:'exact-observation'}}}];
 await cmpOnboardingAction(id);
}
process.stdout.write(JSON.stringify(snapshot()));
''')
    assert result['navigation'].count(['observation', 'exact-observation']) == 2
    assert ['observation', 'same-id'] not in result['navigation']
    assert ['scroll', 'obs-inquiry-panel'] in result['navigation']
    assert result['requests'] == result['preferences'] == []


def test_reader_route_is_awaited_before_question_or_workstation_opens():
    result = _run(r'''
_cmpStudyCycle=projection;_currentStageId='setup';
let release;
e10Go=route=>{navigation.push(['route-start',route]);return new Promise(resolve=>{
 release=()=>{_currentStageId=route;navigation.push(['route-ready',route]);resolve();};});};
const opening=cmpOnboardingAction('explore_perspective');
await tick();const pending=JSON.parse(JSON.stringify(navigation));
release();await opening;
process.stdout.write(JSON.stringify(snapshot({pending})));
''')
    assert ['bottom', 'perspective'] not in result['pending']
    assert result['navigation'].index(['route-ready', 'reader']) < result['navigation'].index(['bottom', 'perspective'])


def test_workspace_change_cancels_pending_guide_navigation():
    result = _run(r'''
_cmpStudyCycle=projection;_currentStageId='setup';
let release;
e10Go=route=>new Promise(resolve=>{release=()=>{_currentStageId=route;resolve();};});
const opening=cmpOnboardingAction('organize_evidence');
_cmpResetStudyCycle();release();await opening;
process.stdout.write(JSON.stringify(snapshot()));
''')
    assert ['bottom', 'evidence'] not in result['navigation']
    assert result['data'] is None


def test_untrusted_step_metadata_is_escaped_and_rendering_does_not_modify_projection():
    result = _run(r'''
projection.steps[0].title='<script>alert(1)</script>';
projection.steps[0].why_it_matters='"unsafe" <img>';
projection.steps[0].evidence_or_state_basis=[{record:{table:'x',key:{id:'<evil>'}}}];
const before=JSON.stringify(projection);_cmpStudyCycle=projection;_cmpRenderOnboarding(false);
process.stdout.write(JSON.stringify(snapshot({unchanged:before===JSON.stringify(projection)})));
''')
    assert '<script>' not in result['html']
    assert '<img>' not in result['html']
    assert '&lt;evil&gt;' in result['html']
    assert result['unchanged']


def test_ui_has_no_independent_eligibility_completion_or_award_logic():
    source = INDEX.read_text()
    block = source[source.index('const _CMP_ONBOARDING_KEY ='):source.index('function cmpToggleFlag(')]
    for forbidden in ['_cmpStepComplete', '_CMP_ONBOARDING_STEPS', 'state.completed',
                      'state.finished', 'invLoad(', '_crHighlights', 'fetch(', 'post(',
                      'badge', 'achievement', 'Full Cycle', 'XP', 'unlocked']:
        assert forbidden not in block
    assert '/api/guided-study-cycle' in block
    assert "typeof _cmpResetStudyCycle === 'function'" in source
    # Normal Companion chat remains separately rendered and provider-backed.
    assert 'async function _cmpRender()' in source
    assert 'async function cmpAsk()' in source
    assert 'id="cmp-input"' in source
    assert 'onclick="cmpAsk()"' in source


def test_current_named_frame_query_is_exact_encoded_and_never_custom_or_room_history():
    result = _run(r'''
_crPerspectiveKind='built-in';_crPerspectiveMode='single';_cmpFrameSelectionEpoch=_cmpStudyWorkspaceEpoch;
element('cr-perspective-select').value='frame&one';
element('cr-perspective-saved-select').value='saved/one';
const builtin=_cmpStudyCycleURL();
_crPerspectiveKind='saved';const saved=_cmpStudyCycleURL();
_crPerspectiveKind='custom';const custom=_cmpStudyCycleURL();
_crPerspectiveKind='invented';const invalid=_cmpStudyCycleURL();
_crPerspectiveKind='built-in';_crPerspectiveMode='room';const room=_cmpStudyCycleURL();
process.stdout.write(JSON.stringify({builtin,saved,custom,invalid,room}));
''')
    assert result['builtin'] == '/api/guided-study-cycle?perspective_kind=builtin&perspective_id=frame%26one'
    assert result['saved'] == '/api/guided-study-cycle?perspective_kind=saved&perspective_id=saved%2Fone'
    assert result['custom'] == result['invalid'] == result['room'] == '/api/guided-study-cycle'


def test_supported_history_does_not_hide_current_missing_prerequisites():
    result = _run(r'''
projection.recommended_step_id='form_interpretation';
const step=projection.steps[7];step.status='historically_exercised';
step.availability='not_yet_available';step.capability_status='already_exercised_under_supported_evidence';
step.history_support={status:'supported',reason:'Retained interpretation with exact lineage.'};
_cmpStudyCycle=projection;_cmpRenderOnboarding(false);
process.stdout.write(JSON.stringify(snapshot()));
''')
    assert 'Supported retained result' in result['html']
    assert '<strong>Readiness</strong><br>Prerequisite needed' in result['html']
    assert 'Retained interpretation with exact lineage.' in result['html']


def test_observation_work_with_a_mark_opens_explicit_candidate_inspector_without_promotion():
    result = _run(r'''
_cmpStudyCycle=projection;
projection.steps[3].evidence_or_state_basis=[{record:{table:'reader_highlights',key:{id:'retained-mark'}}}];
await cmpOnboardingAction('record_observation');
process.stdout.write(JSON.stringify(snapshot()));
''')
    assert ['rail', 'capture'] in result['navigation']
    assert ['rail', 'observations'] not in result['navigation']
    assert result['requests'] == result['preferences'] == []


def test_retained_question_context_uses_only_exact_typed_provenance_and_ambiguous_uses_chooser():
    result = _run(r'''
_cmpStudyCycle=projection;
projection.steps[4].evidence_or_state_basis=[{record:{table:'inquiry_notes',key:{id:'question'}},
 provenance:{references:[{table:'reader_highlights',key:{id:'wrong'}},{table:'observations',key:{id:'source-observation'}}]}}];
await cmpOnboardingAction('preserve_question');
projection.steps[4].evidence_or_state_basis[0].provenance.references.push({table:'observations',key:{id:'other-observation'}});
await cmpOnboardingAction('preserve_question');
process.stdout.write(JSON.stringify(snapshot()));
''')
    assert result['navigation'].count(['observation', 'source-observation']) == 1
    assert ['observation', 'wrong'] not in result['navigation']
    assert ['observation', 'other-observation'] not in result['navigation']
    assert ['route', 'corpus'] in result['navigation']


def test_workspace_change_removes_old_frame_hint_until_current_selection_or_metadata():
    result = _run(r'''
_crPerspectiveKind='saved';_crPerspectiveMode='single';
element('cr-perspective-saved-select').value='old-workspace-frame';
_cmpFrameSelectionEpoch=_cmpStudyWorkspaceEpoch;const prior=_cmpStudyCycleURL();
const oldEpoch=_cmpStudyWorkspaceEpoch;_cmpResetStudyCycle();
const cleared=_cmpStudyCycleURL();_cmpFrameSelectionChanged(oldEpoch);
const stale=_cmpStudyCycleURL();
elements['cr-perspective-saved-select'].value='new-workspace-frame';
_cmpFrameSelectionChanged();const fresh=_cmpStudyCycleURL();
process.stdout.write(JSON.stringify({prior,cleared,stale,fresh,requests:requests.map(r=>r.url)}));
''')
    assert 'old-workspace-frame' in result['prior']
    assert result['cleared'] == result['stale'] == '/api/guided-study-cycle'
    assert 'new-workspace-frame' in result['fresh']
    assert result['requests'] == [result['fresh']]


def test_first_run_mount_starts_provider_free_projection_load():
    source = INDEX.read_text()
    first_run = re.search(r"async function e10LoadFirstRun\(\).*?\n\}\n", source, re.S).group(0)
    script = _script(r'''
element('firstrun-panel');
const opening=e10LoadFirstRun();
requests[0].resolve({database_exists:false,document_count:0,demo_available:false,db_path:'absent',runtime:{}});
await opening;await tick();
requests[1].resolve(projection);await tick();
process.stdout.write(JSON.stringify(snapshot()));
''')
    script = script.replace('const projection = ',
        "const _setWorkspaceDatabaseAvailable=()=>{},_runtimeApplyWorkspaceDraftScope=()=>{};\n"
        + first_run + '\nconst projection = ', 1)
    result = _run_node(script)
    assert result['requests'] == ['/api/setup/state', '/api/guided-study-cycle']
    assert 'Step 1 of 11' in result['firstRun']
    assert result['preferences'] == []


def test_governing_question_uses_existing_setup_when_native_reader_recovers_first_run():
    source = INDEX.read_text()
    native_route = _extract_function(source, 'function e10Go(')
    script = _script(r'''
_cmpStudyCycle=projection;_currentStageId='firstrun';
await cmpOnboardingAction('governing_question');
process.stdout.write(JSON.stringify(snapshot({route:_currentStageId})));
''')
    script = script.replace('const projection = ', r'''
let _crReaderLoadSeq=0,_expert=false;
document.body={classList:{remove(){}}};
const _e10ShouldRecoverMissingWorkspace=id=>id==='reader';
const _e10RenderMissingWorkspaceRecovery=()=>{_currentStageId='firstrun';navigation.push(['recovery','firstrun']);};
const _e10ApplyRouteChrome=id=>{_currentStageId=id;navigation.push(['route',id]);};
const e10LoadSetup=()=>navigation.push(['loader','setup']);
e10Go =
''' + native_route + ';\nconst projection = ', 1)
    result = _run_node(script)
    assert result['route'] == 'setup'
    assert ['recovery', 'firstrun'] in result['navigation']
    assert ['loader', 'setup'] in result['navigation']
    assert result['requests'] == result['preferences'] == []


def test_challenge_counterevidence_action_opens_source_search_not_publication_fidelity():
    result = _run(r'''
_cmpStudyCycle=projection;
const before=JSON.stringify(projection.steps[8]);
await cmpOnboardingAction('challenge_interpretation');
process.stdout.write(JSON.stringify(snapshot({unchanged:before===JSON.stringify(projection.steps[8])})));
''')
    assert ['bottom', 'search'] in result['navigation']
    assert ['route', 'critic'] not in result['navigation']
    assert ['bottom', 'critic'] not in result['navigation']
    assert result['unchanged']
    assert result['requests'] == result['preferences'] == []
