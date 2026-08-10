"""Field Notes cadence must not infer semantic reflection from page navigation."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_fn(html: str, name: str) -> str:
    match = re.search(
        r"\n(?:async\s+)?function " + re.escape(name) + r"\(.*?\n\}\n",
        html,
        re.S,
    )
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Field Notes cadence UI test")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_page_navigation_does_not_auto_open_field_notes() -> None:
    html = INDEX.read_text()
    script = (
        "let _crPage=1;let _crTotalPages=10;let renders=0;let scrollCalls=0;"
        "let trayOpen=false;let trayCalls=0;let onboardingCalls=0;"
        "const workstationClasses=new Set();"
        "const workstation={classList:{add(c){workstationClasses.add(c);},"
        "remove(c){workstationClasses.delete(c);}}};"
        "const document={getElementById(id){"
        "if(id==='cr-page-view')return {offsetTop:120};"
        "if(id==='cr-bottom-workstation')return workstation;"
        "return null;},querySelector(){return {id:'reader'};}};"
        "const window={scrollTo(){scrollCalls++;}};"
        "function setTimeout(){}"
        "function flnToggleTray(force){trayCalls++;trayOpen=!!force;}"
        "function cmpMarkOnboardingStep(){onboardingCalls++;}"
        "function _crRenderPage(){renders++;_flnActivityTick();}"
        + _extract_fn(html, "_flnActivityTick")
        + _extract_fn(html, "_crNextPage")
        + _extract_fn(html, "_crPrevPage")
        + """
for (let i = 0; i < 8; i++) _crNextPage();
const afterForward = {
  page: _crPage,
  renders,
  trayOpen,
  trayCalls,
  scrollCalls,
  onboardingCalls,
};
for (let i = 0; i < 3; i++) _crPrevPage();
const afterBackward = {
  page: _crPage,
  renders,
  trayOpen,
  trayCalls,
  scrollCalls,
  onboardingCalls,
};
for (let i = 0; i < 20; i++) _flnActivityTick();
const afterTicks = {trayOpen, trayCalls};
process.stdout.write(JSON.stringify({afterForward, afterBackward, afterTicks}));
"""
    )

    behavior = _run_node(script)

    assert behavior["afterForward"] == {
        "page": 9,
        "renders": 8,
        "trayOpen": False,
        "trayCalls": 0,
        "scrollCalls": 8,
        "onboardingCalls": 8,
    }
    assert behavior["afterBackward"] == {
        "page": 6,
        "renders": 11,
        "trayOpen": False,
        "trayCalls": 0,
        "scrollCalls": 11,
        "onboardingCalls": 11,
    }
    assert behavior["afterTicks"] == {"trayOpen": False, "trayCalls": 0}


def test_manual_field_notes_still_opens_from_reader_rail() -> None:
    html = INDEX.read_text()
    script = (
        "let trayOpen=false;let trayCalls=0;let dockCalls=[];"
        "const bottomClasses=new Set();"
        "const bottom={classList:{add(c){bottomClasses.add(c);},"
        "remove(c){bottomClasses.delete(c);}}};"
        "const document={getElementById(id){"
        "if(id==='cr-bottom-workstation')return bottom;"
        "return null;}};"
        "const _CR_TOOL_TARGETS={fieldnotes:'cr-fln-tray'};"
        "function setTimeout(fn){if(typeof fn==='function')fn();}"
        "function flnToggleTray(force){trayCalls++;trayOpen=!!force;}"
        "function _dockOpenPanel(key){dockCalls.push(key);}"
        + _extract_fn(html, "_crRailGo")
        + """
_crRailGo('fieldnotes');
process.stdout.write(JSON.stringify({
  trayOpen,
  trayCalls,
  dockCalls,
  flashed: bottomClasses.has('cr-tool-flash'),
}));
"""
    )

    behavior = _run_node(script)

    assert behavior == {
        "trayOpen": True,
        "trayCalls": 1,
        "dockCalls": [],
        "flashed": False,
    }


def test_page_progress_does_not_change_saved_field_notes(tmp_path: Path) -> None:
    db_path = tmp_path / "field_notes_cadence.db"
    SQLiteStore(db_path).close()
    doc_id = "c" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            doc_id,
            "second-sale.pdf",
            doc_id,
            6,
            datetime.now(timezone.utc).isoformat(),
            "test",
            "primary",
            0,
        ),
    )
    conn.commit()
    conn.close()

    client = create_app(db_path=db_path).test_client()
    note = {
        "lane": "corpus",
        "understanding": "Chapter 12 feels complete only after the boundary is crossed.",
        "pressing_questions": "What changes after the donor room begins?",
        "source_document_id": doc_id,
        "page": 2,
        "governing_question": "How does the sale reshape responsibility?",
    }
    assert client.post("/api/investigation-log", json=note).status_code == 201

    for page in (1, 2, 3, 2):
        assert client.post(
            "/api/reader/progress",
            json={"document_id": doc_id, "page": page},
        ).status_code == 200

    entries = client.get("/api/investigation-log").get_json()["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["lane"] == note["lane"]
    assert entry["understanding"] == note["understanding"]
    assert entry["pressing_questions"] == note["pressing_questions"]
    assert entry["source_document_id"] == doc_id
    assert entry["page"] == note["page"]
    assert entry["governing_question"] == note["governing_question"]
