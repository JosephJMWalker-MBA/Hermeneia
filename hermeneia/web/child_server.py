"""Internal one-workspace child runtime for the supervised web server."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from werkzeug.serving import make_server

from .app import create_app


READY_EVENT = "hermeneia_child_ready"


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermeneia supervised child runtime")
    parser.add_argument("--db", required=True, help="Database path for this child runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    app = create_app(db_path=Path(args.db))
    server = make_server(args.host, args.port, app, threaded=True)
    host, port = server.socket.getsockname()[:2]
    print(
        json.dumps({"event": READY_EVENT, "host": host, "port": int(port)}),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            json.dumps({"event": "hermeneia_child_failed", "error": str(exc)}),
            flush=True,
        )
        raise
