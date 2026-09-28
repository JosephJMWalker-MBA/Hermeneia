#!/usr/bin/env python3
"""Serve the unchanged product UI over an already captured private snapshot.

Evidence harness only. Never pass a live workspace here. HTTP mutations and
unrelated endpoints are blocked; explicit Reader navigation normally writes
reading progress and therefore cannot be claimed as ordinarily read-only.
Stop with Ctrl-C to write browser-integrity.json beside the private copy.
"""
import argparse
from pathlib import Path
import json
import re
import shutil
import sqlite3
from contextlib import closing
from urllib.parse import unquote, urlparse

from flask import request, jsonify
from werkzeug.serving import make_server

from validate_readonly import files, connect_ro, logical_hash, durable_files_equal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captured_db", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args()
    source = args.captured_db.resolve(strict=True)
    output = args.output_directory.resolve()
    if output.exists() or Path("/private/tmp") not in output.parents:
        raise ValueError("Use a fresh directory under /private/tmp")
    if Path(str(source) + "-wal").exists() and Path(str(source) + "-wal").stat().st_size:
        raise ValueError("Use a completed snapshot without pending WAL bytes")
    output.mkdir(mode=0o700)
    db = output / "private-browser-copy.db"
    from hermeneia.web.app import create_app
    app = create_app(db_path=db)  # Absent path prevents startup migrations.
    shutil.copyfile(source, db)
    with closing(connect_ro(db)) as conn:
        before_logical = logical_hash(conn)
    before = files(db)
    real_connect = sqlite3.connect
    def guarded_connect(database, *unused_args, **unused_kwargs):
        raw = str(database)
        path = Path(unquote(urlparse(raw).path)) if raw.startswith("file:") else Path(raw)
        if path.resolve() != db:
            raise RuntimeError("Browser attempted to open another database")
        conn = real_connect(db.as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn
    sqlite3.connect = guarded_connect
    requests = []
    allowed = re.compile(r"^/(?:|static/.*|api/(?:health|setup/state|project/summary|study-lineage(?:/export)?|evidence-board|"
                         r"lineage/[^/]+/[^/]+|reader/documents(?:/[^/]+/(?:pages|highlights))?|workspace/identity))$")
    @app.before_request
    def restrict_requests():
        permitted = request.method == "GET" and bool(allowed.fullmatch(request.path))
        requests.append({"method": request.method, "path": request.path, "allowed": permitted})
        if not permitted:
            return jsonify(error="Blocked by evidence-only read-only browser harness"), 403
    server = make_server("127.0.0.1", args.port, app)
    print(f"Read-only evidence browser: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        with closing(connect_ro(db)) as conn:
            after_logical = logical_hash(conn)
        after = files(db)
        report = {"guard": "private snapshot; allowlisted GETs; mode=ro and query_only",
                  "files_before": before, "files_after": after,
                  "logical_sha256_before": before_logical, "logical_sha256_after": after_logical,
                  "unchanged": durable_files_equal(before, after) and before_logical == after_logical,
                  "requests": requests}
        (output / "browser-integrity.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
