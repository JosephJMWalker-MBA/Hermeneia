"""Read-only checks of historical award bytes, witnesses and snapshot replay.

Recorded mutable-row digests cannot recover yesterday's rows. Checking the
recorded basis's own hash is receipt integrity, never independent replay.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import sqlite3

from .achievement_awards import UnsupportedAward, award_from_row, historical_profile_supported
from .perspective_achievement_evidence import (
    _EvidenceProblem, _FRAME_COLUMNS, _Snapshot, _check_frame_and_prompt,
    read_perspective_achievement_evidence,
)
from .perspective_achievements import (
    EVALUATOR_VERSION, SCHEMA as RESULT_SCHEMA, _different_methodology,
    _methodology, _same_inquiry, achievement_evidence_basis,
    evaluate_perspective_achievements, perspective_achievement_rules,
)
from .perspective_execution_receipts import (
    TABLE as EXECUTION_TABLE, canonical_bytes, execution_references,
    receipt_from_row, validate_execution_references,
)
from .perspective_identity import definition_from_frame_v2_row
from .perspective_runs import transient_perspective_semantics

SCHEMA = "hermeneia.perspective-achievement-award-verification/v1"
_AWARD_TABLE = "achievement_awards"
_EVIDENCE_PRECEDENCE = (
    "invalid_evidence", "unverifiable_missing_evidence", "unverifiable_missing_coverage",
    "unverifiable_unsupported_rule", "verified",
)
_REQUIRED = {
    "source_documents": {"id", "file_hash", "excluded_from_analysis"},
    "source_extractions": {"id", "document_id", "page", "source_locator", "raw_text"},
    "observations": {"id", "source_document_id", "source_extraction_id", "raw_text"},
    "reader_highlights": {"id", "source_document_id"},
    "perspectives": _FRAME_COLUMNS,
    "supersession_relations": {"old_id", "new_id", "reason", "ratified_at"},
    EXECUTION_TABLE: {"id", "run_id", "receipt_json"},
    _AWARD_TABLE: {"id", "achievement_id", "rule_id", "rule_version", "receipt_json"},
}


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


class _Checks:
    def __init__(self, conn: sqlite3.Connection, award_id: str):
        self.conn = conn
        self.tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.columns: dict[str, set[str]] = {}
        self.checks: list[dict] = []
        self.report = {
            "schema": SCHEMA, "award_id": award_id,
            "receipt_integrity": "unsupported",
            "evidence_verification": "unverifiable_missing_coverage",
            "historical_snapshot_replay": "unsupported", "checks": self.checks,
            "limitations": [
                "Receipt hashes are integrity bindings, not authenticated issuance, participant identity or an external clock.",
                "Original mutable row bytes and complete past enumeration are not stored; recorded digests cannot restore lost snapshot material.",
                "Historical earned assessment, current eligibility and current verification remain separate.",
            ],
        }

    def add(self, dimension: str, state: str, code: str, record: dict | None = None) -> None:
        self.checks.append({"dimension": dimension, "state": state, "reason_code": code, "record": record})

    def evidence(self, state: str, code: str, record: dict | None = None) -> None:
        self.add("evidence_verification", state, code, record)

    def row(self, record: dict) -> dict | None:
        table, key = record["table"], record["key"]
        if not all(isinstance(value, str) and value for value in key.values()):
            self.evidence("invalid_evidence", "REQUIRED_REFERENCE_IDENTITY_INVALID")
            return None
        if table not in _REQUIRED:
            self.evidence("unverifiable_unsupported_rule", "REQUIRED_RECORD_PROFILE_UNSUPPORTED", record)
            return None
        if table not in self.tables:
            self.evidence("unverifiable_missing_coverage", "REQUIRED_TABLE_UNAVAILABLE", record)
            return None
        if table not in self.columns:
            cursor = self.conn.execute(f'SELECT * FROM "{table}" LIMIT 0')
            self.columns[table] = {column[0] for column in cursor.description}
        if not (_REQUIRED.get(table, set()) | set(key)) <= self.columns[table]:
            self.evidence("unverifiable_missing_coverage", "REQUIRED_COLUMNS_UNAVAILABLE", record)
            if not set(key) <= self.columns[table]:
                return None
        # Table/key names come only from the strict receipt validator; values
        # are always bound. Composite supersession identities remain exact.
        where = " AND ".join(f'"{field}" IS ?' for field in key)
        cursor = self.conn.execute(f'SELECT * FROM "{table}" WHERE {where}', tuple(key.values()))
        rows = cursor.fetchall()
        if not rows:
            self.evidence("unverifiable_missing_evidence", "REQUIRED_RECORD_UNAVAILABLE", record)
            return None
        if len(rows) != 1:
            self.evidence("invalid_evidence", "AMBIGUOUS_REQUIRED_RECORD", record)
            return None
        return dict(zip((column[0] for column in cursor.description), rows[0]))

    def bound_row(self, record: dict, expected: str, *, mutable: bool = False) -> dict | None:
        row = self.row(record)
        if row is None:
            return None
        if not _REQUIRED[record["table"]] <= self.columns[record["table"]]:
            # Available columns can still disclose a known binding violation,
            # but a digest of a partial row cannot prove byte-level tampering.
            return row
        try:
            matches = _digest(canonical_bytes(row)) == expected
        except (ValueError, TypeError, UnicodeError):
            self.evidence("invalid_evidence", "REQUIRED_RECORD_NOT_FINITE_JSON", record)
            return row
        if matches:
            self.evidence("verified", "REQUIRED_ROW_DIGEST_MATCHES", record)
        elif mutable:
            self.evidence("unverifiable_missing_coverage", "ORIGINAL_MUTABLE_SNAPSHOT_UNAVAILABLE", record)
        else:
            self.evidence("invalid_evidence", "IMMUTABLE_ROW_DIGEST_MISMATCH", record)
        return row

    def finish(self) -> dict:
        states = {check["state"] for check in self.checks if check["dimension"] == "evidence_verification"}
        self.report["evidence_verification"] = next(
            (state for state in _EVIDENCE_PRECEDENCE if state in states), "unverifiable_missing_coverage",
        )
        self.checks.sort(key=lambda value: canonical_bytes(value))
        return self.report


def _supported(receipt: dict) -> bool:
    assessment = receipt["evidence_package"]["assessment"]
    rules = perspective_achievement_rules()
    return (
        receipt["achievement_id"] in {"perspective_explorer", "second_opinion"}
        and receipt["rule_id"] == "achievement." + receipt["achievement_id"]
        and receipt["rule_version"] == "1.0.0"
        and assessment["result_schema"] == RESULT_SCHEMA
        and assessment["evaluator_version"] == EVALUATOR_VERSION == "1.0.0"
        and historical_profile_supported(receipt)
        and assessment["rules_sha256"] == _digest(canonical_bytes(rules))
        and receipt["evidence_package"]["rule_definitions"] == rules
    )


def _families(checks: _Checks, receipt: dict, witnesses: list[dict]) -> list[list | None]:
    package = receipt["evidence_package"]
    selected = {entry["lineage_ref"]["record"]["key"]["id"]: entry
                for entry in package["adapter_basis"]["executions"]}
    result = []
    snapshot = _Snapshot(checks.conn)
    for witness in witnesses:
        recorded = selected[witness["id"]]
        family = recorded["family_evidence"]
        try:
            key, current = snapshot.family(witness["run"]["perspective"])
            result.append(list(key))
            if list(key) == recorded["family_key"] and current == family:
                checks.evidence("verified", "REQUIRED_FAMILY_PROOF_MATCHES",
                                {"table": EXECUTION_TABLE, "key": {"id": witness["id"]}})
            else:
                # An appended graph edge cannot recover the old absence of
                # that edge. Contradictions in recorded rows were checked above.
                checks.evidence("unverifiable_missing_coverage", "ORIGINAL_FAMILY_GRAPH_SNAPSHOT_UNAVAILABLE")
        except (_EvidenceProblem, sqlite3.Error, ValueError, KeyError, TypeError, UnicodeError):
            result.append(None)
            checks.evidence("unverifiable_missing_coverage", "ORIGINAL_FAMILY_GRAPH_SNAPSHOT_UNAVAILABLE")
    return result


def _required_closure(checks: _Checks, witness: dict, validated: dict,
                      mutable_drift: set[tuple[str, str]]) -> None:
    """Establish ancestry from P3/current immutable rows, never a stored list.

    The package can bind a digest of an incomplete list. That is insufficient
    coverage; required closure and captured eligibility must also be present.
    """
    dependencies = {(value["record"]["table"], value["record"]["key"]["id"])
                    for value in validated["dependency_evidence"]}
    eligibility = {(value["record"]["table"], value["record"]["key"]["id"]): value
                   for value in validated["eligibility_observations"]}
    visited = set()

    def visit(table, identifier):
        if not isinstance(identifier, str) or not identifier:
            checks.evidence("invalid_evidence", "REQUIRED_REFERENCE_IDENTITY_INVALID")
            return
        token = (table, identifier)
        record = {"table": table, "key": {"id": identifier}}
        if token in visited:
            return
        visited.add(token)
        if token not in dependencies:
            checks.evidence("unverifiable_missing_coverage", "REQUIRED_DEPENDENCY_BINDING_NOT_CAPTURED", record)
        row = checks.row(record)
        if row is None:
            return
        if table in {"source_documents", "reader_highlights"} and token not in eligibility:
            checks.evidence("unverifiable_missing_coverage", "REQUIRED_ELIGIBILITY_OBSERVATION_NOT_CAPTURED", record)
        if table == "source_extractions" and "document_id" in row:
            visit("source_documents", row["document_id"])
        elif table == "observations" and {"source_document_id", "source_extraction_id"} <= set(row):
            visit("source_documents", row["source_document_id"])
            visit("source_extractions", row["source_extraction_id"])
            extraction = checks.row({"table": "source_extractions", "key": {"id": row["source_extraction_id"]}})
            if extraction is not None and "document_id" in extraction and extraction["document_id"] != row["source_document_id"]:
                checks.evidence("invalid_evidence", "OBSERVATION_SOURCE_BINDING_MISMATCH", record)
        elif table == "reader_highlights" and "source_document_id" in row:
            # Recover only historical identities already captured, never the
            # original mutable bytes. A changed mark retains a coverage limit.
            historical = eligibility.get(token, {})
            document = historical.get("source_document_id") if token in mutable_drift else row["source_document_id"]
            observation = historical.get("observation_id") if token in mutable_drift else row.get("observation_id")
            if document:
                visit("source_documents", document)
            if observation:
                visit("observations", observation)
    for reference in execution_references(witness):
        visit(reference["table"], reference["key"]["id"])
    scope = witness["run"]["scope_receipt"]
    for part in [scope["primary"], *scope["supporting"]]:
        source = eligibility.get(("source_documents", part["source_document_id"]))
        if source is not None and source["file_hash"] != scope["primary"]["source_document_hash"]:
            checks.evidence("invalid_evidence", "CAPTURED_SOURCE_HASH_BINDING_MISMATCH", source["record"])
        if part["kind"] == "reader_highlight":
            token = ("reader_highlights", part["id"])
            historical = eligibility.get(token)
            if historical is not None and historical["source_document_id"] != part["source_document_id"]:
                checks.evidence("invalid_evidence", "CAPTURED_HIGHLIGHT_SOURCE_BINDING_MISMATCH", historical["record"])
            continue
        for identifier in part["extraction_ids"]:
            record = {"table": "source_extractions", "key": {"id": identifier}}
            extraction = checks.row(record)
            if extraction is not None and {"document_id", "page", "source_locator"} <= set(extraction) and (
                    extraction["document_id"] != part["source_document_id"]
                    or extraction["page"] != part["page"]
                    or extraction["source_locator"] not in part["source_locators"]):
                checks.evidence("invalid_evidence", "P3_EXTRACTION_ASSOCIATION_MISMATCH", record)
    perspective = witness["run"]["perspective"]
    if perspective["origin"] != "built_in":
        record = {"table": "perspectives", "key": {"id": perspective["id"]}}
        row = checks.row(record)
        if row is not None and _FRAME_COLUMNS <= set(row):
            try:
                matches = (transient_perspective_semantics(definition_from_frame_v2_row(row)) == perspective["definition"]
                           and row.get("declared_by") == perspective["metadata"].get("declared_by")
                           and row.get("declared_date") == perspective["metadata"].get("declared_date"))
            except (ValueError, KeyError, TypeError, UnicodeError):
                matches = False
            if not matches:
                checks.evidence("invalid_evidence", "P3_SAVED_PERSPECTIVE_BINDING_MISMATCH", record)


def _lineage_binding(checks: _Checks, witness: dict, reference: dict) -> None:
    run = witness["run"]
    expected = {
        "references": execution_references(witness), "records": [],
        "perspective": run["perspective"], "execution": run["execution"],
        "execution_created_at": run["created_at"], "execution_completed_at": run["completed_at"],
        "retention": witness["retention"], "receipt_schema": witness["schema"],
        **{field: run[field] for field in ("prompt_sha256", "scope_sha256", "question_sha256", "response_sha256")},
    }
    if any(reference["provenance"].get(field) != value for field, value in expected.items()):
        checks.evidence("invalid_evidence", "CAPTURED_LINEAGE_P3_BINDING_MISMATCH",
                        {"table": EXECUTION_TABLE, "key": {"id": witness["id"]}})


def _check_witnesses(checks: _Checks, receipt: dict, supported: bool) -> None:
    package = receipt["evidence_package"]
    finding = package["assessment"]["finding"]
    if receipt["achievement_id"] == "second_opinion":
        selected = set(finding["qualifying_receipt_ids"])
        # Known immutable family bindings remain checkable even when the
        # historical evaluator is unavailable or a selected P3 row is missing.
        for execution in package["adapter_basis"]["executions"]:
            if execution["lineage_ref"]["record"]["key"]["id"] not in selected:
                continue
            for category in ("perspectives", "supersessions"):
                for binding in execution["family_evidence"].get(category, []):
                    checks.bound_row(binding["record"], binding["sha256"])
    witnesses = []
    mutable_drift: set[tuple[str, str]] = set()
    for validated in finding["validated_evidence"]:
        for dependency in validated["dependency_evidence"]:
            record = dependency["record"]
            before = len(checks.checks)
            checks.bound_row(record, dependency["record_sha256"],
                             mutable=dependency["basis"] == "evaluation_snapshot")
            if (dependency["basis"] == "evaluation_snapshot"
                    and any(check["reason_code"] == "ORIGINAL_MUTABLE_SNAPSHOT_UNAVAILABLE"
                            for check in checks.checks[before:])):
                mutable_drift.add((record["table"], record["key"]["id"]))
        for observation in validated["eligibility_observations"]:
            row = checks.row(observation["record"])
            if row is not None:
                fields = {key: value for key, value in observation.items() if key != "record"}
                if all(row.get(key) == value for key, value in fields.items()):
                    checks.evidence("verified", "HISTORICAL_ELIGIBILITY_OBSERVATION_MATCHES", observation["record"])
                else:
                    checks.evidence("unverifiable_missing_coverage", "ORIGINAL_ELIGIBILITY_SNAPSHOT_UNAVAILABLE", observation["record"])
    for index, binding in enumerate(package["witness_bindings"]):
        record = {"table": EXECUTION_TABLE, "key": {"id": binding["receipt_id"]}}
        row = checks.row(record)
        if row is None:
            continue
        try:
            witness = receipt_from_row(row)
            if (_digest(row["receipt_json"].encode("utf-8")) != binding["receipt_sha256"]
                    or witness["run"]["run_id"] != binding["run_id"]
                    or witness["retention"]["retained_at"] != finding["selection_basis"]["selected"][index]["retained_at"]):
                raise ValueError("Historical witness binding differs")
            witnesses.append(witness)
            checks.evidence("verified", "EXACT_P3_WITNESS_BINDING_MATCHES", record)
        except (ValueError, KeyError, TypeError, UnicodeError, OverflowError):
            checks.evidence("invalid_evidence", "P3_WITNESS_INTEGRITY_INVALID", record)
            continue
        if supported:
            try:
                _check_frame_and_prompt(witness)
                checks.evidence("verified", "HISTORICAL_FRAME_AND_TEMPLATE_SUPPORTED", record)
            except _EvidenceProblem as problem:
                checks.evidence("unverifiable_unsupported_rule" if problem.state == "unsupported"
                                else "invalid_evidence", problem.code.upper(), record)
        _required_closure(checks, witness, finding["validated_evidence"][index], mutable_drift)
        _lineage_binding(checks, witness, finding["evidence_refs"][index])
        # Source hash is immutable even though the full source row contains
        # mutable scope/exclusion metadata. Its contradiction is never drift.
        for ref in execution_references(witness):
            if ref["table"] == "source_documents":
                source = checks.row(ref)
                if source is not None and "file_hash" in source and source["file_hash"] != witness["run"]["scope_receipt"]["primary"]["source_document_hash"]:
                    checks.evidence("invalid_evidence", "P3_SOURCE_HASH_BINDING_MISMATCH", ref)
        # A changed highlight association is unavailable old mutable snapshot
        # material, not an immutable P3 contradiction. All captured immutable
        # dependencies have still been checked individually above.
        if not any(table == "reader_highlights" for table, _ in mutable_drift):
            try:
                validate_execution_references(checks.conn, witness)
                checks.evidence("verified", "P3_IMMUTABLE_REFERENCE_BINDINGS_MATCH", record)
            except sqlite3.Error:
                checks.evidence("unverifiable_missing_coverage", "P3_REFERENCE_SCHEMA_UNAVAILABLE", record)
            except (ValueError, KeyError, TypeError):
                # Preserve precise row absence/schema classifications already
                # made, rather than calling absence an immutable contradiction.
                direct = execution_references(witness)
                unavailable = any(check["state"] in {"unverifiable_missing_evidence", "unverifiable_missing_coverage"}
                                  and check["record"] in direct for check in checks.checks)
                if not unavailable:
                    checks.evidence("invalid_evidence", "P3_IMMUTABLE_REFERENCE_BINDING_INVALID", record)
    if supported and receipt["achievement_id"] == "second_opinion" and len(witnesses) == 2:
        families = _families(checks, receipt, witnesses)
        if all(families):
            expected = finding["perspective_distinctness_basis"]
            runs = [witness["run"] for witness in witnesses]
            if (not _same_inquiry(*witnesses) or not _different_methodology(*witnesses)
                    or families[0] == families[1]
                    or finding["question_comparison_basis"]["sha256"] != runs[0]["question_sha256"]
                    or finding["scope_comparison_basis"]["sha256"] != runs[0]["scope_sha256"]
                    or expected["revision_ids"] != [run["perspective"]["id"] for run in runs]
                    or expected["definition_fingerprints"] != [run["perspective"]["definition_fingerprint"] for run in runs]
                    or expected["methodology_sha256"] != [_digest(_methodology(witness)) for witness in witnesses]):
                checks.evidence("invalid_evidence", "SECOND_OPINION_SELECTED_PREDICATE_MISMATCH")
            else:
                checks.evidence("verified", "SECOND_OPINION_SELECTED_PREDICATE_MATCHES")


def _replay(checks: _Checks, receipt: dict, supported: bool) -> None:
    if not supported:
        checks.add("historical_snapshot_replay", "unsupported", "HISTORICAL_IMPLEMENTATION_UNAVAILABLE")
        return
    try:
        evidence = read_perspective_achievement_evidence(checks.conn)
        current = evaluate_perspective_achievements(evidence)
        basis = achievement_evidence_basis(evidence)
    except Exception:
        checks.add("historical_snapshot_replay", "unsupported", "COHERENT_REPLAY_SNAPSHOT_UNAVAILABLE")
        return
    package = receipt["evidence_package"]
    if basis != package["adapter_basis"]:
        checks.add("historical_snapshot_replay", "unsupported", "ORIGINAL_WHOLE_CATEGORY_SNAPSHOT_UNAVAILABLE")
        return
    finding = next(item for item in current["achievements"] if item["achievement_id"] == receipt["achievement_id"])
    original = package["assessment"]
    reproduced = {
        "result_schema": current["schema"],
        **{key: current[key] for key in ("evaluator_version", "rules_sha256", "evidence_sha256", "coverage", "diagnostics", "limitations")},
        "finding": finding,
    }
    if reproduced != original:
        checks.report["historical_snapshot_replay"] = "invalid"
        checks.add("historical_snapshot_replay", "invalid", "ORIGINAL_ASSESSMENT_NOT_REPRODUCED")
        return
    if checks.finish()["evidence_verification"] != "verified":
        checks.add("historical_snapshot_replay", "unsupported", "REQUIRED_HISTORICAL_EVIDENCE_NOT_VERIFIED")
        return
    checks.report["historical_snapshot_replay"] = "verified"
    checks.add("historical_snapshot_replay", "verified", "ORIGINAL_SNAPSHOT_AND_SELECTION_REPRODUCED")


def _verify_snapshot(conn: sqlite3.Connection, award_id: str) -> dict:
    checks = _Checks(conn, award_id)
    record = {"table": _AWARD_TABLE, "key": {"id": award_id}}
    row = checks.row(record)
    if row is None or not _REQUIRED[_AWARD_TABLE] <= checks.columns.get(_AWARD_TABLE, set()):
        checks.add("receipt_integrity", "unsupported", "AWARD_RECEIPT_UNAVAILABLE", record)
        return checks.finish()
    try:
        receipt = award_from_row(row)
    except UnsupportedAward:
        checks.add("receipt_integrity", "unsupported", "AWARD_RECEIPT_UNSUPPORTED", record)
        checks.evidence("unverifiable_unsupported_rule", "AWARD_RECEIPT_PROFILE_UNSUPPORTED", record)
        return checks.finish()
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        checks.report["receipt_integrity"] = "invalid"
        checks.add("receipt_integrity", "invalid", "AWARD_RECEIPT_INVALID", record)
        checks.evidence("invalid_evidence", "HISTORICAL_EARNED_CLAIM_UNTRUSTED", record)
        return checks.finish()
    checks.report["receipt_integrity"] = "valid"
    checks.add("receipt_integrity", "valid", "CANONICAL_AWARD_AND_PACKAGE_BINDINGS_MATCH", record)
    if (datetime.fromisoformat(receipt["awarded_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
            < datetime.fromisoformat(receipt["earned_at"].replace("Z", "+00:00")).astimezone(timezone.utc)):
        checks.add("receipt_integrity", "valid", "AWARD_TIME_PRECEDES_EARNED_TIME", record)
    try:
        supported = _supported(receipt)
    except Exception:
        supported = False
    if not supported:
        checks.evidence("unverifiable_unsupported_rule", "HISTORICAL_RULE_EVALUATOR_PROFILE_UNAVAILABLE")
    try:
        _check_witnesses(checks, receipt, supported)
    except Exception:
        checks.evidence("unverifiable_missing_coverage", "REMAINING_WITNESS_CHECKS_UNAVAILABLE")
    try:
        _replay(checks, receipt, supported)
    except Exception:
        checks.add("historical_snapshot_replay", "unsupported", "REMAINING_REPLAY_CHECKS_UNAVAILABLE")
    return checks.finish()


def verify_achievement_award(conn: sqlite3.Connection, award_id: str) -> dict:
    """Check one award in a coherent caller-preserving read snapshot.

    No initialization, providers, current Scope resolution, issuance, database
    writes or connection setting changes occur. Caller transactions stay open.
    """
    own_transaction = not conn.in_transaction
    try:
        if own_transaction:
            conn.execute("BEGIN")
        return _verify_snapshot(conn, award_id)
    except (sqlite3.Error, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        # Do not expose raw exceptions, which may carry private evidence data.
        return {
            "schema": SCHEMA, "award_id": award_id, "receipt_integrity": "unsupported",
            "evidence_verification": "unverifiable_missing_coverage", "historical_snapshot_replay": "unsupported",
            "checks": [{"dimension": "evidence_verification", "state": "unverifiable_missing_coverage",
                        "reason_code": "COHERENT_VERIFICATION_SNAPSHOT_UNAVAILABLE", "record": None}],
            "limitations": ["Required coherent verification snapshot or implementation support could not be obtained."],
        }
    finally:
        if own_transaction and conn.in_transaction:
            conn.rollback()
