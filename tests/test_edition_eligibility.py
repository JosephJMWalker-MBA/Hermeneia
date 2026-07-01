"""
Edition Eligibility Tests

Invariants:
  - An edition is not an export. It is a signed maturity state.
  - A cycle does not count unless the system can prove disciplined completion.
  - Exports, incomplete stages, and skipped steps do not increment cycle count.
  - Human signature is required for Edition designation.
  - 12 qualified cycles create eligibility; they do not create an Edition.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermeneia.cli.edition_cmd import (
    EDITION_MIN_CYCLES,
    EditionError,
    _check_cycle_qualification,
    _edition_status,
    _load_cycles,
    _save_cycles,
    cmd_edition_record,
    cmd_edition_status,
    cmd_edition_designate,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _write_build(pub: Path, source_artifacts: list | None = None) -> None:
    artifacts = source_artifacts if source_artifacts is not None else [
        {"path": "docs/papers/blueprint.md", "sha256": "abc123", "tags": ["blueprint"]}
    ]
    (pub / "build.json").write_text(json.dumps({
        "build_id": "test-build-001",
        "build_timestamp": "2026-01-01T00:00:00+00:00",
        "hermeneia_version": "0.1.0",
        "source_artifacts": artifacts,
        "blueprint": {"path": "docs/papers/blueprint.md", "status": "ratified"},
    }))


def _write_coverage(pub: Path, outcome: str = "pass") -> None:
    (pub / "coverage.json").write_text(json.dumps({
        "build_id": "test-build-001",
        "outcome": outcome,
        "tag_index": {},
    }))


def _write_release(pub: Path) -> None:
    (pub / "release_recommendation.json").write_text(json.dumps({
        "build_id": "test-build-001",
        "outcome": "RECOMMEND_RELEASE",
        "steward_signature": None,
    }))


def _write_preservation(pub: Path, overall: str = "pass") -> None:
    (pub / "preservation_report.json").write_text(json.dumps({
        "build_id": "test-build-001",
        "overall_outcome": overall,
    }))


def _full_pub_dir(tmp_path: Path) -> Path:
    pub = tmp_path / "publication"
    pub.mkdir()
    _write_build(pub)
    _write_coverage(pub)
    _write_release(pub)
    _write_preservation(pub)
    return pub


# ── Qualification checks ──────────────────────────────────────────────────────

def test_all_missing_files_fail_qualification(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    qualified, reasons, evidence = _check_cycle_qualification(pub)
    assert not qualified
    assert any("build.json" in r for r in reasons)
    assert any("coverage.json" in r for r in reasons)
    assert any("release_recommendation.json" in r for r in reasons)
    assert any("preservation_report.json" in r for r in reasons)


def test_empty_source_artifacts_disqualify(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    _write_build(pub, source_artifacts=[])
    _write_coverage(pub)
    _write_release(pub)
    _write_preservation(pub)
    qualified, reasons, evidence = _check_cycle_qualification(pub)
    assert not qualified
    assert not evidence["source_artifacts_nonempty"]
    assert any("empty" in r.lower() or "source_artifact" in r for r in reasons)


def test_coverage_warn_disqualifies(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    _write_build(pub)
    _write_coverage(pub, outcome="warn")
    _write_release(pub)
    _write_preservation(pub)
    qualified, reasons, evidence = _check_cycle_qualification(pub)
    assert not qualified
    assert not evidence["coverage_pass"]
    assert any("coverage" in r.lower() for r in reasons)


def test_coverage_fail_disqualifies(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    _write_build(pub)
    _write_coverage(pub, outcome="fail")
    _write_release(pub)
    _write_preservation(pub)
    qualified, reasons, _ = _check_cycle_qualification(pub)
    assert not qualified


def test_preservation_fail_disqualifies(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    _write_build(pub)
    _write_coverage(pub)
    _write_release(pub)
    _write_preservation(pub, overall="fail")
    qualified, reasons, evidence = _check_cycle_qualification(pub)
    assert not qualified
    assert not evidence["preservation_verified"]


def test_preservation_warn_qualifies(tmp_path):
    """warn is acceptable — only fail blocks a qualified cycle."""
    pub = tmp_path / "publication"
    pub.mkdir()
    _write_build(pub)
    _write_coverage(pub)
    _write_release(pub)
    _write_preservation(pub, overall="warn")
    qualified, reasons, evidence = _check_cycle_qualification(pub)
    assert qualified, f"Expected qualified but got reasons: {reasons}"
    assert evidence["preservation_verified"]


def test_all_present_qualifies(tmp_path):
    pub = _full_pub_dir(tmp_path)
    qualified, reasons, evidence = _check_cycle_qualification(pub)
    assert qualified, f"Expected qualified but got: {reasons}"
    assert all(evidence.values())


# ── Edition status ─────────────────────────────────────────────────────────────

def test_zero_cycles_is_working_draft(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    status = _edition_status(store)
    assert status["status_label"] == "Working Draft"
    assert status["cycle_count"] == 0
    assert not status["eligible"]


def test_one_cycle_is_reviewed_draft(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    store["cycles"] = [{"qualified": True, "build_id": "b001"}]
    status = _edition_status(store)
    assert "Reviewed Draft" in status["status_label"]
    assert status["cycle_count"] == 1
    assert not status["eligible"]


def test_eleven_cycles_not_eligible(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    store["cycles"] = [{"qualified": True, "build_id": f"b{i}"} for i in range(11)]
    status = _edition_status(store)
    assert not status["eligible"]
    assert status["cycles_remaining"] == 1


def test_twelve_cycles_edition_eligible(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    store["cycles"] = [{"qualified": True, "build_id": f"b{i}"} for i in range(12)]
    status = _edition_status(store)
    assert status["eligible"]
    assert status["status_label"] == "Edition-Eligible"
    assert status["cycles_remaining"] == 0


def test_unqualified_cycles_do_not_count(tmp_path):
    """Cycles recorded as qualified=False must not count toward edition eligibility."""
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    # 11 qualified + 100 unqualified = still not eligible
    store["cycles"] = (
        [{"qualified": True, "build_id": f"ok-{i}"} for i in range(11)]
        + [{"qualified": False, "build_id": f"bad-{i}"} for i in range(100)]
    )
    status = _edition_status(store)
    assert not status["eligible"]
    assert status["cycle_count"] == 11


# ── cmd_edition_record ─────────────────────────────────────────────────────────

def test_record_incomplete_pipeline_fails(tmp_path):
    """An incomplete pipeline must not record a cycle."""
    pub = tmp_path / "publication"
    pub.mkdir()
    _write_build(pub)
    # missing coverage, release, preservation
    with pytest.raises(SystemExit) as exc:
        cmd_edition_record(output_dir=str(pub))
    assert exc.value.code == 1


def test_record_qualified_cycle_increments_count(tmp_path):
    pub = _full_pub_dir(tmp_path)
    cmd_edition_record(output_dir=str(pub))
    store = _load_cycles(pub)
    status = _edition_status(store)
    assert status["cycle_count"] == 1


def test_record_does_not_increment_on_coverage_fail(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    _write_build(pub)
    _write_coverage(pub, outcome="fail")
    _write_release(pub)
    _write_preservation(pub)
    with pytest.raises(SystemExit):
        cmd_edition_record(output_dir=str(pub))
    store = _load_cycles(pub)
    assert _edition_status(store)["cycle_count"] == 0


def test_duplicate_build_id_blocked_without_reaffirmation(tmp_path):
    """The same build_id cannot be recorded twice without a reaffirmation note."""
    pub = _full_pub_dir(tmp_path)
    cmd_edition_record(output_dir=str(pub))
    with pytest.raises(SystemExit) as exc:
        cmd_edition_record(output_dir=str(pub))
    assert exc.value.code == 1
    # Only one cycle recorded
    assert _edition_status(_load_cycles(pub))["cycle_count"] == 1


def test_duplicate_build_id_allowed_with_reaffirmation(tmp_path):
    """A reaffirmation note allows recording the same build_id a second time."""
    pub = _full_pub_dir(tmp_path)
    cmd_edition_record(output_dir=str(pub))
    cmd_edition_record(
        output_dir=str(pub),
        steward_reaffirmation="Prior understanding reviewed and intentionally preserved.",
    )
    assert _edition_status(_load_cycles(pub))["cycle_count"] == 2


# ── cmd_edition_designate ──────────────────────────────────────────────────────

def test_designate_blocked_when_not_eligible(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    # Only 1 cycle — not eligible
    store = _load_cycles(pub)
    store["cycles"] = [{"qualified": True, "build_id": "b001"}]
    _save_cycles(store, pub)
    with pytest.raises(SystemExit) as exc:
        cmd_edition_designate(steward="Test Steward", output_dir=str(pub))
    assert exc.value.code == 1
    assert not (pub / "edition.json").exists()


def test_designate_succeeds_when_eligible(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    store["cycles"] = [{"qualified": True, "build_id": f"b{i}"} for i in range(12)]
    _save_cycles(store, pub)
    cmd_edition_designate(steward="Test Steward", output_dir=str(pub))
    edition = json.loads((pub / "edition.json").read_text())
    assert edition["steward"] == "Test Steward"
    assert edition["status_at_designation"] == "Edition"
    assert edition["qualified_cycle_count"] == 12


def test_designate_blocked_if_edition_already_exists(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    store["cycles"] = [{"qualified": True, "build_id": f"b{i}"} for i in range(12)]
    _save_cycles(store, pub)
    cmd_edition_designate(steward="First Steward", output_dir=str(pub))
    with pytest.raises(SystemExit) as exc:
        cmd_edition_designate(steward="Second Steward", output_dir=str(pub))
    assert exc.value.code == 1
    # Original designation preserved
    edition = json.loads((pub / "edition.json").read_text())
    assert edition["steward"] == "First Steward"


def test_edition_label_defaults_to_edition_n(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    store["cycles"] = [{"qualified": True, "build_id": f"b{i}"} for i in range(12)]
    _save_cycles(store, pub)
    cmd_edition_designate(steward="Steward", output_dir=str(pub))
    edition = json.loads((pub / "edition.json").read_text())
    assert edition["edition_label"] == "Edition 12"


def test_custom_edition_label(tmp_path):
    pub = tmp_path / "publication"
    pub.mkdir()
    store = _load_cycles(pub)
    store["cycles"] = [{"qualified": True, "build_id": f"b{i}"} for i in range(12)]
    _save_cycles(store, pub)
    cmd_edition_designate(steward="Steward", edition_label="First Edition", output_dir=str(pub))
    edition = json.loads((pub / "edition.json").read_text())
    assert edition["edition_label"] == "First Edition"
