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


def test_reading_tools_preserve_reader_selection_for_dock_fallback():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader accessibility UI test")

    html = INDEX.read_text()
    harness = (
        "const readerNode={};\n"
        "let selection={rangeCount:0,isCollapsed:true,toString(){return '';}};\n"
        "const window={getSelection(){return selection;}};\n"
        "const pageView={contains(node){return node===readerNode;}};\n"
        "const document={getElementById(id){return id==='cr-page-view'?pageView:null;}};\n"
        "const _a11y={read:false};\n"
        "let _a11yHintShown=true;\n"
        "let _a11yLastReaderSelection='';\n"
        "let spoken='';\n"
        "let status='';\n"
        "function a11ySpeak(text){spoken=text;}\n"
        "function _a11ySetStatus(message){status=message;}\n"
        "function _a11ySync(){}\n"
        "function setTimeout(){}\n"
        + _extract_fn(html, "_a11yGetSelectedText")
        + _extract_fn(html, "_a11yCacheReaderSelection")
        + _extract_fn(html, "_a11yGetDockReadText")
        + _extract_fn(html, "a11yClickRead")
        + "selection={rangeCount:1,isCollapsed:false,"
        "getRangeAt(){return {commonAncestorContainer:readerNode};},"
        "toString(){return '  Cached   Reader passage  ';}};\n"
        "_a11yCacheReaderSelection();\n"
        "selection={rangeCount:1,isCollapsed:false,"
        "getRangeAt(){return {commonAncestorContainer:{}};},"
        "toString(){return 'Outside the Reader';}};\n"
        "_a11yCacheReaderSelection();\n"
        "const cachedAfterOutside=_a11yLastReaderSelection;\n"
        "selection={rangeCount:0,isCollapsed:true,toString(){return '';}};\n"
        "_a11yCacheReaderSelection();\n"
        "a11yClickRead();\n"
        "const fallback={cached:_a11yLastReaderSelection,cachedAfterOutside,spoken,status};\n"
        "spoken='';status='';\n"
        "selection={rangeCount:1,isCollapsed:false,"
        "getRangeAt(){return {commonAncestorContainer:{}};},"
        "toString(){return 'Current window selection';}};\n"
        "a11yClickRead();\n"
        "const current={spoken,status};\n"
        "spoken='';status='';_a11yLastReaderSelection='';\n"
        "selection={rangeCount:0,isCollapsed:true,toString(){return '';}};\n"
        "a11yClickRead();\n"
        "process.stdout.write(JSON.stringify({fallback,current,emptyStatus:status}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior["fallback"] == {
        "cached": "Cached Reader passage",
        "cachedAfterOutside": "Cached Reader passage",
        "spoken": "Cached Reader passage",
        "status": "",
    }
    assert behavior["current"] == {
        "spoken": "Current window selection",
        "status": "",
    }
    assert behavior["emptyStatus"] == "Select text first."


def test_passage_read_action_still_uses_reader_passage_text():
    html = INDEX.read_text()

    assert 'onclick="_crReadResolvedSelection()" title="Read aloud"' in html
    assert "function _crReadResolvedSelection()" in html
    # a11yReadSelection reads the current selection; it now also auto-enables
    # read mode so the popup's Read button works without pre-toggling (item 7).
    assert "function a11yReadSelection() {" in html
    assert "_a11yGetSelectedText()" in html
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
