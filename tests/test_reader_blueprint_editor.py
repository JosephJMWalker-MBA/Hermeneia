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
        "_crClearBlueprintRevisionState",
        "_crUpdateBlueprintRevisionReason",
        "_crUpdateBlueprintTitle",
        "_crUpdateBlueprintThesis",
        "_crUpdateBlueprintClaim",
        "_crMoveBlueprintClaim",
        "_crAddBlueprintClaim",
        "_crRemoveBlueprintClaim",
        "_crBlueprintCandidateFromSkeleton",
        "_crBeginBlueprintRevision",
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
        "let _crBlueprintRevision = null;"
        "let _crBlueprintRevisionRequestSeq = 0;"
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
        "'cr-blueprint-thesis':makeEl('cr-blueprint-thesis'),"
        "'cr-blueprint-revision-reason':makeEl('cr-blueprint-revision-reason'),"
        "'cr-render-body':makeEl('cr-render-body')"
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
        "if(url==='/api/pipeline/revise-blueprint'){"
        " if(generateMode==='commit-fail'){return {ok:false,json:async()=>({error:'revision failed'})};}"
        " return {ok:true,json:async()=>({blueprint_id:'bp-revision',plan_id:'plan-revision',committed_blueprint:body.proposed_blueprint,supersession:{old_id:body.predecessor_id,new_id:'bp-revision',reason:body.reason,ratified_at:'2026-01-01T00:00:00Z'}})};"
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


def test_blueprint_workspace_change_during_seed_assembly_sends_no_provider_request():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
let pendingSeed = null;
_crAssembleBlueprintSeed = async function() {
  return await new Promise(resolve => { pendingSeed = {resolve}; });
};
fetch = async function(url, opts) {
  const body=opts && opts.body ? JSON.parse(opts.body) : {};
  posts.push({url, body});
  return {ok:true,json:async()=>({proposed_blueprint:generatedB})};
};
(async () => {
  _crUpdateBlueprintTitle('Edited A');
  const generatePromise = _crGenerateBlueprintCandidate(true);
  await Promise.resolve();
  _crResetBlueprintWorkingStateForWorkspaceChange();
  pendingSeed.resolve('valid stale workspace-A seed');
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
    assert result["generationCount"] == 0
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


def test_begin_blueprint_revision_loads_committed_blueprint_as_unsaved_working_revision():
    html = _index()
    script = (
        _dom_prefix("null")
        + "async function _crFetchSkeleton(id){return {id,title:'Committed A',thesis:'Thesis A.',sections:[{claim:'Claim A.',supporting_observations:['obs-1'],supporting_interpretations:['int-1']}],claims:[],hasPlan:true,planId:'plan-a',supersedes:[],supersededBy:[]};}"
        + "async function _crOpenBottomWorkstation(mode){posts.push({url:'open', mode});}"
        + _editor_functions(html)
        + """
(async () => {
  await _crBeginBlueprintRevision('bp-a');
  process.stdout.write(JSON.stringify({
    candidate:_crBlueprintCandidate,
    dirty:_crBlueprintCandidateDirty,
    revision:_crBlueprintRevision,
    html:elements['cr-blueprint-proposal'].innerHTML,
    opens:posts.filter(p => p.url === 'open')
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["candidate"] == {
        "title": "Committed A",
        "thesis": "Thesis A.",
        "sections": [
            {"claim": "Claim A.", "supporting_observations": ["obs-1"], "supporting_interpretations": ["int-1"]},
        ],
    }
    assert result["dirty"] is False
    assert result["revision"] == {"predecessorId": "bp-a", "predecessorTitle": "Committed A", "reason": ""}
    assert "Working revision · not saved of Committed A · bp-a…" in result["html"]
    assert "Why are you revising this Blueprint?" in result["html"]
    assert result["opens"] == [{"url": "open", "mode": "blueprint"}]


def test_blueprint_revision_requires_human_reason_before_commit():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
(async () => {
  _crBlueprintRevision = {predecessorId:'bp-a', predecessorTitle:'Committed A', reason:'   '};
  _crUpdateBlueprintTitle('Revision title');
  await _crCommitBlueprintCandidate();
  process.stdout.write(JSON.stringify({
    revision:_crBlueprintRevision,
    dirty:_crBlueprintCandidateDirty,
    html:elements['cr-blueprint-proposal'].innerHTML,
    reviseCount:posts.filter(p => p.url === '/api/pipeline/revise-blueprint').length,
    ratifyCount:posts.filter(p => p.url === '/api/pipeline/ratify-blueprint').length
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["reviseCount"] == 0
    assert result["ratifyCount"] == 0
    assert result["dirty"] is True
    assert result["revision"]["predecessorId"] == "bp-a"
    assert "Add a reason before committing this revision." in result["html"]


def test_blueprint_revision_commit_posts_successor_reason_and_clears_transient_state():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
(async () => {
  _crBlueprintRevision = {predecessorId:'bp-a', predecessorTitle:'Committed A', reason:'Initial reason'};
  _crUpdateBlueprintTitle('Revision title');
  _crUpdateBlueprintRevisionReason('Human reason.');
  await _crCommitBlueprintCandidate();
  const revisePost = posts.find(p => p.url === '/api/pipeline/revise-blueprint');
  process.stdout.write(JSON.stringify({
    reviseCount:posts.filter(p => p.url === '/api/pipeline/revise-blueprint').length,
    ratifyCount:posts.filter(p => p.url === '/api/pipeline/ratify-blueprint').length,
    payload:revisePost.body,
    candidate:_crBlueprintCandidate,
    dirty:_crBlueprintCandidateDirty,
    revision:_crBlueprintRevision,
    active:_crActiveBlueprintId,
    html:elements['cr-blueprint-proposal'].innerHTML
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["reviseCount"] == 1
    assert result["ratifyCount"] == 0
    assert result["payload"]["predecessor_id"] == "bp-a"
    assert result["payload"]["reason"] == "Human reason."
    assert result["payload"]["proposed_blueprint"]["title"] == "Revision title"
    assert result["candidate"] is None
    assert result["dirty"] is False
    assert result["revision"] is None
    assert result["active"] == "bp-revision"
    assert "supersedes bp-a…" in result["html"]


def test_failed_blueprint_revision_commit_preserves_candidate_reason_for_retry():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + _editor_functions(html)
        + """
(async () => {
  _crBlueprintRevision = {predecessorId:'bp-a', predecessorTitle:'Committed A', reason:'Human reason.'};
  _crUpdateBlueprintTitle('Revision title');
  _crUpdateBlueprintClaim(1, 'Revision claim B.');
  generateMode = 'commit-fail';
  await _crCommitBlueprintCandidate();
  const afterFailure = {
    candidate:JSON.parse(JSON.stringify(_crBlueprintCandidate)),
    dirty:_crBlueprintCandidateDirty,
    revision:_crBlueprintRevision,
    html:elements['cr-blueprint-proposal'].innerHTML
  };
  generateMode = 'success';
  await _crCommitBlueprintCandidate();
  const revisePosts = posts.filter(p => p.url === '/api/pipeline/revise-blueprint');
  process.stdout.write(JSON.stringify({afterFailure, retryPayload:revisePosts[1].body, reviseCount:revisePosts.length, candidate:_crBlueprintCandidate, revision:_crBlueprintRevision}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["afterFailure"]["candidate"]["title"] == "Revision title"
    assert result["afterFailure"]["candidate"]["sections"][1]["claim"] == "Revision claim B."
    assert result["afterFailure"]["dirty"] is True
    assert result["afterFailure"]["revision"] == {
        "predecessorId": "bp-a",
        "predecessorTitle": "Committed A",
        "reason": "Human reason.",
    }
    assert "revision failed" in result["afterFailure"]["html"]
    assert result["reviseCount"] == 2
    assert result["retryPayload"]["reason"] == "Human reason."
    assert result["candidate"] is None
    assert result["revision"] is None


def test_working_blueprint_revision_survives_workstation_and_page_continuity():
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
  _crBlueprintRevision = {predecessorId:'bp-a', predecessorTitle:'Committed A', reason:'Human reason.'};
  _crUpdateBlueprintTitle('Revision title');
  _crUpdateBlueprintClaim(1, 'Revision claim B.');
  const edited = JSON.stringify(_crBlueprintCandidate);
  const revision = JSON.stringify(_crBlueprintRevision);
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
  process.stdout.write(JSON.stringify({edited, revision, afterReopen, afterResource, afterSubview, afterPage, afterRevision:JSON.stringify(_crBlueprintRevision), dirty:_crBlueprintCandidateDirty, html:elements['cr-blueprint-proposal'].innerHTML}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["afterReopen"] == result["edited"]
    assert result["afterResource"] == result["edited"]
    assert result["afterSubview"] == result["edited"]
    assert result["afterPage"] == result["edited"]
    assert result["afterRevision"] == result["revision"]
    assert result["dirty"] is True
    assert "Working revision · edited · not saved of Committed A · bp-a…" in result["html"]


def test_starting_another_blueprint_revision_requires_confirmation_and_cancel_preserves_existing_work():
    html = _index()
    script = (
        _dom_prefix(_candidate_js())
        + "const skeletons={"
        + "'bp-cancel':{id:'bp-cancel',title:'Cancel target',thesis:'Cancel thesis.',sections:[{claim:'Cancel claim.',supporting_observations:[],supporting_interpretations:[]}],claims:[],hasPlan:true,planId:'plan-cancel'},"
        + "'bp-next':{id:'bp-next',title:'Next target',thesis:'Next thesis.',sections:[{claim:'Next claim.',supporting_observations:['obs-next'],supporting_interpretations:[]}],claims:[],hasPlan:true,planId:'plan-next'}"
        + "};"
        + "async function _crFetchSkeleton(id){return skeletons[id];}"
        + "async function _crOpenBottomWorkstation(mode){posts.push({url:'open', mode});}"
        + _editor_functions(html)
        + """
(async () => {
  _crBlueprintRevision = {predecessorId:'bp-a', predecessorTitle:'Committed A', reason:'Human reason.'};
  _crUpdateBlueprintTitle('Edited revision A');
  const before = JSON.stringify(_crBlueprintCandidate);
  window.confirmResult = false;
  await _crBeginBlueprintRevision('bp-cancel');
  const afterCancel = {candidate:JSON.stringify(_crBlueprintCandidate), revision:_crBlueprintRevision};
  window.confirmResult = true;
  await _crBeginBlueprintRevision('bp-next');
  const afterConfirm = {candidate:_crBlueprintCandidate, revision:_crBlueprintRevision};
  process.stdout.write(JSON.stringify({before, afterCancel, afterConfirm, confirms}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["afterCancel"]["candidate"] == result["before"]
    assert result["afterCancel"]["revision"]["predecessorId"] == "bp-a"
    assert result["afterConfirm"]["candidate"]["title"] == "Next target"
    assert result["afterConfirm"]["candidate"]["sections"][0]["supporting_observations"] == ["obs-next"]
    assert result["afterConfirm"]["revision"] == {
        "predecessorId": "bp-next",
        "predecessorTitle": "Next target",
        "reason": "",
    }
    assert len(result["confirms"]) == 2
    assert "Start another Blueprint revision?" in result["confirms"][0]


def test_stale_blueprint_revision_load_after_workspace_change_is_ignored():
    html = _index()
    script = (
        _dom_prefix("null")
        + "let pending = null;"
        + "async function _crFetchSkeleton(id){return await new Promise((resolve,reject)=>{pending={id,resolve,reject};});}"
        + "async function _crOpenBottomWorkstation(mode){posts.push({url:'open', mode});}"
        + _editor_functions(html)
        + """
(async () => {
  const load = _crBeginBlueprintRevision('bp-a');
  await Promise.resolve();
  _crResetBlueprintWorkingStateForWorkspaceChange();
  pending.resolve({id:'bp-a',title:'Blueprint A',thesis:'Thesis A.',sections:[{claim:'Claim A.',supporting_observations:['obs-a'],supporting_interpretations:[]}],claims:[],hasPlan:true,planId:'plan-a'});
  await load;
  process.stdout.write(JSON.stringify({
    candidate:_crBlueprintCandidate,
    revision:_crBlueprintRevision,
    dirty:_crBlueprintCandidateDirty,
    active:_crActiveBlueprintId,
    html:elements['cr-blueprint-proposal'].innerHTML,
    renderError:elements['cr-render-body'].innerHTML,
    opens:posts.filter(p => p.url === 'open'),
    seq:_crBlueprintRevisionRequestSeq,
    epoch:_crBlueprintWorkspaceEpoch
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["candidate"] is None
    assert result["revision"] is None
    assert result["dirty"] is False
    assert result["active"] == ""
    assert result["html"] == ""
    assert result["renderError"] == ""
    assert result["opens"] == []
    assert result["epoch"] == 1
    assert result["seq"] == 2


def test_newer_same_workspace_blueprint_revision_load_wins_over_late_old_success():
    html = _index()
    script = (
        _dom_prefix("null")
        + "const pending = {};"
        + "async function _crFetchSkeleton(id){return await new Promise((resolve,reject)=>{pending[id]={resolve,reject};});}"
        + "async function _crOpenBottomWorkstation(mode){posts.push({url:'open', mode});}"
        + _editor_functions(html)
        + """
(async () => {
  const oldLoad = _crBeginBlueprintRevision('bp-a');
  await Promise.resolve();
  const newLoad = _crBeginBlueprintRevision('bp-c');
  await Promise.resolve();
  pending['bp-c'].resolve({id:'bp-c',title:'Blueprint C',thesis:'Thesis C.',sections:[{claim:'Claim C.',supporting_observations:['obs-c'],supporting_interpretations:[]}],claims:[],hasPlan:true,planId:'plan-c'});
  await newLoad;
  pending['bp-a'].resolve({id:'bp-a',title:'Blueprint A',thesis:'Thesis A.',sections:[{claim:'Claim A.',supporting_observations:['obs-a'],supporting_interpretations:[]}],claims:[],hasPlan:true,planId:'plan-a'});
  await oldLoad;
  process.stdout.write(JSON.stringify({
    candidate:_crBlueprintCandidate,
    revision:_crBlueprintRevision,
    dirty:_crBlueprintCandidateDirty,
    html:elements['cr-blueprint-proposal'].innerHTML,
    opens:posts.filter(p => p.url === 'open')
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["candidate"]["title"] == "Blueprint C"
    assert result["candidate"]["sections"][0]["supporting_observations"] == ["obs-c"]
    assert result["revision"] == {
        "predecessorId": "bp-c",
        "predecessorTitle": "Blueprint C",
        "reason": "",
    }
    assert result["dirty"] is False
    assert "Blueprint C" in result["html"]
    assert "Blueprint A" not in result["html"]
    assert result["opens"] == [{"url": "open", "mode": "blueprint"}]


def test_stale_blueprint_revision_load_error_after_newer_intent_is_ignored():
    html = _index()
    script = (
        _dom_prefix("null")
        + "const pending = {};"
        + "async function _crFetchSkeleton(id){return await new Promise((resolve,reject)=>{pending[id]={resolve,reject};});}"
        + "async function _crOpenBottomWorkstation(mode){posts.push({url:'open', mode});}"
        + _editor_functions(html)
        + """
(async () => {
  const oldLoad = _crBeginBlueprintRevision('bp-a');
  await Promise.resolve();
  const newLoad = _crBeginBlueprintRevision('bp-c');
  await Promise.resolve();
  pending['bp-c'].resolve({id:'bp-c',title:'Blueprint C',thesis:'Thesis C.',sections:[{claim:'Claim C.',supporting_observations:[],supporting_interpretations:[]}],claims:[],hasPlan:true,planId:'plan-c'});
  await newLoad;
  pending['bp-a'].reject(new Error('stale A failed'));
  await oldLoad;
  process.stdout.write(JSON.stringify({
    candidate:_crBlueprintCandidate,
    revision:_crBlueprintRevision,
    renderError:elements['cr-render-body'].innerHTML,
    html:elements['cr-blueprint-proposal'].innerHTML,
    opens:posts.filter(p => p.url === 'open')
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["candidate"]["title"] == "Blueprint C"
    assert result["revision"]["predecessorId"] == "bp-c"
    assert result["renderError"] == ""
    assert "stale A failed" not in result["html"]
    assert "Blueprint C" in result["html"]
    assert result["opens"] == [{"url": "open", "mode": "blueprint"}]


def test_structure_preview_renders_blueprint_history_and_revision_action():
    html = _index()
    script = (
        _dom_prefix("null")
        + "async function _crFetchSkeleton(id){return {id,title:'Blueprint B',thesis:'Thesis B.',claims:[{n:1,claim:'Claim B.',evidence:[]}],hasPlan:true,planId:'plan-b',supersedes:[{old_id:'bp-a',old_title:'Blueprint A',reason:'Because A needed revision.'}],supersededBy:[{new_id:'bp-c',new_title:'Blueprint C',reason:'Because C branched.'}]};}"
        + _extract_fn(html, "_crBlueprintCanMutate")
        + _extract_fn(html, "_crRenderBlueprintSkeleton")
        + """
(async () => {
  await _crRenderBlueprintSkeleton('bp-b');
  process.stdout.write(JSON.stringify({
    active:_crActiveBlueprintId,
    html:elements['cr-render-body'].innerHTML
  }));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["active"] == "bp-b"
    assert "Supersedes" in result["html"]
    assert "Blueprint A · bp-a…" in result["html"]
    assert "Because A needed revision." in result["html"]
    assert "Superseded by" in result["html"]
    assert "Blueprint C · bp-c…" in result["html"]
    assert "Because C branched." in result["html"]
    assert "_crBeginBlueprintRevision('bp-b')" in result["html"]
    assert "current" not in result["html"].lower()
    assert "latest" not in result["html"].lower()
