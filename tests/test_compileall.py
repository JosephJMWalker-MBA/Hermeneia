from __future__ import annotations

import compileall
from pathlib import Path


def test_hermeneia_package_compiles() -> None:
    """All package modules must parse, including scaffold modules not imported elsewhere."""
    package_dir = Path(__file__).parent.parent / "hermeneia"
    assert compileall.compile_dir(str(package_dir), quiet=1)
