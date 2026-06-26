"""
Critic v0.1 — deterministic semantic fidelity validator.

The Critic does not judge writing quality. It judges semantic fidelity.

Inputs:  ArchitectPlan + RenderedNarrative + ExpressionProfile (optional)
Output:  ValidationReport (all fields inspectable, nothing subjective)

v0.1 checks (all deterministic, no LLM):
  1. Required terms present/missing (case-insensitive substring match)
  2. Forbidden claims absent
  3. Paragraph count matches plan
  4. Narrative is rendered (not the null placeholder)

v0.2 will add: observation reference detection, interpretation coverage.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ...storage.hashing import make_validation_report_id
from .profile_fidelity import check_profile_fidelity

_NULL_PLACEHOLDER = "[Artist not configured"


def validate(
    plan: dict,
    paragraphs: list[dict],
    narrative: dict,
    profile: dict | None = None,
) -> dict:
    """Run all Critic v0.1 checks. Returns a dict ready for DB insertion."""
    text = narrative.get("text", "")
    text_lower = text.lower()
    is_rendered = _NULL_PLACEHOLDER not in text and text.strip() != ""

    # ── 1. Required terms ──────────────────────────────────────────────────────
    seen_terms: dict[str, bool] = {}  # term → found?
    for para in paragraphs:
        terms = json.loads(para.get("required_terms", "[]"))
        for t in terms:
            term = t["term"]
            if term not in seen_terms:
                seen_terms[term] = term.lower() in text_lower

    required_present = [t for t, found in seen_terms.items() if found]
    required_missing = [t for t, found in seen_terms.items() if not found]

    # ── 2. Forbidden claims ────────────────────────────────────────────────────
    unsupported_claims: list[str] = []
    for para in paragraphs:
        for claim in json.loads(para.get("forbidden_claims", "[]")):
            if claim.lower() in text_lower and claim not in unsupported_claims:
                unsupported_claims.append(claim)

    # ── 3. Paragraph count ─────────────────────────────────────────────────────
    warnings: list[str] = []
    expected_paragraphs = len(paragraphs)
    if is_rendered:
        actual_paragraphs = [p for p in text.split("\n\n") if p.strip()]
        if len(actual_paragraphs) != expected_paragraphs:
            warnings.append(
                f"Paragraph count mismatch: Architect specified {expected_paragraphs}, "
                f"narrative has {len(actual_paragraphs)}"
            )

    # ── 4. Not placeholder ─────────────────────────────────────────────────────
    if not is_rendered:
        warnings.append("Narrative is a placeholder — Artist provider not connected")

    # ── Fidelity score ─────────────────────────────────────────────────────────
    # Terms are the primary signal. Forbidden violations and placeholder subtract.
    total_terms = len(seen_terms)
    if total_terms > 0:
        term_score = len(required_present) / total_terms
    else:
        term_score = 1.0 if is_rendered else 0.0

    forbidden_penalty = min(len(unsupported_claims) * 0.1, 0.3)
    raw_score = (term_score - forbidden_penalty) if is_rendered else 0.0
    semantic_fidelity = round(max(0.0, min(1.0, raw_score)) * 100, 1)

    # ── Approval ───────────────────────────────────────────────────────────────
    # Approved iff: rendered + no forbidden claims + all critical terms present
    critical_terms = set()
    for para in paragraphs:
        for t in json.loads(para.get("required_terms", "[]")):
            if t.get("priority") == "critical":
                critical_terms.add(t["term"])

    critical_missing = critical_terms & set(required_missing)
    approved = (
        is_rendered
        and len(unsupported_claims) == 0
        and len(critical_missing) == 0
    )

    # ── Profile fidelity ───────────────────────────────────────────────────────
    # Separate from semantic fidelity: did the expression contract hold?
    profile_fidelity_report = check_profile_fidelity(text, profile) if profile else None

    report_id = make_validation_report_id(narrative["id"])
    now = datetime.now(timezone.utc).isoformat()

    return {
        "id":                    report_id,
        "rendered_narrative_id": narrative["id"],
        "architect_plan_id":     plan["id"],
        "expression_profile_id": narrative.get("expression_profile_id"),
        "semantic_fidelity":     semantic_fidelity,
        "required_terms_present": json.dumps(required_present),
        "required_terms_missing": json.dumps(required_missing),
        "unsupported_claims":    json.dumps(unsupported_claims),
        "omitted_observations":  json.dumps([]),   # v0.2
        "omitted_interpretations": json.dumps([]), # v0.2
        "semantic_drift":        json.dumps([]),   # v0.2
        "warnings":              json.dumps(warnings),
        "approved":              1 if approved else 0,
        "profile_fidelity":      json.dumps(profile_fidelity_report) if profile_fidelity_report else None,
        "created_at":            now,
    }


def run_critic(
    obs_n: int,
    all_obs_ids: list[str],
    conn: sqlite3.Connection,
    narrative_id: str | None = None,
) -> dict:
    """
    Full Critic run for a given observation index.
    Resolves obs → blueprint → architect plan → rendered narrative → validate.
    Returns the validation report dict (not yet stored).
    Raises ValueError with a descriptive message if any step is missing.
    """
    if narrative_id:
        rn_row = conn.execute(
            "SELECT * FROM rendered_narratives WHERE id = ?",
            (narrative_id,),
        ).fetchone()
        if not rn_row:
            raise ValueError(f"Rendered Narrative {narrative_id!r} not found")
        narrative = dict(rn_row)

        plan_row = conn.execute(
            "SELECT * FROM architect_plans WHERE id = ?",
            (narrative["architect_plan_id"],),
        ).fetchone()
        if not plan_row:
            raise ValueError(
                f"No Architect Plan for Rendered Narrative {narrative_id!r}"
            )
        plan = dict(plan_row)
        paragraphs = [
            dict(r) for r in conn.execute(
                "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
                (plan["id"],),
            ).fetchall()
        ]
    else:
        if obs_n < 1 or obs_n > len(all_obs_ids):
            raise ValueError(f"OBS-{obs_n} not found")

        obs_id = all_obs_ids[obs_n - 1]

        bp_row = conn.execute(
            """
            SELECT nb.* FROM narrative_blueprints nb
            JOIN blueprint_observation_links bol ON bol.blueprint_id = nb.id
            WHERE bol.observation_id = ? ORDER BY nb.created_at LIMIT 1
            """,
            (obs_id,),
        ).fetchone()
        if not bp_row:
            raise ValueError(f"No Narrative Blueprint cites OBS-{obs_n}")

        plan_row = conn.execute(
            "SELECT * FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
            (bp_row["id"],),
        ).fetchone()
        if not plan_row:
            raise ValueError(f"No Architect Plan for OBS-{obs_n} — run: herm architect OBS-{obs_n}")

        plan = dict(plan_row)
        paragraphs = [
            dict(r) for r in conn.execute(
                "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
                (plan["id"],),
            ).fetchall()
        ]
        rn_row = conn.execute(
            "SELECT * FROM rendered_narratives WHERE architect_plan_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (plan["id"],),
        ).fetchone()

        if not rn_row:
            raise ValueError(f"No Rendered Narrative for OBS-{obs_n} — run: herm artist OBS-{obs_n}")
        narrative = dict(rn_row)

    profile: dict | None = None
    if narrative.get("expression_profile_id"):
        pr = conn.execute(
            "SELECT * FROM expression_profiles WHERE id = ?",
            (narrative["expression_profile_id"],),
        ).fetchone()
        if pr:
            profile = dict(pr)

    return validate(plan, paragraphs, narrative, profile)
