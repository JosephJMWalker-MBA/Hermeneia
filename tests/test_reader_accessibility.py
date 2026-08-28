from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def _css_block(html: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{(?P<body>.*?)\n\}", html, re.S)
    assert match, f"could not extract CSS block {selector}"
    return match.group("body")


def test_reading_tools_read_current_structural_reader_selection():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let currentReaderSelection={text:'Exact Reader source text'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "const window={getSelection(){return {rangeCount:1,isCollapsed:false,toString(){return 'UI chrome Exact Reader source text';}};}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let spoken='';\n"
        "let status='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yClickRead")
        + "a11yClickRead();\n"
        "process.stdout.write(JSON.stringify({spoken,status,cached:_a11yLastReaderSelection}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "spoken": "Exact Reader source text",
        "status": "",
        "cached": "Exact Reader source text",
    }


def test_reading_tools_use_cached_reader_selection_after_native_selection_collapse():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let currentReaderSelection={text:'Cached Reader source text'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "const window={getSelection(){return {rangeCount:0,isCollapsed:true,toString(){return '';}};}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let spoken='';\n"
        "let status='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yClickRead")
        + "_a11yCacheReaderSelection();\n"
        "currentReaderSelection=null;\n"
        "a11yClickRead();\n"
        "process.stdout.write(JSON.stringify({spoken,status,cached:_a11yLastReaderSelection}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "spoken": "Cached Reader source text",
        "status": "",
        "cached": "Cached Reader source text",
    }


def test_reading_tools_cache_excludes_ui_chrome_and_unrelated_selection():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let currentReaderSelection={text:'Reader-only passage'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "let rawSelection='Reader-only passage Capture this passage Open marginal tools';\n"
        "const window={getSelection(){return {rangeCount:1,isCollapsed:false,toString(){return rawSelection;}};}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let spoken='';\n"
        "let status='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yClickRead")
        + "_a11yCacheReaderSelection();\n"
        "currentReaderSelection=null;\n"
        "rawSelection='Outside application selection';\n"
        "_a11yCacheReaderSelection();\n"
        "a11yClickRead();\n"
        "process.stdout.write(JSON.stringify({spoken,status,cached:_a11yLastReaderSelection}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "spoken": "Reader-only passage",
        "status": "",
        "cached": "Reader-only passage",
    }


def test_new_reader_selection_replaces_prior_reading_tools_cache():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let currentReaderSelection={text:'First Reader passage'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "const window={getSelection(){return {rangeCount:0,isCollapsed:true,toString(){return '';}};}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let spoken='';\n"
        "let status='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yClickRead")
        + "_a11yCacheReaderSelection();\n"
        "currentReaderSelection={text:'Second Reader passage'};\n"
        "_a11yCacheReaderSelection();\n"
        "currentReaderSelection=null;\n"
        "a11yClickRead();\n"
        "process.stdout.write(JSON.stringify({spoken,status,cached:_a11yLastReaderSelection}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "spoken": "Second Reader passage",
        "status": "",
        "cached": "Second Reader passage",
    }


def test_reading_tools_do_not_resurrect_cleared_reader_selection():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let currentReaderSelection={text:'Reader passage to clear'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "const window={getSelection(){return {rangeCount:0,isCollapsed:true,toString(){return '';}};}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let spoken='';\n"
        "let status='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yClickRead")
        + "_a11yCacheReaderSelection();\n"
        "_a11yClearReaderSelectionCache();\n"
        "currentReaderSelection=null;\n"
        "a11yClickRead();\n"
        "process.stdout.write(JSON.stringify({spoken,status,cached:_a11yLastReaderSelection}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "spoken": "",
        "status": "Select text first.",
        "cached": "",
    }


def test_reader_page_context_reset_invalidates_cached_reading_tools_passage():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let currentReaderSelection={text:'Page one Reader passage'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "const window={getSelection(){return {rangeCount:0,isCollapsed:true,toString(){return '';}};}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let _crReaderSelectionState={valid:true,text:'Page one Reader passage'};\n"
        "let _crSelRange={detached:true};\n"
        "let _crSelText='Page one Reader passage';\n"
        "let _crSelectionRect={left:1,top:2,bottom:3,right:4};\n"
        "let _crCaptureOpen=false;\n"
        "let spoken='';\n"
        "let status='';\n"
        "let pendingCleared=false;\n"
        "let toolbarHidden=false;\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function _crHideToolbar(force){toolbarHidden=!!force;}\n"
        "function _crClearPending(){pendingCleared=true;}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yClickRead")
        + _extract_fn(html, "_crClearReaderSelectionState")
        + _extract_fn(html, "_crResetReaderTransientSelectionForContext")
        + "_a11yCacheReaderSelection();\n"
        "currentReaderSelection=null;\n"
        "_crResetReaderTransientSelectionForContext();\n"
        "a11yClickRead();\n"
        "process.stdout.write(JSON.stringify({spoken,status,cached:_a11yLastReaderSelection,readerState:_crReaderSelectionState,range:_crSelRange,selText:_crSelText,rect:_crSelectionRect,pendingCleared,toolbarHidden}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "spoken": "",
        "status": "Select text first.",
        "cached": "",
        "readerState": None,
        "range": None,
        "selText": "",
        "rect": None,
        "pendingCleared": True,
        "toolbarHidden": True,
    }


def test_reader_context_reset_before_document_load_failure_invalidates_old_passage():
    html = INDEX.read_text()

    open_start = html.index("async function _crOpenDoc(docId)")
    reset_at = html.index("_crResetReaderTransientSelectionForContext();", open_start)
    loading_at = html.index("view.innerHTML = '<div class=\"e10-empty\">Loading pages", open_start)
    fetch_at = html.index("await get(`/api/reader/documents/", open_start)
    catch_at = html.index("} catch(e) {", open_start)

    assert reset_at < loading_at < fetch_at < catch_at


def test_reader_page_render_invalidates_selection_before_replacing_dom():
    html = INDEX.read_text()

    render_start = html.index("function _crRenderPage()")
    reset_at = html.index("_crResetReaderTransientSelectionForContext();", render_start)
    no_page_dom_at = html.index("view.innerHTML = `<div class=\"e10-empty\">No extracted text", render_start)
    normal_dom_at = html.index("view.innerHTML = `", no_page_dom_at + 1)

    assert reset_at < no_page_dom_at
    assert reset_at < normal_dom_at


def test_floating_read_popup_uses_same_cached_reader_selection_after_collapse():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let currentReaderSelection={text:'Popup cached Reader source'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "const window={getSelection(){return {rangeCount:0,isCollapsed:true,toString(){return '';}};}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let spoken='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySync(){}\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yReadSelection")
        + "_a11yCacheReaderSelection();\n"
        "currentReaderSelection=null;\n"
        "a11yReadSelection();\n"
        "process.stdout.write(JSON.stringify({spoken,cached:_a11yLastReaderSelection,read:_a11y.read}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "spoken": "Popup cached Reader source",
        "cached": "Popup cached Reader source",
        "read": True,
    }


def test_new_reader_selection_after_context_reset_establishes_new_reading_tools_cache():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let currentReaderSelection={text:'Old Reader passage'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "const window={getSelection(){return {rangeCount:0,isCollapsed:true,toString(){return '';}};}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let _crReaderSelectionState={valid:true,text:'Old Reader passage'};\n"
        "let _crSelRange={detached:true};\n"
        "let _crSelText='Old Reader passage';\n"
        "let _crSelectionRect={left:1,top:2,bottom:3,right:4};\n"
        "let _crCaptureOpen=false;\n"
        "let spoken='';\n"
        "let status='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function _crHideToolbar(){}\n"
        "function _crClearPending(){}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yClickRead")
        + _extract_fn(html, "_crClearReaderSelectionState")
        + _extract_fn(html, "_crResetReaderTransientSelectionForContext")
        + "_a11yCacheReaderSelection();\n"
        "_crResetReaderTransientSelectionForContext();\n"
        "currentReaderSelection={text:'Page two Reader passage'};\n"
        "_a11yCacheReaderSelection();\n"
        "currentReaderSelection=null;\n"
        "a11yClickRead();\n"
        "process.stdout.write(JSON.stringify({spoken,status,cached:_a11yLastReaderSelection}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "spoken": "Page two Reader passage",
        "status": "",
        "cached": "Page two Reader passage",
    }


def test_passage_read_action_still_uses_reader_passage_text():
    html = INDEX.read_text()

    assert 'onclick="_crReadResolvedSelection()" title="Read aloud"' in html
    assert "function _crReadResolvedSelection()" in html
    # a11yReadSelection reads the same current-or-cached Reader selection path;
    # it still auto-enables read mode so the popup's Read button works without
    # pre-toggling (item 7).
    assert "function a11yReadSelection() {" in html
    assert "_a11yGetDockReadText()" in html
    assert "if (!_a11y.read) { _a11y.read = true; _a11ySync(); }" in html


def test_reading_tools_can_use_central_reader_selection_state():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "let centralCalls=0;\n"
        "function _crGetReaderSelection(opts){centralCalls+=1;return {text:'Exact Reader source text'};}\n"
        "const window={getSelection(){return {rangeCount:1,isCollapsed:false,toString(){return 'Raw UI chrome text';}};}};\n"
        "let _a11yLastReaderSelection='';\n"
        + _extract_fn(html, "_a11yRememberReaderSelection")
        + _extract_fn(html, "_a11yClearReaderSelectionCache")
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yGetDockReadText")
        + "process.stdout.write(JSON.stringify({selected:_a11yGetSelectedText(),dock:_a11yGetDockReadText(),centralCalls}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "selected": "Exact Reader source text",
        "dock": "Exact Reader source text",
        "centralCalls": 2,
    }


def test_large_text_state_still_controls_body_class_and_labels():
    html = INDEX.read_text()
    sync = _extract_fn(html, "_a11ySync")

    assert "document.body.classList.toggle('a11y-text-lg', _a11y.textLg)" in sync
    assert "textState.textContent = _a11y.textLg ? 'Large' : 'Normal'" in sync
    assert "a11yToggle('textLg')" in html
    assert 'id="a11y-text-state">Normal</span>' in html


def test_reader_source_prose_uses_shared_typography_tokens():
    html = INDEX.read_text()

    page_view = _css_block(html, ".cr-page-view")
    page_text = _css_block(html, ".cr-page-text")
    large_view = _css_block(html, "body.a11y-text-lg .cr-page-view")

    assert "--reader-prose-size: 1rem;" in page_view
    assert "--reader-prose-leading: 1.85;" in page_view
    assert "font-size: var(--reader-prose-size)" in page_text
    assert "line-height: var(--reader-prose-leading)" in page_text
    assert "--reader-prose-size: 1.25rem;" in large_view
    assert "--reader-prose-leading: 1.9;" in large_view
    assert "body.a11y-text-lg .cr-page-text { font-size: 21px !important" not in html


def test_large_text_composes_with_focus_scroll_typography():
    html = INDEX.read_text()

    focus_view = _css_block(html, ".cr-page-view.focus-scroll")
    focus_text = _css_block(html, ".cr-page-view.focus-scroll .cr-page-text")
    large_focus_view = _css_block(html, "body.a11y-text-lg .cr-page-view.focus-scroll")

    assert "--reader-prose-size: clamp(1.05rem, 1.6vw, 1.35rem);" in focus_view
    assert "--reader-prose-size: clamp(1.32rem, 2.05vw, 1.7rem);" in large_focus_view
    assert "font-size:" not in focus_text
    assert "line-height:" not in focus_text
    assert "opacity: calc(0.38 + (var(--focus) * 0.62));" in focus_text
    assert "transform: translateY(calc((1 - var(--focus)) * 5px));" in focus_text

    normal_focus_max_rem = 1.35
    large_focus_max_rem = 1.7
    assert large_focus_max_rem / normal_focus_max_rem >= 1.20


def test_large_text_uses_reflow_not_transform_or_zoom():
    html = INDEX.read_text()

    large_view = _css_block(html, "body.a11y-text-lg .cr-page-view")
    large_focus_view = _css_block(html, "body.a11y-text-lg .cr-page-view.focus-scroll")
    page_text = _css_block(html, ".cr-page-text")

    combined = "\n".join([large_view, large_focus_view])
    assert "transform" not in combined
    assert "zoom" not in combined
    assert "white-space: pre-wrap" in page_text
    assert "overflow-wrap: anywhere" in page_text
