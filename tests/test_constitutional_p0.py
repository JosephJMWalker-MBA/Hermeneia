"""
P0 constitutional conformance tests.

These tests encode the first executable slice of docs/02_Constitutional_Invariants.md.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.compiler.compiler import Compiler
from hermeneia.compiler.observation_compiler import compile_observations
from hermeneia.compiler.paragraph_splitter import Paragraph
from hermeneia.compiler.parser import RawBlock, parse_pdf, parser_name, parser_version
from hermeneia.compiler.source_extraction_compiler import compile_source_extractions
from hermeneia.compiler.architect import compile_architect_plan
from hermeneia.field.index import term_id
from hermeneia.storage.hashing import (
    make_architect_plan_id,
    make_blueprint_id,
    make_expression_profile_id,
    make_interpretation_id,
    make_observation_id,
    make_perspective_id,
    make_rendered_narrative_id,
    make_semantic_hash,
    make_source_extraction_id,
    make_source_locator,
    make_validation_report_id,
    sha256_file,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


GATSBY_PDF = Path(__file__).parent.parent / "examples" / "gatsby.pdf"
needs_pdf = pytest.mark.skipif(
    not GATSBY_PDF.exists(), reason="gatsby.pdf not found in examples/"
)


def test_ci002_source_extraction_preserves_exact_parser_text():
    raw = "  Weird   parser text\nwith spacing.  \n"
    block = RawBlock(page=7, block_index=3, text=raw, x0=1.0, y0=2.0, x1=3.0, y1=4.0)

    rows = compile_source_extractions(
        blocks=[block],
        source_document_id="d" * 64,
        source_document_hash="d" * 64,
        parser="test-parser",
        parser_version="1.2.3",
        now=datetime(2026, 6, 19, tzinfo=timezone.utc),
    )

    assert rows[0].row["raw_text"] == raw
    assert rows[0].row["source_locator"] == "page:7:block:3"


def test_ci004_observation_identity_is_occurrence_based():
    raw = "For God so loved the world."
    source_hash = "a" * 64

    bible = make_observation_id(source_hash, "page:1:block:1:sentence:1", raw)
    mug = make_observation_id(source_hash, "page:1:block:2:sentence:1", raw)
    bible_again = make_observation_id(source_hash, "page:1:block:1:sentence:1", raw)

    assert bible == bible_again
    assert bible != mug
    assert make_semantic_hash(raw) == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_ci004_observation_identity_ignores_normalization():
    source_hash = "b" * 64
    locator = "page:2:block:1:sentence:1"
    raw = "Gatsby’s house was still empty."
    normalized = "Gatsby's house was still empty."

    raw_id = make_observation_id(source_hash, locator, raw)
    assert raw_id == make_observation_id(source_hash, locator, raw)
    assert raw_id != make_observation_id(source_hash, locator, normalized)


def _seed_evidence(store: SQLiteStore) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "c" * 64
    raw = "Evidence remains fixed."
    extraction_locator = make_source_locator(1, 1)
    extraction_id = make_source_extraction_id(
        doc_id,
        extraction_locator,
        raw,
        "test-parser",
        "test",
    )
    obs_locator = make_source_locator(1, 1, 1)
    obs_id = make_observation_id(doc_id, obs_locator, raw)

    store.insert_source_document({
        "id": doc_id,
        "original_filename": "evidence.pdf",
        "file_hash": doc_id,
        "total_pages": 1,
        "registered_at": now,
        "compiler_version": "test",
    })
    store.insert_source_extractions_batch([{
        "id": extraction_id,
        "epistemic_class": "Evidence",
        "document_id": doc_id,
        "page": 1,
        "region": "block:1",
        "raw_text": raw,
        "parser": "test-parser",
        "parser_version": "test",
        "coordinates": "{}",
        "source_locator": extraction_locator,
        "source_hash": doc_id,
        "hash": extraction_id,
        "extracted_at": now,
    }])
    store.insert_observations_batch([{
        "id": obs_id,
        "epistemic_class": "Evidence",
        "source_document_id": doc_id,
        "source_extraction_id": extraction_id,
        "raw_text": raw,
        "source_locator": obs_locator,
        "semantic_hash": make_semantic_hash(raw),
        "page": 1,
        "paragraph": 1,
        "sentence": 1,
        "preceding_observation_id": None,
        "following_observation_id": None,
        "created_at": now,
    }])
    store.insert_provenance_batch([{
        "id": obs_id,
        "observation_id": obs_id,
        "source_document_id": doc_id,
        "source_extraction_id": extraction_id,
        "source_document_hash": doc_id,
        "page": 1,
        "paragraph": 1,
        "sentence": 1,
        "verbatim_text": raw,
        "location_precision": "sentence",
        "char_offset_start": None,
        "char_offset_end": None,
        "bbox_x": None,
        "bbox_y": None,
        "bbox_width": None,
        "bbox_height": None,
        "bbox_dpi": None,
        "created_at": now,
        "compiler_version": "test",
        "compilation_run_id": "test-run",
    }])
    store.insert_observation_derived_batch([{
        "observation_id": obs_id,
        "normalized_text": raw,
        "sentence_tokens": "[]",
        "whitespace_map": "[]",
        "derivation_version": "test",
        "derived_at": now,
    }])
    return {
        "doc_id": doc_id,
        "extraction_id": extraction_id,
        "obs_id": obs_id,
    }


def _insert_test_interpretation(
    store: SQLiteStore,
    observation_id: str,
    perspective: str,
    text: str,
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    interpretation_id = make_interpretation_id(observation_id, perspective, text)
    store.insert_interpretation({
        "id": interpretation_id,
        "observation_id": observation_id,
        "perspective": perspective,
        "perspective_id": None,
        "text": text,
        "evidential_status": "established",
        "evidence_observation_ids": json.dumps([observation_id]),
        "confidence": "human",
        "source": "steward-authored",
        "created_at": now,
    })
    return interpretation_id


def test_ci005_database_rejects_update_delete_for_immutable_evidence(tmp_path):
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_evidence(store)

    checks = [
        ("source_documents", "id", ids["doc_id"], "original_filename"),
        ("source_extractions", "id", ids["extraction_id"], "raw_text"),
        ("observations", "id", ids["obs_id"], "raw_text"),
        ("provenance", "id", ids["obs_id"], "verbatim_text"),
    ]

    for table, key, value, field in checks:
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(f"UPDATE {table} SET {field} = 'mutated' WHERE {key} = ?", (value,))
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(f"DELETE FROM {table} WHERE {key} = ?", (value,))

    store.close()


def test_ci016_observation_derived_is_disposable(tmp_path):
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_evidence(store)

    assert store._conn.execute("SELECT COUNT(*) FROM observation_derived").fetchone()[0] == 1
    store._conn.execute("DELETE FROM observation_derived WHERE observation_id = ?", (ids["obs_id"],))
    store._conn.commit()

    assert store.get_observation_by_id(ids["obs_id"]) is not None
    assert store._conn.execute("SELECT COUNT(*) FROM observation_derived").fetchone()[0] == 0
    store.close()


@needs_pdf
def test_ci013_compiler_emits_constitutional_bundle_shape(tmp_path):
    compiler = Compiler(db_path=tmp_path / "hermeneia.db", build_dir=tmp_path / "build")
    bundle = compiler.compile(GATSBY_PDF)
    compiler.close()

    assert (bundle / "context.json").exists()
    assert (bundle / "hermeneia.db").exists()
    assert not (bundle / "observations.jsonl").exists()
    assert not (bundle / "provenance.jsonl").exists()
    assert not (bundle / "source_document.json").exists()
    assert not (bundle / "manifest.json").exists()

    context = json.loads((bundle / "context.json").read_text())
    assert context["schema"] == "hermeneia-bundle-v1"
    assert context["storage"]["database"] == "hermeneia.db"


# ── CI-014: Monotonic Supersession ───────────────────────────────────────────

def test_ci014_supersession_preserves_original_object(tmp_path):
    """Supersession adds a relation; it must not mutate the superseded object."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_evidence(store)
    old_id = _insert_test_interpretation(
        store,
        ids["obs_id"],
        "literary",
        "The first reading remains historical evidence.",
    )
    new_id = _insert_test_interpretation(
        store,
        ids["obs_id"],
        "literary",
        "The second reading supersedes without erasing the first.",
    )

    original_before = dict(store._conn.execute(
        "SELECT * FROM interpretations WHERE id = ?", (old_id,)
    ).fetchone())

    store.insert_supersession_relation({
        "old_id": old_id,
        "new_id": new_id,
        "reason": "Refined by later steward review.",
        "ratified_at": "2026-06-20T00:00:00+00:00",
    })

    original_after = dict(store._conn.execute(
        "SELECT * FROM interpretations WHERE id = ?", (old_id,)
    ).fetchone())
    relations = store.supersessions_from(old_id)

    assert original_after == original_before
    assert relations == [{
        "old_id": old_id,
        "new_id": new_id,
        "reason": "Refined by later steward review.",
        "ratified_at": "2026-06-20T00:00:00+00:00",
    }]
    store.close()


def test_ci014_supersession_relation_is_append_only(tmp_path):
    """SupersessionRelation rows cannot be updated or deleted."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_evidence(store)
    old_id = _insert_test_interpretation(
        store, ids["obs_id"], "literary", "Original interpretation."
    )
    new_id = _insert_test_interpretation(
        store, ids["obs_id"], "literary", "Superseding interpretation."
    )
    relation = {
        "old_id": old_id,
        "new_id": new_id,
        "reason": "Constitutional append-only test.",
        "ratified_at": "2026-06-20T00:00:00+00:00",
    }
    store.insert_supersession_relation(relation)

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "UPDATE supersession_relations SET reason = 'mutated' WHERE old_id = ?",
            (old_id,),
        )
    store._conn.rollback()

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "DELETE FROM supersession_relations WHERE old_id = ?",
            (old_id,),
        )
    store._conn.rollback()

    assert store.supersession_relation_count() == 1
    assert dict(store._conn.execute(
        "SELECT * FROM interpretations WHERE id = ?", (old_id,)
    ).fetchone())["text"] == "Original interpretation."
    store.close()


def test_ci014_multiple_competing_supersessions_coexist(tmp_path):
    """One object may have multiple superseding descendants without collapse."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_evidence(store)
    old_id = _insert_test_interpretation(
        store, ids["obs_id"], "literary", "Original interpretation."
    )
    new_a = _insert_test_interpretation(
        store, ids["obs_id"], "literary", "Superseding interpretation A."
    )
    new_b = _insert_test_interpretation(
        store, ids["obs_id"], "historical", "Superseding interpretation B."
    )

    store.insert_supersession_relation({
        "old_id": old_id,
        "new_id": new_a,
        "reason": "Literary refinement.",
        "ratified_at": "2026-06-20T00:00:00+00:00",
    })
    store.insert_supersession_relation({
        "old_id": old_id,
        "new_id": new_b,
        "reason": "Historical refinement.",
        "ratified_at": "2026-06-20T00:01:00+00:00",
    })

    relations = store.supersessions_from(old_id)
    assert {row["new_id"] for row in relations} == {new_a, new_b}
    assert len(relations) == 2
    store.close()


def test_ci014_full_supersession_chain_is_traversable(tmp_path):
    """Historical supersession graph remains traversable across generations."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_evidence(store)
    root = _insert_test_interpretation(
        store, ids["obs_id"], "literary", "Root interpretation."
    )
    middle = _insert_test_interpretation(
        store, ids["obs_id"], "literary", "Middle interpretation."
    )
    leaf = _insert_test_interpretation(
        store, ids["obs_id"], "literary", "Leaf interpretation."
    )

    store.insert_supersession_relation({
        "old_id": root,
        "new_id": middle,
        "reason": "First refinement.",
        "ratified_at": "2026-06-20T00:00:00+00:00",
    })
    store.insert_supersession_relation({
        "old_id": middle,
        "new_id": leaf,
        "reason": "Second refinement.",
        "ratified_at": "2026-06-20T00:01:00+00:00",
    })

    chain = store.supersession_descendants(root)
    depths = {(row["old_id"], row["new_id"]): row["depth"] for row in chain}

    assert depths[(root, middle)] == 1
    assert depths[(middle, leaf)] == 2
    assert store.supersessions_to(leaf)[0]["old_id"] == middle
    store.close()


# ── CI-015: Anti-Helpfulness Compliance ──────────────────────────────────────

def test_ci015_source_extraction_preserves_pathological_parser_text_exactly():
    """SourceExtraction must persist parser text without repair or normalization."""
    raw = "  co-\noperate   “quoted”\u00a0text — hyphen-\nation…  \n"
    block = RawBlock(page=1, block_index=9, text=raw, x0=0.0, y0=0.0, x1=1.0, y1=1.0)

    rows = compile_source_extractions(
        blocks=[block],
        source_document_id="e" * 64,
        source_document_hash="e" * 64,
        parser="pathological-parser",
        parser_version="test",
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )

    assert rows[0].row["raw_text"] == raw


def test_ci015_observation_raw_text_partitions_source_without_normalization():
    """Observation raw_text must be exact selected characters, not cleaned text."""
    raw = "  “Odd”   spacing.  Hyphen-\nation remains?  "
    paragraph = Paragraph(
        page=1,
        paragraph=1,
        text=raw,
        x0=0.0,
        y0=0.0,
        x1=100.0,
        y1=20.0,
        source_extraction_id="source-extraction",
        source_locator="page:1:block:1",
        block_index=1,
    )

    records = compile_observations(
        paragraphs=[paragraph],
        source_document_id="f" * 64,
        source_document_hash="f" * 64,
        compilation_run_id="anti-helpfulness",
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )

    observed_raw = "".join(record.obs["raw_text"] for record in records)

    assert observed_raw == raw
    assert records[0].obs["raw_text"].startswith("  “")
    assert records[0].obs["raw_text"].endswith(".  ")
    assert "normalized_text" not in records[0].obs
    assert records[0].derived["normalized_text"] != records[0].obs["raw_text"]


def test_ci015_normalization_storage_only_in_observation_derived(tmp_path):
    """The observations table must not store normalized text."""
    store = SQLiteStore(tmp_path / "test.db")

    observation_cols = {
        row["name"]
        for row in store._conn.execute("PRAGMA table_info(observations)").fetchall()
    }
    derived_cols = {
        row["name"]
        for row in store._conn.execute("PRAGMA table_info(observation_derived)").fetchall()
    }

    assert "normalized_text" not in observation_cols
    assert "normalized_text" in derived_cols
    store.close()


def _write_pathological_pdf(path: Path) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(72, 72, 500, 260),
        "  Odd   spacing with punctuation...\n"
        "Soft-hyphen-like line-\n"
        "break and quoted text.  Next sentence?",
        fontsize=12,
    )
    doc.save(path)
    doc.close()


def test_ci015_pathological_pdf_source_extractions_equal_parser_output(tmp_path):
    """Regression: even pathological PDFs use parser output as the storage oracle."""
    pdf_path = tmp_path / "pathological.pdf"
    _write_pathological_pdf(pdf_path)

    expected_blocks = list(parse_pdf(pdf_path))
    assert expected_blocks

    compiler = Compiler(db_path=tmp_path / "hermeneia.db", build_dir=tmp_path / "build")
    compiler.compile(pdf_path)
    compiler.close()

    conn = sqlite3.connect(tmp_path / "hermeneia.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT source_locator, raw_text FROM source_extractions"
    ).fetchall()
    conn.close()

    expected = {
        make_source_locator(block.page, block.block_index): block.text
        for block in expected_blocks
    }
    stored = {row["source_locator"]: row["raw_text"] for row in rows}

    assert stored == expected


def test_ci015_no_downstream_layer_rewrites_evidence_static():
    """Downstream layers may read evidence but must not rewrite evidence tables."""
    import re

    repo_root = Path(__file__).parent.parent
    downstream_roots = [
        repo_root / "hermeneia" / name
        for name in ("cli", "field", "narrative", "planner", "validation", "web")
    ]
    evidence_tables = {
        "source_documents",
        "source_extractions",
        "observations",
        "provenance",
    }
    write_ops = re.compile(
        r"\b(INSERT|UPDATE|DELETE)\s+(?:OR\s+\w+\s+)?(?:INTO\s+)?(\w+)",
        re.IGNORECASE,
    )

    violations: list[str] = []
    for root in downstream_roots:
        for py_file in root.rglob("*.py"):
            src = py_file.read_text()
            for match in write_ops.finditer(src):
                table = match.group(2).lower()
                if table in evidence_tables:
                    violations.append(
                        f"{py_file.relative_to(repo_root)}: {match.group(0).strip()!r}"
                    )

    assert not violations, "\n".join(violations)


def test_ci015_no_pre_source_extraction_text_repair_helpers_static():
    """Parser and SourceExtraction compiler must not repair text before storage."""
    repo_root = Path(__file__).parent.parent
    checked_files = [
        repo_root / "hermeneia" / "compiler" / "parser.py",
        repo_root / "hermeneia" / "compiler" / "source_extraction_compiler.py",
    ]
    forbidden_tokens = (
        ".strip(",
        ".replace(",
        "normalize_",
        "re.sub",
        "unicodedata",
    )

    violations: list[str] = []
    for py_file in checked_files:
        src = py_file.read_text()
        for token in forbidden_tokens:
            if token in src:
                violations.append(f"{py_file.name}: {token}")

    assert not violations, "\n".join(violations)


@needs_pdf
def test_ci001_ci002_ci003_compiler_persists_evidence_chain(tmp_path):
    compiler = Compiler(db_path=tmp_path / "hermeneia.db", build_dir=tmp_path / "build")
    compiler.compile(GATSBY_PDF)
    compiler.close()

    conn = sqlite3.connect(tmp_path / "hermeneia.db")
    conn.row_factory = sqlite3.Row
    doc = conn.execute("SELECT * FROM source_documents LIMIT 1").fetchone()
    extraction = conn.execute("SELECT * FROM source_extractions LIMIT 1").fetchone()
    obs = conn.execute("SELECT * FROM observations LIMIT 1").fetchone()

    assert doc["id"] == sha256_file(GATSBY_PDF)
    assert extraction["document_id"] == doc["id"]
    assert obs["source_extraction_id"] == extraction["id"]
    assert obs["id"] == make_observation_id(doc["id"], obs["source_locator"], obs["raw_text"])
    conn.close()


@needs_pdf
def test_ci012_web_get_requests_do_not_mutate_database(tmp_path):
    db_path = tmp_path / "hermeneia.db"
    compiler = Compiler(db_path=db_path, build_dir=tmp_path / "build")
    compiler.compile(GATSBY_PDF)
    compiler.close()

    # create_app runs schema migrations (legitimate startup writes).
    # before_hash is taken after initialization so the assertion isolates
    # GET-request behaviour only.
    app = create_app(db_path=db_path)
    client = app.test_client()

    before_hash = sha256_file(db_path)
    before_tables = _table_counts(db_path)

    for url in (
        "/api/health",
        "/api/search?q=Gatsby",
        "/api/trace/1",
        "/api/profiles",
        "/api/matrix",
        "/api/coverage",
    ):
        response = client.get(url)
        assert response.status_code == 200, url

    after_hash = sha256_file(db_path)
    after_tables = _table_counts(db_path)

    assert after_hash == before_hash
    assert after_tables == before_tables


def _table_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    conn.close()
    return counts


# ── Shared seed helper ────────────────────────────────────────────────────────

def _seed_full_chain(
    store: SQLiteStore,
    *,
    architect_terms: list[str] | None = None,
    include_narrative: bool = True,
    include_report: bool = True,
    report_overrides: dict | None = None,
) -> dict:
    """Seed a complete ancestry chain from source_document to validation_report.

    Returns all IDs so tests can traverse the chain.
    """
    now = datetime.now(timezone.utc).isoformat()
    ids = _seed_evidence(store)
    obs_id = ids["obs_id"]

    # Interpretation
    interp_text = "The phrase encodes an epistemological claim."
    perspective_name = "literary"
    perspective_id = make_perspective_id(perspective_name)
    store.register_perspective({
        "id": perspective_id,
        "name": perspective_name,
        "description": "Test perspective",
        "created_at": now,
    })
    interp_id = make_interpretation_id(obs_id, perspective_name, interp_text)
    store.insert_interpretation({
        "id": interp_id,
        "observation_id": obs_id,
        "perspective": perspective_name,
        "perspective_id": perspective_id,
        "text": interp_text,
        "evidential_status": "established",
        "evidence_observation_ids": json.dumps([obs_id]),
        "confidence": 0.9,
        "source": "test",
        "created_at": now,
    })

    if architect_terms:
        store.insert_terms_batch([
            {"id": term_id(term), "term": term}
            for term in architect_terms
        ])
        store.insert_observation_terms_batch([
            {"observation_id": obs_id, "term_id": term_id(term)}
            for term in architect_terms
        ])

    # Blueprint
    sections = [{"claim": "Evidence remains fixed.", "supporting_observations": [obs_id], "supporting_interpretations": [interp_id]}]
    bp_id = make_blueprint_id("Test Blueprint", "Evidence is fixed.", sections)
    store.insert_blueprint(
        {
            "id": bp_id,
            "title": "Test Blueprint",
            "thesis": "Evidence is fixed.",
            "sections": json.dumps(sections),
            "source": "test",
            "created_at": now,
        },
        obs_ids=[obs_id],
        interp_ids=[interp_id],
    )

    # Architect plan (via compiler — deterministic, no LLM)
    result = compile_architect_plan(bp_id, store._conn)
    store.insert_architect_plan(result["plan_row"], result["paragraph_rows"])
    plan_id = result["plan_row"]["id"]

    # Expression profile
    profile_slug = "literary-en"
    profile_id = make_expression_profile_id(profile_slug)
    store.insert_expression_profile({
        "id": profile_id,
        "slug": profile_slug,
        "name": "Literary English",
        "description": "Test profile",
        "language": "en",
        "audience": "general",
        "reading_level": "college",
        "tone": "formal",
        "voice": "active",
        "artist_prompt": "Write formally.",
        "critic_expectations": json.dumps([]),
        "source": "test",
        "created_at": now,
    })

    # Rendered narrative
    narrative_id = make_rendered_narrative_id(plan_id, "null", profile_id)
    if include_narrative:
        store.insert_rendered_narrative({
            "id": narrative_id,
            "architect_plan_id": plan_id,
            "provider": "null",
            "expression_profile_id": profile_id,
            "text": "Evidence remains fixed.",
            "prompt_used": "Test prompt.",
            "execution_config": json.dumps({
                "provider": "null",
                "model_id": None,
                "sdk_version": None,
                "request_schema_version": "1",
                "constitutional_profile": {
                    "constitution_version": "1.0.0",
                    "authority_index_version": "1.0.0",
                    "invariant_profile": "CI-001..CI-016",
                    "architecture_profile": "v1.0",
                },
            }),
            "created_at": now,
        })

    # Validation report
    report_id = make_validation_report_id(narrative_id)
    report_row = {
        "id": report_id,
        "rendered_narrative_id": narrative_id,
        "architect_plan_id": plan_id,
        "expression_profile_id": profile_id,
        "semantic_fidelity": 1.0,
        "required_terms_present": json.dumps([]),
        "required_terms_missing": json.dumps([]),
        "unsupported_claims": json.dumps([]),
        "omitted_observations": json.dumps([]),
        "omitted_interpretations": json.dumps([]),
        "semantic_drift": 0.0,
        "warnings": json.dumps([]),
        "approved": 1,
        "created_at": now,
    }
    if report_overrides:
        report_row.update(report_overrides)
    if include_report:
        if not include_narrative:
            raise ValueError("include_report requires include_narrative")
        store.insert_validation_report(report_row)

    return {
        **ids,
        "interp_id": interp_id,
        "bp_id": bp_id,
        "plan_id": plan_id,
        "profile_id": profile_id,
        "narrative_id": narrative_id,
        "report_id": report_id,
    }


# ── CI-006: Strict Ancestry ───────────────────────────────────────────────────

def test_ci006_foreign_keys_enforced_on_each_layer(tmp_path):
    """SQLite must reject inserts with a dangling parent FK at every layer."""
    store = SQLiteStore(tmp_path / "test.db")
    conn = store._conn

    phantom = "z" * 64

    cases = [
        # (table, row_dict)
        ("source_extractions", {
            "id": phantom, "epistemic_class": "Evidence", "document_id": phantom,
            "page": 1, "region": "block:1", "raw_text": "x", "parser": "p",
            "parser_version": "1", "coordinates": "{}", "source_locator": "page:1:block:1",
            "source_hash": phantom, "hash": phantom,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }),
        ("observations", {
            "id": phantom, "epistemic_class": "Evidence",
            "source_document_id": phantom, "source_extraction_id": phantom,
            "raw_text": "x", "source_locator": "page:1:block:1:sentence:1",
            "semantic_hash": phantom, "page": 1, "paragraph": 1, "sentence": 1,
            "preceding_observation_id": None, "following_observation_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }),
        ("interpretations", {
            "id": phantom, "observation_id": phantom, "perspective": "test",
            "perspective_id": None, "text": "x", "evidential_status": "established",
            "evidence_observation_ids": "[]", "confidence": 0.5, "source": "test",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }),
        ("architect_plans", {
            "id": phantom, "blueprint_id": phantom, "blueprint_hash": phantom,
            "title": "x", "source": "test",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }),
        ("rendered_narratives", {
            "id": phantom, "architect_plan_id": phantom, "provider": "null",
            "expression_profile_id": None, "text": "x", "prompt_used": "x",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }),
        ("validation_reports", {
            "id": phantom, "rendered_narrative_id": phantom,
            "architect_plan_id": phantom, "expression_profile_id": None,
            "semantic_fidelity": 1.0, "required_terms_present": "[]",
            "required_terms_missing": "[]", "unsupported_claims": "[]",
            "omitted_observations": "[]", "omitted_interpretations": "[]",
            "semantic_drift": 0.0, "warnings": "[]", "approved": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }),
    ]

    for table, row in cases:
        cols = ", ".join(row.keys())
        placeholders = ", ".join(f":{k}" for k in row.keys())
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", row)
            conn.commit()

    store.close()


def test_ci006_full_ancestry_chain_traversable(tmp_path):
    """Every node in the chain must be reachable from the leaf back to the root."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store)
    conn = store._conn

    # Traverse upward: validation_report → rendered_narrative → architect_plan
    #   → blueprint → (blueprint_observation_links) → observation
    #   → source_extraction → source_document

    report = conn.execute(
        "SELECT * FROM validation_reports WHERE id = ?", (ids["report_id"],)
    ).fetchone()
    assert report is not None, "validation_report missing"

    narrative = conn.execute(
        "SELECT * FROM rendered_narratives WHERE id = ?", (report["rendered_narrative_id"],)
    ).fetchone()
    assert narrative is not None, "rendered_narrative missing"
    assert narrative["id"] == ids["narrative_id"]

    plan = conn.execute(
        "SELECT * FROM architect_plans WHERE id = ?", (narrative["architect_plan_id"],)
    ).fetchone()
    assert plan is not None, "architect_plan missing"
    assert plan["id"] == ids["plan_id"]

    blueprint = conn.execute(
        "SELECT * FROM narrative_blueprints WHERE id = ?", (plan["blueprint_id"],)
    ).fetchone()
    assert blueprint is not None, "narrative_blueprint missing"
    assert blueprint["id"] == ids["bp_id"]

    obs_link = conn.execute(
        "SELECT * FROM blueprint_observation_links WHERE blueprint_id = ?", (blueprint["id"],)
    ).fetchone()
    assert obs_link is not None, "blueprint_observation_link missing"

    observation = conn.execute(
        "SELECT * FROM observations WHERE id = ?", (obs_link["observation_id"],)
    ).fetchone()
    assert observation is not None, "observation missing"
    assert observation["id"] == ids["obs_id"]

    extraction = conn.execute(
        "SELECT * FROM source_extractions WHERE id = ?", (observation["source_extraction_id"],)
    ).fetchone()
    assert extraction is not None, "source_extraction missing"
    assert extraction["document_id"] == ids["doc_id"]

    doc = conn.execute(
        "SELECT * FROM source_documents WHERE id = ?", (extraction["document_id"],)
    ).fetchone()
    assert doc is not None, "source_document missing"
    assert doc["id"] == ids["doc_id"]

    store.close()


# ── CI-008: Plural Interpretation ────────────────────────────────────────────

def test_ci008_multiple_interpretations_coexist_per_observation(tmp_path):
    """A single observation must support multiple independent interpretations."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_evidence(store)
    obs_id = ids["obs_id"]
    now = datetime.now(timezone.utc).isoformat()

    perspectives = [
        ("literary", "The phrase is a rhetorical device."),
        ("historical", "The phrase reflects 19th-century usage."),
        ("psychoanalytic", "The phrase reveals repressed anxiety."),
    ]

    inserted_ids = []
    for perspective, text in perspectives:
        iid = make_interpretation_id(obs_id, perspective, text)
        store.insert_interpretation({
            "id": iid,
            "observation_id": obs_id,
            "perspective": perspective,
            "perspective_id": None,
            "text": text,
            "evidential_status": "established",
            "evidence_observation_ids": json.dumps([obs_id]),
            "confidence": 0.8,
            "source": "test",
            "created_at": now,
        })
        inserted_ids.append(iid)

    stored = store.interpretations_for_observation(obs_id)
    assert len(stored) == 3
    stored_ids = {r["id"] for r in stored}
    assert set(inserted_ids) == stored_ids


# ── CI-009 / INV-XI: Critic Authority Boundary (static) ──────────────────────

def test_inv_xi_critic_source_only_writes_validation_reports(tmp_path):
    """Static: the Narrative Fidelity Critic (cli/critic_cmd.py and
    compiler/critic/narrative_fidelity.py) must contain no INSERT/UPDATE/DELETE
    targeting any table other than validation_reports.

    The Interpretation Grounding Critic (compiler/critic/report.py) writes to
    critic_reports (an operational artifact) and is governed by a separate boundary.
    """
    import re
    critic_files = [
        Path(__file__).parent.parent / "hermeneia" / "cli" / "critic_cmd.py",
        Path(__file__).parent.parent / "hermeneia" / "compiler" / "critic" / "narrative_fidelity.py",
    ]

    write_ops = re.compile(
        r"\b(INSERT|UPDATE|DELETE)\s+(?:OR\s+\w+\s+)?(?:INTO\s+)?(\w+)",
        re.IGNORECASE,
    )
    forbidden_tables = re.compile(
        r"^(?!validation_reports$)(?!sqlite_)",
        re.IGNORECASE,
    )

    violations: list[str] = []
    for fpath in critic_files:
        src = fpath.read_text()
        for m in write_ops.finditer(src):
            table = m.group(2)
            if table.lower() != "validation_reports":
                violations.append(f"{fpath.name}: {m.group(0).strip()!r}")

    assert not violations, (
        "Critic code wrote to a table other than validation_reports:\n"
        + "\n".join(violations)
    )


# ── CI-009: Contract Dominance — Architect plan is content-addressable ────────

def test_ci009_architect_plan_id_is_content_addressable(tmp_path):
    """Recompiling the same blueprint must yield the same plan ID (INSERT OR IGNORE = idempotent).

    This is the structural form of plan immutability: the ID encodes the blueprint
    content, so a plan for the same blueprint cannot produce a different ID.
    """
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store)
    bp_id = ids["bp_id"]
    plan_id = ids["plan_id"]

    result2 = compile_architect_plan(bp_id, store._conn)
    assert result2["plan_row"]["id"] == plan_id, (
        "Re-compiling the same blueprint produced a different plan ID"
    )

    # Inserting again must be a silent no-op (INSERT OR IGNORE)
    before_count = store._conn.execute("SELECT COUNT(*) FROM architect_plans").fetchone()[0]
    store.insert_architect_plan(result2["plan_row"], result2["paragraph_rows"])
    after_count = store._conn.execute("SELECT COUNT(*) FROM architect_plans").fetchone()[0]
    assert before_count == after_count, "Duplicate plan insert added a row — INSERT OR IGNORE broken"

    store.close()


# ── INV-09: Architect Invariance Across Profiles ──────────────────────────────

def test_inv09_same_blueprint_produces_same_plan_id_regardless_of_profile(tmp_path):
    """make_architect_plan_id(blueprint_id) must be deterministic and profile-agnostic."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store)
    bp_id = ids["bp_id"]

    # Compile the plan a second time — must return the exact same ID
    result2 = compile_architect_plan(bp_id, store._conn)
    assert result2["plan_row"]["id"] == ids["plan_id"], (
        "Architect plan ID changed between compilations of the same blueprint"
    )

    # Explicitly: plan ID must not depend on any profile slug
    assert make_architect_plan_id(bp_id) == make_architect_plan_id(bp_id)

    store.close()


# ── INV-10: Critic Determinism ────────────────────────────────────────────────

def test_inv10_validation_report_id_is_deterministic(tmp_path):
    """make_validation_report_id must be idempotent: same narrative → same report ID."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store)
    narrative_id = ids["narrative_id"]

    id1 = make_validation_report_id(narrative_id)
    id2 = make_validation_report_id(narrative_id)
    assert id1 == id2

    # INSERT OR IGNORE: inserting the same report a second time must not error
    now = datetime.now(timezone.utc).isoformat()
    store.insert_validation_report({
        "id": id1,
        "rendered_narrative_id": narrative_id,
        "architect_plan_id": ids["plan_id"],
        "expression_profile_id": ids["profile_id"],
        "semantic_fidelity": 0.5,        # different score — must be silently ignored
        "required_terms_present": "[]",
        "required_terms_missing": "[]",
        "unsupported_claims": "[]",
        "omitted_observations": "[]",
        "omitted_interpretations": "[]",
        "semantic_drift": 0.5,
        "warnings": "[]",
        "approved": 0,
        "created_at": now,
    })

    # The original score must survive
    row = store.validation_report_for_narrative(narrative_id)
    assert row["semantic_fidelity"] == 1.0, "INSERT OR IGNORE must not overwrite existing report"

    store.close()


# ── INV-XIII: Steward Context Shall Not Determine Semantic Standing ──────────

def test_inv_xiii_steward_credentials_do_not_drive_semantic_standing():
    """Static: steward credential/status fields must not feed automatic sort,
    filter, ranking, suppression, or scoring logic.

    docs/04_Invariants.md INV-XIII allows steward provenance to be preserved and
    surfaced as context. It forbids using institutional credentials, reputation,
    identity, or social status as inputs to semantic standing decisions.
    """
    import re

    repo_root = Path(__file__).parent.parent
    guarded_paths = [
        repo_root / "hermeneia" / "web",
        repo_root / "hermeneia" / "cli",
        repo_root / "hermeneia" / "field",
        repo_root / "hermeneia" / "planner",
        repo_root / "hermeneia" / "narrative",
        repo_root / "hermeneia" / "compiler",
        repo_root / "hermeneia" / "storage",
    ]

    credential_terms = (
        "credential", "credentials", "degree", "degrees", "phd", "md",
        "institution", "institutional", "reputation", "social_status",
        "social status", "institutional_status", "steward_status",
        "steward_identity",
    )
    decision_terms = (
        "sort", "sorted", "order", "order_by", "filter", "rank", "ranking",
        "score", "scoring", "suppress", "suppression", "semantic_standing",
        "standing",
    )
    credential_re = re.compile("|".join(re.escape(t) for t in credential_terms), re.IGNORECASE)
    decision_re = re.compile("|".join(re.escape(t) for t in decision_terms), re.IGNORECASE)
    sql_decision_re = re.compile(
        r"\b(ORDER\s+BY|WHERE|HAVING)\b[^\n;]*(credential|degree|phd|md|institution|"
        r"reputation|social_status|social\s+status|institutional_status|"
        r"steward_status|steward_identity)",
        re.IGNORECASE,
    )

    violations: list[str] = []

    for base in guarded_paths:
        for fpath in sorted(base.rglob("*.py")):
            rel = fpath.relative_to(repo_root)
            src = fpath.read_text()

            for match in sql_decision_re.finditer(src):
                violations.append(f"{rel}: SQL credential decision input: {match.group(0).strip()!r}")

            for lineno, line in enumerate(src.splitlines(), start=1):
                if credential_re.search(line) and decision_re.search(line):
                    violations.append(
                        f"{rel}:{lineno}: credential term appears in decision logic: "
                        f"{line.strip()!r}"
                    )

    assert not violations, (
        "INV-XIII violated — steward credentials/status flowed into semantic "
        "sort/filter/ranking/suppression/scoring logic:\n"
        + "\n".join(violations)
    )


# ── CI-007: Downward Non-Interference (static) ────────────────────────────────

def test_ci007_narrative_layer_cannot_write_evidence_tables(tmp_path):
    """Static: web/app.py and cli/*.py (except ingest) must contain no INSERT/UPDATE/DELETE
    targeting evidence tables (source_documents, source_extractions, observations, provenance).
    """
    import re
    repo_root = Path(__file__).parent.parent

    evidence_tables = {
        "source_documents", "source_extractions",
        "observations", "provenance", "observation_derived",
    }

    write_ops = re.compile(
        r"\b(INSERT|UPDATE|DELETE)\s+(?:OR\s+\w+\s+)?(?:INTO\s+)?(\w+)",
        re.IGNORECASE,
    )

    allowed_write_files = {
        "ingest_cmd.py",    # ingest is the only writer
        "sqlite.py",        # storage layer (not narrative/CLI)
        "compiler.py",
        "source_extraction_compiler.py",
        "observation_compiler.py",
    }

    violations: list[str] = []

    scan_paths = list((repo_root / "hermeneia" / "web").rglob("*.py")) + \
                 list((repo_root / "hermeneia" / "cli").rglob("*.py"))

    for fpath in scan_paths:
        if fpath.name in allowed_write_files:
            continue
        src = fpath.read_text()
        for m in write_ops.finditer(src):
            table = m.group(2).lower()
            if table in evidence_tables:
                violations.append(f"{fpath.relative_to(repo_root)}: {m.group(0).strip()!r}")

    assert not violations, (
        "Narrative/CLI layer attempted to write to an evidence table:\n"
        + "\n".join(violations)
    )
