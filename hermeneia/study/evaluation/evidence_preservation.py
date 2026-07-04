"""Evidence-preservation scorer (design §9) — the first ruler.

It asks one non-subjective question of a compiled synthesis packet:

    Did every surfaced packet item preserve a walkable path back to evidence,
    or did the system explicitly say why it could not?

Every record in the packet's lineage projection (issue #62) already carries a
``traceable`` flag and an explicit ``missing`` list. This scorer aggregates
them into a single obligation verdict. It is deterministic and provider-free,
reads only the packet, and never mutates canonical evidence.
"""
from __future__ import annotations

from typing import Any

from .scorer import FAIL, NOT_APPLICABLE, PASS, ScorerVerdict


EVIDENCE_PRESERVATION = "evidence_preservation"


def _describe(record: dict[str, Any]) -> str:
    record_id = record.get("record_id")
    missing = ", ".join(record.get("missing") or []) or "source reference"
    return f"{record_id} (missing: {missing})"


def score_evidence_preservation(packet: dict[str, Any]) -> ScorerVerdict:
    """Score whether every surfaced study record traces back to evidence."""
    lineage = packet.get("lineage") or {}
    records = lineage.get("records") or []

    if not records:
        return ScorerVerdict(
            dimension=EVIDENCE_PRESERVATION,
            verdict=NOT_APPLICABLE,
            reason=(
                "no surfaced study records to evaluate for evidence "
                "preservation"
            ),
            details={"record_count": 0},
        )

    untraceable = [record for record in records if not record.get("traceable")]

    if not untraceable:
        return ScorerVerdict(
            dimension=EVIDENCE_PRESERVATION,
            verdict=PASS,
            reason=(
                f"all {len(records)} surfaced records trace to a walkable "
                "source"
            ),
            details={
                "record_count": len(records),
                "traceable": len(records),
                "untraceable": 0,
            },
        )

    offending = [
        str(record.get("record_id"))
        for record in untraceable
        if record.get("record_id")
    ]
    described = "; ".join(_describe(record) for record in untraceable)
    return ScorerVerdict(
        dimension=EVIDENCE_PRESERVATION,
        verdict=FAIL,
        reason=(
            f"{len(untraceable)} of {len(records)} surfaced records do not "
            f"trace to a walkable source: {described}"
        ),
        offending=offending,
        details={
            "record_count": len(records),
            "traceable": len(records) - len(untraceable),
            "untraceable": len(untraceable),
        },
    )
