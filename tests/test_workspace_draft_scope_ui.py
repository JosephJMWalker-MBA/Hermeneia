"""Browser recovery draft scope is owned by runtime workspace identity."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


def _extract_region(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


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


def _draft_region() -> str:
    html = _index()
    return _extract_region(
        html,
        "// ── Runtime connectivity and local authored drafts",
        "// ── Accessibility Dock",
    )


def _workspace_drawer_region() -> str:
    html = _index()
    return _extract_region(
        html,
        "// ── Workspace drawer",
        "function _wsCloseMenu(",
    )


def _node_base() -> str:
    html = _index()
    return (
        r"""
function makeClassList(){return {items:[],add(c){this.items.push(c);},remove(c){this.items=this.items.filter(x=>x!==c);},toggle(c,on){on?this.add(c):this.remove(c);}};}
function makeInput(value=''){return {value,checked:false,style:{},dataset:{},textContent:'',listeners:{},classList:makeClassList(),addEventListener(type,fn){this.listeners[type]=fn;},focus(){}};}
const elements={
  'fln-understanding':makeInput(''),
  'fln-questions':makeInput(''),
  'cmp-input':makeInput(''),
  'cr-edit-important':makeInput(''),
  'cr-edit-tags':makeInput(''),
  'cr-edit-rank':makeInput(''),
  'cr-edit-theme':makeInput(''),
  'cr-edit-note':makeInput('saved note'),
  'cr-edit-q':makeInput('saved question'),
  'cr-edit-msg':makeInput(''),
  'cr-sel-form':makeInput(''),
  'cr-note-input':makeInput(''),
  'cr-q-input':makeInput(''),
  'cr-important-input':makeInput(''),
  'cr-tags-input':makeInput(''),
  'cr-rank-input':makeInput(''),
  'cr-theme-input':makeInput(''),
  'cr-concept-input':makeInput(''),
  'cr-capture-msg':makeInput(''),
};
const document={
  body:{dataset:{}},
  getElementById(id){return elements[id]||null;},
  querySelectorAll(){return [];}
};
const window={location:{origin:'http://hermeneia.local'}};
const localStorage={data:{},getItem(k){return Object.prototype.hasOwnProperty.call(this.data,k)?this.data[k]:null;},setItem(k,v){this.data[k]=String(v);},removeItem(k){delete this.data[k];}};
function x(value){return String(value??'');}
let _crDocId='doc-1';
let _crPage=5;
let _flnLane='corpus';
let _crRelevance='supports';
let _crSelText='Selected passage';
let _crReaderSelectionState={text:'Selected passage'};
let _crHighlights=[{id:'hl-1',source_document_id:'doc-1',page:5,note_text:'saved note',question_text:'saved question',relevance:'supports',tags:[]}];
function _crHighlightTags(h){return Array.isArray(h&&h.tags)?h.tags:[];}
function _crGetReaderSelection(){return {text:'Selected passage'};}
function _crEncodeReaderSpanLocator(){return 'p5:block1';}
"""
        + _draft_region()
    )


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for draft scope UI tests")
    result = subprocess.run(
        [node, "-e", _node_base() + script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_v2_keys_use_backend_scope_and_do_not_leak_paths() -> None:
    result = _run_node(
        r"""
const unsafeAccepted = _runtimeApplyWorkspaceDraftScope({
  runtime_scope:'custom:/private/tmp/work/hermeneia.db',
  draft_migration_scope:'/private/tmp/work/hermeneia.db',
});
_runtimeApplyWorkspaceDraftScope({
  runtime_scope:'custom:0123456789abcdef0123456789abcdef',
  draft_migration_scope:'oldscopea',
});
const key = _flnDraftKey('corpus');
elements['fln-understanding'].value = 'safe custom draft';
_flnPersistDraft('corpus');
const keys = Object.keys(localStorage.data);
process.stdout.write(JSON.stringify({
  unsafeAccepted,
  key,
  keys,
  bodyScope:document.body.dataset.workspaceDraftScopeVersion,
}));
"""
    )

    assert result["unsafeAccepted"] is False
    assert result["key"].startswith("hermeneia:draft:v2:")
    assert "custom%3A0123456789abcdef0123456789abcdef" in result["key"]
    assert result["bodyScope"] == "2"
    serialized = json.dumps(result["keys"])
    for forbidden in ("/private", "/home", "hermeneia.db", "uploads"):
        assert forbidden not in serialized


def test_exact_v1_draft_migrates_once_without_scanning_or_overwriting_v2() -> None:
    result = _run_node(
        r"""
_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-a',draft_migration_scope:'oldscopea'});
const corpusKey = _flnDraftKey('corpus');
const corpusOld = _authoredDraftV1Key(_authoredDraftKeyParts.get(corpusKey));
const unrelatedOld = 'hermeneia_authored_draft_v1:oldscopeb:field-notes:doc-1:5:corpus';
localStorage.setItem(corpusOld, JSON.stringify({schema:1,fields:{understanding:'old A',pressing_questions:'old q'}}));
localStorage.setItem(unrelatedOld, JSON.stringify({schema:1,fields:{understanding:'other workspace'}}));
const migrated = _authoredDraftLoad(corpusKey);
const afterFirst = {...localStorage.data};
const migratedAgain = _authoredDraftLoad(corpusKey);

const instrumentKey = _authoredDraftKey(['field-notes','doc-1','5','instrument']);
const instrumentOld = _authoredDraftV1Key(_authoredDraftKeyParts.get(instrumentKey));
localStorage.setItem(instrumentKey, JSON.stringify({schema:2,fields:{understanding:'v2 wins'}}));
localStorage.setItem(instrumentOld, JSON.stringify({schema:1,fields:{understanding:'old loses'}}));
const conflict = _authoredDraftLoad(instrumentKey);
process.stdout.write(JSON.stringify({
  migrated:migrated.fields.understanding,
  migratedAgain:migratedAgain.fields.understanding,
  corpusOldPresent:localStorage.getItem(corpusOld)!==null,
  corpusNewPresent:localStorage.getItem(corpusKey)!==null,
  unrelatedOldPresent:localStorage.getItem(unrelatedOld)!==null,
  broadDeleteCount:Object.keys(localStorage.data).length,
  afterFirstKeys:Object.keys(afterFirst),
  conflict:conflict.fields.understanding,
  conflictOldPresent:localStorage.getItem(instrumentOld)!==null,
}));
"""
    )

    assert result["migrated"] == "old A"
    assert result["migratedAgain"] == "old A"
    assert result["corpusOldPresent"] is False
    assert result["corpusNewPresent"] is True
    assert result["unrelatedOldPresent"] is True
    assert result["broadDeleteCount"] == 4
    assert len(result["afterFirstKeys"]) == 2
    assert result["conflict"] == "v2 wins"
    assert result["conflictOldPresent"] is True


def test_field_notes_and_companion_drafts_are_isolated_by_runtime_scope() -> None:
    result = _run_node(
        r"""
_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-a',draft_migration_scope:'olda'});
elements['fln-understanding'].value='field note A';
elements['fln-questions'].value='';
_flnPersistDraft('corpus');
elements['cmp-input'].value='companion A';
_cmpPersistDraft();

_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-b',draft_migration_scope:'oldb'});
_flnApplyDraft('corpus');
_cmpApplyDraft({replace:true});
const bInitially={field:elements['fln-understanding'].value,companion:elements['cmp-input'].value};
elements['fln-understanding'].value='field note B';
_flnPersistDraft('corpus');
elements['cmp-input'].value='companion B';
_cmpPersistDraft();

_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-a',draft_migration_scope:'olda'});
const backToA={field:elements['fln-understanding'].value,companion:elements['cmp-input'].value};
_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-b',draft_migration_scope:'oldb'});
const backToB={field:elements['fln-understanding'].value,companion:elements['cmp-input'].value};
process.stdout.write(JSON.stringify({bInitially,backToA,backToB,keys:Object.keys(localStorage.data)}));
"""
    )

    assert result["bInitially"] == {"field": "", "companion": ""}
    assert result["backToA"] == {"field": "field note A", "companion": "companion A"}
    assert result["backToB"] == {"field": "field note B", "companion": "companion B"}
    assert all(key.startswith("hermeneia:draft:v2:") for key in result["keys"])


def test_highlight_inspector_drafts_are_isolated_by_runtime_scope() -> None:
    result = _run_node(
        r"""
const form = elements['cr-sel-form'];
form.dataset.draftKind='reader-highlight-edit';
form.dataset.highlightId='hl-1';
const h = _crHighlights[0];

_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-a',draft_migration_scope:'olda'});
_crApplyHighlightEditBaseDraft(h);
form.dataset.draftKey=_crHighlightEditDraftKey(h);
elements['cr-edit-note'].value='highlight draft A';
_crStoreActiveReaderDraft();

_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-b',draft_migration_scope:'oldb'});
const bInitial=elements['cr-edit-note'].value;
elements['cr-edit-note'].value='highlight draft B';
_crStoreActiveReaderDraft();

_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-a',draft_migration_scope:'olda'});
const backToA=elements['cr-edit-note'].value;
_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-b',draft_migration_scope:'oldb'});
const backToB=elements['cr-edit-note'].value;
process.stdout.write(JSON.stringify({bInitial,backToA,backToB,keys:Object.keys(localStorage.data)}));
"""
    )

    assert result["bInitial"] == "saved note"
    assert result["backToA"] == "highlight draft A"
    assert result["backToB"] == "highlight draft B"
    assert len(result["keys"]) == 2


def test_runtime_scope_transition_flushes_old_scope_before_hydrating_new_scope() -> None:
    result = _run_node(
        r"""
_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-b',draft_migration_scope:'oldb'});
elements['fln-understanding'].value='preexisting B';
_flnPersistDraft('corpus');

_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-a',draft_migration_scope:'olda'});
elements['fln-understanding'].value='typed under A before handoff';
_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-b',draft_migration_scope:'oldb'});
const bKey = _flnDraftKey('corpus');
const bPayload = JSON.parse(localStorage.getItem(bKey));
const visibleAfterTransition = elements['fln-understanding'].value;

_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-a',draft_migration_scope:'olda'});
const aRecovered = elements['fln-understanding'].value;
process.stdout.write(JSON.stringify({
  afterTransition: bPayload.fields.understanding,
  visibleAfterTransition,
  aRecovered,
}));
"""
    )

    assert result["afterTransition"] == "preexisting B"
    assert result["visibleAfterTransition"] == "preexisting B"
    assert result["aRecovered"] == "typed under A before handoff"


def test_ack_clear_and_failed_save_affect_only_exact_current_workspace_key() -> None:
    result = _run_node(
        r"""
_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-a',draft_migration_scope:'olda'});
elements['cmp-input'].value='message A';
_cmpPersistDraft();
const keyA = _cmpDraftKey();

_runtimeApplyWorkspaceDraftScope({runtime_scope:'managed:ws-b',draft_migration_scope:'oldb'});
elements['cmp-input'].value='message B';
_cmpPersistDraft();
const keyB = _cmpDraftKey();

const failedRetains = localStorage.getItem(keyB) !== null;
_authoredDraftClear(keyB);
const afterAck = {
  aPresent: localStorage.getItem(keyA) !== null,
  bPresent: localStorage.getItem(keyB) !== null,
  keys:Object.keys(localStorage.data),
  failedRetains,
};
process.stdout.write(JSON.stringify(afterAck));
"""
    )

    assert result["failedRetains"] is True
    assert result["aPresent"] is True
    assert result["bPresent"] is False
    assert len(result["keys"]) == 1


def test_workspace_open_flushes_old_drafts_and_hydrates_target_drafts() -> None:
    result = _run_node(
        r"""
let get;
elements['workspace-catalog']=makeInput('');
elements['workspace-catalog-status']=makeInput('');
elements['runtime-workspace-chip']=makeInput('');
elements['runtime-workspace-name']=makeInput('');
window.confirms=[];
window.confirm=function(message){ this.confirms.push(message); return true; };
"""
        + _workspace_drawer_region()
        + r"""
        (async () => {
const current = {
  id:'ws-a',
  name:'The Second Sale',
  slug:'the-second-sale',
  kind:'managed',
  runtime_scope:'managed:ws-a',
  draft_migration_scope:'olda',
};
const target = {
  id:'ws-b',
  name:'Research Notes',
  slug:'research-notes',
  kind:'managed',
  runtime_scope:'managed:ws-b',
  draft_migration_scope:'oldb',
};
_wsCatalog = [
  {id:'ws-a',name:'The Second Sale',slug:'the-second-sale',kind:'managed',is_active:true},
  {id:'ws-b',name:'Research Notes',slug:'research-notes',kind:'managed',is_active:false},
];

_runtimeApplyWorkspaceDraftScope(target);
elements['fln-understanding'].value='target field note';
elements['fln-questions'].value='';
_flnPersistDraft('corpus');
elements['cmp-input'].value='target companion draft';
_cmpPersistDraft();
const targetFieldKey = _flnDraftKey('corpus');
const targetCompanionKey = _cmpDraftKey();

_runtimeApplyWorkspaceDraftScope(current);
elements['fln-understanding'].value='current field note before switch';
elements['fln-questions'].value='';
elements['cmp-input'].value='current companion before switch';
_wsApplyRuntimePayload({workspace:current,capabilities:{workspace_switch:true}});
const currentFieldKey = _flnDraftKey('corpus');
const currentCompanionKey = _cmpDraftKey();

runtimeApiFetch = async (url, options) => ({
  ok:true,
  status:200,
  json:async () => ({changed:true,workspace:target}),
});
get = async (url) => {
  if (url === '/api/runtime/workspace') {
    return {workspace:target,capabilities:{workspace_switch:true}};
  }
  return {workspaces:[
    {id:'ws-a',name:'The Second Sale',slug:'the-second-sale',kind:'managed',is_active:false},
    {id:'ws-b',name:'Research Notes',slug:'research-notes',kind:'managed',is_active:true},
  ]};
};

await _wsOpenWorkspace('research-notes');
const currentField = JSON.parse(localStorage.getItem(currentFieldKey));
const currentCompanion = JSON.parse(localStorage.getItem(currentCompanionKey));
const targetField = JSON.parse(localStorage.getItem(targetFieldKey));
const targetCompanion = JSON.parse(localStorage.getItem(targetCompanionKey));
process.stdout.write(JSON.stringify({
  currentSlug:_wsCurrentWorkspace.slug,
  visibleField:elements['fln-understanding'].value,
  visibleCompanion:elements['cmp-input'].value,
  currentField:currentField.fields.understanding,
  currentCompanion:currentCompanion.fields.message,
  targetField:targetField.fields.understanding,
  targetCompanion:targetCompanion.fields.message,
  confirmCount:window.confirms.length,
  confirmMessage:window.confirms[0],
  status:_wsCatalogStatusMessage,
}));
        })();
"""
    )

    assert result["currentSlug"] == "research-notes"
    assert result["visibleField"] == "target field note"
    assert result["visibleCompanion"] == "target companion draft"
    assert result["currentField"] == "current field note before switch"
    assert result["currentCompanion"] == "current companion before switch"
    assert result["targetField"] == "target field note"
    assert result["targetCompanion"] == "target companion draft"
    assert result["confirmCount"] == 1
    assert "Field Notes" in result["confirmMessage"]
    assert "Companion" in result["confirmMessage"]
    assert result["status"] == "Opened Research Notes."
