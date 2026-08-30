"""Reader Expression voice view — capture witness constraints as an ExpressionProfile (#93).

A nested Expression workstation view lets the steward capture the
witness the future draft must not erase — voice, audience, non-negotiables,
phrases to preserve, phrases/styles to avoid, critic expectations — and save it
as a real ExpressionProfile. Design-first: no drafting, no LLM, no voice
critique here. These tests guard the wiring, the create-endpoint use, and the
directive-composition logic.
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


def test_voice_tab_and_panel_present():
    index = _index()
    assert 'id="cr-bottom-tab-voice"' not in index
    assert 'id="cr-bottom-resource-expression"' in index
    assert 'data-workstation-resource="expression"' in index
    assert 'id="cr-expression-subtab-voice"' in index
    assert 'data-workstation-submode="voice"' in index
    assert 'aria-controls="cr-voice-profile"' in index
    assert "_crOpenBottomWorkstation('voice')" in index
    assert 'id="cr-voice-profile"' in index
    assert 'id="cr-voice-profile" hidden' in index
    assert "Expression · Voice" in index


def test_voice_is_a_workstation_mode_not_a_separate_drawer():
    index = _index()
    assert "voice: document.getElementById('cr-voice-profile')" in index
    assert "else if (mode === 'voice')" in index
    assert "['cr-bottom-resource-expression', () => _crOpenBottomWorkstation('voice')]" in index
    assert "['cr-expression-subtab-voice', () => _crOpenBottomWorkstation('voice')]" in index
    assert "if (mode === 'voice' || mode === 'draft') return 'expression';" in index


def test_voice_captures_all_witness_fields():
    index = _index()
    for field_id in ("cr-voice-voice", "cr-voice-audience", "cr-voice-nonneg",
                     "cr-voice-preserve", "cr-voice-avoid", "cr-voice-critic"):
        assert f'id="{field_id}"' in index, field_id
    # The example the user named is offered as guidance.
    assert "do not turn this into consultant language" in index


def test_voice_saves_via_create_endpoint_no_llm():
    index = _index()
    region = _extract_fn(index, "_crSaveVoiceProfile")
    assert "'/api/profiles'" in region
    assert "method: 'POST'" in region
    # Capture only — never generates or critiques prose.
    save_lower = region.lower()
    assert "/api/architect/generate" not in save_lower
    assert "companion/ask" not in save_lower


def test_voice_functions_exposed():
    index = _index()
    assert "window._crLoadVoiceProfile = _crLoadVoiceProfile;" in index
    assert "window._crSaveVoiceProfile = _crSaveVoiceProfile;" in index


def test_compose_voice_directive_emits_labeled_witness_sections():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Voice directive composition test")

    html = _index()
    harness = (
        _extract_fn(html, "_crVoiceLines")
        + _extract_fn(html, "_crComposeVoiceDirective")
        + "const out = _crComposeVoiceDirective({"
        "  voice:'first-person, testimonial',"
        "  audience:'a reader who was not in the room',"
        "  nonNegotiables:'Keep it in the witness\\u2019s own frame.',"
        "  preserve:'\"I only know what I saw\"\\nthe hesitation before naming it',"
        "  avoid:'do not turn this into consultant language\\nno \"stakeholders\"'"
        "});\n"
        "process.stdout.write(out);\n"
    )
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "Voice: first-person, testimonial" in out
    assert "Audience: a reader who was not in the room" in out
    assert "Non-negotiables:" in out
    assert "Preserve these phrases and moves" in out
    assert "Avoid — never do this:" in out
    assert "- do not turn this into consultant language" in out
    assert '- "I only know what I saw"' in out
