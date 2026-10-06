"""Frozen witness for #225: the herm CLI must open exactly the target it is given.

Run from inside another workspace (so ./build/hermeneia.db exists), every CLI
database resolver must resolve an explicit target exactly (a SQLite file of
any name, or the hermeneia.db inside a .herm bundle or workspace directory)
or fail loudly. None may substitute ./build/hermeneia.db.
Synthetic databases only.
"""
from __future__ import annotations

import importlib
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
RESOLVER_MODULES = ["inspector", "architect_cmd", "artist_cmd", "blueprinter", "comparer", "bootstrap_cmd",
                    "critic_cmd", "health", "interpreter", "profile_cmd", "theme_cmd"]


class WrongWorkspaceTarget(AssertionError):
    """Only the observed silent-substitution failure is expected here."""


def _workspace(path: Path, filename: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteStore(path).close()
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO source_documents (id, original_filename, file_hash, total_pages, registered_at, compiler_version)"
        " VALUES (?, ?, ?, 1, '2026-10-06T00:00:00+00:00', 'test')", (filename * 2, filename, filename * 2))
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def layout(tmp_path, monkeypatch):
    study_a = _workspace(tmp_path / "studyA" / "build" / "hermeneia.db", "studyA.pdf")
    _workspace(tmp_path / "studyB" / "build" / "hermeneia.db", "studyB.pdf")
    portable = tmp_path / "Downloads" / "studyA.herm"
    portable.mkdir(parents=True)
    shutil.copyfile(study_a, portable / "hermeneia.db")
    (portable / "context.json").write_text("{}")
    copy = tmp_path / "studyA-copy.sqlite"
    shutil.copyfile(study_a, copy)
    monkeypatch.chdir(tmp_path / "studyB")          # the shell sits inside another workspace
    return {"portable": portable, "copy": copy, "missing": tmp_path / "nowhere.sqlite",
            "empty_dir": tmp_path / "Downloads"}


def _resolve(module: str, target: str) -> Path:
    if module == "extract_cmd":
        path, conn = importlib.import_module("hermeneia.cli.extract_cmd")._open_db(target)
        conn.close()
        return path
    return importlib.import_module(f"hermeneia.cli.{module}")._resolve_db(target)


def _documents(path: Path) -> list[str]:
    return [r[0] for r in sqlite3.connect(path).execute("SELECT original_filename FROM source_documents")]


@pytest.mark.xfail(strict=True, raises=WrongWorkspaceTarget,
                   reason="#225: CLI resolvers substitute ./build/hermeneia.db; repair requires its own packet")
@pytest.mark.parametrize("module", RESOLVER_MODULES + ["extract_cmd"])
def test_explicit_targets_resolve_exactly(layout, module):
    for label in ("portable", "copy"):
        try:
            resolved = _resolve(module, str(layout[label]))
        except SystemExit as exc:
            raise WrongWorkspaceTarget(f"{module} refused existing {label} target: {exc}") from exc
        if _documents(resolved) != ["studyA.pdf"]:
            raise WrongWorkspaceTarget(f"{module} resolved {label} to {resolved} ({_documents(resolved)})")


@pytest.mark.xfail(strict=True, raises=WrongWorkspaceTarget,
                   reason="#225: unresolvable explicit targets fall back silently; repair requires its own packet")
@pytest.mark.parametrize("module", RESOLVER_MODULES + ["extract_cmd"])
def test_unresolvable_explicit_targets_fail_loudly(layout, module):
    for label in ("missing", "empty_dir"):
        try:
            resolved = _resolve(module, str(layout[label]))
        except SystemExit:
            continue
        raise WrongWorkspaceTarget(f"{module} resolved unresolvable {label} target to {resolved}")


@pytest.mark.xfail(strict=True, raises=WrongWorkspaceTarget,
                   reason="#225: herm stats reports another workspace; repair requires its own packet")
def test_herm_stats_on_portable_bundle_reports_that_bundle(layout):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-m", "hermeneia.cli.main", "stats", str(layout["portable"])],
                            capture_output=True, text=True, env=env, timeout=120)
    if "studyA.pdf" not in result.stdout or "studyB.pdf" in result.stdout:
        raise WrongWorkspaceTarget(result.stdout[-400:] + result.stderr[-400:])
