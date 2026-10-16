"""ADR-0046 activation gate: changed evaluation semantics require a recorded ratification (Constitution Art. XIV).

U activates as one step: provenance-v1.1 as the default, schema 22, and `unverifiable` admitted for provenance. This
test fails if any piece is active while ADR-0046 or ADR-0048 lacks a completed ratification record, or if only some of
the pieces are active.
"""
from __future__ import annotations

import inspect
from pathlib import Path
import re

from hermeneia.compiler.evaluation_functions import provenance
from hermeneia.storage import sqlite as storage

ADR = Path(__file__).resolve().parents[1] / "docs" / "adr"


def _ratified(name: str) -> bool:
    text = (ADR / name).read_text(encoding="utf-8")
    status = re.search(r"^\*\*Status:\*\* ([A-Z]+)", text, re.M)
    ratified_by = re.search(r"^\| Ratified by \|\s*([^|]*?)\s*\|", text, re.M)
    return bool(status and status.group(1) == "RATIFIED" and ratified_by and ratified_by.group(1))


def _pieces() -> dict[str, bool]:
    default = inspect.signature(provenance.evaluate_provenance).parameters["method"].default
    return {
        "provenance-v1.1 is the default": default == provenance.UNVERIFIABLE_METHOD,
        "schema 22": storage.SCHEMA_VERSION >= 22,
        "unverifiable admitted": ("unverifiable", "unverifiable") in storage.ACTIVE_DIMENSION_DISPOSITIONS.get("provenance", ()),
    }


def test_unverifiable_activates_whole_or_not_at_all():
    assert len(set(_pieces().values())) == 1, _pieces()


def test_unverifiable_is_active_only_after_recorded_ratification():
    if any(_pieces().values()):
        assert _ratified("ADR-0046-provenance-absence-is-not-transformation.md"), "ADR-0046 has no ratification record"
        assert _ratified("ADR-0048-newer-workspace-schemas-are-refused.md"), "ADR-0048 has no ratification record"


def test_the_gate_reads_the_current_records():
    assert not _ratified("ADR-0046-provenance-absence-is-not-transformation.md")
    assert not any(_pieces().values())
