"""Versioned, provider-free capabilities over the existing Study Lineage view.

This evaluates possible operations, not mastery, awards or a new event history.
The caller supplies an already access-filtered project_study_lineage snapshot.
Current inputs are readiness hints, never historical evidence or Scope admission.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import re
from typing import Any

from hermeneia.study_lineage import SCHEMA as LINEAGE_SCHEMA

REGISTRY_SCHEMA = "hermeneia.capability-registry/v1"
RESULT_SCHEMA = "hermeneia.capability-evaluation/v1"
EVALUATOR_VERSION = "1.1.0"
STATUSES = frozenset({"available", "not_yet_available",
    "already_exercised_under_supported_evidence", "unsupported_due_to_missing_history"})
_FACTS = frozenset({"reader_material", "evidence", "observation", "inquiry_context",
    "perspective_frame", "interpretation", "blueprint", "lineage",
    "preserved_question", "attributed_interpretation", "retained_perspective_execution"})
_REASONS = frozenset({"READY", "MISSING_SOURCE", "INSUFFICIENT_EVIDENCE",
    "MISSING_INQUIRY_CONTEXT", "MISSING_PERSPECTIVE", "NO_INTERPRETATION",
    "NO_BLUEPRINT", "NO_LINEAGE", "HISTORY_UNSUPPORTED", "COVERAGE_UNSUPPORTED",
    "ALREADY_EXERCISED"})
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")


class CapabilityRegistryError(ValueError):
    """An invalid registry cannot be evaluated or silently repaired."""


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CapabilityRegistryError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_registry(value: Any) -> dict:
    def require(condition, message):
        if not condition:
            raise CapabilityRegistryError(message)

    require(isinstance(value, dict) and set(value) == {"schema", "registry_version", "capabilities"}, "Invalid registry fields")
    require(value["schema"] == REGISTRY_SCHEMA, "Unsupported registry schema")
    require(isinstance(value["registry_version"], str) and _VERSION.fullmatch(value["registry_version"]), "Explicit registry semantic version required")
    definitions = value["capabilities"]
    require(isinstance(definitions, list) and bool(definitions), "Nonempty capability definitions required")
    fields = {"capability_id", "definition_version", "title", "purpose", "prerequisites",
        "positive_evidence", "refusal_or_unknown_conditions", "expected_outputs",
        "related_or_next_capabilities", "user_facing_explanation"}
    ids = set()
    for definition in definitions:
        require(isinstance(definition, dict) and set(definition) == fields, "Invalid capability fields")
        identifier = definition["capability_id"]
        require(isinstance(identifier, str) and re.fullmatch(r"[a-z][a-z0-9_]*", identifier), "Invalid capability ID")
        require(identifier not in ids, f"Duplicate capability ID: {identifier}")
        ids.add(identifier)
        require(isinstance(definition["definition_version"], str) and _VERSION.fullmatch(definition["definition_version"]), "Explicit definition semantic version required")
        for field in ("title", "purpose", "user_facing_explanation"):
            require(_text(definition[field]), f"Nonblank {field} required")
        for field in ("expected_outputs", "related_or_next_capabilities"):
            values = definition[field]
            require(isinstance(values, list) and all(_text(v) for v in values), f"Invalid {field}")
            require(len(values) == len(set(values)), f"Duplicate {field}")
        require(bool(definition["expected_outputs"]), "Expected outputs required")
        for field in ("prerequisites", "positive_evidence"):
            predicates = definition[field]
            require(isinstance(predicates, list), f"Invalid {field}")
            seen = set()
            for predicate in predicates:
                keys = {"fact", "minimum"} | ({"reason_code", "reason"} if field == "prerequisites" else set())
                require(isinstance(predicate, dict) and set(predicate) == keys, "Invalid symbolic predicate")
                fact = predicate["fact"]
                require(isinstance(fact, str) and fact in _FACTS and fact not in seen, "Unknown or duplicate fact")
                seen.add(fact)
                require(type(predicate["minimum"]) is int and predicate["minimum"] > 0, "Positive integer minimum required")
                if field == "prerequisites":
                    require(isinstance(predicate["reason_code"], str) and predicate["reason_code"] in _REASONS and _text(predicate["reason"]), "Invalid prerequisite reason")
        unknown = definition["refusal_or_unknown_conditions"]
        require(isinstance(unknown, dict) and set(unknown) == {"reason_code", "reason"}, "Explicit historical unknown condition required")
        require(unknown["reason_code"] == "HISTORY_UNSUPPORTED" and _text(unknown["reason"]), "Invalid historical unknown condition")
        # Readiness facts can never be promoted into historical exercise by data.
        historical_facts = {"preserved_question", "attributed_interpretation"}
        if (identifier == "explore_perspective" and definition["definition_version"] == "1.1.0"
                and tuple(map(int, value["registry_version"].split("."))) >= (1, 1, 0)):
            historical_facts.add("retained_perspective_execution")
        require(all(p["fact"] in historical_facts for p in definition["positive_evidence"]), "Readiness or unversioned receipt evidence is not historical exercise")
    for definition in definitions:
        require(all(target in ids for target in definition["related_or_next_capabilities"]), "Unknown related capability")
    normalized = deepcopy(value)
    normalized["capabilities"].sort(key=lambda row: row["capability_id"])
    # Enforce a JSON-only value space, including caller-supplied registries.
    try:
        _canonical(normalized)
    except (TypeError, ValueError) as error:
        raise CapabilityRegistryError("Registry must contain finite JSON values") from error
    return normalized


def load_capability_registry(path: Path | str | None = None) -> dict:
    """Load the canonical packaged definitions, or validate an explicit file.

    No caching or caller mutation can change later default evaluations.
    """
    resource = files("hermeneia").joinpath("data/capability-registry-v1.1.json") if path is None else Path(path)
    try:
        value = json.loads(resource.read_bytes(), object_pairs_hook=_object,
            parse_constant=lambda token: (_ for _ in ()).throw(CapabilityRegistryError(f"Nonfinite value: {token}")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CapabilityRegistryError("Malformed registry bytes") from error
    return _validate_registry(value)


@dataclass
class _Fact:
    refs: list[dict]
    unknown: list[str]

    @property
    def count(self) -> int:
        # Multiple event views cannot create a second durable identity. Keep
        # all views in the audit refs while counting their real typed keys.
        return len({_canonical(ref.get("record", ref)) for ref in self.refs})


_TERMINAL_TABLES = frozenset({"achievement_awards", "accepted_perspective_comparisons"})


def _fact_inputs(lineage: dict, current_state: dict) -> dict[str, _Fact]:
    """Extract bounded typed facts; Lineage alone owns eligibility/provenance."""
    coverage = lineage["coverage"]
    # Award history and accepted Perspective comparisons are terminal records,
    # never P1/P2 prerequisite evidence. Their missing/invalid coverage must not
    # change those history predicates.
    missing_tables = [table for table in coverage["missing_tables"] if table not in _TERMINAL_TABLES]
    missing_columns = {table: value for table, value in coverage["missing_columns"].items()
                       if table not in _TERMINAL_TABLES}
    omitted = {table: value for table, value in coverage["omitted"].items()
               if table not in _TERMINAL_TABLES}
    items = lineage["items"]

    def record_fact(tables, test=lambda item: True):
        refs, unknown = [], []
        for table in tables:
            if table in missing_tables:
                unknown.append(f"Missing Lineage table: {table}.")
            # The projection owns required identity/parent/content fields.
            # Never turn a missing field it reports into known absence here.
            absent = sorted(missing_columns.get(table, []))
            if absent:
                unknown.append(f"Missing Lineage fields: {table}: {', '.join(absent)}.")
            if omitted.get(table, 0):
                unknown.append(f"Lineage omits unsupported or excluded {table} records.")
        for item in items:
            if item["record"]["table"] not in tables or item["event"] == "decision":
                continue
            if test(item):
                refs.append({"basis": item["event"], **deepcopy({key:item[key] for key in
                    ("record", "event", "authorship", "timestamp", "provenance")})})
        return _Fact(refs, unknown)

    def nonblank(item, field):
        return _text(item["record_data"].get(field))

    facts = {
        "reader_material": record_fact(("source_extractions",), lambda i: nonblank(i, "raw_text")),
        "evidence": record_fact(("observations", "reader_highlights")),
        "observation": record_fact(("observations",)),
        "interpretation": record_fact(("interpretations", "proposed_interpretations"), lambda i: nonblank(i, "text")),
        "blueprint": record_fact(("narrative_blueprints",)),
        "lineage": record_fact(tuple(sorted({item["record"]["table"] for item in items
                                              if item["record"]["table"] not in _TERMINAL_TABLES}))),
        "preserved_question": record_fact(("inquiry_notes",),
            lambda i: i["event"] == "recorded" and nonblank(i, "question_text")),
        "attributed_interpretation": record_fact(("interpretations",),
            lambda i: i["event"] == "recorded" and i["authorship"] in ("human", "accepted_model") and nonblank(i, "text")),
        "retained_perspective_execution": record_fact(("perspective_execution_receipts",),
            lambda i: i["event"] == "recorded" and i["authorship"] == "model"
            and i.get("record_type") == "retained_perspective_execution"),
    }
    facts["retained_perspective_execution"].unknown.append(
        "Only explicitly retained executions are covered; absent receipts do not establish no past Perspective activity.")
    for item in items:
        if (item["record"]["table"] == "interpretations" and item["authorship"] == "unknown"):
            facts["attributed_interpretation"].unknown.append("Canonical interpretation authorship is unknown; formation cannot be attributed.")
    inquiry = record_fact(("inquiry_notes",), lambda i: nonblank(i, "question_text"))
    if "governing_question" in current_state:
        if _text(current_state["governing_question"]):
            inquiry.refs.append({"basis":"current_state", "input":"governing_question"})
    else:
        question = record_fact(("workspace_investigation",),
            lambda i: i["record"]["key"] == {"id": "current"} and nonblank(i, "thesis"))
        inquiry.refs.extend(question.refs)
        inquiry.unknown.extend(question.unknown)
    facts["inquiry_context"] = inquiry
    if "perspective_available" in current_state:
        facts["perspective_frame"] = _Fact(
            [{"basis":"current_state", "input":"perspective_available"}] if current_state["perspective_available"] else [], [])
    else:
        facts["perspective_frame"] = record_fact(("perspectives",), lambda i: nonblank(i, "name"))
    # An empty projection with missing/omitted storage cannot prove that there
    # is no reviewable lineage. Positive extant records remain sufficient.
    if not facts["lineage"].refs and (missing_tables or missing_columns or any(omitted.values())):
        facts["lineage"].unknown.append("Lineage coverage is incomplete.")
    for fact in facts.values():
        fact.refs.sort(key=lambda ref: _canonical(ref))
        fact.unknown = sorted(set(fact.unknown))
    return facts


def _validate_inputs(lineage, current_state):
    if not isinstance(current_state, dict) or set(current_state) - {"governing_question", "perspective_available"}:
        raise ValueError("Only explicit current question/frame readiness inputs are supported")
    if "governing_question" in current_state and current_state["governing_question"] is not None and not isinstance(current_state["governing_question"], str):
        raise ValueError("Current governing question must be text or null")
    if "perspective_available" in current_state and type(current_state["perspective_available"]) is not bool:
        raise ValueError("Current frame readiness must be boolean")
    if not isinstance(lineage, dict) or lineage.get("schema") != LINEAGE_SCHEMA:
        raise ValueError("Supported Study Lineage v1 projection required")
    if not isinstance(lineage.get("workspace"), dict) or not isinstance(lineage.get("items"), list):
        raise ValueError("Malformed Study Lineage projection")
    coverage = lineage.get("coverage")
    if (not isinstance(coverage, dict) or not isinstance(coverage.get("missing_tables"), list)
            or not isinstance(coverage.get("missing_columns"), dict) or not isinstance(coverage.get("omitted"), dict)):
        raise ValueError("Explicit Lineage coverage required")
    if (not all(isinstance(t, str) for t in coverage["missing_tables"])
            or not all(isinstance(t, str) and isinstance(v, list) and all(isinstance(c, str) for c in v) for t,v in coverage["missing_columns"].items())
            or not all(isinstance(t, str) and type(v) is int and v >= 0 for t,v in coverage["omitted"].items())):
        raise ValueError("Malformed Lineage coverage")
    seen = set()
    for item in lineage["items"]:
        if not isinstance(item, dict) or not all(key in item for key in ("record", "event", "authorship", "timestamp", "provenance", "record_data")):
            raise ValueError("Malformed typed Lineage item")
        record = item["record"]
        if (not isinstance(record, dict) or not _text(record.get("table")) or not isinstance(record.get("key"), dict) or not record["key"]
                or item["event"] not in ("recorded", "current_snapshot", "decision")
                or item["authorship"] not in ("human", "model", "accepted_model", "derived", "unknown")
                or not all(isinstance(item[key], dict) for key in ("timestamp", "provenance", "record_data"))):
            raise ValueError("Malformed typed Lineage item")
        token = _canonical([record, item["event"]])
        if token in seen:
            raise ValueError("Duplicate typed Lineage item/event")
        seen.add(token)
    _canonical(lineage)


def evaluate_capabilities(lineage: dict, registry: dict | None = None, *, current_state: dict | None = None) -> dict:
    """Pure domain seam; no SQL, providers, UI state, clocks or persistence.

    ``availability`` answers current readiness separately from ``status``'s
    historical limit. A supported saved question/attributed interpretation is
    a narrowly witnessed result, never proof of mastery or a complete history.
    """
    registry = load_capability_registry() if registry is None else _validate_registry(registry)
    current_state = {} if current_state is None else current_state
    _validate_inputs(lineage, current_state)
    facts = _fact_inputs(lineage, current_state)
    results = []
    for definition in registry["capabilities"]:
        satisfied, missing, refs, notes = [], [], [], []
        availability, availability_code, availability_reason = "available", "READY", "Current prerequisites are supported; this does not authorize an execution."
        for predicate in definition["prerequisites"]:
            fact = facts[predicate["fact"]]
            refs.extend(fact.refs)
            notes.extend(fact.unknown)
            if fact.count >= predicate["minimum"]:
                satisfied.append(predicate["fact"])
            else:
                missing.append(predicate["fact"])
                # An unknown prerequisite outranks a known absence.
                if fact.unknown:
                    availability, availability_code = "unsupported_due_to_missing_history", "COVERAGE_UNSUPPORTED"
                    availability_reason = "Required readiness evidence has incomplete coverage."
                elif availability == "available":
                    availability, availability_code, availability_reason = "not_yet_available", predicate["reason_code"], predicate["reason"]
        positive = definition["positive_evidence"]
        exercised = bool(positive) and all(facts[p["fact"]].count >= p["minimum"] for p in positive)
        unknown = definition["refusal_or_unknown_conditions"]
        if exercised:
            status, code, reason = "already_exercised_under_supported_evidence", "ALREADY_EXERCISED", "The narrowly defined retained result is supported; no mastery, complete history or unrecorded human action is inferred."
        elif availability != "available":
            status, code, reason = availability, availability_code, availability_reason
        elif not positive or any(facts[p["fact"]].unknown for p in positive):
            status, code, reason = "unsupported_due_to_missing_history", unknown["reason_code"], unknown["reason"]
        else:
            status, code, reason = "available", "READY", availability_reason
        for predicate in positive:
            fact = facts[predicate["fact"]]
            refs.extend(fact.refs)
            notes.extend(fact.unknown)
        if not exercised:
            notes.append(unknown["reason"])
        notes.append("Absence of an extant record is not proof that an operation never occurred.")
        unique_refs = {_canonical(ref): ref for ref in refs}
        results.append({"capability_id":definition["capability_id"], "definition_version":definition["definition_version"],
            "status":status, "reason_code":code, "reason":reason,
            "availability":availability, "availability_reason_code":availability_code, "availability_reason":availability_reason,
            "prerequisites_satisfied":satisfied, "prerequisites_missing":missing,
            "evidence_refs":[unique_refs[key] for key in sorted(unique_refs)], "coverage_or_unknown_notes":sorted(set(notes))})
    return {"schema":RESULT_SCHEMA, "registry_version":registry["registry_version"], "evaluator_version":EVALUATOR_VERSION,
        "registry_sha256":hashlib.sha256(_canonical(registry)).hexdigest(),
        "workspace":deepcopy(lineage["workspace"]), "lineage_coverage":deepcopy(lineage["coverage"]), "capabilities":results}
