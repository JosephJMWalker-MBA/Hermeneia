"""
Perspective Registry compliance tests.

Invariants guarded:
  - ID formula: sha256(name.lower().strip()) — case-insensitive, whitespace-normalized
  - "Literary" and "literary" resolve to the same Perspective
  - Perspectives are append-only (INSERT OR IGNORE)
  - Every interpretation with a perspective_id references a real Perspective
  - Contradiction analysis is deterministic (no AI, pure set arithmetic)
  - Divergence score is 0.0 for identical evidence, 1.0 for completely disjoint
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from hermeneia.compiler.compiler import Compiler
from hermeneia.cli.comparer import _analyze
from hermeneia.storage.hashing import make_perspective_id, make_interpretation_id
from hermeneia.storage.sqlite import SQLiteStore

GATSBY_PDF = Path(__file__).parent.parent / "examples" / "gatsby.pdf"
needs_pdf = pytest.mark.skipif(
    not GATSBY_PDF.exists(), reason="gatsby.pdf not found in examples/"
)


# ── ID formula ────────────────────────────────────────────────────────────────

def test_perspective_id_is_sha256_of_lowered_name():
    expected = hashlib.sha256("literary".encode("utf-8")).hexdigest()
    assert make_perspective_id("Literary") == expected
    assert make_perspective_id("literary") == expected
    assert make_perspective_id("LITERARY") == expected


def test_perspective_id_is_case_insensitive():
    assert make_perspective_id("Literary") == make_perspective_id("literary")
    assert make_perspective_id("Psychoanalytic") == make_perspective_id("PSYCHOANALYTIC")


def test_perspective_id_strips_whitespace():
    assert make_perspective_id("Literary") == make_perspective_id("  Literary  ")


def test_different_perspectives_have_different_ids():
    assert make_perspective_id("Literary") != make_perspective_id("Historical")
    assert make_perspective_id("Psychoanalytic") != make_perspective_id("Marxist")


# ── Registry: append-only, idempotent ────────────────────────────────────────

@needs_pdf
def test_perspective_registration_is_idempotent(tmp_path):
    """Registering the same perspective twice must not create a duplicate."""
    c = Compiler(db_path=tmp_path / "test.db", build_dir=tmp_path / "build")
    c.compile(GATSBY_PDF)
    c.close()

    store = SQLiteStore(tmp_path / "test.db")
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": make_perspective_id("Literary"),
        "name": "Literary",
        "description": "Attends to narrative craft, symbol, and form.",
        "created_at": now,
    }
    store.register_perspective(row)
    store.register_perspective(row)  # second call: no-op

    all_p = store.all_perspectives()
    literary = [p for p in all_p if p["name"] == "Literary"]
    assert len(literary) == 1
    store.close()


@needs_pdf
def test_perspective_name_is_case_normalized_in_registry(tmp_path):
    """'Literary' and 'literary' must not coexist as separate perspectives."""
    c = Compiler(db_path=tmp_path / "test.db", build_dir=tmp_path / "build")
    c.compile(GATSBY_PDF)
    c.close()

    store = SQLiteStore(tmp_path / "test.db")
    now = datetime.now(timezone.utc).isoformat()

    store.register_perspective({
        "id": make_perspective_id("Literary"),
        "name": "Literary",
        "description": "",
        "created_at": now,
    })
    # Same ID (sha256 of "literary") — INSERT OR IGNORE silently skips
    store.register_perspective({
        "id": make_perspective_id("literary"),  # same as "Literary"
        "name": "literary",
        "description": "",
        "created_at": now,
    })

    count = store.perspective_count()
    assert count == 1, f"Expected 1 perspective, found {count}"
    store.close()


@needs_pdf
def test_interpretation_perspective_id_references_registered_perspective(tmp_path):
    """Every interpretation.perspective_id must reference a perspective in the registry."""
    c = Compiler(db_path=tmp_path / "test.db", build_dir=tmp_path / "build")
    c.compile(GATSBY_PDF)
    c.close()

    store = SQLiteStore(tmp_path / "test.db")
    obs = store.all_observations()[0]
    now = datetime.now(timezone.utc).isoformat()

    persp_id = make_perspective_id("Literary")
    store.register_perspective({
        "id": persp_id, "name": "Literary", "description": "", "created_at": now
    })
    store.insert_interpretation({
        "id": make_interpretation_id(obs["id"], "Literary", "A reading."),
        "observation_id": obs["id"],
        "perspective": "Literary",
        "perspective_id": persp_id,
        "text": "A reading.",
        "evidential_status": "speculative",
        "evidence_observation_ids": json.dumps([obs["id"]]),
        "confidence": "human",
        "source": "steward-authored",
        "created_at": now,
    })

    # Verify FK integrity via query
    orphaned = store._conn.execute(
        """
        SELECT i.id FROM interpretations i
        LEFT JOIN perspectives p ON p.id = i.perspective_id
        WHERE i.perspective_id IS NOT NULL AND p.id IS NULL
        """
    ).fetchall()
    assert not orphaned, f"{len(orphaned)} interpretations reference non-existent perspectives"
    store.close()


# ── Pydantic model ────────────────────────────────────────────────────────────

def test_perspective_model_is_frozen():
    from hermeneia.ontology.perspective import Perspective
    p = Perspective(
        id=make_perspective_id("Literary"),
        name="Literary",
        description="Attends to narrative form.",
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(Exception):
        p.name = "Mutated"  # type: ignore[misc]


def test_perspective_model_fields_present():
    from hermeneia.ontology.perspective import Perspective
    p = Perspective(
        id=make_perspective_id("Historical"),
        name="Historical",
        description="",
        created_at=datetime.now(timezone.utc),
    )
    assert p.id == make_perspective_id("Historical")
    assert p.name == "Historical"
    assert p.description == ""


# ── Contradiction analysis (pure unit tests, no DB needed) ───────────────────

def _make_interp(perspective: str, status: str, evidence: list[str]) -> dict:
    return {
        "perspective": perspective,
        "evidential_status": status,
        "evidence_observation_ids": json.dumps(evidence),
    }


def test_analysis_identical_evidence_has_zero_divergence():
    interps = [
        _make_interp("Literary", "speculative", ["obs-a", "obs-b"]),
        _make_interp("Historical", "speculative", ["obs-a", "obs-b"]),
    ]
    result = _analyze(interps, {})
    assert result["divergence_score"] == 0.0
    assert result["shared_evidence"] == {"obs-a", "obs-b"}
    assert not result["status_conflict"]


def test_analysis_disjoint_evidence_has_full_divergence():
    interps = [
        _make_interp("Literary", "speculative", ["obs-a"]),
        _make_interp("Historical", "speculative", ["obs-b"]),
    ]
    result = _analyze(interps, {})
    assert result["divergence_score"] == 1.0
    assert result["shared_evidence"] == set()


def test_analysis_partial_overlap():
    interps = [
        _make_interp("A", "speculative", ["obs-a", "obs-b"]),
        _make_interp("B", "speculative", ["obs-b", "obs-c"]),
    ]
    result = _analyze(interps, {})
    assert result["shared_evidence"] == {"obs-b"}
    assert result["exclusive"][0] == {"obs-a"}
    assert result["exclusive"][1] == {"obs-c"}
    # union = {a,b,c}, shared = {b} → score = 1 - 1/3 = 0.667
    assert abs(result["divergence_score"] - 2 / 3) < 1e-9


def test_analysis_status_conflict_detected():
    interps = [
        _make_interp("Literary", "established", ["obs-a"]),
        _make_interp("Historical", "speculative", ["obs-a"]),
    ]
    result = _analyze(interps, {})
    assert result["status_conflict"] is True
    assert result["unique_statuses"] == {"established", "speculative"}


def test_analysis_no_status_conflict_when_all_agree():
    interps = [
        _make_interp("Literary", "contested", ["obs-a"]),
        _make_interp("Historical", "contested", ["obs-b"]),
        _make_interp("Marxist", "contested", ["obs-c"]),
    ]
    result = _analyze(interps, {})
    assert result["status_conflict"] is False
    assert result["unique_statuses"] == {"contested"}


def test_analysis_three_way_exclusive():
    interps = [
        _make_interp("A", "speculative", ["obs-1"]),
        _make_interp("B", "speculative", ["obs-2"]),
        _make_interp("C", "speculative", ["obs-3"]),
    ]
    result = _analyze(interps, {})
    assert result["exclusive"][0] == {"obs-1"}
    assert result["exclusive"][1] == {"obs-2"}
    assert result["exclusive"][2] == {"obs-3"}
    assert result["shared_evidence"] == set()
    assert result["divergence_score"] == 1.0


def test_analysis_single_interpretation_is_trivial():
    """A single interpretation has no divergence and no conflict with itself."""
    interps = [_make_interp("Literary", "speculative", ["obs-a", "obs-b"])]
    result = _analyze(interps, {})
    assert result["divergence_score"] == 0.0
    assert result["shared_evidence"] == {"obs-a", "obs-b"}
    assert not result["status_conflict"]


def test_analysis_is_deterministic():
    """Same input → same output, always. No random, no AI."""
    interps = [
        _make_interp("Literary", "speculative", ["obs-x", "obs-y"]),
        _make_interp("Historical", "established", ["obs-y", "obs-z"]),
    ]
    r1 = _analyze(interps, {})
    r2 = _analyze(interps, {})
    assert r1["shared_evidence"] == r2["shared_evidence"]
    assert r1["divergence_score"] == r2["divergence_score"]
    assert r1["status_conflict"] == r2["status_conflict"]
