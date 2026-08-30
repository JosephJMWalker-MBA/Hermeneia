"""Reader Expression draft view — labeled Artist draft preview (no save, no accept).

A nested Expression workstation view renders Structure Preview + ExpressionProfile
into a clearly-labeled draft *preview*. This is the danger point where the app
could collapse into "AI writes essay", so these tests guard the honest framing:
the button previews (never "generates a final essay"), the output is labeled as
an unsaved preview, and the code path has no save/accept action.
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
    assert 'id="cr-draft-blueprint"' in index      # which Structure Preview
    assert 'title="Which Structure Preview"' in index
    assert 'id="cr-draft-profile"' in index        # which ExpressionProfile (voice)
    assert 'id="cr-draft-provider"' in index        # provider (stub default)
    assert "'/api/profiles'" in index


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
