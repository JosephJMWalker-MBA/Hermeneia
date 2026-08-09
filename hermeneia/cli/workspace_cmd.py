"""CLI commands for runtime workspace lifecycle."""
from __future__ import annotations

from pathlib import Path

from hermeneia.workspace import (
    WorkspaceLifecycleError,
    WorkspaceRecord,
    create_workspace,
    inspect_workspace,
    list_workspaces,
    resolve_serve_db,
)


def cmd_workspace_list() -> None:
    """Print known legacy and managed workspaces."""
    records = list_workspaces()
    if not records:
        print("No workspaces found.")
        print("Legacy default is build/hermeneia.db; create it with herm serve or setup.")
        return
    print("KIND     SLUG                 NAME                 DOCS  DATABASE")
    for record in records:
        print(
            f"{record.kind:<8} "
            f"{record.slug:<20} "
            f"{record.name[:20]:<20} "
            f"{record.document_count:<5} "
            f"{record.db_path}"
        )


def cmd_workspace_create(name: str) -> None:
    """Create a named managed workspace."""
    try:
        record = create_workspace(name)
    except WorkspaceLifecycleError as exc:
        raise SystemExit(str(exc)) from exc
    print("Created workspace")
    _print_record(record)
    print(f"Serve: herm serve --workspace {record.slug}")


def cmd_workspace_inspect(selector: str) -> None:
    """Print one resolved workspace."""
    try:
        record = inspect_workspace(selector)
    except WorkspaceLifecycleError as exc:
        raise SystemExit(str(exc)) from exc
    _print_record(record)


def resolve_cli_serve_db(
    *,
    global_db: str | None,
    command_db: str | None,
    workspace_selector: str | None,
) -> Path:
    """Resolve the DB for ``herm serve`` command-line arguments."""
    if global_db is not None and command_db is not None:
        raise WorkspaceLifecycleError("provide --db either before or after serve, not both")
    return resolve_serve_db(
        db_arg=command_db if command_db is not None else global_db,
        workspace_selector=workspace_selector,
    )


def _print_record(record: WorkspaceRecord) -> None:
    workspace_id = record.workspace_id or "(not persisted)"
    print(f"Name: {record.name}")
    print(f"Slug: {record.slug}")
    print(f"Kind: {record.kind}")
    print(f"Workspace ID: {workspace_id}")
    print(f"Documents: {record.document_count}")
    print(f"Root: {record.root_path}")
    print(f"Database: {record.db_path}")
