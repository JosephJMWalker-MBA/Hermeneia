"""Workspace Bundle — the exchange format (WBS v1, issues #70/#76).

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
    preview_restore,
    read_bundle,
    restore_workspace,
)
from .identity import (
    ensure_workspace_identity,
    read_workspace_id,
    read_workspace_identity,
    set_workspace_name,
)

__all__ = [
    "WBS_VERSION",
    "build_bundle_files",
    "build_workspace_zip",
    "export_workspace_bundle",
    "RestoreError",
    "preview_restore",
    "read_bundle",
    "restore_workspace",
    "ensure_workspace_identity",
    "read_workspace_id",
    "read_workspace_identity",
    "set_workspace_name",
]
