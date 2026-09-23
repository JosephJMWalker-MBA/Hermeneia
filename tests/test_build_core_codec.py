"""Production codec checks against the accepted, independently committed vectors."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hermeneia.build_core import (
    CORE_DOMAIN, InvalidRecord, UnsupportedProfile, canonical_json, core_digest,
    project_core, strict_json_loads, validate_core, validate_portable_reference,
)


VECTORS = Path(__file__).parent / "fixtures/reproducibility-core-design.json"


@pytest.fixture
def example():
    return json.loads(VECTORS.read_text())["build_binding_example"]


def test_accepted_golden_vectors_are_unchanged(example):
    for vector in json.loads(VECTORS.read_text())["canonical_vectors"]:
        actual = canonical_json(vector["value"])
        assert actual == vector["canonical_ascii"].encode("ascii")
        assert hashlib.sha256(CORE_DOMAIN + actual).hexdigest() == vector["domain_sha256"]
        assert canonical_json(strict_json_loads(actual)) == actual
    validate_core(example["core"])
    assert canonical_json(example["core"]) == example["canonical_ascii"].encode("ascii")
    assert core_digest(example["core"]) == example["domain_sha256"]
    build = strict_json_loads(example["legacy_record_utf8"].encode())
    assert project_core(build, example["core"]["result"]["historical_outputs"]) == example["core"]


@pytest.mark.parametrize("raw", [
    b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}', b'{"x":NaN}',
    b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1.0}', b'{"x":1e0}',
    b'{"x":9007199254740992}', b'{"x":-9007199254740992}',
    b'{"x":"\\ud800"}', b'{"x":"\\udfff"}', b'\xef\xbb\xbf{}',
    b'{"x":"\xff"}', b'{"x":', b'{"x":true} trailing',
])
def test_strict_parser_rejects_ambiguous_or_invalid_bytes(raw):
    with pytest.raises(InvalidRecord):
        strict_json_loads(raw)


@pytest.mark.parametrize("value", [1.0, float("nan"), {1: "key"}, ("tuple",),
                                         9007199254740992, "\ud800"])
def test_canonical_codec_rejects_values_outside_domain(value):
    with pytest.raises(InvalidRecord):
        canonical_json(value)


def test_canonical_codec_rejects_cycles():
    cycle = []
    cycle.append(cycle)
    with pytest.raises(InvalidRecord):
        canonical_json(cycle)


def test_codec_preserves_strings_and_array_occurrences():
    assert canonical_json(strict_json_loads(b'{"zero":-0}')) == b'{"zero":0}'
    for first, second in [
        (["a", "b"], ["b", "a"]), (["a"], ["a", "a"]),
        ("\u00e9", "e\u0301"), ("line\r\n", "line\n"), (" a", "a"),
    ]:
        assert canonical_json(first) != canonical_json(second)


@pytest.mark.parametrize("path", ["", "/tmp/a", "../a", "a/../b", "./a", "a/./b",
                                      "a//b", "a/", "C:/a", "C:a", "a\\b", "a\x00b"])
def test_portable_reference_requires_unambiguous_spelling(path):
    with pytest.raises(UnsupportedProfile):
        validate_portable_reference(path)


@pytest.mark.parametrize("path", ["docs/a.md", "a", "docs/\u00e9 a.md", "docs/a:b.md"])
def test_portable_reference_does_not_rewrite_valid_strings(path):
    validate_portable_reference(path)


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(extra="unknown"),
    lambda c: c["result"].pop("manifest_hash"),
    lambda c: c["result"]["compile"].update(method="artist"),
    lambda c: c["result"]["critic"].update(enabled=True),
    lambda c: c["result"]["coverage"][0].update(claims_checked=True),
    lambda c: c["result"]["source_artifacts"][0].update(path="/local/source.md"),
    lambda c: c["result"]["source_artifacts"][0].update(tags=[{"tag": "thesis"}]),
    lambda c: c.update(schema="hermeneia.build-result/v2"),
])
def test_unknown_or_incomplete_profiles_are_unsupported(example, mutation):
    mutation(example["core"])
    with pytest.raises(UnsupportedProfile):
        core_digest(example["core"])


@pytest.mark.parametrize("mutation", [
    lambda c: c["result"].update(manifest_hash="A" * 64),
    lambda c: c["result"]["compile"].update(sha256="abc"),
    lambda c: c["result"]["historical_outputs"].update(rc_log_sha256="?" * 64),
    lambda c: c["result"]["coverage"][0].update(status="WARN"),
    lambda c: c["result"]["coverage"][0].update(missing_tags=["nonexistent"]),
])
def test_core_rejects_malformed_provenance_or_contradictory_coverage(example, mutation):
    mutation(example["core"])
    with pytest.raises(InvalidRecord):
        core_digest(example["core"])


@pytest.mark.parametrize("mutation", [
    lambda b: b.update(blueprint_status="draft"),
    lambda b: b.update(has_draft_artifacts=True),
    lambda b: b.update(outcome="warn"),
    lambda b: b["coverage"].update(sections_evaluated=3),
    lambda b: b["coverage"].update(sections_pass=1),
    lambda b: b["coverage"].update(sections_warn=1),
    lambda b: b["coverage"].update(sections_fail=1),
    lambda b: b["source_artifacts"][0].update(resolved=False),
])
def test_projection_rejects_contradictory_legacy_copies(example, mutation):
    build = strict_json_loads(example["legacy_record_utf8"].encode())
    mutation(build)
    with pytest.raises(InvalidRecord):
        project_core(build, example["core"]["result"]["historical_outputs"])


@pytest.mark.parametrize("mutation", [
    lambda b: b.pop("warnings"),
    lambda b: b.update(new_result_field="unclassified"),
    lambda b: b["outputs"].update(extra="unclassified"),
    lambda b: b["source_artifacts"][0].pop("role"),
    lambda b: b["coverage"].update(sections_pass=True),
    lambda b: b.update(warnings=[{"message": "rich"}]),
])
def test_projection_refuses_incomplete_or_unclassified_legacy_shapes(example, mutation):
    build = strict_json_loads(example["legacy_record_utf8"].encode())
    mutation(build)
    with pytest.raises(UnsupportedProfile):
        project_core(build, example["core"]["result"]["historical_outputs"])


def test_projection_preserves_warning_result_occurrences_and_does_not_mutate(example):
    build = strict_json_loads(example["legacy_record_utf8"].encode())
    first = build["coverage"]["section_detail"][0]
    first.update(required_tags=["absent", "absent"], missing_tags=["absent", "absent"], status="WARN")
    build["coverage"].update(sections_pass=1, sections_warn=1)
    build["outcome"] = "warn"
    build["warnings"] = ["Original diagnostic preserved by envelope"]
    build["source_artifacts"][0]["status"] = "draft"
    build["has_draft_artifacts"] = True
    history = example["core"]["result"]["historical_outputs"]
    original = copy.deepcopy((build, history))
    core = project_core(build, history)
    assert core["result"]["coverage"][0]["missing_tags"] == ["absent", "absent"]
    assert (build, history) == original
    core["result"]["source_artifacts"][0]["tags"].append("changed")
    core["result"]["coverage"][0]["required_tags"].append("changed")
    assert (build, history) == original


def test_only_execution_fields_can_vary_without_changing_projected_core(example):
    build = strict_json_loads(example["legacy_record_utf8"].encode())
    history = example["core"]["result"]["historical_outputs"]
    expected = core_digest(project_core(build, history))
    build.update(build_timestamp="2027-01-01T00:00:00+00:00", hermeneia_version="new-runtime",
                 manifest_path="/different/root/manifest.yaml", warnings=["Execution diagnostic"])
    build["blueprint"]["path"] = "/different/root/blueprint.md"
    build["compile"].update(source="/different/root/paper.md", note="New descriptive prose")
    build["critic"]["note"] = "New descriptive prose"
    build["outputs"] = {role: "/different/root/" + role for role in build["outputs"]}
    assert core_digest(project_core(build, history)) == expected
    build["coverage"]["section_detail"][0]["required_claims"] = ["new obligation"]
    assert core_digest(project_core(build, history)) != expected
