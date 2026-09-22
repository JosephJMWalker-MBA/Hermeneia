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
