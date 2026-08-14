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
