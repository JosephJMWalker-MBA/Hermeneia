from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
SPAN_PREFIX = "reader-span:v1:"


def _extract_fn(html: str, name: str) -> str:
    match = re.search(
        r"\n(?:async\s+)?function " + re.escape(name) + r"\(.*?\n\}\n",
        html,
        re.S,
    )
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def _run_node(script: str, payload: object | None = None) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader highlight reopen tests")
    html = INDEX.read_text()
    helpers = [
        "_crStringList",
        "_crUniqueStringList",
        "_crProjectionExtractionIds",
        "_crProjectionSourceLocators",
        "_crReaderBlockContext",
        "_crIsReaderSpanLocator",
        "_crDecodeReaderSpanLocator",
        "_crInlineHighlightClass",
        "_crFiniteNumber",
        "_crTextOffset",
        "_crHasAnyValue",
        "_crHasComparableProvenance",
        "_crSpanHasProvenance",
        "_crBlockProvenanceWithinSpan",
        "_crBlockMatchesSpan",
        "_crBlockMatchesSpanPoint",
        "_crSpanRangeForBlock",
        "_crPushNonOverlappingRange",
        "_crHighlightSortKey",
        "_crSortedHighlightsForSegment",
        "_crHumanHighlightTitle",
        "_crHumanSegmentsFromRanges",
        "_crRenderTextWithHighlights",
        "_crMachineHighlightClass",
        "_crNodeElement",
        "_crHighlightIdsFromMark",
        "_crShowHighlightChooser",
        "_crOpenPersistedHighlightFromEvent",
        "_crShowHighlightDetail",
        "_crUpdateHighlight",
    ]
    harness = (
        r"""
const Node = { ELEMENT_NODE: 1 };
let _crDocId = 'doc-1';
let _crPage = 1;
let _crHighlights = [];
let _crRelevance = 'unclear';
let _crReaderSelectionState = { stale: true };
let _crSelRange = { stale: true };
let _crSelText = 'stale selected text';
let _crCaptureOpen = true;
let _crSelectionRect = { stale: true };
let openedPanel = '';
let msgPayload = null;
let patchedUrl = '';
let loadHighlightListCalls = 0;
let renderPageCalls = 0;
let refreshTrailCalls = 0;
function x(s){return String(s==null?'':s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function _dockOpenPanel(key){ openedPanel = key; }
function _crHideToolbar(){}
function _crClearPending(){}
function _crClearReaderSelectionState(){ _crReaderSelectionState = null; _crSelRange = null; }
function cmpMarkOnboardingStep(){}
function _crBindHighlightEditDraft(){}
function _crHighlightEditDraftKey(){ return 'edit-draft'; }
function _crStoreHighlightEditDraft(){}
function _authoredDraftClear(){}
async function _crLoadHighlightList(){ loadHighlightListCalls += 1; }
function _crRenderPage(){ renderPageCalls += 1; }
function _crRefreshTrail(){ refreshTrailCalls += 1; }
function _crReadOptionalText(id){ const value = document.getElementById(id)?.value?.trim() || ''; return value || null; }
function _crReadRankValue(id){ const value = document.getElementById(id)?.value; return value ? Number(value) : null; }
function _crRankOptions(selected){ return `<option value="">None</option><option value="4" ${Number(selected)===4?'selected':''}>Strong</option>`; }
function _crParseTypedTags(raw){ return (raw || '').split(',').map(t => t.trim()).filter(Boolean).map(t => t.includes(':') || t === 'important' ? t : `tag:${t}`); }
function _crUniqueTags(tags){ return Array.from(new Set((tags || []).filter(Boolean))); }
const _CR_RANK_LABELS={1:'Speculative',2:'Minor',3:'Useful',4:'Strong',5:'Foundational'};
function _crRankLabel(raw){ const n = Number(raw); return Number.isInteger(n) && n >= 1 && n <= 5 ? `${n} — ${_CR_RANK_LABELS[n]}` : ''; }
function _crHighlightTags(h){ return Array.isArray(h?.tags) ? h.tags.filter(t => typeof t === 'string') : []; }
function _crAnnotationMetaHtml(h){
  const rankLabel = _crRankLabel(h?.rank);
  const theme = (h?.theme_bucket || '').trim();
  const chips = [];
  if (rankLabel) chips.push(`<span>Rank ${x(rankLabel)}</span>`);
  if (theme) chips.push(`<span>Theme ${x(theme)}</span>`);
  return chips.length ? `<div>${chips.join('')}</div>` : '';
}
async function requestJSON(url, opts){ patchedUrl = url; msgPayload = opts.body; return { ok: true }; }
function setTimeout(fn){ fn(); }
const elements = {
  'cr-sel-form': { style: {}, innerHTML: '', scrollIntoView(){ this.scrolled = true; } },
  'cr-sel-prompt': { style: {}, innerHTML: '' },
  'cr-edit-note': { value: '' },
  'cr-edit-q': { value: '' },
  'cr-edit-important': { checked: false },
  'cr-edit-tags': { value: '' },
  'cr-edit-rank': { value: '' },
  'cr-edit-theme': { value: '' },
  'cr-edit-evidence': { value: '' },
  'cr-edit-msg': { textContent: '', style: {} },
};
const document = {
  getElementById(id){ return elements[id] || null; },
};
const window = {
  getSelection(){ return { removed: false, removeAllRanges(){ this.removed = true; selectionCleared = true; } }; },
};
let selectionCleared = false;
const _CR_READER_SPAN_LOCATOR_PREFIX = 'reader-span:v1:';
const inputPayload = JSON.parse(process.argv[1] || '{}');
"""
        + "".join(_extract_fn(html, name) for name in helpers)
        + script
    )
    result = subprocess.run(
        [node, "-e", harness, "--", json.dumps(payload or {})],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _span_locator() -> str:
    payload = {
        "page": 39,
        "start": {
            "block_index": 1,
            "source_locator": "page:39:block:1",
            "source_locators": ["page:39:block:1"],
            "extraction_ids": ["ext-1"],
            "offset": 4,
        },
        "end": {
            "block_index": 3,
            "source_locator": "page:39:block:3",
            "source_locators": ["page:39:block:3"],
            "extraction_ids": ["ext-3"],
            "offset": 8,
        },
        "source_locators": [
            "page:39:block:1",
            "page:39:block:2",
            "page:39:block:3",
        ],
        "extraction_ids": ["ext-1", "ext-2", "ext-3"],
    }
    return SPAN_PREFIX + quote(json.dumps(payload, separators=(",", ":")), safe="")


def test_clicking_single_block_visible_mark_reopens_existing_inspector_record() -> None:
    result = _run_node(
        r"""
_crHighlights = [{
  id: 'hl-single',
  page: 1,
  status: 'saved_highlight',
  selected_text: 'beta',
  note_text: 'Existing note',
  question_text: 'Existing question?',
  relevance: 'supports',
  tags: ['important', 'tag:tension'],
  rank: 4,
  theme_bucket: 'aspiration',
  evidence_bucket: 'draft-1',
}];
const html = _crRenderTextWithHighlights('alpha beta gamma', _crHighlights, [], {
  block_index: 0,
  page: 1,
  source_locators: ['page:1:block:1'],
  extraction_ids: ['ext-1'],
});
const mark = { nodeType: Node.ELEMENT_NODE, dataset: { highlightId: 'hl-single' }, closest(sel){ return sel.includes('[data-highlight-id]') ? mark : null; } };
let prevented = false;
let stopped = false;
_crOpenPersistedHighlightFromEvent({ target: mark, preventDefault(){ prevented = true; }, stopPropagation(){ stopped = true; } });
process.stdout.write(JSON.stringify({
  html,
  openedPanel,
  prevented,
  stopped,
  selectionCleared,
  staleSelectionCleared: _crReaderSelectionState === null && _crSelRange === null && _crSelText === '',
  promptDisplay: elements['cr-sel-prompt'].style.display,
  form: elements['cr-sel-form'].innerHTML,
}));
"""
    )

    assert 'data-highlight-id="hl-single"' in result["html"]
    assert result["openedPanel"] == "inspector"
    assert result["prevented"] is True
    assert result["stopped"] is True
    assert result["selectionCleared"] is True
    assert result["staleSelectionCleared"] is True
    assert result["promptDisplay"] == "none"
    assert "Existing note" in result["form"]
    assert "Existing question?" in result["form"]
    assert "aspiration" in result["form"]
    assert "draft-1" in result["form"]
    assert "_crUpdateHighlight('hl-single')" in result["form"]


def test_clicking_any_multiblock_fragment_reopens_same_highlight_id() -> None:
    result = _run_node(
        r"""
_crHighlights = [{
  id: 'hl-multi',
  page: 39,
  status: 'saved_highlight',
  selected_text: 'multiblock passage',
  source_locator: inputPayload.locator,
  note_text: 'Shared note',
  question_text: '',
  relevance: 'unclear',
  tags: [],
}];
const blocks = ['aaaa selected-start', 'middle selected', 'selected-end zzzz'];
const locators = ['page:39:block:1', 'page:39:block:2', 'page:39:block:3'];
const ids = ['ext-1', 'ext-2', 'ext-3'];
const htmls = blocks.map((text, idx) => _crRenderTextWithHighlights(text, _crHighlights, [], {
  block_index: idx + 1,
  page: 39,
  source_locator: locators[idx],
  source_locators: [locators[idx]],
  extraction_ids: [ids[idx]],
}));
const opened = [];
for (let i = 0; i < 3; i += 1) {
  const mark = { nodeType: Node.ELEMENT_NODE, dataset: { highlightId: 'hl-multi' }, closest(sel){ return sel.includes('[data-highlight-id]') ? mark : null; } };
  _crOpenPersistedHighlightFromEvent({ target: mark, preventDefault(){}, stopPropagation(){} });
  opened.push(openedPanel);
}
process.stdout.write(JSON.stringify({htmls, opened, form: elements['cr-sel-form'].innerHTML}));
""",
        {"locator": _span_locator()},
    )

    assert all(html.count('data-highlight-id="hl-multi"') == 1 for html in result["htmls"])
    assert result["opened"] == ["inspector", "inspector", "inspector"]
    assert "Shared note" in result["form"]
    assert "_crUpdateHighlight('hl-multi')" in result["form"]


def test_clicking_unrelated_reader_text_does_not_open_inspector() -> None:
    result = _run_node(
        r"""
const ordinary = { nodeType: Node.ELEMENT_NODE, dataset: {}, closest(){ return null; } };
let prevented = false;
_crOpenPersistedHighlightFromEvent({ target: ordinary, preventDefault(){ prevented = true; }, stopPropagation(){} });
process.stdout.write(JSON.stringify({openedPanel, prevented, selectionStateStillPresent: !!_crReaderSelectionState}));
"""
    )

    assert result == {
        "openedPanel": "",
        "prevented": False,
        "selectionStateStillPresent": True,
    }


def test_editing_reopened_highlight_saves_same_record_payload() -> None:
    result = _run_node(
        r"""
(async () => {
  _crHighlights = [{
    id: 'hl-edit',
    source_document_id: 'doc-1',
    page: 1,
    status: 'saved_highlight',
    selected_text: 'beta',
    note_text: 'Old note',
    question_text: 'Old question?',
    relevance: 'supports',
    tags: ['important', 'tag:old', 'concept:witness'],
    rank: 4,
    theme_bucket: 'old-theme',
    evidence_bucket: 'old-evidence',
  }];
  await _crShowHighlightDetail('hl-edit');
  elements['cr-edit-note'].value = 'New note';
  elements['cr-edit-q'].value = 'New question?';
  elements['cr-edit-important'].checked = true;
  elements['cr-edit-tags'].value = 'new, second';
  elements['cr-edit-rank'].value = '4';
  elements['cr-edit-theme'].value = 'new-theme';
  elements['cr-edit-evidence'].value = 'draft-2';
  _crRelevance = 'complicates';
  await _crUpdateHighlight('hl-edit');
  process.stdout.write(JSON.stringify({patchedUrl, msgPayload, renderPageCalls, refreshTrailCalls}));
})();
"""
    )

    assert result["patchedUrl"] == "/api/reader/highlights/hl-edit"
    assert result["msgPayload"]["note_text"] == "New note"
    assert result["msgPayload"]["question_text"] == "New question?"
    assert result["msgPayload"]["relevance"] == "complicates"
    assert result["msgPayload"]["rank"] == 4
    assert result["msgPayload"]["theme_bucket"] == "new-theme"
    assert result["msgPayload"]["evidence_bucket"] == "draft-2"
    assert result["msgPayload"]["tags"] == [
        "concept:witness",
        "important",
        "tag:new",
        "tag:second",
    ]
    assert result["renderPageCalls"] == 1
    assert result["refreshTrailCalls"] == 1


def test_identical_overlapping_highlights_click_shows_durable_id_chooser() -> None:
    result = _run_node(
        r"""
_crHighlights = [
  {id: 'hl-b', page: 1, status: 'saved_highlight', selected_text: 'beta', note_text: 'Second', created_at: '2026-01-02T00:00:00Z'},
  {id: 'hl-a', page: 1, status: 'saved_highlight', selected_text: 'beta', note_text: 'First', created_at: '2026-01-01T00:00:00Z'},
];
const html = _crRenderTextWithHighlights('alpha beta gamma', _crHighlights, [], {
  block_index: 0,
  page: 1,
  source_locators: ['page:1:block:1'],
  extraction_ids: ['ext-1'],
});
const mark = { nodeType: Node.ELEMENT_NODE, dataset: { highlightIds: 'hl-a,hl-b' }, closest(sel){ return sel.includes('[data-highlight-ids]') ? mark : null; } };
_crOpenPersistedHighlightFromEvent({ target: mark, preventDefault(){}, stopPropagation(){} });
process.stdout.write(JSON.stringify({html, openedPanel, form: elements['cr-sel-form'].innerHTML}));
"""
    )

    assert 'data-highlight-ids="hl-a,hl-b"' in result["html"]
    assert 'data-highlight-id=' not in result["html"]
    assert result["openedPanel"] == "inspector"
    assert "Overlapping highlights" in result["form"]
    assert result["form"].index("hl-a") < result["form"].index("hl-b")
    assert "First" in result["form"]
    assert "Second" in result["form"]


def test_partial_overlap_segments_expose_only_actual_membership() -> None:
    result = _run_node(
        r"""
_crHighlights = [
  {id: 'hl-left', page: 1, status: 'saved_highlight', selected_text: 'beta gamma', created_at: '2026-01-01T00:00:00Z'},
  {id: 'hl-right', page: 1, status: 'saved_highlight', selected_text: 'gamma delta', created_at: '2026-01-02T00:00:00Z'},
];
const html = _crRenderTextWithHighlights('alpha beta gamma delta epsilon', _crHighlights, [], {
  block_index: 0,
  page: 1,
  source_locators: ['page:1:block:1'],
  extraction_ids: ['ext-1'],
});
process.stdout.write(JSON.stringify({html}));
"""
    )

    html = result["html"]
    assert 'data-highlight-id="hl-left"' in html
    assert '>beta </span>' in html
    assert 'data-highlight-ids="hl-left,hl-right"' in html
    assert '>gamma</span>' in html
    assert 'data-highlight-id="hl-right"' in html
    assert '> delta</span>' in html


def test_chooser_entry_opens_exact_selected_record_metadata() -> None:
    result = _run_node(
        r"""
(async () => {
  _crHighlights = [
    {id: 'hl-a', page: 1, status: 'saved_highlight', selected_text: 'beta', note_text: 'A note', relevance: 'supports', tags: [], created_at: '2026-01-01T00:00:00Z'},
    {id: 'hl-b', page: 1, status: 'saved_highlight', selected_text: 'beta', note_text: 'B note', relevance: 'complicates', tags: [], created_at: '2026-01-02T00:00:00Z'},
  ];
  await _crShowHighlightChooser(['hl-b', 'hl-a']);
  const chooser = elements['cr-sel-form'].innerHTML;
  await _crShowHighlightDetail('hl-b');
  process.stdout.write(JSON.stringify({chooser, detail: elements['cr-sel-form'].innerHTML}));
})();
"""
    )

    assert result["chooser"].index("hl-a") < result["chooser"].index("hl-b")
    assert "B note" in result["detail"]
    assert "_crUpdateHighlight('hl-b')" in result["detail"]
    assert "A note" not in result["detail"]


def test_patch_updates_original_highlight_without_duplicate_or_canonical_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "reader_reopen.db"
    SQLiteStore(db_path).close()
    doc_id = "a" * 64
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 1, now, "test", "primary", 0),
    )
    conn.execute(
        """INSERT INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "ext-1",
            doc_id,
            1,
            "block:0",
            "alpha beta gamma",
            "test",
            "test",
            "{}",
            "page:1:block:1",
            "hash",
            "ext-hash",
            now,
        ),
    )
    conn.commit()
    before = conn.execute("SELECT id, raw_text FROM source_extractions").fetchall()
    conn.close()

    client = create_app(db_path=db_path).test_client()
    created = client.post(
        "/api/reader/highlights",
        json={
            "source_document_id": doc_id,
            "page": 1,
            "source_locator": "page:1:block:1",
            "selected_text": "beta",
            "note_text": "Old note",
            "question_text": "Old question?",
            "relevance": "supports",
            "tags": ["important"],
            "rank": 4,
            "theme_bucket": "old-theme",
            "evidence_bucket": "old-evidence",
        },
    )
    assert created.status_code == 201
    highlight_id = created.get_json()["id"]

    updated = client.patch(
        f"/api/reader/highlights/{highlight_id}",
        json={
            "note_text": "New note",
            "question_text": "New question?",
            "relevance": "complicates",
            "tags": ["important", "tag:new"],
            "rank": 5,
            "theme_bucket": "new-theme",
            "evidence_bucket": "draft-2",
        },
    )
    assert updated.status_code == 200

    verify = sqlite3.connect(db_path)
    verify.row_factory = sqlite3.Row
    rows = verify.execute("SELECT * FROM reader_highlights").fetchall()
    after = [
        tuple(row)
        for row in verify.execute("SELECT id, raw_text FROM source_extractions").fetchall()
    ]
    verify.close()

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == highlight_id
    assert row["selected_text"] == "beta"
    assert row["note_text"] == "New note"
    assert row["question_text"] == "New question?"
    assert row["relevance"] == "complicates"
    assert json.loads(row["tags"]) == ["important", "tag:new"]
    assert row["rank"] == 5
    assert row["theme_bucket"] == "new-theme"
    assert row["evidence_bucket"] == "draft-2"
    assert after == before
