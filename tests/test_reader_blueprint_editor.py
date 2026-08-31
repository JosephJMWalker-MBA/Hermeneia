"""Working Blueprint editor behavior.

The Reader Build surface edits only transient, noncanonical
``_crBlueprintCandidate`` state. Commit must serialize that structured object,
not reconstruct a Blueprint from form markup.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent
INDEX = ROOT / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"(?:^|\n)(?:async\s+)?function " + re.escape(name) + r"\(", html)
    assert match, f"could not find function {name}"
    start = match.start()
    if html[start] == "\n":
        start += 1
    brace = html.find("{", start)
    assert brace >= 0
    depth = 0
    for pos in range(brace, len(html)):
        char = html[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[start : pos + 1] + "\n"
    raise AssertionError(f"could not extract function {name}")


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader Blueprint editor test")
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _candidate_js() -> str:
    return """
{
  title: 'Generated title',
  thesis: 'Generated thesis.',
  sections: [
    { claim: 'Claim A.', supporting_observations: ['obs-1'], supporting_interpretations: [] },
    { claim: 'Claim B.', supporting_observations: ['obs-2'], supporting_interpretations: ['int-2'] },
    { claim: 'Claim C.', supporting_observations: ['obs-3'], supporting_interpretations: [] }
  ]
}
"""


def _editor_functions(html: str) -> str:
    names = [
        "_crCloneBlueprintCandidate",
        "_crBlueprintCanMutate",
        "_crSyncBlueprintOperationState",
        "_crSetBlueprintOperation",
        "_crBlueprintSection",
        "_crBlueprintSections",
        "_crBlueprintEvidenceCountText",
        "_crBlueprintStatusBadge",
        "_crUpdateBlueprintDirtyBadge",
        "_crMarkBlueprintCandidateDirty",
        "_crUpdateBlueprintTitle",
        "_crUpdateBlueprintThesis",
        "_crUpdateBlueprintClaim",
        "_crMoveBlueprintClaim",
        "_crAddBlueprintClaim",
        "_crRemoveBlueprintClaim",
        "_crValidateBlueprintCandidateForCommit",
        "_crRenderBlueprintEditor",
        "_crRenderBlueprintCandidate",
        "_crGenerateBlueprintCandidate",
        "_crCommitBlueprintCandidate",
        "_crResetBlueprintWorkingStateForWorkspaceChange",
    ]
    return "".join(_extract_fn(html, name) for name in names)


def _dom_prefix(candidate_expr: str) -> str:
    return (
        f"let _crBlueprintCandidate = {candidate_expr};"
        "let _crBlueprintCandidateDirty = false;"
        "let _crBlueprintOperation = 'idle';"
        "let _crBlueprintWorkspaceEpoch = 0;"
        "let _crActiveBlueprintId = '';"
        "const posts=[]; const confirms=[]; let generateMode='success';"
        "const generatedB={title:'Generated B',thesis:'Generated thesis B.',sections:[{claim:'Claim B1.',supporting_observations:['obs-b'],supporting_interpretations:[]}]};"
        "function x(v){return String(v == null ? '' : v).replace(/[&<>\"']/g, c => c);}"
        "function makeEl(id){return {id,hidden:false,dataset:{},style:{display:'none'},innerHTML:'',innerText:'',textContent:'',disabled:false,value:'',title:'',focus(){},setAttribute(){},classList:{toggle(){},remove(){}}};}"
        "const elements={"
        "'cr-blueprint-proposal':makeEl('cr-blueprint-proposal'),"
        "'cr-blueprint-btn':makeEl('cr-blueprint-btn'),"
        "'cr-blueprint-commit-btn':makeEl('cr-blueprint-commit-btn'),"
        "'cr-blueprint-title':makeEl('cr-blueprint-title'),"
        "'cr-blueprint-thesis':makeEl('cr-blueprint-thesis')"
        "};"
        "const document={getElementById(id){return elements[id]||null;},querySelectorAll(){return [];}};"
        "const window={confirm(message){confirms.push(message); return window.confirmResult;}, confirmResult:true};"
        "function setTimeout(fn){fn();}"
        "function _crOpenBottomWorkstation(mode){posts.push({url:'open', mode});}"
        "function e10Go(stage){posts.push({url:'go', stage});}"
        "async function _crAssembleBlueprintSeed(){return 'governing question plus evidence';}"
        "async function fetch(url, opts){"
        "const body=opts && opts.body ? JSON.parse(opts.body) : {}; posts.push({url, body});"
        "if(url==='/api/pipeline/extract-blueprint'){"
        " if(generateMode==='fail'){return {ok:false,json:async()=>({error:'generation failed'})};}"
        " return {ok:true,json:async()=>({proposed_blueprint:generatedB})};"
        "}"
        "if(url==='/api/pipeline/ratify-blueprint'){"
        " if(generateMode==='commit-fail'){return {ok:false,json:async()=>({error:'commit failed'})};}"
        " return {ok:true,json:async()=>({blueprint_id:'bp-edited',plan_id:'plan-edited',committed_blueprint:body.proposed_blueprint})};"
        "}"
        "throw new Error('unexpected fetch '+url);"
        "}"
    )


def test_working_blueprint_edits_commit_exact_candidate_with_evidence_moved_by_section():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
(async () => {
  await _crGenerateBlueprintCandidate();
  _crBlueprintCandidate = %s;
  _crUpdateBlueprintTitle('Edited title');
  _crUpdateBlueprintThesis('Edited thesis.');
  _crUpdateBlueprintClaim(1, 'Edited claim B.');
  _crMoveBlueprintClaim(2, -1);
  _crMoveBlueprintClaim(1, -1);
  _crRemoveBlueprintClaim(1);
  _crAddBlueprintClaim();
  _crUpdateBlueprintClaim(2, 'Claim D.');
  await _crCommitBlueprintCandidate();
  const commitPosts = posts.filter(p => p.url === '/api/pipeline/ratify-blueprint');
  process.stdout.write(JSON.stringify({
    candidate:_crBlueprintCandidate,
    dirty:_crBlueprintCandidateDirty,
    proposalCount:posts.filter(p => p.url === '/api/pipeline/extract-blueprint').length,
    commitCount:commitPosts.length,
    commitPayload:commitPosts[0].body.proposed_blueprint
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
        % _candidate_js()
    )

    result = _run_node(script)
    assert result["proposalCount"] == 1
    assert result["commitCount"] == 1
    assert result["candidate"] is None
    assert result["dirty"] is False
    assert result["commitPayload"] == {
        "title": "Edited title",
        "thesis": "Edited thesis.",
        "sections": [
            {"claim": "Claim C.", "supporting_observations": ["obs-3"], "supporting_interpretations": []},
            {"claim": "Edited claim B.", "supporting_observations": ["obs-2"], "supporting_interpretations": ["int-2"]},
            {"claim": "Claim D.", "supporting_observations": [], "supporting_interpretations": []},
        ],
    }


def test_working_blueprint_dom_is_not_commit_authority():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
(async () => {
  _crUpdateBlueprintTitle('Memory title');
  _crUpdateBlueprintThesis('Memory thesis.');
  _crUpdateBlueprintClaim(0, 'Memory claim.');
  _crRenderBlueprintCandidate(_crBlueprintCandidate, 'working');
  elements['cr-blueprint-proposal'].innerHTML = 'DOM title DOM thesis DOM claim';
  await _crCommitBlueprintCandidate();
  const commitPost = posts.find(p => p.url === '/api/pipeline/ratify-blueprint');
  process.stdout.write(JSON.stringify({
    candidateBeforeCommitTitle:commitPost.body.proposed_blueprint.title,
    payload:commitPost.body.proposed_blueprint
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["candidateBeforeCommitTitle"] == "Memory title"
    assert "DOM title" not in json.dumps(result["payload"])


def test_blueprint_commit_locks_mutations_and_uses_exact_pending_snapshot():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
let pendingCommit = null;
fetch = async function(url, opts) {
  const body=opts && opts.body ? JSON.parse(opts.body) : {};
  posts.push({url, body});
  if(url==='/api/pipeline/ratify-blueprint'){
    return await new Promise(resolve => { pendingCommit = {resolve}; });
  }
  if(url==='/api/pipeline/extract-blueprint'){
    return {ok:true,json:async()=>({proposed_blueprint:generatedB})};
  }
  throw new Error('unexpected fetch '+url);
};
(async () => {
  _crUpdateBlueprintTitle('Edited A');
  _crUpdateBlueprintThesis('Edited thesis A.');
  _crUpdateBlueprintClaim(1, 'Edited claim B.');
  const edited = JSON.stringify(_crBlueprintCandidate);
  const commitPromise = _crCommitBlueprintCandidate();
  await Promise.resolve();
  const operationDuringCommit = _crBlueprintOperation;
  _crUpdateBlueprintTitle('Blocked title');
  _crUpdateBlueprintThesis('Blocked thesis.');
  _crUpdateBlueprintClaim(0, 'Blocked claim.');
  _crMoveBlueprintClaim(2, -1);
  _crAddBlueprintClaim();
  _crRemoveBlueprintClaim(1);
  await _crCommitBlueprintCandidate();
  await _crGenerateBlueprintCandidate(true);
  const afterBlockedMutations = JSON.stringify(_crBlueprintCandidate);
  const commitPayload = posts.find(p => p.url === '/api/pipeline/ratify-blueprint').body.proposed_blueprint;
  pendingCommit.resolve({ok:true,json:async()=>({blueprint_id:'bp-1',plan_id:'plan-1',committed_blueprint:commitPayload})});
  await commitPromise;
  process.stdout.write(JSON.stringify({
    operationDuringCommit,
    afterBlockedMutations,
    edited,
    candidate:_crBlueprintCandidate,
    dirty:_crBlueprintCandidateDirty,
    operation:_crBlueprintOperation,
    commitCount:posts.filter(p=>p.url==='/api/pipeline/ratify-blueprint').length,
    generationCount:posts.filter(p=>p.url==='/api/pipeline/extract-blueprint').length,
    commitPayload
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["operationDuringCommit"] == "committing"
    assert result["afterBlockedMutations"] == result["edited"]
    assert result["commitCount"] == 1
    assert result["generationCount"] == 0
    assert result["commitPayload"]["title"] == "Edited A"
    assert result["commitPayload"]["sections"][1]["claim"] == "Edited claim B."
    assert result["candidate"] is None
    assert result["dirty"] is False
    assert result["operation"] == "idle"


def test_failed_blueprint_commit_restores_snapshot_and_unlocks_for_retry():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
let pendingCommit = null;
let commitAttempt = 0;
fetch = async function(url, opts) {
  const body=opts && opts.body ? JSON.parse(opts.body) : {};
  posts.push({url, body});
  if(url==='/api/pipeline/ratify-blueprint'){
    commitAttempt += 1;
    if (commitAttempt === 1) {
      return await new Promise(resolve => { pendingCommit = {resolve}; });
    }
    return {ok:true,json:async()=>({blueprint_id:'bp-2',plan_id:'plan-2',committed_blueprint:body.proposed_blueprint})};
  }
  throw new Error('unexpected fetch '+url);
};
(async () => {
  _crUpdateBlueprintTitle('Edited A');
  _crUpdateBlueprintClaim(1, 'Edited claim B.');
  const edited = JSON.stringify(_crBlueprintCandidate);
  const commitPromise = _crCommitBlueprintCandidate();
  await Promise.resolve();
  pendingCommit.resolve({ok:false,json:async()=>({error:'commit failed'})});
  await commitPromise;
  const afterFailure = {
    candidate:JSON.stringify(_crBlueprintCandidate),
    dirty:_crBlueprintCandidateDirty,
    operation:_crBlueprintOperation,
    html:elements['cr-blueprint-proposal'].innerHTML
  };
  _crUpdateBlueprintTitle('Retry title');
  const afterEdit = JSON.stringify(_crBlueprintCandidate);
  await _crCommitBlueprintCandidate();
  const commitPosts = posts.filter(p=>p.url==='/api/pipeline/ratify-blueprint');
  process.stdout.write(JSON.stringify({edited, afterFailure, afterEdit, commitCount:commitPosts.length, retryPayload:commitPosts[1].body.proposed_blueprint, candidate:_crBlueprintCandidate}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["afterFailure"]["candidate"] == result["edited"]
    assert result["afterFailure"]["dirty"] is True
    assert result["afterFailure"]["operation"] == "idle"
    assert "commit failed" in result["afterFailure"]["html"]
    assert json.loads(result["afterEdit"])["title"] == "Retry title"
    assert result["commitCount"] == 2
    assert result["retryPayload"]["title"] == "Retry title"
    assert result["candidate"] is None


def test_blueprint_regeneration_locks_mutations_and_replaces_only_on_success():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
let pendingGenerate = null;
fetch = async function(url, opts) {
  const body=opts && opts.body ? JSON.parse(opts.body) : {};
  posts.push({url, body});
  if(url==='/api/pipeline/extract-blueprint'){
    return await new Promise(resolve => { pendingGenerate = {resolve}; });
  }
  if(url==='/api/pipeline/ratify-blueprint'){
    return {ok:true,json:async()=>({blueprint_id:'bp-blocked',plan_id:'plan-blocked',committed_blueprint:body.proposed_blueprint})};
  }
  throw new Error('unexpected fetch '+url);
};
(async () => {
  _crUpdateBlueprintTitle('Edited A');
  _crUpdateBlueprintClaim(1, 'Edited claim B.');
  const edited = JSON.stringify(_crBlueprintCandidate);
  const generatePromise = _crGenerateBlueprintCandidate(true);
  await Promise.resolve();
  await Promise.resolve();
  const operationDuringGenerate = _crBlueprintOperation;
  _crUpdateBlueprintTitle('Blocked title');
  _crUpdateBlueprintClaim(0, 'Blocked claim.');
  _crMoveBlueprintClaim(2, -1);
  _crAddBlueprintClaim();
  _crRemoveBlueprintClaim(1);
  await _crGenerateBlueprintCandidate(true);
  await _crCommitBlueprintCandidate();
  const afterBlockedMutations = JSON.stringify(_crBlueprintCandidate);
  pendingGenerate.resolve({ok:true,json:async()=>({proposed_blueprint:generatedB})});
  await generatePromise;
  process.stdout.write(JSON.stringify({
    operationDuringGenerate,
    afterBlockedMutations,
    edited,
    candidate:_crBlueprintCandidate,
    dirty:_crBlueprintCandidateDirty,
    operation:_crBlueprintOperation,
    generationCount:posts.filter(p=>p.url==='/api/pipeline/extract-blueprint').length,
    commitCount:posts.filter(p=>p.url==='/api/pipeline/ratify-blueprint').length
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["operationDuringGenerate"] == "generating"
    assert result["afterBlockedMutations"] == result["edited"]
    assert result["generationCount"] == 1
    assert result["commitCount"] == 0
    assert result["candidate"]["title"] == "Generated B"
    assert result["dirty"] is False
    assert result["operation"] == "idle"


def test_failed_blueprint_regeneration_restores_snapshot_and_unlocks():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
let pendingGenerate = null;
fetch = async function(url, opts) {
  const body=opts && opts.body ? JSON.parse(opts.body) : {};
  posts.push({url, body});
  if(url==='/api/pipeline/extract-blueprint'){
    return await new Promise(resolve => { pendingGenerate = {resolve}; });
  }
  throw new Error('unexpected fetch '+url);
};
(async () => {
  _crUpdateBlueprintTitle('Edited A');
  _crUpdateBlueprintClaim(1, 'Edited claim B.');
  const edited = JSON.stringify(_crBlueprintCandidate);
  const generatePromise = _crGenerateBlueprintCandidate(true);
  await Promise.resolve();
  await Promise.resolve();
  pendingGenerate.resolve({ok:false,json:async()=>({error:'generation failed'})});
  await generatePromise;
  const afterFailure = {
    candidate:JSON.stringify(_crBlueprintCandidate),
    dirty:_crBlueprintCandidateDirty,
    operation:_crBlueprintOperation,
    html:elements['cr-blueprint-proposal'].innerHTML
  };
  _crUpdateBlueprintTitle('Retry title');
  process.stdout.write(JSON.stringify({edited, afterFailure, afterEdit:_crBlueprintCandidate, generationCount:posts.filter(p=>p.url==='/api/pipeline/extract-blueprint').length}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["afterFailure"]["candidate"] == result["edited"]
    assert result["afterFailure"]["dirty"] is True
    assert result["afterFailure"]["operation"] == "idle"
    assert "generation failed" in result["afterFailure"]["html"]
    assert result["afterEdit"]["title"] == "Retry title"
    assert result["generationCount"] == 1


def test_blueprint_workspace_change_discards_stale_inflight_generation_response():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
let pendingGenerate = null;
fetch = async function(url, opts) {
  const body=opts && opts.body ? JSON.parse(opts.body) : {};
  posts.push({url, body});
  if(url==='/api/pipeline/extract-blueprint'){
    return await new Promise(resolve => { pendingGenerate = {resolve}; });
  }
  throw new Error('unexpected fetch '+url);
};
(async () => {
  _crUpdateBlueprintTitle('Edited A');
  const generatePromise = _crGenerateBlueprintCandidate(true);
  await Promise.resolve();
  await Promise.resolve();
  _crResetBlueprintWorkingStateForWorkspaceChange();
  pendingGenerate.resolve({ok:true,json:async()=>({proposed_blueprint:generatedB})});
  await generatePromise;
  process.stdout.write(JSON.stringify({
    candidate:_crBlueprintCandidate,
    dirty:_crBlueprintCandidateDirty,
    operation:_crBlueprintOperation,
    html:elements['cr-blueprint-proposal'].innerHTML,
    display:elements['cr-blueprint-proposal'].style.display,
    generationCount:posts.filter(p=>p.url==='/api/pipeline/extract-blueprint').length
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["generationCount"] == 1
    assert result["candidate"] is None
    assert result["dirty"] is False
    assert result["operation"] == "idle"
    assert result["html"] == ""
    assert result["display"] == "none"


def test_reorder_add_and_remove_edit_candidate_sections_not_evidence_records():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
_crMoveBlueprintClaim(0, -1);
const afterFirstNoop = JSON.parse(JSON.stringify(_crBlueprintCandidate.sections));
_crMoveBlueprintClaim(2, 1);
const afterLastNoop = JSON.parse(JSON.stringify(_crBlueprintCandidate.sections));
_crMoveBlueprintClaim(1, 1);
const afterMoveDown = JSON.parse(JSON.stringify(_crBlueprintCandidate.sections));
_crAddBlueprintClaim();
const afterAdd = JSON.parse(JSON.stringify(_crBlueprintCandidate.sections));
_crRemoveBlueprintClaim(0);
const afterRemove = JSON.parse(JSON.stringify(_crBlueprintCandidate.sections));
process.stdout.write(JSON.stringify({afterFirstNoop, afterLastNoop, afterMoveDown, afterAdd, afterRemove, dirty:_crBlueprintCandidateDirty}));
"""
    )

    result = _run_node(script)
    assert result["afterFirstNoop"][0]["claim"] == "Claim A."
    assert result["afterLastNoop"][2]["claim"] == "Claim C."
    assert [s["claim"] for s in result["afterMoveDown"]] == ["Claim A.", "Claim C.", "Claim B."]
    assert result["afterMoveDown"][2]["supporting_observations"] == ["obs-2"]
    assert result["afterMoveDown"][2]["supporting_interpretations"] == ["int-2"]
    assert result["afterAdd"][-1] == {"claim": "", "supporting_observations": [], "supporting_interpretations": []}
    assert "obs-1" not in [oid for section in result["afterRemove"] for oid in section["supporting_observations"]]
    assert result["dirty"] is True


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("_crBlueprintCandidate.title='   ';", "Add a title before committing."),
        ("_crBlueprintCandidate.thesis='   ';", "The working thesis is empty."),
        ("_crBlueprintCandidate.sections[1].claim='   ';", "Claim 2 needs text."),
    ],
)
def test_client_validation_blocks_invalid_working_blueprint_commit(mutation: str, message: str):
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + f"""
(async () => {{
  {mutation}
  _crBlueprintCandidateDirty = true;
  await _crCommitBlueprintCandidate();
  process.stdout.write(JSON.stringify({{
    commitCount:posts.filter(p => p.url === '/api/pipeline/ratify-blueprint').length,
    candidate:_crBlueprintCandidate,
    dirty:_crBlueprintCandidateDirty,
    html:elements['cr-blueprint-proposal'].innerHTML
  }}));
}})().catch(err => {{ console.error(err.stack || err.message); process.exit(1); }});
"""
    )

    result = _run_node(script)
    assert result["commitCount"] == 0
    assert result["candidate"] is not None
    assert result["dirty"] is True
    assert message in result["html"]


def test_regeneration_protects_edited_working_candidate():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
(async () => {
  _crUpdateBlueprintTitle('Edited title');
  window.confirmResult = false;
  await _crGenerateBlueprintCandidate(true);
  const afterCancel = {candidate:JSON.parse(JSON.stringify(_crBlueprintCandidate)), dirty:_crBlueprintCandidateDirty, proposals:posts.filter(p => p.url === '/api/pipeline/extract-blueprint').length};
  window.confirmResult = true;
  generateMode = 'fail';
  await _crGenerateBlueprintCandidate(true);
  const afterFailed = {candidate:JSON.parse(JSON.stringify(_crBlueprintCandidate)), dirty:_crBlueprintCandidateDirty, proposals:posts.filter(p => p.url === '/api/pipeline/extract-blueprint').length};
  generateMode = 'success';
  await _crGenerateBlueprintCandidate(true);
  const afterSuccess = {candidate:JSON.parse(JSON.stringify(_crBlueprintCandidate)), dirty:_crBlueprintCandidateDirty, proposals:posts.filter(p => p.url === '/api/pipeline/extract-blueprint').length};
  process.stdout.write(JSON.stringify({afterCancel, afterFailed, afterSuccess, confirms}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert len(result["confirms"]) == 3
    assert "replace your current working Blueprint" in result["confirms"][0]
    assert result["afterCancel"]["proposals"] == 0
    assert result["afterCancel"]["candidate"]["title"] == "Edited title"
    assert result["afterCancel"]["dirty"] is True
    assert result["afterFailed"]["proposals"] == 1
    assert result["afterFailed"]["candidate"]["title"] == "Edited title"
    assert result["afterFailed"]["dirty"] is True
    assert result["afterSuccess"]["proposals"] == 2
    assert result["afterSuccess"]["candidate"]["title"] == "Generated B"
    assert result["afterSuccess"]["dirty"] is False


def test_failed_commit_preserves_edited_candidate_for_exact_retry():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
(async () => {
  _crUpdateBlueprintTitle('Edited title');
  _crUpdateBlueprintThesis('Edited thesis.');
  _crUpdateBlueprintClaim(1, 'Edited claim B.');
  _crMoveBlueprintClaim(2, -1);
  generateMode = 'commit-fail';
  await _crCommitBlueprintCandidate();
  const afterFailure = {candidate:JSON.parse(JSON.stringify(_crBlueprintCandidate)), dirty:_crBlueprintCandidateDirty, html:elements['cr-blueprint-proposal'].innerHTML};
  generateMode = 'success';
  await _crCommitBlueprintCandidate();
  const commitPosts = posts.filter(p => p.url === '/api/pipeline/ratify-blueprint');
  process.stdout.write(JSON.stringify({afterFailure, retryPayload:commitPosts[1].body.proposed_blueprint, commitCount:commitPosts.length}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["afterFailure"]["candidate"]["title"] == "Edited title"
    assert result["afterFailure"]["candidate"]["sections"][2]["claim"] == "Edited claim B."
    assert result["afterFailure"]["dirty"] is True
    assert "commit failed" in result["afterFailure"]["html"]
    assert result["commitCount"] == 2
    assert result["retryPayload"] == result["afterFailure"]["candidate"]


def test_edited_working_blueprint_survives_workstation_and_page_continuity():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + "let _crBottomMode = ''; let _crPage = 1; let _crTotalPages = 2; let renders = 0;"
        + "function makePanel(id){return {id,hidden:false,dataset:{},style:{},innerHTML:'',textContent:'',setAttribute(){},classList:{toggle(){},remove(){}}};}"
        + "Object.assign(elements,{"
        + "'cr-bottom-workstation':makePanel('cr-bottom-workstation'),"
        + "'cr-bottom-collapse-handle':makePanel('cr-bottom-collapse-handle'),"
        + "'cr-blueprint-draft':makePanel('cr-blueprint-draft'),"
        + "'cr-render-preview':makePanel('cr-render-preview'),"
        + "'cr-critic-audit':makePanel('cr-critic-audit'),"
        + "'cr-perspective-run':makePanel('cr-perspective-run'),"
        + "'cr-fln-tray':makePanel('cr-fln-tray'),"
        + "'corpus-search':makePanel('corpus-search'),"
        + "'attn-timeline':makePanel('attn-timeline'),"
        + "'cr-voice-profile':makePanel('cr-voice-profile'),"
        + "'cr-artist-draft':makePanel('cr-artist-draft'),"
        + "'cr-record-ledger':makePanel('cr-record-ledger'),"
        + "'cr-blueprint-subtabs':makePanel('cr-blueprint-subtabs'),"
        + "'cr-expression-subtabs':makePanel('cr-expression-subtabs'),"
        + "'cr-blueprint-question':makePanel('cr-blueprint-question'),"
        + "'cr-blueprint-meta':makePanel('cr-blueprint-meta'),"
        + "'cr-page-view':{offsetTop:120}"
        + "});"
        + "document.body={classList:{toggle(){}}}; document.querySelectorAll=()=>[];"
        + "function invLoad(){return {thesis:'What does the light do?'};}"
        + "async function _crGatherBlueprintEvidence(){return {notes:[],highlights:[],observations:[]};}"
        + "function cmpMarkOnboardingStep(){} async function _attnLoad(){} function _flnLoadEntries(){}"
        + "async function _crLoadPerspectiveRun(){} function _crLoadRenderPreview(){} function _crLoadCriticAudit(){}"
        + "function _crLoadVoiceProfile(){} function _crLoadArtistDraft(){} function _crLoadRecordLedger(){}"
        + "function _crRenderPage(){renders++;} window.scrollTo=()=>{};"
        + _extract_fn(html, "_crBottomPanels")
        + _extract_fn(html, "_crWorkstationResourceForMode")
        + _extract_fn(html, "_crSyncBottomWorkstationState")
        + _extract_fn(html, "_crOpenBottomWorkstation")
        + _extract_fn(html, "_crCloseBottomWorkstation")
        + _extract_fn(html, "_crLoadBlueprintDraft")
        + _extract_fn(html, "_crNextPage")
        + _extract_fn(html, "_crPrevPage")
        + _editor_functions(html)
        + """
(async () => {
  _crUpdateBlueprintTitle('Edited title');
  _crUpdateBlueprintClaim(1, 'Edited claim B.');
  _crMoveBlueprintClaim(2, -1);
  const edited = JSON.stringify(_crBlueprintCandidate);
  await _crOpenBottomWorkstation('blueprint');
  _crCloseBottomWorkstation();
  await _crOpenBottomWorkstation('blueprint');
  const afterReopen = JSON.stringify(_crBlueprintCandidate);
  await _crOpenBottomWorkstation('perspective');
  await _crOpenBottomWorkstation('blueprint');
  const afterResource = JSON.stringify(_crBlueprintCandidate);
  await _crOpenBottomWorkstation('render');
  await _crOpenBottomWorkstation('blueprint');
  const afterSubview = JSON.stringify(_crBlueprintCandidate);
  _crNextPage();
  _crPrevPage();
  await _crOpenBottomWorkstation('blueprint');
  const afterPage = JSON.stringify(_crBlueprintCandidate);
  process.stdout.write(JSON.stringify({edited, afterReopen, afterResource, afterSubview, afterPage, dirty:_crBlueprintCandidateDirty, html:elements['cr-blueprint-proposal'].innerHTML}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["afterReopen"] == result["edited"]
    assert result["afterResource"] == result["edited"]
    assert result["afterSubview"] == result["edited"]
    assert result["afterPage"] == result["edited"]
    assert result["dirty"] is True
    assert "Working candidate · edited · not saved" in result["html"]


def test_edited_working_blueprint_clears_dirty_state_on_confirmed_workspace_change():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + "let _wsCurrentWorkspace = null;"
        + "Object.assign(elements,{'runtime-workspace-chip':{hidden:true,dataset:{},title:''},'runtime-workspace-name':{textContent:''}});"
        + "function _runtimeApplyWorkspaceDraftScope(){} function _wsRenderWorkspaceCatalog(){} function _crResetPerspectiveRoomStateForWorkspaceChange(){}"
        + _extract_fn(html, "_wsWorkspaceSelector")
        + _extract_fn(html, "_wsWorkspaceMatches")
        + _editor_functions(html)
        + _extract_fn(html, "_wsApplyCurrentWorkspace")
        + """
_crUpdateBlueprintTitle('Edited title');
_wsApplyCurrentWorkspace({id:'workspace-a',slug:'a',name:'A',kind:'managed'});
_wsApplyCurrentWorkspace({id:'workspace-b',slug:'b',name:'B',kind:'managed'});
process.stdout.write(JSON.stringify({candidate:_crBlueprintCandidate, dirty:_crBlueprintCandidateDirty, html:elements['cr-blueprint-proposal'].innerHTML, display:elements['cr-blueprint-proposal'].style.display}));
"""
    )

    result = _run_node(script)
    assert result["candidate"] is None
    assert result["dirty"] is False
    assert result["html"] == ""
    assert result["display"] == "none"
