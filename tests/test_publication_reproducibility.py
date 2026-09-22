"""Controlled reproducibility measurements; no production timestamp policy.

The clock is injected only in tests to isolate causes of byte divergence. These
characterization tests do not declare timestamps or local paths disposable.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from hermeneia.cli import build_cmd, preserve_cmd


EARLIER = "2026-09-22T12:00:00+00:00"
LATER = "2026-09-22T12:01:00+00:00"
PRESERVE_EARLIER = "2026-09-22T13:00:00+00:00"
PRESERVE_LATER = "2026-09-22T13:01:00+00:00"
INPUTS = {
    "docs/builds/white_paper.compile.yaml": b"""build_id: reproducibility-fixture
compiled_artifact: docs/paper.md
blueprint: docs/blueprint.md
blueprint_id: fixture-blueprint
blueprint_status: ratified
status: RC-fixture
ratification: pending
source_artifacts:
  - path: docs/blueprint.md
    tags: [thesis, blueprint]
    status: ratified
    role: primary-contract
  - path: docs/evidence.md
    tags: [evidence, hypothesis]
    status: complete
    role: evidence
sections:
  - section: abstract
    required_tags: [thesis]
  - section: discussion
    required_tags: [evidence]
""",
    "docs/blueprint.md": b"# Fixture Blueprint\n\nIntent hypothesis: preserve evidence.\n",
    "docs/evidence.md": b"# Fixture evidence\n\nOpen hypothesis: reproducibility is measurable.\n",
    "docs/paper.md": b"\xef\xbb\xbf# Fixture paper\r\ncaf\xc3\xa9\r\n",
    "docs/builds/white_paper_rc_log.md": b"# Fixture RC history\n\nPreserve this history verbatim.\n",
    "docs/builds/white_paper_release_decision.md": b"# Fixture steward record\n\nPending review.\n",
}
# Fixed downstream inputs isolate build/preserve behavior from coverage/release
# generation. These synthetic fixtures are not actual steward decisions.
COVERAGE = b'{"build_id":"reproducibility-fixture","outcome":"pass"}'
RELEASE = b'{"build_id":"reproducibility-fixture","outcome":"RECOMMEND_RELEASE","steward_signature":"fixture-only","steward_notes":"Synthetic reproducibility fixture","signed_at":"2026-01-01T00:00:00+00:00"}'


def _create_inputs(root: Path, *, reverse_creation=False):
    root.mkdir()
    entries = list(INPUTS.items())
    for relative, content in reversed(entries) if reverse_creation else entries:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _input_bytes(root: Path):
    return {name: (root / name).read_bytes() for name in INPUTS}


def _run_clean(root: Path, monkeypatch, *, build_time=EARLIER, preserve_time=PRESERVE_EARLIER):
    publication = root / "publication"
    preservation = root / "preservation"
    assert not publication.exists() and not preservation.exists()
    before = _input_bytes(root)

    def clock_at(instant):
        class Clock:
            @classmethod
            def now(cls, tz):
                return datetime.fromisoformat(instant).astimezone(tz)
        return Clock

    with monkeypatch.context() as patch:
        patch.chdir(root)
        patch.setattr(build_cmd, "datetime", clock_at(build_time))
        patch.setattr(preserve_cmd, "datetime", clock_at(preserve_time))
        build_cmd.cmd_build()
        (publication / "coverage.json").write_bytes(COVERAGE)
        (publication / "release_recommendation.json").write_bytes(RELEASE)
        preserve_cmd.cmd_preserve_verify()
        preserve_cmd.cmd_preserve_export()

    assert _input_bytes(root) == before
    outputs = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for directory in (publication, preservation)
        for path in directory.rglob("*") if path.is_file()
    }
    report = json.loads(outputs["publication/preservation_report.json"])
    assert report["overall_outcome"] == "pass"
    assert outputs["publication/white_paper.md"] == INPUTS["docs/paper.md"]
    return outputs


def _archive_outputs(root: Path, archive: Path):
    """Keep the first run while giving the next run the identical clean paths."""
    archive.mkdir()
    for name in ("publication", "preservation"):
        (root / name).rename(archive / name)


def _changed_files(first, second):
    assert first.keys() == second.keys()
    return {name for name in first if first[name] != second[name]}


def _changed_fields(first, second, prefix=""):
    if isinstance(first, dict) and isinstance(second, dict):
        assert first.keys() == second.keys()
        return set().union(*(
            _changed_fields(first[key], second[key], f"{prefix}/{key}") for key in first
        ))
    if isinstance(first, list) and isinstance(second, list):
        assert len(first) == len(second)
        return set().union(*(
            _changed_fields(a, b, f"{prefix}/{index}")
            for index, (a, b) in enumerate(zip(first, second))
        ))
    return {prefix} if first != second else set()


def test_clean_builds_differ_only_in_execution_time_and_its_downstream_hash(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _create_inputs(root)
    first = _run_clean(root, monkeypatch)
    _archive_outputs(root, tmp_path / "first")
    second = _run_clean(root, monkeypatch, build_time=LATER)

    build_name = "publication/build.json"
    copied_name = "preservation/preservation_package/artifacts/build.json"
    manifest_name = "preservation/preservation_package/manifest.json"
    assert _changed_files(first, second) == {
        build_name, "publication/coverage.md", copied_name, manifest_name,
    }
    first_build, second_build = json.loads(first[build_name]), json.loads(second[build_name])
    assert _changed_fields(first_build, second_build) == {"/build_timestamp"}
    assert first_build["build_timestamp"] == EARLIER
    assert second_build["build_timestamp"] == LATER
    first_package = json.loads(first[manifest_name])
    second_package = json.loads(second[manifest_name])
    build_index = next(i for i, item in enumerate(first_package["artifacts"])
                       if item["preserved_as"] == "artifacts/build.json")
    assert _changed_fields(first_package, second_package) == {f"/artifacts/{build_index}/sha256"}
    for outputs, package in [(first, first_package), (second, second_package)]:
        assert outputs[copied_name] == outputs[build_name]
        assert package["artifacts"][build_index]["sha256"] == hashlib.sha256(outputs[build_name]).hexdigest()


def test_identical_execution_context_is_byte_reproducible_despite_different_staging(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _create_inputs(root)
    real_temporary_directory = build_cmd.tempfile.TemporaryDirectory
    staging_paths = []

    def distinct_staging(*args, **kwargs):
        kwargs["prefix"] = f".distinct-stage-{len(staging_paths)}-"
        directory = real_temporary_directory(*args, **kwargs)
        staging_paths.append(directory.name)
        return directory

    monkeypatch.setattr(build_cmd.tempfile, "TemporaryDirectory", distinct_staging)
    first = _run_clean(root, monkeypatch)
    _archive_outputs(root, tmp_path / "first")
    second = _run_clean(root, monkeypatch)

    assert len(staging_paths) == len(set(staging_paths)) == 4
    assert first == second, "Compare all raw output bytes without stripping any provenance"
    assert all(b".distinct-stage-" not in content for content in first.values())
    assert all(not Path(path).exists() for path in staging_paths)


def test_preservation_event_times_differ_with_identical_build_record(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _create_inputs(root)
    first = _run_clean(root, monkeypatch)
    _archive_outputs(root, tmp_path / "first")
    second = _run_clean(root, monkeypatch, preserve_time=PRESERVE_LATER)

    report_name = "publication/preservation_report.json"
    package_name = "preservation/preservation_package/manifest.json"
    assert _changed_files(first, second) == {
        report_name, "publication/preservation_report.md", package_name,
    }
    assert _changed_fields(json.loads(first[report_name]), json.loads(second[report_name])) == {"/generated_at"}
    assert _changed_fields(json.loads(first[package_name]), json.loads(second[package_name])) == {"/packaged_at"}
    assert json.loads(first[report_name])["generated_at"] == PRESERVE_EARLIER
    assert json.loads(second[report_name])["generated_at"] == PRESERVE_LATER


def test_identical_inputs_at_different_roots_record_local_paths(tmp_path, monkeypatch):
    root_a, root_b = tmp_path / "location-a", tmp_path / "location-b"
    _create_inputs(root_a)
    _create_inputs(root_b)
    assert _input_bytes(root_a) == _input_bytes(root_b) == INPUTS
    first = _run_clean(root_a, monkeypatch)
    second = _run_clean(root_b, monkeypatch)

    build_name = "publication/build.json"
    report_name = "publication/preservation_report.json"
    package_name = "preservation/preservation_package/manifest.json"
    assert _changed_files(first, second) == {
        build_name, report_name, package_name,
        "preservation/preservation_package/artifacts/build.json",
    }
    first_build, second_build = json.loads(first[build_name]), json.loads(second[build_name])
    assert _changed_fields(first_build, second_build) == {
        "/blueprint/path", "/compile/source", "/manifest_path",
        *(f"/outputs/{name}" for name in first_build["outputs"]),
    }
    first_report, second_report = json.loads(first[report_name]), json.loads(second[report_name])
    assert _changed_fields(first_report, second_report) == {
        f"/reconstruction/checks/{index}/path"
        for index, check in enumerate(first_report["reconstruction"]["checks"]) if "path" in check
    }
    first_package, second_package = json.loads(first[package_name]), json.loads(second[package_name])
    expected = {f"/artifacts/{index}/original_path" for index in range(len(first_package["artifacts"]))}
    for index, entry in enumerate(first_package["artifacts"]):
        if entry["preserved_as"] == "artifacts/build.json":
            expected.add(f"/artifacts/{index}/sha256")
    assert _changed_fields(first_package, second_package) == expected
    assert first_build["source_artifacts"] == second_build["source_artifacts"]
    assert first_build["manifest_hash"] == second_build["manifest_hash"]
    assert first_build["compile"]["sha256"] == second_build["compile"]["sha256"]


def test_hash_seed_timezone_file_metadata_and_creation_order_do_not_change_records(tmp_path):
    root = tmp_path / "project"
    snapshots = []
    script = '''
import runpy
import sys
import time
from pathlib import Path
from pytest import MonkeyPatch
if hasattr(time, "tzset"):
    time.tzset()
helpers = runpy.run_path(sys.argv[1])
helpers["_run_clean"](Path.cwd(), MonkeyPatch())
'''
    variants = [
        ("baseline", "1", "UTC", 1600000000, False),
        ("hash-seed", "8675309", "UTC", 1600000000, False),
        ("timezone", "1", "Pacific/Honolulu", 1600000000, False),
        ("mtime", "1", "UTC", 1600001000, False),
        ("creation-order", "1", "UTC", 1600000000, True),
    ]
    for name, seed, zone, mtime, reverse_creation in variants:
        _create_inputs(root, reverse_creation=reverse_creation)
        # Different filesystem mtimes are not different authoritative byte inputs.
        for relative in INPUTS:
            os.utime(root / relative, (mtime,) * 2)
        environment = dict(os.environ, PYTHONHASHSEED=seed, TZ=zone,
                           PYTHONPATH=str(Path(build_cmd.__file__).resolve().parents[2]))
        result = subprocess.run([sys.executable, "-c", script, str(Path(__file__).resolve())],
                                cwd=root, env=environment, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr + result.stdout[-2000:]
        assert _input_bytes(root) == INPUTS
        snapshots.append({path.relative_to(root).as_posix(): path.read_bytes()
                          for path in root.rglob("*") if path.is_file()})
        root.rename(tmp_path / f"completed-{name}")
        assert snapshots[0] == snapshots[-1], f"Raw bytes (including JSON key order) differ for {name}"
