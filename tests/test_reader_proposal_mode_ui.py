"""#251 v1.1 (D2): the Reader reviews a held legacy Blueprint proposal; nothing is saved without a decision.

In proposal mode "Generate Blueprint →" and the onboarding extractor return a
server-held candidate. One review surface serves both, and it shows the
proposal with its cited labels and proposing model, labelled "nothing saved
yet". It commits only through the P8 routes:
- accept exactly;
- edit, then accept, preserving every cited record;
- discard.

Stale and expired candidates are blocked with an explanation; a refused edit
keeps the steward editing. The governed onboarding path (no candidate) still
ratifies the exact preview. The real functions run under Node with a fake DOM
and fetch.
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
ACCEPT_URL = "/api/blueprint/proposals/" + ID.replace(":", "%3A") + "/accept"
DISCARD_URL = "/api/blueprint/proposals/" + ID.replace(":", "%3A") + "/discard"
BLUEPRINT = {"title": "The unasked lamp", "thesis": "The lamp records a vigil.",
             "sections": [{"claim": "The lamp burns.", "supporting_observations": ["o1"], "supporting_interpretations": ["i1"]},
                          {"claim": "The ledger is silent.", "supporting_observations": [], "supporting_interpretations": []}]}
CANDIDATE = {"schema": "hermeneia.legacy-architect-candidate/v1", "candidate_id": ID, "canonical_status": "not_persisted",
             "binding": {"view": {"observations": [{"id": "o1", "label": "OBS-1"}], "interpretations": [{"id": "i1", "label": "INTERP-0123abcd"}]}},
             "extraction": {"execution": {"model_id": "fake-model:1b"}}, "proposal": {"blueprint": BLUEPRINT, "model_explanation": None}}
EXTRACT_CANDIDATE = {"schema": "hermeneia.legacy-extract-candidate/v1", "candidate_id": ID, "binding": {},
                     "extraction": {"execution": {"model_id": "fake-extractor"}},
                     "proposal": {"blueprint": {"title": "Previewed proposal", "thesis": "What the steward reviewed.",
                                                "sections": [{"claim": "Reviewed claim.", "supporting_observations": [],
                                                              "supporting_interpretations": []}]}, "model_explanation": None}}
RECEIPT = {"id": "receipt", "acceptance": {"accepted_blueprint": BLUEPRINT}}
EXECUTED = {"provider": "fake", "interface": "openai", "model_executed": True, "placeholder": False}
REVIEW = ("function _bpReviewLabels(", "function _bpReviewHtml(", "function _bpReviewRender(", "function bpReviewOpen(",
          "function bpReviewEdit(", "function bpReviewCancelEdit(", "async function _bpReviewDecide(", "function _bpReviewRefused(",
          "async function _bpReviewAccepted(", "async function bpReviewAccept(", "async function bpReviewSaveEdit(",
          "async function bpReviewDiscard(")
ARCHITECT = REVIEW + ("async function e10GenerateBlueprint(",)
ONBOARDING = REVIEW + ("function _obExtractProposalHtml(", "async function obExtractBlueprint(", "async function obRatifyPreviewed(")


def _run(functions: tuple[str, ...], responses: list[dict], steps: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for the Reader proposal review test")
    source = INDEX.read_text()
    script = r"""
const els = {'arc-directive': {value: 'Build from the evidence.'}, 'arc-gen-provider': {value: 'fake'},
             'arc-gen-btn': {disabled: false}, 'arc-gen-status': {style: {}, textContent: '', innerHTML: ''},
             'ob-extract-text': {value: 'A source text.'}, 'ob-extract-provider': {value: 'fake'},
             'ob-extract-proposal': {style: {}, innerHTML: ''}, 'ob-extract-btn': {disabled: false, textContent: ''}};
const document = {getElementById: id => els[id] || null};
const x = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const alert = () => {};
const responses = RESPONSES;
const calls = [];
let reloads = 0;
const e10LoadArchitect = async () => { reloads += 1; };
const fetch = async (url, init) => { calls.push({url, body: JSON.parse(init.body)}); const r = responses.shift();
  return {ok: r.ok, json: async () => r.json}; };
let _obPreviewedBlueprint = null;
const _bpReview = {};
const _BP_REVIEW_TARGET = {architect: 'arc-gen-status', onboarding: 'ob-extract-proposal'};
""" + "\n".join(_extract_function(source, signature) for signature in functions) + r"""
(async () => { STEPS
  console.log(JSON.stringify({calls, reloads, architect: els['arc-gen-status'].innerHTML,
    onboarding: els['ob-extract-proposal'].innerHTML}));
})();
"""
    script = script.replace("RESPONSES", json.dumps(responses)).replace("STEPS", steps)
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_review_surface_and_its_state_live_in_the_reader():
    source = INDEX.read_text()
    assert "const _bpReview = {};" in source and "_BP_REVIEW_TARGET = {architect: 'arc-gen-status', onboarding: 'ob-extract-proposal'}" in source
    assert "obExtractBlueprint(true)" not in source


def test_a_legacy_creation_is_still_reported_as_created():
    out = _run(ARCHITECT, [{"ok": True, "json": {"blueprint_id": "b", "plan_id": "p", "title": "T", "section_count": 2}}],
               "await e10GenerateBlueprint();")
    assert "Blueprint created" in out["architect"] and out["reloads"] == 1


def test_a_held_candidate_is_inspected_as_an_unsaved_proposal():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}], "await e10GenerateBlueprint();")
    html = out["architect"]
    assert "Model proposal — nothing saved yet" in html and "Blueprint created" not in html
    assert "[OBS-1, INTERP-0123abcd]" in html and "fake-model:1b" in html and "does not make the claims true" in html
    assert "Accept exactly" in html and "Edit before accepting" in html and "Discard" in html and out["reloads"] == 0


def test_accept_commits_only_the_held_candidate():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": True, "json": RECEIPT}],
               "await e10GenerateBlueprint(); await bpReviewAccept('architect');")
    assert out["calls"][1] == {"url": ACCEPT_URL, "body": {"candidate_id": ID, "decision": "accept"}}
    assert "Saved — accepted exactly" in out["architect"] and "Accept exactly" not in out["architect"] and out["reloads"] == 1


def test_edit_and_accept_sends_the_edited_text_with_every_cited_record_kept():
    steps = ("await e10GenerateBlueprint(); bpReviewEdit('architect'); const editing = els['arc-gen-status'].innerHTML;"
             "els['bp-review-architect-title'] = {value: 'A steward title'}; els['bp-review-architect-thesis'] = {value: 'A steward thesis.'};"
             "els['bp-review-architect-claim-1'] = {value: 'The ledger records only oil.'};"
             "await bpReviewSaveEdit('architect'); els['arc-gen-status'].innerHTML = editing + '|||' + els['arc-gen-status'].innerHTML;")
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": True, "json": RECEIPT}], steps)
    editing, saved = out["architect"].split("|||")
    assert "Editing the model proposal — nothing saved yet" in editing and 'id="bp-review-architect-claim-0"' in editing
    assert "cites OBS-1, INTERP-0123abcd" in editing and "cites nothing" in editing
    assert out["calls"][1]["url"] == ACCEPT_URL and out["calls"][1]["body"] == {"candidate_id": ID, "decision": "edit_and_accept", "blueprint": {
        "title": "A steward title", "thesis": "A steward thesis.",
        "sections": [{"claim": "The lamp burns.", "supporting_observations": ["o1"], "supporting_interpretations": ["i1"]},
                     {"claim": "The ledger records only oil.", "supporting_observations": [], "supporting_interpretations": []}]}}
    assert "Saved — your edited version" in saved and "A steward title" in saved and out["reloads"] == 1


def test_cancel_editing_returns_to_the_unsaved_proposal():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}],
               "await e10GenerateBlueprint(); bpReviewEdit('architect'); bpReviewCancelEdit('architect');")
    assert "Model proposal — nothing saved yet" in out["architect"] and "textarea" not in out["architect"] and len(out["calls"]) == 1


def test_a_stale_candidate_is_blocked_and_dismissing_discards_it_on_the_server():
    stale = {"code": "STALE_CANDIDATE", "error": "inputs changed", "reasons": ["observation OBS-1 is missing, changed or ineligible"]}
    steps = ("await e10GenerateBlueprint(); await bpReviewAccept('architect'); const blocked = els['arc-gen-status'].innerHTML;"
             "await bpReviewDiscard('architect'); els['arc-gen-status'].innerHTML = blocked + '|||' + els['arc-gen-status'].innerHTML;")
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": False, "json": stale}, {"ok": True, "json": {"state": "discarded"}}], steps)
    blocked, dismissed = out["architect"].split("|||")
    assert "Not saved — this proposal can no longer be accepted" in blocked and "observation OBS-1 is missing" in blocked
    assert "Accept exactly" not in blocked and "Edit before accepting" not in blocked and "Dismiss" in blocked
    assert out["calls"][2]["url"] == DISCARD_URL and "Discarded — nothing was saved" in dismissed and out["reloads"] == 0


def test_an_expired_candidate_is_blocked_and_dismissing_makes_no_server_call():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": False, "json": {"code": "UNKNOWN_CANDIDATE", "error": "expired"}}],
               "await e10GenerateBlueprint(); await bpReviewAccept('architect'); await bpReviewDiscard('architect');")
    assert len(out["calls"]) == 2 and "Discarded — nothing was saved" in out["architect"]


def test_a_refused_edit_keeps_the_steward_editing_and_says_nothing_was_saved():
    steps = "await e10GenerateBlueprint(); bpReviewEdit('architect'); await bpReviewSaveEdit('architect');"
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": False, "json": {"code": "PROPOSAL_EDIT_INVALID", "error": "title is required"}}],
               steps)
    assert "Editing the model proposal — nothing saved yet" in out["architect"]
    assert "Not accepted: title is required. Nothing was saved." in out["architect"] and out["reloads"] == 0


def test_discard_saves_nothing():
    out = _run(ARCHITECT, [{"ok": True, "json": CANDIDATE}, {"ok": True, "json": {"state": "discarded"}}],
               "await e10GenerateBlueprint(); await bpReviewDiscard('architect');")
    assert out["calls"][1] == {"url": DISCARD_URL, "body": {"candidate_id": ID, "decision": "discard"}}
    assert "Discarded — nothing was saved" in out["architect"] and out["reloads"] == 0


def test_onboarding_reviews_its_held_candidate_with_the_same_decisions():
    preview = {"proposed_blueprint": EXTRACT_CANDIDATE["proposal"]["blueprint"], "execution": EXECUTED,
               "candidate": EXTRACT_CANDIDATE, "canonical_status": "not_persisted"}
    steps = ("await obExtractBlueprint(false); const shown = els['ob-extract-proposal'].innerHTML; await bpReviewAccept('onboarding');"
             "els['ob-extract-proposal'].innerHTML = shown + '|||' + els['ob-extract-proposal'].innerHTML;")
    out = _run(ONBOARDING, [{"ok": True, "json": preview}, {"ok": True, "json": RECEIPT}], steps)
    shown, saved = out["onboarding"].split("|||")
    assert "Model proposal — nothing saved yet" in shown and "fake-extractor" in shown and "Edit before accepting" in shown
    assert [c["url"] for c in out["calls"]] == ["/api/pipeline/extract-blueprint", ACCEPT_URL]
    assert "Saved — accepted exactly" in saved and "View in Architect" in saved


def test_onboarding_without_a_candidate_ratifies_the_exact_preview():
    preview_blueprint = EXTRACT_CANDIDATE["proposal"]["blueprint"]
    out = _run(ONBOARDING, [{"ok": True, "json": {"proposed_blueprint": preview_blueprint, "execution": EXECUTED}},
                            {"ok": True, "json": {"blueprint_id": "b", "plan_id": "p", "committed_blueprint": preview_blueprint}}],
               "const before = 0; await obExtractBlueprint(false); const shown = els['ob-extract-proposal'].innerHTML;"
               " await obRatifyPreviewed(); els['ob-extract-proposal'].innerHTML = shown + '|||' + els['ob-extract-proposal'].innerHTML;")
    shown, _saved = out["onboarding"].split("|||")
    assert "Preview — nothing saved yet." in shown
    assert [c["url"] for c in out["calls"]] == ["/api/pipeline/extract-blueprint", "/api/pipeline/ratify-blueprint"]
    assert out["calls"][1]["body"] == {"proposed_blueprint": preview_blueprint}


@pytest.mark.parametrize("decision", ["accept", "edit_and_accept", "discard"])
def test_the_request_bodies_the_reader_builds_are_accepted_by_the_real_routes(tmp_path, decision):
    """Replay the Reader's own requests for a real held candidate against the real Flask routes."""
    from urllib.parse import unquote

    import synthetic_study_lab as lab
    import test_r251_proposal_mode as server
    from hermeneia.blueprint_proposals import verify_receipt

    with lab.isolated(tmp_path):
        study = server.Study(tmp_path)
        candidate = study.generate(server.FakeArchitect(server.REPLY)).get_json()
        steps = {"accept": "await e10GenerateBlueprint(); await bpReviewAccept('architect');",
                 "edit_and_accept": ("await e10GenerateBlueprint(); bpReviewEdit('architect');"
                                     "els['bp-review-architect-title'] = {value: 'A steward title'};"
                                     "await bpReviewSaveEdit('architect');"),
                 "discard": "await e10GenerateBlueprint(); await bpReviewDiscard('architect');"}[decision]
        call = _run(ARCHITECT, [{"ok": True, "json": candidate}, {"ok": True, "json": RECEIPT}], steps)["calls"][1]
        response = study.client.post(unquote(call["url"]), json=call["body"])
        rows = study.rows("SELECT title, source FROM narrative_blueprints")
        if decision == "discard":
            assert response.status_code == 200 and rows == [] and study.count("blueprint_proposal_acceptances") == 0
            return
        receipt = response.get_json()
        assert response.status_code == 201 and study.verify(receipt["id"])["candidate_replay"] == "verified"
        expected = (("The unasked lamp", "proposal-accepted") if decision == "accept" else ("A steward title", "proposal-edited"))
        assert rows == [expected]
