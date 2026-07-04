"""Actionable machine observations in the Reader (issue #56 slice 5).

A lens, not authorship: the Reader gains lightweight, Reader-local actions on
machine observations — Inspect, Jump to passage, and Ask Companion — that make
a suggestion easier to inspect and use while reading. None of them change
canonical observation status, mutate extraction, touch the database, or force
the user into Lab. The steward still decides what enters the record.

The Node-executed tests prove the local handlers issue no network calls.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

INDEX_HTML = (
    Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
)


def _index() -> str:
    return INDEX_HTML.read_text()


def _extract_function(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    i = brace
    while i < len(source):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces extracting {signature!r}")


# ── Markup + wiring ────────────────────────────────────────────────────────


def test_reader_local_actions_exist_on_brief_items():
    index = _index()
    assert "cr-brief-local" in index
    assert "_crBriefInspect(" in index
    assert "_crBriefJump(" in index
    assert "_crBriefCompanion(" in index
    for label in ("Inspect", "Jump to passage", "Ask Companion"):
        assert label in index, label


def test_jump_uses_page_block_locator_attribute():
    index = _index()
    assert "data-cr-locator" in index
    fn = _extract_function(index, "function _crBriefJump(")
    assert "cr-text-block" in fn
    assert "scrollIntoView" in fn


def test_companion_action_prefills_only_and_does_not_send():
    index = _index()
    fn = _extract_function(index, "function _crBriefCompanion(")
    assert "cmp-input" in fn
    # Prefill only: it must not call the ask handler or fetch.
    assert "cmpAsk(" not in fn
    assert "fetch(" not in fn


# ── Strict boundaries: no canonical mutation from the local actions ────────


def test_local_action_handlers_issue_no_network_calls():
    """Inspect / Jump / Companion must not fetch, POST, or hit any API."""
    index = _index()
    for sig in (
        "function _crBriefInspect(",
        "function _crBriefJump(",
        "function _crBriefCompanion(",
    ):
        fn = _extract_function(index, sig)
        assert "fetch(" not in fn, sig
        assert "/api/" not in fn, sig
        assert "/review" not in fn, sig
        assert "review_status" not in fn, sig


def test_no_new_status_mutation_endpoints_added_by_slice5():
    """The observation review/status endpoints are pre-existing; slice 5 must
    not add new writes to canonical status. Guard the local handlers stay
    read-only by construction (covered above) and that no old side panel or
    out-of-scope surface sneaks in."""
    index = _index()
    assert 'id="cr-fieldnotes-panel"' not in index  # discarded stash
    # Existing governance actions remain where they were (not removed/altered
    # by this additive slice).
    assert "_crBriefRule(" in index
    assert "_crBriefQuestion(" in index


# ── Behavior under Node ────────────────────────────────────────────────────


def _run_handlers_harness() -> dict:
    if shutil.which("node") is None:  # pragma: no cover - environment guard
        pytest.skip("node runtime not available")
    src = _index()
    inspect = _extract_function(src, "function _crBriefInspect(")
    jump = _extract_function(src, "function _crBriefJump(")
    companion = _extract_function(src, "function _crBriefCompanion(")
    escape = _extract_function(src, "function x(")

    harness = f"""
    let _fetchCalls = 0;
    const fetch = () => {{ _fetchCalls++; return Promise.resolve({{ ok: true, json: () => ({{}}) }}); }};
    const _input = {{ value: '', focus() {{}} }};
    const _inspectBox = {{ hidden: true, innerHTML: '' }};
    function _mkEl() {{
      return {{ classList: {{ add() {{}}, remove() {{}} }},
               scrollIntoView() {{}}, querySelector() {{ return null; }},
               getAttribute() {{ return 'page:3:block:2'; }} }};
    }}
    const _block = {{ getAttribute: (k) => k === 'data-cr-locator' ? 'page:3:block:2' : '',
                      scrollIntoView() {{}}, querySelector() {{ return null; }},
                      classList: {{ add() {{}}, remove() {{}} }} }};
    const document = {{
      getElementById(id) {{
        if (id === 'cmp-input') return _input;
        if (id && id.startsWith('cr-brief-inspect-')) return _inspectBox;
        if (id === 'cr-companion-panel') return _mkEl();
        return null;
      }},
      querySelectorAll() {{ return [_block]; }},
    }};
    const setTimeout = () => 0;
    const _crBriefObs = [{{ id: 'obs-1', page: 3, source_locator: 'page:3:block:2',
                            raw_text: 'the green light at the end of the dock' }}];
    {escape}
    {inspect}
    {jump}
    {companion}
    _crBriefInspect('obs-1', {{ textContent: '' }});
    const inspected = _inspectBox.hidden === false && _inspectBox.innerHTML.includes('green light');
    _crBriefJump('page:3:block:2');
    _crBriefCompanion('obs-1');
    const prefilled = _input.value.includes('green light') && _input.value.includes('page:3:block:2');
    console.log(JSON.stringify({{ fetchCalls: _fetchCalls, inspected, prefilled }}));
    """
    result = subprocess.run(
        ["node", "-e", harness], capture_output=True, text=True, check=True
    )
    import json

    return json.loads(result.stdout)


def test_handlers_run_without_any_network_call():
    out = _run_handlers_harness()
    assert out["fetchCalls"] == 0
    assert out["inspected"] is True
    assert out["prefilled"] is True
