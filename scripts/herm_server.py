#!/usr/bin/env python3
"""
Hermeneia web server.

Usage:
    python scripts/herm_server.py [--db build/hermeneia.db] [--workspace NAME] [--port 5173]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hermeneia.workspace import WorkspaceLifecycleError, resolve_serve_db
from hermeneia.web.app import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hermeneia web server")
    parser.add_argument("--db", default=None)
    parser.add_argument(
        "--workspace",
        default=None,
        help="Named workspace to launch (slug, name, id, or Gatsby)",
    )
    parser.add_argument("--port", type=int, default=5173)
    args = parser.parse_args()

    try:
        db_path = resolve_serve_db(db_arg=args.db, workspace_selector=args.workspace)
    except WorkspaceLifecycleError as exc:
        parser.error(str(exc))

    app = create_app(db_path=db_path)
    print(f"  Hermeneia → http://localhost:{args.port}")
    print(f"  Database  → {db_path}")
    app.run(port=args.port, debug=False)
