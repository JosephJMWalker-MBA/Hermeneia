"""The one resolver for the workspace database a CLI command opens.

An explicit target resolves exactly or fails loudly; it is never replaced by
the working directory's ``build/hermeneia.db``. A directory (an authoritative
``.herm`` bundle or a workspace folder) means its own ``hermeneia.db``
(docs/15_Storage.md, Authoritative Bundle Shape). Only an absent target uses
the documented default.
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_DB = "build/hermeneia.db"


class DatabaseTargetError(SystemExit):
    """An explicit CLI database target that cannot be resolved exactly."""


def resolve_db_target(bundle_or_db: str | Path | None, default: str = DEFAULT_DB) -> Path:
    target = _resolve_db_target(bundle_or_db, default)
    require_cli_supported_schema(target)
    return target


def require_cli_supported_schema(db_path: str | Path) -> None:
    """ADR-0048: refuse a newer workspace before any CLI command opens it for writing.

    A directory is probed through its own ``hermeneia.db``, the database a command will resolve it to.
    """
    from ..storage.schema_guard import SchemaMarkerError, require_supported_schema
    from ..storage.sqlite import SCHEMA_VERSION
    if Path(db_path).is_dir():
        db_path = Path(db_path) / "hermeneia.db"
    try:
        require_supported_schema(db_path, SCHEMA_VERSION)
    except SchemaMarkerError as exc:
        raise DatabaseTargetError(str(exc)) from exc


def _resolve_db_target(bundle_or_db: str | Path | None, default: str) -> Path:
    if bundle_or_db is None:
        return Path(default)
    target = Path(bundle_or_db)
    if target.is_dir():
        inner = target / "hermeneia.db"
        if inner.is_file():
            return inner
        raise DatabaseTargetError(f"No hermeneia.db inside {target}; refusing to guess another workspace.")
    if target.is_file():
        return target
    raise DatabaseTargetError(f"Database not found: {target}")
