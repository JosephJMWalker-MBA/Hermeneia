"""Report association requires the evaluated execution and preserves its findings."""
from datetime import datetime
import json

import pytest

from hermeneia.build_core import canonical_json
from hermeneia.cli import build_cmd, preserve_cmd as preserve
from hermeneia.preservation_provenance import verify_report_binding
from test_build_reproducibility import _snapshot
from test_preservation_provenance import _ready, _report
from test_publication_reproducibility import COVERAGE, RELEASE


def _make_report(root, reports, monkeypatch, **kwargs):
    report = _report(root, reports, monkeypatch, **kwargs)
    return reports / "preservation_report.json", report


def _associate_read_only(report_path, build_path, root, snapshot_root):
    before = _snapshot(snapshot_root)
    result = verify_report_binding(report_path, build_path, project_root=root)
    assert _snapshot(snapshot_root) == before
    return result


def test_valid_association_is_read_only_for_report_and_all_inputs(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    result = _associate_read_only(report_path, build_path, root, tmp_path)
    assert result == {"integrity": "valid", "build_core": report["provenance"]["build_core"],
                      "findings_outcome": "pass"}


def test_identical_paper_from_different_configuration_cannot_inherit_report(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first_build = _ready(first, monkeypatch)

    def change_configuration(root):
        manifest = root / "docs/builds/white_paper.compile.yaml"
        manifest.write_bytes(manifest.read_bytes().replace(
            b"required_tags: [thesis]", b"required_tags: [blueprint]"))

    second_build = _ready(second, monkeypatch, mutate=change_configuration)
    assert (first_build.parent / "white_paper.md").read_bytes() == (
        second_build.parent / "white_paper.md").read_bytes()
    report_path, report = _make_report(first, tmp_path / "reports", monkeypatch)
    _, other_report = _make_report(second, tmp_path / "other-reports", monkeypatch)
    assert report["overall_outcome"] == other_report["overall_outcome"] == "pass"
    assert report["provenance"]["build_core"] != other_report["provenance"]["build_core"]
    result = _associate_read_only(report_path, second_build, second, tmp_path)
    assert result["integrity"] == "invalid"


def test_new_execution_at_same_paths_cannot_inherit_same_core_report(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    report_path, original = _make_report(root, tmp_path / "reports", monkeypatch)
    original_build = build_path.read_bytes()

    class LaterClock:
        @classmethod
        def now(cls, tz):
            return datetime.fromisoformat("2026-09-24T02:01:00+00:00").astimezone(tz)

    with monkeypatch.context() as patch:
        patch.chdir(root)
        patch.setattr(build_cmd, "datetime", LaterClock)
        build_cmd.cmd_build()
    (build_path.parent / "coverage.json").write_bytes(COVERAGE)
    (build_path.parent / "release_recommendation.json").write_bytes(RELEASE)
    _, current = _make_report(root, tmp_path / "current-reports", monkeypatch)
    assert original["provenance"]["build_core"] == current["provenance"]["build_core"]
    assert build_path.read_bytes() != original_build
    result = _associate_read_only(report_path, build_path, root, tmp_path)
    assert result["integrity"] == "invalid"


def test_tampered_failure_cannot_be_promoted_to_success(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    (build_path.parent / "coverage.json").unlink()
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    assert report["provenance"]["integrity"] == "valid"
    assert report["overall_outcome"] == "fail"
    assert _associate_read_only(report_path, build_path, root, tmp_path)["findings_outcome"] == "fail"
    check = next(item for item in report["reconstruction"]["checks"]
                 if item["name"] == "Coverage Record")
    check["status"] = "PASS"
    check.pop("note")
    report["reconstruction"]["summary"] = preserve._summarize(report["reconstruction"]["checks"])
    report["overall_outcome"] = "pass"
    report_path.write_bytes(canonical_json(report))
    result = _associate_read_only(report_path, build_path, root, tmp_path)
    assert result["integrity"] == "invalid"
    assert "findings" in result["reason"]


def test_repaired_coverage_cannot_rewrite_or_validate_original_failure(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    coverage = build_path.parent / "coverage.json"
    coverage.unlink()
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    assert report["overall_outcome"] == "fail"
    assert report["provenance"]["integrity"] == "valid"
    assert any(item["state"] == "missing" and item["path"] == str(coverage)
               for item in report["provenance"]["inputs"])
    before = report_path.read_bytes()
    coverage.write_bytes(COVERAGE)
    result = _associate_read_only(report_path, build_path, root, tmp_path)
    assert result["integrity"] == "invalid"
    assert report_path.read_bytes() == before
    assert json.loads(before)["overall_outcome"] == "fail"


@pytest.mark.parametrize("coverage", ["missing-sidecar", "incompatible-profile", "incomplete-core"])
def test_unsupported_build_coverage_never_acquires_core_provenance(tmp_path, monkeypatch, coverage):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    binding_path = build_path.with_name("build.reproducibility.json")
    if coverage == "missing-sidecar":
        binding_path.unlink()
    else:
        binding = json.loads(binding_path.read_bytes())
        if coverage == "incompatible-profile":
            binding["core"]["schema"] = "hermeneia.build-result/v999"
        else:
            del binding["core"]["result"]["historical_outputs"]
        binding_path.write_bytes(canonical_json(binding))
    before = _snapshot(root)
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    assert _snapshot(root) == before
    assert report["overall_outcome"] == "pass"
    assert report["provenance"]["integrity"] == "unsupported"
    assert "build_core" not in report["provenance"]
    assert _associate_read_only(report_path, build_path, root, tmp_path)["integrity"] == "unsupported"


@pytest.mark.parametrize("mutation", ["compiled-bytes", "missing-digest"])
def test_invalid_core_preserves_every_historical_negative_finding(tmp_path, monkeypatch, mutation):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    if mutation == "compiled-bytes":
        paper = build_path.parent / "white_paper.md"
        paper.write_bytes(paper.read_bytes() + b"\nchanged artifact\n")
    else:
        build = json.loads(build_path.read_bytes())
        del build["compile"]["sha256"]
        build_path.write_bytes(canonical_json(build))
    # The existing historical checks are the oracle for all findings, not merely
    # the outcome. Adding a binding must not suppress or soften any check.
    build, coverage, release, manifest = preserve._load_inputs(build_path, root)
    old_reconstruction = preserve._verify_reconstruction(build, coverage, release, root)
    old_continuation = preserve._verify_continuation(build, manifest, release, root)
    before = _snapshot(root)
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    assert _snapshot(root) == before
    assert report["reconstruction"]["checks"] == old_reconstruction
    assert report["continuation"]["checks"] == old_continuation
    assert report["overall_outcome"] == "fail"
    assert report["provenance"]["integrity"] == "invalid"
    assert "build_core" not in report["provenance"]
    assert _associate_read_only(report_path, build_path, root, tmp_path)["integrity"] == "unsupported"


def test_historical_report_is_not_backfilled_from_current_valid_build(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    del report["provenance"]
    report_path.write_bytes(canonical_json(report))
    result = _associate_read_only(report_path, build_path, root, tmp_path)
    assert result["integrity"] == "unsupported"
    assert "provenance" not in json.loads(report_path.read_bytes())


def test_changed_report_core_claim_is_refused_even_when_findings_match(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    report["provenance"]["build_core"]["sha256"] = "f" * 64
    report_path.write_bytes(canonical_json(report))
    assert _associate_read_only(report_path, build_path, root, tmp_path)["integrity"] == "invalid"


@pytest.mark.parametrize("signature", [3.5, 2**60])
def test_historical_numeric_signature_values_keep_valid_report_association(tmp_path, monkeypatch, signature):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    release_path = build_path.parent / "release_recommendation.json"
    release = json.loads(release_path.read_bytes())
    # The historical preservation reader observes this value verbatim. This
    # test does not confer signature authority or impose a new release schema.
    release["steward_signature"] = signature
    release_path.write_text(json.dumps(release))
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    signature_check = next(item for item in report["reconstruction"]["checks"]
                           if item["name"] == "Steward Signature")
    assert signature_check["value"] == signature
    assert report["provenance"]["integrity"] == "valid"
    result = _associate_read_only(report_path, build_path, root, tmp_path)
    assert result["integrity"] == "valid", result
    assert result["findings_outcome"] == report["overall_outcome"]


def test_boolean_cannot_impersonate_integer_finding_count(tmp_path, monkeypatch):
    root = tmp_path / "project"
    build_path = _ready(root, monkeypatch)
    report_path, report = _make_report(root, tmp_path / "reports", monkeypatch)
    assert report["reconstruction"]["summary"]["fail"] == 0
    report["reconstruction"]["summary"]["fail"] = False
    report_path.write_text(json.dumps(report))
    result = _associate_read_only(report_path, build_path, root, tmp_path)
    assert result["integrity"] == "invalid"
    assert "findings" in result["reason"]
