"""Reader Critic Preview (skeleton → structural audit).

A sixth tab in the Reader's bottom workstation audits the current Blueprint
skeleton BEFORE any prose exists: thesis preservation, governing-question
alignment, evidence grounding, unsupported claims, thesis drift, and next-repair
actions. It is deterministic and client-side — every signal is a transparent
structural check (evidence links / shared terms), never a hidden AI judgment. No
Artist call, no LLM, no generated prose (that is #93 territory, later). These
tests guard the wiring, endpoint reuse, and the audit computation itself.
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
    match = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name}"
    return match.group(0)


# ── Static wiring ────────────────────────────────────────────────────────

def test_critic_tab_and_panel_present():
    index = _index()
    assert 'id="cr-bottom-tab-critic"' in index
    assert 'data-workstation-mode="critic"' in index
    assert 'aria-controls="cr-critic-audit"' in index
    assert "_crToggleBottomWorkstation('critic')" in index
    assert 'id="cr-critic-audit"' in index
    assert 'id="cr-critic-audit" hidden' in index


def test_critic_is_a_workstation_mode_not_a_separate_drawer():
    index = _index()
    assert "critic: document.getElementById('cr-critic-audit')" in index
    assert "else if (mode === 'critic')" in index
    assert "['cr-bottom-tab-critic', () => _crToggleBottomWorkstation('critic')]" in index


def test_critic_reuses_existing_endpoints_without_new_routes():
    index = _index()
    assert "'/api/architect/blueprints'" in index
    # Shares one skeleton-assembly path with Render.
    assert "_crFetchSkeleton" in index
    app = APP.read_text()
    assert app.count('@app.route("/api/architect/blueprints"') == 1
    assert app.count('@app.route("/api/architect/blueprints/<blueprint_id>"') == 1


def test_critic_is_not_a_prose_generator():
    index = _index()
    region = _extract_fn(index, "_crAuditBlueprint") + _extract_fn(index, "_crComputeAudit")
    assert "/api/architect/generate" not in region
    assert "artist" not in region.lower()


def test_critic_functions_exposed():
    index = _index()
    assert "window._crLoadCriticAudit = _crLoadCriticAudit;" in index
    assert "window._crAuditBlueprint = _crAuditBlueprint;" in index


# ── Behavioral: the audit computation is deterministic ───────────────────

def test_compute_audit_scores_grounding_drift_and_thesis():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Critic audit computation test")

    html = _index()
    stopwords = re.search(r"const _CR_AUDIT_STOPWORDS = new Set\(\[.*?\]\);", html, re.S)
    assert stopwords, "could not extract _CR_AUDIT_STOPWORDS"

    harness = (
        stopwords.group(0) + "\n"
        + _extract_fn(html, "_crSignificantTerms")
        + _extract_fn(html, "_crTermOverlap")
        + _extract_fn(html, "_crComputeAudit")
        + "const skeleton = {title:'T', thesis:'Gatsby performs desire as social theater',"
        "  claims:["
        "    {n:1, claim:'Gatsby stages desire through theatrical performance',"
        "     evidence:[{kind:'observation',text:'x',loc:'p.1'}]},"
        "    {n:2, claim:'The parties function as social theater', evidence:[]},"
        "    {n:3, claim:'Weather patterns affect crop yields', evidence:[]}"
        "  ]};\n"
        "const audit = _crComputeAudit(skeleton, 'How does Gatsby perform desire as social theater?');\n"
        "process.stdout.write(JSON.stringify(audit));\n"
    )
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    audit = json.loads(result.stdout)

    assert audit["total"] == 3
    assert audit["supported"] == 1                 # only claim 1 has evidence
    assert audit["unsupported"] == [2, 3]
    assert audit["drift"] == [3]                    # crop/weather claim shares no thesis term
    assert audit["connected"] == 2
    assert audit["thesisPreservation"] == "partial"  # 2/3 connect
    assert audit["governingAlignment"]["level"] == "strong"
    # An actionable next step is always produced.
    assert any("Attach evidence" in a for a in audit["readerActions"])
    assert any("#3" in a for a in audit["readerActions"])


def test_compute_audit_all_grounded_and_on_thesis_is_clean():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")

    html = _index()
    stopwords = re.search(r"const _CR_AUDIT_STOPWORDS = new Set\(\[.*?\]\);", html, re.S)
    harness = (
        stopwords.group(0) + "\n"
        + _extract_fn(html, "_crSignificantTerms")
        + _extract_fn(html, "_crTermOverlap")
        + _extract_fn(html, "_crComputeAudit")
        + "const skeleton = {title:'T', thesis:'desire operates as social theater',"
        "  claims:[{n:1, claim:'desire operates as social theater everywhere',"
        "     evidence:[{kind:'observation',text:'x'}]}]};\n"
        "const audit = _crComputeAudit(skeleton, 'how does desire operate as social theater');\n"
        "process.stdout.write(JSON.stringify(audit));\n"
    )
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    audit = json.loads(result.stdout)
    assert audit["supported"] == 1 and audit["total"] == 1
    assert audit["unsupported"] == []
    assert audit["drift"] == []
    assert audit["thesisPreservation"] == "strong"
    assert any("draft" in a.lower() for a in audit["readerActions"])
