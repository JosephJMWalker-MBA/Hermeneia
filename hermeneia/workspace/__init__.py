"""Workspace Bundle — the exchange format (WBS v1.1, issues #70/#76).

The database is where Hermeneia works; the Workspace Bundle is where it
remembers. This package exports a deterministic, human-readable bundle from the
runtime SQLite database. It is read-only over the DB, performs no provider call,
and never writes canonical data. See docs/workspace-bundle-spec.md.
"""
from .export import (
    WBS_VERSION,
    build_bundle_files,
    build_workspace_zip,
    export_workspace_bundle,
)
from .restore import (
    RestoreError,
    find_bundle_root,
    preview_restore,
    read_bundle,
    restore_workspace,
    safe_extract_zip,
)
from .identity import (
    ensure_workspace_identity,
    read_workspace_id,
    read_workspace_identity,
    set_workspace_name,
)
from .lifecycle import (
    DEFAULT_LEGACY_DB,
    DEFAULT_WORKSPACE_ROOT,
    RESERVED_WORKSPACE_SELECTORS,
    WORKSPACE_DB_NAME,
    WorkspaceAlreadyExistsError,
    WorkspaceLifecycleError,
    WorkspaceNameReservedError,
    WorkspaceRecord,
    create_workspace,
    inspect_workspace,
    list_workspaces,
    resolve_serve_db,
    resolve_workspace_db,
    slugify_workspace_name,
)

__all__ = [
    "WBS_VERSION",
    "build_bundle_files",
    "build_workspace_zip",
    "export_workspace_bundle",
    "RestoreError",
    "find_bundle_root",
    "preview_restore",
    "read_bundle",
    "restore_workspace",
    "ensure_workspace_identity",
    "read_workspace_id",
    "read_workspace_identity",
    "set_workspace_name",
    "DEFAULT_LEGACY_DB",
    "DEFAULT_WORKSPACE_ROOT",
    "RESERVED_WORKSPACE_SELECTORS",
    "WORKSPACE_DB_NAME",
    "WorkspaceAlreadyExistsError",
    "WorkspaceLifecycleError",
    "WorkspaceNameReservedError",
    "WorkspaceRecord",
    "create_workspace",
    "inspect_workspace",
    "list_workspaces",
    "resolve_serve_db",
    "resolve_workspace_db",
    "slugify_workspace_name",
]
