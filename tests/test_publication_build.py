"""Exact emitted-byte provenance and single-artifact publication failures."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from hermeneia.cli import build_cmd


# Include multiple hash chunks, CRLF, Unicode, and non-text bytes. No decoding
# or newline normalization is allowed between source and publication.
PAPER = b"\xef\xbb\xbf# Publication\r\ncaf\xc3\xa9\x00\xff\n" * 4000
CHANGED = b"A different version, written after the copy.\n"
OLD = b"Previous publication.\n"


@pytest.fixture
def publication(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "manuscript.md"
    source.write_bytes(PAPER)
    blueprint = root / "blueprint.md"
    blueprint.write_bytes(b"# Ratified fixture Blueprint\n")
    manifest = {
        "build_id": "compile-byte-provenance",
        "compiled_artifact": source.name,
        "blueprint": blueprint.name,
        "blueprint_id": "test-blueprint",
        "blueprint_status": "ratified",
        "source_artifacts": [
            {"path": blueprint.name, "tags": ["thesis"], "status": "ratified", "role": "primary-contract"},
        ],
        "sections": [{"section": "abstract", "required_tags": ["thesis"]}],
    }
    manifest_path = root / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest))
    output = root / "publication"
    output.mkdir()
    return root, source, manifest, manifest_path, output


@pytest.mark.parametrize("payload", [b"", PAPER])
def test_compile_records_exact_emitted_bytes(publication, payload):
    root, source, manifest, _, output = publication
    source.write_bytes(payload)

    record = build_cmd._stage_compile(manifest, root, output)

    emitted = (output / "white_paper.md").read_bytes()
    assert emitted == payload
    assert record == {
        "source": str(source),
        "sha256": hashlib.sha256(emitted).hexdigest(),
        "method": "copy",
        "note": "v0.1 copies existing compiled artifact. Future versions drive Artist.",
    }
    assert sorted(p.name for p in output.iterdir()) == ["white_paper.md"]


@pytest.mark.parametrize("source_change", ["rewrite", "remove"])
def test_compile_hash_does_not_follow_source_after_copy(publication, monkeypatch, source_change):
    root, source, manifest, _, output = publication
    real_copy = build_cmd.shutil.copy2

    def copy_then_change_source(src, dest):
        result = real_copy(src, dest)
        if source_change == "rewrite":
            source.write_bytes(CHANGED)
        else:
            source.unlink()
        return result

    monkeypatch.setattr(build_cmd.shutil, "copy2", copy_then_change_source)

    record = build_cmd._stage_compile(manifest, root, output)

    emitted = (output / "white_paper.md").read_bytes()
    assert emitted == PAPER
    assert record["sha256"] == hashlib.sha256(emitted).hexdigest()


@pytest.mark.parametrize("prior_output", [False, True])
def test_partial_copy_failure_never_publishes_partial_bytes(publication, monkeypatch, prior_output):
    root, source, manifest, _, output = publication
    dest = output / "white_paper.md"
    if prior_output:
        dest.write_bytes(OLD)

    def partial_copy(src, target):
        Path(target).write_bytes(PAPER[:32])
        raise OSError("injected copy failure")

    monkeypatch.setattr(build_cmd.shutil, "copy2", partial_copy)

    with pytest.raises(build_cmd.BuildError, match="injected copy failure"):
        build_cmd._stage_compile(manifest, root, output)

    assert source.read_bytes() == PAPER
    assert (dest.read_bytes() if dest.exists() else None) == (OLD if prior_output else None)
    assert sorted(p.name for p in output.iterdir()) == (["white_paper.md"] if prior_output else [])


def test_compile_publishes_complete_staged_file_with_one_replace(publication, monkeypatch):
    root, _, manifest, _, output = publication
    dest = output / "white_paper.md"
    dest.write_bytes(OLD)
    real_copy = build_cmd.shutil.copy2
    real_replace = os.replace
    events = []

    def checked_copy(src, target):
        target = Path(target)
        assert target != dest
        assert target.parent.stat().st_dev == output.stat().st_dev
        assert dest.read_bytes() == OLD
        result = real_copy(src, target)
        assert dest.read_bytes() == OLD
        events.append("copy")
        return result

    def checked_replace(src, target):
        assert Path(target) == dest
        assert Path(src).read_bytes() == PAPER
        assert dest.read_bytes() == OLD
        result = real_replace(src, target)
        events.append("replace")
        return result

    monkeypatch.setattr(build_cmd.shutil, "copy2", checked_copy)
    monkeypatch.setattr(os, "replace", checked_replace)

    record = build_cmd._stage_compile(manifest, root, output)

    assert events == ["copy", "replace"]
    assert record["sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()
    assert sorted(p.name for p in output.iterdir()) == ["white_paper.md"]


@pytest.mark.parametrize("failure_point", ["staged_hash", "replace"])
def test_failure_before_replace_preserves_prior_output(publication, monkeypatch, failure_point):
    root, source, manifest, _, output = publication
    dest = output / "white_paper.md"
    dest.write_bytes(OLD)
    real_hash = build_cmd._sha256

    def fail_staged_hash(path):
        if Path(path) != source:
            raise OSError("injected staged hash failure")
        return real_hash(path)

    def fail_replace(src, target):
        raise OSError("injected replace failure")

    if failure_point == "staged_hash":
        monkeypatch.setattr(build_cmd, "_sha256", fail_staged_hash)
    else:
        monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(build_cmd.BuildError, match="injected"):
        build_cmd._stage_compile(manifest, root, output)

    assert dest.read_bytes() == OLD
    assert source.read_bytes() == PAPER
    assert sorted(p.name for p in output.iterdir()) == ["white_paper.md"]


@pytest.mark.parametrize("failure_point", ["before_replace", "after_replace", "readback"])
def test_unverified_published_bytes_fail_closed(publication, monkeypatch, capsys, failure_point):
    root, source, _, manifest_path, output = publication
    dest = output / "white_paper.md"
    real_replace = os.replace
    real_hash = build_cmd._sha256

    def corrupt_replace(src, target):
        if failure_point == "before_replace":
            Path(src).write_bytes(CHANGED)
        result = real_replace(src, target)
        if failure_point == "after_replace":
            Path(target).write_bytes(CHANGED)
        return result

    def fail_readback(path):
        if Path(path) == dest:
            raise OSError("injected emitted-file read failure")
        return real_hash(path)

    monkeypatch.setattr(os, "replace", corrupt_replace)
    if failure_point == "readback":
        monkeypatch.setattr(build_cmd, "_sha256", fail_readback)
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        build_cmd.cmd_build(str(manifest_path), str(output))

    assert exc.value.code == 1
    assert not (output / "build.json").exists()
    assert source.read_bytes() == PAPER
    assert sorted(p.name for p in output.iterdir()) == ["white_paper.md"]
    stdout = capsys.readouterr().out
    assert "Publication Build Complete" not in stdout
    assert "No outputs written" not in stdout
    expected_error = "read failure" if failure_point == "readback" else "hash mismatch"
    assert expected_error in stdout.lower()


@pytest.mark.parametrize("change", ["overwrite", "remove"])
def test_build_refuses_drift_between_compile_and_record(publication, monkeypatch, capsys, change):
    root, _, _, manifest_path, output = publication
    dest = output / "white_paper.md"
    previous_record = b'{"previous_build":"keep historical record"}'
    (output / "build.json").write_bytes(previous_record)
    real_report = build_cmd._stage_steward_report

    def report_then_change_artifact(*args):
        real_report(*args)
        if change == "overwrite":
            dest.write_bytes(CHANGED)
        else:
            dest.unlink()

    monkeypatch.setattr(build_cmd, "_stage_steward_report", report_then_change_artifact)
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        build_cmd.cmd_build(str(manifest_path), str(output))

    assert exc.value.code == 1
    assert (output / "build.json").read_bytes() == previous_record
    assert "Publication Build Complete" not in capsys.readouterr().out


@pytest.mark.parametrize("alias", ["same_path", "hardlink", "symlink"])
def test_compile_refuses_source_destination_alias(publication, alias):
    root, source, manifest, _, output = publication
    dest = output / "white_paper.md"
    if alias == "same_path":
        dest.write_bytes(PAPER)
        manifest["compiled_artifact"] = str(dest.relative_to(root))
    elif alias == "hardlink":
        dest.hardlink_to(source)
    else:
        dest.symlink_to(source)

    with pytest.raises(build_cmd.BuildError, match="same file"):
        build_cmd._stage_compile(manifest, root, output)

    assert dest.read_bytes() == source.read_bytes() == PAPER
    assert sorted(p.name for p in output.iterdir()) == ["white_paper.md"]


def test_compile_replaces_destination_symlink_without_writing_its_target(publication):
    root, _, manifest, _, output = publication
    unrelated = root / "unrelated.md"
    unrelated.write_bytes(OLD)
    dest = output / "white_paper.md"
    dest.symlink_to(unrelated)

    record = build_cmd._stage_compile(manifest, root, output)

    assert unrelated.read_bytes() == OLD
    assert not dest.is_symlink()
    assert dest.read_bytes() == PAPER
    assert record["sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()


def test_build_preserves_provenance_and_output_contract(publication, monkeypatch):
    root, source, _, manifest_path, output = publication
    monkeypatch.chdir(root)
    before = {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}

    build_cmd.cmd_build(str(manifest_path), str(output))

    record = json.loads((output / "build.json").read_text())
    assert record["compile"]["sha256"] == hashlib.sha256((output / "white_paper.md").read_bytes()).hexdigest()
    assert record["compile"]["source"] == str(source)
    assert record["compile"]["method"] == "copy"
    assert record["blueprint"]["sha256"] == hashlib.sha256((root / "blueprint.md").read_bytes()).hexdigest()
    assert record["manifest_hash"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert record["outcome"] == "pass"
    assert record["release_ratification"] == "pending"
    assert sorted(p.name for p in output.iterdir()) == ["build.json", "build.reproducibility.json", "coverage.md", "rc_log.md", "release_decision.md", "white_paper.md"]
    assert record["outputs"]["white_paper"] == str(output / "white_paper.md")
    assert {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()} == before


def test_dry_run_creates_no_staging_or_output(publication, monkeypatch):
    root, _, _, manifest_path, _ = publication
    output = root / "dry-run-output"
    monkeypatch.chdir(root)

    build_cmd.cmd_build(str(manifest_path), str(output), dry_run=True)

    assert not output.exists()


@pytest.mark.parametrize("mutation_point", ["after_capture", "before_parse", "after_parse"])
def test_manifest_snapshot_keeps_captured_interpretation_and_digest(publication, monkeypatch, mutation_point):
    _, _, manifest, manifest_path, _ = publication
    captured = manifest_path.read_bytes()
    replacement = captured.replace(b"compile-byte-provenance", b"replacement-build")
    real_read = Path.read_bytes
    real_parse = build_cmd.yaml.safe_load
    reads = []

    def capture_then_mutate(path):
        data = real_read(path)
        if path == manifest_path:
            reads.append(data)
            if mutation_point == "after_capture":
                manifest_path.write_bytes(replacement)
        return data

    def parse_then_mutate(stream):
        if mutation_point == "before_parse":
            manifest_path.write_bytes(replacement)
        parsed = real_parse(stream)
        if mutation_point == "after_parse":
            manifest_path.write_bytes(replacement)
        return parsed

    monkeypatch.setattr(Path, "read_bytes", capture_then_mutate)
    monkeypatch.setattr(build_cmd.yaml, "safe_load", parse_then_mutate)

    interpreted, digest = build_cmd._stage_load_manifest(manifest_path)

    assert interpreted == manifest
    assert digest == hashlib.sha256(captured).hexdigest()
    assert reads == [captured], "Interpretation and identity must use one capture"
    assert real_read(manifest_path) == replacement


@pytest.mark.parametrize("payload", [
    b"broken: [unclosed",
    b"build_id: \xff\n",
    b"build_id: bad\x00value\n",
    b"[]\n",
    b"build_id: missing-required-fields\n",
])
def test_invalid_captured_manifest_cannot_be_replaced_by_valid_reread(publication, monkeypatch, payload):
    _, _, _, manifest_path, _ = publication
    valid = manifest_path.read_bytes()
    manifest_path.write_bytes(payload)
    real_read = Path.read_bytes
    reads = []

    def capture_invalid_then_replace(path):
        data = real_read(path)
        if path == manifest_path:
            reads.append(data)
            manifest_path.write_bytes(valid)
        return data

    monkeypatch.setattr(Path, "read_bytes", capture_invalid_then_replace)

    with pytest.raises(build_cmd.BuildError):
        build_cmd._stage_load_manifest(manifest_path)

    assert reads == [payload]
    assert real_read(manifest_path) == valid


def test_manifest_read_failure_is_not_retried(publication, monkeypatch):
    _, _, _, manifest_path, _ = publication
    reads = []

    def fail_read(path):
        reads.append(path)
        raise PermissionError("injected manifest read failure")

    monkeypatch.setattr(Path, "read_bytes", fail_read)

    with pytest.raises(build_cmd.BuildError, match="injected manifest read failure"):
        build_cmd._stage_load_manifest(manifest_path)

    assert reads == [manifest_path]


def test_manifest_capture_preserves_existing_text_decoding(publication):
    _, _, _, manifest_path, _ = publication
    # Passing these bytes directly to PyYAML would newly accept UTF-16.
    # The existing open(path) text-decoding contract rejects this input.
    manifest_path.write_bytes(manifest_path.read_text().encode("utf-16"))
    with pytest.raises((UnicodeError, yaml.YAMLError)):
        with open(manifest_path) as stream:
            yaml.safe_load(stream)

    with pytest.raises(build_cmd.BuildError, match="Manifest YAML malformed"):
        build_cmd._stage_load_manifest(manifest_path)


@pytest.mark.parametrize("change", ["replace", "remove", "comment_only"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_manifest_drift_before_outputs_fails_closed(publication, monkeypatch, change, dry_run):
    root, _, _, manifest_path, output = publication
    original = manifest_path.read_bytes()
    real_coverage = build_cmd._stage_coverage

    def coverage_then_change_manifest(*args):
        result = real_coverage(*args)
        if change == "remove":
            manifest_path.unlink()
        elif change == "comment_only":
            manifest_path.write_bytes(original + b"# different bytes, same meaning\n")
        else:
            replacement = manifest_path.with_suffix(".replacement")
            replacement.write_bytes(original.replace(b"compile-byte-provenance", b"new-build"))
            os.replace(replacement, manifest_path)
        return result

    monkeypatch.setattr(build_cmd, "_stage_coverage", coverage_then_change_manifest)
    monkeypatch.chdir(root)
    new_output = output / "not-created"

    with pytest.raises(SystemExit) as exc:
        build_cmd.cmd_build(str(manifest_path), str(new_output), dry_run=dry_run)

    assert exc.value.code == 1
    assert not new_output.exists()


@pytest.mark.parametrize("change", ["replace", "remove", "unreadable"])
def test_manifest_drift_before_record_preserves_previous_record(publication, monkeypatch, capsys, change):
    root, _, _, manifest_path, output = publication
    original = manifest_path.read_bytes()
    previous = b'{"previous_build":"preserve existing provenance"}'
    (output / "build.json").write_bytes(previous)
    real_report = build_cmd._stage_steward_report
    real_hash = build_cmd._sha256

    def fail_manifest_verification(path):
        if path == manifest_path:
            raise PermissionError("injected manifest verification failure")
        return real_hash(path)

    def report_then_change_manifest(*args):
        real_report(*args)
        if change == "remove":
            manifest_path.unlink()
        elif change == "unreadable":
            monkeypatch.setattr(build_cmd, "_sha256", fail_manifest_verification)
        else:
            manifest_path.write_bytes(original.replace(b"compile-byte-provenance", b"replacement-build"))

    monkeypatch.setattr(build_cmd, "_stage_steward_report", report_then_change_manifest)
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        build_cmd.cmd_build(str(manifest_path), str(output))

    assert exc.value.code == 1
    assert (output / "build.json").read_bytes() == previous
    assert "Publication Build Complete" not in capsys.readouterr().out


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_manifest_hash_is_exact_capture_not_yaml_reserialization(publication, monkeypatch, line_ending):
    root, _, _, manifest_path, output = publication
    text = manifest_path.read_text() + "# Spacing, comments, and Unicode: café\n\n"
    captured = b"\xef\xbb\xbf" + text.replace("\n", line_ending).encode("utf-8")
    manifest_path.write_bytes(captured)
    monkeypatch.chdir(root)

    build_cmd.cmd_build(str(manifest_path), str(output))

    record = json.loads((output / "build.json").read_text())
    assert record["manifest_hash"] == hashlib.sha256(captured).hexdigest()
    assert manifest_path.read_bytes() == captured
    assert record["build_id"] == "compile-byte-provenance"


def test_downstream_paths_and_metadata_use_captured_manifest(publication, monkeypatch):
    root, source, manifest, manifest_path, output = publication
    manifest.update(status="RC-original", ratification="pending")
    captured = yaml.safe_dump(manifest).encode()
    manifest_path.write_bytes(captured)
    alternate = dict(manifest, build_id="wrong-build", compiled_artifact="wrong-paper.md",
                     blueprint="wrong-blueprint.md", blueprint_id="wrong-id",
                     status="wrong-status", ratification="wrong-ratification",
                     source_artifacts=[], sections=[])
    replacement = yaml.safe_dump(alternate).encode()
    real_parse = build_cmd.yaml.safe_load
    real_blueprint = build_cmd._stage_resolve_blueprint

    def change_during_parse(stream):
        manifest_path.write_bytes(replacement)
        return real_parse(stream)

    def resolve_captured_then_restore(interpreted, project_root):
        assert interpreted == manifest
        # The current file remains divergent while this stage resolves paths.
        assert manifest_path.read_bytes() == replacement
        result = real_blueprint(interpreted, project_root)
        manifest_path.write_bytes(captured)
        return result

    monkeypatch.setattr(build_cmd.yaml, "safe_load", change_during_parse)
    monkeypatch.setattr(build_cmd, "_stage_resolve_blueprint", resolve_captured_then_restore)
    monkeypatch.chdir(root)

    build_cmd.cmd_build(str(manifest_path), str(output))

    record = json.loads((output / "build.json").read_text())
    assert record["manifest_hash"] == hashlib.sha256(captured).hexdigest()
    assert record["build_id"] == manifest["build_id"]
    assert record["compile"]["source"] == str(source)
    assert record["blueprint"]["id"] == manifest["blueprint_id"]
    assert record["blueprint"]["path"] == str(root / manifest["blueprint"])
    assert record["source_artifacts"][0]["path"] == manifest["source_artifacts"][0]["path"]
    assert record["coverage"]["section_detail"][0]["section"] == "abstract"
    assert record["release_status"] == "RC-original"
    assert record["release_ratification"] == "pending"


@pytest.fixture
def record_emission(publication):
    root, _, manifest, manifest_path, output = publication
    resolved, tag_index, warnings = build_cmd._stage_resolve_tags(manifest, root)
    coverage, _ = build_cmd._stage_coverage(manifest, tag_index)
    arguments = dict(
        manifest=manifest, manifest_path=manifest_path,
        manifest_hash=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        blueprint=build_cmd._stage_resolve_blueprint(manifest, root),
        resolved_artifacts=resolved, coverage_results=coverage,
        compile_record=build_cmd._stage_compile(manifest, root, output),
        warnings=warnings, output_dir=output,
    )

    def emit(**changes):
        return build_cmd._emit_build_json(**(arguments | changes))

    emit()
    destination = output / "build.json"
    return emit, destination, destination.read_bytes()


@pytest.mark.parametrize("failure", ["unsupported", "circular", "encoding"])
@pytest.mark.parametrize("prior_record", [False, True])
def test_build_record_serialization_failure_preserves_prior(record_emission, monkeypatch, failure, prior_record):
    emit, destination, previous = record_emission
    if not prior_record:
        destination.unlink()
    value = object()
    if failure == "circular":
        value = []
        value.append(value)
    elif failure == "encoding":
        value = "\ud800"

    def no_staging(*args, **kwargs):
        pytest.fail("Serialization must finish before staging or touching the destination")

    monkeypatch.setattr(build_cmd.tempfile, "TemporaryDirectory", no_staging)
    with pytest.raises(build_cmd.BuildError):
        emit(hermeneia_version=value)

    assert (destination.read_bytes() if destination.exists() else None) == (previous if prior_record else None)


@pytest.mark.parametrize("prior_record", [False, True])
@pytest.mark.parametrize("failure", ["staging", "open", "write", "partial", "short", "corrupt", "flush", "close", "read", "replace"])
def test_build_record_pre_replace_failure_preserves_prior(record_emission, monkeypatch, prior_record, failure):
    emit, destination, previous = record_emission
    if not prior_record:
        destination.unlink()
    expected = previous if prior_record else None
    real_open = Path.open
    real_read = Path.read_bytes
    observations = []

    def observe():
        observed = destination.read_bytes() if destination.exists() else None
        observations.append(observed)

    class FailingWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def write(self, data):
            observe()
            if failure == "write":
                raise OSError("injected write failure")
            if failure in {"partial", "short"}:
                count = self.stream.write(data[:16])
                self.stream.flush()
                observe()
                if failure == "partial":
                    raise OSError("injected partial write failure")
                return count
            if failure == "corrupt":
                return self.stream.write(b" " * len(data))
            return self.stream.write(data)

        def flush(self):
            if failure == "flush":
                raise OSError("injected flush failure")
            return self.stream.flush()

        def __exit__(self, *args):
            result = self.stream.__exit__(*args)
            if failure in {"flush", "close"}:
                raise OSError(f"injected {failure} failure")
            return result

    def failing_open(path, mode="r", *args, **kwargs):
        if path.name == "build.json" and "w" in mode:
            if failure == "open":
                raise OSError("injected open failure")
            return FailingWriter(real_open(path, mode, *args, **kwargs))
        return real_open(path, mode, *args, **kwargs)

    def fail_staging(*args, **kwargs):
        raise OSError("injected staging failure")

    def fail_replace(*args):
        observe()
        raise OSError("injected replacement failure")

    def fail_staged_read(path):
        if path.name == "build.json" and path != destination:
            raise OSError("injected staged read failure")
        return real_read(path)

    monkeypatch.setattr(Path, "open", failing_open)
    if failure == "staging":
        monkeypatch.setattr(build_cmd.tempfile, "TemporaryDirectory", fail_staging)
    if failure == "replace":
        monkeypatch.setattr(os, "replace", fail_replace)
    if failure == "read":
        monkeypatch.setattr(Path, "read_bytes", fail_staged_read)

    with pytest.raises(build_cmd.BuildError):
        emit()

    observe()
    assert observations and all(observed == expected for observed in observations)
    assert not list(destination.parent.glob(".herm-build-*"))


def test_build_record_complete_bytes_visible_only_after_replace(record_emission, monkeypatch):
    emit, destination, previous = record_emission
    real_open = Path.open
    real_replace = os.replace
    real_dumps = json.dumps
    intended = []
    writers = []
    events = []

    def capture_serialization(value, **kwargs):
        text = real_dumps(value, **kwargs)
        intended.append(text.encode("utf-8"))
        events.append("serialize")
        return text

    def checked_open(path, mode="r", *args, **kwargs):
        if path.name == "build.json" and "w" in mode:
            assert intended, "Serialization must precede every destination or staging write"
            assert path != destination
            assert path.parent.parent == destination.parent
            assert path.parent.stat().st_mode & 0o077 == 0
            assert destination.read_bytes() == previous
            stream = real_open(path, mode, *args, **kwargs)
            writers.append(stream)
            events.append("stage")
            return stream
        return real_open(path, mode, *args, **kwargs)

    def checked_replace(source, target):
        assert Path(target) == destination
        assert all(stream.closed for stream in writers)
        assert Path(source).read_bytes() == intended[0]
        assert destination.read_bytes() == previous
        result = real_replace(source, target)
        assert destination.read_bytes() == intended[0]
        events.append("replace")
        return result

    monkeypatch.setattr(build_cmd.json, "dumps", capture_serialization)
    monkeypatch.setattr(Path, "open", checked_open)
    monkeypatch.setattr(os, "replace", checked_replace)
    with destination.open("rb") as prior_reader:
        record = emit(hermeneia_version="test-café")
        assert prior_reader.read() == previous

    assert events == ["serialize", "stage", "replace"]
    assert destination.read_bytes() == intended[0]
    assert json.loads(intended[0]) == record
    assert not intended[0].endswith(b"\n")
    assert not list(destination.parent.glob(".herm-build-*"))


@pytest.mark.parametrize("failure", ["corrupt", "unreadable", "replace_then_raise"])
def test_build_record_installed_verification_fails_closed(record_emission, monkeypatch, failure):
    emit, destination, previous = record_emission
    real_replace = os.replace
    real_read = Path.read_bytes
    installed = []
    replacement_record = b'{"another_complete_record":true}'

    def replace_then_fault(source, target):
        result = real_replace(source, target)
        installed.append(real_read(destination))
        if failure == "replace_then_raise":
            raise OSError("injected error after replacement")
        if failure == "corrupt":
            # Model an external writer replacing the record with other valid JSON.
            destination.write_bytes(replacement_record)
        return result

    def unreadable_installed(path):
        if path == destination and installed:
            raise OSError("injected installed read failure")
        return real_read(path)

    monkeypatch.setattr(os, "replace", replace_then_fault)
    if failure == "unreadable":
        monkeypatch.setattr(Path, "read_bytes", unreadable_installed)
    with pytest.raises(build_cmd.BuildError):
        emit(hermeneia_version="new-record")

    assert len(installed) == 1
    assert installed[0] != previous
    assert json.loads(installed[0])["build_id"] == "compile-byte-provenance"
    assert real_read(destination) == (replacement_record if failure == "corrupt" else installed[0])
    assert not list(destination.parent.glob(".herm-build-*"))


@pytest.mark.parametrize("artifact", ["manifest.yaml", "white_paper.md"])
@pytest.mark.parametrize("mutation_point", ["serialization", "staging"])
def test_build_record_rechecks_input_provenance_after_preparation(record_emission, publication, monkeypatch, artifact, mutation_point):
    emit, destination, previous = record_emission
    root, _, _, manifest_path, _ = publication
    target = manifest_path if artifact == "manifest.yaml" else destination.parent / artifact
    real_dumps = json.dumps
    real_read = Path.read_bytes

    def serialize_then_change_input(*args, **kwargs):
        text = real_dumps(*args, **kwargs)
        target.write_bytes(b"Changed during record preparation")
        return text

    def read_staging_then_change_input(path):
        data = real_read(path)
        if path.name == "build.json" and path != destination:
            target.write_bytes(b"Changed during record preparation")
        return data

    if mutation_point == "serialization":
        monkeypatch.setattr(build_cmd.json, "dumps", serialize_then_change_input)
    else:
        monkeypatch.setattr(Path, "read_bytes", read_staging_then_change_input)
    with pytest.raises(build_cmd.BuildError, match="[Hh]ash mismatch"):
        emit()
    assert destination.read_bytes() == previous
    assert not list(destination.parent.glob(".herm-build-*"))


@pytest.mark.parametrize("alias", ["symlink", "hardlink"])
def test_build_record_replacement_leaves_linked_target_untouched(record_emission, alias):
    emit, destination, previous = record_emission
    target = destination.parent / "linked-record.json"
    target.write_bytes(previous)
    destination.unlink()
    if alias == "symlink":
        destination.symlink_to(target)
    else:
        destination.hardlink_to(target)

    emit(hermeneia_version="new-record")

    assert target.read_bytes() == previous
    assert not destination.is_symlink()
    assert json.loads(destination.read_bytes())["hermeneia_version"] == "new-record"


@pytest.mark.parametrize("prior_record", [False, True])
def test_build_record_process_interruption_never_exposes_partial_bytes(record_emission, publication, prior_record):
    _, destination, previous = record_emission
    root, _, _, manifest_path, output = publication
    if not prior_record:
        destination.unlink()
    script = '''
import os
from pathlib import Path
from hermeneia.cli import build_cmd
real_open = Path.open
class InterruptedWriter:
    def __init__(self, stream): self.stream = stream
    def __enter__(self): return self
    def __exit__(self, *args): return self.stream.__exit__(*args)
    def write(self, data):
        self.stream.write(data[:16])
        self.stream.flush()
        os._exit(73)
def interrupt_open(path, mode="r", *args, **kwargs):
    stream = real_open(path, mode, *args, **kwargs)
    if path.name == "build.json" and "w" in mode:
        return InterruptedWriter(stream)
    return stream
Path.open = interrupt_open
build_cmd.cmd_build("manifest.yaml", "publication")
'''
    environment = dict(os.environ, PYTHONPATH=str(Path(build_cmd.__file__).resolve().parents[2]))
    result = subprocess.run([sys.executable, "-c", script], cwd=root, env=environment,
                            capture_output=True, text=True, timeout=15)

    assert result.returncode == 73, result.stderr
    assert (destination.read_bytes() if destination.exists() else None) == (previous if prior_record else None)
    partial_staging = list(output.glob(".herm-build-*/build.json"))
    assert len(partial_staging) == 1
    assert len(partial_staging[0].read_bytes()) == 16


@pytest.mark.parametrize("failure", ["serialization", "open", "replace", "readback"])
def test_build_record_failure_never_announces_cli_success(record_emission, publication, monkeypatch, capsys, failure):
    _, destination, previous = record_emission
    root, _, _, manifest_path, output = publication
    real_open = Path.open
    real_replace = os.replace
    real_read = Path.read_bytes

    def fail_serialization(*args, **kwargs):
        raise TypeError("injected record serialization failure")

    def fail_open(path, mode="r", *args, **kwargs):
        if path.name == "build.json" and "w" in mode:
            raise OSError("injected record open failure")
        return real_open(path, mode, *args, **kwargs)

    def fail_replace(source, target):
        if Path(target) == destination:
            raise OSError("injected record replacement failure")
        return real_replace(source, target)

    def fail_readback(path):
        if path == destination:
            raise OSError("injected record readback failure")
        return real_read(path)

    if failure == "serialization":
        monkeypatch.setattr(build_cmd.json, "dumps", fail_serialization)
    elif failure == "open":
        monkeypatch.setattr(Path, "open", fail_open)
    elif failure == "replace":
        monkeypatch.setattr(os, "replace", fail_replace)
    else:
        monkeypatch.setattr(Path, "read_bytes", fail_readback)
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        build_cmd.cmd_build(str(manifest_path), str(output))

    assert exc.value.code == 1
    stdout = capsys.readouterr().out
    assert "Publication Build Complete" not in stdout
    assert "Build failed" in stdout
    assert "injected record" in stdout
    if failure != "readback":
        assert real_read(destination) == previous
    else:
        assert json.loads(real_read(destination))["build_id"] == "compile-byte-provenance"
    assert not list(output.glob(".herm-build-*"))
