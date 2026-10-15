"""Shared behavioral check: a workstation rail button opens its Reader workstation mode.

Since f36328d ("keep workstation rail anchored to Reader") the rail buttons
call `_wfGo(target)`. That routes to the Reader and opens the bottom
workstation resource, mapping `expression` to `voice`. Older string pins
named the direct `_crToggleBottomWorkstationResource(...)` binding. This
runs the real `_wfGo` under Node instead.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_evidence_board_ui import _extract_function

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def wf_go_routes(*targets: str) -> dict[str, dict]:
    """For each target: the workstation mode opened, whether the Reader was entered, whether it was closed instead."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for the workstation routing check")
    script = ("let _currentStageId='lab'; let calls=[];\n"
              "function e10Go(stage){calls.push(['stage', stage]); _currentStageId=stage;}\n"
              "function _crCloseBottomWorkstation(){calls.push(['close']);}\n"
              "function _crToggleBottomWorkstationResource(mode){calls.push(['open', mode]); return mode;}\n"
              + _extract_function(INDEX.read_text(), "function _wfGo(")
              + "\nconst out={};\n"
              + "".join(f"calls=[]; _currentStageId='lab'; _wfGo({json.dumps(t)}); out[{json.dumps(t)}]=calls.slice();\n" for t in targets)
              + "console.log(JSON.stringify(out));")
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    return {t: {"opened": next((c[1] for c in out[t] if c[0] == "open"), None),
                "entered_reader": ["stage", "reader"] in out[t],
                "closed": ["close"] in out[t]} for t in targets}
