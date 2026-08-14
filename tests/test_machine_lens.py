"""
Machine Auto-Highlight Lens tests (issue #12).

The lens shows current-page machine observations inline on the book page,
non-destructively and visibly distinct from the reader's own highlights.
The machine may point; the human decides what enters the record. These tests
exercise the actual client rendering logic (`_crRenderTextWithHighlights` and
`_crMachineHighlightClass`) by extracting them from index.html and running
them under Node, so the matching, precedence, and state styling are verified
behaviourally rather than by string presence alone.

Covers:
  - lens on wraps matching current-page machine text in machine-highlight markup
  - lens off (no machine observations passed) produces no machine markup
  - user highlights stay distinct and win precedence on an overlapping span
  - rejected observations are hidden (never drawn as attention)
  - approved = confirmed style, deferred = subtle style (distinct classes)
  - an observation whose text is not found verbatim is safely not drawn
Plus static guards that the toggle, persistence, and current-page scoping ship.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_fn(html: str, name: str) -> str:
    """Pull a top-level function definition (closing brace in column 0)."""
    m = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert m, f"could not extract function {name} from index.html"
    return m.group(0)


def _run_lens(text, highlights, machine_obs):
    """Run the extracted render function in Node and return the HTML string."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for behavioural lens test")
    html = INDEX.read_text()
    harness = (
        "function x(s){return String(s==null?'':s)"
        ".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}\n"
        "function _crHighlightTags(h){return (h&&h.tags)||[];}\n"
        "const _CR_READER_SPAN_LOCATOR_PREFIX='reader-span:v1:';\n"
        + _extract_fn(html, "_crStringList")
        + _extract_fn(html, "_crUniqueStringList")
        + _extract_fn(html, "_crInlineHighlightClass")
        + _extract_fn(html, "_crDecodeReaderSpanLocator")
        + _extract_fn(html, "_crFiniteNumber")
        + _extract_fn(html, "_crTextOffset")
        + _extract_fn(html, "_crHasAnyValue")
        + _extract_fn(html, "_crBlockMatchesSpanPoint")
        + _extract_fn(html, "_crSpanRangeForBlock")
        + _extract_fn(html, "_crPushNonOverlappingRange")
        + _extract_fn(html, "_crRenderTextWithHighlights")
        + _extract_fn(html, "_crMachineHighlightClass")
        + "const [t,h,m]=JSON.parse(process.argv[1]);\n"
        "process.stdout.write(_crRenderTextWithHighlights(t,h,m));\n"
    )
    payload = json.dumps([text, highlights, machine_obs])
    out = subprocess.run(
        [node, "-e", harness, "--", payload],
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


TEXT = "Gatsby believed in the green light, the orgastic future that recedes."


def test_lens_on_wraps_matching_machine_text():
    obs = [{"id": "o1", "page": 1, "raw_text": "green light", "review_status": None}]
    html = _run_lens(TEXT, [], obs)
    assert "cr-machine-hl" in html
    assert 'data-machine-obs="o1"' in html
    assert ">green light<" in html


def test_lens_off_produces_no_machine_markup():
    # Lens off is modelled as no machine observations passed to the renderer.
    html = _run_lens(TEXT, [], [])
    assert "cr-machine-hl" not in html
    assert html  # text still rendered


def test_user_highlight_stays_distinct_and_wins_overlap():
    user = [{"id": "u1", "page": 1, "selected_text": "green light", "status": "saved"}]
    obs = [{"id": "o1", "page": 1, "raw_text": "green light", "review_status": None}]
    html = _run_lens(TEXT, user, obs)
    # The overlapping span is the user's mark, not a machine highlight.
    assert "cr-inline-highlight" in html
    assert 'data-highlight-id="u1"' in html
    assert "cr-machine-hl" not in html


def test_rejected_observation_is_hidden():
    obs = [{"id": "o1", "page": 1, "raw_text": "green light", "review_status": "rejected"}]
    html = _run_lens(TEXT, [], obs)
    assert "cr-machine-hl" not in html, "rejected observations must not appear as attention"


def test_approved_and_deferred_states_are_distinct():
    approved = _run_lens(TEXT, [], [{"id": "o1", "page": 1, "raw_text": "green light", "review_status": "approved"}])
    deferred = _run_lens(TEXT, [], [{"id": "o2", "page": 1, "raw_text": "green light", "review_status": "unsure"}])
    assert "cr-machine-approved" in approved
    assert "cr-machine-deferred" not in approved
    assert "cr-machine-deferred" in deferred
    assert "cr-machine-approved" not in deferred


def test_unmatched_observation_is_safely_not_drawn():
    obs = [{"id": "o1", "page": 1, "raw_text": "a phrase that is not on this page", "review_status": None}]
    html = _run_lens(TEXT, [], obs)
    assert "cr-machine-hl" not in html


def test_lens_toggle_and_scope_ship_in_index():
    html = INDEX.read_text()
    # Visible toggle near the brief.
    assert 'id="cr-lens-toggle"' in html
    assert "Machine highlights" in html
    assert "_crToggleLens()" in html
    # Non-destructive re-render + persistence + current-page-only scope.
    assert "_crApplyLens" in html
    assert "hermeneia_machine_lens" in html
    assert "Number(o.page) === Number(_crPage)" in html
    # Distinct machine styling exists and differs from user highlight styling.
    assert ".cr-machine-hl" in html
    assert ".cr-machine-approved" in html and ".cr-machine-deferred" in html
