from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _selection_region() -> str:
    html = INDEX.read_text()
    start = html.index("// Selection capture")
    end = html.index("async function _crShowHighlightDetail", start)
    return html[start:end]


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader selection UI tests")

    harness = (
        r"""
const Node = { ELEMENT_NODE: 1 };
let _crCurrentExtractions = [
  { id: 'ex-1', source_locator: 'p1:block0' },
  { id: 'ex-2', source_locator: 'p1:block1' },
  { id: 'ex-3', source_locator: 'p1:block2' },
];
let _crDocId = 'doc-1';
let _crPage = 1;
let _crSelText = '';
let _crSelRange = null;
let _crSelectionRect = null;
let _crSelToolbar = null;
let _crCaptureOpen = false;
let _crRelevance = 'unclear';
let _crConcept = '';
let savedPayload = null;
function x(value){ return String(value ?? ''); }
function _dockOpenPanel(){}
function _crHideToolbar(){}
function _crShowToolbar(){}
function _crMarkPending(){}
function _crClearPending(){}
function _crNewHighlightDraftKey(){ return 'draft-key'; }
function _crStoreNewHighlightDraft(){}
function _authoredDraftClear(){}
async function _crLoadHighlightList(){}
function _crRenderPage(){}
function _crRefreshTrail(){}
function _flnActivityTick(){}
function _crShowHighlightDetail(){}
function cmpMarkOnboardingStep(){}
async function requestJSON(url, opts){
  savedPayload = opts && opts.body;
  return { id: 'hl-1' };
}
function _crRankOptions(){ return ''; }
function _crReadRankValue(){ return null; }
function _crReadOptionalText(){ return null; }
function _crBindNewHighlightDraft(){}
function invLoad(){ return {}; }
function requestAnimationFrame(fn){ fn(); }
function setTimeout(fn){ fn(); }

function makeBlock(index, locator, text){
  const block = {
    nodeType: Node.ELEMENT_NODE,
    dataset: { crBlock: String(index), crLocator: locator },
    parentElement: null,
    children: [],
    getBoundingClientRect(){ return { left: 1, top: 2, right: 3, bottom: 4, width: 2, height: 2 }; },
    querySelector(sel){ return sel === '.cr-page-text' ? textEl : null; },
    closest(sel){ return sel === '.cr-text-block' ? block : null; },
    contains(node){ return node === block || node === textEl || block.children.includes(node); },
  };
  const textEl = {
    nodeType: Node.ELEMENT_NODE,
    className: 'cr-page-text',
    textContent: text,
    dataset: {},
    parentElement: block,
    getBoundingClientRect(){ return { left: 1, top: 2, right: 3, bottom: 4, width: 2, height: 2 }; },
    querySelector(){ return null; },
    closest(sel){
      if (sel === '.cr-page-text') return textEl;
      if (sel === '.cr-text-block') return block;
      return null;
    },
  };
  block.children.push(textEl);
  return { block, textEl };
}

const b0 = makeBlock(0, 'p1:block0', 'First projected source line.');
const b1 = makeBlock(1, 'p1:block1', 'Second projected source line with “Unicode” — punctuation.');
const b2 = makeBlock(2, 'p1:block2', 'Final source line: end.');
const allBlocks = [b0.block, b1.block, b2.block];
function input(value=''){ return { value, checked: false, style: {}, textContent: '', innerHTML: '' }; }
const elements = {
  'cr-note-input': input(''),
  'cr-q-input': input(''),
  'cr-important-input': { checked: false },
  'cr-tags-input': input(''),
  'cr-rank-input': input(''),
  'cr-theme-input': input(''),
  'cr-concept-input': input(''),
  'cr-capture-msg': input(''),
  'cr-sel-prompt': input(''),
};
const pageView = {
  contains(node){ return node === pageView || allBlocks.some(block => block.contains(node)); },
  querySelectorAll(sel){ return sel === '.cr-page-text' ? [b0.textEl, b1.textEl, b2.textEl] : []; },
};
const document = {
  body: { appendChild(){} },
  createElement(){ return { className: '', id: '', innerHTML: '', style: {}, classList: { add(){} }, remove(){} }; },
  getElementById(id){ return id === 'cr-page-view' ? pageView : (elements[id] || null); },
  querySelector(sel){
    const match = String(sel).match(/data-cr-block="(\d+)"/);
    if (!match) return null;
    return allBlocks[Number(match[1])] || null;
  },
  querySelectorAll(sel){ return sel === '#cr-page-view .cr-page-text' ? [b0.textEl, b1.textEl, b2.textEl] : []; },
};
let activeSelection = null;
const window = {
  innerWidth: 1200,
  innerHeight: 800,
  scrollY: 0,
  getSelection(){ return activeSelection; },
};
"""
        + _selection_region()
        + script
    )
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_multiblock_selection_ignores_enclosed_reader_controls_structurally() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b0.textEl,
  endContainer: b1.textEl,
  commonAncestorContainer: pageView,
  cloneRange(){ return this; },
  cloneContents(){
    return {
      querySelectorAll(sel){
        if (sel !== '.cr-page-text') return [];
        return [
          { textContent: b0.textEl.textContent },
          { textContent: b1.textEl.textContent },
        ];
      },
    };
  },
  getBoundingClientRect(){ return { left: 10, top: 20, right: 40, bottom: 60, width: 30, height: 40 }; },
};
const raw = [
  b0.textEl.textContent,
  'Capture this passage',
  'Open marginal tools',
  b1.textEl.textContent,
].join('\n');
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return raw; } };
const selection = _crGetReaderSelection({ refresh: true, fallback: false });
process.stdout.write(JSON.stringify({
  text: selection.text,
  locator: _crEncodeReaderSpanLocator(selection),
  raw,
}));
"""
    )

    assert result["text"] == (
        "First projected source line.\n\n"
        "Second projected source line with “Unicode” — punctuation."
    )
    assert "Capture this passage" in result["raw"]
    assert "Open marginal tools" in result["raw"]
    assert "Capture this passage" not in result["text"]
    assert "Open marginal tools" not in result["text"]
    assert result["locator"] == "p1:block0..p1:block1"


def test_single_block_selection_preserves_text_with_existing_trim_semantics() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b2.textEl,
  endContainer: b2.textEl,
  commonAncestorContainer: b2.textEl,
  cloneRange(){ return this; },
  cloneContents(){ return { querySelectorAll(){ return []; } }; },
  toString(){ return '  "Already," she said — naïve façade.  '; },
  getBoundingClientRect(){ return { left: 10, top: 20, right: 40, bottom: 60, width: 30, height: 40 }; },
};
activeSelection = {
  rangeCount: 1,
  isCollapsed: false,
  getRangeAt(){ return range; },
  toString(){ return '  "Already," she said — naïve façade.  '; },
};
const selection = _crGetReaderSelection({ refresh: true, fallback: false });
process.stdout.write(JSON.stringify({ text: selection.text }));
"""
    )

    assert result["text"] == '"Already," she said — naïve façade.'


def test_genuine_multiline_multiblock_source_text_is_preserved_in_order() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b0.textEl,
  endContainer: b2.textEl,
  commonAncestorContainer: pageView,
  cloneRange(){ return this; },
  cloneContents(){
    return {
      querySelectorAll(sel){
        if (sel !== '.cr-page-text') return [];
        return [
          { textContent: 'Line one.\nLine two.' },
          { textContent: b1.textEl.textContent },
          { textContent: 'Final source line: end.' },
        ];
      },
    };
  },
  getBoundingClientRect(){ return { left: 10, top: 20, right: 40, bottom: 60, width: 30, height: 40 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return 'raw mixed selection'; } };
const selection = _crGetReaderSelection({ refresh: true, fallback: false });
process.stdout.write(JSON.stringify({ text: selection.text }));
"""
    )

    assert result["text"] == (
        "Line one.\nLine two.\n\n"
        "Second projected source line with “Unicode” — punctuation.\n\n"
        "Final source line: end."
    )


def test_save_payload_uses_structural_selection_not_stale_ui_copy() -> None:
    result = _run_node(
        r"""
(async () => {
  _crReaderSelectionState = {
    valid: true,
    text: 'First projected source line.\n\nSecond projected source line with “Unicode” — punctuation.',
    source_locators: ['p1:block0', 'p1:block1'],
    blocks: [{ block_index: 0 }, { block_index: 1 }],
    page: 1,
  };
  _crSelText = [
    'First projected source line.',
    'Capture this passage',
    'Open marginal tools',
    'Second projected source line with “Unicode” — punctuation.',
  ].join('\n');
  await _crSaveHighlight(false);
  process.stdout.write(JSON.stringify({ selectedText: savedPayload.selected_text, note: savedPayload.note_text }));
})();
"""
    )

    assert result["selectedText"] == (
        "First projected source line.\n\n"
        "Second projected source line with “Unicode” — punctuation."
    )
    assert "Capture this passage" not in result["selectedText"]
    assert "Open marginal tools" not in result["selectedText"]
    assert result["note"] is None
