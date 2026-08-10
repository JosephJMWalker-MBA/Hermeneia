"""Stewardship projection for derived Reader structure candidates."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence


VALID_STRUCTURE_VERDICTS = {"accepted", "rejected"}


def canonical_json(value: object) -> str:
    """Stable JSON for governance IDs and persisted snapshots."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def make_reader_structure_decision_id(
    *,
    candidate_id: str,
    verdict: str,
    rationale: str,
    steward_id: str,
    decided_at: str,
    supersedes_decision_id: str | None,
) -> str:
    payload = canonical_json(
        {
            "candidate_id": candidate_id,
            "verdict": verdict,
            "rationale": rationale,
            "steward_id": steward_id,
            "decided_at": decided_at,
            "supersedes_decision_id": supersedes_decision_id,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def decision_payload(row: Mapping[str, object]) -> dict[str, object]:
    snapshot = row.get("candidate_snapshot")
    parsed_snapshot: object
    if isinstance(snapshot, str):
        try:
            parsed_snapshot = json.loads(snapshot)
        except json.JSONDecodeError:
            parsed_snapshot = None
    else:
        parsed_snapshot = snapshot
    return {
        "decision_id": row.get("id"),
        "candidate_id": row.get("candidate_id"),
        "document_id": row.get("document_id"),
        "candidate_snapshot": parsed_snapshot,
        "candidate_inference_version": row.get("candidate_inference_version"),
        "verdict": row.get("verdict"),
        "rationale": row.get("rationale"),
        "steward_id": row.get("steward_id"),
        "decided_at": row.get("decided_at"),
        "supersedes_decision_id": row.get("supersedes_decision_id"),
        "created_at": row.get("created_at"),
    }


def load_structure_decisions(conn, document_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        """SELECT * FROM reader_structure_decisions
           WHERE document_id = ?
           ORDER BY candidate_id, decided_at, created_at, id""",
        (document_id,),
    ).fetchall()
    return [decision_payload(dict(row)) for row in rows]


def enrich_structure_with_stewardship(
    structure: Mapping[str, object],
    decisions: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Attach effective stewardship without hiding rejected inferences."""
    enriched = dict(structure)
    items = []
    decisions_by_candidate: dict[str, list[dict[str, object]]] = defaultdict(list)
    for decision in decisions:
        decisions_by_candidate[str(decision.get("candidate_id") or "")].append(
            dict(decision)
        )

    for item in structure.get("items") or []:
        candidate = dict(item)
        candidate_id = str(candidate.get("candidate_id") or candidate.get("id") or "")
        history = decisions_by_candidate.get(candidate_id, [])
        candidate["stewardship"] = resolve_stewardship(history)
        items.append(candidate)
    enriched["items"] = items
    enriched["accepted_structure"] = [
        item for item in items
        if item["stewardship"]["status"] == "accepted"
    ]
    enriched["rejected_candidates"] = [
        item for item in items
        if item["stewardship"]["status"] == "rejected"
    ]
    enriched["undecided_candidates"] = [
        item for item in items
        if item["stewardship"]["status"] == "undecided"
    ]
    return enriched


def resolve_stewardship(
    history: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    ordered = sorted(
        [dict(item) for item in history],
        key=lambda item: (
            str(item.get("decided_at") or ""),
            str(item.get("created_at") or ""),
            str(item.get("decision_id") or ""),
        ),
    )
    superseded = {
        str(item.get("supersedes_decision_id"))
        for item in ordered
        if item.get("supersedes_decision_id")
    }
    for item in ordered:
        decision_id = str(item.get("decision_id") or "")
        item["superseded"] = decision_id in superseded
        item["superseded_by"] = [
            str(other.get("decision_id"))
            for other in ordered
            if other.get("supersedes_decision_id") == decision_id
        ]
    active = [
        item for item in ordered
        if not item.get("superseded")
    ]
    effective = active[-1] if active else None
    return {
        "status": str(effective.get("verdict")) if effective else "undecided",
        "effective_decision": effective,
        "history": ordered,
    }


def decision_row(
    *,
    candidate: Mapping[str, object],
    candidate_snapshot: Mapping[str, object],
    verdict: str,
    rationale: str,
    steward_id: str,
    decided_at: str,
    supersedes_decision_id: str | None,
) -> dict[str, object]:
    candidate_id = str(candidate.get("candidate_id") or candidate.get("id") or "")
    return {
        "id": make_reader_structure_decision_id(
            candidate_id=candidate_id,
            verdict=verdict,
            rationale=rationale,
            steward_id=steward_id,
            decided_at=decided_at,
            supersedes_decision_id=supersedes_decision_id,
        ),
        "candidate_id": candidate_id,
        "document_id": str(candidate.get("document_id") or ""),
        "candidate_snapshot": canonical_json(candidate_snapshot),
        "candidate_inference_version": str(candidate.get("inference_version") or ""),
        "verdict": verdict,
        "rationale": rationale,
        "steward_id": steward_id,
        "decided_at": decided_at,
        "supersedes_decision_id": supersedes_decision_id,
        "created_at": decided_at,
    }
