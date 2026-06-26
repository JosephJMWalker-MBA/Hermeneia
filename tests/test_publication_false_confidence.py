"""
False-confidence tests for the publication infrastructure.

Encodes the invariant:
    The system must not claim more confidence than its evidence,
    coverage, provenance, or verification state supports.

VS-004 — F01 (stale coverage), F02 (coverage corpus mismatch), F04 (empty artifact)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from hermeneia.cli.preserve_cmd import _verify_reconstruction


_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _make_root(tmp: Path, build_id: str = "test-build") -> tuple[Path, dict, Path]:
    root = tmp / "project"
    root.mkdir()
    bp = root / "bp.md"
    bp.write_text("Blueprint\n**Governing question:** Q?\n**Intent hypothesis:** H.")
    manifest = root / "manifest.yaml"
    manifest.write_text(yaml.dump({"sections": [], "source_artifacts": []}))
    build = {
        "build_id": build_id,
        "blueprint": {"path": str(bp), "sha256": _sha(bp), "status": "ratified"},
        "manifest_path": "manifest.yaml",
        "manifest_hash": _sha(manifest),
        "source_artifacts": [],
        "outcome": "pass",
        "blueprint_status": "ratified",
        "has_draft_artifacts": False,
    }
    return root, build, bp


# ── F01: Stale coverage (build_id mismatch) ──────────────────────────────────

def test_f01_stale_coverage_build_id_produces_warn(tmp_path):
    """coverage.json from a different build must produce Coverage Build ID WARN."""
    root, build_v2, _ = _make_root(tmp_path, build_id="wp-v2")
    stale_coverage = {
        "build_id": "wp-v1",   # different build
        "outcome": "pass",
        "summary": {"sections_evaluated": 1, "pass": 1, "warn": 0, "fail": 0},
    }
    release = {"steward_signature": None}

    recon = _verify_reconstruction(build_v2, stale_coverage, release, root)
    check = next((r for r in recon if r["name"] == "Coverage Build ID"), None)

    assert check is not None, "Coverage Build ID check missing from reconstruction results"
    assert check["status"] == "WARN", (
        f"Expected WARN for stale build_id, got {check['status']}: {check.get('note')}"
    )
    assert "wp-v1" in check["note"] and "wp-v2" in check["note"]


def test_f01_matching_coverage_build_id_no_warn(tmp_path):
    """coverage.json from the same build must not produce Coverage Build ID WARN."""
    root, build, _ = _make_root(tmp_path, build_id="wp-v1")
    fresh_coverage = {
        "build_id": "wp-v1",  # same build
        "outcome": "pass",
        "summary": {"sections_evaluated": 1, "pass": 1, "warn": 0, "fail": 0},
    }
    release = {"steward_signature": None}

    recon = _verify_reconstruction(build, fresh_coverage, release, root)
    build_id_checks = [r for r in recon if r["name"] == "Coverage Build ID"]
    assert not build_id_checks, (
        "Matching build_id should not produce Coverage Build ID check"
    )


def test_f01_no_coverage_build_id_no_spurious_warn(tmp_path):
    """coverage.json without a build_id field must not produce a spurious WARN."""
    root, build, _ = _make_root(tmp_path, build_id="wp-v1")
    coverage_no_id = {"outcome": "pass", "summary": {"sections_evaluated": 0, "pass": 0, "warn": 0, "fail": 0}}
    release = {"steward_signature": None}

    recon = _verify_reconstruction(build, coverage_no_id, release, root)
    build_id_checks = [r for r in recon if r["name"] == "Coverage Build ID"]
    assert not build_id_checks, "Missing coverage build_id should not produce WARN"


# ── F02: Coverage corpus integrity ────────────────────────────────────────────

def test_f02_coverage_attests_ghost_artifact_produces_warn(tmp_path):
    """coverage.json attesting to a path not in build must produce Coverage Corpus Integrity WARN."""
    root, build, _ = _make_root(tmp_path)
    coverage_ghost = {
        "build_id": "test-build",
        "outcome": "pass",
        "summary": {"fail": 0},
        "tag_index": {
            "evidence": ["ghost_artifact.md"],  # not in build's source_artifacts
        },
    }
    release = {"steward_signature": None}

    recon = _verify_reconstruction(build, coverage_ghost, release, root)
    check = next((r for r in recon if r["name"] == "Coverage Corpus Integrity"), None)

    assert check is not None, "Coverage Corpus Integrity check missing"
    assert check["status"] == "WARN"
    assert "ghost_artifact.md" in check["note"]


def test_f02_coverage_attests_only_build_artifacts_no_warn(tmp_path):
    """coverage.json attesting only to declared build artifacts must not warn."""
    root, build, bp = _make_root(tmp_path)
    art = root / "evidence.md"
    art.write_text("Evidence")
    build["source_artifacts"] = [
        {"path": "evidence.md", "sha256": _sha(art), "tags": ["evidence"], "status": "active", "role": "evidence"}
    ]
    coverage_clean = {
        "build_id": "test-build",
        "outcome": "pass",
        "summary": {"fail": 0},
        "tag_index": {
            "evidence": ["evidence.md"],  # matches build artifact
        },
    }
    release = {"steward_signature": None}

    recon = _verify_reconstruction(build, coverage_clean, release, root)
    corpus_checks = [r for r in recon if r["name"] == "Coverage Corpus Integrity"]
    assert not corpus_checks, "Clean corpus coverage should not produce corpus integrity check"


def test_f02_empty_tag_index_no_spurious_warn(tmp_path):
    """coverage.json with no tag_index must not produce a spurious WARN."""
    root, build, _ = _make_root(tmp_path)
    coverage_no_index = {"build_id": "test-build", "outcome": "pass", "summary": {"fail": 0}}
    release = {"steward_signature": None}

    recon = _verify_reconstruction(build, coverage_no_index, release, root)
    corpus_checks = [r for r in recon if r["name"] == "Coverage Corpus Integrity"]
    assert not corpus_checks, "Missing tag_index should not produce corpus integrity WARN"


# ── F04: Empty artifact ───────────────────────────────────────────────────────

def test_f04_empty_artifact_produces_warn(tmp_path):
    """A 0-byte source artifact must produce WARN in reconstruction, not PASS."""
    root, build, _ = _make_root(tmp_path)
    empty_art = root / "empty_evidence.md"
    empty_art.write_text("")

    build["source_artifacts"] = [
        {"path": "empty_evidence.md", "sha256": _sha(empty_art), "tags": ["evidence"],
         "status": "active", "role": "evidence"}
    ]
    release = {"steward_signature": None}

    recon = _verify_reconstruction(build, {}, release, root)
    art_check = next((r for r in recon if "empty_evidence.md" in r.get("name", "")), None)

    assert art_check is not None, "empty_evidence.md not checked in reconstruction"
    assert art_check["status"] == "WARN", (
        f"Expected WARN for empty artifact, got {art_check['status']}"
    )
    assert "empty" in art_check.get("note", "").lower() or "0 bytes" in art_check.get("note", "").lower()


def test_f04_nonempty_artifact_passes(tmp_path):
    """A non-empty source artifact must produce PASS in reconstruction (regression guard)."""
    root, build, _ = _make_root(tmp_path)
    art = root / "evidence.md"
    art.write_text("Actual evidence content")

    build["source_artifacts"] = [
        {"path": "evidence.md", "sha256": _sha(art), "tags": ["evidence"],
         "status": "active", "role": "evidence"}
    ]
    release = {"steward_signature": None}

    recon = _verify_reconstruction(build, {}, release, root)
    art_check = next((r for r in recon if "evidence.md" in r.get("name", "")), None)

    assert art_check is not None
    assert art_check["status"] == "PASS", (
        f"Non-empty artifact should PASS, got {art_check['status']}: {art_check.get('note')}"
    )
