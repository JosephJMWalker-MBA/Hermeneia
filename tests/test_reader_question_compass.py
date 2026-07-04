"""Always-visible Question Compass (issue #56 slice 2).

A persistent, unobtrusive orientation element near the top of the Reader,
above the book surface. Visible even when no question is set — your question
is your compass, not your conclusion. It never replaces the "Your Question"
form and holds no state of its own; it reflects the saved investigation.

Copy assertions guard the markup; the Node-executed test proves the compass
renders the unset tagline with no question and the current question when one
exists.
"""
from __future__ import annotations

import json
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


# ── Markup + copy ──────────────────────────────────────────────────────────


def test_compass_markup_exists_in_reader():
    index = _index()
    assert 'id="cr-question-compass"' in index
    assert "cr-question-compass" in index  # css class
    assert "_crRenderQuestionCompass()" in index
    # Rendered above the book surface: compass appears before the reading view.
    assert index.index('id="cr-question-compass"') < index.index('id="cr-page-view"')


def test_compass_unset_state_copy_exists():
    index = _index()
    assert "Question Compass" in index
    assert "Your question is your compass, not your conclusion." in index
    assert "Set a question to guide what you notice, challenge, and revise." in index


def test_compass_set_state_copy_and_current_question_path_exists():
    index = _index()
    # Set-state guidance copy.
    assert (
        "Use the corpus to inform, pressure-test, complicate, revise, or overturn it."
        in index
    )
    # The set-state renders the saved question text (invLoad thesis).
    fn = _extract_function(index, "function _crRenderQuestionCompass(")
    assert "invLoad()" in fn
    assert "cr-compass-question" in fn


def test_compass_is_not_a_modal_or_side_panel():
    """Guard the placement constraints from issue #56 slice 2."""
    index = _index()
    fn_marker = "function _crRenderQuestionCompass("
    assert fn_marker in index
    # It lives inline in the reader top area, not as a side panel or modal.
    assert 'class="cr-side-panel" id="cr-question-compass"' not in index
    assert 'class="modal" id="cr-question-compass"' not in index


def test_existing_your_question_form_remains_available():
    """The compass must not replace the existing question form."""
    index = _index()
    assert "_crRenderQuestionCard" in index
    assert "_crKeepQuestion()" in index
    assert "Keep this question" in index
    assert 'id="cr-question-panel"' in index


# ── Behavior: execute the render under Node ────────────────────────────────


def _render_compass(saved_question: dict | None) -> str:
    if shutil.which("node") is None:  # pragma: no cover - environment guard
        pytest.skip("node runtime not available")

    src = _index()
    inv_key_line = "const _INV_KEY = 'hermeneia_investigation_v1';"
    assert inv_key_line in src
    inv_load = _extract_function(src, "function invLoad(")
    render = _extract_function(src, "function _crRenderQuestionCompass(")
    escape = _extract_function(src, "function x(")

    harness = f"""
    const _store = {{}};
    const localStorage = {{
      getItem(k) {{ return k in _store ? _store[k] : null; }},
      setItem(k, v) {{ _store[k] = String(v); }},
      removeItem(k) {{ delete _store[k]; }},
    }};
    let _captured = '';
    const document = {{
      getElementById(id) {{
        if (id !== 'cr-question-compass') return null;
        return {{ set innerHTML(v) {{ _captured = v; }} }};
      }},
    }};
    {inv_key_line}
    {escape}
    {inv_load}
    {render}
    const saved = {json.dumps(saved_question)};
    if (saved !== null) localStorage.setItem(_INV_KEY, JSON.stringify(saved));
    _crRenderQuestionCompass();
    console.log(_captured);
    """
    result = subprocess.run(
        ["node", "-e", harness], capture_output=True, text=True, check=True
    )
    return result.stdout


def test_compass_renders_unset_tagline_when_no_question():
    html = _render_compass(saved_question=None)
    assert "Your question is your compass, not your conclusion." in html
    assert "Set a question to guide what you notice, challenge, and revise." in html
    assert "cr-compass-question" not in html


def test_compass_renders_current_question_when_set():
    html = _render_compass(
        saved_question={"thesis": "What does the green light mean?"}
    )
    assert "What does the green light mean?" in html
    assert (
        "Use the corpus to inform, pressure-test, complicate, revise, or overturn it."
        in html
    )
    assert "Your question is your compass, not your conclusion." not in html


def test_find_the_x_helper_signature_is_stable():
    """The compass escapes the question via the shared x() helper; guard it
    exists so a rename does not silently drop escaping."""
    assert "function x(" in _index()
