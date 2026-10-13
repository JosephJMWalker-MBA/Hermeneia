"""#252 coverage audit: the import preview names what a bundle does not carry before anything is restored.

The Reader no longer calls the export "a portable bundle of your work". The
import preview lists every not-carried surface the server declares, with the
source count, or "count unknown" for older bundles, and says nothing is
recreated. The real function runs under Node.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_evidence_board_ui import _extract_function

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _render(coverage) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for the import coverage test")
    source = INDEX.read_text()
    start = source.index("const _WS_SURFACE_LABELS = {")
    labels = source[start:source.index("};", start) + 2]
    script = ("const x = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');\n"
              + labels + "\n" + _extract_function(source, "function _wsCoverageHtml(")
              + f"\nconsole.log(JSON.stringify(_wsCoverageHtml({json.dumps(coverage)})));")
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_export_is_not_described_as_a_complete_bundle():
    source = INDEX.read_text()
    assert "portable .zip bundle of your work" not in source and "some record types are not included yet" in source


def test_the_preview_lists_every_not_carried_surface_with_its_source_count():
    html = _render({"not_carried": {
        "study_reviews": {"status": "unsupported", "source_records": {"observation_reviews": 1, "inquiry_notes": 3}},
        "blueprint_dependency_chain": {"status": "unsupported", "source_records": {"interpretations": 2, "narrative_blueprints": 1}},
        "derived_indexes": {"status": "unsupported", "source_records": {"terms": None, "observation_derived": 5}}}})
    assert "Not in this bundle" in html and "nothing is recreated" in html
    assert "Observation reviews and inquiry questions</span><span>4 in the source" in html
    assert "acceptance receipts</span><span>3 in the source" in html and "not rebuilt on restore" in html


def test_an_older_bundle_says_count_unknown_and_no_coverage_renders_nothing():
    html = _render({"not_carried": {"reports": {"status": "unsupported", "source_records": "unknown"}}})
    assert "count unknown" in html
    assert _render({}) == ""
