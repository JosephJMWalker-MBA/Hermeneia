"""Corrected sibling association does not reinterpret historical report evidence."""
from copy import deepcopy
import hashlib
import json

import pytest

from hermeneia.build_core import canonical_json
from hermeneia.cli import preserve_cmd as preserve
from hermeneia.preservation_provenance import verify_report_binding
from test_build_reproducibility import _snapshot
from test_custom_build_path_divergence import FIXTURES, _prepare
from test_preservation_provenance import _ready, _report


LEGACY_SCHEMA = "hermeneia.preservation-verification-inputs/v1"
CURRENT_SCHEMA = "hermeneia.preservation-verification-inputs/v2"
LEGACY_REPORT_SHA256 = "4b99379a8f92cf6bf27c9821f8b325cc2b1f66aaae9f0c7800dd97092ecc3b56"


def _receipt_digest(provenance, version):
    domain = f"Hermeneia preservation verification inputs v{version}\n".encode("ascii")
    provenance["inputs_sha256"] = hashlib.sha256(domain + canonical_json(provenance["inputs"])).hexdigest()


def _synthetic_legacy(report):
    """Test encoding only: this is not an archived report or historical migration."""
    result = deepcopy(report)
    result["provenance"]["schema"] = LEGACY_SCHEMA
    _receipt_digest(result["provenance"], 1)
    return result


def _associate_read_only(report_path, build_path, root, snapshot_root):
    before = _snapshot(snapshot_root)
    result = verify_report_binding(report_path, build_path, project_root=root)
    assert _snapshot(snapshot_root) == before
    return result


def test_exact_archived_mixed_report_refuses_association_before_current_evaluation(tmp_path, monkeypatch):
    # Emitted by unmodified 2fdfde6, copied byte-for-byte; all original absolute
    # paths, findings, timestamps, and provenance remain historical evidence.
    historical = FIXTURES / "legacy-mixed-report.json"
    original, original_mtime = historical.read_bytes(), historical.stat().st_mtime_ns
    assert hashlib.sha256(original).hexdigest() == LEGACY_REPORT_SHA256
    report = json.loads(original)
    assert report["provenance"]["schema"] == LEGACY_SCHEMA
    assert report["overall_outcome"] == "warn"

    def no_current_evaluation(*args, **kwargs):
        pytest.fail("Historical mixed association must be refused without reinterpretation")

    monkeypatch.setattr(preserve, "_evaluate_verification", no_current_evaluation)
    result = verify_report_binding(historical, tmp_path / "no-build.json", project_root=tmp_path)
    assert result["integrity"] == "unsupported"
    assert result["compatibility"] == "legacy-unsupported-association"
    assert "build_core" not in result and "findings_outcome" not in result
    assert historical.read_bytes() == original
    assert historical.stat().st_mtime_ns == original_mtime
    assert json.loads(historical.read_bytes())["overall_outcome"] == "warn"


def test_synthetic_unmixed_v1_encoding_preserves_exact_read_only_association(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build = _ready(root, monkeypatch)
    current = _report(root, tmp_path / "reports", monkeypatch)
    synthetic = _synthetic_legacy(current)
    legacy_path = tmp_path / "synthetic-unmixed-v1.json"
    legacy_path.write_bytes(canonical_json(synthetic))
    result = _associate_read_only(legacy_path, build, root, tmp_path)
    assert result["integrity"] == "valid", result
    assert result["build_core"] == synthetic["provenance"]["build_core"]
    assert result["findings_outcome"] == synthetic["overall_outcome"] == "pass"


@pytest.mark.parametrize("mutation", ["duplicate-role", "missing-role", "null-resolved-path"])
def test_ambiguous_legacy_association_is_unsupported_without_reinterpretation(tmp_path, monkeypatch, mutation):
    root = tmp_path / "project"
    build = _ready(root, monkeypatch)
    synthetic = _synthetic_legacy(_report(root, tmp_path / "reports", monkeypatch))
    provenance = synthetic["provenance"]
    coverage = next(entry for entry in provenance["inputs"] if "coverage-interpretation" in entry["roles"])
    if mutation == "duplicate-role":
        provenance["inputs"].append(deepcopy(coverage))
    elif mutation == "missing-role":
        coverage["roles"].remove("coverage-interpretation")
    else:
        coverage["resolved_path"] = None
    _receipt_digest(provenance, 1)
    legacy_path = tmp_path / "synthetic-incomplete-v1.json"
    legacy_path.write_bytes(canonical_json(synthetic))

    def no_current_evaluation(*args, **kwargs):
        pytest.fail("Incomplete historical evidence must not be filled from current files")

    monkeypatch.setattr(preserve, "_evaluate_verification", no_current_evaluation)
    result = _associate_read_only(legacy_path, build, root, tmp_path)
    assert result["integrity"] == "unsupported"
    assert result["compatibility"] == "legacy-unsupported-association"
    assert "build_core" not in result and "findings_outcome" not in result


@pytest.mark.parametrize("mutation", ["mixed-namespace", "changed-core"])
def test_current_receipt_cannot_acquire_mixed_or_tampered_association(tmp_path, monkeypatch, mutation):
    root = tmp_path / "project"
    build = _ready(root, monkeypatch)
    report = _report(root, tmp_path / "reports", monkeypatch)
    provenance = report["provenance"]
    assert provenance["schema"] == CURRENT_SCHEMA
    if mutation == "mixed-namespace":
        coverage = next(entry for entry in provenance["inputs"] if "coverage-interpretation" in entry["roles"])
        coverage["roles"].remove("reconstruction:Coverage Record")
        other = deepcopy(coverage)
        other["roles"] = ["reconstruction:Coverage Record"]
        other["path"] = other["resolved_path"] = str(root / "other/coverage.json")
        provenance["inputs"].append(other)
        provenance["inputs"].sort(key=lambda entry: entry["path"])
        _receipt_digest(provenance, 2)
    else:
        provenance["build_core"]["sha256"] = "f" * 64
    tampered_path = tmp_path / "tampered-v2.json"
    tampered_path.write_bytes(canonical_json(report))
    result = _associate_read_only(tampered_path, build, root, tmp_path)
    assert result["integrity"] == "invalid", result
    assert "findings_outcome" not in result


@pytest.mark.parametrize("name", [
    "build.json", "build.reproducibility.json", "coverage.json", "release_recommendation.json",
])
def test_custom_namespace_rejects_cross_parent_leaf_symlinks_without_report(tmp_path, monkeypatch, name):
    root = tmp_path / "project"
    build = _prepare(root, monkeypatch, adjacent="conventional", conventional="conventional")
    selected, other = build.parent / name, root / "publication" / name
    other.write_bytes(selected.read_bytes())
    selected.unlink()
    selected.symlink_to(other)
    before = _snapshot(root)
    reports = tmp_path / "reports"
    with monkeypatch.context() as patch:
        patch.chdir(root)
        with pytest.raises(SystemExit) as exc:
            preserve.cmd_preserve_verify(build_path=str(build), output_dir=str(reports))
    assert exc.value.code == 1
    assert _snapshot(root) == before
    assert not (reports / "preservation_report.json").exists()
    assert not (reports / "preservation_report.md").exists()


def test_conventional_default_uses_corrected_receipt_without_changing_findings(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build = _ready(root, monkeypatch)
    before = _snapshot(root)
    reports = tmp_path / "reports"
    report = _report(root, reports, monkeypatch)
    assert _snapshot(root) == before
    assert report["overall_outcome"] == "pass"
    provenance = report["provenance"]
    assert provenance["schema"] == CURRENT_SCHEMA
    assert provenance["integrity"] == "valid"
    for name, role, label in [
        ("coverage.json", "coverage-interpretation", "Coverage Record"),
        ("release_recommendation.json", "release-interpretation", "Release Recommendation"),
    ]:
        receipt = next(entry for entry in provenance["inputs"] if role in entry["roles"])
        assert receipt["path"] == receipt["resolved_path"] == str(build.parent / name)
        assert receipt["roles"] == sorted([role, "reconstruction:" + label])
    result = _associate_read_only(reports / "preservation_report.json", build, root, tmp_path)
    assert result["integrity"] == "valid" and result["findings_outcome"] == "pass"
