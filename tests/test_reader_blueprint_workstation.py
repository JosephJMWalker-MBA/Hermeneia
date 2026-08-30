"""Thesis → Blueprint workflow (PR 6).

A forward path from the reader's governing question + captured evidence to a
proposed Intent Hypothesis, living under the Blueprint resource in the shared
bottom workstation. Generation and commit are separate so the reviewed candidate
is the exact structure persisted and compiled.
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
APP = ROOT / "hermeneia" / "web" / "app.py"


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
        pytest.skip("node not available for Reader Blueprint UI test")
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_blueprint_tab_and_panel_present():
    index = _index()
    assert 'id="cr-bottom-resource-blueprint"' in index
    assert 'data-workstation-resource="blueprint"' in index
    assert 'aria-controls="cr-blueprint-draft cr-render-preview cr-critic-audit"' in index
    assert 'id="cr-blueprint-subtab-build"' in index
    assert 'data-workstation-submode="blueprint"' in index
    assert "_crOpenBottomWorkstation('blueprint')" in index
    # Panel exists and starts hidden.
    assert 'id="cr-blueprint-draft"' in index
    assert 'id="cr-blueprint-draft" hidden' in index
    assert "Blueprint · Build" in index


def test_blueprint_is_a_workstation_mode_not_a_separate_drawer():
    index = _index()
    # Registered in the mutually-exclusive panel map, the open branch, and the
    # resource bindings — so _crSyncBottomWorkstationState shows only one at a time.
    assert "blueprint: document.getElementById('cr-blueprint-draft')" in index
    assert "else if (mode === 'blueprint')" in index
    assert "['cr-bottom-resource-blueprint', () => _crToggleBottomWorkstationResource('blueprint')]" in index
    assert "if (mode === 'render' || mode === 'critic') return 'blueprint';" in index


def test_blueprint_generation_and_commit_use_separate_endpoints():
    index = _index()
    assert "'/api/pipeline/extract-blueprint'" in index
    assert "'/api/pipeline/ratify-blueprint'" in index
    assert "save: false" in index
    assert "_crDraftBlueprint(true)" not in index
    app = APP.read_text()
    assert app.count('@app.route("/api/pipeline/extract-blueprint"') == 1
    assert app.count('@app.route("/api/pipeline/ratify-blueprint"') == 1


def test_blueprint_seeds_from_question_and_captured_evidence():
    index = _index()
    assert "function _crAssembleBlueprintSeed" in index
    assert "invLoad()?.thesis" in index          # governing question
    assert "/api/investigation-log" in index      # field notes
    assert "/api/e10/observations" in index       # observations
    assert "_crHighlights" in index               # saved highlights


def test_blueprint_draft_and_load_are_exposed():
    index = _index()
    assert "window._crLoadBlueprintDraft = _crLoadBlueprintDraft;" in index
    assert "window._crDraftBlueprint = _crDraftBlueprint;" in index
    assert "window._crGenerateBlueprintCandidate = _crGenerateBlueprintCandidate;" in index
    assert "window._crCommitBlueprintCandidate = _crCommitBlueprintCandidate;" in index


def test_blueprint_build_copy_marks_working_state_and_exact_commit():
    index = _index()
    assert "Generate candidate" in index
    assert "Working candidate · not saved" in index
    assert "Commit reviewed Blueprint" in index
    assert "Committed Blueprint" in index
    assert "Architect contract compiled" in index
    assert "Generation proposes. You review. Commit saves exactly what you reviewed." in index
    assert "let _crBlueprintCandidate = null;" in index


def test_blueprint_commit_submits_stored_candidate_not_displayed_html_or_generation_path():
    index = _index()
    commit_start = index.index("async function _crCommitBlueprintCandidate")
    commit_end = index.index("async function _crDraftBlueprint", commit_start)
    commit_fn = index[commit_start:commit_end]

    assert "JSON.stringify({ proposed_blueprint: _crBlueprintCandidate })" in commit_fn
    assert "/api/pipeline/ratify-blueprint" in commit_fn
    assert "/api/pipeline/extract-blueprint" not in commit_fn
    assert "_crAssembleBlueprintSeed" not in commit_fn


def test_blueprint_client_flow_preserves_working_candidate_across_commit_and_failures():
    html = _index()
    script = (
        "let _crBlueprintCandidate = null; let _crActiveBlueprintId = '';"
        "const candidateA={title:'Reviewed A',thesis:'Thesis A.',sections:[{claim:'Claim A.',supporting_observations:['obs-1'],supporting_interpretations:[]}]};"
        "const candidateB={title:'Replacement B',thesis:'Thesis B.',sections:[{claim:'Claim B.',supporting_observations:[],supporting_interpretations:[]}]};"
        "const posts=[]; let generateFailures=0; let commitFailures=0;"
        "function x(v){return String(v == null ? '' : v).replace(/[&<>\"']/g, c => c);}"
        "const elements={"
        "'cr-blueprint-provider':{value:'null'},"
        "'cr-blueprint-btn':{disabled:false,textContent:'Generate candidate'},"
        "'cr-blueprint-proposal':{style:{display:'none'},innerHTML:''},"
        "'cr-blueprint-commit-btn':{disabled:false,textContent:'Commit reviewed Blueprint'}"
        "};"
        "const document={getElementById(id){return elements[id]||null;}};"
        "function invLoad(){return {thesis:'What does the light do?'};}"
        "async function _crAssembleBlueprintSeed(){return 'governing question plus evidence';}"
        "function _crOpenBottomWorkstation(mode){posts.push({url:'open', mode});}"
        "function e10Go(stage){posts.push({url:'go', stage});}"
        "async function fetch(url, opts){"
        "const body=JSON.parse(opts.body); posts.push({url, body});"
        "if(url==='/api/pipeline/extract-blueprint'){"
        " if(generateFailures){return {ok:false,json:async()=>({error:'generation failed'})};}"
        " return {ok:true,json:async()=>({proposed_blueprint:candidateA})};"
        "}"
        "if(url==='/api/pipeline/ratify-blueprint'){"
        " if(commitFailures){return {ok:false,json:async()=>({error:'commit failed'})};}"
        " return {ok:true,json:async()=>({blueprint_id:'bp-1',plan_id:'plan-1',committed_blueprint:body.proposed_blueprint})};"
        "}"
        "throw new Error('unexpected fetch '+url);"
        "}"
        + _extract_fn(html, "_crRenderBlueprintCandidate")
        + _extract_fn(html, "_crGenerateBlueprintCandidate")
        + _extract_fn(html, "_crCommitBlueprintCandidate")
        + """
(async () => {
  await _crGenerateBlueprintCandidate();
  const afterGenerate = {candidate:_crBlueprintCandidate, extractPosts:posts.filter(p=>p.url==='/api/pipeline/extract-blueprint').length};
  await _crCommitBlueprintCandidate();
  const commitPost = posts.find(p=>p.url==='/api/pipeline/ratify-blueprint');
  const afterCommit = {candidate:_crBlueprintCandidate, active:_crActiveBlueprintId, commitPost};
  commitFailures = 1;
  _crBlueprintCandidate = candidateA;
  await _crCommitBlueprintCandidate();
  const afterFailedCommit = {candidate:_crBlueprintCandidate, html:elements['cr-blueprint-proposal'].innerHTML};
  generateFailures = 1;
  _crBlueprintCandidate = candidateB;
  await _crGenerateBlueprintCandidate(true);
  const afterFailedRegenerate = {candidate:_crBlueprintCandidate, html:elements['cr-blueprint-proposal'].innerHTML};
  process.stdout.write(JSON.stringify({afterGenerate, afterCommit, afterFailedCommit, afterFailedRegenerate}));
})().catch(err => { console.error(err.stack || err.message); process.exit(1); });
"""
    )

    result = _run_node(script)
    assert result["afterGenerate"]["candidate"]["title"] == "Reviewed A"
    assert result["afterGenerate"]["extractPosts"] == 1
    assert result["afterCommit"]["commitPost"]["body"]["proposed_blueprint"]["title"] == "Reviewed A"
    assert result["afterCommit"]["active"] == "bp-1"
    assert result["afterFailedCommit"]["candidate"]["title"] == "Reviewed A"
    assert "commit failed" in result["afterFailedCommit"]["html"]
    assert result["afterFailedRegenerate"]["candidate"]["title"] == "Replacement B"
    assert "generation failed" in result["afterFailedRegenerate"]["html"]
