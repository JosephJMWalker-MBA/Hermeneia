"""
Era II Sprint E2 — Finding Persistence tests.

Verifies:
- Full lineage traversal: Finding → RenderedNarrative → ArchitectPlan
  → Blueprint → Observations → SourceExtractions → SourceDocument
- Finding supersession is append-only (CI-014 extended to Findings)
- Supersession existence trigger now covers findings table
- Finding rows are immutable (no UPDATE / DELETE)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.compiler.evaluation_functions.structural import evaluate_structural
from hermeneia.storage.sqlite import SQLiteStore

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


@pytest.fixture
def seeded_with_findings(tmp_path):
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store, architect_terms=["evidence", "fixed"])

    findings = evaluate_structural(ids["narrative_id"], ids["plan_id"], store._conn)
    store.insert_findings_batch(findings)
    yield store, ids, findings
    store.close()


# ── Lineage ───────────────────────────────────────────────────────────────────

def test_e2_finding_lineage_reaches_source_document(seeded_with_findings):
    """Full ancestry chain must be traversable from any Finding back to SourceDocument."""
    store, ids, findings = seeded_with_findings
    assert findings, "No findings produced — cannot test lineage"

    lineage = store.get_finding_lineage(findings[0]["id"])

    assert lineage is not None
    assert lineage["finding"]["id"] == findings[0]["id"]
    assert lineage["rendered_narrative"]["id"] == ids["narrative_id"]
    assert lineage["architect_plan"]["id"] == ids["plan_id"]
    assert lineage["blueprint"]["id"] == ids["bp_id"]
    assert any(o["id"] == ids["obs_id"] for o in lineage["observations"])
    assert any(e["id"] == ids["extraction_id"] for e in lineage["source_extractions"])
    assert any(d["id"] == ids["doc_id"] for d in lineage["source_documents"])


def test_e2_lineage_has_no_gaps(seeded_with_findings):
    """Every layer of the lineage chain must be non-null — no dangling links."""
    store, ids, findings = seeded_with_findings

    for f in findings:
        lineage = store.get_finding_lineage(f["id"])
        assert lineage["finding"] is not None
        assert lineage["rendered_narrative"] is not None
        assert lineage["architect_plan"] is not None
        assert lineage["blueprint"] is not None
        assert len(lineage["observations"]) > 0
        assert len(lineage["source_extractions"]) > 0
        assert len(lineage["source_documents"]) > 0


def test_e2_lineage_returns_none_for_missing_finding(tmp_path):
    store = SQLiteStore(tmp_path / "test.db")
    assert store.get_finding_lineage("z" * 64) is None
    store.close()


# ── Immutability ──────────────────────────────────────────────────────────────

def test_e2_finding_rows_reject_update(seeded_with_findings):
    """Finding immutability trigger must block UPDATE."""
    store, ids, findings = seeded_with_findings
    finding_id = findings[0]["id"]

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "UPDATE findings SET status = 'transformed' WHERE id = ?", (finding_id,)
        )


def test_e2_finding_rows_reject_delete(seeded_with_findings):
    """Finding immutability trigger must block DELETE."""
    store, ids, findings = seeded_with_findings
    finding_id = findings[0]["id"]

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "DELETE FROM findings WHERE id = ?", (finding_id,)
        )


# ── Supersession ──────────────────────────────────────────────────────────────

def test_e2_finding_can_be_superseded_by_another_finding(seeded_with_findings):
    """A Finding may be superseded by a later Finding; both remain accessible."""
    store, ids, findings = seeded_with_findings
    now = datetime.now(timezone.utc).isoformat()

    old_id = findings[0]["id"]

    # Produce a second finding set (same inputs — INSERT OR IGNORE makes it the same set,
    # so we simulate a "new evaluation method" by directly inserting a variant)
    new_finding = dict(findings[0])
    new_finding["id"] = "a" * 64   # synthetic new finding ID (normally from a new EF run)
    new_finding["evaluation_method"] = "structural-v2.0"
    store._conn.execute(
        """
        INSERT OR IGNORE INTO findings
            (id, rendered_narrative_id, architect_plan_id, dimension,
             obligation_id, operation, status, evidence,
             evaluation_method, constitution_version, created_at)
        VALUES
            (:id, :rendered_narrative_id, :architect_plan_id, :dimension,
             :obligation_id, :operation, :status, :evidence,
             :evaluation_method, :constitution_version, :created_at)
        """,
        new_finding,
    )
    store._conn.commit()

    store.insert_supersession_relation({
        "old_id": old_id,
        "new_id": "a" * 64,
        "reason": "structural-v2.0 replaces v1.0 for this narrative",
        "ratified_at": now,
    })

    # Both Findings remain accessible — supersession is append-only
    old = store._conn.execute("SELECT * FROM findings WHERE id = ?", (old_id,)).fetchone()
    new = store._conn.execute("SELECT * FROM findings WHERE id = ?", ("a" * 64,)).fetchone()
    assert old is not None, "Old Finding must remain after supersession"
    assert new is not None, "New Finding must exist"

    chain = store.supersessions_from(old_id)
    assert len(chain) == 1
    assert chain[0]["new_id"] == "a" * 64


def test_e2_supersession_of_finding_requires_both_to_exist(seeded_with_findings):
    """Supersession trigger must reject phantom old or new IDs — even for findings."""
    store, ids, findings = seeded_with_findings
    now = datetime.now(timezone.utc).isoformat()
    real_id = findings[0]["id"]
    phantom = "z" * 64

    # Phantom old — finding that doesn't exist
    with pytest.raises(sqlite3.IntegrityError, match="Supersession old object missing"):
        store._conn.execute(
            "INSERT INTO supersession_relations (old_id, new_id, reason, ratified_at) "
            "VALUES (?, ?, ?, ?)",
            (phantom, real_id, "test", now),
        )

    # Phantom new — finding that doesn't exist
    with pytest.raises(sqlite3.IntegrityError, match="Supersession new object missing"):
        store._conn.execute(
            "INSERT INTO supersession_relations (old_id, new_id, reason, ratified_at) "
            "VALUES (?, ?, ?, ?)",
            (real_id, phantom, "test", now),
        )


def test_e2_supersession_relation_is_append_only(seeded_with_findings):
    """Once recorded, a supersession relation must not be updatable or deletable."""
    store, ids, findings = seeded_with_findings
    now = datetime.now(timezone.utc).isoformat()
    old_id = findings[0]["id"]

    # Need a second valid finding to supersede with
    new_finding = dict(findings[0])
    new_finding["id"] = "b" * 64
    new_finding["evaluation_method"] = "structural-v2.0"
    store._conn.execute(
        """
        INSERT OR IGNORE INTO findings
            (id, rendered_narrative_id, architect_plan_id, dimension,
             obligation_id, operation, status, evidence,
             evaluation_method, constitution_version, created_at)
        VALUES
            (:id, :rendered_narrative_id, :architect_plan_id, :dimension,
             :obligation_id, :operation, :status, :evidence,
             :evaluation_method, :constitution_version, :created_at)
        """,
        new_finding,
    )
    store._conn.commit()

    store.insert_supersession_relation({
        "old_id": old_id,
        "new_id": "b" * 64,
        "reason": "append-only test",
        "ratified_at": now,
    })

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "UPDATE supersession_relations SET reason = 'tampered' WHERE old_id = ?",
            (old_id,),
        )

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "DELETE FROM supersession_relations WHERE old_id = ?", (old_id,)
        )
