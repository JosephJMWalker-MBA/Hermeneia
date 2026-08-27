from __future__ import annotations

import importlib
import tomllib
from pathlib import Path


ROOT = Path(__file__).parent.parent


def _dependency_name(requirement: str) -> str:
    name = requirement.split(";", 1)[0].strip()
    for separator in ("[", "<", ">", "=", "~", "!"):
        name = name.split(separator, 1)[0].strip()
    return name.lower()


def test_pyyaml_is_declared_runtime_dependency_for_cli_startup_imports() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    dependencies = pyproject["project"]["dependencies"]

    assert any(
        _dependency_name(dependency) == "pyyaml"
        for dependency in dependencies
    )
    importlib.import_module("hermeneia.cli.main")
