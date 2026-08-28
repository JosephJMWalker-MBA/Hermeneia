from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"\n(?:async\s+)?function " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def test_reader_capture_and_edit_forms_expose_rank_and_theme_bucket_controls():
    index_html = INDEX.read_text()

    assert 'id="cr-rank-input"' in index_html
    assert 'id="cr-theme-input"' in index_html
    assert 'id="cr-edit-rank"' in index_html
    assert 'id="cr-edit-theme"' in index_html
    assert "How much weight should this mark carry?" in index_html
    assert "What kind of meaning does this belong to?" in index_html
    assert "Speculative" in index_html
    assert "Foundational" in index_html
    assert "_crRankOptions(null)" in index_html
    assert "_crRankOptions(h.rank)" in index_html
    assert "theme_bucket: themeBucket" in index_html
    assert "_crReadRankValue('cr-rank-input')" in index_html
    assert "_crReadRankValue('cr-edit-rank')" in index_html


def test_reader_ui_keeps_evidence_bucket_separate_from_theme_bucket():
    index_html = INDEX.read_text()

    assert "theme_bucket: themeBucket" in index_html
    assert "evidence_bucket: evidenceBucket" in index_html
    assert 'id="cr-edit-evidence"' in index_html
    assert "Optional working set membership, separate from theme." in index_html


def test_rank_theme_glance_only_renders_when_present():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader annotation UI helper test")

    html = INDEX.read_text()
    harness = (
        "function x(s){return String(s==null?'':s)"
        ".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}\n"
        "const _CR_RANK_LABELS={1:'Speculative',2:'Minor',3:'Useful',4:'Strong',5:'Foundational'};\n"
        + _extract_fn(html, "_crRankLabel")
        + _extract_fn(html, "_crAnnotationMetaHtml")
        + "const samples=JSON.parse(process.argv[1]);\n"
        + "process.stdout.write(JSON.stringify(samples.map(_crAnnotationMetaHtml)));\n"
    )
    payload = json.dumps([
        {},
        {"rank": None, "theme_bucket": ""},
        {"rank": 4, "theme_bucket": "aspiration", "evidence_bucket": "draft-1"},
    ])
    out = subprocess.run(
        [node, "-e", harness, "--", payload],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert out.returncode == 0, out.stderr
    empty, unranked, filled = json.loads(out.stdout)
    assert empty == ""
    assert unranked == ""
    assert "Rank 4 — Strong" in filled
    assert "Theme aspiration" in filled
    assert "Evidence" not in filled


def test_selection_preserving_mousedown_allows_native_capture_controls():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader annotation UI helper test")

    html = INDEX.read_text()
    harness = (
        "const Node = { ELEMENT_NODE: 1 };\n"
        "let _crCaptureOpen = false;\n"
        "let _crSelToolbar = null;\n"
        "let listener = null;\n"
        "const appended = [];\n"
        "const window = { innerWidth: 1200, innerHeight: 800 };\n"
        "const document = {\n"
        "  body: { appendChild(node){ appended.push(node); } },\n"
        "  createElement(){ return { style:{}, offsetWidth:390, offsetHeight:120, remove(){}, addEventListener(type, fn){ if (type === 'mousedown') listener = fn; } }; },\n"
        "};\n"
        "function makeTarget(kind){ return { nodeType: Node.ELEMENT_NODE, parentElement: null, closest(selector){\n"
        "  const parts = selector.split(',').map(s => s.trim());\n"
        "  if (parts.includes(kind)) return this;\n"
        "  if (kind === 'contenteditable' && parts.includes('[contenteditable=\"true\"]')) return this;\n"
        "  return null;\n"
        "} }; }\n"
        + _extract_fn(html, "_crNodeElement")
        + _extract_fn(html, "_crPlaceToolbar")
        + _extract_fn(html, "_crShouldPreserveSelectionMouseDown")
        + _extract_fn(html, "_crHideToolbar")
        + _extract_fn(html, "_crShowToolbar")
        + "function fired(kind){ let prevented = false; listener({ target: makeTarget(kind), preventDefault(){ prevented = true; } }); return prevented; }\n"
        + "_crShowToolbar({left:10,top:10,bottom:20,right:50,width:40,height:10});\n"
        + "process.stdout.write(JSON.stringify({\n"
        + "  button: fired('button'),\n"
        + "  select: fired('select'),\n"
        + "  option: fired('option'),\n"
        + "  input: fired('input'),\n"
        + "  textarea: fired('textarea'),\n"
        + "  label: fired('label'),\n"
        + "  contenteditable: fired('contenteditable'),\n"
        + "  listenerInstalled: typeof listener === 'function',\n"
        + "  toolbarAppended: appended.length === 1,\n"
        + "}));\n"
    )
    out = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {
        "button": True,
        "select": False,
        "option": False,
        "input": False,
        "textarea": False,
        "label": False,
        "contenteditable": False,
        "listenerInstalled": True,
        "toolbarAppended": True,
    }


def test_capture_save_reads_rank_once_without_changing_reader_selection():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader annotation UI helper test")

    html = INDEX.read_text()
    harness = (
        "let _crDocId = 'doc-1';\n"
        "let _crPage = 7;\n"
        "let _crSelText = 'The sea never asked permission.';\n"
        "let _crReaderSelectionState = { valid:true, text:'The sea never asked permission.', source_locators:['page:7:block:1'], blocks:[{block_index:1}], page:7 };\n"
        "let _crSelRange = { detached:true };\n"
        "let _crCaptureOpen = true;\n"
        "let _crConcept = '';\n"
        "let _crRelevance = 'unclear';\n"
        "let _crSelectionRect = { left:1, top:2, bottom:3, right:4 };\n"
        "let savedPayload = null;\n"
        "let requestCount = 0;\n"
        "const elements = {\n"
        "  'cr-note-input': { value:'ranked note' },\n"
        "  'cr-q-input': { value:'' },\n"
        "  'cr-important-input': { checked:false },\n"
        "  'cr-tags-input': { value:'' },\n"
        "  'cr-rank-input': { value:'4' },\n"
        "  'cr-theme-input': { value:'' },\n"
        "  'cr-capture-msg': { textContent:'', style:{} },\n"
        "  'cr-sel-prompt': { textContent:'', style:{}, innerHTML:'' },\n"
        "};\n"
        "const document = { getElementById(id){ return elements[id] || null; }, querySelectorAll(sel){ return sel === '#cr-page-view .cr-page-text' ? [{ textContent:'The sea never asked permission.' }] : []; } };\n"
        "const window = { getSelection(){ return { removeAllRanges(){} }; } };\n"
        "function _crGetReaderSelection(){ return _crReaderSelectionState; }\n"
        "function _crNewHighlightDraftKey(){ return 'draft-key'; }\n"
        "function _crStoreNewHighlightDraft(){}\n"
        "function _authoredDraftClear(){}\n"
        "async function _crLoadHighlightList(){}\n"
        "function _crRenderPage(){}\n"
        "function _crRefreshTrail(){}\n"
        "function _crHideToolbar(){}\n"
        "function _crClearPending(){}\n"
        "function _crClearReaderSelectionState(){}\n"
        "function _flnActivityTick(){}\n"
        "function _crShowHighlightDetail(){}\n"
        "function cmpMarkOnboardingStep(){}\n"
        "function _crEncodeReaderSpanLocator(){ return 'page:7:block:1'; }\n"
        "function _crReadOptionalText(id){ const value = document.getElementById(id)?.value?.trim() || ''; return value || null; }\n"
        "async function requestJSON(url, opts){ requestCount += 1; savedPayload = opts.body; return { id:'hl-1' }; }\n"
        "function setTimeout(fn){ fn(); }\n"
        + _extract_fn(html, "_crParseTypedTags")
        + _extract_fn(html, "_crUniqueTags")
        + _extract_fn(html, "_crReadRankValue")
        + _extract_fn(html, "_crPageReadingText")
        + _extract_fn(html, "_crSaveHighlight")
        + "(async () => { await _crSaveHighlight(false); process.stdout.write(JSON.stringify({ requestCount, selectedText: savedPayload.selected_text, rank: savedPayload.rank, note: savedPayload.note_text, fallbackText: _crReaderSelectionState && _crReaderSelectionState.text })); })();\n"
    )
    out = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {
        "requestCount": 1,
        "selectedText": "The sea never asked permission.",
        "rank": 4,
        "note": "ranked note",
        "fallbackText": "The sea never asked permission.",
    }
