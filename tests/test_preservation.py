"""
Tests for herm preserve — Sprint 005

All tests are deterministic. No LLM calls. No database required.
Tests cover:
  - complete publication (verify passes)
  - missing build.json
  - missing Blueprint
  - hash mismatch (artifact modified since build)
  - missing continuation prerequisite (no research hypotheses)
  - unsigned release recommendation (advisory)
  - draft publication (advisory from release, continuation still possible)
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
    _sha256,
    _verify_continuation,
    _verify_reconstruction,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _make_corpus(tmp: Path) -> Path:
    """Create a minimal valid corpus for preservation tests."""
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

    # Blueprint
    bp = docs / "blueprint_000001.md"
    bp.write_text(
        "# Blueprint 000001\n\n"
        "**Governing question:** How does understanding evolve?\n"
        "**Intent hypothesis:** Disciplined revision is the primitive operation.\n"
    )
    bp_hash = _sha256(bp)

    # Source artifact (evidence)
    evidence = research / "experiment_001.md"
    evidence.write_text("# Experiment 001\n\nObservations from calibration run.\n")
    ev_hash = _sha256(evidence)

    # Research hypotheses artifact
    hyp = research / "research_hypotheses.md"
    hyp.write_text("# Research Hypotheses\n\n**RH-001:** Disciplined revision...\n")
    hyp_hash = _sha256(hyp)

    # Compile manifest
    manifest_path = builds / "white_paper.compile.yaml"
    manifest_data = {
        "build_id": "white-paper-test",
        "compiled_artifact": "docs/papers/hermeneia_white_paper.md",
        "blueprint": "docs/papers/blueprint_000001.md",
        "blueprint_id": "000001",
        "blueprint_status": "ratified",
        "status": "RC-1",
        "ratification": "pending",
        "source_artifacts": [
            {
                "path": "docs/papers/blueprint_000001.md",
                "tags": ["blueprint", "thesis"],
                "status": "ratified",
                "role": "primary-contract",
            },
            {
                "path": "docs/research/experiment_001.md",
                "tags": ["calibration", "evidence"],
                "status": "complete",
                "role": "evidence",
            },
            {
                "path": "docs/research/research_hypotheses.md",
                "tags": ["hypothesis", "research-program"],
                "status": "active",
                "role": "research-program",
            },
        ],
        "sections": [
            {
                "section": "abstract",
                "required_tags": ["thesis"],
                "required_claims": ["Understanding evolves through disciplined revision"],
            }
        ],
    }
    manifest_path.write_text(yaml.dump(manifest_data))
    manifest_hash = _sha256(manifest_path)

    # build.json
    build_data = {
        "build_id": "white-paper-test",
        "build_timestamp": "2026-06-26T00:00:00+00:00",
        "hermeneia_version": "0.1.0",
        "blueprint": {
            "path": str(bp),
            "id": "000001",
            "status": "ratified",
            "sha256": bp_hash,
        },
        "manifest_path": "docs/builds/white_paper.compile.yaml",
        "manifest_hash": manifest_hash,
        "source_artifacts": [
            {
                "path": "docs/papers/blueprint_000001.md",
                "sha256": bp_hash,
                "tags": ["blueprint", "thesis"],
                "status": "ratified",
                "role": "primary-contract",
            },
            {
                "path": "docs/research/experiment_001.md",
                "sha256": ev_hash,
                "tags": ["calibration", "evidence"],
                "status": "complete",
                "role": "evidence",
            },
            {
                "path": "docs/research/research_hypotheses.md",
                "sha256": hyp_hash,
                "tags": ["hypothesis", "research-program"],
                "status": "active",
                "role": "research-program",
            },
        ],
        "outcome": "pass",
        "blueprint_status": "ratified",
        "has_draft_artifacts": False,
    }
    build_json = pub / "build.json"
    build_json.write_text(json.dumps(build_data, indent=2))

    # coverage.json
    coverage_data = {
        "coverage_engine_version": "0.1.0",
        "build_id": "white-paper-test",
        "outcome": "pass",
        "summary": {"sections_evaluated": 1, "pass": 1, "warn": 0, "fail": 0, "overall_pct": 100},
        "sections": [],
    }
    (pub / "coverage.json").write_text(json.dumps(coverage_data, indent=2))

    # release_recommendation.json (signed)
    release_data = {
        "release_engine_version": "0.1.0",
        "build_id": "white-paper-test",
        "outcome": "RECOMMEND_RELEASE",
        "recommendation": "All criteria satisfied.",
        "steward_signature": "Joseph Walker",
        "steward_notes": "Verified experimentally.",
        "signed_at": "2026-06-26T12:00:00+00:00",
    }
    (pub / "release_recommendation.json").write_text(json.dumps(release_data, indent=2))

    return root


# ── Tests: Reconstruction ─────────────────────────────────────────────────────

def test_reconstruction_complete_pass(tmp_path):
    root = _make_corpus(tmp_path)
    build, _, release, _ = _load_inputs(root / "publication" / "build.json", root)
    results = _verify_reconstruction(build, {}, release, root)
    failures = [r for r in results if r["status"] == "FAIL"]
    assert not failures, f"Expected no FAIL: {failures}"
    passes = [r for r in results if r["status"] == "PASS"]
    assert len(passes) >= 4  # blueprint, manifest, 3 sources, pipeline outputs


def test_reconstruction_missing_blueprint(tmp_path):
    root = _make_corpus(tmp_path)
    (root / "docs" / "papers" / "blueprint_000001.md").unlink()
    build, _, release, _ = _load_inputs(root / "publication" / "build.json", root)
    results = _verify_reconstruction(build, {}, release, root)
    blueprint_check = next(r for r in results if r["name"] == "Blueprint")
    assert blueprint_check["status"] == "FAIL"


def test_reconstruction_hash_mismatch(tmp_path):
    root = _make_corpus(tmp_path)
    # Silently modify the evidence artifact after build
    ev = root / "docs" / "research" / "experiment_001.md"
    ev.write_text(ev.read_text() + "\n\n<!-- tampered -->")
    build, _, release, _ = _load_inputs(root / "publication" / "build.json", root)
    results = _verify_reconstruction(build, {}, release, root)
    mismatch = [r for r in results if r["status"] == "FAIL" and "mismatch" in r.get("note", "")]
    assert len(mismatch) == 1
    assert "experiment_001.md" in mismatch[0]["name"]


def test_reconstruction_unsigned_release_is_advisory(tmp_path):
    root = _make_corpus(tmp_path)
    rel_path = root / "publication" / "release_recommendation.json"
    data = json.loads(rel_path.read_text())
    data["steward_signature"] = None
    data["signed_at"] = None
    rel_path.write_text(json.dumps(data))
    build, _, release, _ = _load_inputs(root / "publication" / "build.json", root)
    results = _verify_reconstruction(build, {}, release, root)
    sig_check = next(r for r in results if r["name"] == "Steward Signature")
    assert sig_check["status"] == "ADVISORY"


# ── Tests: Continuation ────────────────────────────────────────────────────────

def test_continuation_complete_pass(tmp_path):
    root = _make_corpus(tmp_path)
    build, _, release, manifest = _load_inputs(root / "publication" / "build.json", root)
    results = _verify_continuation(build, manifest, release, root)
    failures = [r for r in results if r["status"] == "FAIL"]
    assert not failures, f"Expected no FAIL: {failures}"


def test_continuation_missing_hypothesis_artifacts(tmp_path):
    root = _make_corpus(tmp_path)
    build_path = root / "publication" / "build.json"
    data = json.loads(build_path.read_text())
    # Remove hypothesis-tagged artifacts
    data["source_artifacts"] = [
        a for a in data["source_artifacts"]
        if "hypothesis" not in a.get("tags", []) and "research-program" not in a.get("tags", [])
    ]
    build_path.write_text(json.dumps(data))
    build, _, release, manifest = _load_inputs(build_path, root)
    results = _verify_continuation(build, manifest, release, root)
    hyp_check = next(r for r in results if r["name"] == "Research Hypotheses")
    assert hyp_check["status"] == "WARN"


def test_continuation_missing_blueprint_ratification(tmp_path):
    root = _make_corpus(tmp_path)
    build_path = root / "publication" / "build.json"
    data = json.loads(build_path.read_text())
    data["blueprint_status"] = "draft"
    build_path.write_text(json.dumps(data))
    build, _, release, manifest = _load_inputs(build_path, root)
    results = _verify_continuation(build, manifest, release, root)
    rat_check = next(r for r in results if r["name"] == "Blueprint Ratification")
    assert rat_check["status"] == "WARN"


def test_continuation_steward_notes_advisory(tmp_path):
    root = _make_corpus(tmp_path)
    rel_path = root / "publication" / "release_recommendation.json"
    data = json.loads(rel_path.read_text())
    data["steward_notes"] = None
    rel_path.write_text(json.dumps(data))
    build, _, release, manifest = _load_inputs(root / "publication" / "build.json", root)
    results = _verify_continuation(build, manifest, release, root)
    notes_check = next(r for r in results if r["name"] == "Steward Notes")
    assert notes_check["status"] == "ADVISORY"


# ── Tests: Failure conditions ─────────────────────────────────────────────────

def test_load_inputs_missing_build_json(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(PreservationError, match="build.json not found"):
        _load_inputs(root / "publication" / "build.json", root)


def test_load_inputs_malformed_build_json(tmp_path):
    root = tmp_path / "bad"
    pub = root / "publication"
    pub.mkdir(parents=True)
    (pub / "build.json").write_text("not json {{{{")
    with pytest.raises(PreservationError, match="malformed"):
        _load_inputs(pub / "build.json", root)
