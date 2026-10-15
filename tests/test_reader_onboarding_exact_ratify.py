"""#251 R5/R6: onboarding "Ratify & Save" commits the exact previewed Blueprint, never a new extraction.

The onboarding preview keeps the proposal it displayed. Ratification posts
exactly that object to the human approval boundary
(/api/pipeline/ratify-blueprint, no provider call) instead of re-running
extract-blueprint with save:true. A placeholder (no model ran) is shown as
such and cannot be ratified from this panel. The real functions run under
Node with a fake DOM and fetch.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_evidence_board_ui import _extract_function

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
PREVIEW = {"title": "Previewed proposal", "thesis": "What the steward reviewed.", "sections": [{"claim": "Reviewed claim."}]}


def _run(responses: list[dict], steps: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for the onboarding ratify test")
    source = INDEX.read_text()
    functions = "\n".join(_extract_function(source, sig) for sig in (
        "function _obExtractProposalHtml(", "async function obExtractBlueprint(", "async function obRatifyPreviewed("))
    script = r"""
const els = {'ob-extract-text': {value: 'A source text.'}, 'ob-extract-provider': {value: 'fake'},
             'ob-extract-proposal': {style: {}, innerHTML: ''}, 'ob-extract-btn': {disabled: false, textContent: ''}};
const document = {getElementById: id => els[id] || null};
const x = s => String(s ?? '');
const alert = () => {};
const responses = RESPONSES;
const calls = [];
const fetch = async (url, init) => { calls.push({url, body: JSON.parse(init.body)}); const r = responses.shift();
  return {ok: r.ok, json: async () => r.json}; };
let _obPreviewedBlueprint = null;
""" + functions + r"""
(async () => { STEPS
  console.log(JSON.stringify({calls, html: els['ob-extract-proposal'].innerHTML, held: _obPreviewedBlueprint}));
})();
"""
    script = script.replace("RESPONSES", json.dumps(responses)).replace("STEPS", steps)
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_ratify_and_save_posts_the_exact_preview_to_the_approval_boundary():
    executed = {"provider": "fake", "interface": "openai", "model_executed": True, "placeholder": False}
    out = _run([{"ok": True, "json": {"proposed_blueprint": PREVIEW, "execution": executed}},
                {"ok": True, "json": {"blueprint_id": "b", "plan_id": "p", "committed_blueprint": PREVIEW}}],
               "await obExtractBlueprint(false); await obRatifyPreviewed();")
    assert [c["url"] for c in out["calls"]] == ["/api/pipeline/extract-blueprint", "/api/pipeline/ratify-blueprint"]
    assert out["calls"][0]["body"] == {"text": "A source text.", "provider": "fake", "save": False}
    assert out["calls"][1]["body"] == {"proposed_blueprint": PREVIEW}
    assert "saved" in out["html"] and "Previewed proposal" in out["html"] and out["held"] is None


def test_a_placeholder_is_shown_as_such_and_cannot_be_ratified_here():
    placeholder = {"provider": "null", "interface": "placeholder", "model_executed": False, "placeholder": True}
    canned = {"title": "Extracted Blueprint", "thesis": "The document establishes a central claim.", "sections": []}
    out = _run([{"ok": True, "json": {"proposed_blueprint": canned, "execution": placeholder}}],
               "await obExtractBlueprint(false); await obRatifyPreviewed();")
    assert [c["url"] for c in out["calls"]] == ["/api/pipeline/extract-blueprint"]
    assert "No model ran" in out["html"] and "obRatifyPreviewed()" not in out["html"] and out["held"] is None


def test_a_refused_ratification_keeps_the_reviewed_preview():
    executed = {"provider": "fake", "interface": "openai", "model_executed": True, "placeholder": False}
    out = _run([{"ok": True, "json": {"proposed_blueprint": PREVIEW, "execution": executed}},
                {"ok": False, "json": {"error": "Scope refused"}}],
               "await obExtractBlueprint(false); await obRatifyPreviewed();")
    assert "Scope refused" in out["html"] and "obRatifyPreviewed()" in out["html"] and out["held"] == PREVIEW


def test_onboarding_never_saves_by_re_running_extraction():
    assert "obExtractBlueprint(true)" not in INDEX.read_text()
