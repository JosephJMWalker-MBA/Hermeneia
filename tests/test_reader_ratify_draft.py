"""Reader Ratify Draft — explicit, honest ratification inside the Draft tab.

Saving is the moment a generated artifact enters the record, so it must read as
ratification, not convenience. These tests guard the framing: the button says
"Ratify & Save Draft" (not "Save"), it persists the exact previewed bytes via the
ratify endpoint without re-rendering, and both audits are shown before it.
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


def test_button_language_is_ratification_not_save():
    index = _index()
    assert "Ratify &amp; Save Draft" in index
    assert "_crRatifyDraft()" in index
    # A bare "Save" action would frame it as convenience — it must not appear.
    assert ">Save<" not in index


def test_ratify_persists_exact_previewed_bytes_no_rerender():
    index = _index()
    region = _extract_fn(index, "_crRatifyDraft")
    assert "'/api/pipeline/ratify-draft'" in region
    # Sends the exact held draft text…
    assert "_crLastArtistDraft" in region
    assert "text: d.text" in region
    low = region.lower()
    # …and never re-runs the Artist.
    assert "preview-artist" not in low
    assert "generate" not in low


def test_preview_captures_provenance_for_ratification():
    index = _index()
    preview = _extract_fn(index, "_crPreviewArtistDraft")
    # The exact bytes plus plan/provider provenance are held for a faithful save.
    assert "planId: sk.planId" in preview
    assert "provider: d.provider" in preview


def test_both_audits_shown_before_ratification():
    index = _index()
    region = _extract_fn(index, "_crRenderRatifyAudits")
    assert "_crComputeAudit" in region                  # structural / grounding
    assert "'/api/critic/voice-preview'" in region      # voice / witness verdict
    assert "Structural / grounding" in region
    assert "Voice / witness" in region


def test_ratify_function_exposed():
    index = _index()
    assert "window._crRatifyDraft = _crRatifyDraft;" in index
