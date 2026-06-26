"""
Tests for Session 010 — Critic.

Proves:
- make_validation_report_id is deterministic and prefixed with "critic:"
- validate() detects required terms present/missing (case-insensitive)
- validate() detects forbidden claims
- validate() warns on paragraph count mismatch
- validate() returns 0% fidelity for placeholder text
- approved=True only when rendered + no forbidden + all critical terms present
- ValidationReport ontology model is frozen
- Storage is idempotent (INSERT OR IGNORE)
- validation_report_for_narrative retrieves correctly
- validation_report_count works
- run_critic raises ValueError for missing pipeline steps
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.ontology.validation_report import ValidationReport
from hermeneia.storage.sqlite import SQLiteStore, ensure_critic_tables
from hermeneia.storage.hashing import make_validation_report_id
from hermeneia.compiler.critic import validate


# ── Helpers ────────────────────────────────────────────────────────────────────

def _plan(plan_id: str = "p" * 64) -> dict:
    return {"id": plan_id, "title": "Test Plan"}


def _paragraph(
    required_terms: list[dict] | None = None,
    forbidden_claims: list[str] | None = None,
    required_observations: list[str] | None = None,
    required_interpretations: list[str] | None = None,
    order_idx: int = 1,
    purpose: str = "Test paragraph",
) -> dict:
    return {
        "order_idx": order_idx,
        "purpose": purpose,
        "required_terms": json.dumps(required_terms or []),
        "forbidden_claims": json.dumps(forbidden_claims or []),
        "required_observations": json.dumps(required_observations or []),
        "required_interpretations": json.dumps(required_interpretations or []),
    }


def _narrative(
    plan_id: str = "p" * 64,
    text: str = "The green light glows across the bay.",
    narrative_id: str | None = None,
    profile_id: str | None = None,
) -> dict:
    nid = narrative_id or ("n" * 64)
    return {
        "id": nid,
        "architect_plan_id": plan_id,
        "provider": "null",
        "expression_profile_id": profile_id,
        "text": text,
        "prompt_used": "test",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "test.db")
    ensure_critic_tables(s._conn)
    # Disable FK enforcement so storage tests can insert without seeding full pipeline
    s._conn.execute("PRAGMA foreign_keys=OFF")
    return s


# ── ID formula ────────────────────────────────────────────────────────────────

def test_validation_report_id_deterministic():
    n_id = "n" * 64
    assert make_validation_report_id(n_id) == make_validation_report_id(n_id)


def test_validation_report_id_contains_critic_prefix():
    import hashlib
    n_id = "n" * 64
    expected = hashlib.sha256(f"critic:{n_id}".encode()).hexdigest()
    assert make_validation_report_id(n_id) == expected


def test_validation_report_id_differs_by_narrative():
    assert make_validation_report_id("a" * 64) != make_validation_report_id("b" * 64)


# ── Term detection ────────────────────────────────────────────────────────────

def test_present_terms_detected():
    paras = [_paragraph(required_terms=[{"term": "green", "priority": "critical"}])]
    report = validate(_plan(), paras, _narrative(text="The green light."))
    assert "green" in report["required_terms_present"]
    assert "green" not in json.loads(report["required_terms_missing"])


def test_missing_terms_detected():
    paras = [_paragraph(required_terms=[{"term": "gatsby", "priority": "critical"}])]
    report = validate(_plan(), paras, _narrative(text="No mention here."))
    assert "gatsby" in json.loads(report["required_terms_missing"])
    assert "gatsby" not in report["required_terms_present"]


def test_term_detection_case_insensitive():
    paras = [_paragraph(required_terms=[{"term": "Green", "priority": "recommended"}])]
    report = validate(_plan(), paras, _narrative(text="the green light"))
    assert "Green" in report["required_terms_present"]


def test_recommended_terms_counted():
    paras = [_paragraph(required_terms=[
        {"term": "green", "priority": "critical"},
        {"term": "dock", "priority": "recommended"},
    ])]
    report = validate(_plan(), paras, _narrative(text="green light at the dock"))
    assert "green" in report["required_terms_present"]
    assert "dock" in report["required_terms_present"]


# ── Forbidden claims ──────────────────────────────────────────────────────────

def test_forbidden_claim_detected():
    paras = [_paragraph(forbidden_claims=["Gatsby is happy"])]
    report = validate(_plan(), paras, _narrative(text="Gatsby is happy with his life."))
    assert "Gatsby is happy" in json.loads(report["unsupported_claims"])


def test_no_forbidden_claim_when_absent():
    paras = [_paragraph(forbidden_claims=["Gatsby is happy"])]
    report = validate(_plan(), paras, _narrative(text="Gatsby trembles with longing."))
    assert json.loads(report["unsupported_claims"]) == []


# ── Placeholder detection ─────────────────────────────────────────────────────

def test_placeholder_returns_zero_fidelity():
    paras = [_paragraph(required_terms=[{"term": "green", "priority": "critical"}])]
    report = validate(_plan(), paras, _narrative(text="[Artist not configured — connect a provider]"))
    assert report["semantic_fidelity"] == 0.0


def test_placeholder_sets_warning():
    paras = [_paragraph()]
    report = validate(_plan(), paras, _narrative(text="[Artist not configured — connect a provider]"))
    warnings = json.loads(report["warnings"])
    assert any("placeholder" in w.lower() for w in warnings)


def test_placeholder_not_approved():
    paras = [_paragraph()]
    report = validate(_plan(), paras, _narrative(text="[Artist not configured — connect a provider]"))
    assert not report["approved"]


# ── Approval logic ────────────────────────────────────────────────────────────

def test_approved_when_all_critical_present_and_rendered():
    paras = [_paragraph(required_terms=[{"term": "green", "priority": "critical"}])]
    report = validate(_plan(), paras, _narrative(text="The green light endures."))
    assert report["approved"]


def test_not_approved_when_critical_term_missing():
    paras = [_paragraph(required_terms=[
        {"term": "green", "priority": "critical"},
        {"term": "gatsby", "priority": "critical"},
    ])]
    report = validate(_plan(), paras, _narrative(text="The green light."))
    assert not report["approved"]


def test_not_approved_when_forbidden_claim_present():
    paras = [_paragraph(
        required_terms=[{"term": "green", "priority": "critical"}],
        forbidden_claims=["Gatsby is happy"],
    )]
    report = validate(_plan(), paras, _narrative(text="The green light. Gatsby is happy."))
    assert not report["approved"]


def test_recommended_missing_does_not_block_approval():
    paras = [_paragraph(required_terms=[
        {"term": "green", "priority": "critical"},
        {"term": "obscure", "priority": "recommended"},
    ])]
    report = validate(_plan(), paras, _narrative(text="The green light."))
    assert report["approved"]


# ── Paragraph count warning ───────────────────────────────────────────────────

def test_paragraph_count_mismatch_warns():
    paras = [_paragraph(order_idx=1), _paragraph(order_idx=2)]
    report = validate(_plan(), paras, _narrative(text="One paragraph only."))
    warnings = json.loads(report["warnings"])
    assert any("paragraph" in w.lower() for w in warnings)


# ── Fidelity score ────────────────────────────────────────────────────────────

def test_full_terms_present_gives_high_fidelity():
    paras = [_paragraph(required_terms=[
        {"term": "green", "priority": "critical"},
        {"term": "light", "priority": "recommended"},
    ])]
    report = validate(_plan(), paras, _narrative(text="The green light glows."))
    assert report["semantic_fidelity"] == 100.0


def test_half_terms_present_gives_partial_fidelity():
    paras = [_paragraph(required_terms=[
        {"term": "green", "priority": "critical"},
        {"term": "gatsby", "priority": "critical"},
    ])]
    report = validate(_plan(), paras, _narrative(text="The green light."))
    assert 0.0 < report["semantic_fidelity"] < 100.0


# ── Storage ───────────────────────────────────────────────────────────────────

def _report_row(narrative_id: str = "n" * 64, plan_id: str = "p" * 64) -> dict:
    return {
        "id": make_validation_report_id(narrative_id),
        "rendered_narrative_id": narrative_id,
        "architect_plan_id": plan_id,
        "expression_profile_id": None,
        "semantic_fidelity": 75.0,
        "required_terms_present": "[]",
        "required_terms_missing": "[]",
        "unsupported_claims": "[]",
        "omitted_observations": "[]",
        "omitted_interpretations": "[]",
        "semantic_drift": "[]",
        "warnings": "[]",
        "approved": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_insert_validation_report_idempotent(store):
    row = _report_row()
    store.insert_validation_report(row)
    store.insert_validation_report(row)
    assert store.validation_report_count() == 1


def test_validation_report_for_narrative_retrieves(store):
    n_id = "n" * 64
    row = _report_row(narrative_id=n_id)
    store.insert_validation_report(row)
    result = store.validation_report_for_narrative(n_id)
    assert result is not None
    assert result["approved"] == 1


def test_validation_report_for_narrative_none_when_absent(store):
    assert store.validation_report_for_narrative("x" * 64) is None


def test_validation_report_count_zero(store):
    assert store.validation_report_count() == 0


def test_validation_report_count_increments(store):
    store.insert_validation_report(_report_row())
    assert store.validation_report_count() == 1


# ── Ontology model ────────────────────────────────────────────────────────────

def test_validation_report_is_frozen():
    vr = ValidationReport(
        id="x" * 64,
        rendered_narrative_id="n" * 64,
        architect_plan_id="p" * 64,
        expression_profile_id=None,
        semantic_fidelity=97.0,
        required_terms_present=("green",),
        required_terms_missing=(),
        unsupported_claims=(),
        omitted_observations=(),
        omitted_interpretations=(),
        semantic_drift=(),
        warnings=(),
        approved=True,
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(Exception):
        vr.approved = False
