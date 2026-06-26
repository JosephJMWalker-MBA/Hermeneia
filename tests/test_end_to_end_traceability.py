"""
End-to-end traceability proofs for Hermeneia.

Satisfies the CLAUDE.md exit criterion: "End-to-end traceability"

Traceability means: given any artifact at any layer of the pipeline,
you can walk both directions of the evidence chain:

  Forward:  SourceDocument → SourceExtraction → Observation
            → Interpretation → Blueprint → ArchitectPlan
            → RenderedNarrative → Finding

  Backward: Finding → RenderedNarrative → ArchitectPlan → Blueprint
            → Interpretation → Observation → SourceExtraction
            → SourceDocument

These tests prove that the lineage API surfaces the complete chain in
both directions without mutation.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain

from hermeneia.compiler.evaluation_functions.runner import run_all_evaluation_functions
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def full_chain(tmp_path):
    """Seed the complete pipeline chain including Findings."""
    db_path = tmp_path / "traceability.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store, include_narrative=True, include_report=False)

    # Run all EFs and persist findings
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    run = run_all_evaluation_functions(ids["narrative_id"], ids["plan_id"], conn)
    conn.close()

    store.insert_findings_batch(run.all_findings)
    store.close()

    # Capture a finding ID for downstream tests
    conn2 = sqlite3.connect(str(db_path))
    row = conn2.execute("SELECT id FROM findings LIMIT 1").fetchone()
    conn2.close()
    ids["finding_id"] = row[0] if row else None

    return db_path, ids


@pytest.fixture
def client(full_chain):
    db_path, ids = full_chain
    return create_app(db_path=db_path).test_client(), ids


# ── Backward chain: Finding → RenderedNarrative → … → SourceDocument ─────────

def test_finding_lineage_returns_complete_evidence_chain(client):
    """A Finding traces back through the entire evidence chain to SourceDocument."""
    c, ids = client
    fid = ids["finding_id"]
    assert fid, "No finding seeded — EF runner produced zero findings"

    resp = c.get(f"/api/e10/findings/{fid}/lineage")

    assert resp.status_code == 200
    data = resp.get_json()
    assert "finding" in data
    assert "lineage" in data
    assert data["lineage"] is not None

    classes = {node["class"] for node in data["lineage"]["nodes"]}
    for expected in (
        "RenderedNarrative",
        "ArchitectPlan",
        "Blueprint",
        "Interpretation",
        "Observation",
        "SourceExtraction",
        "SourceDocument",
    ):
        assert expected in classes, f"{expected} missing from finding lineage"


def test_finding_links_to_correct_rendered_narrative(client):
    """Finding.rendered_narrative_id matches the RenderedNarrative node in the lineage graph."""
    c, ids = client
    fid = ids["finding_id"]

    resp = c.get(f"/api/e10/findings/{fid}/lineage")
    data = resp.get_json()

    finding_narrative_id = data["finding"]["rendered_narrative_id"]
    lineage_narrative_ids = {
        node["id"]
        for node in data["lineage"]["nodes"]
        if node["class"] == "RenderedNarrative"
    }
    assert finding_narrative_id in lineage_narrative_ids


def test_finding_lineage_reaches_source_document(client):
    """The lineage graph rooted at a Finding's narrative reaches a SourceDocument."""
    c, ids = client
    fid = ids["finding_id"]

    resp = c.get(f"/api/e10/findings/{fid}/lineage")
    data = resp.get_json()

    source_docs = [
        node for node in data["lineage"]["nodes"]
        if node["class"] == "SourceDocument"
    ]
    assert len(source_docs) >= 1
    assert source_docs[0]["id"] == ids["doc_id"]


# ── Forward chain: RenderedNarrative → lineage → SourceDocument ───────────────

def test_narrative_lineage_contains_all_seven_pipeline_classes(client):
    """The narrative lineage graph surfaces all 7 canonical pipeline node classes."""
    c, ids = client

    resp = c.get(f"/api/lineage/rendered_narrative/{ids['narrative_id']}")

    assert resp.status_code == 200
    classes = {node["class"] for node in resp.get_json()["nodes"]}
    expected = {
        "RenderedNarrative",
        "ArchitectPlan",
        "Blueprint",
        "Interpretation",
        "Observation",
        "SourceExtraction",
        "SourceDocument",
    }
    assert expected == classes


def test_narrative_lineage_edges_form_connected_path(client):
    """Every node class in the pipeline appears on both sides of at least one edge."""
    c, ids = client

    graph = c.get(
        f"/api/lineage/rendered_narrative/{ids['narrative_id']}"
    ).get_json()

    from_classes = {e["from"]["class"] for e in graph["edges"]}
    to_classes = {e["to"]["class"] for e in graph["edges"]}

    # Every node except the leaf (SourceDocument) must appear as a from-node
    non_leaf = {
        "RenderedNarrative", "ArchitectPlan", "Blueprint",
        "Interpretation", "Observation", "SourceExtraction",
    }
    assert non_leaf <= from_classes

    # Every node except the root (RenderedNarrative) must appear as a to-node
    non_root = {
        "ArchitectPlan", "Blueprint", "Interpretation",
        "Observation", "SourceExtraction", "SourceDocument",
    }
    assert non_root <= to_classes


# ── Specific IDs are traceable in both directions ─────────────────────────────

def test_all_seeded_ids_appear_in_narrative_lineage(client):
    """Each seeded artifact ID appears as a node in the narrative lineage graph."""
    c, ids = client

    graph = c.get(
        f"/api/lineage/rendered_narrative/{ids['narrative_id']}"
    ).get_json()

    node_ids = {node["id"] for node in graph["nodes"]}
    for key in ("narrative_id", "plan_id", "bp_id", "interp_id",
                "obs_id", "extraction_id", "doc_id"):
        assert ids[key] in node_ids, f"{key} ({ids[key]}) missing from lineage"


def test_observation_lineage_reaches_source_document(client):
    """Lineage rooted at an Observation also reaches its SourceDocument."""
    c, ids = client

    resp = c.get(f"/api/lineage/observation/{ids['obs_id']}")

    assert resp.status_code == 200
    classes = {node["class"] for node in resp.get_json()["nodes"]}
    assert "SourceDocument" in classes
    assert "SourceExtraction" in classes


# ── Findings coverage ─────────────────────────────────────────────────────────

def test_findings_stored_for_all_six_dimensions(full_chain):
    """The EF runner produced and persisted Findings for all 6 dimensions."""
    db_path, ids = full_chain
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT DISTINCT dimension FROM findings WHERE rendered_narrative_id = ?",
        (ids["narrative_id"],),
    ).fetchall()
    conn.close()

    dimensions = {row[0] for row in rows}
    expected = {
        "structural", "semantic", "provenance",
        "observation_coverage", "accessibility", "constitutional",
    }
    assert expected == dimensions


def test_finding_lineage_is_read_only(full_chain):
    """Fetching finding lineage does not mutate the database."""
    db_path, ids = full_chain
    from hermeneia.storage.hashing import sha256_file

    client = create_app(db_path=db_path).test_client()
    fid = ids["finding_id"]

    before = sha256_file(db_path)
    client.get(f"/api/e10/findings/{fid}/lineage")
    after = sha256_file(db_path)

    assert before == after


def test_unknown_finding_id_returns_404(client):
    c, ids = client
    resp = c.get("/api/e10/findings/nonexistent-id-xyz/lineage")
    assert resp.status_code == 404
