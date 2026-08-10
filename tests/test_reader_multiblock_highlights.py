"""Reader highlight rendering across projected display blocks.

Invariant: a human Reader highlight is one authored record. Rendering may split
that record across display blocks, but it must not mutate canonical source
extractions or create one highlight row per extraction.
"""
from __future__ import annotations

import json
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
    import re

    match = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def _renderer_harness() -> str:
    html = INDEX.read_text()
    helpers = [
        "_crStringList",
        "_crUniqueStringList",
        "_crReaderSpanPoint",
        "_crEncodeReaderSpanLocator",
        "_crDecodeReaderSpanLocator",
        "_crInlineHighlightClass",
        "_crFiniteNumber",
        "_crTextOffset",
        "_crHasAnyValue",
        "_crBlockMatchesSpanPoint",
        "_crSpanRangeForBlock",
        "_crPushNonOverlappingRange",
        "_crRenderTextWithHighlights",
    ]
    return (
        "function x(s){return String(s==null?'':s)"
        ".replace(/&/g,'&amp;').replace(/</g,'&lt;')"
        ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');}\n"
        "function _crHighlightTags(h){return (h&&h.tags)||[];}\n"
        f"const _CR_READER_SPAN_LOCATOR_PREFIX='{SPAN_PREFIX}';\n"
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
  "The walls displayed photographs of clients on stages, television sets, conference",
  "screens, university lecterns, and magazine covers. A monitor showed a dashboard",
  "titled POST-PUBLICATION CONVERSION PLAN."
];
const locators = ["page:39:block:1", "page:39:block:2", "page:39:block:3"];
const extractionIds = ["ext-1", "ext-2", "ext-3"];
const startOffset = blocks[0].indexOf("photographs");
const endOffset = blocks[2].indexOf(" PLAN");
const selection = {
  valid: true,
  page: 39,
  start: {block_index: 0, source_locator: locators[0], source_locators: [locators[0]], extraction_ids: [extractionIds[0]], offset: startOffset},
  end: {block_index: 2, source_locator: locators[2], source_locators: [locators[2]], extraction_ids: [extractionIds[2]], offset: endOffset},
  blocks: locators.map((locator, i) => ({block_index: i, source_locator: locator, source_locators: [locator], extraction_ids: [extractionIds[i]]})),
  source_locators: locators,
  extraction_ids: extractionIds
};
const highlight = {
  id: "hl-multi",
  page: 39,
  status: "saved_highlight",
  relevance: "unclear",
  selected_text: blocks[0].slice(startOffset) + " " + blocks[1] + " " + blocks[2].slice(0, endOffset),
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
    assert all(html.count('data-highlight-id="hl-multi"') == 1 for html in result["htmls"])
    assert (
        '>photographs of clients on stages, television sets, conference</span>'
        in result["htmls"][0]
    )
    assert result["htmls"][0].startswith("The walls displayed ")
    assert (
        '>screens, university lecterns, and magazine covers. A monitor showed a dashboard</span>'
        in result["htmls"][1]
    )
    assert ">titled POST-PUBLICATION CONVERSION</span> PLAN." in result["htmls"][2]


def test_single_block_and_distinct_same_page_highlights_still_render() -> None:
    script = _renderer_harness() + r"""
const text = "alpha beta gamma delta";
const single = _crRenderTextWithHighlights(text, [
  {id: "h-single", page: 1, status: "saved_highlight", selected_text: "beta", source_locator: null}
], [], {block_index: 0, page: 1, source_locators: ["page:1:block:1"], extraction_ids: ["ext-1"]});
const distinct = _crRenderTextWithHighlights(text, [
  {id: "h-beta", page: 1, status: "saved_highlight", selected_text: "beta", source_locator: null},
  {id: "h-delta", page: 1, status: "saved_highlight", selected_text: "delta", source_locator: null}
], [], {block_index: 0, page: 1, source_locators: ["page:1:block:1"], extraction_ids: ["ext-1"]});
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


def test_highlight_span_locator_round_trips_without_mutating_extractions(tmp_path: Path) -> None:
    db_path = tmp_path / "reader_multiblock.db"
    doc_id, before = _seed_projection_fixture(db_path)
    blocks = [raw_text for _, raw_text in before]
    selected = (
        blocks[0][blocks[0].index("photographs"):]
        + " "
        + blocks[1]
        + " "
        + blocks[2][: blocks[2].index(" PLAN")]
    )
    locator = _span_locator(
        {
            "page": 39,
            "start": {
                "block_index": 0,
                "source_locator": "page:39:block:1",
                "source_locators": ["page:39:block:1"],
                "extraction_ids": ["ext-1"],
                "offset": blocks[0].index("photographs"),
            },
            "end": {
                "block_index": 2,
                "source_locator": "page:39:block:3",
                "source_locators": ["page:39:block:3"],
                "extraction_ids": ["ext-3"],
                "offset": blocks[2].index(" PLAN"),
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

    highlights = client.get(f"/api/reader/documents/{doc_id}/highlights").get_json()["highlights"]
    assert len(highlights) == 1
    assert highlights[0]["id"] == highlight_id
    assert highlights[0]["source_locator"] == locator

    for _ in range(2):
        page = client.get(f"/api/reader/documents/{doc_id}/pages").get_json()["pages"][0]
        assert page["highlights"][0]["source_locator"] == locator

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    after = conn.execute("SELECT id, raw_text FROM source_extractions ORDER BY id").fetchall()
    conn.close()

    assert count == 1
    assert after == before
