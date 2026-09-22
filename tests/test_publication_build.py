"""Exact emitted-byte provenance and single-artifact publication failures."""
from __future__ import annotations

import hashlib
import json
import os
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
    assert sorted(p.name for p in output.iterdir()) == ["build.json", "coverage.md", "rc_log.md", "release_decision.md", "white_paper.md"]
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
