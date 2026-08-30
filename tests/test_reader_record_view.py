"""Reader "Record" tab — a ledger of ratified narratives.

This is a record ledger, not an outputs gallery: it shows accountable artifacts
with provenance, the exact saved text, and lineage back to evidence. These tests
guard the wiring, the read-only endpoints it uses, and the ledger framing.
"""
from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name}"
    return match.group(0)


def test_record_tab_and_panel_present():
    index = _index()
    assert 'id="cr-bottom-resource-record"' in index
    assert 'data-workstation-resource="record"' in index
    assert 'aria-controls="cr-record-ledger"' in index
    assert "_crOpenBottomWorkstation('record')" in index
    assert 'id="cr-record-ledger"' in index
    assert 'id="cr-record-ledger" hidden' in index


def test_record_is_a_workstation_mode_not_a_separate_drawer():
    index = _index()
    assert "record: document.getElementById('cr-record-ledger')" in index
    assert "else if (mode === 'record')" in index
    assert "['cr-bottom-resource-record', () => _crOpenBottomWorkstation('record')]" in index


def test_record_uses_readonly_narrative_endpoints():
    index = _index()
    assert "'/api/reader/narratives'" in index
    assert "/api/reader/narratives/" in index
    detail = _extract_fn(index, "_crShowRecord")
    # Shows the exact saved bytes and offers trace-to-evidence.
    assert "rendered_narrative" in detail
    assert "_crRecordTrace()" in detail
    trace = _extract_fn(index, "_crRecordTrace")
    assert "lineageHref" in trace          # lineage surface from the detail


def test_it_is_a_ledger_not_a_gallery():
    index = _index()
    assert "Record" in index
    # Framed as an accountable record, never a showcased-content gallery.
    assert "My Essays" not in index
    ledger_region = _extract_fn(index, "_crLoadRecordLedger")
    assert "No ratified records yet" in ledger_region


def test_record_functions_exposed():
    index = _index()
    assert "window._crLoadRecordLedger = _crLoadRecordLedger;" in index
    assert "window._crShowRecord = _crShowRecord;" in index
