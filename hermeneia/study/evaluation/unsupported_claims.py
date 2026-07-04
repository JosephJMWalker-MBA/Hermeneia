"""Unsupported-claims scorer (design §9, future scorer) — the third ruler.

It composes the two prior obligations at the level of a surfaced claim:

    A surfaced claim is unsupported when it has no acceptable support path.

An acceptable support path requires all three:
  1. lineage exists — the claim reaches a source document;
  2. the lineage is traceable — a walkable path to a source location;
  3. the supporting document is inside the declared corpus boundary
     (declared and not excluded).

**Constitutional guardrail:** *unsupported* does not mean "bad interpretation."
It means Hermeneia cannot walk this claim to permissible evidence. The scorer
judges support, never quality.

Each surfaced lineage record (issue #62) is treated as a claim-bearing item.
The checks are evaluated inline — mirroring, but not calling, the evidence and
corpus-boundary scorers — so this scorer stands alone and no scorer order
matters. Deterministic and provider-free; it reads only the packet and mutates
nothing.
"""
from __future__ import annotations

from typing import Any

from .scorer import FAIL, NOT_APPLICABLE, PASS, ScorerVerdict


UNSUPPORTED_CLAIMS = "unsupported_claims"


def _support_gap(
    record: dict[str, Any],
    declared: dict[str, dict[str, Any]],
) -> str | None:
    """Return the reason a claim lacks acceptable support, or None if supported."""
    source = record.get("source") or {}
    document_id = source.get("document_id")

    # 1. Lineage exists — the claim reaches a source document.
    if document_id is None:
        return "no lineage path to a source document"

    # 2. The lineage is traceable — a walkable path to a source location.
    if not record.get("traceable"):
        missing = ", ".join(record.get("missing") or []) or "source reference"
        return f"lineage is not traceable (missing: {missing})"

    # 3. The supporting document is inside the declared corpus boundary.
    document = declared.get(str(document_id))
    if document is None:
        return f"support document {document_id} is not in the declared corpus"
    if document.get("excluded"):
        return f"support document {document_id} is excluded from analysis"

    return None


def score_unsupported_claims(packet: dict[str, Any]) -> ScorerVerdict:
    """Score whether every surfaced claim has an acceptable support path."""
    documents = ((packet.get("identity") or {}).get("documents")) or []
    declared: dict[str, dict[str, Any]] = {
        str(document.get("id")): document
        for document in documents
        if document.get("id") is not None
    }

    records = (packet.get("lineage") or {}).get("records") or []
    if not records:
        return ScorerVerdict(
            dimension=UNSUPPORTED_CLAIMS,
            verdict=NOT_APPLICABLE,
            reason="no surfaced claims to score for support",
            details={"claim_count": 0},
        )

    unsupported: list[tuple[str, str]] = []
    for record in records:
        gap = _support_gap(record, declared)
        if gap is not None:
            unsupported.append((str(record.get("record_id")), gap))

    if not unsupported:
        return ScorerVerdict(
            dimension=UNSUPPORTED_CLAIMS,
            verdict=PASS,
            reason=(
                f"all {len(records)} surfaced claims have an acceptable support "
                "path"
            ),
            details={"claim_count": len(records), "unsupported": 0},
        )

    described = "; ".join(
        f"{record_id} ({reason})" for record_id, reason in unsupported
    )
    return ScorerVerdict(
        dimension=UNSUPPORTED_CLAIMS,
        verdict=FAIL,
        reason=(
            f"{len(unsupported)} of {len(records)} surfaced claims cannot be "
            f"walked to permissible evidence: {described}"
        ),
        offending=[record_id for record_id, _ in unsupported],
        details={"claim_count": len(records), "unsupported": len(unsupported)},
    )
