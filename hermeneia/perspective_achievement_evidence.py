"""Read-only canonical evidence for the two frozen Perspective v1 rules.

This adapter never initializes storage, resolves current Scope, invokes a
provider, or records an award. Immutable JSON strings retain exact captured
facts while keeping the pure evaluator independent of SQLite and display text.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import inspect
import json
import sqlite3
from types import MappingProxyType
from typing import Any

from .perspective_execution_receipts import (
    CAPABILITY, SCHEMA, TABLE, canonical_bytes, execution_references,
    receipt_from_row, validate_execution_references,
)
from .perspective_identity import FRAME_V2_SCHEME, validate_frame_v2_row_identity
from .perspective_runs import PerspectiveDefinition, build_perspective_prompt
from .study_lineage import _SUPERSESSION_TABLES, project_study_lineage


# Frozen packaged revisions at the rule-design baseline 33931f4. These are not
# inferred from whichever definitions happen to be installed at evaluation time.
BUILTIN_V1_FINGERPRINTS = MappingProxyType({
    ("close-reader", "1"): "sha256:b10fb209b7d596a02c27190fd0cc36ef96c9cac17bcba9ad4a9d26d0b713e590",
    ("contextual-reader", "1"): "sha256:90267217c613d2381f826fc78fa9828334a8540123c5cb39d9ce8bd6a19f6fc1",
    ("skeptical-reader", "1"): "sha256:a84815cde927669454974c2513e27e912aeb9655e7d18ef0d6de26b4de157730",
})
PROMPT_VERSION = "perspective-run/v1"
TEMPLATE_IMPLEMENTATION_SHA256 = "sha256:26d8533f2d4e9c0235fbfc89f058484b22346b9c08b4139498ae8f4b22432e2e"
_EDGE_KEY = ("old_id", "new_id", "reason", "ratified_at")
_FRAME_COLUMNS = {
    "id", "name", "identity_scheme", "definition_fingerprint", "purpose",
    "questions_json", "challenges_json", "limitations_json", "declared_by",
    "declared_date",
}
_NO_HISTORY_CLAIM = (
    "Extant retained-receipt category only; no complete historical activity claim."
)


@dataclass(frozen=True, slots=True)
class RetainedExecutionEvidence:
    receipt_json: str
    lineage_ref_json: str
    family_key: tuple[str, str] | None
    family_state: str
    family_evidence_json: str
    family_reason_code: str | None = None
    dependency_evidence_json: str = "[]"
    eligibility_json: str = "[]"

    @property
    def receipt(self) -> dict:
        return json.loads(self.receipt_json)

    @property
    def lineage_ref(self) -> dict:
        return json.loads(self.lineage_ref_json)

    @property
    def family_evidence(self) -> dict:
        return json.loads(self.family_evidence_json)

    @property
    def dependency_evidence(self) -> list[dict]:
        return json.loads(self.dependency_evidence_json)

    @property
    def eligibility(self) -> list[dict]:
        return json.loads(self.eligibility_json)


@dataclass(frozen=True, slots=True)
class PerspectiveAchievementEvidence:
    executions: tuple[RetainedExecutionEvidence, ...]
    coverage_json: str
    diagnostics_json: str
    source_state: str

    @property
    def coverage(self) -> dict:
        return json.loads(self.coverage_json)

    @property
    def diagnostics(self) -> list[dict]:
        return json.loads(self.diagnostics_json)


class _EvidenceProblem(Exception):
    def __init__(self, state: str, code: str):
        self.state = state
        self.code = code
        super().__init__(code)


def _json(value: Any) -> str:
    return canonical_bytes(value).decode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _record(row: dict) -> dict | None:
    identifier = row.get("id")
    return {"table": TABLE, "key": {"id": identifier}} if isinstance(identifier, str) else None


def _diagnostic(state: str, stage: str, code: str, row: dict | None = None) -> dict:
    # Never copy payload text or arbitrary exception messages into diagnostics.
    return {"state": state, "stage": stage, "reason_code": code,
            "record": _record(row) if row is not None else None}


class _Snapshot:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.columns: dict[str, set[str]] = {}
        self.dependencies: dict[tuple[str, str], dict] = {}
        self.eligibility_observations: dict[tuple[str, str], dict] = {}

    def remember(self, table: str, row: dict, *, mutable: bool = False) -> None:
        record = {"table": table, "key": {"id": row["id"]}}
        self.dependencies[(table, row["id"])] = {
            "record": record, "record_sha256": _digest(row),
            "basis": "evaluation_snapshot" if mutable else "immutable_reference",
        }

    def require(self, table: str, columns: set[str]) -> None:
        if table not in self.tables:
            raise _EvidenceProblem("unsupported", "missing_reference_schema")
        if table not in self.columns:
            cursor = self.conn.execute(f'SELECT * FROM "{table}" LIMIT 0')
            self.columns[table] = {column[0] for column in cursor.description}
        if not columns <= self.columns[table]:
            raise _EvidenceProblem("unsupported", "missing_reference_columns")

    def row(self, table: str, identifier: str) -> dict:
        self.require(table, {"id"})
        cursor = self.conn.execute(f'SELECT * FROM "{table}" WHERE id=?', (identifier,))
        values = cursor.fetchall()
        if not values:
            raise _EvidenceProblem("invalid", "missing_reference_record")
        if len(values) != 1:
            raise _EvidenceProblem("invalid", "ambiguous_reference_record")
        return dict(zip((column[0] for column in cursor.description), values[0]))

    def source_eligibility(self, table: str, identifier: str, visiting: set[tuple[str, str]]) -> None:
        """Classify only the forensic closure used by P3/Lineage eligibility."""
        key = (table, identifier)
        if key in visiting:
            raise _EvidenceProblem("invalid", "cyclic_reference_closure")
        visiting.add(key)
        try:
            if table == "source_documents":
                self.require(table, {"id", "file_hash", "excluded_from_analysis"})
                row = self.row(table, identifier)
                exclusion = row["excluded_from_analysis"]
                if exclusion == 1:
                    raise _EvidenceProblem("excluded", "excluded_source_evidence")
                if exclusion != 0:
                    raise _EvidenceProblem("unsupported", "unknown_source_eligibility")
                self.remember(table, row, mutable=True)
                self.eligibility_observations[key] = {
                    "record": {"table": table, "key": {"id": identifier}},
                    "excluded_from_analysis": exclusion,
                    "file_hash": row["file_hash"],
                }
            elif table == "source_extractions":
                self.require(table, {"id", "document_id", "page", "source_locator"})
                row = self.row(table, identifier)
                self.remember(table, row)
                self.source_eligibility("source_documents", row["document_id"], visiting)
            elif table == "observations":
                self.require(table, {"id", "source_document_id", "source_extraction_id"})
                row = self.row(table, identifier)
                self.remember(table, row)
                self.source_eligibility("source_documents", row["source_document_id"], visiting)
                self.source_eligibility("source_extractions", row["source_extraction_id"], visiting)
                extraction = self.row("source_extractions", row["source_extraction_id"])
                if extraction["document_id"] != row["source_document_id"]:
                    raise _EvidenceProblem("invalid", "observation_source_binding_mismatch")
            elif table == "reader_highlights":
                self.require(table, {"id", "source_document_id"})
                row = self.row(table, identifier)
                self.remember(table, row, mutable=True)
                self.eligibility_observations[key] = {
                    "record": {"table": table, "key": {"id": identifier}},
                    "source_document_id": row["source_document_id"],
                    "observation_id": row.get("observation_id"),
                }
                self.source_eligibility("source_documents", row["source_document_id"], visiting)
                if row.get("observation_id"):
                    self.source_eligibility("observations", row["observation_id"], visiting)
        finally:
            visiting.remove(key)

    def execution_closure(self, receipt: dict) -> None:
        self.dependencies = {}
        self.eligibility_observations = {}
        references = execution_references(receipt)
        for ref in references:
            table, identifier = ref["table"], ref["key"]["id"]
            if table == "perspectives":
                self.require(table, _FRAME_COLUMNS)
                self.require("supersession_relations", set(_EDGE_KEY))
                self.remember(table, self.row(table, identifier))
            elif table == "source_documents":
                self.require(table, {"id", "file_hash", "excluded_from_analysis"})
                self.row(table, identifier)
            elif table == "source_extractions":
                self.require(table, {"id", "document_id", "page", "source_locator"})
                self.row(table, identifier)
            elif table == "reader_highlights":
                self.require(table, {"id", "source_document_id"})
                self.row(table, identifier)
        try:
            validate_execution_references(self.conn, receipt)
        except (ValueError, KeyError, TypeError) as exc:
            raise _EvidenceProblem("invalid", "execution_reference_binding_invalid") from exc
        for ref in references:
            if ref["table"] != "perspectives":
                self.source_eligibility(ref["table"], ref["key"]["id"], set())

    def family(self, perspective: dict) -> tuple[tuple[str, str], dict]:
        if perspective["origin"] == "built_in":
            return ("built_in", perspective["id"]), {
                "origin": "built_in", "id": perspective["id"],
                "version": perspective["version"],
                "definition_fingerprint": perspective["definition_fingerprint"],
            }
        self.require("perspectives", _FRAME_COLUMNS)
        self.require("supersession_relations", set(_EDGE_KEY))
        current = perspective["id"]
        seen: set[str] = set()
        nodes, edges = [], []
        while True:
            if current in seen:
                raise _EvidenceProblem("invalid", "cyclic_perspective_ancestry")
            seen.add(current)
            row = self.row("perspectives", current)
            if row.get("identity_scheme") != FRAME_V2_SCHEME:
                raise _EvidenceProblem("unsupported", "unsupported_perspective_ancestor")
            for table in _SUPERSESSION_TABLES:
                if table != "perspectives" and table in self.tables:
                    self.require(table, {"id"})
                    if self.conn.execute(f'SELECT 1 FROM "{table}" WHERE id=?', (current,)).fetchone():
                        raise _EvidenceProblem("invalid", "ambiguous_perspective_ancestry_type")
            cursor = self.conn.execute(
                "SELECT * FROM supersession_relations WHERE new_id=? ORDER BY old_id,reason,ratified_at", (current,)
            )
            incoming = []
            for values in cursor.fetchall():
                edge = dict(zip((column[0] for column in cursor.description), values))
                parent = self.conn.execute("SELECT 1 FROM perspectives WHERE id=?", (edge["old_id"],)).fetchone()
                if parent is None:
                    raise _EvidenceProblem("invalid", "missing_or_cross_type_perspective_predecessor")
                incoming.append(edge)
            if len(incoming) > 1:
                raise _EvidenceProblem("invalid", "ambiguous_perspective_predecessor")
            predecessor = incoming[0]["old_id"] if incoming else None
            try:
                validate_frame_v2_row_identity(row, predecessor_perspective_id=predecessor)
                nodes.append({"record": {"table": "perspectives", "key": {"id": current}}, "sha256": _digest(row)})
            except (ValueError, KeyError, TypeError) as exc:
                raise _EvidenceProblem("invalid", "perspective_ancestor_identity_invalid") from exc
            if predecessor is None:
                return ("canonical_saved", current), {
                    "root_id": current, "perspectives": nodes, "supersessions": edges,
                }
            edge = incoming[0]
            edges.append({"record": {"table": "supersession_relations", "key": {key: edge[key] for key in _EDGE_KEY}}, "sha256": _digest(edge)})
            current = predecessor


def _check_frame_and_prompt(receipt: dict) -> None:
    run, perspective = receipt["run"], receipt["run"]["perspective"]
    if perspective["origin"] == "built_in":
        fingerprint = BUILTIN_V1_FINGERPRINTS.get((perspective["id"], perspective["version"]))
        if fingerprint is None:
            raise _EvidenceProblem("unsupported", "unsupported_builtin_revision")
        if perspective["definition_fingerprint"] != fingerprint:
            raise _EvidenceProblem("invalid", "builtin_definition_binding_mismatch")
    semantic = perspective["definition"]
    definition = PerspectiveDefinition(
        id=perspective["id"], version=perspective["version"], label=semantic["label"],
        purpose=semantic["purpose"], questions=tuple(semantic["questions"]),
        challenges=tuple(semantic["challenges"]), limitations=tuple(semantic["limitations"]),
    )
    try:
        # Inspect the callable's own code, not an unwrapped decorator target.
        # A wrapper cannot inherit support merely by copying __wrapped__.
        template_digest = "sha256:" + hashlib.sha256(inspect.getsource(build_perspective_prompt.__code__).encode("utf-8")).hexdigest()
    except (OSError, TypeError, AttributeError) as exc:
        raise _EvidenceProblem("unsupported", "unsupported_template_implementation") from exc
    if template_digest != TEMPLATE_IMPLEMENTATION_SHA256:
        raise _EvidenceProblem("unsupported", "unsupported_template_implementation")
    expected = build_perspective_prompt(
        definition, question=run["question"], scope_receipt=run["scope_receipt"],
        scope_materialization=run["scope_receipt"]["materialization"],
    )
    if expected != run["prompt"]:
        raise _EvidenceProblem("invalid", "prompt_input_binding_mismatch")
    try:
        datetime.fromisoformat(receipt["retention"]["retained_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise _EvidenceProblem("invalid", "retention_utc_order_invalid") from exc


def _read_snapshot(conn: sqlite3.Connection) -> PerspectiveAchievementEvidence:
    snapshot = _Snapshot(conn)
    coverage = {"source": "local_sqlite_snapshot", "receipt_schema": SCHEMA,
                "capability": CAPABILITY, "historical_completeness": "unknown",
                "reason": _NO_HISTORY_CLAIM}
    try:
        snapshot.require(TABLE, {"id", "run_id", "receipt_json"})
    except _EvidenceProblem as problem:
        coverage.update(status="unsupported", extant_records=None, eligible_records=0)
        diagnostic = _diagnostic("unsupported", "source", "missing_receipt_category")
        return PerspectiveAchievementEvidence((), _json(coverage), _json([diagnostic]), "unsupported")
    cursor = conn.execute(f'SELECT * FROM "{TABLE}"')
    rows = [dict(zip((column[0] for column in cursor.description), row)) for row in cursor.fetchall()]
    identifiers = Counter(row["id"] for row in rows)
    run_ids = Counter(row["run_id"] for row in rows)
    lineage = project_study_lineage(conn)
    lineage_items = {
        item["record"]["key"]["id"]: item for item in lineage["items"]
        if item["record"].get("table") == TABLE
    }
    executions, diagnostics = [], []
    classified = {"eligible": 0, "excluded": 0, "unsupported": 0, "invalid": 0}
    family_counts = {"supported": 0, "unsupported": 0, "invalid": 0}
    for row in sorted(rows, key=lambda value: str(value.get("id"))):
        try:
            if identifiers[row["id"]] != 1 or run_ids[row["run_id"]] != 1:
                raise _EvidenceProblem("invalid", "duplicate_canonical_receipt_identity")
            try:
                receipt = receipt_from_row(row)
            except (ValueError, KeyError, TypeError, OverflowError, UnicodeError) as exc:
                state = "unsupported" if str(exc) in {
                    "Unsupported receipt schema", "Unsupported prompt version", "Unsupported Scope receipt",
                } else "invalid"
                raise _EvidenceProblem(state, "unsupported_receipt_contract" if state == "unsupported" else "receipt_integrity_invalid") from exc
            _check_frame_and_prompt(receipt)
            snapshot.execution_closure(receipt)
            item = lineage_items.get(receipt["id"])
            if item is None:
                raise _EvidenceProblem("unsupported", "unresolved_lineage_omission")
            if (item.get("event"), item.get("record_type"), item.get("authorship")) != ("recorded", "retained_perspective_execution", "model"):
                raise _EvidenceProblem("invalid", "lineage_identity_binding_invalid")
            family_key, family_state, family_reason = None, "supported", None
            family_evidence: dict = {}
            try:
                family_key, family_evidence = snapshot.family(receipt["run"]["perspective"])
            except _EvidenceProblem as problem:
                family_state, family_reason = problem.state, problem.code
                diagnostics.append(_diagnostic(problem.state, "family", problem.code, row))
            family_counts[family_state] += 1
            lineage_ref = {key: item[key] for key in ("record", "event", "record_type", "authorship", "provenance", "timestamp")}
            executions.append(RetainedExecutionEvidence(
                receipt_json=row["receipt_json"], lineage_ref_json=_json(lineage_ref),
                family_key=family_key, family_state=family_state,
                family_evidence_json=_json(family_evidence), family_reason_code=family_reason,
                dependency_evidence_json=_json([snapshot.dependencies[key] for key in sorted(snapshot.dependencies)]),
                eligibility_json=_json([snapshot.eligibility_observations[key] for key in sorted(snapshot.eligibility_observations)]),
            ))
            classified["eligible"] += 1
        except _EvidenceProblem as problem:
            classified[problem.state] += 1
            diagnostics.append(_diagnostic(problem.state, "execution", problem.code, row))
        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
            classified["invalid"] += 1
            diagnostics.append(_diagnostic("invalid", "execution", "evidence_adaptation_invalid", row))
    coverage.update(status="covered", extant_records=len(rows), eligible_records=len(executions),
                    classified_records=classified, family_states=family_counts)
    diagnostics.sort(key=_json)
    return PerspectiveAchievementEvidence(tuple(executions), _json(coverage), _json(diagnostics), "supported")


def read_perspective_achievement_evidence(conn: sqlite3.Connection) -> PerspectiveAchievementEvidence:
    """Gather one coherent snapshot without changing caller state or storage.

    Caller-owned transactions are retained, including pending work. Otherwise a
    read transaction is opened and rolled back after adaptation. The adapter
    performs no schema initialization and never changes connection pragmas.
    """
    own_transaction = not conn.in_transaction
    try:
        if own_transaction:
            conn.execute("BEGIN")
        return _read_snapshot(conn)
    except (sqlite3.Error, AttributeError, IndexError):
        coverage = {"source": "local_sqlite_snapshot", "status": "invalid",
                    "historical_completeness": "unknown", "reason": _NO_HISTORY_CLAIM,
                    "extant_records": None, "eligible_records": 0}
        return PerspectiveAchievementEvidence(
            (), _json(coverage), _json([_diagnostic("invalid", "source", "source_read_integrity_invalid")]), "invalid",
        )
    finally:
        if own_transaction and conn.in_transaction:
            conn.rollback()
