"""Exercise corrected F02 resolution against the preserved divergence fixtures.

The original observations remain in the dated evidence note and frozen v1 report.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path

import pytest

from hermeneia.cli import build_cmd, preserve_cmd
from hermeneia.preservation_provenance import verify_report_binding
from test_build_reproducibility import _snapshot
from test_publication_reproducibility import _create_inputs


FIXTURES = Path(__file__).parent / "fixtures/custom-build-path-divergence"
NAMES = ("coverage.json", "release_recommendation.json")


class _Clock:
    @classmethod
    def now(cls, tz):
        return datetime.fromisoformat("2026-09-23T12:00:00+00:00").astimezone(tz)


def _prepare(root, monkeypatch, *, adjacent="adjacent", conventional="conventional"):
    _create_inputs(root)
    with monkeypatch.context() as patch:
        patch.chdir(root)
        patch.setattr(build_cmd, "datetime", _Clock)
        build_cmd.cmd_build(output_dir=str(root / "custom"))
    for destination, fixture in [("custom", adjacent), ("publication", conventional)]:
        (root / destination).mkdir(exist_ok=True)
        for name in NAMES:
            (root / destination / name).write_bytes((FIXTURES / fixture / name).read_bytes())
    return root / "custom/build.json"


def _verify(root, reports, monkeypatch):
    """Exercise the production command; only its clock is fixed for the witness."""
    before = _snapshot(root)
    exit_code = 0
    with monkeypatch.context() as patch:
        patch.chdir(root)
        patch.setattr(preserve_cmd, "datetime", _Clock)
        try:
            preserve_cmd.cmd_preserve_verify(build_path="custom/build.json", output_dir=str(reports))
        except SystemExit as exc:
            exit_code = exc.code
    assert _snapshot(root) == before, "Verification changed an input"
    path = reports / "preservation_report.json"
    return exit_code, json.loads(path.read_bytes()) if path.exists() else None


def _checks(report, side):
    return {item["name"]: item for item in report[side]["checks"]}


@pytest.mark.parametrize("reverse", [False, True], ids=["adjacent-withhold", "conventional-withhold"])
def test_custom_build_interprets_and_hashes_the_same_sibling_records(tmp_path, monkeypatch, reverse):
    root = tmp_path / "project"
    build = _prepare(root, monkeypatch,
                     adjacent="conventional" if reverse else "adjacent",
                     conventional="adjacent" if reverse else "conventional")
    reports = tmp_path / "reports"
    exit_code, report = _verify(root, reports, monkeypatch)
    reconstruction, continuation = _checks(report, "reconstruction"), _checks(report, "continuation")
    assert exit_code == 0  # WARN is historically non-failing; it does not approve release.
    assert report["overall_outcome"] == ("pass" if reverse else "warn")
    assert report["build_id"] == "reproducibility-fixture"
    assert not (root / "publication/build.json").exists(), "Conventional build is not needed for this witness"

    # Presence/hash findings now name exactly the interpreted siblings.
    for name, label in zip(NAMES, ("Coverage Record", "Release Recommendation")):
        selected, conventional = root / "custom" / name, root / "publication" / name
        assert reconstruction[label] == {
            "name": label, "status": "PASS", "path": str(selected),
            "sha256": hashlib.sha256(selected.read_bytes()).hexdigest(),
        }
        assert selected.read_bytes() != conventional.read_bytes()
        assert reconstruction[label]["sha256"] != hashlib.sha256(conventional.read_bytes()).hexdigest()

    # The same report interprets custom-directory values, even when they conflict.
    assert continuation["Release Recommendation"]["outcome"] == ("RECOMMEND_RELEASE" if reverse else "WITHHOLD")
    assert continuation["Release Recommendation"]["status"] == ("PASS" if reverse else "WARN")
    assert reconstruction["Steward Signature"]["value"] == ("SYNTHETIC-CONVENTIONAL-ONLY" if reverse else None)
    assert reconstruction["Steward Signature"]["status"] == ("PASS" if reverse else "ADVISORY")
    assert continuation["Steward Notes"]["status"] == ("PASS" if reverse else "ADVISORY")
    if reverse:
        assert "Coverage Build ID" not in reconstruction
        assert "Coverage Corpus Integrity" not in reconstruction
    else:
        assert reconstruction["Coverage Build ID"]["status"] == "WARN"
        assert "adjacent-other-build" in reconstruction["Coverage Build ID"]["note"]
        assert reconstruction["Coverage Corpus Integrity"]["status"] == "WARN"
        assert "docs/adjacent-only.md" in reconstruction["Coverage Corpus Integrity"]["note"]

    # Record every evaluated artifact; paths below are test assertions, not a
    # normalization or rewrite of the raw machine report/provenance receipt.
    receipts = {Path(item["path"]).relative_to(root).as_posix(): item for item in report["provenance"]["inputs"]}
    assert set(receipts) == {
        "custom/build.json", "custom/build.reproducibility.json", "custom/white_paper.md",
        "custom/rc_log.md", "custom/release_decision.md", "docs/blueprint.md",
        "docs/builds/white_paper.compile.yaml", "docs/evidence.md", "docs/paper.md",
        "custom/coverage.json", "custom/release_recommendation.json",
    }
    for name, role, label in zip(NAMES, ("coverage-interpretation", "release-interpretation"),
                                  ("Coverage Record", "Release Recommendation")):
        assert receipts["custom/" + name]["roles"] == sorted([role, "reconstruction:" + label])
    assert report["provenance"]["integrity"] == "valid"
    # Binding retains negative observations without admitting conventional substitutes.
    before = _snapshot(tmp_path)
    association = verify_report_binding(reports / "preservation_report.json", build, project_root=root)
    assert association["integrity"] == "valid"
    assert association["findings_outcome"] == report["overall_outcome"]
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("side,name,expected,exit_code", [
    ("publication", "coverage.json", "pass", 0),
    ("publication", "release_recommendation.json", "pass", 0),
    ("custom", "coverage.json", "fail", 1),
    ("custom", "release_recommendation.json", "fail", 1),
])
def test_missing_sibling_fails_without_conventional_fallback(tmp_path, monkeypatch, side, name, expected, exit_code):
    root = tmp_path / "project"
    _prepare(root, monkeypatch, adjacent="conventional", conventional="conventional")
    (root / side / name).unlink()
    actual_exit, report = _verify(root, tmp_path / "reports", monkeypatch)
    assert actual_exit == exit_code
    assert report["overall_outcome"] == expected
    label = "Coverage Record" if name == "coverage.json" else "Release Recommendation"
    assert _checks(report, "reconstruction")[label]["status"] == ("FAIL" if side == "custom" else "PASS")
    assert report["provenance"]["integrity"] == "valid"
    entries = [item for item in report["provenance"]["inputs"] if item["path"] == str(root / side / name)]
    if side == "custom":
        assert len(entries) == 1 and entries[0]["state"] == "missing" and "sha256" not in entries[0]
    else:
        assert entries == []


@pytest.mark.parametrize("side", ["custom", "publication"])
@pytest.mark.parametrize("name", NAMES)
def test_malformed_json_is_parsed_only_on_the_adjacent_side(tmp_path, monkeypatch, side, name):
    root = tmp_path / "project"
    _prepare(root, monkeypatch, adjacent="conventional", conventional="conventional")
    malformed = b"{not JSON\n"
    (root / side / name).write_bytes(malformed)
    exit_code, report = _verify(root, tmp_path / "reports", monkeypatch)
    if side == "custom":
        assert exit_code == 1 and report is None
    else:
        assert exit_code == 0 and report["overall_outcome"] == "pass"
        label = "Coverage Record" if name == "coverage.json" else "Release Recommendation"
        assert _checks(report, "reconstruction")[label]["sha256"] == hashlib.sha256((root / "custom" / name).read_bytes()).hexdigest()
        assert str(root / "publication" / name) not in {item["path"] for item in report["provenance"]["inputs"]}
        assert report["provenance"]["integrity"] == "valid"


@pytest.mark.parametrize("name", ["coverage.json", "release_recommendation.json"])
def test_sibling_redirected_after_namespace_selection_is_refused(tmp_path, monkeypatch, name):
    from hermeneia.preservation_provenance import VerificationInputs
    root = tmp_path / "project"
    _prepare(root, monkeypatch, adjacent="conventional", conventional="conventional")
    sibling = root / "custom" / name
    real = VerificationInputs._read_observed

    def redirect(self, path):
        if path == sibling and not sibling.is_symlink():
            sibling.unlink()
            sibling.symlink_to(root / "publication" / name)
        return real(self, path)

    # Only the adversary changes the fixture; the verifier must write no report
    # and must not accept identical bytes found in another namespace.
    monkeypatch.setattr(VerificationInputs, "_read_observed", redirect)
    reports = tmp_path / "reports"
    with monkeypatch.context() as patch:
        patch.chdir(root)
        with pytest.raises(SystemExit) as exc:
            preserve_cmd.cmd_preserve_verify(build_path="custom/build.json", output_dir=str(reports))
    assert exc.value.code == 1
    assert not reports.exists()


def test_late_sibling_redirection_refuses_core_claim(tmp_path, monkeypatch):
    from hermeneia.preservation_provenance import VerificationInputs
    root = tmp_path / "project"
    _prepare(root, monkeypatch, adjacent="conventional", conventional="conventional")
    sibling = root / "custom/coverage.json"
    real = VerificationInputs.receipt

    def redirect(self, *args):
        sibling.unlink()
        sibling.symlink_to(root / "publication/coverage.json")
        return real(self, *args)

    monkeypatch.setattr(VerificationInputs, "receipt", redirect)
    reports = tmp_path / "reports"
    with monkeypatch.context() as patch:
        patch.chdir(root)
        preserve_cmd.cmd_preserve_verify(build_path="custom/build.json", output_dir=str(reports))
    report = json.loads((reports / "preservation_report.json").read_bytes())
    assert report["provenance"]["integrity"] == "invalid"
    assert "build_core" not in report["provenance"]
    assert "changed" in report["provenance"]["reason"]
    assert verify_report_binding(reports / "preservation_report.json", root / "custom/build.json",
                                 project_root=root)["integrity"] != "valid"


@pytest.mark.parametrize("selector", ["docs/../custom/build.json", "alias/build.json"])
def test_consistent_resolved_namespace_preserves_authored_lookup(tmp_path, monkeypatch, selector):
    root = tmp_path / "project"
    _prepare(root, monkeypatch, adjacent="conventional", conventional="conventional")
    (root / "alias").symlink_to(root / "custom", target_is_directory=True)
    reports = tmp_path / "reports"
    before = _snapshot(root)
    with monkeypatch.context() as patch:
        patch.chdir(root)
        preserve_cmd.cmd_preserve_verify(build_path=selector, output_dir=str(reports))
    report = json.loads((reports / "preservation_report.json").read_bytes())
    assert report["provenance"]["integrity"] == "valid"
    lookup = next(item for item in report["provenance"]["inputs"] if "build-record" in item["roles"])
    assert lookup["path"] == str(root / selector)
    assert lookup["resolved_path"] == str(root / "custom/build.json")
    report_before = _snapshot(reports)
    association = verify_report_binding(reports / "preservation_report.json", root / selector, project_root=root)
    assert association["integrity"] == "valid", association
    assert _snapshot(root) == before and _snapshot(reports) == report_before
