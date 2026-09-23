"""Preservation reports identify the bytes evaluated, never a transferable label."""
import hashlib
import json
import os
from contextlib import contextmanager

import pytest

from hermeneia.cli import preserve_cmd as preserve
from hermeneia.preservation_provenance import VerificationInputs, verify_report_binding
from test_build_reproducibility import _build, _snapshot
from test_publication_reproducibility import COVERAGE, RELEASE


def _ready(root, monkeypatch, **kwargs):
    path = _build(root, monkeypatch, **kwargs)
    (path.parent / "coverage.json").write_bytes(COVERAGE)
    (path.parent / "release_recommendation.json").write_bytes(RELEASE)
    return path


def _report(root, reports, monkeypatch, *, build_path=None):
    with monkeypatch.context() as patch:
        patch.chdir(root)
        try:
            preserve.cmd_preserve_verify(build_path=str(build_path) if build_path else None,
                                        output_dir=str(reports))
        except SystemExit as exc:
            assert exc.code == 1
    return json.loads((reports / "preservation_report.json").read_bytes())


def test_valid_report_identifies_validated_core_and_exact_build_bytes(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _ready(root, monkeypatch)
    binding = json.loads(path.with_name("build.reproducibility.json").read_bytes())
    before = _snapshot(root)
    report = _report(root, tmp_path / "reports", monkeypatch)
    provenance = report["provenance"]
    assert provenance["integrity"] == "valid"
    assert provenance["build_core"] == {
        "profile": binding["core"]["schema"],
        "sha256": binding["envelope"]["core_sha256"],
    }
    entry = next(item for item in provenance["inputs"] if "build-record" in item["roles"])
    assert entry["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["overall_outcome"] == "pass"
    assert _snapshot(root) == before


def test_stale_core_cannot_claim_provenance_even_when_old_checks_pass(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _ready(root, monkeypatch)
    binding_path = path.with_name("build.reproducibility.json")
    binding = json.loads(binding_path.read_bytes())
    binding["envelope"]["core_sha256"] = "f" * 64
    binding_path.write_text(json.dumps(binding))
    report = _report(root, tmp_path / "reports", monkeypatch)
    assert report["overall_outcome"] == "pass"  # Historical check contract is unchanged.
    assert report["provenance"]["integrity"] == "invalid"
    assert "build_core" not in report["provenance"]


def test_report_destination_hardlink_cannot_mutate_evaluated_build(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _ready(root, monkeypatch)
    original = path.read_bytes()
    reports = tmp_path / "reports"
    reports.mkdir()
    os.link(path, reports / "preservation_report.json")
    report = _report(root, reports, monkeypatch)
    assert path.read_bytes() == original
    assert report["provenance"]["integrity"] == "valid"


def test_manifest_interpretation_and_hash_use_one_capture_and_drift_refuses_claim(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _ready(root, monkeypatch)
    manifest = root / "docs/builds/white_paper.compile.yaml"
    original = manifest.read_bytes()
    real_verify = preserve._verify_reconstruction

    def mutate_after_parse(*args, **kwargs):
        manifest.write_bytes(original + b"\n# changed after interpretation\n")
        return real_verify(*args, **kwargs)

    monkeypatch.setattr(preserve, "_verify_reconstruction", mutate_after_parse)
    report = _report(root, tmp_path / "reports", monkeypatch)
    check = next(item for item in report["reconstruction"]["checks"] if item["name"] == "Compile Manifest")
    assert check["status"] == "PASS", "Hashing reread bytes different from the parsed manifest"
    assert check["sha256"] == hashlib.sha256(original).hexdigest()
    assert report["provenance"]["integrity"] == "invalid"
    assert "build_core" not in report["provenance"]


@pytest.mark.parametrize("artifact", ["build", "coverage", "blueprint", "missing-coverage"])
def test_capture_mutation_keeps_original_observations_and_refuses_provenance(tmp_path, monkeypatch, artifact):
    root = tmp_path / "project"
    path = _ready(root, monkeypatch)
    target = {"build": path, "coverage": path.parent / "coverage.json",
              "blueprint": root / "docs/blueprint.md",
              "missing-coverage": path.parent / "coverage.json"}[artifact]
    original = target.read_bytes()
    if artifact == "missing-coverage":
        target.unlink()
    hook = "_verify_continuation" if artifact == "blueprint" else "_verify_reconstruction"
    real = getattr(preserve, hook)

    def mutate(*args, **kwargs):
        target.write_bytes(original if artifact == "missing-coverage" else
                           b"# No governing purpose\n" if artifact == "blueprint" else original + b"\n")
        return real(*args, **kwargs)

    monkeypatch.setattr(preserve, hook, mutate)
    report = _report(root, tmp_path / "reports", monkeypatch)
    receipt = next(item for item in report["provenance"]["inputs"] if item["path"] == str(target))
    if artifact == "missing-coverage":
        assert receipt["state"] == "missing" and "sha256" not in receipt
        check = next(item for item in report["reconstruction"]["checks"] if item["name"] == "Coverage Record")
        assert check["status"] == "FAIL"
    else:
        assert receipt["sha256"] == hashlib.sha256(original).hexdigest()
        assert report["overall_outcome"] == "pass"
    assert report["provenance"]["integrity"] == "invalid"
    assert "build_core" not in report["provenance"]


@pytest.mark.parametrize("initially_invalid", [False, True])
def test_binding_changes_after_capture_are_never_adopted(tmp_path, monkeypatch, initially_invalid):
    root = tmp_path / "project"
    path = _ready(root, monkeypatch)
    binding_path = path.with_name("build.reproducibility.json")
    valid = binding_path.read_bytes()
    if initially_invalid:
        binding_path.write_bytes(b"{malformed")
    real = VerificationInputs.read

    def mutate(self, value, *args, **kwargs):
        raw = real(self, value, *args, **kwargs)
        if value == binding_path:
            binding_path.write_bytes(valid if initially_invalid else b"{malformed")
        return raw

    monkeypatch.setattr(VerificationInputs, "read", mutate)
    report = _report(root, tmp_path / "reports", monkeypatch)
    assert report["provenance"]["integrity"] == "invalid"
    assert "build_core" not in report["provenance"]


def test_custom_build_records_both_interpreted_and_conventional_pipeline_inputs(tmp_path, monkeypatch):
    from hermeneia.cli import build_cmd
    root = tmp_path / "project"
    _ready(root, monkeypatch)
    custom = root / "custom"
    with monkeypatch.context() as patch:
        patch.chdir(root)
        build_cmd.cmd_build(output_dir=str(custom))
    custom_coverage = COVERAGE + b"\n"
    (custom / "coverage.json").write_bytes(custom_coverage)
    (custom / "release_recommendation.json").write_bytes(RELEASE + b"\n")
    report = _report(root, tmp_path / "reports", monkeypatch, build_path=custom / "build.json")
    assert report["provenance"]["integrity"] == "valid"
    receipts = {item["path"]: item for item in report["provenance"]["inputs"]}
    for name, role in [("coverage.json", "coverage-interpretation"),
                       ("release_recommendation.json", "release-interpretation")]:
        assert role in receipts[str(custom / name)]["roles"]
        assert receipts[str(custom / name)]["sha256"] != receipts[str(root / "publication" / name)]["sha256"]
    assert "reconstruction:Coverage Record" in receipts[str(root / "publication/coverage.json")]["roles"]


def test_association_rechecks_inputs_after_comparing_findings(tmp_path, monkeypatch):
    from hermeneia import preservation_provenance as provenance
    root = tmp_path / "project"
    path = _ready(root, monkeypatch)
    reports = tmp_path / "reports"
    _report(root, reports, monkeypatch)
    real = provenance._same_observation

    def mutate(*args):
        coverage = path.parent / "coverage.json"
        coverage.write_bytes(COVERAGE + b"\n")
        return real(*args)

    monkeypatch.setattr(provenance, "_same_observation", mutate)
    result = verify_report_binding(reports / "preservation_report.json", path, project_root=root)
    assert result["integrity"] == "invalid"


def test_report_parent_redirection_cannot_overwrite_an_input(tmp_path, monkeypatch):
    root = tmp_path / "project"

    def custom_source(root):
        (root / "docs/preservation_report.json").write_bytes((root / "docs/paper.md").read_bytes())
        manifest = root / "docs/builds/white_paper.compile.yaml"
        manifest.write_bytes(manifest.read_bytes().replace(b"compiled_artifact: docs/paper.md",
                                                          b"compiled_artifact: docs/preservation_report.json"))

    _ready(root, monkeypatch, mutate=custom_source)
    source = root / "docs/preservation_report.json"
    original = source.read_bytes()
    safe = tmp_path / "safe"
    safe.mkdir()
    reports = tmp_path / "reports"
    reports.symlink_to(safe, target_is_directory=True)
    real = preserve._write_report
    redirected = False

    def redirect(*args, **kwargs):
        nonlocal redirected
        if not redirected:
            reports.unlink()
            reports.symlink_to(root / "docs", target_is_directory=True)
            redirected = True
        return real(*args, **kwargs)

    monkeypatch.setattr(preserve, "_write_report", redirect)
    monkeypatch.chdir(root)
    preserve.cmd_preserve_verify(output_dir=str(reports))
    assert source.read_bytes() == original
    assert json.loads((safe / "preservation_report.json").read_bytes())["provenance"]["integrity"] == "valid"


def test_input_directory_redirection_after_pin_cannot_bypass_alias_refusal(tmp_path, monkeypatch):
    root = tmp_path / "project"

    def custom_source(root):
        (root / "docs/preservation_report.json").write_bytes((root / "docs/paper.md").read_bytes())
        manifest = root / "docs/builds/white_paper.compile.yaml"
        manifest.write_bytes(manifest.read_bytes().replace(b"compiled_artifact: docs/paper.md",
                                                          b"compiled_artifact: docs/preservation_report.json"))

    _ready(root, monkeypatch, mutate=custom_source)
    original = (root / "docs/preservation_report.json").read_bytes()
    moved = root / "moved-docs"
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    real = preserve._report_directory

    @contextmanager
    def redirect(path):
        with real(path) as destination:
            path.rename(moved)
            path.symlink_to(replacement, target_is_directory=True)
            yield destination

    monkeypatch.setattr(preserve, "_report_directory", redirect)
    monkeypatch.chdir(root)
    with pytest.raises(SystemExit) as exc:
        preserve.cmd_preserve_verify(output_dir=str(root / "docs"))
    assert exc.value.code == 1
    assert (moved / "preservation_report.json").read_bytes() == original
