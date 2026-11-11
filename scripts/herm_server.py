#!/usr/bin/env python3
"""
Hermeneia web server.

Usage:
    python scripts/herm_server.py [--db build/hermeneia.db] [--workspace NAME] [--port 5173] [--supervised]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hermeneia.workspace import WorkspaceLifecycleError, resolve_serve_db
from hermeneia.workspace.startup import select_initial_workspace
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
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--supervised",
        action="store_true",
        help="Use the normal, workspace-switching runtime (default)",
    )
    modes.add_argument(
        "--direct",
        action="store_true",
        help="Advanced troubleshooting: pin one workspace; switching unavailable",
    )
    args = parser.parse_args()

    try:
        db_path = resolve_serve_db(db_arg=args.db, workspace_selector=args.workspace)
    except WorkspaceLifecycleError as exc:
        parser.error(str(exc))

    # Normal launches must be able to switch workspaces without a special flag.
    # Respect explicitly named workspaces and database paths.
    initial_selector = args.workspace
    if not args.db and not args.workspace and not args.direct:
        initial = select_initial_workspace()
        db_path = initial.db_path
        initial_selector = initial.slug

    if not args.direct:
        from hermeneia.web.supervisor import (
            WorkspaceRuntimeSupervisor,
            create_supervisor_app,
            runtime_target_from_serve_args,
        )

        supervisor = WorkspaceRuntimeSupervisor(
            initial_target=runtime_target_from_serve_args(
                db_path=db_path,
                workspace_selector=initial_selector,
            )
        )
        try:
            supervisor.start()
        except Exception as exc:
            parser.error(f"failed to start workspace supervisor: {exc}")
        app = create_supervisor_app(supervisor)
        print(f"  Hermeneia -> http://localhost:{args.port}")
        print(f"  Database  -> {db_path}")
        print("  Runtime   -> supervised workspace handoff")
        try:
            app.run(port=args.port, debug=False)
        finally:
            supervisor.shutdown()
        raise SystemExit(0)

    app = create_app(db_path=db_path)
    print(f"  Hermeneia → http://localhost:{args.port}")
    print(f"  Database  → {db_path}")
    app.run(port=args.port, debug=False)
