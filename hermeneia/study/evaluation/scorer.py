"""Scorer interface for the evaluation harness (design §8).

A scorer is a pure function over a compiled study snapshot that returns a
structured verdict. No I/O, no provider calls, no persistence. A ``FAIL`` must
always carry a non-empty ``reason`` and, where meaningful, the offending record
ids — the same never-silently-drop discipline the lineage ``missing`` field
follows. ``NOT_APPLICABLE`` is a first-class verdict, distinct from a pass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


PASS = "pass"
FAIL = "fail"
NOT_APPLICABLE = "not_applicable"

_VALID_VERDICTS = frozenset({PASS, FAIL, NOT_APPLICABLE})


@dataclass(frozen=True)
class ScorerVerdict:
    """The result of scoring one obligation against a study snapshot."""

    dimension: str
    verdict: str
    reason: str
    offending: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in _VALID_VERDICTS:
            raise ValueError(
                f"invalid verdict {self.verdict!r}; "
                f"expected one of {sorted(_VALID_VERDICTS)}"
            )
        if not str(self.reason or "").strip():
            raise ValueError("ScorerVerdict.reason must be non-empty")
        if self.verdict == FAIL and not self.offending:
            # A failure with nothing to point at is a silent drop; forbid it
            # unless the reason explicitly stands in for the offending set.
            if "offending" not in self.details:
                raise ValueError(
                    "a FAIL verdict must name offending records or record why "
                    "it cannot in details['offending']"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "verdict": self.verdict,
            "reason": self.reason,
            "offending": list(self.offending),
            "details": dict(self.details),
        }


class Scorer(Protocol):
    """A deterministic obligation check over a compiled study snapshot.

    The snapshot for the first scorer is the synthesis packet (which carries
    its own lineage projection). Later scorers may accept a richer snapshot; the
    contract is only that ``score`` is pure and returns a ``ScorerVerdict``.
    """

    name: str
    dimension: str

    def score(self, snapshot: dict[str, Any]) -> ScorerVerdict: ...
