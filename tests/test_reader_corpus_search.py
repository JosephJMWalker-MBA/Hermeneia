"""Reader-side Corpus Search (PR 2).

"Where else does this idea appear?" — a slide-in panel beside the book that
searches the corpus without leaving the Reader. Reuses the existing /api/search
endpoint over observations; clicking a result navigates the book to that passage
while the panel stays open. These tests cover the search API contract the panel
depends on and the panel's UI wiring.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed(tmp_path: Path) -> Path:
    db_path = tmp_path / "workspace.db"
    SQLiteStore(db_path).close()
    doc_id = "a" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 3, _now(), "test", "primary", 0),
    )
    conn.execute(
        """INSERT INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("ext-1", doc_id, 2, "block:4", "the green light", "pymupdf", "1.7",
         "{}", "page:2:block:4", doc_id, "ext-1", _now()),
    )
    conn.execute(
        """INSERT INTO observations
           (id, epistemic_class, source_document_id, source_extraction_id,
            raw_text, source_locator, semantic_hash, page, paragraph, sentence,
            created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("obs-1", "Evidence", doc_id, "ext-1",
         "Gatsby believed in the green light.", "page:2:block:4",
         "hash-1", 2, 1, 1, _now()),
    )
    conn.commit()
    conn.close()
    return db_path


# ── The search API the panel depends on ────────────────────────────────────


def test_search_returns_matching_observations(tmp_path: Path):
    client = create_app(db_path=_seed(tmp_path)).test_client()
    body = client.get("/api/search?q=green+light").get_json()
    assert body["count"] == 1
    assert body["passage_count"] == 1
    assert body["occurrence_count"] == 1
    assert body["page_count"] == 1
    assert body["document_count"] == 1
    assert body["matching"]["mode"] == "literal-case-insensitive-substring-v1"
    hit = body["results"][0]
    assert "green light" in hit["text"]
    assert hit["canonical_text"] == "Gatsby believed in the green light."
    assert hit["occurrence_count"] == 1
    assert hit["occurrences"] == [
        {"start": 23, "end": 34, "matched_text": "green light"}
    ]
    assert hit["document_name"] == "gatsby.pdf"
    assert hit["page"] == 2
    assert hit["source_role"] == "primary"
    assert len(body["occurrences"]) == body["occurrence_count"]


def test_search_is_empty_for_no_match(tmp_path: Path):
    client = create_app(db_path=_seed(tmp_path)).test_client()
    body = client.get("/api/search?q=zznomatch").get_json()
    assert body["count"] == 0
    assert body["passage_count"] == 0
    assert body["occurrence_count"] == 0
    assert body["occurrences"] == []
    assert body["distribution"] == {"documents": []}
    assert body["results"] == []


def test_search_excludes_muted_documents(tmp_path: Path):
    db_path = _seed(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE source_documents SET excluded_from_analysis = 1")
    conn.commit()
    conn.close()
    client = create_app(db_path=db_path).test_client()
    body = client.get("/api/search?q=green+light").get_json()
    assert body["count"] == 0
    assert body["occurrence_count"] == 0


# ── Panel UI wiring ────────────────────────────────────────────────────────


def test_corpus_search_panel_markup_and_trigger_present():
    index = INDEX.read_text()
    assert 'id="cr-bottom-workstation"' in index
    assert 'id="corpus-search"' in index
    assert 'id="corpus-search-input"' in index
    assert "openCorpusSearch()" in index          # rail trigger
    assert "closeCorpusSearch()" in index
    assert "_corpusRunSearch" in index
    assert "/api/search?q=" in index
    # The trigger lives in the Reader tool rail, and search opens in the shared
    # bottom workstation rather than a separate side panel.
    assert "cr-rail-search" in index
    assert 'class="corpus-search"' in index
    assert "Search Corpus" in index
    assert "separating literal occurrences from matching passages" in index
    assert "literal occurrence" in index
    assert "passageCount" in index
    assert "results_truncated" in index
    assert "occurrence_count" in index
    assert "Expanded cards are limited; use backend concordance totals" in index
    assert "literal-occurrence ratio" in index
    assert "literal occurrences in this passage" in index
    assert "renderMotifPanel(q, observations, motifHost, null, data)" in index
    assert "renderMotifPanel(query, full.observations" not in index
    assert "The other ${others} passage" in index
    assert "The other ${others} occurrence" not in index
    assert "Number(data.occurrence_count)" in index
    assert "Expanded cards are limited; use backend concordance totals" in index
    assert "_concordanceDocuments(concordance)" in index
    assert "suppressPatternView" in index
    assert "bookmarked_subset" in index
    assert "Pattern View is unavailable for bookmarked subsets" in index
    assert "Switch to All or another corpus filter for complete concordance" in index
    assert "first 100 matching passages" in index
    assert "complete bookmarked concordance unavailable" in index
    assert "bookmarked passage${count === 1 ? '' : 's'}" in index
    assert "filter=all&limit=100" in index
    assert "filter=all&limit=5000`" not in index
    assert "results_truncated: Boolean(data.results_truncated)" in index
    assert "renderResults(query, {\n      count: filtered.length" in index


def test_result_click_navigates_the_book_not_a_page_away():
    index = INDEX.read_text()
    # Clicking a result opens the doc/page in the Reader; it does not leave to a
    # separate corpus screen.
    assert "_corpusOpenResult" in index
    assert "function _crGoToPage" in index
    assert "_crRenderPage()" in index
