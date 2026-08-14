"""Reader highlight rendering across projected display blocks.

Invariant: a human Reader highlight is one authored record. Rendering may split
that record across display blocks, but it must not mutate canonical source
extractions or create one highlight row per extraction.
"""
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
    match = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def _renderer_harness() -> str:
    html = INDEX.read_text()
    helpers = [
        "_crStringList",
        "_crUniqueStringList",
        "_crProjectionExtractionIds",
        "_crProjectionSourceLocators",
        "_crReaderBlockContext",
        "_crReaderSpanPoint",
        "_crEncodeReaderSpanLocator",
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
        "_crRenderTextWithHighlights",
        "_crMachineHighlightClass",
    ]
    return (
        "function x(s){return String(s==null?'':s)"
        ".replace(/&/g,'&amp;').replace(/</g,'&lt;')"
        ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');}\n"
        "function _crHighlightTags(h){return (h&&h.tags)||[];}\n"
        f"const _CR_READER_SPAN_LOCATOR_PREFIX='{SPAN_PREFIX}';\n"
        "let _crPage=39;\n"
        + "".join(_extract_fn(html, name) for name in helpers)
    )


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader highlight rendering test")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _span_locator(payload: dict) -> str:
    return SPAN_PREFIX + quote(json.dumps(payload, separators=(",", ":")), safe="")


def test_persisted_multiblock_highlight_renders_suffix_middle_prefix() -> None:
    """A single durable highlight can produce visible fragments in several
    projected Reader blocks while preserving the same highlight ID everywhere.
    """
    script = _renderer_harness() + r"""
const blocks = [
  "Before the paragraph.",
  "The walls displayed photographs of clients on stages, television sets, conference",
  "screens, university lecterns, and magazine covers. A monitor showed a dashboard",
  "titled POST-PUBLICATION CONVERSION PLAN.",
  "After the paragraph. photographs should stay plain here."
];
const locators = blocks.map((_, i) => `page:39:block:${i}`);
const extractionIds = blocks.map((_, i) => `ext-${i}`);
const startOffset = blocks[1].indexOf("photographs");
const endOffset = blocks[3].indexOf(" PLAN");
const selection = {
  valid: true,
  page: 39,
  start: {block_index: 1, source_locator: locators[1], source_locators: [locators[1]], extraction_ids: [extractionIds[1]], offset: startOffset},
  end: {block_index: 3, source_locator: locators[3], source_locators: [locators[3]], extraction_ids: [extractionIds[3]], offset: endOffset},
  blocks: [1, 2, 3].map(i => ({block_index: i, source_locator: locators[i], source_locators: [locators[i]], extraction_ids: [extractionIds[i]]})),
  source_locators: [locators[1], locators[2], locators[3]],
  extraction_ids: [extractionIds[1], extractionIds[2], extractionIds[3]]
};
const highlight = {
  id: "hl-multi",
  page: 39,
  status: "saved_highlight",
  relevance: "unclear",
  selected_text: blocks[1].slice(startOffset) + "\n\n" + blocks[2] + "\n\n" + blocks[3].slice(0, endOffset),
  source_locator: _crEncodeReaderSpanLocator(selection)
};
const htmls = blocks.map((text, i) => _crRenderTextWithHighlights(text, [highlight], [], {
  block_index: i,
  page: 39,
  source_locator: locators[i],
  source_locators: [locators[i]],
  extraction_ids: [extractionIds[i]]
}));
process.stdout.write(JSON.stringify({locator: highlight.source_locator, htmls}));
"""
    result = _run_node(script)

    assert result["locator"].startswith(SPAN_PREFIX)
    assert 'data-highlight-id="hl-multi"' not in result["htmls"][0]
    assert 'data-highlight-id="hl-multi"' not in result["htmls"][4]
    assert result["htmls"][4] == "After the paragraph. photographs should stay plain here."
    assert all(result["htmls"][i].count('data-highlight-id="hl-multi"') == 1 for i in (1, 2, 3))
    assert result["htmls"][1].startswith("The walls displayed ")
    assert (
        '>photographs of clients on stages, television sets, conference</span>'
        in result["htmls"][1]
    )
    assert (
        '>screens, university lecterns, and magazine covers. A monitor showed a dashboard</span>'
        in result["htmls"][2]
    )
    assert ">titled POST-PUBLICATION CONVERSION</span> PLAN." in result["htmls"][3]


def test_span_offsets_prevent_repeated_text_drift() -> None:
    script = _renderer_harness() + r"""
const text = "dashboard before dashboard selected dashboard after";
const start = text.indexOf("dashboard selected");
const end = start + "dashboard selected".length;
const highlight = {
  id: "hl-repeat",
  page: 39,
  status: "saved_highlight",
  selected_text: "dashboard",
  source_locator: _crEncodeReaderSpanLocator({
    valid: true,
    page: 39,
    start: {block_index: 0, source_locator: "page:39:block:1", source_locators: ["page:39:block:1"], extraction_ids: ["ext-1"], offset: start},
    end: {block_index: 0, source_locator: "page:39:block:1", source_locators: ["page:39:block:1"], extraction_ids: ["ext-1"], offset: end},
    blocks: [{block_index: 0, source_locator: "page:39:block:1", source_locators: ["page:39:block:1"], extraction_ids: ["ext-1"]}],
    source_locators: ["page:39:block:1"],
    extraction_ids: ["ext-1"]
  })
};
const html = _crRenderTextWithHighlights(text, [highlight], [], {
  block_index: 0,
  page: 39,
  source_locator: "page:39:block:1",
  source_locators: ["page:39:block:1"],
  extraction_ids: ["ext-1"]
});
process.stdout.write(JSON.stringify({html}));
"""
    result = _run_node(script)

    assert result["html"].startswith("dashboard before ")
    assert ">dashboard selected</span> dashboard after" in result["html"]
    assert result["html"].count('data-highlight-id="hl-repeat"') == 1


def test_reader_span_provenance_vetoes_stale_block_indexes() -> None:
    script = _renderer_harness() + r"""
const highlight = {
  id: "hl-stale",
  page: 12,
  status: "saved_highlight",
  selected_text: "old selected text",
  source_locator: _crEncodeReaderSpanLocator({
    valid: true,
    page: 12,
    start: {block_index: 1, source_locator: "page:12:block:old-1", source_locators: ["page:12:block:old-1"], extraction_ids: ["old-ext-1"], offset: 4},
    end: {block_index: 3, source_locator: "page:12:block:old-3", source_locators: ["page:12:block:old-3"], extraction_ids: ["old-ext-3"], offset: 8},
    blocks: [1, 2, 3].map(i => ({block_index: i, source_locator: `page:12:block:old-${i}`, source_locators: [`page:12:block:old-${i}`], extraction_ids: [`old-ext-${i}`]})),
    source_locators: ["page:12:block:old-1", "page:12:block:old-2", "page:12:block:old-3"],
    extraction_ids: ["old-ext-1", "old-ext-2", "old-ext-3"]
  })
};
const html = _crRenderTextWithHighlights("new projection at the stale index", [highlight], [], {
  block_index: 2,
  page: 12,
  source_locator: "page:12:block:new-2",
  source_locators: ["page:12:block:new-2"],
  extraction_ids: ["new-ext-2"]
});
process.stdout.write(JSON.stringify({html}));
"""
    result = _run_node(script)

    assert result["html"] == "new projection at the stale index"
    assert 'data-highlight-id="hl-stale"' not in result["html"]


def test_reader_span_reordered_blocks_map_by_provenance_not_old_index() -> None:
    script = _renderer_harness() + r"""
const highlight = {
  id: "hl-reordered",
  page: 12,
  status: "saved_highlight",
  selected_text: "old selected text",
  source_locator: _crEncodeReaderSpanLocator({
    valid: true,
    page: 12,
    start: {block_index: 1, source_locator: "page:12:block:old-1", source_locators: ["page:12:block:old-1"], extraction_ids: ["old-ext-1"], offset: 6},
    end: {block_index: 3, source_locator: "page:12:block:old-3", source_locators: ["page:12:block:old-3"], extraction_ids: ["old-ext-3"], offset: 9},
    blocks: [1, 2, 3].map(i => ({block_index: i, source_locator: `page:12:block:old-${i}`, source_locators: [`page:12:block:old-${i}`], extraction_ids: [`old-ext-${i}`]})),
    source_locators: ["page:12:block:old-1", "page:12:block:old-2", "page:12:block:old-3"],
    extraction_ids: ["old-ext-1", "old-ext-2", "old-ext-3"]
  })
};
const renderedStart = _crRenderTextWithHighlights("start selected text", [highlight], [], {
  block_index: 8,
  page: 12,
  source_locator: "page:12:block:old-1",
  source_locators: ["page:12:block:old-1"],
  extraction_ids: ["old-ext-1"]
});
const renderedMiddle = _crRenderTextWithHighlights("middle selected text", [highlight], [], {
  block_index: 9,
  page: 12,
  source_locator: "page:12:block:old-2",
  source_locators: ["page:12:block:old-2"],
  extraction_ids: ["old-ext-2"]
});
const renderedEnd = _crRenderTextWithHighlights("end text after", [highlight], [], {
  block_index: 7,
  page: 12,
  source_locator: "page:12:block:old-3",
  source_locators: ["page:12:block:old-3"],
  extraction_ids: ["old-ext-3"]
});
process.stdout.write(JSON.stringify({renderedStart, renderedMiddle, renderedEnd}));
"""
    result = _run_node(script)

    assert result["renderedStart"].startswith("start ")
    assert ">selected text</span>" in result["renderedStart"]
    assert ">middle selected text</span>" in result["renderedMiddle"]
    assert ">end text </span>after" in result["renderedEnd"]


def test_reader_span_fails_closed_for_projection_block_with_outside_provenance() -> None:
    script = _renderer_harness() + r"""
const highlight = {
  id: "hl-mixed",
  page: 12,
  status: "saved_highlight",
  selected_text: "selected",
    source_locator: _crEncodeReaderSpanLocator({
      valid: true,
      page: 12,
      start: {block_index: 1, source_locator: "page:12:block:old-1", source_locators: ["page:12:block:old-1"], extraction_ids: ["old-ext-1"], offset: 0},
      end: {block_index: 2, source_locator: "page:12:block:old-2", source_locators: ["page:12:block:old-2"], extraction_ids: ["old-ext-2"], offset: 8},
      blocks: [
        {block_index: 1, source_locator: "page:12:block:old-1", source_locators: ["page:12:block:old-1"], extraction_ids: ["old-ext-1"]},
        {block_index: 2, source_locator: "page:12:block:old-2", source_locators: ["page:12:block:old-2"], extraction_ids: ["old-ext-2"]}
      ],
      source_locators: ["page:12:block:old-1", "page:12:block:old-2"],
      extraction_ids: ["old-ext-1", "old-ext-2"]
    })
};
const html = _crRenderTextWithHighlights("selected plus outside material", [highlight], [], {
  block_index: 2,
  page: 12,
  source_locators: ["page:12:block:old-2", "page:12:block:outside"],
  extraction_ids: ["old-ext-2", "outside-ext"]
});
process.stdout.write(JSON.stringify({html}));
"""
    result = _run_node(script)

    assert result["html"] == "selected plus outside material"
    assert 'data-highlight-id="hl-mixed"' not in result["html"]


def test_malformed_reader_span_locator_does_not_substring_highlight() -> None:
    script = _renderer_harness() + r"""
const html = _crRenderTextWithHighlights("alpha beta gamma", [
  {
    id: "hl-bad-v1",
    page: 1,
    status: "saved_highlight",
    selected_text: "beta",
    source_locator: "reader-span:v1:%7Bnot-json"
  }
], [], {
  block_index: 0,
  page: 1,
  source_locators: ["page:1:block:1"],
  extraction_ids: ["ext-1"]
});
process.stdout.write(JSON.stringify({html}));
"""
    result = _run_node(script)

    assert result["html"] == "alpha beta gamma"
    assert 'data-highlight-id="hl-bad-v1"' not in result["html"]


def test_reader_span_without_usable_provenance_cannot_paint_by_block_index() -> None:
    script = _renderer_harness() + r"""
const locator = "reader-span:v1:" + encodeURIComponent(JSON.stringify({
  page: 1,
  start: {block_index: 0, offset: 6},
  end: {block_index: 0, offset: 10}
}));
const html = _crRenderTextWithHighlights("alpha beta gamma", [
  {
    id: "hl-index-only",
    page: 1,
    status: "saved_highlight",
    selected_text: "beta",
    source_locator: locator
  }
], [], {
  block_index: 0,
  page: 1,
  source_locators: ["page:1:block:1"],
  extraction_ids: ["ext-1"]
});
process.stdout.write(JSON.stringify({html}));
"""
    result = _run_node(script)

    assert result["html"] == "alpha beta gamma"
    assert 'data-highlight-id="hl-index-only"' not in result["html"]


def test_single_block_and_distinct_same_page_highlights_still_render() -> None:
    script = _renderer_harness() + r"""
const text = "alpha beta gamma delta";
const ctx = {block_index: 0, page: 1, source_locators: ["page:1:block:1"], extraction_ids: ["ext-1"]};
const single = _crRenderTextWithHighlights(text, [
  {id: "h-single", page: 1, status: "saved_highlight", selected_text: "beta", source_locator: null}
], [], ctx);
const distinct = _crRenderTextWithHighlights(text, [
  {id: "h-beta", page: 1, status: "saved_highlight", selected_text: "beta", source_locator: null},
  {id: "h-delta", page: 1, status: "saved_highlight", selected_text: "delta", source_locator: null}
], [], ctx);
process.stdout.write(JSON.stringify({single, distinct}));
"""
    result = _run_node(script)

    assert 'data-highlight-id="h-single"' in result["single"]
    assert result["distinct"].count("cr-inline-highlight") == 2
    assert 'data-highlight-id="h-beta"' in result["distinct"]
    assert 'data-highlight-id="h-delta"' in result["distinct"]


def _seed_projection_fixture(db_path: Path) -> tuple[str, list[tuple[str, str]]]:
    SQLiteStore(db_path).close()
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "c" * 64
    blocks = [
        ("ext-0", 0, "Before the paragraph."),
        (
            "ext-1",
            1,
            "The walls displayed photographs of clients on stages, television sets, conference",
        ),
        (
            "ext-2",
            2,
            "screens, university lecterns, and magazine covers. A monitor showed a dashboard",
        ),
        ("ext-3", 3, "titled POST-PUBLICATION CONVERSION PLAN."),
        ("ext-4", 4, "After the paragraph."),
    ]
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "the-second-sale.pdf", doc_id, 39, now, "test", "primary", 0),
    )
    for extraction_id, block, raw_text in blocks:
        conn.execute(
            """INSERT INTO source_extractions
               (id, document_id, page, region, raw_text, parser, parser_version,
                coordinates, source_locator, source_hash, hash, extracted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                extraction_id,
                doc_id,
                39,
                f"block:{block}",
                raw_text,
                "pymupdf",
                "test",
                "{}",
                f"page:39:block:{block}",
                doc_id,
                extraction_id,
                now,
            ),
        )
    conn.commit()
    conn.close()
    return doc_id, [(extraction_id, raw_text) for extraction_id, _, raw_text in blocks]


def test_highlight_span_locator_round_trips_and_rerenders_without_mutating_extractions(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "reader_multiblock.db"
    doc_id, before = _seed_projection_fixture(db_path)
    blocks = [raw_text for _, raw_text in before]
    selected = (
        blocks[1][blocks[1].index("photographs"):]
        + "\n\n"
        + blocks[2]
        + "\n\n"
        + blocks[3][: blocks[3].index(" PLAN")]
    )
    locator = _span_locator(
        {
            "page": 39,
            "start": {
                "block_index": 1,
                "source_locator": "page:39:block:1",
                "source_locators": ["page:39:block:1"],
                "extraction_ids": ["ext-1"],
                "offset": blocks[1].index("photographs"),
            },
            "end": {
                "block_index": 3,
                "source_locator": "page:39:block:3",
                "source_locators": ["page:39:block:3"],
                "extraction_ids": ["ext-3"],
                "offset": blocks[3].index(" PLAN"),
            },
            "source_locators": ["page:39:block:1", "page:39:block:2", "page:39:block:3"],
            "extraction_ids": ["ext-1", "ext-2", "ext-3"],
        }
    )
    client = create_app(db_path=db_path).test_client()

    response = client.post(
        "/api/reader/highlights",
        json={
            "source_document_id": doc_id,
            "page": 39,
            "source_locator": locator,
            "selected_text": selected,
        },
    )
    assert response.status_code == 201
    highlight_id = response.get_json()["id"]

    page = client.get(f"/api/reader/documents/{doc_id}/pages").get_json()["pages"][0]
    highlights = page["highlights"]
    extractions = page["extractions"]
    assert len(highlights) == 1
    assert highlights[0]["id"] == highlight_id
    assert highlights[0]["source_locator"] == locator

    render = _run_node(
        _renderer_harness()
        + "\nconst page="
        + json.dumps({"highlights": highlights, "extractions": extractions})
        + r""";
const htmls = page.extractions.map((ex, i) => _crRenderTextWithHighlights(
  ex.text,
  page.highlights,
  [],
  _crReaderBlockContext(ex, i, 39)
));
process.stdout.write(JSON.stringify({htmls}));
"""
    )

    assert 'data-highlight-id="' + highlight_id + '"' not in render["htmls"][0]
    assert 'data-highlight-id="' + highlight_id + '"' not in render["htmls"][4]
    assert all(render["htmls"][i].count('data-highlight-id="' + highlight_id + '"') == 1 for i in (1, 2, 3))
    assert render["htmls"][1].startswith("The walls displayed ")
    assert ">titled POST-PUBLICATION CONVERSION</span> PLAN." in render["htmls"][3]

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    after = conn.execute("SELECT id, raw_text FROM source_extractions ORDER BY id").fetchall()
    conn.close()

    assert count == 1
    assert after == before
