"""Read-only Interpretive Divergence Projection authorized by ADR-0043."""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any


class InterpretiveDivergenceError(ValueError):
    """Raised when required canonical inputs or lineage are unavailable."""


def _normalized_claim(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _evidence_ids(row: sqlite3.Row) -> set[str]:
    try:
        stored = json.loads(row["evidence_observation_ids"] or "[]")
    except (TypeError, json.JSONDecodeError):
        stored = []
    return {row["observation_id"], *stored}


def _interpretation(
    conn: sqlite3.Connection,
    interpretation_id: str,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT i.*, p.name AS registered_perspective_name,
               p.description AS perspective_description
        FROM interpretations i
        LEFT JOIN perspectives p ON p.id = i.perspective_id
        WHERE i.id = ?
        """,
        (interpretation_id,),
    ).fetchone()
    if row is None:
        raise InterpretiveDivergenceError(
            f"interpretation missing: {interpretation_id}"
        )
    if row["perspective_id"] and row["registered_perspective_name"] is None:
        raise InterpretiveDivergenceError(
            f"Perspective missing: {row['perspective_id']}"
        )

    evidence_ids = sorted(_evidence_ids(row))
    placeholders = ",".join("?" for _ in evidence_ids)
    observations = conn.execute(
        f"""
        SELECT id, raw_text, page, paragraph, sentence
        FROM observations
        WHERE id IN ({placeholders})
        ORDER BY page, paragraph, sentence, id
        """,
        evidence_ids,
    ).fetchall()
    if len(observations) != len(evidence_ids):
        found = {observation["id"] for observation in observations}
        missing = sorted(set(evidence_ids) - found)
        raise InterpretiveDivergenceError(
            f"Observation missing: {', '.join(missing)}"
        )

    return {
        "id": row["id"],
        "text": row["text"],
        "normalized_text": _normalized_claim(row["text"]),
        "perspective": {
            "id": row["perspective_id"],
            "name": row["registered_perspective_name"] or row["perspective"],
            "registered": row["perspective_id"] is not None,
            "description": row["perspective_description"],
        },
        "evidential_status": row["evidential_status"],
        "confidence": row["confidence"],
        "evidence": {
            observation["id"]: {
                "id": observation["id"],
                "raw_text": observation["raw_text"],
                "location": {
                    "page": observation["page"],
                    "paragraph": observation["paragraph"],
                    "sentence": observation["sentence"],
                },
            }
            for observation in observations
        },
    }


def _claim_ref(interpretation: dict[str, Any]) -> dict[str, Any]:
    return {
        "interpretation_id": interpretation["id"],
        "text": interpretation["text"],
        "perspective": interpretation["perspective"],
        "evidential_status": interpretation["evidential_status"],
        "confidence": interpretation["confidence"],
    }


def _summary(
    interpretation_a: dict[str, Any],
    interpretation_b: dict[str, Any],
    shared_evidence: set[str],
    evidence_a: set[str],
    evidence_b: set[str],
) -> dict[str, list[str]]:
    stayed_same: list[str] = []
    changed: list[str] = []
    why: list[str] = []

    claims_match = (
        interpretation_a["normalized_text"]
        == interpretation_b["normalized_text"]
    )
    perspectives_match = (
        interpretation_a["perspective"]["id"],
        interpretation_a["perspective"]["name"],
    ) == (
        interpretation_b["perspective"]["id"],
        interpretation_b["perspective"]["name"],
    )
    statuses_match = (
        interpretation_a["evidential_status"]
        == interpretation_b["evidential_status"]
    )

    if claims_match:
        stayed_same.append("The canonical claim text is identical after whitespace and case normalization.")
    else:
        changed.append("The canonical Interpretation claims are distinct.")

    if perspectives_match:
        stayed_same.append(
            f"Both claims use the {interpretation_a['perspective']['name']} Perspective."
        )
    else:
        changed.append("The claims use different Perspectives.")
        why.append(
            "Perspective changed from "
            f"{interpretation_a['perspective']['name']} to "
            f"{interpretation_b['perspective']['name']}."
        )

    if evidence_a == evidence_b:
        stayed_same.append("Both claims cite the same Observation evidence.")
    else:
        changed.append("The supporting Observation sets differ.")
        if shared_evidence:
            why.append(
                "The claims share some evidence but emphasize different additional Observations."
            )
        else:
            why.append("The claims rely on disjoint Observation evidence.")

    if statuses_match:
        stayed_same.append(
            "Both claims have evidential status "
            f"{interpretation_a['evidential_status']}."
        )
    else:
        changed.append("The evidential statuses differ.")
        why.append(
            "Evidential status changed from "
            f"{interpretation_a['evidential_status']} to "
            f"{interpretation_b['evidential_status']}."
        )

    if not claims_match and not why:
        why.append(
            "The canonical claims differ, but Phase 1 has no authorized semantic rule "
            "for attributing the cause."
        )

    return {
        "what_stayed_the_same": stayed_same,
        "what_changed": changed,
        "why_it_changed": why,
    }


def interpretive_divergence_projection(
    conn: sqlite3.Connection,
    interpretation_a_id: str,
    interpretation_b_id: str,
) -> dict[str, Any]:
    """Regenerate a comparison projection from two canonical Interpretations."""
    interpretation_a = _interpretation(conn, interpretation_a_id)
    interpretation_b = _interpretation(conn, interpretation_b_id)

    evidence_a = set(interpretation_a["evidence"])
    evidence_b = set(interpretation_b["evidence"])
    shared_evidence = evidence_a & evidence_b
    only_a = evidence_a - evidence_b
    only_b = evidence_b - evidence_a
    claims_match = (
        interpretation_a["normalized_text"]
        == interpretation_b["normalized_text"]
    )

    shared_claims = []
    distinct_claims = {"interpretation_a": [], "interpretation_b": []}
    if claims_match:
        shared_claims.append({
            "interpretation_a": _claim_ref(interpretation_a),
            "interpretation_b": _claim_ref(interpretation_b),
            "basis": "exact_normalized_claim_text",
        })
    else:
        distinct_claims["interpretation_a"].append(
            _claim_ref(interpretation_a)
        )
        distinct_claims["interpretation_b"].append(
            _claim_ref(interpretation_b)
        )

    def evidence_rows(
        ids: set[str],
        interpretation: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            interpretation["evidence"][observation_id]
            for observation_id in sorted(ids)
        ]

    shared_rows = [
        interpretation_a["evidence"][observation_id]
        for observation_id in sorted(shared_evidence)
    ]

    return {
        "classification": "interpretive_divergence_projection",
        "persistence": "none",
        "inputs": {
            "interpretation_a": _claim_ref(interpretation_a),
            "interpretation_b": _claim_ref(interpretation_b),
        },
        "shared_claims": shared_claims,
        "distinct_claims": distinct_claims,
        "contradictory_claims": {
            "status": "not_computed",
            "claims": [],
            "reason": (
                "No ratified deterministic Interpretation contradiction rule exists."
            ),
        },
        "evidence_differences": {
            "shared": shared_rows,
            "only_interpretation_a": evidence_rows(only_a, interpretation_a),
            "only_interpretation_b": evidence_rows(only_b, interpretation_b),
        },
        "interpretive_summary": _summary(
            interpretation_a,
            interpretation_b,
            shared_evidence,
            evidence_a,
            evidence_b,
        ),
        "expressive_divergence": {
            "status": "not_evaluated",
            "reason": (
                "This surface compares Interpretations, not RenderedNarratives "
                "or ExpressionProfiles."
            ),
        },
        "regeneration": {
            "source": "existing canonical Interpretation, Perspective, and Observation records",
            "persisted": False,
        },
    }
