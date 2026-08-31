"""Reader Expression draft view — contract/profile/provider Artist preview.

A nested Expression workstation view renders ArchitectPlan + ExpressionProfile
through one provider into a clearly-labeled draft *preview*. This is the danger
point where the app could collapse Blueprint, profile, and provider into a vague
"AI writes essay" surface, so these tests guard the honest framing and payload.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name}"
    return match.group(0)


def test_draft_tab_and_panel_present():
    index = _index()
    assert 'id="cr-bottom-tab-draft"' not in index
    assert 'id="cr-bottom-resource-expression"' in index
    assert 'data-workstation-resource="expression"' in index
    assert 'id="cr-expression-subtab-draft"' in index
    assert 'data-workstation-submode="draft"' in index
    assert 'aria-controls="cr-artist-draft"' in index
    assert "_crOpenBottomWorkstation('draft')" in index
    assert 'id="cr-artist-draft"' in index
    assert 'id="cr-artist-draft" hidden' in index
    assert "Expression · Draft" in index


def test_draft_is_a_workstation_mode_not_a_separate_drawer():
    index = _index()
    assert "draft: document.getElementById('cr-artist-draft')" in index
    assert "else if (mode === 'draft')" in index
    assert "['cr-expression-subtab-draft', () => _crOpenBottomWorkstation('draft')]" in index
    assert "if (mode === 'voice' || mode === 'draft') return 'expression';" in index


def test_draft_lets_the_steward_choose_skeleton_and_profile():
    index = _index()
    assert 'id="cr-draft-blueprint"' in index      # compiled ArchitectPlan selector
    assert 'title="Semantic contract compiled from a Blueprint"' in index
    assert 'id="cr-draft-profile"' in index        # ExpressionProfile selector
    assert 'id="cr-draft-provider"' in index        # execution provider selector
    assert "Semantic contract" in index
    assert "Expression Profile" in index
    assert "Execution provider" in index
    assert "'/api/profiles'" in index
    assert 'title="Which Structure Preview"' not in index


def test_button_language_is_honest_not_final_essay():
    index = _index()
    assert "Preview Artist Draft" in index
    # The danger this slice is built to avoid.
    assert "Generate Final Essay" not in index
    assert "Final Essay" not in index


def test_preview_path_saves_nothing_and_uses_preview_endpoint():
    index = _index()
    region = _extract_fn(index, "_crPreviewArtistDraft")
    assert "'/api/pipeline/preview-artist'" in region
    assert "plan_id: sk.planId" in region
    assert "profile: profile || null" in region
    assert "provider" in region
    assert "blueprint_text" not in region
    assert "execution_config" not in region
    # The preview itself persists nothing — it never calls a saving endpoint.
    # (It may render a separate "Ratify & Save Draft" affordance, but that is a
    # distinct explicit action handled by _crRatifyDraft, not the preview.)
    low = region.lower()
    assert "run-artist" not in low
    assert "ratify-draft" not in low        # preview never saves
    # The output is labeled as an unsaved preview.
    assert "not saved, not accepted" in index


def test_draft_functions_exposed():
    index = _index()
    assert "window._crLoadArtistDraft = _crLoadArtistDraft;" in index
    assert "window._crPreviewArtistDraft = _crPreviewArtistDraft;" in index


def test_expression_contract_copy_distinguishes_contract_profile_and_execution():
    index = _index()
    assert "A Perspective controls how evidence is examined" in index
    assert "an Expression Profile controls how an already-governed semantic contract may be expressed" in index
    assert "Artist previews render one compiled ArchitectPlan through one Expression Profile with one execution provider" in index
    assert "The Blueprint remains ancestry for the contract; it is not a second drafting authority" in index
    assert "Pick a skeleton, a voice, and a provider" not in index
    assert "Which Structure Preview" not in index


def test_missing_architect_plan_is_blocked_before_preview_request():
    index = _index()
    region = _extract_fn(index, "_crPreviewArtistDraft")
    missing_plan = region[region.index("if (!sk.planId)"):]
    assert "no compiled semantic contract" in missing_plan
    assert region.index("if (!sk.planId)") < region.index("fetch('/api/pipeline/preview-artist'")


def test_blueprint_list_labels_contract_readiness():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for draft label test")

    html = _index()
    harness = (
        "function x(s){return String(s ?? '');}\n"
        + _extract_fn(html, "_crDraftPlanLabel")
        + "const ready = _crDraftPlanLabel({title:'The Witness Contract', has_architect_plan:true});\n"
        + "const missing = _crDraftPlanLabel({title:'Loose Blueprint', has_architect_plan:false});\n"
        + "process.stdout.write(JSON.stringify({ready, missing}));\n"
    )
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert '"The Witness Contract · contract ready"' in result.stdout
    assert '"Loose Blueprint · no contract"' in result.stdout


def test_contract_profile_and_provider_controls_are_independent_choices():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for draft orthogonality test")

    html = _index()
    harness = (
        r"""
function x(s){return String(s ?? '');}
class FakeElement {
  constructor(id) {
    this.id = id;
    this.value = '';
    this.dataset = {};
    this.listeners = {};
    this.options = [];
    this._innerHTML = '';
  }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  async dispatch(name) {
    if (this.listeners[name]) await this.listeners[name]();
  }
  set innerHTML(value) {
    this._innerHTML = String(value);
    const optionValues = [...this._innerHTML.matchAll(/<option value="([^"]*)"/g)].map(m => m[1]);
    this.options = optionValues;
    if (optionValues.length && !optionValues.includes(this.value)) this.value = optionValues[0];
  }
  get innerHTML() { return this._innerHTML; }
}
const elements = new Map();
function el(id) {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
}
global.document = { getElementById: el };
let _crActiveBlueprintId = 'bp-a';
let _crDraftProfiles = [];
const blueprints = [
  {id:'bp-b', title:'Contract B', has_architect_plan:true},
  {id:'bp-a', title:'Contract A', has_architect_plan:true}
];
const profiles = [
  {slug:'profile-p', name:'Profile P', source:'steward-authored', voice:'plain'},
  {slug:'profile-q', name:'Profile Q', source:'built-in', voice:'formal'}
];
global.get = async (url) => {
  if (url === '/api/architect/blueprints') return {blueprints};
  if (url === '/api/profiles') return {profiles};
  throw new Error(url);
};
global._crFetchSkeleton = async (id) => ({
  id,
  title: id === 'bp-a' ? 'Contract A' : 'Contract B',
  thesis: 'Thesis',
  hasPlan: true,
  planId: id === 'bp-a' ? 'plan-a' : 'plan-b',
  claims: [{n:1, claim:'Claim', evidence:['obs-1']}],
});
el('cr-draft-blueprint');
el('cr-draft-profile');
el('cr-draft-provider').value = 'null';
el('cr-draft-structure');
el('cr-draft-profile-summary');
el('cr-draft-execution-summary');
"""
        + _extract_fn(html, "_crDraftPlanLabel")
        + _extract_fn(html, "_crDraftSelectedProfile")
        + _extract_fn(html, "_crRenderDraftProfileSummary")
        + _extract_fn(html, "_crRenderDraftExecutionSummary")
        + _extract_fn(html, "_crDraftRenderStructure")
        + _extract_fn(html, "_crLoadArtistDraft")
        + r"""
(async () => {
  await _crLoadArtistDraft();
  const start = {
    contract: el('cr-draft-blueprint').value,
    profile: el('cr-draft-profile').value,
    provider: el('cr-draft-provider').value,
  };
  el('cr-draft-provider').value = 'openai';
  await el('cr-draft-provider').dispatch('change');
  const afterProvider = {
    contract: el('cr-draft-blueprint').value,
    profile: el('cr-draft-profile').value,
    provider: el('cr-draft-provider').value,
  };
  el('cr-draft-profile').value = 'profile-q';
  await el('cr-draft-profile').dispatch('change');
  const afterProfile = {
    contract: el('cr-draft-blueprint').value,
    profile: el('cr-draft-profile').value,
    provider: el('cr-draft-provider').value,
  };
  el('cr-draft-blueprint').value = 'bp-b';
  await el('cr-draft-blueprint').dispatch('change');
  const afterContract = {
    contract: el('cr-draft-blueprint').value,
    profile: el('cr-draft-profile').value,
    provider: el('cr-draft-provider').value,
  };
  process.stdout.write(JSON.stringify({start, afterProvider, afterProfile, afterContract}));
})().catch(err => { console.error(err); process.exit(1); });
"""
    )
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert '"start":{"contract":"bp-a","profile":"profile-p","provider":"null"}' in out
    assert '"afterProvider":{"contract":"bp-a","profile":"profile-p","provider":"openai"}' in out
    assert '"afterProfile":{"contract":"bp-a","profile":"profile-q","provider":"openai"}' in out
    assert '"afterContract":{"contract":"bp-b","profile":"profile-q","provider":"openai"}' in out
