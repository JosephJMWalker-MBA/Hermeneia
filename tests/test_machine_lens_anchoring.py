"""
Machine Lens anchoring by identity (real API → Reader renderer path).

A machine Observation must be drawn on exactly the canonical evidence it came
from: its parent SourceExtraction, its stored sentence occurrence, mapped
through the Reader projection's own provenance. These tests seed a database,
read the actual `/pages` and `/related-observations` payloads, and run the
extracted client renderer under Node — so the whole API→renderer path is
exercised, not a text-matching shortcut.

Regression families (each failed on the text-search renderer):
  1. repeated text: the stored second occurrence is marked, not the first
  2. same text in two SourceExtractions: only the parent extraction is marked
  3. projected soft-wrap: canonical span maps to the joined display span
  4. offset adjustment inside a transformed sentence
  5. a human mark over the intended occurrence suppresses the machine mark
     instead of relocating it to another equal string
Plus: ambiguity/misattribution abstains, the API carries identity read-only.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from hermeneia.compiler.sentence_splitter import sentence_spans, split_sentences
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.web.reader_projection import observation_canonical_span

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
NOW = "2026-01-01T00:00:00+00:00"
DOC = "a" * 64

_FNS = [
    "_crStringList", "_crUniqueStringList", "_crProjectionExtractionIds",
    "_crProjectionSourceLocators", "_crReaderBlockContext", "_crInlineHighlightClass",
    "_crIsReaderSpanLocator", "_crDecodeReaderSpanLocator", "_crFiniteNumber",
    "_crTextOffset", "_crSourceOffset", "_crHasAnyValue", "_crHasComparableProvenance",
    "_crSpanHasProvenance", "_crBlockProvenanceWithinSpan", "_crSourceSpanMatchesProvenance",
    "_crDisplaySourceSpansForProvenance", "_crLegacySpanEligibleSourceSpans",
    "_crBlockMatchesSpan", "_crBlockMatchesSpanPoint", "_crDisplaySourceSpanForPoint",
    "_crSpanPointOffsetInBlock", "_crSpanUsesProjectedOffsets", "_crSpanRangeForBlock",
    "_crPushNonOverlappingRange", "_crHighlightSortKey", "_crSortedHighlightsForSegment",
    "_crHumanHighlightTitle", "_crHumanSegmentsFromRanges", "_crProjectSourceBoundary",
    "_crWithoutWhitespace", "_crMachineRangeForBlock", "_crRenderTextWithHighlights",
    "_crMachineHighlightClass",
]


def _extract_fn(html: str, name: str) -> str:
    m = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert m, f"could not extract function {name} from index.html"
    return m.group(0)


def _render(jobs: list[dict]) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for behavioural anchoring test")
    html = INDEX.read_text()
    harness = (
        "function x(s){return String(s==null?'':s).replace(/&/g,'&amp;')"
        ".replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');}\n"
        "function _crHighlightTags(h){return (h&&h.tags)||[];}\n"
        "const _CR_READER_SPAN_LOCATOR_PREFIX='reader-span:v1:';\nlet _crPage=1;\n"
        + "".join(_extract_fn(html, name) for name in _FNS)
        + "const jobs=JSON.parse(require('fs').readFileSync(0,'utf8'));\n"
        "process.stdout.write(JSON.stringify(jobs.map(j=>_crRenderTextWithHighlights("
        "j.text,j.highlights,j.obs,j.ctx||_crReaderBlockContext(j.ex,j.idx,j.page)))));\n"
    )
    out = subprocess.run([node, "-e", harness], input=json.dumps(jobs),
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


_TOKEN = re.compile(r"<span ([^>]*)>|</span>|[^<]+")


def _marks(markup: str, attr: str) -> list[tuple[int, int, str]]:
    """Display-coordinate spans whose opening tag carries ``attr``."""
    plain, stack, found = "", [], []
    for m in _TOKEN.finditer(markup):
        tok = m.group(0)
        if tok.startswith("<span "):
            ident = re.search(attr + r'="([^"]*)"', m.group(1))
            stack.append((ident.group(1) if ident else None, len(plain)))
        elif tok == "</span>":
            ident, start = stack.pop()
            if ident is not None:
                found.append((start, len(plain), ident))
        else:
            plain += htmllib.unescape(tok)
    return found


def _seed(tmp_path: Path, extractions, observations, highlights=()) -> Path:
    db = tmp_path / "anchoring.db"
    SQLiteStore(db).close()
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO source_documents (id, original_filename, file_hash, total_pages,"
        " registered_at, compiler_version, source_role, excluded_from_analysis)"
        " VALUES (?,?,?,?,?,?,?,0)", (DOC, "book.pdf", DOC, 3, NOW, "t", "primary"))
    texts = {}
    for ext_id, page, block, raw in extractions:
        texts[ext_id] = raw
        conn.execute(
            "INSERT INTO source_extractions (id, document_id, page, region, raw_text, parser,"
            " parser_version, coordinates, source_locator, source_hash, hash, extracted_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (ext_id, DOC, page, f"block:{block}", raw, "t", "1", "{}",
             f"page:{page}:block:{block}", DOC, ext_id, NOW))
    for obs_id, ext_id, page, sentence in observations:
        raw = split_sentences(texts[ext_id])[sentence - 1]
        conn.execute(
            "INSERT INTO observations (id, epistemic_class, source_document_id, source_extraction_id,"
            " raw_text, source_locator, semantic_hash, page, paragraph, sentence, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (obs_id, "Evidence", DOC, ext_id, raw, f"p{page}s{sentence}", obs_id, page, 1, sentence, NOW))
    for hid, selected in highlights:
        conn.execute(
            "INSERT INTO reader_highlights (id, source_document_id, page, selected_text, created_at,"
            " updated_at) VALUES (?,?,?,?,?,?)", (hid, DOC, 1, selected, NOW, NOW))
    conn.commit()
    conn.close()
    return db


def _canonical_rows(db: Path) -> list:
    conn = sqlite3.connect(db)
    rows = [conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()
            for t in ("source_extractions", "observations", "provenance")]
    conn.close()
    return rows


def _reader_page(db: Path, page: int = 1) -> list[dict]:
    """Mirror the Reader: projected page blocks + current-page lens source."""
    client = create_app(db_path=db).test_client()
    pages = client.get(f"/api/reader/documents/{DOC}/pages").get_json()["pages"]
    page_data = next(p for p in pages if p["page"] == page)
    obs = client.get(f"/api/reader/documents/{DOC}/related-observations?page={page}").get_json()["observations"]
    page_obs = [o for o in obs if int(o["page"]) == page]
    exs = page_data["extractions"]
    jobs = [{"text": ex.get("text") or "", "highlights": page_data.get("highlights", []),
             "obs": page_obs, "ex": ex, "idx": i, "page": page} for i, ex in enumerate(exs)]
    return [
        {"text": ex.get("text") or "", "markup": markup,
         "machine": _marks(markup, "data-machine-obs"), "human": _marks(markup, "data-highlight-id")}
        for ex, markup in zip(exs, _render(jobs))
    ]


# ── The five regression families ─────────────────────────────────────────────

def test_repeated_text_marks_the_stored_occurrence(tmp_path):
    db = _seed(tmp_path, [("e1", 1, 1, "Echo. Echo.")], [("o2", "e1", 1, 2)])
    blocks = _reader_page(db)
    assert blocks[0]["machine"] == [(6, 11, "o2")], "must mark the second Echo., not the first"


def test_same_text_in_two_extractions_marks_only_the_parent(tmp_path):
    db = _seed(
        tmp_path,
        [("e1", 1, 1, "The lamp glows."), ("e2", 1, 2, "The lamp glows.")],
        [("o1", "e2", 1, 1)],
    )
    blocks = _reader_page(db)
    assert [b["machine"] for b in blocks] == [[], [(0, 15, "o1")]]


def test_soft_wrap_projection_maps_canonical_span_to_display(tmp_path):
    db = _seed(tmp_path, [("e1", 1, 1, "The quiet\nriver flows.")], [("o1", "e1", 1, 1)])
    blocks = _reader_page(db)
    assert blocks[0]["text"] == "The quiet river flows."
    assert blocks[0]["machine"] == [(0, 22, "o1")]


def test_offset_adjustments_inside_transformed_sentence(tmp_path):
    raw = "First line\n  wraps. The quiet\n  river flows now."
    db = _seed(tmp_path, [("e1", 1, 1, raw)], [("o2", "e1", 1, 2)])
    blocks = _reader_page(db)
    text = blocks[0]["text"]
    assert text == "First line wraps. The quiet river flows now."
    assert blocks[0]["machine"] == [(18, 44, "o2")]
    assert text[18:44] == "The quiet river flows now."


def test_human_mark_over_intended_occurrence_suppresses_machine(tmp_path):
    db = _seed(tmp_path, [("e1", 1, 1, "Echo. Echo.")], [("o1", "e1", 1, 1)],
               highlights=[("h1", "Echo.")])
    blocks = _reader_page(db)
    assert blocks[0]["human"] == [(0, 5, "h1")]
    assert blocks[0]["machine"] == [], "machine meaning must not relocate to the second Echo."


# ── Protected behaviour on the same path ─────────────────────────────────────

def test_drop_cap_and_prose_merge_continuations_still_anchor(tmp_path):
    db = _seed(
        tmp_path,
        [("e1", 1, 2, "I"), ("e2", 1, 3, "n my younger years my father gave me advice.")],
        [("o1", "e2", 1, 1)],
    )
    blocks = _reader_page(db)
    assert blocks[0]["machine"] == [(1, len(blocks[0]["text"]), "o1")]

    (tmp_path / "merge").mkdir()
    merge_db = _seed(
        tmp_path / "merge",
        [("m1", 1, 1, "The old house stood on the hill where"),
         ("m2", 1, 2, "nobody went anymore. Birds sang.")],
        [("om", "m2", 1, 1)],
    )
    merged = _reader_page(merge_db)
    assert len(merged) == 1
    assert merged[0]["machine"] == [(38, 58, "om")]


def test_anchoring_reads_but_never_mutates_canonical_evidence(tmp_path):
    db = _seed(tmp_path, [("e1", 1, 1, "The quiet\nriver flows.")], [("o1", "e1", 1, 1)])
    before = _canonical_rows(db)
    _reader_page(db)
    assert _canonical_rows(db) == before


def test_related_observations_carry_identity_and_canonical_span(tmp_path):
    db = _seed(tmp_path, [("e1", 1, 1, "Echo. Echo.")], [("o2", "e1", 1, 2)])
    obs = create_app(db_path=db).test_client().get(
        f"/api/reader/documents/{DOC}/related-observations?page=1").get_json()["observations"]
    assert obs[0]["source_extraction_id"] == "e1"
    assert obs[0]["canonical_span"] == {
        "source_extraction_id": "e1", "start": 6, "end": 11, "text": "Echo.",
        "basis": "sentence_segmentation",
    }
    assert "extraction_raw_text" not in obs[0]


# ── Abstention at the renderer boundary ──────────────────────────────────────

_CTX = {"block_index": 0, "page": 1, "source_locator": "page:1:block:1",
        "source_locators": ["page:1:block:1"], "extraction_ids": ["e-A"], "display_source_spans": []}


@pytest.mark.parametrize("obs", [
    {"id": "o1", "page": 1, "raw_text": "Echo."},  # no identity → no text search
    {"id": "o1", "page": 1, "raw_text": "Echo.", "canonical_span":
        {"source_extraction_id": "e-B", "start": 6, "end": 11, "text": "Echo."}},
    {"id": "o1", "page": 1, "raw_text": "Echo.", "canonical_span":
        {"source_extraction_id": "e-A", "start": 40, "end": 45, "text": "Echo."}},
    {"id": "o1", "page": 1, "raw_text": "Echo.", "canonical_span":
        {"source_extraction_id": "e-A", "start": 0, "end": 5, "text": "Other"}},
])
def test_renderer_abstains_without_a_faithful_identity_anchor(obs):
    [markup] = _render([{"text": "Echo. Echo.", "highlights": [], "obs": [obs], "ctx": _CTX}])
    assert "cr-machine-hl" not in markup


def test_renderer_abstains_when_projection_span_is_ambiguous():
    ctx = dict(_CTX, display_source_spans=[
        {"source_extraction_id": "e-A", "start": 0, "end": 5},
        {"source_extraction_id": "e-A", "start": 6, "end": 11},
    ])
    obs = {"id": "o1", "page": 1, "raw_text": "Echo.", "canonical_span":
           {"source_extraction_id": "e-A", "start": 0, "end": 5, "text": "Echo."}}
    [markup] = _render([{"text": "Echo. Echo.", "highlights": [], "obs": [obs], "ctx": ctx}])
    assert "cr-machine-hl" not in markup


# ── Server-side span reconstruction ──────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Echo. Echo.", "Dr. Smith arrived. He sat.  Then left!", "   ", "One\n\nTwo. Three.",
])
def test_sentence_spans_reproduce_split_sentences(text):
    assert [text[s:e] for s, e in sentence_spans(text)] == split_sentences(text)


def test_canonical_span_prefers_verified_provenance_offsets_and_abstains_on_conflict():
    assert observation_canonical_span("Echo. Echo.", "Echo.", 1, 6, 11)["start"] == 6
    assert observation_canonical_span("Echo. Echo.", "Other", 2) is None
    assert observation_canonical_span("Echo. Echo.", "Echo.", 3) is None
    assert observation_canonical_span("Echo. Echo.", "Echo.", 1, 2, 7) is None
    assert observation_canonical_span(None, "Echo.", 1) is None
