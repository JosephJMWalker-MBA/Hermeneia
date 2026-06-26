"""
Tests for Session 007 — Artist.

Proves:
- ArtistProvider Protocol is satisfied by NullArtistProvider
- NullArtistProvider returns the expected placeholder
- Prompt is generated deterministically (same plan → same prompt)
- Prompt contains all required structural elements
- make_rendered_narrative_id is deterministic
- RenderedNarrative storage is idempotent
- rendered_narrative_for_plan retrieves correctly
- rendered_narrative_count works
- AnthropicArtistProvider raises ImportError if SDK absent
- get_provider resolves 'null' → NullArtistProvider
- get_provider raises ValueError for unknown providers
- RenderedNarrative ontology model is frozen
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.ontology.rendered_narrative import RenderedNarrative
from hermeneia.storage.sqlite import SQLiteStore, ensure_artist_tables
from hermeneia.storage.hashing import make_rendered_narrative_id
from hermeneia.narrative.artist_providers import (
    ArtistProvider,
    NullArtistProvider,
    generate_prompt,
    get_provider,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return SQLiteStore(tmp_path / "test.db")


@pytest.fixture
def conn(store):
    ensure_artist_tables(store._conn)
    return store._conn


def _seed_full_pipeline(store: SQLiteStore) -> dict:
    """Seed observation → blueprint → architect plan. Return ids."""
    from hermeneia.storage.hashing import (
        make_observation_id,
        make_blueprint_id,
        make_source_extraction_id,
        make_source_locator,
        make_semantic_hash,
    )
    from hermeneia.compiler.architect import compile_architect_plan
    import hashlib

    doc_id = "a" * 64
    store.insert_source_document({
        "id": doc_id,
        "original_filename": "test.pdf",
        "file_hash": doc_id,
        "total_pages": 1,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "compiler_version": "test",
    })

    extraction_text = "The green light glowed."
    extraction_locator = make_source_locator(1, 1)
    extraction_id = make_source_extraction_id(
        doc_id,
        extraction_locator,
        extraction_text,
        "test-parser",
        "test",
    )
    store.insert_source_extractions_batch([{
        "id": extraction_id,
        "epistemic_class": "Evidence",
        "document_id": doc_id,
        "page": 1,
        "region": "block:1",
        "raw_text": extraction_text,
        "parser": "test-parser",
        "parser_version": "test",
        "coordinates": "{}",
        "source_locator": extraction_locator,
        "source_hash": doc_id,
        "hash": extraction_id,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }])

    obs_locator = make_source_locator(1, 1, 1)
    obs_id = make_observation_id(doc_id, obs_locator, extraction_text)
    store.insert_observations_batch([{
        "id": obs_id,
        "epistemic_class": "Evidence",
        "source_document_id": doc_id,
        "source_extraction_id": extraction_id,
        "raw_text": extraction_text,
        "normalized_text": extraction_text,
        "source_locator": obs_locator,
        "semantic_hash": make_semantic_hash(extraction_text),
        "page": 1, "paragraph": 1, "sentence": 1,
        "preceding_observation_id": None,
        "following_observation_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }])

    terms = ["green", "light", "glowed"]
    store.insert_terms_batch([{"id": hashlib.sha256(t.encode()).hexdigest(), "term": t} for t in terms])
    store.insert_observation_terms_batch([
        {"observation_id": obs_id, "term_id": hashlib.sha256(t.encode()).hexdigest()}
        for t in terms
    ])

    from hermeneia.storage.hashing import make_interpretation_id
    interp_id = make_interpretation_id(obs_id, "Literary", "The light means hope.")
    store.insert_interpretation({
        "id": interp_id,
        "observation_id": obs_id,
        "perspective": "Literary",
        "perspective_id": None,
        "text": "The light means hope.",
        "evidential_status": "speculative",
        "evidence_observation_ids": "[]",
        "confidence": "human",
        "source": "steward-authored",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    sections = [{"claim": "Introduce the motif", "supporting_observations": [obs_id], "supporting_interpretations": [interp_id]}]
    bp_id = make_blueprint_id("Test", "A thesis.", sections)
    store.insert_blueprint(
        {"id": bp_id, "title": "Test", "thesis": "A thesis.", "sections": json.dumps(sections),
         "source": "steward-authored", "created_at": datetime.now(timezone.utc).isoformat()},
        obs_ids=[obs_id], interp_ids=[interp_id],
    )

    ensure_artist_tables(store._conn)
    result = compile_architect_plan(bp_id, store._conn)
    store.insert_architect_plan(result["plan_row"], result["paragraph_rows"])

    return {"obs_id": obs_id, "bp_id": bp_id, "plan_id": result["plan_row"]["id"]}


# ── Protocol compliance ───────────────────────────────────────────────────────

def test_null_provider_satisfies_protocol():
    p = NullArtistProvider()
    assert isinstance(p, ArtistProvider)


def test_null_provider_name():
    assert NullArtistProvider().provider_name == "null"


def test_null_provider_render_returns_placeholder():
    text = NullArtistProvider().render("any prompt")
    assert "[Artist not configured" in text


# ── Prompt generation ─────────────────────────────────────────────────────────

def test_prompt_is_deterministic(store, conn):
    ids = _seed_full_pipeline(store)
    plan = dict(conn.execute("SELECT * FROM architect_plans WHERE id = ?", (ids["plan_id"],)).fetchone())
    paras = [dict(r) for r in conn.execute(
        "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx", (ids["plan_id"],)
    ).fetchall()]

    p1 = generate_prompt(plan, paras, conn)
    p2 = generate_prompt(plan, paras, conn)
    assert p1 == p2


def test_prompt_contains_purpose(store, conn):
    ids = _seed_full_pipeline(store)
    plan = dict(conn.execute("SELECT * FROM architect_plans WHERE id = ?", (ids["plan_id"],)).fetchone())
    paras = [dict(r) for r in conn.execute(
        "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx", (ids["plan_id"],)
    ).fetchall()]
    prompt = generate_prompt(plan, paras, conn)
    assert "Introduce the motif" in prompt


def test_prompt_contains_obs_reference(store, conn):
    ids = _seed_full_pipeline(store)
    plan = dict(conn.execute("SELECT * FROM architect_plans WHERE id = ?", (ids["plan_id"],)).fetchone())
    paras = [dict(r) for r in conn.execute(
        "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx", (ids["plan_id"],)
    ).fetchall()]
    prompt = generate_prompt(plan, paras, conn)
    assert "OBS-1" in prompt


def test_prompt_contains_artist_instruction(store, conn):
    ids = _seed_full_pipeline(store)
    plan = dict(conn.execute("SELECT * FROM architect_plans WHERE id = ?", (ids["plan_id"],)).fetchone())
    paras = [dict(r) for r in conn.execute(
        "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx", (ids["plan_id"],)
    ).fetchall()]
    prompt = generate_prompt(plan, paras, conn)
    assert "You are the Artist" in prompt
    assert "Do not invent meaning" in prompt


def test_prompt_contains_plan_title(store, conn):
    ids = _seed_full_pipeline(store)
    plan = dict(conn.execute("SELECT * FROM architect_plans WHERE id = ?", (ids["plan_id"],)).fetchone())
    paras = [dict(r) for r in conn.execute(
        "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx", (ids["plan_id"],)
    ).fetchall()]
    prompt = generate_prompt(plan, paras, conn)
    assert "Test" in prompt  # plan title


# ── ID formula ────────────────────────────────────────────────────────────────

def test_rendered_narrative_id_is_deterministic():
    plan_id = "p" * 64
    assert make_rendered_narrative_id(plan_id, "null") == make_rendered_narrative_id(plan_id, "null")


def test_rendered_narrative_id_differs_by_provider():
    plan_id = "p" * 64
    assert make_rendered_narrative_id(plan_id, "null") != make_rendered_narrative_id(plan_id, "anthropic")


# ── Storage ───────────────────────────────────────────────────────────────────

def _make_narrative_row(plan_id: str, provider: str = "null", system_prompt_id: str | None = None) -> dict:
    return {
        "id": make_rendered_narrative_id(plan_id, provider, system_prompt_id),
        "architect_plan_id": plan_id,
        "provider": provider,
        "system_prompt_id": system_prompt_id,
        "text": "[Artist not configured]",
        "prompt_used": "You are the Artist.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_insert_rendered_narrative_is_idempotent(store):
    ids = _seed_full_pipeline(store)
    row = _make_narrative_row(ids["plan_id"])
    store.insert_rendered_narrative(row)
    store.insert_rendered_narrative(row)
    assert store.rendered_narrative_count() == 1


def test_rendered_narrative_for_plan_retrieves(store):
    ids = _seed_full_pipeline(store)
    row = _make_narrative_row(ids["plan_id"])
    store.insert_rendered_narrative(row)
    result = store.rendered_narrative_for_plan(ids["plan_id"])
    assert result is not None
    assert result["provider"] == "null"


def test_rendered_narrative_for_plan_returns_none_when_absent(store):
    ids = _seed_full_pipeline(store)
    assert store.rendered_narrative_for_plan(ids["plan_id"]) is None


def test_rendered_narrative_count_zero_initially(store):
    _seed_full_pipeline(store)
    assert store.rendered_narrative_count() == 0


def test_rendered_narrative_count_increments(store):
    ids = _seed_full_pipeline(store)
    store.insert_rendered_narrative(_make_narrative_row(ids["plan_id"]))
    assert store.rendered_narrative_count() == 1


# ── Provider registry ─────────────────────────────────────────────────────────

def test_get_provider_null():
    p = get_provider("null")
    assert isinstance(p, NullArtistProvider)


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("banana")


def test_anthropic_provider_raises_without_sdk():
    """AnthropicArtistProvider must raise ImportError if anthropic not installed."""
    try:
        import anthropic  # noqa: F401
        pytest.skip("anthropic SDK is installed — skip absence test")
    except ImportError:
        pass
    from hermeneia.narrative.artist_providers import AnthropicArtistProvider
    with pytest.raises(ImportError, match="anthropic package required"):
        AnthropicArtistProvider()


# ── Ontology model ────────────────────────────────────────────────────────────

def test_rendered_narrative_is_frozen():
    rn = RenderedNarrative(
        id="x" * 64,
        architect_plan_id="p" * 64,
        provider="null",
        text="[Artist not configured]",
        prompt_used="You are the Artist.",
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(Exception):
        rn.text = "changed"


def test_null_provider_full_flow(store, conn):
    """End-to-end: generate prompt → NullArtist render → store → retrieve."""
    ids = _seed_full_pipeline(store)
    plan = dict(conn.execute("SELECT * FROM architect_plans WHERE id = ?", (ids["plan_id"],)).fetchone())
    paras = [dict(r) for r in conn.execute(
        "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
        (ids["plan_id"],)
    ).fetchall()]

    prompt = generate_prompt(plan, paras, conn)
    provider = NullArtistProvider()
    text = provider.render(prompt)

    row = {
        "id": make_rendered_narrative_id(ids["plan_id"], provider.provider_name, None),
        "architect_plan_id": ids["plan_id"],
        "provider": provider.provider_name,
        "system_prompt_id": None,
        "text": text,
        "prompt_used": prompt,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    store.insert_rendered_narrative(row)

    retrieved = store.rendered_narrative_for_plan(ids["plan_id"])
    assert retrieved["text"] == text
    assert retrieved["prompt_used"] == prompt
    assert retrieved["provider"] == "null"
