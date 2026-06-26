from __future__ import annotations

import importlib
import subprocess
import sys
import tomllib
import warnings
from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_canonical_import_path_is_hermeneia() -> None:
    package = importlib.import_module("hermeneia")

    assert package.__title__ == "Hermeneia"
    assert package.__version__ == "0.1.0"


def test_legacy_hermenia_import_warns_and_delegates() -> None:
    sys.modules.pop("hermenia", None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        package = importlib.import_module("hermenia")

    assert package.__title__ == "Hermeneia"
    assert any(
        "use 'hermeneia' instead" in str(warning.message)
        for warning in caught
    )


def test_legacy_submodules_share_canonical_module_and_class_identity() -> None:
    canonical_ontology = importlib.import_module("hermeneia.ontology")
    legacy_ontology = importlib.import_module("hermenia.ontology")
    canonical_observation = importlib.import_module(
        "hermeneia.ontology.observation"
    )
    legacy_observation = importlib.import_module(
        "hermenia.ontology.observation"
    )

    assert legacy_ontology is canonical_ontology
    assert legacy_observation is canonical_observation
    assert legacy_observation.Observation is canonical_observation.Observation


def test_pyproject_declares_identity_and_console_script() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert pyproject["project"]["name"] == "hermeneia"
    assert "hermeneia" in pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "hermenia" in pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    assert pyproject["project"]["scripts"]["herm"] == "hermeneia.cli.main:main"
    assert "flask" in pyproject["project"]["dependencies"]
    assert pyproject["project"]["optional-dependencies"]["anthropic"] == ["anthropic"]
    assert pyproject["project"]["optional-dependencies"]["openai"] == ["openai"]
    assert pyproject["project"]["optional-dependencies"]["gemini"] == ["google-genai"]
    assert pyproject["project"]["optional-dependencies"]["ollama"] == ["ollama"]


def test_package_cli_help_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "hermeneia.cli.main", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Hermeneia inspection CLI" in result.stdout
