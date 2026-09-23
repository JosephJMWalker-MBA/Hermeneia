"""Build-result bindings, adversarial verification and read-only comparison."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from hermeneia import build_reproducibility as repro
from hermeneia.build_core import InvalidRecord, canonical_json, core_digest
from hermeneia.cli import build_cmd
from test_publication_reproducibility import COVERAGE, RELEASE, _create_inputs


def _build(root, monkeypatch, *, mutate=None, instant="2026-09-23T01:00:00+00:00"):
    _create_inputs(root)
    if mutate:
        mutate(root)

    class Clock:
        @classmethod
        def now(cls, tz):
            return datetime.fromisoformat(instant).astimezone(tz)

    with monkeypatch.context() as patch:
        patch.chdir(root)
        patch.setattr(build_cmd, "datetime", Clock)
        build_cmd.cmd_build()
    return root / "publication/build.json"


def test_build_persists_binding_to_exact_record_and_historical_outputs(tmp_path, monkeypatch):
    build_path = _build(tmp_path / "project", monkeypatch)
    binding_path = build_path.with_name("build.reproducibility.json")
    assert binding_path.exists(), "Successful build has no reproducibility core binding"
    binding = json.loads(binding_path.read_bytes())
    assert binding["envelope"]["records"][0]["sha256"] == hashlib.sha256(build_path.read_bytes()).hexdigest()
    for role in ("rc_log", "release_decision"):
        assert binding["core"]["result"]["historical_outputs"][role + "_sha256"] == hashlib.sha256(
            (build_path.parent / (role + ".md")).read_bytes()).hexdigest()


def test_relocated_roots_compare_equivalent_without_changing_record_bytes(tmp_path, monkeypatch):
    left_root, right_root = tmp_path / "left", tmp_path / "right"
    left, right = _build(left_root, monkeypatch), _build(right_root, monkeypatch)
    assert left.read_bytes() != right.read_bytes()
    from hermeneia.build_reproducibility import compare_builds
    result = compare_builds(left, right, left_root=left_root, right_root=right_root)
    assert result["comparison"] == "equivalent", result


def _snapshot(root):
    return {p.relative_to(root): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


def test_times_differ_but_result_is_equivalent_and_comparison_is_read_only(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    left = _build(a, monkeypatch)
    right = _build(b, monkeypatch, instant="2026-09-24T02:01:00+00:00")
    assert json.loads(left.read_bytes())["build_timestamp"] != json.loads(right.read_bytes())["build_timestamp"]
    before = _snapshot(tmp_path)
    result = repro.compare_builds(left, right, left_root=a, right_root=b)
    assert result["comparison"] == "equivalent"
    assert result["execution_evidence_changed"] is True
    assert result["left"]["record_sha256"] != result["right"]["record_sha256"]
    assert result["differences"] == []
    assert repro.compare_builds(left, left, left_root=a, right_root=a)["execution_evidence_changed"] is False
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("change", ["paper", "source", "configuration", "history", "historical-date"])
def test_changed_authoritative_content_or_configuration_compares_different(tmp_path, monkeypatch, change):
    def mutate(root):
        paths = {"paper": "docs/paper.md", "source": "docs/evidence.md",
                 "configuration": "docs/builds/white_paper.compile.yaml",
                 "history": "docs/builds/white_paper_rc_log.md",
                 "historical-date": "docs/builds/white_paper_release_decision.md"}
        path = root / paths[change]
        raw = path.read_bytes()
        if change == "configuration":
            raw = raw.replace(b"required_tags: [thesis]", b"required_tags: [new-obligation]")
        else:
            raw += b"\n2026-09-23: changed authoritative content\n"
        path.write_bytes(raw)
    a, b = tmp_path / "a", tmp_path / "b"
    left, right = _build(a, monkeypatch), _build(b, monkeypatch, mutate=mutate)
    result = repro.compare_builds(left, right, left_root=a, right_root=b)
    assert result["comparison"] == "different", result
    assert result["left"]["integrity"] == result["right"]["integrity"] == "valid"
    fields = {item["path"] for item in result["differences"]}
    expected = {"paper": "/result/compile/sha256", "source": "/result/source_artifacts/1/sha256",
                "configuration": "/result/manifest_hash", "history": "/result/historical_outputs/rc_log_sha256",
                "historical-date": "/result/historical_outputs/release_decision_sha256"}[change]
    assert expected in fields


@pytest.mark.parametrize("mutation", ["digest", "record", "core", "rehashed-core", "paper", "source", "history"])
def test_tampering_is_invalid_evidence_not_a_valid_different_result(tmp_path, monkeypatch, mutation):
    root = tmp_path / "project"
    build_path = _build(root, monkeypatch)
    binding_path = build_path.with_name(repro.BINDING_NAME)
    binding = json.loads(binding_path.read_bytes())
    if mutation in ("digest", "core", "rehashed-core"):
        if mutation == "digest":
            binding["envelope"]["core_sha256"] = "f" * 64
        else:
            binding["core"]["result"]["compile"]["sha256"] = "f" * 64
            if mutation == "rehashed-core":
                binding["envelope"]["core_sha256"] = core_digest(binding["core"])
        binding_path.write_bytes(canonical_json(binding))
    else:
        target = {"record": build_path, "paper": root / "publication/white_paper.md",
                  "source": root / "docs/evidence.md", "history": root / "publication/rc_log.md"}[mutation]
        target.write_bytes(target.read_bytes() + b"\n")
    result = repro.compare_builds(build_path, build_path, left_root=root, right_root=root)
    assert result["comparison"] == "unsupported"
    assert result["left"]["integrity"] == "invalid", result


@pytest.mark.parametrize("field", ["binding", "profile", "missing-history", "missing-core-field", "missing-record"])
def test_incompatible_or_incomplete_coverage_refuses_comparison(tmp_path, monkeypatch, field):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    binding_path = path.with_name(repro.BINDING_NAME)
    binding = json.loads(binding_path.read_bytes())
    if field == "binding":
        binding["schema"] = "hermeneia.reproducibility-binding/v999"
    elif field == "profile":
        binding["core"]["schema"] = "hermeneia.build-result/v999"
    elif field == "missing-history":
        del binding["core"]["result"]["historical_outputs"]
    elif field == "missing-core-field":
        del binding["core"]["result"]["source_artifacts"][0]["role"]
    else:
        binding["envelope"]["records"] = []
    binding_path.write_bytes(canonical_json(binding))
    before = _snapshot(root)
    result = repro.compare_builds(path, path, left_root=root, right_root=root)
    assert result["comparison"] == "unsupported"
    assert result["left"]["integrity"] == "unsupported", result
    assert _snapshot(root) == before


def test_legacy_record_retains_old_readers_and_preservation_contract(tmp_path, monkeypatch):
    from hermeneia.cli.coverage_cmd import _load_build_json
    from hermeneia.cli.preserve_cmd import cmd_preserve_verify
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    # Exercise the unchanged legacy record alone, as pre-profile readers do.
    path.with_name(repro.BINDING_NAME).unlink()
    original = path.read_bytes()
    assert _load_build_json(path) == json.loads(original)
    (path.parent / "coverage.json").write_bytes(COVERAGE)
    (path.parent / "release_recommendation.json").write_bytes(RELEASE)
    with monkeypatch.context() as patch:
        patch.chdir(root)
        cmd_preserve_verify()
    assert json.loads((path.parent / "preservation_report.json").read_bytes())["overall_outcome"] == "pass"
    before = _snapshot(root)
    result = repro.compare_builds(path, path, left_root=root, right_root=root)
    assert result["comparison"] == "unsupported"
    assert "legacy" in result["left"]["reason"]
    assert _snapshot(root) == before and path.read_bytes() == original


@pytest.mark.parametrize("authored", ["blueprint", "compiled_artifact", "source"])
def test_authored_absolute_references_are_preserved_and_not_normalized(tmp_path, monkeypatch, authored):
    def mutate(root):
        path = root / "docs/builds/white_paper.compile.yaml"
        reference = {"blueprint": b"blueprint: docs/blueprint.md",
                     "compiled_artifact": b"compiled_artifact: docs/paper.md",
                     "source": b"path: docs/evidence.md"}[authored]
        key, value = reference.split(b": ")
        path.write_bytes(path.read_bytes().replace(reference, key + b": " + str(root).encode() + b"/" + value))
    root = tmp_path / "project"
    path = _build(root, monkeypatch, mutate=mutate)
    assert not path.with_name(repro.BINDING_NAME).exists()
    manifest = root / "docs/builds/white_paper.compile.yaml"
    assert str(root).encode() in manifest.read_bytes()
    assert repro.verify_build(path, project_root=root)["integrity"] == "unsupported"


def test_symlink_escape_is_unsupported_even_with_identical_content(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    source = root / "docs/evidence.md"
    outside = tmp_path / "outside.md"
    outside.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(outside)
    result = repro.verify_build(path, project_root=root)
    assert result["integrity"] == "unsupported" and "escapes" in result["reason"]


def test_changed_capture_is_not_reparsed_or_adopted(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    manifest = root / "docs/builds/white_paper.compile.yaml"
    read = repro._Captures._read_confined
    fired = False

    def change_after_capture(captures, target):
        nonlocal fired
        raw = read(captures, target)
        if target == manifest and not fired:
            fired = True
            target.write_bytes(raw + b"\n# later version\n")
        return raw

    monkeypatch.setattr(repro._Captures, "_read_confined", change_after_capture)
    result = repro.verify_build(path, project_root=root)
    assert fired and result["integrity"] == "invalid", result


def test_history_drift_after_emission_is_refused_before_record_install(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    original = path.read_bytes()
    stage = build_cmd._stage_steward_report

    def emit_then_change(*args):
        captured = stage(*args)
        (args[2] / "rc_log.md").write_bytes(b"later bytes")
        return captured

    monkeypatch.setattr(build_cmd, "_stage_steward_report", emit_then_change)
    monkeypatch.chdir(root)
    with pytest.raises(SystemExit) as exc:
        build_cmd.cmd_build()
    assert exc.value.code == 1
    assert path.read_bytes() == original


@pytest.mark.parametrize("fault", ["stage", "write", "interrupt", "flush", "replace", "readback"])
def test_binding_publication_failures_never_expose_partial_binding(tmp_path, monkeypatch, fault):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    binding_path = path.with_name(repro.BINDING_NAME)
    previous = binding_path.read_bytes()
    raw = path.read_bytes()
    real_open, real_replace, real_read = Path.open, repro.os.replace, Path.read_bytes

    class FaultyStream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, data):
            assert binding_path.read_bytes() == previous
            if fault in ("write", "interrupt"):
                self.stream.write(data[:13])
                self.stream.flush()
                assert binding_path.read_bytes() == previous
                if fault == "interrupt":
                    raise KeyboardInterrupt("interrupted staging")
                raise OSError("partial staging write")
            return self.stream.write(data)

        def flush(self):
            self.stream.flush()
            if fault == "flush":
                raise OSError("staging flush")

    def failing_open(target, *args, **kwargs):
        stream = real_open(target, *args, **kwargs)
        if target.name == repro.BINDING_NAME and target != binding_path and args == ("wb",):
            return FaultyStream(stream)
        return stream

    def failing_replace(src, dst):
        assert binding_path.read_bytes() == previous
        if fault == "replace":
            raise OSError("replacement failure")
        real_replace(src, dst)

    def failing_read(target):
        data = real_read(target)
        if fault == "readback" and target.name == repro.BINDING_NAME and target != binding_path:
            return data[:11]
        return data

    def failing_stage(*args, **kwargs):
        raise OSError("staging unavailable")

    if fault == "stage":
        monkeypatch.setattr(repro.tempfile, "TemporaryDirectory", failing_stage)
    monkeypatch.setattr(Path, "open", failing_open)
    monkeypatch.setattr(Path, "read_bytes", failing_read)
    monkeypatch.setattr(repro.os, "replace", failing_replace)
    with pytest.raises((OSError, InvalidRecord, KeyboardInterrupt)):
        repro.publish_binding(previous, raw, path, root)
    assert binding_path.read_bytes() == previous
    assert path.read_bytes() == raw
    assert not list(path.parent.glob(".herm-build-binding-*"))


def test_record_tampering_at_binding_install_fails_closed(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    binding_path = path.with_name(repro.BINDING_NAME)
    raw = path.read_bytes()
    serialized = binding_path.read_bytes()
    replace = repro.os.replace

    def install_then_change(src, dst):
        replace(src, dst)
        path.write_bytes(raw + b"\n")

    monkeypatch.setattr(repro.os, "replace", install_then_change)
    with pytest.raises(InvalidRecord, match="changed"):
        repro.publish_binding(serialized, raw, path, root)
    assert repro.verify_build(path, project_root=root)["integrity"] == "invalid"


def test_new_record_with_previous_binding_cannot_compare_successfully(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    binding_path = path.with_name(repro.BINDING_NAME)
    previous = binding_path.read_bytes()
    replace = repro.os.replace

    def refuse_binding(src, dst):
        if Path(dst).name == repro.BINDING_NAME:
            raise OSError("binding replacement unavailable")
        replace(src, dst)

    # Change an authoritative input so the newly installed record differs even
    # if two build clocks happen to have the same timestamp.
    (root / "docs/paper.md").write_bytes(b"new emitted result")
    monkeypatch.chdir(root)
    monkeypatch.setattr(repro.os, "replace", refuse_binding)
    with pytest.raises(SystemExit) as exc:
        build_cmd.cmd_build()
    assert exc.value.code == 1
    assert binding_path.read_bytes() == previous
    assert repro.verify_build(path, project_root=root)["integrity"] == "invalid"


def test_installed_binding_corruption_is_detected(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    binding_path = path.with_name(repro.BINDING_NAME)
    serialized = binding_path.read_bytes()
    replace = repro.os.replace

    def corrupt_install(src, dst):
        replace(src, dst)
        Path(dst).write_bytes(b"{partial")

    monkeypatch.setattr(repro.os, "replace", corrupt_install)
    with pytest.raises(InvalidRecord, match="Installed build binding"):
        repro.publish_binding(serialized, path.read_bytes(), path, root)
    assert repro.verify_build(path, project_root=root)["integrity"] == "invalid"


def test_comparison_rechecks_first_execution_after_capturing_second(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    left, right = _build(a, monkeypatch), _build(b, monkeypatch)
    read = repro._Captures._read_confined
    fired = False

    def change_left_while_reading_right(captures, target):
        nonlocal fired
        raw = read(captures, target)
        if target == right and not fired:
            fired = True
            (a / "docs/evidence.md").write_bytes(b"drift during comparison")
        return raw

    monkeypatch.setattr(repro._Captures, "_read_confined", change_left_while_reading_right)
    result = repro.compare_builds(left, right, left_root=a, right_root=b)
    assert fired and result["comparison"] == "unsupported"
    assert result["left"]["integrity"] == "invalid"


def test_missing_artifact_and_wrong_root_never_prove_equivalence(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    assert repro.verify_build(path, project_root=unrelated)["integrity"] == "unsupported"
    (root / "docs/evidence.md").unlink()
    assert repro.verify_build(path, project_root=root)["integrity"] == "invalid"


@pytest.mark.parametrize("where", ["envelope", "build"])
def test_nul_locators_return_invalid_evidence_instead_of_crashing(tmp_path, monkeypatch, where):
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    binding_path = path.with_name(repro.BINDING_NAME)
    binding = json.loads(binding_path.read_bytes())
    if where == "envelope":
        binding["envelope"]["records"][0]["path"] = "bad\x00path"
    else:
        build = json.loads(path.read_bytes())
        build["manifest_path"] = "bad\x00path"
        raw = json.dumps(build).encode()
        path.write_bytes(raw)
        binding["envelope"]["records"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    binding_path.write_bytes(canonical_json(binding))
    result = repro.compare_builds(path, path, left_root=root, right_root=root)
    assert result["comparison"] == "unsupported"
    assert result["left"]["integrity"] == "invalid"
    assert "NUL" in result["left"]["reason"]


@pytest.mark.parametrize("swap", ["leaf", "parent"])
def test_symlink_replacement_cannot_read_outside_root_even_before_drift_check(tmp_path, monkeypatch, swap):
    import shutil
    root = tmp_path / "project"
    path = _build(root, monkeypatch)
    target = root / "docs/blueprint.md"
    outside = tmp_path / "outside"
    if swap == "leaf":
        outside.write_bytes(target.read_bytes())
    else:
        shutil.copytree(root / "docs", outside)
    read = repro._Captures._read_confined
    fired = False
    leaked = False

    def swap_after_resolution(captures, resolved):
        nonlocal fired, leaked
        if resolved == target and not fired:
            fired = True
            if swap == "leaf":
                target.unlink()
                target.symlink_to(outside)
            else:
                (root / "docs").rename(root / "retained-docs")
                (root / "docs").symlink_to(outside, target_is_directory=True)
            raw = read(captures, resolved)
            leaked = True  # Must not reach this, even when outside bytes match.
            return raw
        return read(captures, resolved)

    monkeypatch.setattr(repro._Captures, "_read_confined", swap_after_resolution)
    result = repro.verify_build(path, project_root=root)
    assert fired and not leaked
    assert result["integrity"] == "invalid", result


@pytest.mark.parametrize("state,code", [("equivalent", 0), ("different", 1), ("unsupported", 2), ("invalid", 3)])
def test_cli_distinguishes_result_comparison_from_integrity(tmp_path, monkeypatch, capsys, state, code):
    from hermeneia.cli.main import main
    a, b = tmp_path / "a", tmp_path / "b"
    mutate = None
    if state == "different":
        mutate = lambda root: (root / "docs/paper.md").write_bytes(b"changed")
    left, right = _build(a, monkeypatch), _build(b, monkeypatch, mutate=mutate)
    if state == "unsupported":
        right.with_name(repro.BINDING_NAME).unlink()
    elif state == "invalid":
        right.write_bytes(right.read_bytes() + b"\n")
    capsys.readouterr()
    monkeypatch.setattr("sys.argv", ["herm", "build-compare", str(left), str(right),
                                    "--left-root", str(a), "--right-root", str(b)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == code
    result = json.loads(capsys.readouterr().out)
    assert result["comparison"] == ("unsupported" if state == "invalid" else state)
