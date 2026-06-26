"""
Narrative Blueprint compliance tests.

Invariants guarded:
  - ID is content-addressable: sha256({sections, thesis, title})
  - Identical blueprints produce the same ID (idempotency)
  - Sections preserve order: section 1 must remain section 1
  - Link tables are populated atomically with the blueprint
  - Observation links enable bidirectional lookup (obs → blueprints)
  - Interpretation links enable bidirectional lookup (interp → blueprints)
  - Source is always 'steward-authored' (ADR-0010)
  - Blueprint is append-only (INSERT OR IGNORE)
  - NarrativeBlueprint Pydantic model is frozen (ADR-0001)
  - BlueprintSection is immutable (ADR-0001)
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
from hermeneia.storage.hashing import (
    make_blueprint_id,
    make_interpretation_id,
    make_perspective_id,
)
from hermeneia.storage.sqlite import SQLiteStore

GATSBY_PDF = Path(__file__).parent.parent / "examples" / "gatsby.pdf"
needs_pdf = pytest.mark.skipif(
    not GATSBY_PDF.exists(), reason="gatsby.pdf not found in examples/"
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def store_with_data(tmp_path_factory):
    """Compile gatsby.pdf; seed two interpretations; yield store + data."""
    root = tmp_path_factory.mktemp("blueprint_compliance")
    c = Compiler(db_path=root / "test.db", build_dir=root / "build")
    c.compile(GATSBY_PDF)
    c.close()

    store = SQLiteStore(root / "test.db")
    obs = store.all_observations()
    obs1, obs2, obs3 = obs[311], obs[310], obs[312]  # OBS-312, 311, 313

    now = datetime.now(timezone.utc).isoformat()
    persp_id = make_perspective_id("Literary")
    store.register_perspective({
        "id": persp_id, "name": "Literary", "description": "", "created_at": now
    })

    interp_id = make_interpretation_id(obs1["id"], "Literary", "The green light as symbol.")
    store.insert_interpretation({
        "id": interp_id,
        "observation_id": obs1["id"],
        "perspective": "Literary",
        "perspective_id": persp_id,
        "text": "The green light as symbol.",
        "evidential_status": "speculative",
        "evidence_observation_ids": json.dumps([obs1["id"]]),
        "confidence": "human",
        "source": "steward-authored",
        "created_at": now,
    })

    yield store, obs1, obs2, obs3, interp_id
    store.close()


def _make_sections(obs1_id: str, obs2_id: str, interp_id: str) -> list[dict]:
    return [
        {
            "claim": "The green light is introduced as a personal symbol.",
            "supporting_observations": [obs1_id, obs2_id],
            "supporting_interpretations": [interp_id],
        },
        {
            "claim": "The symbol expands to encompass cultural myth.",
            "supporting_observations": [obs1_id],
            "supporting_interpretations": [],
        },
    ]


# ── ID formula ────────────────────────────────────────────────────────────────

def test_blueprint_id_is_sha256_of_canonical_payload():
    sections = [{"claim": "A claim.", "supporting_observations": [], "supporting_interpretations": []}]
    payload = json.dumps(
        {"sections": sections, "thesis": "A thesis.", "title": "A title."},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert make_blueprint_id("A title.", "A thesis.", sections) == expected


def test_blueprint_id_is_deterministic():
    sections = [{"claim": "C.", "supporting_observations": ["x"], "supporting_interpretations": []}]
    id1 = make_blueprint_id("T", "Th.", sections)
    id2 = make_blueprint_id("T", "Th.", sections)
    assert id1 == id2


def test_blueprint_id_differs_by_title():
    sections: list[dict] = []
    assert make_blueprint_id("Title A", "Thesis.", sections) != make_blueprint_id("Title B", "Thesis.", sections)


def test_blueprint_id_differs_by_thesis():
    sections: list[dict] = []
    assert make_blueprint_id("T", "Thesis A.", sections) != make_blueprint_id("T", "Thesis B.", sections)


def test_blueprint_id_differs_by_section_content():
    s1 = [{"claim": "First.", "supporting_observations": [], "supporting_interpretations": []}]
    s2 = [{"claim": "Second.", "supporting_observations": [], "supporting_interpretations": []}]
    assert make_blueprint_id("T", "Th.", s1) != make_blueprint_id("T", "Th.", s2)


def test_blueprint_id_differs_by_section_order():
    """Section order matters — section 1 first is a different blueprint from section 2 first."""
    sa = {"claim": "A.", "supporting_observations": [], "supporting_interpretations": []}
    sb = {"claim": "B.", "supporting_observations": [], "supporting_interpretations": []}
    id_ab = make_blueprint_id("T", "Th.", [sa, sb])
    id_ba = make_blueprint_id("T", "Th.", [sb, sa])
    assert id_ab != id_ba


# ── storage: insert + link tables ────────────────────────────────────────────

@needs_pdf
def test_blueprint_insert_populates_observation_links(store_with_data):
    store, obs1, obs2, obs3, interp_id = store_with_data
    sections = _make_sections(obs1["id"], obs2["id"], interp_id)
    bp_id = make_blueprint_id("Test Blueprint A", "Thesis A.", sections)
    now = datetime.now(timezone.utc).isoformat()

    store.insert_blueprint(
        {"id": bp_id, "title": "Test Blueprint A", "thesis": "Thesis A.",
         "sections": json.dumps(sections), "source": "steward-authored", "created_at": now},
        obs_ids=[obs1["id"], obs2["id"]],
        interp_ids=[interp_id],
    )

    # obs1 should be linked
    bps = store.blueprints_for_observation(obs1["id"])
    assert any(b["id"] == bp_id for b in bps)

    # obs2 should also be linked
    bps2 = store.blueprints_for_observation(obs2["id"])
    assert any(b["id"] == bp_id for b in bps2)

    # obs3 should NOT be linked
    bps3 = store.blueprints_for_observation(obs3["id"])
    assert not any(b["id"] == bp_id for b in bps3)


@needs_pdf
def test_blueprint_insert_populates_interpretation_links(store_with_data):
    store, obs1, obs2, obs3, interp_id = store_with_data
    sections = _make_sections(obs1["id"], obs2["id"], interp_id)
    bp_id = make_blueprint_id("Test Blueprint B", "Thesis B.", sections)
    now = datetime.now(timezone.utc).isoformat()

    store.insert_blueprint(
        {"id": bp_id, "title": "Test Blueprint B", "thesis": "Thesis B.",
         "sections": json.dumps(sections), "source": "steward-authored", "created_at": now},
        obs_ids=[obs1["id"], obs2["id"]],
        interp_ids=[interp_id],
    )

    linked = store._conn.execute(
        "SELECT interpretation_id FROM blueprint_interpretation_links WHERE blueprint_id = ?",
        (bp_id,),
    ).fetchall()
    assert any(r[0] == interp_id for r in linked)


@needs_pdf
def test_blueprint_insert_is_idempotent(store_with_data):
    """INSERT OR IGNORE: inserting the same blueprint twice creates only one row."""
    store, obs1, obs2, obs3, interp_id = store_with_data
    sections = _make_sections(obs1["id"], obs2["id"], interp_id)
    bp_id = make_blueprint_id("Idempotent Blueprint", "Thesis.", sections)
    now = datetime.now(timezone.utc).isoformat()
    row = {"id": bp_id, "title": "Idempotent Blueprint", "thesis": "Thesis.",
           "sections": json.dumps(sections), "source": "steward-authored", "created_at": now}

    store.insert_blueprint(row, obs_ids=[obs1["id"]], interp_ids=[])
    store.insert_blueprint(row, obs_ids=[obs1["id"]], interp_ids=[])  # no-op

    count = store._conn.execute(
        "SELECT COUNT(*) FROM narrative_blueprints WHERE id = ?", (bp_id,)
    ).fetchone()[0]
    assert count == 1


@needs_pdf
def test_blueprint_source_is_steward_authored(store_with_data):
    """All blueprints must carry source = 'steward-authored' (ADR-0010)."""
    store, _, _, _, _ = store_with_data
    bad = store._conn.execute(
        "SELECT id FROM narrative_blueprints WHERE source != 'steward-authored'"
    ).fetchall()
    assert not bad, f"{len(bad)} blueprints with source != 'steward-authored'"


# ── section ordering ──────────────────────────────────────────────────────────

@needs_pdf
def test_blueprint_sections_preserve_insertion_order(store_with_data):
    """Sections must remain in insertion order when deserialized from the DB."""
    store, obs1, obs2, obs3, interp_id = store_with_data
    sections = [
        {"claim": "First section.", "supporting_observations": [obs1["id"]], "supporting_interpretations": []},
        {"claim": "Second section.", "supporting_observations": [obs2["id"]], "supporting_interpretations": []},
        {"claim": "Third section.", "supporting_observations": [obs3["id"]], "supporting_interpretations": []},
    ]
    bp_id = make_blueprint_id("Ordering Test", "Order matters.", sections)
    now = datetime.now(timezone.utc).isoformat()

    store.insert_blueprint(
        {"id": bp_id, "title": "Ordering Test", "thesis": "Order matters.",
         "sections": json.dumps(sections), "source": "steward-authored", "created_at": now},
        obs_ids=[obs1["id"], obs2["id"], obs3["id"]],
        interp_ids=[],
    )

    row = store._conn.execute(
        "SELECT sections FROM narrative_blueprints WHERE id = ?", (bp_id,)
    ).fetchone()
    recovered = json.loads(row[0])

    assert recovered[0]["claim"] == "First section."
    assert recovered[1]["claim"] == "Second section."
    assert recovered[2]["claim"] == "Third section."


# ── Pydantic model ────────────────────────────────────────────────────────────

def test_blueprint_section_model_is_frozen():
    from hermeneia.ontology.narrative_blueprint import BlueprintSection
    s = BlueprintSection(
        claim="A claim.",
        supporting_observations=("obs-1",),
        supporting_interpretations=(),
    )
    with pytest.raises(Exception):
        s.claim = "Mutated"  # type: ignore[misc]


def test_narrative_blueprint_model_is_frozen():
    from hermeneia.ontology.narrative_blueprint import NarrativeBlueprint, BlueprintSection
    s = BlueprintSection(
        claim="A claim.", supporting_observations=(), supporting_interpretations=()
    )
    bp = NarrativeBlueprint(
        id=make_blueprint_id("T", "Th.", []),
        title="T",
        thesis="Th.",
        sections=(s,),
        source="steward-authored",
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(Exception):
        bp.title = "Mutated"  # type: ignore[misc]


def test_narrative_blueprint_source_rejects_non_steward():
    from hermeneia.ontology.narrative_blueprint import NarrativeBlueprint
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        NarrativeBlueprint(
            id="abc",
            title="T",
            thesis="Th.",
            sections=(),
            source="ai-generated",  # type: ignore[arg-type]
            created_at=datetime.now(timezone.utc),
        )
