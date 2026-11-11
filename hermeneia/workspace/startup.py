"""Select a usable first runtime without demanding a terminal workspace selector.

The standard app always starts through the workspace-switching supervisor.
A pre-existing legacy database still opens as Gatsby. If no legacy database
exists, a managed workspace is selected without changing its data; a brand-new
installation receives a single ordinary, empty starter workspace.

Explicit --db and --workspace selections bypass this default policy.
"""
from __future__ import annotations

from pathlib import Path

from .lifecycle import DEFAULT_LEGACY_DB, WorkspaceRecord, create_workspace, list_workspaces


def select_initial_workspace() -> WorkspaceRecord:
    """Choose the default selectable workspace for a standard UI launch."""
    existing = list_workspaces()
    if existing:
        legacy = next((record for record in existing if record.kind == "legacy"), None)
        return legacy or existing[0]
    # The supervisor verifies its child via /api/health, which needs a real DB.
    # Create exactly one empty managed workspace rather than a fictitious
    # manuscript, import, or source-derived Gatsby database.
    return create_workspace("Starter Workspace")
