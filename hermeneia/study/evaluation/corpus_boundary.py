"""Corpus-boundary scorer (design §9, future scorer #1) — the second ruler.

Where evidence preservation asks *can the surfaced item walk back to
evidence?*, this scorer asks the prior question of permissibility:

    Was that evidence allowed to be used at all?

The corpus model is Primary / Supporting / Excluded. Primary and Supporting
(reference, commentary, …) roles are permitted to inform interpretation;
**Excluded** documents are not, and a record grounded outside the declared
corpus is a boundary violation. This mirrors the query-time exclusion proven in
``tests/test_corpus_scope_boundary.py``, applied here in the study lane.

Deterministic and provider-free: it reads only the packet's declared corpus
(``identity.documents``) and its lineage records. It mutates nothing.
"""
from __future__ import annotations

from typing import Any

from .scorer import FAIL, NOT_APPLICABLE, PASS, ScorerVerdict


CORPUS_BOUNDARY = "corpus_boundary"


def score_corpus_boundary(packet: dict[str, Any]) -> ScorerVerdict:
    """Score whether every surfaced record draws on a permitted document."""
    documents = ((packet.get("identity") or {}).get("documents")) or []
    declared: dict[str, dict[str, Any]] = {
        str(document.get("id")): document
        for document in documents
        if document.get("id") is not None
    }

    lineage = packet.get("lineage") or {}
    records = lineage.get("records") or []
    assessable = [
        record
        for record in records
        if (record.get("source") or {}).get("document_id") is not None
    ]

    if not assessable:
        return ScorerVerdict(
            dimension=CORPUS_BOUNDARY,
            verdict=NOT_APPLICABLE,
            reason=(
                "no surfaced records reference a source document to assess for "
                "corpus boundary permissibility"
            ),
            details={"assessable_records": 0},
        )

    violations: list[tuple[str, str, str]] = []  # (record_id, document_id, why)
    for record in assessable:
        record_id = str(record.get("record_id"))
        document_id = str((record.get("source") or {}).get("document_id"))
        document = declared.get(document_id)
        if document is None:
            violations.append(
                (record_id, document_id, "document not in the declared corpus")
            )
        elif document.get("excluded"):
            violations.append(
                (record_id, document_id, "document is excluded from analysis")
            )

    if not violations:
        return ScorerVerdict(
            dimension=CORPUS_BOUNDARY,
            verdict=PASS,
            reason=(
                f"all {len(assessable)} surfaced records draw on permitted "
                "corpus documents"
            ),
            details={
                "assessable_records": len(assessable),
                "violations": 0,
            },
        )

    described = "; ".join(
        f"{record_id} → {document_id} ({why})"
        for record_id, document_id, why in violations
    )
    return ScorerVerdict(
        dimension=CORPUS_BOUNDARY,
        verdict=FAIL,
        reason=(
            f"{len(violations)} of {len(assessable)} surfaced records draw on "
            f"impermissible documents: {described}"
        ),
        offending=[record_id for record_id, _, _ in violations],
        details={
            "assessable_records": len(assessable),
            "violations": len(violations),
        },
    )
