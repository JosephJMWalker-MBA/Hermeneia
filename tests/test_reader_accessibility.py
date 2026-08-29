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


def _run_accessibility_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


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
        + _extract_fn(html, "_a11ySetReadEnabled")
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
        + _extract_fn(html, "_a11ySetReadEnabled")
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
        + _extract_fn(html, "_a11ySetReadEnabled")
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
        + _extract_fn(html, "_a11ySetReadEnabled")
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
        + _extract_fn(html, "_a11ySetReadEnabled")
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
        + _extract_fn(html, "_a11ySetReadEnabled")
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
        + _extract_fn(html, "_a11ySetReadEnabled")
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


def test_inline_read_enabled_speaks_exact_reader_selection_without_prompt():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let currentReaderSelection={text:'The sea never asked permission.'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "let _crSelText='';\n"
        "let confirmCalls=0;\n"
        "const window={confirm(){confirmCalls+=1;return true;},getSelection(){return {toString(){return 'Toolbar Read Highlight Note Ask';}};}};\n"
        "const speechSynthesis={};\n"
        "function SpeechSynthesisUtterance(){}\n"
        "const _a11y={read:true};\n"
        "let _a11yHintShown=true;\n"
        "let spoken=[];\n"
        "let status='';\n"
        "let syncCalls=0;\n"
        "function a11ySpeak(text){spoken.push(text);}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){syncCalls+=1;}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "_crReadResolvedSelection")
        + "_crReadResolvedSelection();\n"
        "process.stdout.write(JSON.stringify({spoken,status,read:_a11y.read,confirmCalls,syncCalls}));\n"
    )

    assert behavior == {
        "spoken": ["The sea never asked permission."],
        "status": "",
        "read": True,
        "confirmCalls": 0,
        "syncCalls": 0,
    }


def test_inline_read_disabled_confirm_enables_reading_tools_and_speaks_once():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let currentReaderSelection={text:'The sea never asked permission.'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "let _crSelText='';\n"
        "let events=[];\n"
        "const window={confirm(message){events.push(['confirm',message]);return true;}};\n"
        "const speechSynthesis={};\n"
        "function SpeechSynthesisUtterance(){}\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let spoken=[];\n"
        "let status='';\n"
        "let syncCalls=0;\n"
        "function a11ySpeak(text){events.push(['speak',text]);spoken.push(text);}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){events.push(['sync',_a11y.read]);syncCalls+=1;}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "_crReadResolvedSelection")
        + "_crReadResolvedSelection();\n"
        "process.stdout.write(JSON.stringify({spoken,status,read:_a11y.read,syncCalls,events}));\n"
    )

    assert behavior["spoken"] == ["The sea never asked permission."]
    assert behavior["status"] == ""
    assert behavior["read"] is True
    assert behavior["syncCalls"] == 1
    assert behavior["events"][0][0] == "confirm"
    assert "Enable Reading Tools for this session." in behavior["events"][0][1]
    assert behavior["events"][1:] == [["sync", True], ["speak", "The sea never asked permission."]]


def test_inline_read_disabled_cancel_preserves_selection_and_does_not_speak():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let central={text:'The sea never asked permission.'};\n"
        "function _crGetReaderSelection(opts){return central;}\n"
        "let _crSelText='';\n"
        "let confirmCalls=0;\n"
        "const window={confirm(){confirmCalls+=1;return false;}};\n"
        "const speechSynthesis={};\n"
        "function SpeechSynthesisUtterance(){}\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let spoken=[];\n"
        "let status='';\n"
        "let syncCalls=0;\n"
        "function a11ySpeak(text){spoken.push(text);}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){syncCalls+=1;}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "_crReadResolvedSelection")
        + "_crReadResolvedSelection();\n"
        "process.stdout.write(JSON.stringify({spoken,status,read:_a11y.read,confirmCalls,syncCalls,selection:central.text}));\n"
    )

    assert behavior == {
        "spoken": [],
        "status": "",
        "read": False,
        "confirmCalls": 1,
        "syncCalls": 0,
        "selection": "The sea never asked permission.",
    }


def test_inline_read_unsupported_browser_reports_without_activation():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let currentReaderSelection={text:'The sea never asked permission.'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "let _crSelText='';\n"
        "let confirmCalls=0;\n"
        "const window={confirm(){confirmCalls+=1;return true;}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let spoken=[];\n"
        "let status='';\n"
        "let syncCalls=0;\n"
        "function a11ySpeak(text){spoken.push(text);}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){syncCalls+=1;}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "_crReadResolvedSelection")
        + "_crReadResolvedSelection();\n"
        "process.stdout.write(JSON.stringify({spoken,status,read:_a11y.read,confirmCalls,syncCalls}));\n"
    )

    assert behavior == {
        "spoken": [],
        "status": "Read aloud is not supported in this browser.",
        "read": False,
        "confirmCalls": 0,
        "syncCalls": 0,
    }


def test_inline_read_uses_central_reader_selection_not_raw_window_selection():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let currentReaderSelection={text:'Canonical Reader passage'};\n"
        "function _crGetReaderSelection(opts){return currentReaderSelection;}\n"
        "let _crSelText='';\n"
        "const window={confirm(){return true;},getSelection(){return {rangeCount:1,isCollapsed:false,toString(){return 'Toolbar Read Highlight Note Ask';}};}};\n"
        "const speechSynthesis={};\n"
        "function SpeechSynthesisUtterance(){}\n"
        "const _a11y={read:true};\n"
        "let _a11yHintShown=true;\n"
        "let spoken='';\n"
        "let status='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "_crReadResolvedSelection")
        + "_crReadResolvedSelection();\n"
        "process.stdout.write(JSON.stringify({spoken,status}));\n"
    )

    assert behavior == {"spoken": "Canonical Reader passage", "status": ""}


def test_current_page_speech_text_uses_structural_extractions_not_dom():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let domConsulted=false;\n"
        "const document={querySelectorAll(){domConsulted=true;return [{textContent:'CAPTURE BUTTON CHROME'}];}};\n"
        "let _crCurrentExtractions=[\n"
        "  {text:'First source block.'},\n"
        "  {text:''},\n"
        "  {text:'  Second source block.  '},\n"
        "];\n"
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + "process.stdout.write(JSON.stringify({text:_crCurrentPageSpeechText(),domConsulted}));\n"
    )

    assert behavior == {
        "text": "First source block.\n\nSecond source block.",
        "domConsulted": False,
    }


def test_read_page_button_is_rendered_in_page_header_with_accessible_label():
    html = INDEX.read_text()
    render_page = _extract_fn(html, "_crRenderPage")

    assert 'class="cr-read-page-btn"' in render_page
    assert 'type="button"' in render_page
    assert 'onclick="_crReadCurrentPage()"' in render_page
    assert 'aria-label="Read page ${x(_crPage)} aloud"' in render_page
    assert "▶ Read page" in render_page


def test_read_current_page_enabled_speaks_structural_page_without_selection():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=4;\n"
        "let _crCurrentExtractions=[{text:'Alpha.'},{text:'Beta.'}];\n"
        "const _a11y={read:true};\n"
        "let status='';\n"
        "let requests=[];\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _requestReadingToolsSpeech(text, options){requests.push({text,options});return true;}\n"
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + "_crReadCurrentPage();\n"
        "process.stdout.write(JSON.stringify({status,requests}));\n"
    )

    assert behavior["status"] == ""
    assert len(behavior["requests"]) == 1
    assert behavior["requests"][0]["text"] == "Alpha.\n\nBeta."
    assert "Read page 4 aloud?" in behavior["requests"][0]["options"]["prompt"]


def test_read_current_page_disabled_confirm_reuses_reading_tools_contract():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=4;\n"
        "let _crCurrentExtractions=[{text:'Alpha.'},{text:'Beta.'}];\n"
        "let events=[];\n"
        "const window={confirm(message){events.push(['confirm',message]);return true;}};\n"
        "const speechSynthesis={};\n"
        "function SpeechSynthesisUtterance(){}\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let status='';\n"
        "let spoken=[];\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){events.push(['sync',_a11y.read]);}\n"
        "function a11ySpeak(text){events.push(['speak',text]);spoken.push(text);}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + "_crReadCurrentPage();\n"
        "process.stdout.write(JSON.stringify({read:_a11y.read,status,spoken,events}));\n"
    )

    assert behavior["read"] is True
    assert behavior["status"] == ""
    assert behavior["spoken"] == ["Alpha.\n\nBeta."]
    assert behavior["events"][0][0] == "confirm"
    assert "Read page 4 aloud?" in behavior["events"][0][1]
    assert behavior["events"][1:] == [["sync", True], ["speak", "Alpha.\n\nBeta."]]


def test_read_current_page_disabled_cancel_does_not_speak_or_change_page():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=4;\n"
        "let _crCurrentExtractions=[{text:'Alpha.'},{text:'Beta.'}];\n"
        "let confirmCalls=0;\n"
        "const window={confirm(){confirmCalls+=1;return false;}};\n"
        "const speechSynthesis={};\n"
        "function SpeechSynthesisUtterance(){}\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let status='';\n"
        "let spoken=[];\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function a11ySpeak(text){spoken.push(text);}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + "_crReadCurrentPage();\n"
        "process.stdout.write(JSON.stringify({read:_a11y.read,status,spoken,confirmCalls,page:_crPage,text:_crCurrentPageSpeechText()}));\n"
    )

    assert behavior == {
        "read": False,
        "status": "",
        "spoken": [],
        "confirmCalls": 1,
        "page": 4,
        "text": "Alpha.\n\nBeta.",
    }


def test_read_current_page_unsupported_reuses_147_feedback_without_activation():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=4;\n"
        "let _crCurrentExtractions=[{text:'Alpha.'}];\n"
        "let confirmCalls=0;\n"
        "const window={confirm(){confirmCalls+=1;return true;}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let status='';\n"
        "let spoken=[];\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function a11ySpeak(text){spoken.push(text);}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + "_crReadCurrentPage();\n"
        "process.stdout.write(JSON.stringify({read:_a11y.read,status,spoken,confirmCalls}));\n"
    )

    assert behavior == {
        "read": False,
        "status": "Read aloud is not supported in this browser.",
        "spoken": [],
        "confirmCalls": 0,
    }


def test_read_current_page_empty_page_reports_page_specific_status():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=4;\n"
        "let _crCurrentExtractions=[{text:'   '},{text:''}];\n"
        "let status='';\n"
        "let requests=0;\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _requestReadingToolsSpeech(){requests+=1;}\n"
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + "_crReadCurrentPage();\n"
        "process.stdout.write(JSON.stringify({status,requests}));\n"
    )

    assert behavior == {
        "status": "No readable source text on this page.",
        "requests": 0,
    }


def test_page_read_and_inline_read_use_distinct_source_authorities():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=4;\n"
        "let _crSelText='';\n"
        "let _crCurrentExtractions=[{text:'Complete page source text.'}];\n"
        "let currentReaderSelection={text:'Only this selected sentence.'};\n"
        "function _crGetReaderSelection(){return currentReaderSelection;}\n"
        "const window={getSelection(){return {toString(){return 'Read page Page 4 Capture this passage';}};}};\n"
        "let requests=[];\n"
        "function _a11ySetStatus(){}\n"
        "function _requestReadingToolsSpeech(text, options){requests.push({text,prompt:options?.prompt || ''});return true;}\n"
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + _extract_fn(html, "_crReadResolvedSelection")
        + "_crReadCurrentPage();\n"
        "_crReadResolvedSelection();\n"
        "process.stdout.write(JSON.stringify({requests}));\n"
    )

    assert behavior["requests"] == [
        {
            "text": "Complete page source text.",
            "prompt": "Read page 4 aloud?\n\nEnable Reading Tools for this session.",
        },
        {"text": "Only this selected sentence.", "prompt": ""},
    ]


def test_page_speech_excludes_rendered_ui_chrome():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crCurrentExtractions=[{text:'SOURCE BLOCK A'},{text:'SOURCE BLOCK B'}];\n"
        "const document={querySelectorAll(){return [{textContent:'CAPTURE BUTTON CHROME MACHINE OBSERVATION CHROME COMPANION CHROME FIELD NOTES CHROME READ PAGE BUTTON CHROME'}];}};\n"
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + "process.stdout.write(JSON.stringify({text:_crCurrentPageSpeechText()}));\n"
    )

    assert behavior == {"text": "SOURCE BLOCK A\n\nSOURCE BLOCK B"}


def test_read_page_navigation_uses_invocation_time_page_snapshot():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=1;\n"
        "let _crCurrentExtractions=[{text:'Alpha page.'}];\n"
        "let requests=[];\n"
        "function _a11ySetStatus(){}\n"
        "function _requestReadingToolsSpeech(text, options){requests.push({text,page:options.page});return true;}\n"
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + "_crReadCurrentPage();\n"
        "_crPage=2;\n"
        "_crCurrentExtractions=[{text:'Beta page.'}];\n"
        "_crReadCurrentPage();\n"
        "process.stdout.write(JSON.stringify({requests}));\n"
    )

    assert behavior["requests"] == [
        {"text": "Alpha page.", "page": 1},
        {"text": "Beta page.", "page": 2},
    ]


def test_reader_context_reset_clears_stale_page_speech_source():
    html = INDEX.read_text()

    open_start = html.index("async function _crOpenDoc(docId)")
    page_clear_at = html.index("_crCurrentExtractions = [];", open_start)
    reset_at = html.index("_crResetReaderTransientSelectionForContext();", open_start)
    loading_at = html.index("view.innerHTML = '<div class=\"e10-empty\">Loading pages", open_start)
    assert page_clear_at < reset_at < loading_at

    render_start = html.index("function _crRenderPage()")
    render_clear_at = html.index("_crCurrentExtractions = [];", render_start)
    page_data_at = html.index("const pageData =", render_start)
    no_page_dom_at = html.index("view.innerHTML = `<div class=\"e10-empty\">No extracted text", render_start)
    set_extractions_at = html.index("_crCurrentExtractions = pageData.extractions || [];", render_start)
    assert render_clear_at < page_data_at < no_page_dom_at < set_extractions_at


def test_failed_or_missing_page_cannot_speak_prior_page_source():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=2;\n"
        "let _crTotalPages=2;\n"
        "let _crPages=[];\n"
        "let _crHighlights=[];\n"
        "let _crCurrentExtractions=[{text:'Old document page.'}];\n"
        "let _register='simple';\n"
        "let _crLensOn=false;\n"
        "let status='';\n"
        "let requests=0;\n"
        "const view={innerHTML:'',classList:{toggle(){}}};\n"
        "const document={getElementById(id){return id==='cr-page-view'?view:null;}};\n"
        "function _crResetReaderTransientSelectionForContext(){}\n"
        "function _fsApply(){}\n"
        "function _flnActivityTick(){}\n"
        "function _crLoadRelated(){}\n"
        "function runtimeApiFetch(){return Promise.resolve({});}\n"
        "function x(value){return String(value ?? '');}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _requestReadingToolsSpeech(){requests+=1;}\n"
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + _extract_fn(html, "_crRenderPage")
        + "_crRenderPage();\n"
        "_crReadCurrentPage();\n"
        "process.stdout.write(JSON.stringify({current:_crCurrentExtractions,text:_crCurrentPageSpeechText(),status,requests,html:view.innerHTML}));\n"
    )

    assert behavior["current"] == []
    assert behavior["text"] == ""
    assert behavior["status"] == "No readable source text on this page."
    assert behavior["requests"] == 0
    assert "Old document page." not in behavior["html"]


def test_read_page_uses_existing_stop_path():
    html = INDEX.read_text()
    behavior = _run_accessibility_node(
        "let _crDocId='doc-1';\n"
        "let _crPage=4;\n"
        "let _crCurrentExtractions=[{text:'Alpha.'}];\n"
        "const window={confirm(){return true;}};\n"
        "const speechSynthesis={cancel(){cancelCalls+=1;},speak(utt){spoken.push(utt.text);utt.onstart?.();}};\n"
        "function SpeechSynthesisUtterance(text){this.text=text;}\n"
        "const _a11y={read:true,speaking:false};\n"
        "let _a11yHintShown=true;\n"
        "let spoken=[];\n"
        "let cancelCalls=0;\n"
        "let statuses=[];\n"
        "function _a11ySetStatus(message){statuses.push(message);}\n"
        "function _a11ySync(){statuses.push(_a11y.speaking ? 'sync-speaking' : 'sync-idle');}\n"
        "function a11yDismissTip(){}\n"
        "function setTimeout(fn){fn();}\n"
        + _extract_fn(html, "_a11ySetReadEnabled")
        + _extract_fn(html, "_a11ySpeechSupported")
        + _extract_fn(html, "_requestReadingToolsSpeech")
        + _extract_fn(html, "a11ySpeak")
        + _extract_fn(html, "a11yStop")
        + _extract_fn(html, "_crCurrentPageSpeechText")
        + _extract_fn(html, "_crReadCurrentPage")
        + "_crReadCurrentPage();\n"
        "const speakingAfterRead=_a11y.speaking;\n"
        "a11yStop();\n"
        "process.stdout.write(JSON.stringify({spoken,cancelCalls,speakingAfterRead,speakingAfterStop:_a11y.speaking,statuses}));\n"
    )

    assert behavior["spoken"] == ["Alpha."]
    assert behavior["speakingAfterRead"] is True
    assert behavior["speakingAfterStop"] is False
    assert behavior["cancelCalls"] >= 2
    assert "Stopped — select text to read again" in behavior["statuses"]


def test_passage_read_action_still_uses_reader_passage_text():
    html = INDEX.read_text()

    assert 'onclick="_crReadResolvedSelection()" title="Read aloud"' in html
    assert "function _crReadResolvedSelection()" in html
    assert "_requestReadingToolsSpeech(text)" in _extract_fn(html, "_crReadResolvedSelection")
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


def test_focus_mode_state_still_controls_body_class_and_labels():
    html = INDEX.read_text()
    sync = _extract_fn(html, "_a11ySync")

    assert "document.body.classList.toggle('a11y-focus-mode', _a11y.focus)" in sync
    assert "focusState.textContent = _a11y.focus ? 'On' : 'Off'" in sync
    assert "a11yToggle('focus')" in html
    assert 'id="a11y-focus-state">Off</span>' in html


def test_focus_mode_does_not_mute_reader_source_surfaces():
    html = INDEX.read_text()
    focus_rules = "\n".join(re.findall(r"body\.a11y-focus-mode[^{]+\{[^}]+\}", html, re.S))

    assert "body.a11y-focus-mode #reader {" not in focus_rules
    assert "body.a11y-focus-mode .cr-page-view" not in focus_rules
    assert "body.a11y-focus-mode .cr-page-text" not in focus_rules
    assert "body.a11y-focus-mode .cr-text-block" not in focus_rules


def test_focus_mode_mutes_persistent_reader_chrome_without_locking_it():
    html = INDEX.read_text()

    assert "--reader-focus-muted-opacity: 0.26;" in html
    assert "body.a11y-focus-mode #reader .cr-doc-picker" in html
    assert "body.a11y-focus-mode #reader .cr-question-compass" in html
    assert "body.a11y-focus-mode #reader .cr-tool-rail" in html
    assert 'body.a11y-focus-mode #reader .cr-page-brief[data-open="0"]' in html
    assert "body.a11y-focus-mode #reader .cr-side" in html
    assert "body.a11y-focus-mode .workflow-rail" in html
    assert "body.a11y-focus-mode .nav" in html
    assert "body.a11y-focus-mode .thesis-bar" in html
    assert "pointer-events: none" not in _css_block(html, "body.a11y-focus-mode .nav,\nbody.a11y-focus-mode .page-head,\nbody.a11y-focus-mode .thesis-bar,\nbody.a11y-focus-mode #reader .cr-doc-picker,\nbody.a11y-focus-mode #reader .cr-question-compass,\nbody.a11y-focus-mode #reader .cr-tool-rail,\nbody.a11y-focus-mode #reader .cr-page-brief[data-open=\"0\"],\nbody.a11y-focus-mode #reader .cr-side,\nbody.a11y-focus-mode .workflow-rail")


def test_focus_mode_restores_reader_chrome_on_hover_and_focus():
    html = INDEX.read_text()

    for selector in [
        "body.a11y-focus-mode #reader .cr-doc-picker:hover",
        "body.a11y-focus-mode #reader .cr-doc-picker:focus-within",
        "body.a11y-focus-mode .thesis-bar:hover",
        "body.a11y-focus-mode .thesis-bar:focus-within",
        "body.a11y-focus-mode #reader .cr-question-compass:hover",
        "body.a11y-focus-mode #reader .cr-question-compass:focus-within",
        "body.a11y-focus-mode #reader .cr-tool-rail:hover",
        "body.a11y-focus-mode #reader .cr-tool-rail:focus-within",
        "body.a11y-focus-mode #reader .cr-page-brief:hover",
        "body.a11y-focus-mode #reader .cr-page-brief:focus-within",
        "body.a11y-focus-mode #reader .cr-side:hover",
        "body.a11y-focus-mode #reader .cr-side:focus-within",
        "body.a11y-focus-mode .workflow-rail:hover",
        "body.a11y-focus-mode .workflow-rail:focus-within",
    ]:
        assert selector in html


def test_focus_mode_keeps_foreground_reader_surfaces_full_contrast():
    html = INDEX.read_text()

    assert 'body.a11y-focus-mode #reader .cr-page-brief[data-open="1"]' in html
    assert "body.a11y-focus-mode .cr-bottom-workstation" in html
    assert "body.a11y-focus-mode #a11y-dock .dock-panel" in html
    assert "body.a11y-focus-mode #a11y-selection-tip" in html
    assert "body.a11y-focus-mode .cr-sel-toolbar" in html

    muted_rule = _css_block(html, "body.a11y-focus-mode .nav,\nbody.a11y-focus-mode .page-head,\nbody.a11y-focus-mode .thesis-bar,\nbody.a11y-focus-mode #reader .cr-doc-picker,\nbody.a11y-focus-mode #reader .cr-question-compass,\nbody.a11y-focus-mode #reader .cr-tool-rail,\nbody.a11y-focus-mode #reader .cr-page-brief[data-open=\"0\"],\nbody.a11y-focus-mode #reader .cr-side,\nbody.a11y-focus-mode .workflow-rail")
    assert ".cr-bottom-workstation" not in muted_rule
    assert ".cr-sel-toolbar" not in muted_rule
    assert ".dock-panel" not in muted_rule
    assert 'data-open="1"' not in muted_rule


def test_focus_mode_keeps_reading_tools_and_active_dock_discoverable():
    html = INDEX.read_text()

    assert 'body.a11y-focus-mode #a11y-dock .dock-rail-btn:not(.active):not([data-panel="tools"])' in html
    assert 'body.a11y-focus-mode #a11y-dock .dock-rail-btn[data-panel="tools"]' in html
    assert "body.a11y-focus-mode #a11y-dock .dock-rail-btn.active" in html
    assert "body.a11y-focus-mode #a11y-dock .dock-rail-btn:focus-visible" in html


def test_focus_mode_respects_reduced_motion():
    html = INDEX.read_text()

    assert "@media (prefers-reduced-motion: reduce)" in html
    assert "body.a11y-focus-mode #reader .cr-question-compass" in html
    assert "body.a11y-focus-mode #reader .cr-tool-rail" in html
    assert "body.a11y-focus-mode #reader .cr-side" in html
    assert "body.a11y-focus-mode #a11y-dock .dock-rail-btn" in html
    assert re.search(
        r"@media \(prefers-reduced-motion: reduce\) \{.*?"
        r"body\.a11y-focus-mode #reader \.cr-question-compass.*?"
        r"transition: none;",
        html,
        re.S,
    )


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
