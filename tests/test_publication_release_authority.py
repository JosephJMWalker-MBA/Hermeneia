"""
Constitutional authority tests for the publication infrastructure.

Encodes the invariant:
    A signed or steward-ratified recommendation artifact must not be
    silently overwritten by automation.

VS-001 Remediation — F09, F03, F02, F05 coverage.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from hermeneia.cli.preserve_cmd import (
    PreservationError,
    _load_inputs,
    _run_export,
    _verify_continuation,
)
from hermeneia.cli.release_cmd import ReleaseError, _emit_recommendation


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_publication(tmp: Path) -> Path:
    """Minimal valid publication directory for release authority tests."""
    root = tmp / "project"
    root.mkdir()
    pub = root / "publication"
    pub.mkdir()
    docs = root / "docs" / "papers"
    docs.mkdir(parents=True)
    research = root / "docs" / "research"
    research.mkdir(parents=True)
    builds = root / "docs" / "builds"
    builds.mkdir(parents=True)

    bp = docs / "blueprint_000001.md"
    bp.write_text(
        "# Blueprint 000001\n\n"
        "**Governing question:** What properties become measurable?\n"
        "**Intent hypothesis:** Constitutional discipline enables measurement.\n"
    )
    bp_hash = _sha(bp)

    evidence = research / "experiment_001.md"
    evidence.write_text("# Experiment 001\n\nObservations.\n")
    ev_hash = _sha(evidence)

    hyp = research / "research_hypotheses.md"
    hyp.write_text("# Research Hypotheses\n\n**RH-001:** Disciplined revision...\n")
    hyp_hash = _sha(hyp)

    manifest_path = builds / "white_paper.compile.yaml"
    manifest_data = {
        "build_id": "authority-test",
        "blueprint": "docs/papers/blueprint_000001.md",
        "blueprint_id": "000001",
        "blueprint_status": "ratified",
        "status": "RC-1",
        "sections": [{"section": "abstract", "required_tags": ["thesis"]}],
        "source_artifacts": [
            {"path": "docs/papers/blueprint_000001.md", "tags": ["blueprint", "thesis"], "status": "ratified", "role": "primary-contract"},
            {"path": "docs/research/experiment_001.md", "tags": ["evidence"], "status": "complete", "role": "evidence"},
            {"path": "docs/research/research_hypotheses.md", "tags": ["hypothesis", "research-program"], "status": "active", "role": "research-program"},
        ],
    }
    manifest_path.write_text(yaml.dump(manifest_data))
    manifest_hash = _sha(manifest_path)

    build_data = {
        "build_id": "authority-test",
        "blueprint": {"path": str(bp), "id": "000001", "status": "ratified", "sha256": bp_hash},
        "manifest_path": "docs/builds/white_paper.compile.yaml",
        "manifest_hash": manifest_hash,
        "source_artifacts": [
            {"path": "docs/papers/blueprint_000001.md", "sha256": bp_hash, "tags": ["blueprint", "thesis"], "status": "ratified", "role": "primary-contract"},
            {"path": "docs/research/experiment_001.md", "sha256": ev_hash, "tags": ["evidence"], "status": "complete", "role": "evidence"},
            {"path": "docs/research/research_hypotheses.md", "sha256": hyp_hash, "tags": ["hypothesis", "research-program"], "status": "active", "role": "research-program"},
        ],
        "outcome": "pass",
        "blueprint_status": "ratified",
        "has_draft_artifacts": False,
    }
    (pub / "build.json").write_text(json.dumps(build_data, indent=2))

    (pub / "coverage.json").write_text(json.dumps({
        "coverage_engine_version": "0.1.0",
        "build_id": "authority-test",
        "outcome": "pass",
        "summary": {"sections_evaluated": 1, "pass": 1, "warn": 0, "fail": 0, "overall_pct": 100},
        "sections": [],
    }, indent=2))

    (pub / "release_recommendation.json").write_text(json.dumps({
        "release_engine_version": "0.1.0",
        "build_id": "authority-test",
        "outcome": "RECOMMEND_RELEASE",
        "recommendation": "All criteria satisfied.",
        "steward_signature": "Joseph Walker",
        "steward_notes": "Verified.",
        "signed_at": "2026-06-26T12:00:00+00:00",
    }, indent=2))

    return root


# ── F09: Constitutional authority guard ──────────────────────────────────────

def test_f09_signed_recommendation_refuses_overwrite(tmp_path):
    """A signed release_recommendation.json must not be silently overwritten."""
    output_dir = tmp_path / "pub"
    output_dir.mkdir()

    signed = {
        "steward_signature": "Joseph Walker",
        "steward_notes": "Signed and ratified.",
        "signed_at": "2026-06-26T00:00:00+00:00",
        "outcome": "RECOMMEND_RELEASE",
    }
    (output_dir / "release_recommendation.json").write_text(json.dumps(signed, indent=2))

    with pytest.raises(ReleaseError, match="already signed"):
        _emit_recommendation(
            build={"build_id": "test"},
            criteria_path=tmp_path / "criteria.yaml",
            build_path=tmp_path / "build.json",
            coverage_path=tmp_path / "coverage.json",
            criteria_results=[],
            outcome="RECOMMEND_RELEASE",
            output_dir=output_dir,
        )


def test_f09_signed_artifact_byte_for_byte_unchanged(tmp_path):
    """After refusal, the signed artifact must be byte-for-byte unchanged."""
    output_dir = tmp_path / "pub"
    output_dir.mkdir()

    signed = {
        "steward_signature": "Joseph Walker",
        "steward_notes": "Ratified.",
        "signed_at": "2026-06-26T00:00:00+00:00",
    }
    signed_text = json.dumps(signed, indent=2)
    out_path = output_dir / "release_recommendation.json"
    out_path.write_text(signed_text)

    try:
        _emit_recommendation(
            build={"build_id": "test"},
            criteria_path=tmp_path / "criteria.yaml",
            build_path=tmp_path / "build.json",
            coverage_path=tmp_path / "coverage.json",
            criteria_results=[],
            outcome="RECOMMEND_RELEASE",
            output_dir=output_dir,
        )
    except ReleaseError:
        pass

    assert out_path.read_text() == signed_text, "Signed artifact was modified despite refusal"


def test_f09_unsigned_recommendation_may_be_regenerated(tmp_path):
    """An unsigned recommendation (steward_signature: null) may be overwritten."""
    output_dir = tmp_path / "pub"
    output_dir.mkdir()

    unsigned = {"steward_signature": None, "steward_notes": None, "signed_at": None}
    (output_dir / "release_recommendation.json").write_text(json.dumps(unsigned, indent=2))

    _emit_recommendation(
        build={"build_id": "regenerated"},
        criteria_path=tmp_path / "criteria.yaml",
        build_path=tmp_path / "build.json",
        coverage_path=tmp_path / "coverage.json",
        criteria_results=[],
        outcome="RECOMMEND_RELEASE",
        output_dir=output_dir,
    )

    result = json.loads((output_dir / "release_recommendation.json").read_text())
    assert result["build_id"] == "regenerated"


def test_f09_missing_recommendation_allows_first_write(tmp_path):
    """If no recommendation file exists, herm release may write one freely."""
    output_dir = tmp_path / "pub"
    output_dir.mkdir()

    _emit_recommendation(
        build={"build_id": "first-write"},
        criteria_path=tmp_path / "criteria.yaml",
        build_path=tmp_path / "build.json",
        coverage_path=tmp_path / "coverage.json",
        criteria_results=[],
        outcome="RECOMMEND_RELEASE",
        output_dir=output_dir,
    )

    result = json.loads((output_dir / "release_recommendation.json").read_text())
    assert result["build_id"] == "first-write"


# ── F03: WITHHOLD must not pass continuation check ───────────────────────────

def test_f03_withhold_outcome_does_not_pass_continuation(tmp_path):
    """WITHHOLD recommendation must not appear as PASS in continuation check."""
    root = _make_publication(tmp_path)
    build, _, _, manifest = _load_inputs(root / "publication" / "build.json", root)

    withhold_release = {
        "outcome": "WITHHOLD",
        "steward_signature": None,
        "steward_notes": None,
        "recommendation": "Required criteria not satisfied.",
    }
    results = _verify_continuation(build, manifest, withhold_release, root)
    rec_check = next(r for r in results if r["name"] == "Release Recommendation")
    assert rec_check["status"] != "PASS", (
        f"WITHHOLD should not produce PASS in continuation; got: {rec_check}"
    )


def test_f03_recommend_release_passes_continuation(tmp_path):
    """RECOMMEND_RELEASE outcome must pass the continuation check."""
    root = _make_publication(tmp_path)
    build, _, release, manifest = _load_inputs(root / "publication" / "build.json", root)
    results = _verify_continuation(build, manifest, release, root)
    rec_check = next(r for r in results if r["name"] == "Release Recommendation")
    assert rec_check["status"] == "PASS", f"Expected PASS, got: {rec_check}"


def test_f03_withhold_note_references_actual_outcome(tmp_path):
    """When WITHHOLD, the continuation note must reference the actual outcome."""
    root = _make_publication(tmp_path)
    build, _, _, manifest = _load_inputs(root / "publication" / "build.json", root)

    withhold_release = {"outcome": "WITHHOLD"}
    results = _verify_continuation(build, manifest, withhold_release, root)
    rec_check = next(r for r in results if r["name"] == "Release Recommendation")
    assert "WITHHOLD" in (rec_check.get("note") or ""), (
        f"Note should mention WITHHOLD: {rec_check}"
    )


# ── F02: build path controls sibling artifact paths ──────────────────────────

def test_f02_build_path_controls_coverage_and_release_paths(tmp_path):
    """coverage.json and release_recommendation.json must resolve from build.json's directory."""
    root = _make_publication(tmp_path)

    # Copy publication to an alternate directory
    alt = tmp_path / "alt_pub"
    shutil.copytree(root / "publication", alt)

    # Corrupt the original publication so a path confusion would be detectable
    (root / "publication" / "coverage.json").write_text(json.dumps({"outcome": "wrong"}))
    (root / "publication" / "release_recommendation.json").write_text(json.dumps({"steward_signature": "WRONG"}))

    build, coverage, release, _ = _load_inputs(alt / "build.json", root)

    assert coverage.get("outcome") == "pass", (
        "coverage.json should be read from build.json's directory, not project_root/publication"
    )
    assert release.get("steward_signature") == "Joseph Walker", (
        "release_recommendation.json should be read from build.json's directory"
    )


# ── F05: export halts on missing artifact ────────────────────────────────────

def test_f05_export_halts_on_missing_artifact(tmp_path):
    """preserve export must halt with PreservationError when a declared artifact is missing."""
    root = _make_publication(tmp_path)
    build, _, _, _ = _load_inputs(root / "publication" / "build.json", root)

    (root / "docs" / "research" / "experiment_001.md").unlink()

    with pytest.raises(PreservationError, match="[Mm]issing"):
        _run_export(build, root, tmp_path / "output", verbose=False)


def test_f05_export_succeeds_with_all_artifacts_present(tmp_path):
    """preserve export must succeed and produce manifest.json when all artifacts are present."""
    root = _make_publication(tmp_path)
    build, _, _, _ = _load_inputs(root / "publication" / "build.json", root)

    _run_export(build, root, tmp_path / "output", verbose=False)

    assert (tmp_path / "output" / "preservation_package" / "manifest.json").exists()
