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


def _run_node(harness: str) -> dict:
    if shutil.which("node") is None:  # pragma: no cover - environment guard
        pytest.skip("node runtime not available")

    result = subprocess.run(
        ["node", "-e", harness], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def _thesis_bar_harness(saved_question: dict | None) -> str:
    src = _index()
    inv_key_line = "const _INV_KEY = 'hermeneia_investigation_v1';"
    escape = _extract_function(src, "function x(")
    inv_load = _extract_function(src, "function invLoad(")
    render = _extract_function(src, "function _renderThesisBar(")

    return f"""
    const _store = {{}};
    const localStorage = {{
      getItem(k) {{ return k in _store ? _store[k] : null; }},
      setItem(k, v) {{ _store[k] = String(v); }},
      removeItem(k) {{ delete _store[k]; }},
    }};
    const bar = {{
      hidden: true,
      className: 'thesis-bar',
      _attrs: {{}},
      classList: {{
        add(c) {{
          const parts = new Set(bar.className.split(/\\s+/).filter(Boolean));
          parts.add(c);
          bar.className = Array.from(parts).join(' ');
        }},
        remove(c) {{
          bar.className = bar.className.split(/\\s+/).filter(Boolean).filter(x => x !== c).join(' ');
        }},
        contains(c) {{ return bar.className.split(/\\s+/).includes(c); }},
      }},
      setAttribute(k, v) {{ this._attrs[k] = String(v); }},
      getAttribute(k) {{ return this._attrs[k]; }},
      innerHTML: '',
      title: '',
    }};
    const document = {{
      getElementById(id) {{ return id === 'thesis-bar' ? bar : null; }},
    }};
    {inv_key_line}
    {escape}
    {inv_load}
    {render}
    const saved = {json.dumps(saved_question)};
    if (saved !== null) localStorage.setItem(_INV_KEY, JSON.stringify(saved));
    _renderThesisBar();
    console.log(JSON.stringify({{
      className: bar.className,
      hidden: bar.hidden,
      html: bar.innerHTML,
      title: bar.title,
      ariaLabel: bar.getAttribute('aria-label'),
    }}));
    """


def test_unset_global_question_bar_has_attention_state_and_compass_copy():
    state = _run_node(_thesis_bar_harness(saved_question=None))

    assert state["hidden"] is False
    assert "unset" in state["className"].split()
    assert "thesis-bar-attention" in state["className"].split()
    assert "Set a governing question to guide your reading →" in state["html"]
    assert state["title"] == "Your question is the compass for the investigation."
    assert "compass for the investigation" in state["ariaLabel"]


def test_saved_global_question_bar_removes_unset_attention_state():
    state = _run_node(
        _thesis_bar_harness(
            saved_question={"thesis": "How does Gatsby imagine return?"}
        )
    )

    assert "unset" not in state["className"].split()
    assert "thesis-bar-attention" not in state["className"].split()
    assert "How does Gatsby imagine return?" in state["html"]
    assert state["title"] == "How does Gatsby imagine return?"
    assert state["ariaLabel"] == "Governing question: How does Gatsby imagine return?"


def test_saving_reader_question_clears_unset_attention_in_session():
    src = _index()
    inv_key_line = "const _INV_KEY = 'hermeneia_investigation_v1';"
    escape = _extract_function(src, "function x(")
    inv_load = _extract_function(src, "function invLoad(")
    inv_save = _extract_function(src, "function invSave(")
    render_bar = _extract_function(src, "function _renderThesisBar(")
    update_page = _extract_function(src, "function updatePageThesis(")
    keep_question = _extract_function(src, "function _crKeepQuestion(")

    harness = f"""
    const _store = {{}};
    const localStorage = {{
      getItem(k) {{ return k in _store ? _store[k] : null; }},
      setItem(k, v) {{ _store[k] = String(v); }},
      removeItem(k) {{ delete _store[k]; }},
    }};
    const fetch = () => Promise.resolve({{}});
    const input = {{ value: 'What does the green light demand?', focusCalled: false, focus() {{ this.focusCalled = true; }} }};
    const bar = {{
      hidden: true,
      className: 'thesis-bar unset thesis-bar-attention',
      _attrs: {{}},
      classList: {{
        add(c) {{
          const parts = new Set(bar.className.split(/\\s+/).filter(Boolean));
          parts.add(c);
          bar.className = Array.from(parts).join(' ');
        }},
        remove(c) {{
          bar.className = bar.className.split(/\\s+/).filter(Boolean).filter(x => x !== c).join(' ');
        }},
      }},
      setAttribute(k, v) {{ this._attrs[k] = String(v); }},
      innerHTML: '',
      title: '',
    }};
    const pageThesis = {{ textContent: '', classList: {{ toggle() {{}} }}, title: '', onclick: null }};
    const pageWrap = {{ style: {{ display: '' }} }};
    const document = {{
      getElementById(id) {{
        if (id === 'cr-question-input') return input;
        if (id === 'thesis-bar') return bar;
        if (id === 'page-thesis') return pageThesis;
        if (id === 'page-thesis-wrap') return pageWrap;
        if (id === 'cr-firstrun-banner') return {{ remove() {{}} }};
        return null;
      }},
    }};
    function _crRenderQuestionCard() {{}}
    function _crRenderQuestionCompass() {{}}
    function cmpMarkOnboardingStep() {{}}
    {inv_key_line}
    {escape}
    {inv_load}
    {inv_save}
    {render_bar}
    {update_page}
    {keep_question}
    _crKeepQuestion();
    console.log(JSON.stringify({{
      className: bar.className,
      html: bar.innerHTML,
      saved: JSON.parse(localStorage.getItem(_INV_KEY)),
      inputValue: input.value,
    }}));
    """
    state = _run_node(harness)

    assert state["saved"]["thesis"] == "What does the green light demand?"
    assert "unset" not in state["className"].split()
    assert "thesis-bar-attention" not in state["className"].split()
    assert "What does the green light demand?" in state["html"]
    assert state["inputValue"] == ""


def test_unset_global_question_bar_click_opens_existing_question_editor():
    src = _index()
    click = _extract_function(src, "function _thesisBarClick(")
    harness = f"""
    let route = null;
    let renderedEditing = null;
    let focused = false;
    function e10Go(dest) {{ route = dest; }}
    function _crRenderQuestionCard(editing) {{ renderedEditing = editing; }}
    const document = {{
      getElementById(id) {{
        if (id === 'cr-question-input') return {{ focus() {{ focused = true; }} }};
        return null;
      }},
    }};
    function setTimeout(fn) {{ fn(); }}
    {click}
    _thesisBarClick();
    console.log(JSON.stringify({{ route, renderedEditing, focused }}));
    """
    state = _run_node(harness)

    assert state == {
        "route": "reader",
        "renderedEditing": True,
        "focused": True,
    }


def test_unset_global_question_bar_attention_has_reduced_motion_and_focus_rules():
    index = _index()

    assert "@keyframes thesis-unset-attention" in index
    assert ".thesis-bar.unset.thesis-bar-attention" in index
    assert "animation: thesis-unset-attention 2.8s ease-in-out infinite;" in index
    reduced = index[index.index("@media (prefers-reduced-motion: reduce)") :]
    assert ".thesis-bar.unset.thesis-bar-attention" in reduced
    assert "animation: none;" in reduced
    assert "body.a11y-focus-mode .thesis-bar.unset" in index
    assert "body.a11y-focus-mode .thesis-bar.unset.thesis-bar-attention" in index
