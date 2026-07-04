"""Reader-first boot destination (issue #56 slice 1, issue #26).

Product principle: the user reads first. Once a readable corpus exists,
Hermeneia opens the book before any pipeline/dashboard surface — even for a
returning steward who already saved an investigation question. A fresh
environment still lands on first-run onboarding, and every older stage stays
reachable by explicit navigation.

These tests execute the *actual* `_bootDestination` routing logic extracted
from index.html under Node, so they prove behavior rather than mere markup.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX_HTML = (
    Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
)


def _extract_function(source: str, signature: str) -> str:
    """Return `signature` plus its balanced `{ ... }` body from `source`."""
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    i = brace
    while i < len(source):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces extracting {signature!r}")


def _run_boot_destination(health: dict | None, saved_question: dict | None) -> str:
    """Evaluate the real `_bootDestination(h)` for a given environment."""
    if shutil.which("node") is None:  # pragma: no cover - environment guard
        pytest.skip("node runtime not available")

    src = INDEX_HTML.read_text()
    inv_key_line = "const _INV_KEY = 'hermeneia_investigation_v1';"
    assert inv_key_line in src, "investigation storage key moved"
    inv_load = _extract_function(src, "function invLoad(")
    boot = _extract_function(src, "function _bootDestination(h)")

    harness = f"""
    const _store = {{}};
    const localStorage = {{
      getItem(k) {{ return k in _store ? _store[k] : null; }},
      setItem(k, v) {{ _store[k] = String(v); }},
      removeItem(k) {{ delete _store[k]; }},
    }};
    {inv_key_line}
    {inv_load}
    {boot}
    const saved = {json.dumps(saved_question)};
    if (saved !== null) localStorage.setItem(_INV_KEY, JSON.stringify(saved));
    const h = {json.dumps(health)};
    console.log(_bootDestination(h));
    """
    result = subprocess.run(
        ["node", "-e", harness],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


# ── Behavior: the three required guarantees ────────────────────────────────


def test_fresh_environment_without_database_boots_to_first_run():
    """No workspace database → first-run setup still appears."""
    dest = _run_boot_destination(
        {"document": {"filename": None}, "_noDatabase": True},
        saved_question=None,
    )
    assert dest == "firstrun"


def test_database_without_corpus_boots_to_first_run():
    """A database exists but holds no readable document → first-run setup."""
    dest = _run_boot_destination(
        {"document": {"filename": None}},
        saved_question=None,
    )
    assert dest == "firstrun"


def test_existing_corpus_boots_into_reader():
    """A readable document present → open the book."""
    dest = _run_boot_destination(
        {"document": {"filename": "gatsby.pdf"}},
        saved_question=None,
    )
    assert dest == "reader"


def test_returning_steward_with_corpus_still_boots_into_reader():
    """The core slice-1 change: a saved investigation no longer diverts a
    steward who has a corpus to the pipeline dashboard."""
    dest = _run_boot_destination(
        {"document": {"filename": "gatsby.pdf"}},
        saved_question={"question": "What does the green light mean?"},
    )
    assert dest == "reader"


def test_returning_steward_without_corpus_resumes_onboarding():
    """Returning-user resume behavior is preserved when there is no book yet."""
    dest = _run_boot_destination(
        {"document": {"filename": None}},
        saved_question={"question": "What does the green light mean?"},
    )
    assert dest == "onboarding"


# ── Structure: older pipeline surfaces remain explicitly reachable ─────────


def test_pipeline_surfaces_remain_reachable_by_explicit_navigation():
    """Reader-first boot must not remove access to the older stages; the
    explicit navigation entry points still exist."""
    index_html = INDEX_HTML.read_text()
    for target in (
        "e10Go('onboarding')",
        "e10Go('corpus')",
        "e10Go('lab')",
        "e10Go('architect')",
        "e10Go('critic')",
        "e10Go('lineage')",
        "e10Go('reader')",
    ):
        assert target in index_html, target
