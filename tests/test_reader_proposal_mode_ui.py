"""#251 v1.1: the Reader shows a held legacy candidate as a proposal and accepts it exactly.

In `proposal` mode "Generate Blueprint →" receives a server-held candidate,
not a created Blueprint. The Architect panel must say that nothing is saved,
show the proposal with its cited labels, and commit it only through the P8
accept route; Discard saves nothing. Onboarding "Ratify & Save" accepts the
held candidate behind its preview when there is one, and otherwise ratifies
the exact preview (governed). The real functions run under Node with a fake
DOM and fetch.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_evidence_board_ui import _extract_function

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
ID = "blueprint-proposal-candidate:sha256:" + "a" * 64
BLUEPRINT = {"title": "The unasked lamp", "thesis": "The lamp records a vigil.",
             "sections": [{"claim": "The lamp burns.", "supporting_observations": ["o1"], "supporting_interpretations": ["i1"]}]}
CANDIDATE = {"schema": "hermeneia.legacy-architect-candidate/v1", "candidate_id": ID, "canonical_status": "not_persisted",
             "binding": {"view": {"observations": [{"id": "o1", "label": "OBS-1"}], "interpretations": [{"id": "i1", "label": "INTERP-0123abcd"}]}},
             "extraction": {"execution": {"model_id": "fake-model:1b"}}, "proposal": {"blueprint": BLUEPRINT, "model_explanation": None}}
RECEIPT = {"id": "receipt", "acceptance": {"accepted_blueprint": BLUEPRINT}}
PREVIEW = {"title": "Previewed proposal", "thesis": "What the steward reviewed.", "sections": [{"claim": "Reviewed claim."}]}
EXECUTED = {"provider": "fake", "interface": "openai", "model_executed": True, "placeholder": False}


def _run(functions: tuple[str, ...], responses: list[dict], steps: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for the Reader proposal-mode test")
    source = INDEX.read_text()
    script = r"""
const els = {'arc-directive': {value: 'Build from the evidence.'}, 'arc-gen-provider': {value: 'fake'},
             'arc-gen-btn': {disabled: false}, 'arc-gen-status': {textContent: '', innerHTML: ''},
             'ob-extract-text': {value: 'A source text.'}, 'ob-extract-provider': {value: 'fake'},
             'ob-extract-proposal': {style: {}, innerHTML: ''}, 'ob-extract-btn': {disabled: false, textContent: ''}};
const document = {getElementById: id => els[id] || null};
const x = s => String(s ?? '');
const alert = () => {};
const responses = RESPONSES;
const calls = [];
let reloads = 0;
const e10LoadArchitect = async () => { reloads += 1; };
const fetch = async (url, init) => { calls.push({url, body: JSON.parse(init.body)}); const r = responses.shift();
  return {ok: r.ok, json: async () => r.json}; };
let _obPreviewedBlueprint = null;
let _obPreviewedCandidateId = null;
let _e10ArchitectCandidate = null;
""" + "\n".join(_extract_function(source, signature) for signature in functions) + r"""
(async () => { STEPS
  const status = els['arc-gen-status'];
  console.log(JSON.stringify({calls, reloads, status: status.innerHTML || status.textContent,
    onboarding: els['ob-extract-proposal'].innerHTML, held: _e10ArchitectCandidate && _e10ArchitectCandidate.candidate_id}));
})();
"""
    script = script.replace("RESPONSES", json.dumps(responses)).replace("STEPS", steps)
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


ARCHITECT = ("function _e10ArchitectProposalHtml(", "async function e10AcceptArchitectProposal(",
             "async function e10DiscardArchitectProposal(", "async function e10GenerateBlueprint(")
ONBOARDING = ("function _obExtractProposalHtml(", "async function obExtractBlueprint(", "async function obRatifyPreviewed(")


def test_a_legacy_creation_is_still_reported_as_created():
    out = _run(ARCHITECT, [{"ok": True, "json": {"blueprint_id": "b", "plan_id": "p", "title": "T", "section_count": 2}}],
               "await e10GenerateBlueprint();")
    assert "Blueprint created" in out["status"] and out["reloads"] == 1 and out["held"] is None


def test_a_held_candidate_is_shown_as_a_proposal_never_as_created():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}], "await e10GenerateBlueprint();")
    assert "nothing saved yet" in out["status"] and "Blueprint created" not in out["status"]
    assert "[OBS-1, INTERP-0123abcd]" in out["status"] and "fake-model:1b" in out["status"]
    assert out["reloads"] == 0 and out["held"] == ID and [c["url"] for c in out["calls"]] == ["/api/architect/generate"]


def test_accept_commits_only_the_held_candidate_through_the_p8_route():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": True, "json": RECEIPT}],
               "await e10GenerateBlueprint(); await e10AcceptArchitectProposal();")
    accept = out["calls"][1]
    assert accept["url"] == "/api/blueprint/proposals/" + ID.replace(":", "%3A") + "/accept"
    assert accept["body"] == {"decision": "accept", "candidate_id": ID}
    assert "Accepted" in out["status"] and out["reloads"] == 1 and out["held"] is None


def test_a_refused_acceptance_keeps_the_proposal_under_review():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": False, "json": {"code": "STALE_CANDIDATE", "error": "inputs changed"}}],
               "await e10GenerateBlueprint(); await e10AcceptArchitectProposal();")
    assert "Not accepted: inputs changed" in out["status"] and "nothing saved yet" in out["status"] and out["held"] == ID


def test_discard_saves_nothing():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": True, "json": {"state": "discarded"}}],
               "await e10GenerateBlueprint(); await e10DiscardArchitectProposal();")
    assert out["calls"][1]["url"].endswith("/discard") and out["calls"][1]["body"] == {"decision": "discard", "candidate_id": ID}
    assert out["status"] == "Proposal discarded; nothing was saved." and out["reloads"] == 0 and out["held"] is None


def test_onboarding_accepts_the_held_candidate_behind_its_preview():
    preview = {"proposed_blueprint": PREVIEW, "execution": EXECUTED, "candidate": {"candidate_id": ID}, "canonical_status": "not_persisted"}
    out = _run(ONBOARDING, [{"ok": True, "json": preview}, {"ok": True, "json": {"acceptance": {"accepted_blueprint": PREVIEW}}}],
               "await obExtractBlueprint(false); await obRatifyPreviewed();")
    assert [c["url"] for c in out["calls"]] == ["/api/pipeline/extract-blueprint", "/api/blueprint/proposals/" + ID.replace(":", "%3A") + "/accept"]
    assert out["calls"][1]["body"] == {"decision": "accept", "candidate_id": ID}
    assert "saved" in out["onboarding"] and "Previewed proposal" in out["onboarding"]


def test_onboarding_without_a_candidate_ratifies_the_exact_preview():
    out = _run(ONBOARDING, [{"ok": True, "json": {"proposed_blueprint": PREVIEW, "execution": EXECUTED}},
                            {"ok": True, "json": {"blueprint_id": "b", "plan_id": "p", "committed_blueprint": PREVIEW}}],
               "await obExtractBlueprint(false); await obRatifyPreviewed();")
    assert [c["url"] for c in out["calls"]] == ["/api/pipeline/extract-blueprint", "/api/pipeline/ratify-blueprint"]
    assert out["calls"][1]["body"] == {"proposed_blueprint": PREVIEW}
