"""Executable examples for a PROPOSED protocol, not a production record migration.

The local codec/projection below is a test oracle for design vectors. No CLI uses
it. Real legacy producers are exercised only in disposable fixture directories.
Production schema validation, atomic sidecars, and package equivalence are future
packets, not implemented or certified here.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

from test_publication_reproducibility import (
    LATER, PRESERVE_LATER, _create_inputs, _run_clean,
)


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs/design/build-preservation-reproducibility.md"
VECTORS = ROOT / "tests/fixtures/reproducibility-core-design.json"
DOMAIN = b"Hermeneia reproducibility core v1\n"
PROFILE = "hermeneia.build-result/v1"
BUILD = "publication/build.json"


def _canonical(value):
    """Test-only reference encoding of the proposal's restricted JSON domain."""
    def validate(item):
        if item is None or type(item) is bool:
            return
        if type(item) is int and abs(item) <= 9007199254740991:
            return
        if isinstance(item, str):
            item.encode("utf-8", errors="strict")  # Reject lone surrogates.
            return
        if isinstance(item, list):
            for child in item:
                validate(child)
            return
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            for key, child in item.items():
                validate(key)
                validate(child)
            return
        raise ValueError("Outside proposed canonical JSON domain")

    validate(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _parse(raw):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)
    _canonical(value)
    return value


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _core_digest(core):
    if core.get("schema") != PROFILE:
        raise ValueError("Unsupported core profile")
    return _sha(DOMAIN + _canonical(core))


def _candidate_core(outputs):
    """Explicit design projection of this test's known, valid legacy fixture.

    Not a legacy adapter: it requires the complete fresh-run output capture, and
    does not claim that reading today's files establishes historical provenance.
    """
    build = json.loads(outputs[BUILD])
    return {
        "schema": PROFILE,
        "result": {
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
            "historical_outputs": {
                "rc_log_sha256": _sha(outputs["publication/rc_log.md"]),
                "release_decision_sha256": _sha(outputs["publication/release_decision.md"]),
            },
        },
    }


def _binding(core, raw, path):
    return {
        "schema": "hermeneia.reproducibility-binding/v1",
        "core": core,
        "envelope": {
            "core_sha256": _core_digest(core),
            "records": [{"role": "build-record", "path": str(path), "sha256": _sha(raw)}],
        },
    }


def _check_example_binding(binding, raw, expected_core):
    """Three independent necessary checks; NOT a full production validator."""
    assert binding["envelope"]["core_sha256"] == _core_digest(binding["core"])
    assert binding["envelope"]["records"][0]["sha256"] == _sha(raw)
    assert _canonical(binding["core"]) == _canonical(expected_core)


def _inventory_paths(value, prefix=""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}/{key}"
            yield path
            yield from _inventory_paths(child, path)
    elif isinstance(value, list) and any(isinstance(child, dict) for child in value):
        for child in value:
            yield from _inventory_paths(child, prefix + "/[]")


def test_golden_canonical_bytes_and_digest():
    """Expected bytes/digests are committed constants, not computed expectations."""
    vectors = json.loads(VECTORS.read_text())
    for vector in vectors["canonical_vectors"]:
        actual = _canonical(vector["value"])
        assert actual == vector["canonical_ascii"].encode("ascii")
        assert _sha(DOMAIN + actual) == vector["domain_sha256"]
        reordered = dict(reversed(list(vector["value"].items())))
        assert _canonical(reordered) == actual
    example = vectors["build_binding_example"]
    assert _canonical(example["core"]) == example["canonical_ascii"].encode("ascii")
    assert _core_digest(example["core"]) == example["domain_sha256"]


@pytest.mark.parametrize("raw", [
    b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1.0}',
    b'{"x":9007199254740992}', b'{"x":"\\ud800"}', b'\xef\xbb\xbf{}',
    b'{"x":"\xff"}', b'{"nested":{"x":1,"x":2}}',
])
def test_reject_ambiguous_or_unsupported_json_encoding(raw):
    with pytest.raises((ValueError, UnicodeError)):
        _parse(raw)


def test_string_and_array_content_is_never_normalized():
    assert _canonical({"value": "\u00e9"}) != _canonical({"value": "e\u0301"})
    assert _canonical({"value": "a\r\n"}) != _canonical({"value": "a\n"})
    assert _canonical({"items": ["a", "b"]}) != _canonical({"items": ["b", "a"]})
    assert _canonical({"items": ["a"]}) != _canonical({"items": ["a", "a"]})
    assert _canonical({"value": None}) != _canonical({})


def test_legacy_producers_have_proposed_equal_cores_and_distinct_bound_envelopes(tmp_path, monkeypatch):
    first_root, second_root = tmp_path / "machine-a", tmp_path / "machine-b"
    _create_inputs(first_root)
    _create_inputs(second_root)
    first = _run_clean(first_root, monkeypatch)
    second = _run_clean(second_root, monkeypatch, build_time=LATER, preserve_time=PRESERVE_LATER)
    assert first[BUILD] != second[BUILD]
    core_a, core_b = _candidate_core(first), _candidate_core(second)
    assert _canonical(core_a) == _canonical(core_b)
    assert _core_digest(core_a) == _core_digest(core_b)
    binding_a = _binding(core_a, first[BUILD], first_root / BUILD)
    binding_b = _binding(core_b, second[BUILD], second_root / BUILD)
    assert binding_a["envelope"] != binding_b["envelope"]
    _check_example_binding(binding_a, first[BUILD], core_a)
    _check_example_binding(binding_b, second[BUILD], core_b)

    # No candidate binding/schema was written into either production output tree.
    assert not list(tmp_path.rglob("*.reproducibility.json"))
    for outputs, core in [(first, core_a), (second, core_b)]:
        assert "schema" not in json.loads(outputs[BUILD])
        assert core["result"]["compile"]["sha256"] == _sha(outputs["publication/white_paper.md"])
        # Keep transitive custody hashes truthful; do not make a package core.
        package = json.loads(outputs["preservation/preservation_package/manifest.json"])
        entry = next(item for item in package["artifacts"] if item["preserved_as"] == "artifacts/build.json")
        assert entry["sha256"] == _sha(outputs[BUILD])

    # Guard the documented current happy-path field inventory against drift.
    sections = DESIGN.read_text().split("### ")
    for title, name in [
        ("`build.json`", BUILD),
        ("`preservation_report.json`", "publication/preservation_report.json"),
        ("`preservation_package/manifest.json`", "preservation/preservation_package/manifest.json"),
    ]:
        section = next(part for part in sections if part.startswith(title))
        documented = set(re.findall(r"^\| `([^`]+)` \|", section, re.MULTILINE))
        assert set(_inventory_paths(json.loads(first[name]))) <= documented


@pytest.mark.parametrize("mutation", ["stale-core", "record-tamper", "rehashed-unrelated-core"])
def test_binding_examples_reject_detachment(mutation):
    vector = json.loads(VECTORS.read_text())["build_binding_example"]
    core = vector["core"]
    raw = vector["legacy_record_utf8"].encode("utf-8")
    binding = _binding(copy.deepcopy(core), raw, "/synthetic/run/build.json")
    _check_example_binding(binding, raw, core)
    if mutation == "record-tamper":
        raw += b"\n"  # Even equivalent parsed JSON is different custody evidence.
    else:
        binding["core"]["result"]["compile"]["sha256"] = "f" * 64
        if mutation == "rehashed-unrelated-core":
            binding["envelope"]["core_sha256"] = _core_digest(binding["core"])
    with pytest.raises(AssertionError):
        _check_example_binding(binding, raw, core)


@pytest.mark.parametrize("field", ["manifest_hash", "compile", "blueprint", "source_artifacts", "coverage", "historical_outputs", "release_ratification"])
def test_authoritative_changes_cannot_disappear_from_core_identity(field):
    core = json.loads(VECTORS.read_text())["build_binding_example"]["core"]
    altered = copy.deepcopy(core)
    original = altered["result"][field]
    if field == "compile":
        original["sha256"] = "f" * 64
    elif field == "blueprint":
        original["status"] = "draft"
    elif field == "historical_outputs":
        original["release_decision_sha256"] = "f" * 64
    elif field == "source_artifacts":
        original[0]["sha256"] = "f" * 64
    elif field == "coverage":
        original[0]["claims_checked"] = True
    else:
        altered["result"][field] = "different"
    # Tests sensitivity, not eligibility of the altered candidate for emission.
    assert _core_digest(altered) != _core_digest(core)


def test_legacy_and_unknown_profiles_are_not_inferred():
    with pytest.raises(ValueError, match="Unsupported"):
        _core_digest({"build_id": "legacy-without-core"})
    with pytest.raises(ValueError, match="Unsupported"):
        _core_digest({"schema": "hermeneia.build-result/v999", "result": {}})
