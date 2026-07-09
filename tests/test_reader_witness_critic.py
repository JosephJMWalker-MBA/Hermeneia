"""Reader "Check against the voice" — the witness critic inside the Draft tab.

After previewing an Artist draft, the steward can judge it against the chosen
ExpressionProfile's witness constraints before anything is saved. These tests
guard the honest framing: it runs on the previewed draft, uses the deterministic
voice-preview endpoint, and has no generate/LLM/ratify/save path.
"""
from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name}"
    return match.group(0)


def test_check_against_voice_button_and_region_present():
    index = _index()
    assert "Check against the voice" in index
    assert "_crCheckVoiceFidelity()" in index
    assert 'id="cr-draft-critic"' in index


def test_preview_holds_the_exact_draft_for_judgment():
    index = _index()
    preview = _extract_fn(index, "_crPreviewArtistDraft")
    # The previewed text is captured so the critic judges THAT draft.
    assert "_crLastArtistDraft" in preview


def test_witness_check_uses_deterministic_endpoint_only():
    index = _index()
    region = _extract_fn(index, "_crCheckVoiceFidelity")
    assert "'/api/critic/voice-preview'" in region
    low = region.lower()
    # No generation, no acceptance, no save in the judging path.
    assert "preview-artist" not in low          # does not re-run the Artist
    assert "generate" not in low
    assert "ratif" not in low
    assert "run-artist" not in low


def test_expectations_are_labeled_for_human_judgment():
    index = _index()
    region = _extract_fn(index, "_crCheckVoiceFidelity")
    assert "judge these yourself" in region.lower() or "judge whether the witness survived" in region.lower()


def test_function_exposed():
    index = _index()
    assert "window._crCheckVoiceFidelity = _crCheckVoiceFidelity;" in index
