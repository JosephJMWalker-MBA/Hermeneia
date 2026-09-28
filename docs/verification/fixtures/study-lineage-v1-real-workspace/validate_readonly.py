#!/usr/bin/env python3
"""Manual, evidence-only validation of an existing study database.

Run from the repository with PYTHONPATH=. Supply the source database and a
nonexistent directory beneath the system temporary directory or /private/tmp.
The private output contains a database snapshot: never commit that snapshot.
Only result.json is sanitized for review (IDs, counts, times and hashes).
No migration, source repair, or missing historical association is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
from urllib.parse import quote, unquote, urlparse


class ProjectionDefect(AssertionError):
    """A deterministic disagreement; preserve evidence and stop before repair."""


class ValidationProbeError(RuntimeError):
    """An incomplete probe is not evidence of a projection defect."""


def require(condition, message):
    if not condition:
        raise ProjectionDefect(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def files(db):
    result = {}
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(db) + suffix)
        data = path.read_bytes() if path.exists() else None
        result[suffix or "database"] = {
            "exists": data is not None, "size": len(data) if data is not None else None,
            "sha256": sha(data) if data is not None else None,
        }
    return result


def durable_files_equal(before, after):
    # Shared-memory locks/read marks are SQLite coordination, not study records.
    # Preserve their exact observations separately rather than hiding changes.
    return all(before[key] == after[key] for key in ("database", "-wal"))


def connect_ro(path):
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def logical_hash(conn):
    return sha("\n".join(conn.iterdump()).encode("utf-8"))


def ident(value):
    return '"' + value.replace('"', '""') + '"'


def stored_row(conn, record):
    key = record["key"]
    require(bool(key), "Projected identity is empty")
    where = " AND ".join(ident(field) + " IS ?" for field in key)
    rows = conn.execute("SELECT * FROM " + ident(record["table"]) + " WHERE " + where,
                        tuple(key.values())).fetchall()
    require(len(rows) == 1, "Projected typed identity does not resolve uniquely")
    return dict(rows[0])


def check_projection(client, snapshot, report):
    responses = [client.get(route) for route in (
        "/api/study-lineage", "/api/study-lineage/export", "/api/study-lineage/export")]
    report["api_statuses"] = [response.status_code for response in responses]
    if not all(response.status_code == 200 for response in responses):
        raise ValidationProbeError("Lineage API did not return 200; inspect HTTP statuses")
    require(len({response.data for response in responses}) == 1, "Repeated projection/export bytes differ")
    payload = responses[0].get_json()
    require(payload["schema"] == "hermeneia.study-lineage/v1", "Unexpected projection schema")
    report["export_sha256"] = sha(responses[0].data)
    report["workspace_id"] = payload["workspace"]["id"]
    report["coverage"] = payload["coverage"]
    report["projected_counts"] = dict(sorted(Counter(item["record"]["table"] for item in payload["items"]).items()))
    report["authorship_counts"] = dict(sorted(Counter(item["authorship"] for item in payload["items"]).items()))
    report["chronology_counts"] = dict(sorted(Counter(item["timestamp"]["status"] for item in payload["items"]).items()))
    report["reader_samples"], report["observation_context_samples"] = [], []
    chronology = [(item["timestamp"]["status"] != "ordered", item["timestamp"]["sort_key"] or "")
                  for item in payload["items"]]
    require(chronology == sorted(chronology), "Projection chronology is out of recorded-time order")
    with closing(connect_ro(snapshot)) as conn:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        report["stored_counts"] = {table: conn.execute("SELECT COUNT(*) FROM " + ident(table)).fetchone()[0] for table in tables}
        for item in payload["items"]:
            row = stored_row(conn, item["record"])
            require(row == item["record_data"], "Projected raw row differs from its durable typed record")
            timestamp = item["timestamp"]
            require(timestamp["value"] == row.get(timestamp["field"]), "Projected time differs from its recorded field")
            if item["record"]["table"] == "reader_highlights":
                require(item["authorship"] == "unknown", "Reader authorship was inferred without attribution")
                require(item["event"] == "current_snapshot" and timestamp["field"] == "updated_at",
                        "Current Reader state is presented as a historical creation event")
            if timestamp["status"] == "ordered":
                parsed = datetime.fromisoformat(timestamp["value"].replace("Z", "+00:00"))
                require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "Naive timestamp is presented as ordered")
                require(timestamp["sort_key"] == parsed.astimezone(timezone.utc).isoformat(timespec="microseconds"), "Timestamp sort key denotes another instant")
            for provenance in item["provenance"]["records"]:
                require(stored_row(conn, provenance) == provenance["record_data"], "Projected provenance differs from durable record")
        marks = [item for item in payload["items"] if item["record"]["table"] == "reader_highlights"
                 and item["record_data"].get("status") != "dismissed" and item["contexts"]]
        for item in marks[:3]:
            row = item["record_data"]
            context = next((value for value in item["contexts"] if value["kind"] == "reader"), None)
            require(context is not None, "Reader mark has no Reader context")
            require((context["document_id"], context["page"], context["highlight_id"]) ==
                    (row["source_document_id"], row["page"], row["id"]), "Reader mark context changes identity or source association")
            response = client.get("/api/reader/documents/" + quote(context["document_id"], safe="") + "/pages")
            if response.status_code != 200:
                report["context_http_status"] = response.status_code
                raise ValidationProbeError("Recorded Reader context did not return 200")
            pages = response.get_json()
            require(pages["document"]["id"] == row["source_document_id"], "Reader context returns another document")
            require(any(page["page"] == row["page"] and any(mark["id"] == row["id"] for mark in page["highlights"])
                        for page in pages["pages"]), "Reader context omits the exact mark at its recorded page")
            report["reader_samples"].append({"id": row["id"], "document_id": row["source_document_id"],
                                             "page": row["page"], "observation_id": row.get("observation_id"),
                                             "timestamp": item["timestamp"], "status": "verified"})
        observations = [item for item in payload["items"] if item["record"]["table"] == "observations"]
        for item in observations[:3]:
            context = item["contexts"][0]
            response = client.get("/api/lineage/" + quote(context["epistemic_class"], safe="") + "/" + quote(context["object_id"], safe=""))
            if response.status_code != 200:
                report["context_http_status"] = response.status_code
                raise ValidationProbeError("Observation object context did not return 200")
            nodes = {(node["class"], node["id"]) for node in response.get_json()["nodes"]}
            row = item["record_data"]
            require({("Observation", row["id"]), ("SourceDocument", row["source_document_id"]),
                     ("SourceExtraction", row["source_extraction_id"])} <= nodes,
                    "Observation context omits its exact source chain")
            report["observation_context_samples"].append({"id": row["id"], "document_id": row["source_document_id"],
                                                          "extraction_id": row["source_extraction_id"], "status": "verified"})
        report["reader_sampling"] = "verified" if marks else "not_exercised_no_eligible_marks"
        report["observation_sampling"] = "verified" if observations else "not_exercised_no_observations"
        docs = [dict(row) for row in conn.execute("SELECT * FROM source_documents")] if "source_documents" in tables else []
        excluded = {row["id"] for row in docs if row.get("excluded_from_analysis") not in (0, None)}
        report["excluded_document_count"] = len(excluded)
        # A zero count is lack of a real excluded-evidence case, never a passing test.
        report["excluded_evidence_validation"] = "requires_manual_reference_closure_audit" if excluded else "not_exercised_no_excluded_documents"
        report["chain_validation"] = "requires_manual_durable_reference_trace_no_association_inferred"
    report["raw_rows_and_recorded_times"] = "verified"


def run(source, output):
    source = source.expanduser().resolve(strict=True)
    output = output.expanduser().resolve()
    roots = {Path(tempfile.gettempdir()).resolve(), Path("/private/tmp").resolve(), Path("/tmp").resolve()}
    if output.exists() or not any(root in output.parents for root in roots):
        raise ValueError("Output must be a nonexistent private temporary directory")
    output.mkdir(mode=0o700, parents=False)
    snapshot = output / "private-study-snapshot.db"
    report = {"schema": "hermeneia.study-lineage.real-workspace-validation/v1",
              "scope": "existing records; private snapshot; no migrations; API reads only",
              "status": "incomplete"}
    # The absent path is deliberate: create_app's existing migration path must
    # not execute. Install the exact source snapshot only after app construction.
    from hermeneia.web.app import create_app
    app = create_app(db_path=snapshot)
    app.testing = True
    before = files(source)
    real_connect = sqlite3.connect
    try:
        with closing(connect_ro(source)) as conn:
            conn.execute("BEGIN")
            report["source_logical_sha256_before"] = logical_hash(conn)
            with closing(real_connect(snapshot)) as destination:
                conn.backup(destination)
        with closing(connect_ro(snapshot)) as conn:
            snapshot_logical = logical_hash(conn)
        before_snapshot = files(snapshot)
        report["snapshot_files_before"] = before_snapshot
        if snapshot_logical != report["source_logical_sha256_before"]:
            raise ValidationProbeError("Captured snapshot differs from the source read transaction")

        def guarded_connect(database, *args, **kwargs):
            raw = str(database)
            path = Path(unquote(urlparse(raw).path)) if raw.startswith("file:") else Path(raw)
            if path.resolve() != snapshot:
                raise ValidationProbeError("Endpoint attempted a connection outside the private snapshot")
            conn = real_connect(snapshot.as_uri() + "?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            return conn

        with patch.object(sqlite3, "connect", guarded_connect):
            check_projection(app.test_client(), snapshot, report)
        with closing(connect_ro(snapshot)) as conn:
            report["snapshot_logical_sha256_after"] = logical_hash(conn)
        report["snapshot_files_after"] = files(snapshot)
        require(durable_files_equal(before_snapshot, report["snapshot_files_after"]) and report["snapshot_logical_sha256_after"] == snapshot_logical,
                "Validation altered the captured database or its durable records")
        report["snapshot_unchanged"] = True
        report["status"] = "completed_bounded_checks"
    except Exception as exc:
        report["status"] = "stopped_for_review"
        report["error_type"] = type(exc).__name__
        report["failure_class"] = "projection_or_context_disagreement" if isinstance(exc, ProjectionDefect) else "probe_incomplete_not_a_proven_projection_defect"
        # Only our fixed assertion messages are safe to include; arbitrary SQL
        # or HTTP exceptions may contain workspace text or local filesystem paths.
        if isinstance(exc, (ProjectionDefect, ValidationProbeError)):
            report["failure"] = str(exc)
    finally:
        report["source_files_before"] = before
        try:
            with closing(connect_ro(source)) as conn:
                conn.execute("BEGIN")
                report["source_logical_sha256_after"] = logical_hash(conn)
            report["source_files_after"] = after = files(source)
            report["source_integrity_checks"] = {
                "database_bytes_equal": before["database"] == after["database"],
                "wal_presence_and_bytes_equal": before["-wal"] == after["-wal"],
                "shm_presence_and_bytes_equal": before["-shm"] == after["-shm"],
                "logical_records_equal": report.get("source_logical_sha256_before") == report["source_logical_sha256_after"],
            }
            report["source_unchanged"] = (durable_files_equal(before, after) and
                report["source_integrity_checks"]["logical_records_equal"])
            if not report["source_unchanged"]:
                report["status"] = "stopped_for_review"
                report["source_integrity_finding"] = "File presence/bytes or logical records changed; this alone does not establish study mutation"
        except Exception as exc:
            report["status"] = "stopped_for_review"
            report["source_unchanged"] = None
            report["source_integrity_probe_error"] = type(exc).__name__
        (output / "result.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["status"] == "completed_bounded_checks" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_db", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    raise SystemExit(run(args.source_db, args.output_directory))
