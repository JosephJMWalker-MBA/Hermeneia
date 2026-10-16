"""ADR-0046 activation gate: changed evaluation semantics require a recorded ratification (Constitution Art. XIV).

U activates as one step: provenance-v1.1 as the default, schema 22, and `unverifiable` admitted for provenance. This
test fails if any piece is active while ADR-0046 or ADR-0048 lacks a completed ratification record, or if only some of
the pieces are active.
"""
from __future__ import annotations

import inspect
from pathlib import Path
import re
import subprocess

from hermeneia.compiler.evaluation_functions import provenance
from hermeneia.storage import findings_vocabulary
from hermeneia.storage import sqlite as storage

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs" / "adr"


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


def _git_show(revision_path: str) -> str | None:
    result = subprocess.run(["git", "show", revision_path], cwd=ROOT, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def _release_refuses_newer_schemas(tag: str | None) -> bool:
    """The tagged release ships ADR-0048's refusal at schema 21, so its builds refuse a schema-22 workspace."""
    if not tag:
        return False
    guard, store = _git_show(f"{tag}:hermeneia/storage/schema_guard.py"), _git_show(f"{tag}:hermeneia/storage/sqlite.py")
    return bool(guard and "NewerSchemaError" in guard and store and re.search(r"^SCHEMA_VERSION = 21\b", store, re.M))


def test_schema_22_waits_for_a_released_boundary():
    """ADR-0048 must ship in a tagged release at schema 21 before any build migrates a workspace to schema 22."""
    if storage.SCHEMA_VERSION >= 22:
        assert _release_refuses_newer_schemas(findings_vocabulary.REFUSING_RELEASE_TAG), (
            "schema 22 needs REFUSING_RELEASE_TAG naming a tagged release that refuses newer schemas at schema 21")


def test_the_boundary_check_rejects_a_release_without_the_refusal():
    assert not _release_refuses_newer_schemas(None)
    assert not _release_refuses_newer_schemas("v0.6.0")  # the only existing tag predates ADR-0048
