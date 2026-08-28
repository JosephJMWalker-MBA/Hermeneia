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
let _crReaderSelectionState = null;
let _crSelToolbar = null;
let _crCaptureOpen = false;
let _crRelevance = 'unclear';
let _crConcept = '';
let savedPayload = null;
let failNextRequest = false;
let spokenText = '';
let a11yCacheCleared = false;
function x(value){ return String(value ?? ''); }
function ttsSpeak(text){ spokenText = text; }
function _requestReadingToolsSpeech(text){ spokenText = text; }
function _a11yClearReaderSelectionCache(){ a11yCacheCleared = true; }
function _dockOpenPanel(){}
function _crHideToolbar(){}
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
  if (failNextRequest) {
    failNextRequest = false;
    throw new Error('network unavailable');
  }
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
const _CR_READER_SPAN_LOCATOR_PREFIX = 'reader-span:v1:';
function _crStringList(value){ return Array.isArray(value) ? value.filter(v => typeof v === 'string' && v.trim()).map(v => v.trim()) : []; }
function _crUniqueStringList(values){ return Array.from(new Set((values || []).filter(v => typeof v === 'string' && v.trim()).map(v => v.trim()))); }
function _crProjectionExtractionIds(ex){ return _crUniqueStringList([ex?.id || '', ex?.source_extraction_id || '']); }
function _crProjectionSourceLocators(ex, fallbackLocator = ''){ return _crUniqueStringList([ex?.source_locator || '', fallbackLocator]); }
function _crReaderBlockContext(ex, blockIndex, page = _crPage){
  return {
    block_index: Number.isFinite(Number(blockIndex)) ? Number(blockIndex) : null,
    page: page || null,
    source_locator: ex?.source_locator || '',
    source_locators: _crProjectionSourceLocators(ex),
    extraction_ids: _crProjectionExtractionIds(ex),
  };
}
function _crReaderSpanPoint(info){
  const blockIndex = Number(info?.block_index);
  const offset = Number(info?.offset);
  return {
    block_index: Number.isFinite(blockIndex) ? blockIndex : null,
    source_locator: info?.source_locator || '',
    source_locators: _crUniqueStringList([...(info?.source_locators || []), info?.source_locator || '']),
    extraction_ids: _crUniqueStringList([...(info?.extraction_ids || []), info?.extraction_id || '']),
    offset: Number.isFinite(offset) ? offset : null,
  };
}

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
function input(value=''){ return { value, checked: false, style: {}, textContent: '', innerHTML: '', focus(){} }; }
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
    assert result["locator"].startswith("reader-span:v1:")
    assert "p1%3Ablock0" in result["locator"]
    assert "p1%3Ablock1" in result["locator"]


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


def test_partial_drag_selection_resolves_state_and_shows_toolbar_without_persisting() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b0.textEl,
  endContainer: b0.textEl,
  commonAncestorContainer: b0.textEl,
  startOffset: 0,
  endOffset: 5,
  cloneRange(){ return this; },
  cloneContents(){ return { querySelectorAll(){ return []; } }; },
  toString(){ return 'First'; },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 41, bottom: 61, width: 30, height: 40 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return 'First'; } };
_crHandleSelection({ target: b0.textEl, clientX: 20, clientY: 30 });
process.stdout.write(JSON.stringify({
  text: _crReaderSelectionState && _crReaderSelectionState.text,
  toolbar: !!_crSelToolbar,
  payload: savedPayload,
}));
"""
    )

    assert result == {"text": "First", "toolbar": True, "payload": None}


def test_one_character_reader_source_selection_shows_toolbar() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b0.textEl,
  endContainer: b0.textEl,
  commonAncestorContainer: b0.textEl,
  startOffset: 0,
  endOffset: 1,
  cloneRange(){ return this; },
  cloneContents(){ return { querySelectorAll(){ return []; } }; },
  toString(){ return 'F'; },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 14, bottom: 41, width: 3, height: 20 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return 'F'; } };
_crHandleSelection({ target: b0.textEl });
process.stdout.write(JSON.stringify({
  text: _crReaderSelectionState && _crReaderSelectionState.text,
  toolbar: !!_crSelToolbar,
  payload: savedPayload,
}));
"""
    )

    assert result == {"text": "F", "toolbar": True, "payload": None}


def test_two_character_reader_source_selection_shows_toolbar() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b0.textEl,
  endContainer: b0.textEl,
  commonAncestorContainer: b0.textEl,
  startOffset: 0,
  endOffset: 2,
  cloneRange(){ return this; },
  cloneContents(){ return { querySelectorAll(){ return []; } }; },
  toString(){ return 'Fi'; },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 16, bottom: 41, width: 5, height: 20 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return 'Fi'; } };
_crHandleSelection({ target: b0.textEl });
process.stdout.write(JSON.stringify({
  text: _crReaderSelectionState && _crReaderSelectionState.text,
  toolbar: !!_crSelToolbar,
  payload: savedPayload,
}));
"""
    )

    assert result == {"text": "Fi", "toolbar": True, "payload": None}


def test_whitespace_only_reader_source_selection_stays_rejected() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b0.textEl,
  endContainer: b0.textEl,
  commonAncestorContainer: b0.textEl,
  startOffset: 0,
  endOffset: 2,
  cloneRange(){ return this; },
  cloneContents(){ return { querySelectorAll(){ return []; } }; },
  toString(){ return '  '; },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 16, bottom: 41, width: 5, height: 20 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return '  '; } };
_crHandleSelection({ target: b0.textEl });
process.stdout.write(JSON.stringify({
  selectionState: _crReaderSelectionState,
  toolbar: !!_crSelToolbar,
  payload: savedPayload,
}));
"""
    )

    assert result == {"selectionState": None, "toolbar": False, "payload": None}


def test_double_click_word_selection_resolves_through_same_transient_state() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b1.textEl,
  endContainer: b1.textEl,
  commonAncestorContainer: b1.textEl,
  startOffset: 7,
  endOffset: 16,
  cloneRange(){ return this; },
  cloneContents(){ return { querySelectorAll(){ return []; } }; },
  toString(){ return 'projected'; },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 41, bottom: 61, width: 30, height: 40 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return 'projected'; } };
_crHandleSelectionChange();
process.stdout.write(JSON.stringify({
  text: _crReaderSelectionState && _crReaderSelectionState.text,
  toolbar: !!_crSelToolbar,
  sourceLocators: _crReaderSelectionState && _crReaderSelectionState.source_locators,
}));
"""
    )

    assert result == {
        "text": "projected",
        "toolbar": True,
        "sourceLocators": ["p1:block1"],
    }


def test_full_parsed_block_selection_resolves_from_projected_source_node() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b1.block,
  endContainer: b1.block,
  commonAncestorContainer: b1.block,
  startOffset: 0,
  endOffset: 1,
  cloneRange(){ return this; },
  intersectsNode(node){ return node === b1.textEl; },
  cloneContents(){
    return { querySelectorAll(sel){ return sel === '.cr-page-text' ? [{ textContent: b1.textEl.textContent }] : []; } };
  },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 41, bottom: 61, width: 30, height: 40 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return b1.textEl.textContent; } };
_crHandleSelection({ target: b1.block });
process.stdout.write(JSON.stringify({
  text: _crReaderSelectionState && _crReaderSelectionState.text,
  toolbar: !!_crSelToolbar,
  startOffset: _crReaderSelectionState && _crReaderSelectionState.start.offset,
  endOffset: _crReaderSelectionState && _crReaderSelectionState.end.offset,
  blocks: _crReaderSelectionState && _crReaderSelectionState.blocks.map(b => b.block_index),
}));
"""
    )

    assert result == {
        "text": "Second projected source line with “Unicode” — punctuation.",
        "toolbar": True,
        "startOffset": 0,
        "endOffset": len("Second projected source line with “Unicode” — punctuation."),
        "blocks": [1],
    }


def test_full_logical_span_selection_resolves_all_projected_source_blocks() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: pageView,
  endContainer: pageView,
  commonAncestorContainer: pageView,
  startOffset: 0,
  endOffset: 3,
  cloneRange(){ return this; },
  intersectsNode(node){ return node === b0.textEl || node === b1.textEl || node === b2.textEl; },
  cloneContents(){
    return { querySelectorAll(sel){ return sel === '.cr-page-text' ? [
      { textContent: b0.textEl.textContent },
      { textContent: b1.textEl.textContent },
      { textContent: b2.textEl.textContent },
    ] : []; } };
  },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 41, bottom: 61, width: 30, height: 40 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return 'browser raw text'; } };
_crHandleSelectionChange();
process.stdout.write(JSON.stringify({
  text: _crReaderSelectionState && _crReaderSelectionState.text,
  toolbar: !!_crSelToolbar,
  sourceLocators: _crReaderSelectionState && _crReaderSelectionState.source_locators,
  blocks: _crReaderSelectionState && _crReaderSelectionState.blocks.map(b => b.block_index),
}));
"""
    )

    assert result == {
        "text": (
            "First projected source line.\n\n"
            "Second projected source line with “Unicode” — punctuation.\n\n"
            "Final source line: end."
        ),
        "toolbar": True,
        "sourceLocators": ["p1:block0", "p1:block1", "p1:block2"],
        "blocks": [0, 1, 2],
    }


def test_keyboard_selection_event_path_updates_the_same_state() -> None:
    result = _run_node(
        r"""
const range = {
  startContainer: b2.textEl,
  endContainer: b2.textEl,
  commonAncestorContainer: b2.textEl,
  startOffset: 0,
  endOffset: 12,
  cloneRange(){ return this; },
  cloneContents(){ return { querySelectorAll(){ return []; } }; },
  toString(){ return 'Final source'; },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 41, bottom: 61, width: 30, height: 40 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return 'Final source'; } };
_crHandleSelection({ target: b2.textEl, key: 'ArrowRight' });
process.stdout.write(JSON.stringify({
  text: _crReaderSelectionState && _crReaderSelectionState.text,
  toolbar: !!_crSelToolbar,
  rangeText: _crSelRange && _crSelRange.toString(),
}));
"""
    )

    assert result == {"text": "Final source", "toolbar": True, "rangeText": "Final source"}


def test_clicking_persisted_highlight_does_not_start_new_capture_toolbar() -> None:
    result = _run_node(
        r"""
const mark = {
  nodeType: Node.ELEMENT_NODE,
  dataset: { highlightId: 'hl-1' },
  closest(sel){ return sel.includes('.cr-inline-highlight') || sel.includes('[data-highlight-id]') ? mark : null; },
};
const range = {
  startContainer: b0.textEl,
  endContainer: b0.textEl,
  commonAncestorContainer: b0.textEl,
  cloneRange(){ return this; },
  cloneContents(){ return { querySelectorAll(){ return []; } }; },
  toString(){ return 'First projected'; },
  getBoundingClientRect(){ return { left: 11, top: 21, right: 41, bottom: 61, width: 30, height: 40 }; },
};
activeSelection = { rangeCount: 1, isCollapsed: false, getRangeAt(){ return range; }, toString(){ return 'First projected'; } };
_crHandleSelection({ target: mark });
process.stdout.write(JSON.stringify({
  toolbar: !!_crSelToolbar,
  captureOpen: _crCaptureOpen,
  selectionState: _crReaderSelectionState,
}));
"""
    )

    assert result == {"toolbar": False, "captureOpen": False, "selectionState": None}


def test_toolbar_read_action_uses_exact_resolved_selection_state() -> None:
    result = _run_node(
        r"""
_crReaderSelectionState = {
  valid: true,
  text: 'Exact structural Reader text',
  source_locators: ['p1:block0'],
  blocks: [{ block_index: 0 }],
  page: 1,
};
_crSelText = 'Exact structural Reader text';
activeSelection = { rangeCount: 1, isCollapsed: false, toString(){ return 'Raw browser text with UI chrome'; } };
_crReadResolvedSelection();
process.stdout.write(JSON.stringify({ spokenText }));
"""
    )

    assert result == {"spokenText": "Exact structural Reader text"}


def test_clearing_reader_selection_invalidates_reading_tools_cache() -> None:
    result = _run_node(
        r"""
_crReaderSelectionState = {
  valid: true,
  text: 'Reader text that should not linger',
  source_locators: ['p1:block0'],
  blocks: [{ block_index: 0 }],
  page: 1,
};
_crSelRange = { detached: true };
_crClearReaderSelectionState();
process.stdout.write(JSON.stringify({
  fallback: _crGetReaderSelection({ refresh: false, fallback: true }),
  range: _crSelRange,
  cacheCleared: a11yCacheCleared,
}));
"""
    )

    assert result == {"fallback": None, "range": None, "cacheCleared": True}


def test_reader_context_reset_clears_stale_toolbar_passage_text() -> None:
    result = _run_node(
        r"""
_crReaderSelectionState = {
  valid: true,
  text: 'Old page Reader text',
  source_locators: ['p1:block0'],
  blocks: [{ block_index: 0 }],
  page: 1,
};
_crSelRange = { detached: true };
_crSelText = 'Old page Reader text';
_crSelectionRect = { left: 10, top: 20, right: 40, bottom: 60 };
_crSelToolbar = { removed: false, remove(){ this.removed = true; } };
_crResetReaderTransientSelectionForContext();
_crReadResolvedSelection();
process.stdout.write(JSON.stringify({
  fallback: _crGetReaderSelection({ refresh: false, fallback: true }),
  range: _crSelRange,
  selectedText: _crSelText,
  rect: _crSelectionRect,
  toolbar: _crSelToolbar,
  spokenText,
  cacheCleared: a11yCacheCleared,
}));
"""
    )

    assert result == {
        "fallback": None,
        "range": None,
        "selectedText": "",
        "rect": None,
        "toolbar": None,
        "spokenText": "",
        "cacheCleared": True,
    }


def test_new_highlight_note_input_starts_empty_with_placeholder_guidance() -> None:
    result = _run_node(
        r"""
_crReaderSelectionState = {
  valid: true,
  text: 'First projected source line.',
  source_locators: ['p1:block0'],
  blocks: [{ block_index: 0 }],
  page: 1,
};
_crSelText = 'First projected source line.';
_crHighlightSelected('note');
const html = _crSelToolbar.innerHTML;
const match = html.match(/<textarea id="cr-note-input"[^>]*placeholder="([^"]*)"[^>]*>([\s\S]*?)<\/textarea>/);
process.stdout.write(JSON.stringify({
  placeholder: match && match[1],
  value: match && match[2],
  containsSynthetic: html.includes('Candidate for observation.'),
}));
"""
    )

    assert result == {
        "placeholder": "Your reading note…",
        "value": "",
        "containsSynthetic": False,
    }


def test_new_observation_candidate_note_input_still_starts_empty() -> None:
    result = _run_node(
        r"""
_crReaderSelectionState = {
  valid: true,
  text: 'First projected source line.',
  source_locators: ['p1:block0'],
  blocks: [{ block_index: 0 }],
  page: 1,
};
_crSelText = 'First projected source line.';
_crHighlightSelected('candidate');
const html = _crSelToolbar.innerHTML;
const match = html.match(/<textarea id="cr-note-input"[^>]*placeholder="([^"]*)"[^>]*>([\s\S]*?)<\/textarea>/);
process.stdout.write(JSON.stringify({
  importantChecked: html.includes('id="cr-important-input" type="checkbox" checked'),
  placeholder: match && match[1],
  value: match && match[2],
  containsSynthetic: html.includes('Candidate for observation.'),
}));
"""
    )

    assert result == {
        "importantChecked": True,
        "placeholder": "Your reading note…",
        "value": "",
        "containsSynthetic": False,
    }


def test_cancel_clears_transient_reader_selection_state() -> None:
    result = _run_node(
        r"""
_crReaderSelectionState = {
  valid: true,
  text: 'First projected source line.',
  source_locators: ['p1:block0'],
  blocks: [{ block_index: 0 }],
  page: 1,
};
_crSelRange = { detached: true };
_crSelText = 'First projected source line.';
_crCancelHighlight();
process.stdout.write(JSON.stringify({
  fallback: _crGetReaderSelection({ refresh: false, fallback: true }),
  range: _crSelRange,
  selectedText: _crSelText,
}));
"""
    )

    assert result == {"fallback": None, "range": None, "selectedText": ""}


def test_successful_save_ack_clears_transient_reader_selection_state() -> None:
    result = _run_node(
        r"""
(async () => {
  _crReaderSelectionState = {
    valid: true,
    text: 'First projected source line.',
    source_locators: ['p1:block0'],
    blocks: [{ block_index: 0 }],
    page: 1,
  };
  _crSelRange = { detached: true };
  _crSelText = 'First projected source line.';
  await _crSaveHighlight(false);
  process.stdout.write(JSON.stringify({
    fallback: _crGetReaderSelection({ refresh: false, fallback: true }),
    range: _crSelRange,
    selectedText: _crSelText,
    savedText: savedPayload.selected_text,
  }));
})();
"""
    )

    assert result == {
        "fallback": None,
        "range": None,
        "selectedText": "",
        "savedText": "First projected source line.",
    }


def test_failed_save_preserves_transient_reader_selection_state_for_retry() -> None:
    result = _run_node(
        r"""
(async () => {
  _crReaderSelectionState = {
    valid: true,
    text: 'First projected source line.',
    source_locators: ['p1:block0'],
    blocks: [{ block_index: 0 }],
    page: 1,
  };
  _crSelRange = { detached: true };
  _crSelText = 'First projected source line.';
  failNextRequest = true;
  await _crSaveHighlight(false);
  const fallback = _crGetReaderSelection({ refresh: false, fallback: true });
  process.stdout.write(JSON.stringify({
    fallbackText: fallback && fallback.text,
    rangeStillPresent: _crSelRange && _crSelRange.detached === true,
    selectedText: _crSelText,
    errorMessage: elements['cr-capture-msg'].textContent,
  }));
})();
"""
    )

    assert result == {
        "fallbackText": "First projected source line.",
        "rangeStillPresent": True,
        "selectedText": "First projected source line.",
        "errorMessage": "network unavailable",
    }
