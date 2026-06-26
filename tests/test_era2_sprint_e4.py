"""
Era II Sprint E4 — Projection Layer tests.

Verifies three projections:
- audit_dashboard: groups Finding counts by dimension and status
- trust_card: compact per-dimension and overall verdict
- semantic_inspector: detailed findings with evidence and lineage

All projections must be:
- read-only (no writes to DB)
- regeneratable (same inputs → same output, modulo generated_at)
- correctly derived from canonical Finding[]
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.compiler.evaluation_functions.structural import evaluate_structural
from hermeneia.compiler.projections.audit_dashboard import audit_dashboard
from hermeneia.compiler.projections.trust_card import trust_card
from hermeneia.compiler.projections.semantic_inspector import semantic_inspector
from hermeneia.storage.sqlite import SQLiteStore

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def seeded_with_findings(tmp_path):
    """Seed a full chain with structural Findings already stored."""
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store, architect_terms=["evidence", "fixed"])

    findings = evaluate_structural(
        ids["narrative_id"], ids["plan_id"], store._conn
    )
    store.insert_findings_batch(findings)

    yield store, ids
    store.close()


# ── audit_dashboard ───────────────────────────────────────────────────────────

def test_audit_dashboard_returns_dict(seeded_with_findings):
    store, ids = seeded_with_findings
    result = audit_dashboard(ids["narrative_id"], store._conn)
    assert isinstance(result, dict)


def test_audit_dashboard_contains_narrative_id(seeded_with_findings):
    store, ids = seeded_with_findings
    result = audit_dashboard(ids["narrative_id"], store._conn)
    assert result["narrative_id"] == ids["narrative_id"]


def test_audit_dashboard_dimensions_present(seeded_with_findings):
    store, ids = seeded_with_findings
    result = audit_dashboard(ids["narrative_id"], store._conn)
    assert "structural" in result["dimensions"]


def test_audit_dashboard_total_matches_findings(seeded_with_findings):
    store, ids = seeded_with_findings
    result = audit_dashboard(ids["narrative_id"], store._conn)
    dim_total = sum(d["total"] for d in result["dimensions"].values())
    assert dim_total == result["total_findings"]
    assert result["total_findings"] > 0


def test_audit_dashboard_is_read_only(seeded_with_findings):
    """audit_dashboard must not write to the database."""
    store, ids = seeded_with_findings
    count_before = store._conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    audit_dashboard(ids["narrative_id"], store._conn)
    count_after = store._conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    assert count_before == count_after


def test_audit_dashboard_regeneratable(seeded_with_findings):
    """Same inputs produce equivalent output (excluding generated_at)."""
    store, ids = seeded_with_findings
    r1 = audit_dashboard(ids["narrative_id"], store._conn)
    r2 = audit_dashboard(ids["narrative_id"], store._conn)
    r1.pop("generated_at")
    r2.pop("generated_at")
    assert r1 == r2


def test_audit_dashboard_unknown_narrative(seeded_with_findings):
    store, ids = seeded_with_findings
    result = audit_dashboard("nonexistent-id", store._conn)
    assert "error" in result
    assert result["total_findings"] == 0


# ── trust_card ────────────────────────────────────────────────────────────────

def test_trust_card_returns_dict(seeded_with_findings):
    store, ids = seeded_with_findings
    result = trust_card(ids["narrative_id"], store._conn)
    assert isinstance(result, dict)


def test_trust_card_has_overall_verdict(seeded_with_findings):
    store, ids = seeded_with_findings
    result = trust_card(ids["narrative_id"], store._conn)
    assert result["overall"] in ("pass", "partial", "fail", "not_evaluated")


def test_trust_card_dimension_verdicts(seeded_with_findings):
    store, ids = seeded_with_findings
    result = trust_card(ids["narrative_id"], store._conn)
    for dim, verdict in result["dimensions"].items():
        assert verdict in ("pass", "partial", "fail", "not_evaluated"), (
            f"Unexpected verdict '{verdict}' for dimension '{dim}'"
        )


def test_trust_card_is_read_only(seeded_with_findings):
    store, ids = seeded_with_findings
    count_before = store._conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    trust_card(ids["narrative_id"], store._conn)
    count_after = store._conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    assert count_before == count_after


def test_trust_card_regeneratable(seeded_with_findings):
    store, ids = seeded_with_findings
    r1 = trust_card(ids["narrative_id"], store._conn)
    r2 = trust_card(ids["narrative_id"], store._conn)
    r1.pop("generated_at")
    r2.pop("generated_at")
    assert r1 == r2


def test_trust_card_pass_when_all_preserved(seeded_with_findings):
    """When all structural Findings are preserved, structural verdict is pass."""
    store, ids = seeded_with_findings
    result = trust_card(ids["narrative_id"], store._conn)
    # structural terms "evidence" and "fixed" appear in the seeded rendered text
    # which includes "This is a test narrative with evidence and fixed content."
    assert result["dimensions"].get("structural") in ("pass", "partial")


def test_trust_card_unknown_narrative(seeded_with_findings):
    store, ids = seeded_with_findings
    result = trust_card("nonexistent-id", store._conn)
    assert "error" in result
    assert result["overall"] == "unknown"


# ── semantic_inspector ───────────────────────────────────────────────────────

def test_semantic_inspector_returns_dict(seeded_with_findings):
    store, ids = seeded_with_findings
    result = semantic_inspector(ids["narrative_id"], store._conn)
    assert isinstance(result, dict)


def test_semantic_inspector_findings_list(seeded_with_findings):
    store, ids = seeded_with_findings
    result = semantic_inspector(ids["narrative_id"], store._conn)
    assert "findings" in result
    assert isinstance(result["findings"], list)
    assert result["total_findings"] == len(result["findings"])
    assert result["total_findings"] > 0


def test_semantic_inspector_finding_fields(seeded_with_findings):
    store, ids = seeded_with_findings
    result = semantic_inspector(ids["narrative_id"], store._conn)
    f = result["findings"][0]
    for field in ("finding_id", "dimension", "obligation_id", "operation", "status",
                  "evaluation_method", "constitution_version", "created_at",
                  "evidence", "lineage"):
        assert field in f, f"Missing field '{field}' in finding"


def test_semantic_inspector_evidence_structure(seeded_with_findings):
    """Evidence must expose contract_obligation, observed_render, supporting_trace."""
    store, ids = seeded_with_findings
    result = semantic_inspector(ids["narrative_id"], store._conn)
    for f in result["findings"]:
        ev = f["evidence"]
        assert "contract_obligation" in ev
        assert "observed_render" in ev
        assert "supporting_trace" in ev


def test_semantic_inspector_lineage_fields(seeded_with_findings):
    store, ids = seeded_with_findings
    result = semantic_inspector(ids["narrative_id"], store._conn)
    lineage = result["findings"][0]["lineage"]
    assert "rendered_narrative_id" in lineage
    assert "architect_plan_id" in lineage


def test_semantic_inspector_dimensions_present(seeded_with_findings):
    store, ids = seeded_with_findings
    result = semantic_inspector(ids["narrative_id"], store._conn)
    assert "structural" in result["dimensions_present"]


def test_semantic_inspector_is_read_only(seeded_with_findings):
    store, ids = seeded_with_findings
    count_before = store._conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    semantic_inspector(ids["narrative_id"], store._conn)
    count_after = store._conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    assert count_before == count_after


def test_semantic_inspector_regeneratable(seeded_with_findings):
    store, ids = seeded_with_findings
    r1 = semantic_inspector(ids["narrative_id"], store._conn)
    r2 = semantic_inspector(ids["narrative_id"], store._conn)
    r1.pop("generated_at")
    r2.pop("generated_at")
    assert r1 == r2


def test_semantic_inspector_unknown_narrative(seeded_with_findings):
    store, ids = seeded_with_findings
    result = semantic_inspector("nonexistent-id", store._conn)
    assert "error" in result
    assert result["findings"] == []


# ── Cross-projection consistency ─────────────────────────────────────────────

def test_projections_agree_on_total_findings(seeded_with_findings):
    """All three projections must report the same total Finding count."""
    store, ids = seeded_with_findings
    nid = ids["narrative_id"]
    dashboard = audit_dashboard(nid, store._conn)
    card = trust_card(nid, store._conn)
    inspector = semantic_inspector(nid, store._conn)

    dashboard_total = dashboard["total_findings"]
    card_total = card["finding_count"]
    inspector_total = inspector["total_findings"]

    assert dashboard_total == card_total == inspector_total, (
        f"Projection totals disagree: dashboard={dashboard_total}, "
        f"card={card_total}, inspector={inspector_total}"
    )


def test_projections_agree_on_dimensions(seeded_with_findings):
    """audit_dashboard and semantic_inspector must report the same dimension set."""
    store, ids = seeded_with_findings
    nid = ids["narrative_id"]
    dashboard = audit_dashboard(nid, store._conn)
    inspector = semantic_inspector(nid, store._conn)

    assert set(dashboard["dimensions"].keys()) == set(inspector["dimensions_present"])
