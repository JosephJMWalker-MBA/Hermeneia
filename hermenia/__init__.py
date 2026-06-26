"""Temporary compatibility alias for the renamed :mod:`hermeneia` package."""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import warnings

warnings.warn(
    "The 'hermenia' import path is deprecated; use 'hermeneia' instead.",
    DeprecationWarning,
    stacklevel=2,
)

_canonical = importlib.import_module("hermeneia")

__path__ = _canonical.__path__
__all__ = getattr(_canonical, "__all__", [])

for _name in __all__:
    globals()[_name] = getattr(_canonical, _name)


class _LegacyModuleLoader(importlib.abc.Loader):
    def __init__(self, canonical_name: str) -> None:
        self._canonical_name = canonical_name

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> object:
        return importlib.import_module(self._canonical_name)

    def exec_module(self, module: object) -> None:
        return None


class _LegacyModuleFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith("hermenia."):
            return None

        canonical_name = f"hermeneia.{fullname.removeprefix('hermenia.')}"
        canonical_spec = importlib.util.find_spec(canonical_name)
        if canonical_spec is None:
            return None

        return importlib.util.spec_from_loader(
            fullname,
            _LegacyModuleLoader(canonical_name),
            origin=canonical_spec.origin,
            is_package=canonical_spec.submodule_search_locations is not None,
        )


if not any(isinstance(finder, _LegacyModuleFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _LegacyModuleFinder())
