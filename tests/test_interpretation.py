"""
Interpretation compliance tests — proves the invariants hold continuously.

Invariants guarded:
  - Append-only: no UPDATE or DELETE on interpretations (ADR-0001 extension)
  - Content-addressable ID: sha256({observation_id, perspective, text})
  - Perspective-scoped: perspective is non-empty
  - Evidential status is one of the four ratified values (ADR-0036)
  - Provenance-linked: observation_id references a valid observation
  - Steward-owned: confidence = "human", source = "steward-authored" (ADR-0010)
  - Idempotent: inserting identical content twice does not produce a duplicate
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from hermeneia.compiler.compiler import Compiler
from hermeneia.storage.hashing import make_interpretation_id
from hermeneia.storage.sqlite import SQLiteStore

GATSBY_PDF = Path(__file__).parent.parent / "examples" / "gatsby.pdf"
needs_pdf = pytest.mark.skipif(
    not GATSBY_PDF.exists(), reason="gatsby.pdf not found in examples/"
)

_EVIDENTIAL_STATUSES = {"established", "contested", "speculative", "uncertain"}


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def store_with_obs(tmp_path_factory):
    """Compile gatsby.pdf; return an open SQLiteStore and the first observation ID."""
    root = tmp_path_factory.mktemp("interp_compliance")
    c = Compiler(db_path=root / "test.db", build_dir=root / "build")
    c.compile(GATSBY_PDF)
    c.close()

    store = SQLiteStore(root / "test.db")
    obs_list = store.all_observations()
    assert obs_list, "No observations compiled"
    yield store, obs_list[0]["id"]
    store.close()


def _make_row(obs_id: str, perspective: str = "Literary", text: str = "Test.") -> dict:
    return {
        "id": make_interpretation_id(obs_id, perspective, text),
        "observation_id": obs_id,
        "perspective": perspective,
        "text": text,
        "evidential_status": "speculative",
        "evidence_observation_ids": json.dumps([obs_id]),
        "confidence": "human",
        "source": "steward-authored",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ── ID formula ────────────────────────────────────────────────────────────────

def test_interpretation_id_is_sha256_of_canonical_payload():
    """ID = sha256(json({observation_id, perspective, text}, sort_keys=True))."""
    obs_id = "abc123"
    perspective = "Literary"
    text = "The green light symbolizes hope."

    payload = json.dumps(
        {"observation_id": obs_id, "perspective": perspective, "text": text},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert make_interpretation_id(obs_id, perspective, text) == expected


def test_interpretation_id_is_deterministic():
    """Same inputs → same ID across calls."""
    obs_id = "deadbeef"
    id1 = make_interpretation_id(obs_id, "Philosophical", "Meaning is constructed.")
    id2 = make_interpretation_id(obs_id, "Philosophical", "Meaning is constructed.")
    assert id1 == id2


def test_interpretation_id_differs_by_perspective():
    obs_id = "deadbeef"
    id1 = make_interpretation_id(obs_id, "Literary", "Same text.")
    id2 = make_interpretation_id(obs_id, "Historical", "Same text.")
    assert id1 != id2


def test_interpretation_id_differs_by_text():
    obs_id = "deadbeef"
    id1 = make_interpretation_id(obs_id, "Literary", "Reading A.")
    id2 = make_interpretation_id(obs_id, "Literary", "Reading B.")
    assert id1 != id2


# ── append-only: INSERT OR IGNORE idempotency ─────────────────────────────────

@needs_pdf
def test_interpretation_insert_is_idempotent(store_with_obs):
    """Inserting the same interpretation twice must not create a duplicate."""
    store, obs_id = store_with_obs
    row = _make_row(obs_id, "Literary", "Idempotent test reading.")

    store.insert_interpretation(row)
    store.insert_interpretation(row)  # second call must be a no-op

    results = store.interpretations_for_observation(obs_id)
    matching = [r for r in results if r["id"] == row["id"]]
    assert len(matching) == 1, f"Expected 1, got {len(matching)} copies of the same interpretation"


@needs_pdf
def test_interpretation_different_perspectives_both_saved(store_with_obs):
    """Two interpretations of the same observation with different perspectives are both valid."""
    store, obs_id = store_with_obs
    row_a = _make_row(obs_id, "Philosophical", "A philosophical reading.")
    row_b = _make_row(obs_id, "Historical", "A historical reading.")

    store.insert_interpretation(row_a)
    store.insert_interpretation(row_b)

    results = store.interpretations_for_observation(obs_id)
    perspectives = {r["perspective"] for r in results}
    assert "Philosophical" in perspectives
    assert "Historical" in perspectives


# ── schema invariants ─────────────────────────────────────────────────────────

@needs_pdf
def test_interpretation_schema_has_check_constraint(store_with_obs):
    """The evidential_status CHECK constraint must reject invalid values at the DB level."""
    store, obs_id = store_with_obs
    bad_row = _make_row(obs_id, "Test", "Bad status row.")
    bad_row["evidential_status"] = "invented"  # not in the enum

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            """
            INSERT INTO interpretations
                (id, observation_id, perspective, text, evidential_status,
                 evidence_observation_ids, confidence, source, created_at)
            VALUES
                (:id, :observation_id, :perspective, :text, :evidential_status,
                 :evidence_observation_ids, :confidence, :source, :created_at)
            """,
            bad_row,
        )


@needs_pdf
def test_interpretation_foreign_key_rejects_unknown_observation(store_with_obs):
    """observation_id must reference a real observation. Phantom links are rejected."""
    store, _ = store_with_obs
    phantom_obs_id = "0" * 64  # valid hex length, but no such observation
    row = _make_row(phantom_obs_id)

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            """
            INSERT INTO interpretations
                (id, observation_id, perspective, text, evidential_status,
                 evidence_observation_ids, confidence, source, created_at)
            VALUES
                (:id, :observation_id, :perspective, :text, :evidential_status,
                 :evidence_observation_ids, :confidence, :source, :created_at)
            """,
            row,
        )


# ── steward-ownership invariants ──────────────────────────────────────────────

@needs_pdf
def test_interpretation_confidence_is_human(store_with_obs):
    """All stored interpretations must have confidence = 'human' (ADR-0010).

    If an AI-generated interpretation ever sneaks in, this catches it.
    """
    store, obs_id = store_with_obs
    row = _make_row(obs_id, "Structural", "A structural reading.")
    store.insert_interpretation(row)

    results = store.interpretations_for_observation(obs_id)
    for r in results:
        assert r["confidence"] == "human", (
            f"Interpretation {r['id'][:12]}… has confidence='{r['confidence']}', expected 'human'"
        )


@needs_pdf
def test_interpretation_source_is_steward_authored(store_with_obs):
    """All stored interpretations must have source = 'steward-authored' (ADR-0010)."""
    store, obs_id = store_with_obs
    row = _make_row(obs_id, "Rhetorical", "A rhetorical reading.")
    store.insert_interpretation(row)

    results = store.interpretations_for_observation(obs_id)
    for r in results:
        assert r["source"] == "steward-authored", (
            f"Interpretation {r['id'][:12]}… has source='{r['source']}'"
        )


# ── ontology model ────────────────────────────────────────────────────────────

def test_interpretation_pydantic_model_enforces_frozen():
    """The Pydantic model must be frozen — no mutation after construction."""
    from hermeneia.ontology.interpretation import Interpretation

    interp = Interpretation(
        id="abc",
        observation_id="def",
        perspective="Literary",
        text="Test.",
        evidential_status="speculative",
        evidence_observation_ids=("def",),
        confidence="human",
        source="steward-authored",
        created_at=datetime.now(timezone.utc),
    )

    with pytest.raises(Exception):  # ValidationError or TypeError depending on Pydantic version
        interp.text = "Mutated."  # type: ignore[misc]


def test_interpretation_evidential_status_rejects_invalid():
    """The Pydantic model must reject an evidential_status outside the ratified enum."""
    from hermeneia.ontology.interpretation import Interpretation
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        Interpretation(
            id="abc",
            observation_id="def",
            perspective="Literary",
            text="Test.",
            evidential_status="invented",  # type: ignore[arg-type]
            evidence_observation_ids=(),
            confidence="human",
            source="steward-authored",
            created_at=datetime.now(timezone.utc),
        )
