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

from hermeneia.cli import build_cmd, preserve_cmd
from hermeneia.cli.preserve_cmd import (
    PreservationError,
    _load_inputs,
    _sha256,
    _verify_continuation,
    _verify_reconstruction,
    cmd_preserve_verify,
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

    # The emitted bytes and their provenance are part of a current build.
    manuscript = docs / "hermeneia_white_paper.md"
    manuscript.write_bytes(b"# White paper\n\nDisciplined revision preserves understanding.\n")
    compiled = pub / "white_paper.md"
    compiled.write_bytes(manuscript.read_bytes())

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
        "compile": {"source": str(manuscript), "sha256": _sha256(compiled), "method": "copy"},
        "outputs": {"white_paper": "publication/white_paper.md"},
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


def _recorded_digest(build, target):
    """Locate the existing build-time digest, without inventing a new record."""
    if target == "blueprint":
        return build["blueprint"], "sha256", "Blueprint"
    if target == "manifest":
        return build, "manifest_hash", "Compile Manifest"
    artifact = build["source_artifacts"][1]
    return artifact, "sha256", f"Source: {artifact['path']}"


@pytest.mark.parametrize("target", ["blueprint", "manifest", "source"])
@pytest.mark.parametrize("digest", [None, "", False, 0, [], {}, "bad", "g" * 64])
def test_reconstruction_invalid_build_digest_fails(tmp_path, target, digest):
    root = _make_corpus(tmp_path)
    build, coverage, release, _ = _load_inputs(root / "publication" / "build.json", root)
    record, key, name = _recorded_digest(build, target)
    record[key] = digest

    checks = _verify_reconstruction(build, coverage, release, root)
    check = next(r for r in checks if r["name"] == name)

    assert check["status"] == "FAIL"
    assert "build-time SHA-256" in check["note"]
    assert "sha256" not in check, "Observed bytes must not substitute for missing provenance"


@pytest.mark.parametrize("target", ["blueprint", "manifest", "source"])
def test_verify_missing_digest_cannot_hide_modified_artifact(tmp_path, monkeypatch, target):
    """Deleting a build digest must not turn a tampered artifact into a verified one."""
    root = _make_corpus(tmp_path)
    build_path = root / "publication" / "build.json"
    build = json.loads(build_path.read_text())
    record, key, name = _recorded_digest(build, target)
    del record[key]
    artifact_path = root / (build["manifest_path"] if target == "manifest" else record["path"])
    artifact_path.write_text(artifact_path.read_text() + "\n# Modified after build\n")
    if target == "blueprint":
        # The Blueprint is also listed as a source; remove that comparison too.
        del build["source_artifacts"][0]["sha256"]
    build_path.write_text(json.dumps(build, indent=2))
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    reports = tmp_path / "reports"
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        cmd_preserve_verify(build_path=str(build_path), output_dir=str(reports))

    assert exc.value.code == 1
    report = json.loads((reports / "preservation_report.json").read_text())
    assert report["overall_outcome"] == "fail"
    assert report["reconstruction"]["summary"]["outcome"] == "fail"
    check = next(r for r in report["reconstruction"]["checks"] if r["name"] == name)
    assert check["status"] == "FAIL"
    assert "build-time SHA-256" in check["note"]
    assert "## Overall: FAIL" in (reports / "preservation_report.md").read_text()
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert after == before, "Verification must not repair inputs or alter steward history"


def test_reconstruction_empty_artifact_without_digest_fails(tmp_path):
    root = _make_corpus(tmp_path)
    build, coverage, release, _ = _load_inputs(root / "publication" / "build.json", root)
    artifact, key, name = _recorded_digest(build, "source")
    del artifact[key]
    (root / artifact["path"]).write_bytes(b"")

    checks = _verify_reconstruction(build, coverage, release, root)
    check = next(r for r in checks if r["name"] == name)
    assert check["status"] == "FAIL", "Empty-content warnings require verified provenance first"


def test_verify_matching_digests_preserves_inputs(tmp_path, monkeypatch):
    root = _make_corpus(tmp_path)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    reports = tmp_path / "reports"
    monkeypatch.chdir(root)

    cmd_preserve_verify(output_dir=str(reports))

    report = json.loads((reports / "preservation_report.json").read_text())
    assert report["overall_outcome"] == "pass"
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert after == before


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


def _snapshot_preserved_files(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _compiled_report(reports):
    report = json.loads((reports / "preservation_report.json").read_text())
    check = next(r for r in report["reconstruction"]["checks"] if r["name"] == "Compiled Artifact")
    return report, check


def test_preserve_compiled_artifact_rejects_tampering_after_passing_build(tmp_path, monkeypatch):
    root = _make_corpus(tmp_path)
    monkeypatch.chdir(root)
    build_cmd.cmd_build()
    # Preserve an existing package as well as all build/steward input files.
    preserved = root / "preservation" / "preservation_package"
    preserved.mkdir(parents=True)
    (preserved / "manifest.json").write_bytes(b'{"retained_package":"unchanged"}')
    before = _snapshot_preserved_files(root)
    valid_reports = tmp_path / "valid-reports"
    cmd_preserve_verify(output_dir=str(valid_reports))
    valid_report = json.loads((valid_reports / "preservation_report.json").read_text())
    assert valid_report["overall_outcome"] == "pass"
    assert _snapshot_preserved_files(root) == before

    build_path = root / "publication" / "build.json"
    build_bytes = build_path.read_bytes()
    build = json.loads(build_bytes)
    paper = Path(build["outputs"]["white_paper"])
    original_source = Path(build["compile"]["source"]).read_bytes()
    paper.write_bytes(paper.read_bytes() + b"\n<!-- changed after build -->\n")
    before_verification = _snapshot_preserved_files(root)
    failed_reports = tmp_path / "failed-reports"

    with pytest.raises(SystemExit) as exc:
        cmd_preserve_verify(output_dir=str(failed_reports))

    assert exc.value.code == 1
    report, check = _compiled_report(failed_reports)
    assert report["overall_outcome"] == "fail"
    assert report["continuation"]["summary"]["outcome"] == "pass"
    assert [r["name"] for r in report["reconstruction"]["checks"] if r["status"] == "FAIL"] == ["Compiled Artifact"]
    assert check["hash_at_build"] == build["compile"]["sha256"]
    assert check["hash_now"] == hashlib.sha256(paper.read_bytes()).hexdigest()
    assert check["hash_now"] != check["hash_at_build"]
    assert "## Overall: FAIL" in (failed_reports / "preservation_report.md").read_text()
    assert build_path.read_bytes() == build_bytes
    assert Path(build["compile"]["source"]).read_bytes() == original_source
    assert _snapshot_preserved_files(root) == before_verification


@pytest.mark.parametrize("payload", [b"", b"# Compiled paper\n", b"\xef\xbb\xbfcaf\xc3\xa9\r\n\x00\xff" * 7000], ids=["empty", "text", "binary-multiple-chunks"])
def test_preserve_compiled_artifact_checks_exact_bytes_without_mutation(tmp_path, monkeypatch, payload):
    root = _make_corpus(tmp_path)
    build_path = root / "publication" / "build.json"
    build = json.loads(build_path.read_text())
    paper = root / build["outputs"]["white_paper"]
    paper.write_bytes(payload)
    build["compile"]["sha256"] = hashlib.sha256(payload).hexdigest()
    build_path.write_text(json.dumps(build))
    # Source content is irrelevant to the emitted-byte comparison.
    Path(build["compile"]["source"]).write_bytes(b"Different source; emitted bytes remain intact")
    before = _snapshot_preserved_files(root)
    reports = tmp_path / "reports"
    monkeypatch.chdir(root)

    cmd_preserve_verify(output_dir=str(reports))

    report, check = _compiled_report(reports)
    assert check["status"] == ("PASS" if payload else "WARN")
    assert check["sha256"] == hashlib.sha256(payload).hexdigest()
    assert report["overall_outcome"] == ("pass" if payload else "warn")
    assert _snapshot_preserved_files(root) == before


@pytest.mark.parametrize("digest", ["missing", None, "", False, 0, [], {}, "bad", "g" * 64, "A" * 64, "0" * 63, "0" * 65, "0" * 64 + "\n"])
def test_preserve_compiled_artifact_invalid_digest_fails_closed(tmp_path, monkeypatch, digest):
    root = _make_corpus(tmp_path)
    build_path = root / "publication" / "build.json"
    build = json.loads(build_path.read_text())
    if digest == "missing":
        del build["compile"]["sha256"]
    else:
        build["compile"]["sha256"] = digest
    build_path.write_text(json.dumps(build))
    before = _snapshot_preserved_files(root)
    reports = tmp_path / "reports"
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        cmd_preserve_verify(output_dir=str(reports))

    assert exc.value.code == 1
    report, check = _compiled_report(reports)
    assert report["overall_outcome"] == "fail"
    assert check["status"] == "FAIL"
    assert "build-time SHA-256" in check["note"]
    assert "sha256" not in check, "Present bytes cannot supply missing build-time provenance"
    assert _snapshot_preserved_files(root) == before


@pytest.mark.parametrize("field", ["compile", "outputs"])
@pytest.mark.parametrize("value", ["missing", None, [], "wrong", False])
def test_preserve_compiled_artifact_invalid_provenance_container_fails(tmp_path, monkeypatch, field, value):
    root = _make_corpus(tmp_path)
    build_path = root / "publication" / "build.json"
    build = json.loads(build_path.read_text())
    if value == "missing":
        del build[field]
    else:
        build[field] = value
    build_path.write_text(json.dumps(build))
    before = _snapshot_preserved_files(root)
    reports = tmp_path / "reports"
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        cmd_preserve_verify(output_dir=str(reports))

    assert exc.value.code == 1
    _, check = _compiled_report(reports)
    assert check["status"] == "FAIL"
    assert _snapshot_preserved_files(root) == before


@pytest.mark.parametrize("path_value", ["missing", None, "", [], {}, False, 42])
def test_preserve_compiled_artifact_requires_recorded_output_path(tmp_path, monkeypatch, path_value):
    root = _make_corpus(tmp_path)
    build_path = root / "publication" / "build.json"
    build = json.loads(build_path.read_text())
    if path_value == "missing":
        del build["outputs"]["white_paper"]
    else:
        build["outputs"]["white_paper"] = path_value
    build_path.write_text(json.dumps(build))
    before = _snapshot_preserved_files(root)
    reports = tmp_path / "reports"
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        cmd_preserve_verify(output_dir=str(reports))

    assert exc.value.code == 1
    _, check = _compiled_report(reports)
    assert check["status"] == "FAIL"
    assert "outputs.white_paper" in check["note"]
    assert _snapshot_preserved_files(root) == before


@pytest.mark.parametrize("absolute", [False, True])
def test_preserve_compiled_artifact_uses_declared_output_path(tmp_path, monkeypatch, absolute):
    root = _make_corpus(tmp_path)
    build_path = root / "publication" / "build.json"
    build = json.loads(build_path.read_text())
    conventional = root / "publication" / "white_paper.md"
    declared = root / "custom" / "white_paper.md"
    declared.parent.mkdir()
    declared.write_bytes(conventional.read_bytes())
    conventional.write_bytes(b"Wrong conventional output")
    build["outputs"]["white_paper"] = str(declared if absolute else declared.relative_to(root))
    build_path.write_text(json.dumps(build))
    before = _snapshot_preserved_files(root)
    reports = tmp_path / "reports"
    monkeypatch.chdir(root)

    cmd_preserve_verify(output_dir=str(reports))

    _, check = _compiled_report(reports)
    assert check["status"] == "PASS"
    assert check["path"] == str(declared)
    assert _snapshot_preserved_files(root) == before


@pytest.mark.parametrize("failure", ["missing", "directory", "unreadable"])
def test_preserve_compiled_artifact_unavailable_fails_with_report(tmp_path, monkeypatch, failure):
    root = _make_corpus(tmp_path)
    paper = root / "publication" / "white_paper.md"
    if failure in {"missing", "directory"}:
        paper.unlink()
    if failure == "directory":
        paper.mkdir()
    before = _snapshot_preserved_files(root)
    reports = tmp_path / "reports"
    real_hash = preserve_cmd._sha256

    def fail_paper_hash(path):
        if path == paper:
            raise PermissionError("injected compiled artifact read failure")
        return real_hash(path)

    if failure == "unreadable":
        monkeypatch.setattr(preserve_cmd, "_sha256", fail_paper_hash)
    monkeypatch.chdir(root)
    with pytest.raises(SystemExit) as exc:
        cmd_preserve_verify(output_dir=str(reports))

    assert exc.value.code == 1
    report, check = _compiled_report(reports)
    assert report["overall_outcome"] == "fail"
    assert check["status"] == "FAIL"
    assert check.get("note")
    assert _snapshot_preserved_files(root) == before
