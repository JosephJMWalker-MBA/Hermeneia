"""
Era II Sprint E1 — Structural Evaluation Function tests.

Encodes all invariants from ADR-0041 (ratified with amendments 2026-06-20):
- INV-EF-1: Determinism
- INV-EF-2: Read-only boundary
- INV-EF-3 (elevated): Completeness Invariant (Amendment III)
- INV-EF-4: Orthogonality boundary (static)
- Amendment I: identity derives from canonical obligation content, not labels
- Amendment II: evidence preserves observations, not conclusions
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.compiler.architect import compile_architect_plan
from hermeneia.compiler.evaluation_functions import structural as structural_ef
from hermeneia.compiler.evaluation_functions.base import (
    RATIFIED_DIMENSIONS,
    validate_ef_contract,
)
from hermeneia.compiler.evaluation_functions.structural import evaluate_structural
from hermeneia.storage.hashing import (
    make_blueprint_id,
    make_expression_profile_id,
    make_finding_id,
    make_interpretation_id,
    make_obligation_id,
    make_rendered_narrative_id,
)
from hermeneia.storage.sqlite import SQLiteStore

# Re-use the shared chain seeder from the P0 suite
import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def seeded(tmp_path):
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store)
    yield store, ids
    store.close()


# ── INV-EF-1: Determinism ─────────────────────────────────────────────────────

def test_ef1_structural_ef_is_deterministic(seeded):
    """Running the Structural EF twice on the same inputs produces identical Finding IDs."""
    store, ids = seeded

    findings_a = evaluate_structural(
        ids["narrative_id"], ids["plan_id"], store._conn
    )
    findings_b = evaluate_structural(
        ids["narrative_id"], ids["plan_id"], store._conn
    )

    ids_a = {f["id"] for f in findings_a}
    ids_b = {f["id"] for f in findings_b}
    assert ids_a == ids_b, "Finding IDs changed between identical invocations"


def test_ef1_obligation_id_is_content_addressable():
    """Amendment I: same obligation content → same obligation_id regardless of invocation."""
    id1 = make_obligation_id("structural", "plan-abc", 1, "green light")
    id2 = make_obligation_id("structural", "plan-abc", 1, "green light")
    assert id1 == id2

    # Case normalization: "Green Light" and "green light" are the same obligation
    id_upper = make_obligation_id("structural", "plan-abc", 1, "Green Light")
    assert id_upper == id1


def test_ef1_finding_id_is_content_addressable():
    """Amendment I: same (narrative, dimension, obligation) → same finding_id."""
    ob = make_obligation_id("structural", "plan-abc", 1, "green light")
    id1 = make_finding_id("narr-xyz", "structural", ob)
    id2 = make_finding_id("narr-xyz", "structural", ob)
    assert id1 == id2

    # Different obligation → different finding
    ob2 = make_obligation_id("structural", "plan-abc", 1, "red light")
    assert make_finding_id("narr-xyz", "structural", ob2) != id1


# ── INV-EF-3 / Amendment III: Completeness ───────────────────────────────────

def test_ef3_every_obligation_produces_exactly_one_finding(seeded):
    """Completeness Invariant: |Findings| == |obligations in scope|."""
    store, ids = seeded

    # Count obligations in plan
    paragraphs = store._conn.execute(
        "SELECT required_terms FROM architect_plan_paragraphs WHERE plan_id = ?",
        (ids["plan_id"],),
    ).fetchall()
    obligations_in_scope = sum(
        len(json.loads(p["required_terms"] or "[]")) for p in paragraphs
    )

    findings = evaluate_structural(ids["narrative_id"], ids["plan_id"], store._conn)

    assert len(findings) == obligations_in_scope, (
        f"Completeness violated: {obligations_in_scope} obligations, "
        f"{len(findings)} findings"
    )


def test_ef3_preserved_and_omitted_findings_are_both_produced(tmp_path):
    """A plan with one present term and one absent term produces one preserved + one omitted."""
    store = SQLiteStore(tmp_path / "test.db")
    now = datetime.now(timezone.utc).isoformat()

    # Minimal doc/extraction/observation chain
    from test_constitutional_p0 import _seed_evidence
    ids = _seed_evidence(store)
    obs_id = ids["obs_id"]

    interp_text = "The phrase is illustrative."
    interp_id = make_interpretation_id(obs_id, "literary", interp_text)
    store.insert_interpretation({
        "id": interp_id,
        "observation_id": obs_id,
        "perspective": "literary",
        "perspective_id": None,
        "text": interp_text,
        "evidential_status": "established",
        "evidence_observation_ids": json.dumps([obs_id]),
        "confidence": 0.9,
        "source": "test",
        "created_at": now,
    })

    # Blueprint with two terms: one present in narrative, one absent
    sections = [{
        "claim": "Evidence endures.",
        "supporting_observations": [obs_id],
        "supporting_interpretations": [interp_id],
    }]
    bp_id = make_blueprint_id("Completeness Test", "Two terms.", sections)
    store.insert_blueprint(
        {"id": bp_id, "title": "Completeness Test", "thesis": "Two terms.",
         "sections": json.dumps(sections), "source": "test", "created_at": now},
        obs_ids=[obs_id], interp_ids=[interp_id],
    )

    result = compile_architect_plan(bp_id, store._conn)
    # Manually inject two required terms into the paragraph
    plan_id = result["plan_row"]["id"]
    para_rows = result["paragraph_rows"]
    para_rows[0]["required_terms"] = json.dumps([
        {"term": "Evidence", "priority": "critical"},
        {"term": "XYZZY_ABSENT_TERM", "priority": "recommended"},
    ])
    store.insert_architect_plan(result["plan_row"], para_rows)

    profile_id = make_expression_profile_id("literary-en")
    store.insert_expression_profile({
        "id": profile_id, "slug": "literary-en", "name": "Literary English",
        "description": "test", "language": "en", "audience": "general",
        "reading_level": "college", "tone": "formal", "voice": "active",
        "artist_prompt": "Write.", "critic_expectations": "[]",
        "source": "test", "created_at": now,
    })

    narrative_id = make_rendered_narrative_id(plan_id, "null", profile_id)
    store.insert_rendered_narrative({
        "id": narrative_id, "architect_plan_id": plan_id, "provider": "null",
        "expression_profile_id": profile_id,
        "text": "Evidence remains fixed.",   # contains "Evidence", not "XYZZY_ABSENT_TERM"
        "prompt_used": "test", "created_at": now,
    })

    findings = evaluate_structural(narrative_id, plan_id, store._conn)

    assert len(findings) == 2
    by_term = {json.loads(f["evidence"])["contract_obligation"]: f for f in findings}
    assert by_term["Evidence"]["status"] == "preserved"
    assert by_term["XYZZY_ABSENT_TERM"]["status"] == "omitted"

    store.close()


# ── Amendment II: Evidence preserves observations, not conclusions ────────────

def test_amendment_ii_evidence_structure(seeded):
    """Evidence JSON must contain contract_obligation, observed_render, supporting_trace.
    It must not contain evaluative prose keys.
    """
    store, ids = seeded
    findings = evaluate_structural(ids["narrative_id"], ids["plan_id"], store._conn)

    for f in findings:
        ev = json.loads(f["evidence"])
        assert "contract_obligation" in ev, "evidence missing contract_obligation"
        assert "observed_render" in ev,     "evidence missing observed_render"
        assert "supporting_trace" in ev,    "evidence missing supporting_trace"
        assert "finding" not in ev,         "evidence must not editorialize"
        assert "conclusion" not in ev,      "evidence must not editorialize"
        assert "meaning" not in ev,         "evidence must not editorialize"
        # supporting_trace must reference canonical IDs
        assert ids["narrative_id"] in ev["supporting_trace"]
        assert ids["plan_id"] in ev["supporting_trace"]


# ── INV-EF-2: Read-only boundary (static) ────────────────────────────────────

def test_inv_ef2_structural_ef_only_produces_finding_rows():
    """Static: structural.py must contain no writes to any table except findings."""
    import re
    src = (
        Path(__file__).parent.parent
        / "hermeneia" / "compiler" / "evaluation_functions" / "structural.py"
    ).read_text()

    write_ops = re.compile(
        r"\b(INSERT|UPDATE|DELETE)\s+(?:OR\s+\w+\s+)?(?:INTO\s+)?(\w+)",
        re.IGNORECASE,
    )
    for m in write_ops.finditer(src):
        table = m.group(2).lower()
        assert table == "findings", (
            f"Structural EF writes to forbidden table: {table!r} ({m.group(0).strip()!r})"
        )


# ── INV-EF-4: Orthogonality boundary (static) ────────────────────────────────

def test_ef_contract_structural_satisfies_constitutional_contract():
    """Every registered EF must satisfy EvaluationFunctionContract — checked statically."""
    violations = validate_ef_contract(structural_ef)
    assert not violations, (
        "Structural EF violates its constitutional contract:\n" + "\n".join(violations)
    )


def test_ef_contract_dimension_is_ratified():
    """EF dimension must be in the ratified dimension vocabulary."""
    assert structural_ef.dimension in RATIFIED_DIMENSIONS, (
        f"Dimension {structural_ef.dimension!r} is not ratified. "
        f"Ratified: {sorted(RATIFIED_DIMENSIONS)}"
    )


def test_inv_ef4_structural_ef_does_not_import_llm_clients():
    """The Structural EF must have zero LLM dependency."""
    import re
    src = (
        Path(__file__).parent.parent
        / "hermeneia" / "compiler" / "evaluation_functions" / "structural.py"
    ).read_text()

    forbidden = re.compile(r"\b(anthropic|openai|google\.generativeai|genai|mistralai|cohere|ollama)\b")
    assert not forbidden.search(src), "Structural EF contains LLM client import"


# ── Storage round-trip ────────────────────────────────────────────────────────

def test_findings_persist_and_are_idempotent(seeded):
    """Findings written to storage survive retrieval; re-insert is a silent no-op."""
    store, ids = seeded

    findings = evaluate_structural(ids["narrative_id"], ids["plan_id"], store._conn)
    store.insert_findings_batch(findings)

    assert store.finding_count() == len(findings)
    retrieved = store.findings_for_narrative(ids["narrative_id"], dimension="structural")
    assert len(retrieved) == len(findings)

    # Re-insert must be idempotent (INSERT OR IGNORE)
    store.insert_findings_batch(findings)
    assert store.finding_count() == len(findings), "Duplicate insert added rows"


def test_findings_have_constitutional_profile(seeded):
    """Every Finding must carry the constitutional profile under which it was produced."""
    store, ids = seeded
    findings = evaluate_structural(ids["narrative_id"], ids["plan_id"], store._conn)

    for f in findings:
        profile = json.loads(f["constitution_version"])
        assert profile["constitution_version"] == "1.0.0"
        assert profile["adr"] == "ADR-0041"
