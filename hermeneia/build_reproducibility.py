"""Exact-byte build bindings and read-only, root-confined v1 comparison.

This module grants no publication authority and implements no legacy migration,
release identity or preservation-package equivalence. Digests bind evidence;
they do not authenticate the writer of an entirely replaced evidence set.
"""
from __future__ import annotations

import hashlib
import io
import os
import stat
import tempfile
from pathlib import Path

import yaml

from hermeneia.build_core import (
    BINDING_SCHEMA, InvalidRecord, UnsupportedProfile, canonical_json,
    core_digest, project_core, strict_json_loads, validate_portable_reference,
)

BINDING_NAME = "build.reproducibility.json"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class _Captures:
    """Parse/hash the same captures; subsequent reads only detect drift."""

    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        self.files: dict[Path, tuple[Path, bytes]] = {}
        self.content: dict[Path, bytes] = {}

    def location(self, value: str | Path) -> tuple[Path, Path]:
        if not isinstance(value, (str, Path)) or not str(value) or "\x00" in str(value):
            raise InvalidRecord("Invalid empty or NUL-containing artifact locator")
        path = Path(value)
        if not path.is_absolute():
            path = self.root / path
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise UnsupportedProfile(f"Locator escapes supplied artifact root: {path}")
        return path, resolved

    def _read_confined(self, resolved: Path) -> bytes:
        # Walk the resolved absolute path through directory descriptors. A
        # symlink introduced in either a parent or the leaf between resolution
        # and opening must not grant access outside the caller's artifact root.
        if (os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW")
                or not hasattr(os, "O_DIRECTORY")):
            raise UnsupportedProfile("Platform lacks required confined file-open support")
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory = os.open(resolved.anchor, directory_flags)
        try:
            for component in resolved.parts[1:-1]:
                child = os.open(component, directory_flags, dir_fd=directory)
                os.close(directory)
                directory = child
            descriptor = os.open(resolved.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 dir_fd=directory)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise InvalidRecord(f"Required artifact is not a regular file: {resolved}")
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    return stream.read()
            finally:
                os.close(descriptor)
        finally:
            os.close(directory)

    def read(self, value: str | Path) -> bytes:
        path, resolved = self.location(value)
        if path in self.files:
            previous, raw = self.files[path]
            if previous != resolved:
                raise InvalidRecord(f"Locator changed during capture: {path}")
            return raw
        if resolved not in self.content:
            self.content[resolved] = self._read_confined(resolved)
        raw = self.content[resolved]
        self.files[path] = (resolved, raw)
        return raw

    def unchanged(self) -> None:
        for path, (resolved, raw) in self.files.items():
            if self.location(path)[1] != resolved or self._read_confined(resolved) != raw:
                raise InvalidRecord(f"Artifact changed during verification: {path}")


class _ManifestLoader(yaml.SafeLoader):
    """Ambiguous YAML keys are not admitted to the new comparison profile."""


def _manifest_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            if key in result:
                raise UnsupportedProfile("Duplicate/merged manifest keys need an explicit profile")
            result[key] = loader.construct_object(value_node, deep=deep)
        except TypeError as exc:
            raise UnsupportedProfile("Unsupported manifest mapping key") from exc
    return result


_ManifestLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _manifest_mapping)


def _manifest(raw: bytes) -> dict:
    try:
        # Preserve the build loader's text decoding/newline interpretation, but
        # derive it only from the byte capture whose digest was already checked.
        with io.TextIOWrapper(io.BytesIO(raw)) as stream:
            value = yaml.load(stream, Loader=_ManifestLoader)
    except (yaml.YAMLError, UnicodeError, RecursionError) as exc:
        raise InvalidRecord(f"Captured manifest cannot be interpreted: {exc}") from exc
    if not isinstance(value, dict):
        raise InvalidRecord("Captured manifest is not a mapping")
    return value


def _same(first, second, label: str) -> None:
    if canonical_json(first) != canonical_json(second):
        raise InvalidRecord(f"{label} disagrees with captured provenance")


def _verify_result(core: dict, raw: bytes, build_path: Path, captures: _Captures) -> None:
    build = strict_json_loads(raw)
    expected = project_core(build, core["result"]["historical_outputs"])
    _same(core, expected, "Core/build record")
    if captures.location(build["outputs"]["build_json"])[1] != captures.location(build_path)[1]:
        raise InvalidRecord("Build record's self-location disagrees with supplied record")
    for locator in build["outputs"].values():
        captures.location(locator)

    manifest_bytes = captures.read(build["manifest_path"])
    if _sha(manifest_bytes) != build["manifest_hash"]:
        raise InvalidRecord("Manifest bytes do not match captured build-time digest")
    manifest = _manifest(manifest_bytes)
    for field in ("build_id", "blueprint_id", "blueprint_status", "blueprint",
                  "compiled_artifact", "source_artifacts", "sections"):
        if field not in manifest:
            raise InvalidRecord(f"Captured manifest lacks {field}")
    _same(manifest["build_id"], build["build_id"], "Build ID")
    _same(manifest["blueprint_id"], build["blueprint"]["id"], "Blueprint ID")
    _same(manifest["blueprint_status"], build["blueprint"]["status"], "Blueprint status")
    _same(manifest.get("status", "unknown"), build["release_status"], "Declared status")
    _same(manifest.get("ratification", "pending"), build["release_ratification"], "Declared ratification")
    for field, recorded in [("blueprint", build["blueprint"]["path"]),
                            ("compiled_artifact", build["compile"]["source"])]:
        validate_portable_reference(manifest[field], "Manifest " + field)
        if captures.location(manifest[field])[1] != captures.location(recorded)[1]:
            raise InvalidRecord(f"{field} locator disagrees with captured manifest")

    sources = manifest["source_artifacts"]
    if type(sources) is not list or len(sources) != len(build["source_artifacts"]):
        raise InvalidRecord("Source occurrences disagree with captured manifest")
    for declared, recorded in zip(sources, build["source_artifacts"]):
        if type(declared) is not dict or "path" not in declared:
            raise InvalidRecord("Invalid manifest source occurrence")
        _same({"path": declared["path"], "tags": declared.get("tags", []),
               "status": declared.get("status", "unknown"), "role": declared.get("role", "unknown")},
              {key: recorded[key] for key in ("path", "tags", "status", "role")}, "Source declaration")

    sections = manifest["sections"]
    coverage = build["coverage"]["section_detail"]
    if type(sections) is not list or len(sections) != len(coverage):
        raise InvalidRecord("Section occurrences disagree with captured manifest")
    warnings = []
    for declared, recorded in zip(sections, coverage):
        if type(declared) is not dict:
            raise InvalidRecord("Invalid manifest section")
        _same({"section": declared.get("section", "unknown"),
               "required_tags": declared.get("required_tags", []),
               "required_claims": declared.get("required_claims", [])},
              {key: recorded[key] for key in ("section", "required_tags", "required_claims")}, "Section declaration")
        if recorded["missing_tags"]:
            warnings.append(f"Section '{recorded['section']}' missing required tags: {recorded['missing_tags']}")
    if build["warnings"] != warnings:
        raise UnsupportedProfile("Unclassified warning semantics require a reviewed profile")

    required = [(build["blueprint"]["path"], build["blueprint"]["sha256"]),
                (build["compile"]["source"], build["compile"]["sha256"]),
                (build["outputs"]["white_paper"], build["compile"]["sha256"])]
    required += [(item["path"], item["sha256"]) for item in build["source_artifacts"]]
    required += [(build["outputs"][role], core["result"]["historical_outputs"][role + "_sha256"])
                 for role in ("rc_log", "release_decision")]
    for locator, expected_hash in required:
        if _sha(captures.read(locator)) != expected_hash:
            raise InvalidRecord(f"Artifact bytes disagree with recorded digest: {locator}")


def prepare_binding(build: dict, serialized: bytes, historical_outputs: dict,
                    build_path: Path, project_root: Path) -> bytes:
    """Prepare from emission captures, never infer historical hashes from disk."""
    core = project_core(build, historical_outputs)
    captures = _Captures(project_root)
    _verify_result(core, serialized, build_path, captures)
    captures.unchanged()
    return canonical_json({
        "schema": BINDING_SCHEMA,
        "core": core,
        "envelope": {"core_sha256": core_digest(core), "records": [{
            "role": "build-record", "path": str(build_path), "sha256": _sha(serialized),
        }]},
    })


def publish_binding(serialized: bytes, build_bytes: bytes, build_path: Path,
                    project_root: Path) -> None:
    """Individually atomic sidecar; inconsistent multi-file pairs fail closed."""
    binding = strict_json_loads(serialized)
    captures = _Captures(project_root)
    if captures.read(build_path) != build_bytes:
        raise InvalidRecord("Installed build record differs from intended serialized bytes")
    _verify_binding(binding, build_bytes, build_path, captures)
    destination = build_path.with_name(BINDING_NAME)
    captures.location(destination)
    with tempfile.TemporaryDirectory(prefix=".herm-build-binding-", dir=destination.parent) as staging:
        staged = Path(staging) / BINDING_NAME
        with staged.open("wb") as stream:
            stream.write(serialized)
            stream.flush()
        if staged.read_bytes() != serialized:
            raise InvalidRecord("Staged build binding differs from intended bytes")
        captures.unchanged()
        os.replace(staged, destination)
        if destination.read_bytes() != serialized:
            raise InvalidRecord("Installed build binding differs from intended bytes")
        captures.unchanged()


def _verify_binding(binding: dict, raw: bytes, build_path: Path, captures: _Captures) -> dict:
    if type(binding) is not dict or binding.get("schema") != BINDING_SCHEMA:
        raise UnsupportedProfile("Unsupported binding schema")
    if set(binding) != {"schema", "core", "envelope"}:
        raise UnsupportedProfile("Incomplete or unknown binding coverage")
    core = binding["core"]
    digest = core_digest(core)
    envelope = binding["envelope"]
    if type(envelope) is not dict or set(envelope) != {"core_sha256", "records"}:
        raise UnsupportedProfile("Incomplete or unknown execution envelope coverage")
    if envelope["core_sha256"] != digest:
        raise InvalidRecord("Detached core: envelope digest does not match core bytes")
    records = envelope["records"]
    if (type(records) is not list or len(records) != 1 or type(records[0]) is not dict
            or set(records[0]) != {"role", "path", "sha256"} or records[0]["role"] != "build-record"):
        raise UnsupportedProfile("Expected complete build-record binding coverage only")
    record = records[0]
    if type(record["path"]) is not str or not record["path"]:
        raise InvalidRecord("Invalid bound record locator")
    if captures.location(record["path"])[1] != captures.location(build_path)[1]:
        raise InvalidRecord("Execution envelope points to a different build record")
    if record["sha256"] != _sha(raw):
        raise InvalidRecord("Execution record bytes do not match envelope digest")
    _verify_result(core, raw, build_path, captures)
    return core


def validate_captured_build(build_path: Path, captures: _Captures) -> dict:
    """Validate a build using the caller's byte captures, never a second snapshot."""
    raw = captures.read(build_path)
    binding_path = build_path.with_name(BINDING_NAME)
    try:
        binding_raw = captures.read(binding_path)
    except FileNotFoundError as exc:
        raise UnsupportedProfile("Insufficient evidence: legacy/missing build-result binding; no historical backfill") from exc
    binding = strict_json_loads(binding_raw)
    core = _verify_binding(binding, raw, build_path, captures)
    captures.unchanged()
    return core


def _verified(build_path: Path, project_root: Path) -> tuple[dict, _Captures]:
    captures = _Captures(project_root)
    core = validate_captured_build(build_path, captures)
    return core, captures


def _attempt(build_path: Path, project_root: Path) -> tuple[dict, dict | None, _Captures | None]:
    try:
        core, captures = _verified(build_path, project_root)
        envelope = strict_json_loads(captures.read(build_path.with_name(BINDING_NAME)))["envelope"]
        return {"integrity": "valid", "core_sha256": core_digest(core),
                "record_sha256": envelope["records"][0]["sha256"],
                "envelope_sha256": _sha(canonical_json(envelope))}, core, captures
    except UnsupportedProfile as exc:
        return {"integrity": "unsupported", "reason": str(exc)}, None, None
    except (InvalidRecord, OSError, RuntimeError) as exc:
        return {"integrity": "invalid", "reason": str(exc)}, None, None


def verify_build(build_path: Path, *, project_root: Path) -> dict:
    """Verify available v1 evidence without modifying any artifact."""
    return _attempt(build_path, project_root)[0]


def _differences(left, right, pointer="") -> list[dict]:
    if canonical_json(left) == canonical_json(right):
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        changes = []
        for key in sorted(left.keys() | right.keys()):
            child = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            if key in left and key in right:
                changes.extend(_differences(left[key], right[key], child))
            else:
                changes.append({"path": child, **({"left": left[key]} if key in left else {}),
                                **({"right": right[key]} if key in right else {})})
        return changes
    if isinstance(left, list) and isinstance(right, list):
        changes = []
        for index in range(max(len(left), len(right))):
            child = f"{pointer}/{index}"
            if index < min(len(left), len(right)):
                changes.extend(_differences(left[index], right[index], child))
            else:
                changes.append({"path": child, **({"left": left[index]} if index < len(left) else {}),
                                **({"right": right[index]} if index < len(right) else {})})
        return changes
    return [{"path": pointer, "left": left, "right": right}]


def compare_builds(left: Path, right: Path, *, left_root: Path, right_root: Path) -> dict:
    """Never turn invalid/missing evidence into a valid 'different' result."""
    left_status, left_core, left_captures = _attempt(left, left_root)
    right_status, right_core, right_captures = _attempt(right, right_root)
    for status, captures in [(left_status, left_captures), (right_status, right_captures)]:
        if captures is not None:
            try:
                captures.unchanged()
            except (InvalidRecord, UnsupportedProfile, OSError, RuntimeError) as exc:
                status.update(integrity="invalid", reason=str(exc))
    result = {"comparison": "unsupported", "left": left_status, "right": right_status}
    if any(status["integrity"] != "valid" for status in (left_status, right_status)):
        result["reason"] = "Insufficient supported, valid evidence for strict build-result comparison"
        return result
    equal = (canonical_json(left_core) == canonical_json(right_core)
             and left_status["core_sha256"] == right_status["core_sha256"])
    result["comparison"] = "equivalent" if equal else "different"
    result["differences"] = _differences(left_core, right_core)
    result["execution_evidence_changed"] = left_status["envelope_sha256"] != right_status["envelope_sha256"]
    result["scope"] = "build-result only; no release or preservation-package equivalence"
    return result
