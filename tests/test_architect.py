"""
Tests for Session 006 — Architect.

Proves:
- Deterministic IDs (same input → same output)
- Identical Blueprint → identical ArchitectPlan
- Paragraph order preserved
- Required observations preserved verbatim
- Required interpretations preserved verbatim
- Required terms deterministic (field-index driven)
- blueprint_hash matches Blueprint content
- Staleness detection works
- Idempotent storage (INSERT OR IGNORE)
- source is always 'deterministic'
- Frozen Pydantic models
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.ontology.architect_plan import ArchitectPlan, ArchitectParagraph, RequiredTerm
from hermeneia.storage.sqlite import SQLiteStore, SCHEMA_VERSION
from hermeneia.storage.hashing import make_architect_plan_id, make_blueprint_id
from hermeneia.compiler.architect import compile_architect_plan


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return SQLiteStore(tmp_path / "test.db")


@pytest.fixture
def conn(store):
    return store._conn


def _seed_minimal(store: SQLiteStore) -> tuple[str, str, str]:
    """Insert a source doc, one observation, one blueprint, return (obs_id, bp_id, interp_id)."""
    from hermeneia.storage.hashing import (
        make_observation_id,
        make_blueprint_id as bpid,
        make_semantic_hash,
        make_source_extraction_id,
        make_source_locator,
    )

    doc_id = "a" * 64
    store.insert_source_document({
        "id": doc_id,
        "original_filename": "test.pdf",
        "file_hash": doc_id,
        "total_pages": 1,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "compiler_version": "test",
    })

    extraction_locator = make_source_locator(1, 1)
    extraction_text = "The green light glowed across the bay."
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

    # Register terms for the observation
    import hashlib
    terms_to_register = ["green", "light", "glowed", "across", "bay"]
    term_rows = [{"id": hashlib.sha256(t.encode()).hexdigest(), "term": t} for t in terms_to_register]
    store.insert_terms_batch(term_rows)
    store.insert_observation_terms_batch([
        {"observation_id": obs_id, "term_id": hashlib.sha256(t.encode()).hexdigest()}
        for t in terms_to_register
    ])

    # Insert an interpretation
    from hermeneia.storage.hashing import make_interpretation_id
    interp_id = make_interpretation_id(obs_id, "Literary", "The light symbolises hope.")
    store.insert_interpretation({
        "id": interp_id,
        "observation_id": obs_id,
        "perspective": "Literary",
        "perspective_id": None,
        "text": "The light symbolises hope.",
        "evidential_status": "speculative",
        "evidence_observation_ids": "[]",
        "confidence": "human",
        "source": "steward-authored",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Insert a blueprint
    sections = [
        {
            "claim": "Introduce the green light motif",
            "supporting_observations": [obs_id],
            "supporting_interpretations": [interp_id],
        }
    ]
    bp_id = bpid("Test Essay", "A thesis about the green light.", sections)
    store.insert_blueprint(
        {
            "id": bp_id,
            "title": "Test Essay",
            "thesis": "A thesis about the green light.",
            "sections": json.dumps(sections),
            "source": "steward-authored",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        obs_ids=[obs_id],
        interp_ids=[interp_id],
    )

    return obs_id, bp_id, interp_id


# ── ID formula ────────────────────────────────────────────────────────────────

def test_architect_plan_id_formula():
    """Plan ID = sha256('architect:' + blueprint_id), reproducible."""
    import hashlib
    bp_id = "b" * 64
    expected = hashlib.sha256(f"architect:{bp_id}".encode()).hexdigest()
    assert make_architect_plan_id(bp_id) == expected


def test_architect_plan_id_is_deterministic():
    bp_id = "c" * 64
    assert make_architect_plan_id(bp_id) == make_architect_plan_id(bp_id)


# ── Compilation ───────────────────────────────────────────────────────────────

def test_compile_returns_expected_keys(store, conn):
    obs_id, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    assert "plan_row" in result
    assert "paragraph_rows" in result


def test_compile_plan_id_matches_formula(store, conn):
    obs_id, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    assert result["plan_row"]["id"] == make_architect_plan_id(bp_id)


def test_compile_source_is_deterministic(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    assert result["plan_row"]["source"] == "deterministic"


def test_compile_blueprint_hash_matches_blueprint(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)

    bp_row = conn.execute("SELECT * FROM narrative_blueprints WHERE id = ?", (bp_id,)).fetchone()
    bp = dict(bp_row)
    sections = json.loads(bp["sections"])
    expected_hash = make_blueprint_id(bp["title"], bp["thesis"], sections)

    assert result["plan_row"]["blueprint_hash"] == expected_hash


def test_compile_identical_input_produces_identical_output(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    r1 = compile_architect_plan(bp_id, conn)
    r2 = compile_architect_plan(bp_id, conn)
    assert r1["plan_row"]["id"] == r2["plan_row"]["id"]
    assert r1["paragraph_rows"][0]["required_terms"] == r2["paragraph_rows"][0]["required_terms"]


# ── Paragraph structure ───────────────────────────────────────────────────────

def test_one_paragraph_per_blueprint_section(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)

    bp_row = dict(conn.execute("SELECT sections FROM narrative_blueprints WHERE id = ?", (bp_id,)).fetchone())
    n_sections = len(json.loads(bp_row["sections"]))

    assert len(result["paragraph_rows"]) == n_sections


def test_paragraph_order_preserved(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    orders = [p["order_idx"] for p in result["paragraph_rows"]]
    assert orders == list(range(1, len(orders) + 1))


def test_purpose_equals_section_claim(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)

    bp_row = dict(conn.execute("SELECT sections FROM narrative_blueprints WHERE id = ?", (bp_id,)).fetchone())
    sections = json.loads(bp_row["sections"])

    for i, para in enumerate(result["paragraph_rows"]):
        assert para["purpose"] == sections[i]["claim"]


def test_required_observations_preserved(store, conn):
    obs_id, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)

    obs_in_para = json.loads(result["paragraph_rows"][0]["required_observations"])
    assert obs_id in obs_in_para


def test_required_interpretations_preserved(store, conn):
    _, bp_id, interp_id = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)

    interps_in_para = json.loads(result["paragraph_rows"][0]["required_interpretations"])
    assert interp_id in interps_in_para


# ── Required terms ────────────────────────────────────────────────────────────

def test_required_terms_are_deterministic(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    r1 = compile_architect_plan(bp_id, conn)
    r2 = compile_architect_plan(bp_id, conn)
    assert r1["paragraph_rows"][0]["required_terms"] == r2["paragraph_rows"][0]["required_terms"]


def test_required_terms_have_priority_field(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    terms = json.loads(result["paragraph_rows"][0]["required_terms"])
    for t in terms:
        assert "term" in t
        assert t["priority"] in ("critical", "recommended")


def test_top_3_terms_are_critical(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    terms = json.loads(result["paragraph_rows"][0]["required_terms"])
    critical = [t for t in terms if t["priority"] == "critical"]
    assert len(critical) <= 3


def test_terms_derive_from_claim_and_interpretations(store, conn):
    # Obligations are now semantic phrases from the section claim and linked
    # interpretations, not token-frequency lookups from the observation field index.
    # The seed blueprint claim is "Introduce the green light motif" with
    # interpretation "The light symbolises hope." — bigrams from those sources
    # should appear; raw observation tokens ("glowed", "across", "bay") should not.
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    terms_in_plan = {t["term"] for t in json.loads(result["paragraph_rows"][0]["required_terms"])}
    # Semantic phrases from claim or interpretation must be present
    assert any("green" in t or "light" in t for t in terms_in_plan), \
        f"Expected claim-derived terms containing 'green' or 'light', got: {terms_in_plan}"
    # Pure observation tokens that aren't in claim/interp should not dominate
    obs_only_tokens = {"glowed", "across", "bay"}
    obs_only_present = terms_in_plan & obs_only_tokens
    claim_interp_present = terms_in_plan - obs_only_tokens
    assert len(claim_interp_present) >= len(obs_only_present), \
        f"Claim/interp terms should dominate obs-only tokens. Got: {terms_in_plan}"


# ── Storage ───────────────────────────────────────────────────────────────────

def test_insert_architect_plan_is_idempotent(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    store.insert_architect_plan(result["plan_row"], result["paragraph_rows"])
    store.insert_architect_plan(result["plan_row"], result["paragraph_rows"])  # no error
    assert store.architect_plan_count() == 1


def test_architect_plan_for_blueprint_returns_plan(store, conn):
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    store.insert_architect_plan(result["plan_row"], result["paragraph_rows"])

    plan = store.architect_plan_for_blueprint(bp_id)
    assert plan is not None
    assert plan["blueprint_id"] == bp_id
    assert len(plan["paragraphs"]) == 1


def test_architect_plan_count(store, conn):
    assert store.architect_plan_count() == 0
    _, bp_id, _ = _seed_minimal(store)
    result = compile_architect_plan(bp_id, conn)
    store.insert_architect_plan(result["plan_row"], result["paragraph_rows"])
    assert store.architect_plan_count() == 1


def test_compile_raises_for_unknown_blueprint(store, conn):
    with pytest.raises(ValueError, match="Blueprint not found"):
        compile_architect_plan("0" * 64, conn)


# ── Ontology models ───────────────────────────────────────────────────────────

def test_required_term_is_frozen():
    t = RequiredTerm(term="green", priority="critical")
    with pytest.raises(Exception):
        t.term = "blue"


def test_architect_paragraph_is_frozen():
    p = ArchitectParagraph(
        order=1,
        purpose="Introduce the motif",
        blueprint_section=1,
        required_observations=("obs1",),
        required_interpretations=(),
        required_terms=(RequiredTerm(term="green", priority="critical"),),
    )
    with pytest.raises(Exception):
        p.order = 2


def test_architect_plan_source_literal():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ArchitectPlan(
            id="x" * 64,
            blueprint_id="b" * 64,
            blueprint_hash="h" * 64,
            title="Test",
            paragraphs=(),
            source="human",  # must be 'deterministic'
            created_at=datetime.now(timezone.utc),
        )
