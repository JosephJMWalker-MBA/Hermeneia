"""Reader Record ledger rendering.

Record is a read-only projection over persisted RenderedNarratives. These tests
protect the distinction between durable persistence, Critic evaluation, and
Steward acceptance/rejection without adding a new ledger object.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _record_script() -> str:
    html = INDEX.read_text()
    start = html.index("let _crRecordLast = null;")
    end = html.index("function _crBindBottomWorkstationControls()")
    return html[start:end]


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Record ledger UI test")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _base_harness() -> str:
    return (
        "function esc(s){return String(s ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));}\n"
        "function x(s){return esc(s);}\n"
        "const elements = {};\n"
        "function makeEl(id){\n"
        "  const el = {id, hidden:false, dataset:{}, attrs:{}, _html:'', textContent:'',\n"
        "    classList:{classes:new Set(), toggle(n,on){on ? this.classes.add(n) : this.classes.delete(n);}},\n"
        "    get innerHTML(){return this._html;}, set innerHTML(v){this._html=String(v);},\n"
        "    setAttribute(n,v){this.attrs[n]=String(v);}, getAttribute(n){return this.attrs[n];}\n"
        "  };\n"
        "  elements[id] = el; return el;\n"
        "}\n"
        "['cr-record-list','cr-record-count','cr-record-detail','cr-record-trace'].forEach(makeEl);\n"
        "const rows = ['n-accepted','n-rejected','n-pending'].map(id => ({dataset:{id}, attrs:{}, classList:{classes:new Set(), toggle(n,on){on ? this.classes.add(n) : this.classes.delete(n);}}, setAttribute(n,v){this.attrs[n]=String(v);}}));\n"
        "global.document = {getElementById(id){return elements[id] || null;}, querySelectorAll(sel){return sel === '.cr-record-row' ? rows : [];}, body:{appendChild(el){global.__copyNode = el;}}, createElement(){return {value:'', select(){global.__copySelected = this.value;}, remove(){}};}, execCommand(){global.__copied = global.__copySelected; return true;}};\n"
        "global.navigator = {clipboard:{async writeText(t){global.__copied = t;}}};\n"
        "global.window = {open(href){global.__opened = href;}};\n"
    )


def test_record_list_shows_all_steward_statuses_and_accessible_rows() -> None:
    script = (
        _base_harness()
        + _record_script()
        + """
const narratives = [
  {id:'n-accepted', provider:'Stub', created_at:'2026-08-30T21:14:00Z', narrative_status:'accepted', narrative_rationale:'Kept by steward.', profile:{name:'Field Witness', slug:'field'}, blueprint:{title:'Light and Distance'}},
  {id:'n-rejected', provider:'Claude', created_at:'2026-08-30T21:11:00Z', narrative_status:'rejected', narrative_rationale:'Rejected by steward.', profile:{name:'Plain English', slug:'plain'}, blueprint:{title:'Light and Distance'}},
  {id:'n-pending', provider:'GPT', created_at:'2026-08-30T21:10:00Z', narrative_status:'pending', narrative_rationale:null, profile:null, blueprint:{title:'Open Record'}},
];
global.get = async url => ({narratives});
_crLoadRecordLedger().then(() => {
  const html = elements['cr-record-list'].innerHTML;
  process.stdout.write(JSON.stringify({
    count: elements['cr-record-count'].textContent,
    hasButtonRows: (html.match(/<button class="cr-record-row"/g) || []).length,
    accepted: html.includes('Accepted'),
    rejected: html.includes('Rejected'),
    pending: html.includes('Pending'),
    profile: html.includes('Field Witness · field'),
    provider: html.includes('Claude'),
    noRejectedFilter: html.includes('n-rejected')
  }));
});
"""
    )
    state = _run_node(script)

    assert state == {
        "count": "· 3 records · 1 accepted · 1 pending · 1 rejected",
        "hasButtonRows": 3,
        "accepted": True,
        "rejected": True,
        "pending": True,
        "profile": True,
        "provider": True,
        "noRejectedFilter": True,
    }


def test_record_detail_keeps_steward_and_critic_independent_and_exact_text_copy() -> None:
    exact = "Exact saved text\nwith punctuation, Unicode ✦, and line breaks."
    script = (
        _base_harness()
        + f"const exactText = {json.dumps(exact)};\n"
        + _record_script()
        + """
const summaries = [
  {id:'n-rejected', provider:'Stub', created_at:'2026-08-30T21:14:00Z', narrative_status:'rejected', narrative_rationale:'Steward rejected despite Critic approval.', profile:{name:'Field Witness', slug:'field'}, blueprint:{title:'Light and Distance'}},
  {id:'n-accepted', provider:'Stub', created_at:'2026-08-30T21:15:00Z', narrative_status:'accepted', narrative_rationale:'Steward accepted with known caveats.', profile:{name:'Plain English', slug:'plain'}, blueprint:{title:'Light and Distance'}},
];
const details = {
  'n-rejected': {rendered_narrative:{id:'n-rejected', provider:'Stub', text:exactText, created_at:'2026-08-30T21:14:00Z', execution_config:{provider:'Stub', model_id:'local-test', execution_fingerprint:'abcdef1234567890'}}, blueprint:{id:'bp1', title:'Light and Distance', thesis:'Distance matters.'}, architect_plan:{id:'plan1', title:'Semantic Contract'}, profile:{id:'prof1', name:'Field Witness', slug:'field', language:'en', audience:'steward'}, validation_report:{id:'vr1', approved:true, semantic_fidelity:99.5, required_terms_missing:[], unsupported_claims:[]}, surfaces:{lineage:'/api/lineage/rendered_narrative/n-rejected', semantic_contract:'/api/fidelity/bp1/field?narrative=n-rejected'}},
  'n-accepted': {rendered_narrative:{id:'n-accepted', provider:'Stub', text:exactText, created_at:'2026-08-30T21:15:00Z', execution_config:{provider:'Stub'}}, blueprint:{id:'bp1', title:'Light and Distance', thesis:'Distance matters.'}, architect_plan:{id:'plan1', title:'Semantic Contract'}, profile:{id:'prof2', name:'Plain English', slug:'plain', language:'en', audience:'reader'}, validation_report:{id:'vr2', approved:false, semantic_fidelity:40, required_terms_missing:['distance'], unsupported_claims:['unsupported leap']}, surfaces:{lineage:'/api/lineage/rendered_narrative/n-accepted'}},
};
global.get = async url => {
  if (url === '/api/reader/narratives') return {narratives:summaries};
  return details[url.split('/').pop()];
};
(async () => {
  await _crLoadRecordLedger();
  await _crShowRecord('n-rejected');
  const rejectedHtml = elements['cr-record-detail'].innerHTML;
  await _crCopyRecordText();
  await _crShowRecord('n-accepted');
  const acceptedHtml = elements['cr-record-detail'].innerHTML;
  process.stdout.write(JSON.stringify({
    rejectedShowsSteward: rejectedHtml.includes('Steward decision') && rejectedHtml.includes('Rejected'),
    rejectedShowsCritic: rejectedHtml.includes('Critic verdict') && rejectedHtml.includes('Approved'),
    acceptedShowsSteward: acceptedHtml.includes('Steward decision') && acceptedHtml.includes('Accepted'),
    acceptedShowsCritic: acceptedHtml.includes('Critic verdict') && acceptedHtml.includes('Not approved'),
    lineage: rejectedHtml.includes('Blueprint') && rejectedHtml.includes('ArchitectPlan · semantic contract') && rejectedHtml.includes('Expression Profile') && rejectedHtml.includes('Execution') && rejectedHtml.includes('RenderedNarrative'),
    executionFromRecord: rejectedHtml.includes('Model local-test') && rejectedHtml.includes('Config abcdef1234…'),
    rationale: rejectedHtml.includes('Steward rejected despite Critic approval.'),
    exactTextVisible: rejectedHtml.includes('Exact saved text') && rejectedHtml.includes('Unicode ✦'),
    copied: global.__copied
  }));
})();
"""
    )
    state = _run_node(script)

    assert state["rejectedShowsSteward"] is True
    assert state["rejectedShowsCritic"] is True
    assert state["acceptedShowsSteward"] is True
    assert state["acceptedShowsCritic"] is True
    assert state["lineage"] is True
    assert state["executionFromRecord"] is True
    assert state["rationale"] is True
    assert state["exactTextVisible"] is True
    assert state["copied"] == exact


def test_record_stale_detail_response_cannot_replace_newer_selection() -> None:
    script = (
        _base_harness()
        + _record_script()
        + """
_crRecordSummaries = {
  A:{id:'A', narrative_status:'accepted', narrative_rationale:'A rationale'},
  B:{id:'B', narrative_status:'pending', narrative_rationale:null}
};
let resolveA, resolveB;
global.get = url => new Promise(resolve => {
  if (url.endsWith('/A')) resolveA = resolve;
  if (url.endsWith('/B')) resolveB = resolve;
});
const detail = id => ({rendered_narrative:{id, provider:'Stub', text:`Text ${id}`, created_at:'2026-08-30T21:14:00Z', execution_config:{provider:'Stub'}}, blueprint:{id:`bp-${id}`, title:`Blueprint ${id}`, thesis:''}, architect_plan:{id:`plan-${id}`, title:`Plan ${id}`}, profile:{name:'Profile', slug:'profile'}, validation_report:null, surfaces:{lineage:`/lineage/${id}`}});
(async () => {
  const first = _crShowRecord('A');
  const second = _crShowRecord('B');
  resolveB(detail('B'));
  await second;
  const afterB = elements['cr-record-detail'].innerHTML;
  resolveA(detail('A'));
  await first;
  const afterLateA = elements['cr-record-detail'].innerHTML;
  process.stdout.write(JSON.stringify({
    afterBHasB: afterB.includes('Blueprint B'),
    lateAStillB: afterLateA.includes('Blueprint B') && !afterLateA.includes('Blueprint A')
  }));
})();
"""
    )
    state = _run_node(script)

    assert state == {"afterBHasB": True, "lateAStillB": True}


def test_workspace_change_clears_record_state_and_detail() -> None:
    script = (
        _base_harness()
        + _record_script()
        + """
_crRecordLast = {id:'old', text:'old text', lineageHref:'/old'};
_crRecordSummaries = {old:{id:'old'}};
elements['cr-record-count'].textContent = '· 1 records';
elements['cr-record-list'].innerHTML = '<button class="cr-record-row">Old</button>';
elements['cr-record-detail'].innerHTML = '<div>Old workspace narrative</div>';
_crResetRecordLedgerStateForWorkspaceChange();
process.stdout.write(JSON.stringify({
  count: elements['cr-record-count'].textContent,
  list: elements['cr-record-list'].innerHTML,
  detailCleared: elements['cr-record-detail'].innerHTML.includes('Select a saved narrative record'),
  lastCleared: _crRecordLast === null,
  summariesCleared: Object.keys(_crRecordSummaries).length === 0
}));
"""
    )
    state = _run_node(script)

    assert state == {
        "count": "",
        "list": "",
        "detailCleared": True,
        "lastCleared": True,
        "summariesCleared": True,
    }
