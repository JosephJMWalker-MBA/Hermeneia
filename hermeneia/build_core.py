"""Strict, filesystem-independent codec for the first build-result profile.

This projection establishes no artifact availability, authenticity, or release
authority. A verifier must additionally bind the exact record bytes and check the
captured manifest and required artifacts. Historical output hashes supplied to
``project_core`` must come from a new build's emission capture, never a legacy
backfill from whatever files happen to exist at verification time.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any


CORE_SCHEMA = "hermeneia.build-result/v1"
BINDING_SCHEMA = "hermeneia.reproducibility-binding/v1"
CORE_DOMAIN = b"Hermeneia reproducibility core v1\n"
_MAX_INTEGER = 9007199254740991
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class UnsupportedProfile(ValueError):
    """Available evidence or field semantics do not fit this complete profile."""


class InvalidRecord(ValueError):
    """A record is malformed or contradicts its own declared evidence."""


def _validate_json_domain(value: Any, active: set[int]) -> None:
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if abs(value) > _MAX_INTEGER:
            raise InvalidRecord("Integer is outside the canonical JSON range")
        return
    if type(value) is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise InvalidRecord("Lone surrogate is outside the canonical JSON domain") from exc
        return
    if type(value) not in (dict, list):
        raise InvalidRecord("Value is outside the canonical JSON domain")
    identity = id(value)
    if identity in active:
        raise InvalidRecord("Circular value is outside the canonical JSON domain")
    active.add(identity)
    try:
        if type(value) is dict:
            for key, child in value.items():
                if type(key) is not str:
                    raise InvalidRecord("Canonical JSON object keys must be strings")
                _validate_json_domain(key, active)
                _validate_json_domain(child, active)
        else:
            for child in value:
                _validate_json_domain(child, active)
    finally:
        active.remove(identity)


def canonical_json(value: Any) -> bytes:
    """Encode the accepted domain exactly, preserving strings and array order.

    This is the profile's specified Python JSON encoding, not RFC 8785. Object
    keys sort by Unicode code point. No normalization or trailing newline occurs.
    """
    try:
        _validate_json_domain(value, set())
        return json.dumps(value, sort_keys=True, ensure_ascii=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except RecursionError as exc:
        raise InvalidRecord("Canonical JSON nesting is too deep") from exc


def strict_json_loads(raw: bytes) -> Any:
    """Parse one UTF-8 capture without accepting ambiguous JSON representations."""
    if type(raw) is not bytes:
        raise InvalidRecord("JSON input must be captured bytes")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise InvalidRecord("JSON byte-order marks are not supported")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidRecord(f"Duplicate JSON key: {key!r}")
            result[key] = value
        return result

    def reject_number(value: str) -> None:
        raise InvalidRecord(f"Unsupported JSON number: {value}")

    try:
        value = json.loads(raw.decode("utf-8", errors="strict"),
                           object_pairs_hook=unique_pairs,
                           parse_float=reject_number, parse_constant=reject_number)
        canonical_json(value)
        return value
    except InvalidRecord:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InvalidRecord(f"Invalid strict JSON: {exc}") from exc


def _keys(value: Any, expected: set[str], label: str) -> None:
    if type(value) is not dict:
        raise UnsupportedProfile(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise UnsupportedProfile(f"{label} has incomplete or unknown fields: "
                                 f"missing={missing}, unknown={unknown}")


def _text(value: Any, label: str) -> None:
    if type(value) is not str:
        raise UnsupportedProfile(f"{label} must be a string")


def _texts(value: Any, label: str) -> None:
    if type(value) is not list:
        raise UnsupportedProfile(f"{label} must be an array of strings")
    for index, item in enumerate(value):
        _text(item, f"{label}[{index}]")


def _array(value: Any, label: str) -> None:
    if type(value) is not list:
        raise UnsupportedProfile(f"{label} must be an array")


def _boolean(value: Any, label: str) -> None:
    if type(value) is not bool:
        raise UnsupportedProfile(f"{label} must be a boolean")


def _digest(value: Any, label: str) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise InvalidRecord(f"{label} must be a lowercase SHA-256 digest")


def validate_portable_reference(value: Any, label: str = "path") -> None:
    """Admit a declared portable spelling without rewriting or resolving it.

    Filesystem confinement and locator/content correspondence are separate checks.
    Neither valid spelling nor this function proves equivalence of local paths.
    """
    _text(value, label)
    if (not value or value.startswith("/") or "\\" in value or "\x00" in value
            or re.match(r"^[A-Za-z]:", value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise UnsupportedProfile(f"{label} is not a supported portable authored reference")


def _validate_coverage(sections: Any, sources: list[dict]) -> None:
    _array(sections, "coverage")
    tags = {tag for source in sources for tag in source["tags"]}
    for index, section in enumerate(sections):
        label = f"coverage[{index}]"
        _keys(section, {"section", "status", "required_tags", "missing_tags",
                        "required_claims", "claims_checked"}, label)
        _text(section["section"], label + ".section")
        _text(section["status"], label + ".status")
        for key in ("required_tags", "missing_tags", "required_claims"):
            _texts(section[key], label + "." + key)
        _boolean(section["claims_checked"], label + ".claims_checked")
        if section["claims_checked"]:
            raise UnsupportedProfile(f"{label}: checked claims need a different profile")
        if section["status"] not in ("PASS", "WARN"):
            raise UnsupportedProfile(f"{label}: unsupported coverage algorithm status")
        missing = [tag for tag in section["required_tags"] if tag not in tags]
        if section["missing_tags"] != missing:
            raise InvalidRecord(f"{label}.missing_tags disagrees with declared source tags")
        expected_status = "WARN" if missing else "PASS"
        if section["status"] != expected_status:
            raise InvalidRecord(f"{label}.status disagrees with current coverage algorithm")


def validate_core(core: Any) -> None:
    """Require complete v1 coverage and internally consistent copy-build results."""
    canonical_json(core)
    _keys(core, {"schema", "result"}, "core")
    if core["schema"] != CORE_SCHEMA:
        raise UnsupportedProfile(f"Unsupported build-result profile: {core['schema']!r}")
    result = core["result"]
    _keys(result, {"build_id", "manifest_hash", "blueprint", "source_artifacts",
                   "coverage", "compile", "critic", "release_status",
                   "release_ratification", "historical_outputs"}, "result")
    for key in ("build_id", "release_status", "release_ratification"):
        _text(result[key], key)
    _digest(result["manifest_hash"], "manifest_hash")

    blueprint = result["blueprint"]
    _keys(blueprint, {"id", "status", "sha256"}, "blueprint")
    _text(blueprint["id"], "blueprint.id")
    _text(blueprint["status"], "blueprint.status")
    _digest(blueprint["sha256"], "blueprint.sha256")
    if blueprint["status"] != "ratified":
        raise UnsupportedProfile("This profile requires a ratified Blueprint")

    sources = result["source_artifacts"]
    _array(sources, "source_artifacts")
    for index, source in enumerate(sources):
        label = f"source_artifacts[{index}]"
        _keys(source, {"path", "sha256", "tags", "status", "role"}, label)
        validate_portable_reference(source["path"], label + ".path")
        _digest(source["sha256"], label + ".sha256")
        _texts(source["tags"], label + ".tags")
        _text(source["status"], label + ".status")
        _text(source["role"], label + ".role")
    _validate_coverage(result["coverage"], sources)

    compiled = result["compile"]
    _keys(compiled, {"sha256", "method"}, "compile")
    _digest(compiled["sha256"], "compile.sha256")
    if compiled["method"] != "copy":
        raise UnsupportedProfile("This profile supports only the copy compile method")
    _keys(result["critic"], {"enabled"}, "critic")
    _boolean(result["critic"]["enabled"], "critic.enabled")
    if result["critic"]["enabled"]:
        raise UnsupportedProfile("Automated critic execution needs a different profile")
    historical = result["historical_outputs"]
    _keys(historical, {"rc_log_sha256", "release_decision_sha256"}, "historical_outputs")
    for key, digest in historical.items():
        _digest(digest, "historical_outputs." + key)


def core_digest(core: Any) -> str:
    """Digest the domain separator followed by the complete validated core bytes."""
    validate_core(core)
    return hashlib.sha256(CORE_DOMAIN + canonical_json(core)).hexdigest()


def project_core(build: Any, historical_outputs: Any) -> dict:
    """Project complete current-format build evidence without inventing fields.

    Exact-byte custody, captured-manifest agreement and artifact availability must
    be checked separately. This function deliberately never reads a filesystem.
    """
    canonical_json(build)
    canonical_json(historical_outputs)
    _keys(build, {"build_id", "build_timestamp", "hermeneia_version", "blueprint",
                  "manifest_path", "manifest_hash", "source_artifacts", "coverage",
                  "compile", "critic", "warnings", "outcome", "blueprint_status",
                  "has_draft_artifacts", "release_status", "release_ratification",
                  "outputs"}, "build record")
    for key in ("build_timestamp", "hermeneia_version", "manifest_path", "outcome",
                "blueprint_status"):
        _text(build[key], key)
    _texts(build["warnings"], "warnings")
    _boolean(build["has_draft_artifacts"], "has_draft_artifacts")
    _keys(build["blueprint"], {"path", "id", "status", "sha256"}, "build.blueprint")
    _text(build["blueprint"]["path"], "blueprint.path")
    _keys(build["compile"], {"source", "sha256", "method", "note"}, "build.compile")
    _text(build["compile"]["source"], "compile.source")
    _text(build["compile"]["note"], "compile.note")
    _keys(build["critic"], {"enabled", "note"}, "build.critic")
    _text(build["critic"]["note"], "critic.note")
    _keys(build["outputs"], {"white_paper", "coverage", "rc_log", "release_decision",
                            "build_json"}, "outputs")
    for role, path in build["outputs"].items():
        _text(path, "outputs." + role)
    _keys(build["coverage"], {"sections_evaluated", "sections_pass", "sections_warn",
                             "sections_fail", "section_detail"}, "build.coverage")
    for key in ("sections_evaluated", "sections_pass", "sections_warn", "sections_fail"):
        value = build["coverage"][key]
        if type(value) is not int:
            raise UnsupportedProfile(f"coverage.{key} must be an integer")
        if value < 0:
            raise InvalidRecord(f"coverage.{key} cannot be negative")

    _array(build["source_artifacts"], "source_artifacts")
    for index, source in enumerate(build["source_artifacts"]):
        label = f"build.source_artifacts[{index}]"
        _keys(source, {"path", "sha256", "tags", "status", "role", "resolved"}, label)
        _boolean(source["resolved"], label + ".resolved")
        if not source["resolved"]:
            raise InvalidRecord(f"{label}: unresolved source cannot establish a build result")

    result = {
        "build_id": build["build_id"],
        "manifest_hash": build["manifest_hash"],
        "blueprint": {key: build["blueprint"][key] for key in ("id", "status", "sha256")},
        "source_artifacts": [
            {key: source[key] for key in ("path", "sha256", "tags", "status", "role")}
            for source in build["source_artifacts"]
        ],
        "coverage": build["coverage"]["section_detail"],
        "compile": {key: build["compile"][key] for key in ("sha256", "method")},
        "critic": {"enabled": build["critic"]["enabled"]},
        "release_status": build["release_status"],
        "release_ratification": build["release_ratification"],
        "historical_outputs": historical_outputs,
    }
    core = {"schema": CORE_SCHEMA, "result": result}
    validate_core(core)
    sections = result["coverage"]
    expected_counts = {
        "sections_evaluated": len(sections),
        "sections_pass": sum(section["status"] == "PASS" for section in sections),
        "sections_warn": sum(section["status"] == "WARN" for section in sections),
        "sections_fail": 0,
    }
    for key, expected in expected_counts.items():
        if build["coverage"][key] != expected:
            raise InvalidRecord(f"coverage.{key} disagrees with section details")
    expected_outcome = "warn" if expected_counts["sections_warn"] else "pass"
    if build["outcome"] != expected_outcome:
        raise InvalidRecord("outcome disagrees with coverage results")
    if build["blueprint_status"] != result["blueprint"]["status"]:
        raise InvalidRecord("blueprint_status disagrees with Blueprint status")
    expected_draft = any(source["status"] == "draft" for source in result["source_artifacts"])
    if build["has_draft_artifacts"] != expected_draft:
        raise InvalidRecord("has_draft_artifacts disagrees with source statuses")
    return copy.deepcopy(core)
