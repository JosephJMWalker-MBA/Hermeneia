"""Explicit, append-only historical Perspective achievement assertions.

Preparation is read-only. Only materialization writes, after exact approval and
canonical re-evaluation in its own transaction. No model output is copied here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3
import uuid

from .perspective_execution_receipts import (
    TABLE as EXECUTION_TABLE, canonical_bytes, execution_references, receipt_from_row,
    validate_execution_references,
)

TABLE = "achievement_awards"
SCHEMA = "hermeneia.perspective-achievement-award/v1"
CAPABILITY = "perspective-achievement-awards-v1"
PACKAGE_PROFILE = "perspective-achievement-evidence-package/v1"
_PACKAGE_DOMAIN = b"hermeneia.perspective-achievement-evidence-package/v1\0"
_AWARD_DOMAIN = b"hermeneia.perspective-achievement-award/v1\0"
_ID_PREFIX = "achievement-award:sha256:"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SUPPORTED_RULES_SHA256 = {
    "1.0.0": "sha256:6b0065fac155c40fc25ce5cc62c53a7c250c0595dd4e49554669bab55e56197c",
}
_RECEIPT_FIELDS = {"schema", "award_id", "achievement_id", "rule_id", "rule_version",
                   "evaluation_status", "earned_at", "awarded_at", "issuer", "issuance",
                   "evidence_package", "evidence_package_sha256"}
_FINDING_FIELDS = {"achievement_id", "rule_id", "rule_version", "rule_reference", "rule_sha256",
                   "status", "reason_code", "reason", "evidence_refs", "qualifying_receipt_ids",
                   "validated_evidence", "coverage", "selection_basis"}
_SECOND_FIELDS = {"question_comparison_basis", "scope_comparison_basis", "perspective_distinctness_basis"}
_SLOT_FIELDS = ("achievement_id", "rule_id", "rule_version")


class InvalidAward(ValueError):
    """Claimed supported receipt fails integrity or structural validation."""


class UnsupportedAward(ValueError):
    """Wire/profile or released evaluator support is unavailable."""


class StaleAssessment(ValueError):
    """Approved package differs from the current canonical earned assessment."""


def _require(condition, message):
    if not condition:
        raise InvalidAward(message)


def _keys(value, fields, name):
    _require(isinstance(value, dict) and set(value) == set(fields), f"Invalid {name} fields")


def _text(value, name):
    _require(isinstance(value, str) and bool(value.strip()), f"Invalid {name}")


def _digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _hash(value, name):
    _require(isinstance(value, str) and _DIGEST.fullmatch(value) is not None, f"Invalid {name} digest")


def _time(value):
    _text(value, "timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "Unknown timestamp zone")
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise InvalidAward("Invalid aware timestamp") from exc


def _record(value, table=None):
    _keys(value, {"table", "key"}, "typed record")
    _text(value["table"], "record table")
    if table is not None:
        _require(value["table"] == table, "Typed record table mismatch")
    fields = {"old_id", "new_id", "reason", "ratified_at"} if value["table"] == "supersession_relations" else {"id"}
    _keys(value["key"], fields, "typed key")
    for item in value["key"].values():
        _text(item, "record identity")
    return value["key"].get("id")


def _dependencies(values):
    _require(isinstance(values, list), "Invalid dependency evidence")
    identities = []
    for value in values:
        _keys(value, {"record", "record_sha256", "basis"}, "dependency")
        _record(value["record"])
        _hash(value["record_sha256"], "dependency")
        table = value["record"]["table"]
        _require(table in {"source_documents", "source_extractions", "observations", "reader_highlights", "perspectives"}, "Unsupported dependency table")
        expected_basis = "evaluation_snapshot" if table in {"source_documents", "reader_highlights"} else "immutable_reference"
        _require(value["basis"] == expected_basis, "Invalid dependency mutability basis")
        identities.append((value["record"]["table"], value["record"]["key"]["id"]))
    _require(identities == sorted(set(identities)), "Invalid dependency order or duplicate")


def _eligibility(values):
    _require(isinstance(values, list), "Invalid eligibility observations")
    identities = []
    for value in values:
        _require(isinstance(value, dict), "Invalid eligibility observation")
        table = value.get("record", {}).get("table")
        fields = {"record", "excluded_from_analysis", "file_hash"} if table == "source_documents" else {"record", "source_document_id", "observation_id"}
        _keys(value, fields, "eligibility observation")
        _require(table in {"source_documents", "reader_highlights"}, "Unsupported eligibility record")
        identifier = _record(value["record"], table)
        if table == "source_documents":
            _require(type(value["excluded_from_analysis"]) is int and value["excluded_from_analysis"] == 0, "Historical source was not eligible")
            _text(value["file_hash"], "source hash")
        else:
            _text(value["source_document_id"], "highlight source")
            _require(value["observation_id"] is None or isinstance(value["observation_id"], str), "Invalid highlight observation")
        identities.append((table, identifier))
    _require(identities == sorted(set(identities)), "Invalid eligibility order or duplicate")


def _family(execution):
    value = execution["family_evidence"]
    if execution["family_state"] != "supported":
        _require(value == {}, "Unresolved family has invented evidence")
        return
    family = execution["family_key"]
    if family[0] == "built_in":
        _keys(value, {"origin", "id", "version", "definition_fingerprint"}, "built-in family")
        _require(value["origin"] == "built_in" and value["id"] == family[1], "Built-in family binding mismatch")
        _text(value["version"], "family version")
        _text(value["definition_fingerprint"], "family definition fingerprint")
    elif family[0] == "canonical_saved":
        _keys(value, {"root_id", "perspectives", "supersessions"}, "saved family")
        _require(value["root_id"] == family[1], "Family root mismatch")
        _require(isinstance(value["perspectives"], list) and bool(value["perspectives"])
                 and isinstance(value["supersessions"], list), "Missing family proof")
        for item in value["perspectives"] + value["supersessions"]:
            _keys(item, {"record", "sha256"}, "family proof")
            _require(item["record"].get("table") in {"perspectives", "supersession_relations"}, "Invalid family proof type")
            _record(item["record"])
            _hash(item["sha256"], "family proof")
        _require(all(item["record"]["table"] == "perspectives" for item in value["perspectives"])
                 and all(item["record"]["table"] == "supersession_relations" for item in value["supersessions"]), "Mixed family proof types")
        ids = [item["record"]["key"]["id"] for item in value["perspectives"]]
        _require(len(ids) == len(set(ids)) and ids[-1] == family[1]
                 and len(value["supersessions"]) == len(ids) - 1, "Invalid family proof chain")
        for index, edge in enumerate(value["supersessions"]):
            _require(edge["record"]["key"]["new_id"] == ids[index]
                     and edge["record"]["key"]["old_id"] == ids[index + 1], "Family edge mismatch")
    else:
        raise InvalidAward("Unknown family namespace")


def _lineage(value):
    _keys(value, {"record", "event", "record_type", "authorship", "provenance", "timestamp"}, "Lineage reference")
    identifier = _record(value["record"], EXECUTION_TABLE)
    _require(re.fullmatch(r"perspective-execution-receipt:sha256:[0-9a-f]{64}", identifier) is not None, "Invalid canonical receipt ID")
    _require((value["event"], value["record_type"], value["authorship"]) ==
             ("recorded", "retained_perspective_execution", "model"), "Invalid retained Lineage classification")
    _keys(value["provenance"], {"basis", "references", "records", "perspective", "execution",
                               "execution_created_at", "execution_completed_at", "retention", "receipt_schema",
                               "prompt_sha256", "scope_sha256", "question_sha256", "response_sha256"}, "Lineage provenance")
    stamp = value["timestamp"]
    _keys(stamp, {"field", "value", "status", "sort_key"}, "Lineage timestamp")
    instant = _time(stamp["value"])
    _require(stamp["field"] == "retention.retained_at" and stamp["status"] == "ordered"
             and stamp["sort_key"] == instant.isoformat(timespec="microseconds"), "Invalid retained Lineage timestamp")
    provenance = value["provenance"]
    _text(provenance["basis"], "Lineage provenance basis")
    _require(provenance["records"] == [] and isinstance(provenance["execution"], dict), "Invalid captured execution metadata")
    _require(isinstance(provenance["references"], list), "Invalid captured references")
    references = []
    for ref in provenance["references"]:
        ref_id = _record(ref)
        _require(ref["table"] in {"source_documents", "source_extractions", "reader_highlights", "perspectives"}, "Unsupported captured P3 reference")
        references.append((ref["table"], ref_id))
    _require(references == sorted(set(references)), "Captured reference order or duplication")
    retention = provenance.get("retention")
    _keys(retention, {"decision", "actor", "actor_identity", "retained_at"}, "captured retention")
    _require(retention == {"decision": "retain", "actor": "local_steward", "actor_identity": "unknown", "retained_at": stamp["value"]}, "Captured retention mismatch")
    _require(provenance.get("receipt_schema") == "hermeneia.perspective-execution-receipt/v1", "Captured receipt schema mismatch")
    for field in ("question_sha256", "scope_sha256", "prompt_sha256", "response_sha256"):
        _hash(provenance.get(field), "captured " + field)
    _require(_time(provenance.get("execution_created_at")) <= _time(provenance.get("execution_completed_at")) <= instant, "Captured execution time order mismatch")
    perspective = provenance.get("perspective")
    _keys(perspective, {"id", "version", "origin", "definition_fingerprint", "definition", "metadata"}, "captured Perspective")
    _keys(perspective["definition"], {"label", "purpose", "questions", "challenges", "limitations"}, "captured definition")
    _require(isinstance(perspective["metadata"], dict), "Invalid open Perspective metadata")
    _require(perspective.get("definition_fingerprint") == _digest(canonical_bytes(perspective["definition"])), "Captured Perspective fingerprint mismatch")
    return identifier, instant


def evidence_package_digest(package):
    return _digest(_PACKAGE_DOMAIN + canonical_bytes(package))


def _award_id(receipt):
    return _ID_PREFIX + hashlib.sha256(_AWARD_DOMAIN + canonical_bytes(
        {key: value for key, value in receipt.items() if key != "award_id"})).hexdigest()


def validate_evidence_package(package):
    """Strict understood wire shape; executable rule support is a separate check."""
    try:
        canonical_bytes(package)  # finite JSON, string keys; retain all open metadata
        _keys(package, {"profile", "assessment", "adapter_basis", "rule_definitions", "witness_bindings"}, "evidence package")
        if package["profile"] != PACKAGE_PROFILE:
            raise UnsupportedAward("Unsupported award evidence package profile")
        assessment, basis = package["assessment"], package["adapter_basis"]
        _keys(assessment, {"result_schema", "evaluator_version", "rules_sha256", "evidence_sha256", "finding", "coverage", "diagnostics", "limitations"}, "assessment")
        if assessment["result_schema"] != "hermeneia.perspective-achievement-evaluation/v1":
            raise UnsupportedAward("Unsupported achievement result schema")
        _text(assessment["evaluator_version"], "evaluator version")
        _keys(basis, {"source_state", "coverage", "diagnostics", "executions"}, "adapter basis")
        _require(basis["source_state"] == "supported", "Award requires supported evidence snapshot")
        _require(isinstance(assessment["coverage"], dict), "Invalid assessment coverage")
        _keys(assessment["coverage"], {"source", "receipt_schema", "capability", "historical_completeness", "reason", "status", "extant_records", "eligible_records", "classified_records", "family_states"}, "coverage")
        coverage = assessment["coverage"]
        _require(coverage["status"] == "covered" and coverage["source"] == "local_sqlite_snapshot"
                 and coverage["receipt_schema"] == "hermeneia.perspective-execution-receipt/v1"
                 and coverage["capability"] == "perspective-retained-execution-v1"
                 and coverage["historical_completeness"] == "unknown", "Invalid award coverage")
        _text(coverage["reason"], "coverage limitation")
        _keys(coverage["classified_records"], {"eligible", "excluded", "unsupported", "invalid"}, "classified coverage")
        _keys(coverage["family_states"], {"supported", "unsupported", "invalid"}, "family coverage")
        counts = [coverage["extant_records"], coverage["eligible_records"], *coverage["classified_records"].values(), *coverage["family_states"].values()]
        _require(all(type(value) is int and value >= 0 for value in counts), "Invalid coverage counts")
        _require(sum(coverage["classified_records"].values()) == coverage["extant_records"]
                 and coverage["classified_records"]["eligible"] == coverage["eligible_records"]
                 and sum(coverage["family_states"].values()) == coverage["eligible_records"], "Coverage count mismatch")
        _require(assessment["coverage"] == basis["coverage"] and assessment["diagnostics"] == basis["diagnostics"], "Assessment snapshot mismatch")
        _require(isinstance(assessment["diagnostics"], list), "Invalid diagnostics")
        for diagnostic in assessment["diagnostics"]:
            _keys(diagnostic, {"state", "stage", "reason_code", "record"}, "diagnostic")
            _require(diagnostic["state"] in {"excluded", "unsupported", "invalid"}, "Invalid diagnostic state")
            _require(diagnostic["stage"] in {"source", "family", "execution"}, "Invalid diagnostic stage")
            _text(diagnostic["reason_code"], "diagnostic code")
            if diagnostic["record"] is not None:
                _record(diagnostic["record"], EXECUTION_TABLE)
        _require(isinstance(assessment["limitations"], list) and all(isinstance(x, str) for x in assessment["limitations"]), "Invalid limitations")
        rules = package["rule_definitions"]
        _require(isinstance(rules, list) and bool(rules), "Missing rule definitions")
        slots = []
        for rule in rules:
            _require(isinstance(rule, dict), "Invalid open rule definition")
            for key in _SLOT_FIELDS:
                _text(rule.get(key), "rule identity")
            slots.append(tuple(rule[key] for key in _SLOT_FIELDS))
        _require(len(set(slots)) == len(slots), "Duplicate rule definition")
        _hash(assessment["rules_sha256"], "rules")
        _hash(assessment["evidence_sha256"], "evidence")
        _require(assessment["rules_sha256"] == _digest(canonical_bytes(rules)), "Rule registry digest mismatch")
        _require(assessment["evidence_sha256"] == _digest(canonical_bytes(basis)), "Evidence basis digest mismatch")
        finding = assessment["finding"]
        _require(isinstance(finding, dict), "Invalid finding")
        second = finding.get("achievement_id") == "second_opinion"
        _keys(finding, _FINDING_FIELDS | (_SECOND_FIELDS if second else set()), "finding")
        for key in _SLOT_FIELDS:
            _text(finding[key], "finding identity")
        _require(finding["achievement_id"] in {"perspective_explorer", "second_opinion"}, "Unknown achievement wire shape")
        _require(finding["status"] == "earned" and finding["coverage"] == coverage, "Award finding is not earned or coverage differs")
        _require(finding["rule_reference"] == finding["rule_id"] + ".v" + finding["rule_version"], "Rule reference mismatch")
        _text(finding["reason_code"], "finding reason code")
        _text(finding["reason"], "finding reason")
        definition = [rule for rule in rules if all(rule[k] == finding[k] for k in _SLOT_FIELDS)]
        _require(len(definition) == 1, "Missing selected rule definition")
        _require(finding["rule_sha256"] == _digest(canonical_bytes(definition[0])), "Selected rule digest mismatch")
        _require(isinstance(basis["executions"], list), "Invalid candidate basis")
        candidates, ordered = {}, []
        for execution in basis["executions"]:
            _keys(execution, {"receipt_sha256", "lineage_ref", "family_key", "family_state", "family_evidence", "family_reason_code", "dependency_evidence", "eligibility_observations"}, "execution basis")
            _hash(execution["receipt_sha256"], "candidate receipt")
            identifier, instant = _lineage(execution["lineage_ref"])
            _require(identifier not in candidates, "Duplicate candidate identity")
            _require(execution["family_state"] in {"supported", "unsupported", "invalid"}, "Invalid family state")
            family_key = execution["family_key"]
            _require(family_key is None or (isinstance(family_key, list) and len(family_key) == 2 and all(isinstance(x, str) and x for x in family_key)), "Invalid family key")
            _require(isinstance(execution["family_evidence"], dict), "Invalid family evidence")
            if execution["family_state"] == "supported":
                _require(family_key is not None and execution["family_reason_code"] is None, "Invalid supported family binding")
            else:
                _require(family_key is None, "Unresolved family acquired identity")
                _text(execution["family_reason_code"], "family limitation")
            _family(execution)
            _dependencies(execution["dependency_evidence"])
            _eligibility(execution["eligibility_observations"])
            candidates[identifier] = execution
            ordered.append((instant, identifier))
        _require(ordered == sorted(ordered), "Candidate K order mismatch")
        _require(len(candidates) == coverage["eligible_records"], "Candidate coverage mismatch")
        _require(coverage["family_states"] == {state: sum(execution["family_state"] == state for execution in basis["executions"])
                                               for state in ("supported", "unsupported", "invalid")}, "Family coverage histogram mismatch")
        _require(coverage["classified_records"] == {"eligible": len(candidates), **{
            state: sum(item["stage"] == "execution" and item["state"] == state for item in assessment["diagnostics"])
            for state in ("excluded", "unsupported", "invalid")}}, "Execution coverage histogram mismatch")
        selection = finding["selection_basis"]
        _keys(selection, {"order", "candidate_receipt_ids", "selected"}, "selection basis")
        _require(selection["order"] == "retained_at_utc_then_receipt_id_ascii"
                 and selection["candidate_receipt_ids"] == list(candidates), "Selection candidate order mismatch")
        ids, bindings = finding["qualifying_receipt_ids"], package["witness_bindings"]
        arrays = [ids, bindings, finding["evidence_refs"], finding["validated_evidence"], selection["selected"]]
        size = 2 if second else 1
        _require(all(isinstance(value, list) and len(value) == size for value in arrays), "Invalid witness cardinality")
        _require(len(set(ids)) == size and all(identifier in candidates for identifier in ids), "Missing or duplicate witness")
        _require(ids == sorted(ids, key=lambda key: (_time(candidates[key]["lineage_ref"]["timestamp"]["value"]), key)), "Witness K order mismatch")
        if not second:
            _require(ids == list(candidates)[:1], "Explorer witness selection mismatch")
        run_ids, times = [], []
        for index, identifier in enumerate(ids):
            execution, binding = candidates[identifier], bindings[index]
            _keys(binding, {"receipt_id", "run_id", "receipt_sha256"}, "witness binding")
            _text(binding["run_id"], "witness run ID")
            uuid.UUID(binding["run_id"])  # Same accepted identity shape as P3; no rewriting.
            _require(binding["receipt_id"] == identifier and binding["receipt_sha256"] == execution["receipt_sha256"], "Witness digest binding mismatch")
            _require(finding["evidence_refs"][index] == execution["lineage_ref"], "Witness Lineage binding mismatch")
            validated = finding["validated_evidence"][index]
            _keys(validated, {"receipt_id", "receipt_sha256", "dependency_evidence", "eligibility_observations"}, "validated witness")
            _require(validated == {"receipt_id": identifier, **{key: execution[key] for key in ("receipt_sha256", "dependency_evidence", "eligibility_observations")}}, "Validated witness differs from basis")
            selected = selection["selected"][index]
            _keys(selected, {"receipt_id", "retained_at", "retained_at_utc"}, "selected time")
            instant = _time(selected["retained_at"])
            _require(selected["receipt_id"] == identifier and selected["retained_at"] == execution["lineage_ref"]["timestamp"]["value"]
                     and selected["retained_at_utc"] == instant.isoformat(), "Selected time binding mismatch")
            times.append(instant)
            run_ids.append(binding["run_id"])
        _require(len(set(run_ids)) == size, "Duplicate selected execution")
        if second:
            question, scope, distinct = [finding[key] for key in ("question_comparison_basis", "scope_comparison_basis", "perspective_distinctness_basis")]
            _keys(question, {"codec", "sha256", "bytes_equal"}, "question comparison")
            _keys(scope, {"codec", "sha256", "bytes_equal", "receipt_version", "prompt_version"}, "Scope comparison")
            _keys(distinct, {"family_keys", "revision_ids", "definition_fingerprints", "methodology_fields", "methodology_sha256", "family_evidence", "methodology_bytes_different"}, "Perspective distinctness")
            _hash(question["sha256"], "question")
            _hash(scope["sha256"], "Scope")
            _require(question["codec"] == "exact_utf8" and question["bytes_equal"] is True
                     and scope["codec"] == "complete_p3_canonical_bytes" and scope["bytes_equal"] is True
                     and scope["receipt_version"] == "resolved-scope:v1" and scope["prompt_version"] == "perspective-run/v1", "Invalid exact inquiry comparison")
            selected_executions = [candidates[key] for key in ids]
            _require(all(x["family_state"] == "supported" for x in selected_executions)
                     and distinct["family_keys"] == [x["family_key"] for x in selected_executions]
                     and distinct["family_keys"][0] != distinct["family_keys"][1]
                     and distinct["family_evidence"] == [x["family_evidence"] for x in selected_executions], "Invalid selected family comparison")
            for key in ("revision_ids", "definition_fingerprints", "methodology_sha256"):
                _require(isinstance(distinct[key], list) and len(distinct[key]) == size and all(isinstance(x, str) and x for x in distinct[key]), "Invalid distinctness array")
            for value in distinct["methodology_sha256"]:
                _hash(value, "methodology")
            _require(distinct["methodology_bytes_different"] is True and distinct["methodology_sha256"][0] != distinct["methodology_sha256"][1]
                     and distinct["definition_fingerprints"][0] != distinct["definition_fingerprints"][1], "Invalid methodology distinctness")
            _require(distinct["methodology_fields"] == definition[0].get("methodology_fields"), "Methodology definition mismatch")
            provenance = [execution["lineage_ref"]["provenance"] for execution in selected_executions]
            perspectives = [value["perspective"] for value in provenance]
            _require(all(question["sha256"] == value["question_sha256"] and scope["sha256"] == value["scope_sha256"] for value in provenance), "Captured inquiry digest mismatch")
            _require(distinct["revision_ids"] == [value["id"] for value in perspectives]
                     and distinct["definition_fingerprints"] == [value["definition_fingerprint"] for value in perspectives], "Captured Perspective comparison mismatch")
            methodology = [_digest(canonical_bytes({field: value["definition"][field] for field in distinct["methodology_fields"]})) for value in perspectives]
            _require(distinct["methodology_sha256"] == methodology, "Captured methodology digest mismatch")
        return max(times).isoformat()
    except (InvalidAward, UnsupportedAward):
        raise
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, UnicodeError) as exc:
        raise InvalidAward("Malformed award evidence package") from exc


def validate_award_receipt(receipt):
    try:
        canonical_bytes(receipt)
        _keys(receipt, _RECEIPT_FIELDS, "award receipt")
        if receipt["schema"] != SCHEMA:
            raise UnsupportedAward("Unsupported award receipt schema")
        earned_at = validate_evidence_package(receipt["evidence_package"])
        finding = receipt["evidence_package"]["assessment"]["finding"]
        _require(all(receipt[key] == finding[key] for key in _SLOT_FIELDS), "Award slot binding mismatch")
        _require(receipt["evaluation_status"] == "earned", "Award is not earned")
        _require(receipt["earned_at"] == earned_at, "Earned timestamp mismatch")
        _require(receipt["awarded_at"] == _time(receipt["awarded_at"]).isoformat(), "Award timestamp is not UTC canonical")
        _require(receipt["issuer"] == {"kind": "hermeneia", "authorship": "derived"}, "Invalid issuer")
        _keys(receipt["issuance"], {"policy", "actor", "actor_identity", "approved_evidence_package_sha256"}, "issuance")
        digest = evidence_package_digest(receipt["evidence_package"])
        _require(receipt["evidence_package_sha256"] == digest, "Evidence package digest mismatch")
        _require(receipt["issuance"] == {"policy": "explicit-steward-materialization/v1", "actor": "local_steward", "actor_identity": "unknown", "approved_evidence_package_sha256": digest}, "Invalid explicit issuance binding")
        _require(receipt["award_id"] == _award_id(receipt), "Award ID mismatch")
        return receipt
    except (InvalidAward, UnsupportedAward):
        raise
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, UnicodeError) as exc:
        raise InvalidAward("Malformed award receipt") from exc


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate award JSON key")
        result[key] = value
    return result


def award_from_row(row):
    try:
        _keys(dict(row), {"id", "achievement_id", "rule_id", "rule_version", "receipt_json"}, "stored award row")
        raw = row["receipt_json"]
        _require(isinstance(raw, str), "Award JSON must be UTF-8 text")
        receipt = json.loads(raw, object_pairs_hook=_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(InvalidAward("Nonfinite JSON")))
        validate_award_receipt(receipt)
        _require(raw.encode("utf-8") == canonical_bytes(receipt), "Stored award bytes are not canonical")
        _require(row["id"] == receipt["award_id"] and all(row[key] == receipt[key] for key in _SLOT_FIELDS), "Stored award binding mismatch")
        return receipt
    except (InvalidAward, UnsupportedAward):
        raise
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, UnicodeError) as exc:
        raise InvalidAward("Malformed stored award") from exc


def perspective_achievement_rules():
    from .perspective_achievements import perspective_achievement_rules as rules
    return rules()


def historical_profile_supported(receipt):
    package = receipt["evidence_package"]
    assessment = package["assessment"]
    return _SUPPORTED_RULES_SHA256.get(assessment["evaluator_version"]) == assessment["rules_sha256"]


def _released_rules():
    from .perspective_achievements import EVALUATOR_VERSION
    rules = perspective_achievement_rules()
    if _SUPPORTED_RULES_SHA256.get(EVALUATOR_VERSION) != _digest(canonical_bytes(rules)):
        raise UnsupportedAward("Released rule definition conflict or unsupported evaluator")
    return rules


def _prepare(conn, achievement_id, rule_id, rule_version):
    from .perspective_achievement_evidence import read_perspective_achievement_evidence
    from .perspective_achievements import achievement_evidence_basis, evaluate_perspective_achievements
    rules = _released_rules()
    matches = [rule for rule in rules if rule["achievement_id"] == achievement_id and rule["rule_id"] == rule_id and rule["rule_version"] == rule_version]
    if len(matches) != 1:
        raise UnsupportedAward("Unsupported released achievement rule")
    evidence = read_perspective_achievement_evidence(conn)
    result = evaluate_perspective_achievements(evidence)
    finding = next(item for item in result["achievements"] if item["achievement_id"] == achievement_id)
    if finding["status"] != "earned":
        raise StaleAssessment("Canonical assessment is not earned: " + finding["status"])
    by_id = {}
    for execution in evidence.executions:
        raw = json.loads(execution.receipt_json)
        by_id[raw["id"]] = (raw, execution.receipt_json)
    package = {
        "profile": PACKAGE_PROFILE,
        "assessment": {"result_schema": result["schema"], **{key: result[key] for key in ("evaluator_version", "rules_sha256", "evidence_sha256", "coverage", "diagnostics", "limitations")}, "finding": finding},
        "adapter_basis": achievement_evidence_basis(evidence),
        "rule_definitions": rules,
        "witness_bindings": [{"receipt_id": identifier, "run_id": by_id[identifier][0]["run"]["run_id"], "receipt_sha256": _digest(by_id[identifier][1].encode("utf-8"))} for identifier in finding["qualifying_receipt_ids"]],
    }
    validate_evidence_package(package)
    return package


def prepare_perspective_achievement_award(conn, achievement_id, rule_id=None, rule_version="1.0.0"):
    """Read one coherent canonical snapshot; no table initialization or writes."""
    own = not conn.in_transaction
    if own:
        conn.execute("BEGIN")
    try:
        return _prepare(conn, achievement_id, rule_id or "achievement." + achievement_id, rule_version)
    finally:
        if own and conn.in_transaction:
            conn.rollback()


def make_award_receipt(package, *, awarded_at):
    earned_at = validate_evidence_package(package)
    digest = evidence_package_digest(package)
    finding = package["assessment"]["finding"]
    receipt = {
        "schema": SCHEMA, **{key: finding[key] for key in _SLOT_FIELDS},
        "evaluation_status": "earned", "earned_at": earned_at,
        "awarded_at": _time(awarded_at).isoformat(),
        "issuer": {"kind": "hermeneia", "authorship": "derived"},
        "issuance": {"policy": "explicit-steward-materialization/v1", "actor": "local_steward", "actor_identity": "unknown", "approved_evidence_package_sha256": digest},
        "evidence_package": json.loads(canonical_bytes(package)), "evidence_package_sha256": digest,
    }
    receipt["award_id"] = _award_id(receipt)
    return validate_award_receipt(receipt)


def ensure_achievement_award_tables(conn):
    """Explicit additive initialization, never called by reads or materialization."""
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (id TEXT PRIMARY KEY, achievement_id TEXT NOT NULL, rule_id TEXT NOT NULL, rule_version TEXT NOT NULL, receipt_json TEXT NOT NULL, UNIQUE(achievement_id, rule_id, rule_version))")
    for operation in ("UPDATE", "DELETE"):
        conn.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_{operation.lower()} BEFORE {operation} ON {TABLE} BEGIN SELECT RAISE(ABORT, 'Achievement award immutable'); END")
    conn.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_replace BEFORE INSERT ON {TABLE} WHEN EXISTS(SELECT 1 FROM {TABLE} WHERE id=NEW.id OR (achievement_id=NEW.achievement_id AND rule_id=NEW.rule_id AND rule_version=NEW.rule_version)) BEGIN SELECT RAISE(ABORT, 'Achievement award slot already exists'); END")


def _row(conn, sql, parameters):
    cursor = conn.execute(sql, parameters)
    raw = cursor.fetchone()
    return dict(zip((col[0] for col in cursor.description), raw)) if raw is not None else None


def load_achievement_award(conn, award_id):
    row = _row(conn, f"SELECT * FROM {TABLE} WHERE id=?", (award_id,))
    if row is None:
        raise InvalidAward("Missing award record")
    return award_from_row(row)


def _now():
    return datetime.now(timezone.utc).isoformat()


def materialize_perspective_achievement_award(conn, achievement_id, rule_id, rule_version, evidence_package_sha256):
    """Return status plus receipt; retry status never alters historical bytes."""
    if conn.in_transaction:
        raise InvalidAward("Award requires committed evidence and a separate transaction")
    _hash(evidence_package_sha256, "approved package")
    conn.execute("BEGIN IMMEDIATE")
    try:
        rules = _released_rules()
        definition = next((rule for rule in rules if all(rule[key] == value for key, value in zip(_SLOT_FIELDS, (achievement_id, rule_id, rule_version)))), None)
        if definition is None:
            raise UnsupportedAward("Unsupported released achievement rule")
        try:
            existing = _row(conn, f"SELECT * FROM {TABLE} WHERE achievement_id=? AND rule_id=? AND rule_version=?", (achievement_id, rule_id, rule_version))
        except sqlite3.OperationalError as exc:
            raise UnsupportedAward("Award schema is unavailable; explicit initialization required") from exc
        if existing is not None:
            receipt = award_from_row(existing)
            finding = receipt["evidence_package"]["assessment"]["finding"]
            _require(finding["rule_sha256"] == _digest(canonical_bytes(definition)), "Historical released definition conflict")
        else:
            package = _prepare(conn, achievement_id, rule_id, rule_version)
            if evidence_package_digest(package) != evidence_package_sha256:
                raise StaleAssessment("Approved evidence package is stale")
            receipt = make_award_receipt(package, awarded_at=_now())
            encoded = canonical_bytes(receipt).decode("utf-8")
            conn.execute(f"INSERT INTO {TABLE} (id,achievement_id,rule_id,rule_version,receipt_json) VALUES (?,?,?,?,?)", (receipt["award_id"], achievement_id, rule_id, rule_version, encoded))
            installed = load_achievement_award(conn, receipt["award_id"])
            _require(canonical_bytes(installed) == encoded.encode("utf-8"), "Installed award bytes diverge")
        conn.commit()
        return {"status": "already_recorded" if existing is not None else "recorded", "receipt": receipt}
    except BaseException:
        conn.rollback()
        raise


def validate_award_references(conn, receipt):
    """Strict archival closure, distinct from eligibility/historical replay."""
    validate_award_receipt(receipt)
    package = receipt["evidence_package"]
    selected = {binding["receipt_id"]: binding for binding in package["witness_bindings"]}
    for execution in package["adapter_basis"]["executions"]:
        identifier = execution["lineage_ref"]["record"]["key"]["id"]
        row = _row(conn, f"SELECT * FROM {EXECUTION_TABLE} WHERE id=?", (identifier,))
        _require(row is not None, "Missing award candidate receipt")
        parent = receipt_from_row(row)
        validate_award_parent_binding(execution, parent)
        _require(_digest(row["receipt_json"].encode("utf-8")) == execution["receipt_sha256"], "Award candidate receipt digest mismatch")
        if identifier in selected:
            _require(parent["run"]["run_id"] == selected[identifier]["run_id"], "Award witness run binding mismatch")
        validate_execution_references(conn, parent)
        for dependency in execution["dependency_evidence"]:
            ref = dependency["record"]
            _require(ref["table"] in {"source_documents", "source_extractions", "observations", "reader_highlights", "perspectives"}, "Unsupported award dependency table")
            row = _row(conn, f'SELECT * FROM "{ref["table"]}" WHERE id=?', (ref["key"]["id"],))
            _require(row is not None, "Missing award dependency")
            if dependency["basis"] == "immutable_reference":
                _require(_digest(canonical_bytes(row)) == dependency["record_sha256"], "Award immutable dependency digest mismatch")
        if receipt["achievement_id"] == "second_opinion" and identifier in selected:
            from .perspective_achievement_evidence import _EvidenceProblem, _Snapshot
            try:
                family, evidence = _Snapshot(conn).family(parent["run"]["perspective"])
            except _EvidenceProblem as exc:
                raise InvalidAward("Award family closure unavailable or invalid") from exc
            _require(list(family) == execution["family_key"] and evidence == execution["family_evidence"], "Award family closure mismatch")


def validate_award_parent_binding(execution, parent):
    """Bind captured metadata to exact P3 bytes, independent of current access."""
    run = parent["run"]
    reference = execution["lineage_ref"]
    _require(reference["record"]["key"]["id"] == parent["id"]
             and reference["timestamp"]["value"] == parent["retention"]["retained_at"], "Captured P3 identity or time mismatch")
    expected = {
        "perspective": run["perspective"], "execution": run["execution"],
        "execution_created_at": run["created_at"], "execution_completed_at": run["completed_at"],
        "retention": parent["retention"], "receipt_schema": parent["schema"],
        **{key: run[key] for key in ("prompt_sha256", "scope_sha256", "question_sha256", "response_sha256")},
        "references": execution_references(parent), "records": [],
    }
    _require(all(reference["provenance"].get(key) == value for key, value in expected.items()), "Captured Lineage provenance differs from P3 parent")
    dependencies = {(value["record"]["table"], value["record"]["key"]["id"])
                    for value in execution["dependency_evidence"]}
    required = {(ref["table"], ref["key"]["id"]) for ref in execution_references(parent)}
    _require(required <= dependencies, "Required award dependency binding was not captured")
    eligibility = {(value["record"]["table"], value["record"]["key"]["id"]): value
                   for value in execution["eligibility_observations"]}
    _require({ref for ref in required if ref[0] in {"source_documents", "reader_highlights"}} <= set(eligibility), "Required eligibility binding was not captured")
    for (table, _), observation in eligibility.items():
        if table == "reader_highlights" and observation.get("observation_id"):
            _require(("observations", observation["observation_id"]) in dependencies, "Historical highlight Observation dependency was not captured")
