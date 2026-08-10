"""Persisted Reader highlight marks reopen the exact saved Inspector record.

Invariant: a visible Reader highlight is one durable authored record. Clicking
its rendered mark may reopen that record, but must not infer a new selection or
create another highlight row.
"""
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


def _click_harness() -> str:
    html = INDEX.read_text()
    functions = [
        "_crNodeElement",
        "_crSelectionInsideReader",
        "_crRankLabel",
        "_crRankOptions",
        "_crAnnotationMetaHtml",
        "_crReaderHasActiveNativeSelection",
        "_crOpenHighlightInspectorById",
        "_crShowHighlightDetail",
        "_crHandlePersistedHighlightClick",
    ]
    return (
        "const Node={ELEMENT_NODE:1};\n"
        "const _CR_RANK_LABELS={1:'Speculative',2:'Minor',3:'Useful',4:'Strong',5:'Foundational'};\n"
        "function x(s){return String(s==null?'':s)"
        ".replace(/&/g,'&amp;').replace(/</g,'&lt;')"
        ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');}\n"
        "function matches(el,sel){if(!el)return false;return sel.split(',').some(raw=>{const s=raw.trim();"
        "if(s.startsWith('#'))return el.id===s.slice(1);"
        "if(s.startsWith('.'))return el.classes&&el.classes.has(s.slice(1));"
        "if(s==='[data-highlight-id]')return !!(el.dataset&&el.dataset.highlightId);"
        "return false;});}\n"
        "function makeEl(opts={}){const el={nodeType:1,id:opts.id||'',dataset:opts.dataset||{},"
        "classes:new Set(opts.classes||[]),parentElement:null,children:[],style:{},hidden:false,"
        "innerHTML:'',removed:false,"
        "getAttribute(name){if(name==='data-highlight-id')return this.dataset.highlightId||'';return opts.attrs?.[name]||'';},"
        "setAttribute(name,value){this.attrs=this.attrs||{};this.attrs[name]=String(value);},"
        "contains(node){let cur=node&&node.nodeType===3?node.parentElement:node;while(cur){if(cur===el)return true;cur=cur.parentElement;}return false;},"
        "closest(sel){let cur=el;while(cur){if(matches(cur,sel))return cur;cur=cur.parentElement;}return null;},"
        "scrollIntoView(){globalThis.scrollCalls=(globalThis.scrollCalls||0)+1;},"
        "classList:{add(c){el.classes.add(c);},remove(c){el.classes.delete(c);},toggle(c,on){on?el.classes.add(c):el.classes.delete(c);}},"
        "remove(){this.removed=true;}};return el;}\n"
        "const pageView=makeEl({id:'cr-page-view'});\n"
        "const textEl=makeEl({classes:['cr-page-text']});textEl.parentElement=pageView;pageView.children.push(textEl);\n"
        "const form=makeEl({id:'cr-sel-form'});const prompt=makeEl({id:'cr-sel-prompt'});\n"
        "function mark(id){const el=makeEl({dataset:{highlightId:id}});el.parentElement=textEl;textEl.children.push(el);return el;}\n"
        "const marks=[mark('hl-one'),mark('hl-one'),mark('hl-one')];const legacyMark=mark('legacy-id');\n"
        "let nativeSelectionActive=false;"
        "const range={startContainer:{nodeType:3,parentElement:textEl},endContainer:{nodeType:3,parentElement:textEl},commonAncestorContainer:textEl};"
        "const window={getSelection(){return nativeSelectionActive?{rangeCount:1,isCollapsed:false,getRangeAt(){return range;}}:{rangeCount:0,isCollapsed:true};},"
        "CSS:{highlights:{delete(name){globalThis.pendingDeletes=(globalThis.pendingDeletes||[]).concat([name]);}}}};\n"
        "const document={getElementById(id){if(id==='cr-page-view')return pageView;if(id==='cr-sel-form')return form;if(id==='cr-sel-prompt')return prompt;return null;}};\n"
        "let _crDocId='doc-1';let _crHighlights=[];let _crCaptureOpen=false;let _crSelToolbar=null;let _crRelevance='unclear';"
        "let _crReaderSelectionState={text:'cached selection'};let loadCalls=0;let dockPanels=[];let onboardingSteps=[];"
        "let highlightSelectedCalls=0;let setSelectionCalls=0;let fetchCalls=0;let appErrors=[];"
        "function _crHighlightTags(h){return Array.isArray(h&&h.tags)?h.tags:[];}"
        "function _crHideToolbar(force=false){if(_crSelToolbar){_crSelToolbar.removed=true;_crSelToolbar=null;}}"
        "function _dockOpenPanel(name){dockPanels.push(name);}"
        "function cmpMarkOnboardingStep(step){onboardingSteps.push(step);}"
        "async function _crLoadHighlightList(){loadCalls++;}"
        "function _crHighlightSelected(){highlightSelectedCalls++;}"
        "function _crSetReaderSelectionState(){setSelectionCalls++;}"
        "function showAppError(message){appErrors.push(message);}"
        "function fetch(){fetchCalls++;return Promise.resolve({ok:true,json(){return Promise.resolve({});}});}\n"
        + "".join(_extract_fn(html, name) for name in functions)
    )


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader highlight click behavior test")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_persisted_highlight_marks_open_exact_saved_inspector_record() -> None:
    script = _click_harness() + r"""
_crHighlights = [{
  id: 'hl-one',
  page: 7,
  selected_text: 'first saved passage',
  note_text: 'stored note text',
  question_text: 'stored question text',
  relevance: 'supports',
  status: 'saved_highlight',
  rank: 4,
  theme_bucket: 'voice',
  tags: ['important', 'tag:craft'],
}, {
  id: 'legacy-id',
  page: 2,
  selected_text: 'legacy exact-text mark',
  note_text: 'legacy note',
  question_text: '',
  relevance: 'unclear',
  status: 'saved_highlight',
  tags: [],
  source_locator: null,
}];
function click(target){
  const event = {target, prevented:false, stopped:false,
    preventDefault(){this.prevented=true;},
    stopPropagation(){this.stopped=true;}};
  _crHandlePersistedHighlightClick(event);
  return {prevented:event.prevented, stopped:event.stopped, html:form.innerHTML};
}
const first = click(marks[0]);
form.innerHTML = ''; prompt.style.display = '';
const second = click(marks[1]);
form.innerHTML = ''; prompt.style.display = '';
const third = click(marks[2]);
form.innerHTML = ''; prompt.style.display = '';
const legacy = click(legacyMark);
process.stdout.write(JSON.stringify({
  first, second, third, legacy,
  formDisplay: form.style.display,
  promptDisplay: prompt.style.display,
  dockPanels,
  onboardingSteps,
  loadCalls,
  pendingDeletes: globalThis.pendingDeletes || [],
  readerSelectionText: _crReaderSelectionState.text,
  highlightSelectedCalls,
  setSelectionCalls,
  fetchCalls,
  appErrors,
  scrollCalls: globalThis.scrollCalls || 0,
}));
"""
    behavior = _run_node(script)

    for opened in (behavior["first"], behavior["second"], behavior["third"]):
        assert opened["prevented"] is True
        assert opened["stopped"] is True
        assert "first saved passage" in opened["html"]
        assert "stored note text" in opened["html"]
        assert "stored question text" in opened["html"]
        assert "Rank 4" in opened["html"]
        assert "Theme voice" in opened["html"]

    assert "legacy exact-text mark" in behavior["legacy"]["html"]
    assert "legacy note" in behavior["legacy"]["html"]
    assert behavior["dockPanels"] == ["inspector"] * 4
    assert behavior["onboardingSteps"] == ["observe"] * 4
    assert behavior["loadCalls"] == 0
    assert behavior["pendingDeletes"] == ["hermeneia-pending"] * 4
    assert behavior["readerSelectionText"] == "cached selection"
    assert behavior["highlightSelectedCalls"] == 0
    assert behavior["setSelectionCalls"] == 0
    assert behavior["fetchCalls"] == 0
    assert behavior["appErrors"] == []
    assert behavior["scrollCalls"] == 4
    assert behavior["formDisplay"] == "block"
    assert behavior["promptDisplay"] == "none"


def test_persisted_highlight_click_defers_to_active_reader_selection() -> None:
    script = _click_harness() + r"""
_crHighlights = [{
  id: 'hl-one',
  page: 7,
  selected_text: 'first saved passage',
  note_text: 'stored note text',
  relevance: 'unclear',
  status: 'saved_highlight',
  tags: [],
}];
nativeSelectionActive = true;
const event = {target: marks[0], prevented:false, stopped:false,
  preventDefault(){this.prevented=true;},
  stopPropagation(){this.stopped=true;}};
_crHandlePersistedHighlightClick(event);
process.stdout.write(JSON.stringify({
  prevented: event.prevented,
  stopped: event.stopped,
  html: form.innerHTML,
  dockPanels,
  loadCalls,
  readerSelectionText: _crReaderSelectionState.text,
  highlightSelectedCalls,
  setSelectionCalls,
  fetchCalls,
}));
"""
    behavior = _run_node(script)

    assert behavior == {
        "prevented": False,
        "stopped": False,
        "html": "",
        "dockPanels": [],
        "loadCalls": 0,
        "readerSelectionText": "cached selection",
        "highlightSelectedCalls": 0,
        "setSelectionCalls": 0,
        "fetchCalls": 0,
    }


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "reader_highlight_click.db"
    SQLiteStore(db_path).close()
    return db_path


def _insert_doc(conn: sqlite3.Connection, doc_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 1, now, "test", "primary", 0),
    )


def test_highlight_note_edit_updates_same_record_and_survives_reload(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    doc_id = "a" * 64
    conn = sqlite3.connect(db)
    _insert_doc(conn, doc_id)
    conn.commit()
    conn.close()

    client = create_app(db_path=db).test_client()
    created = client.post(
        "/api/reader/highlights",
        json={
            "source_document_id": doc_id,
            "selected_text": "the exact saved passage",
            "note_text": "original note",
            "question_text": "original question",
            "relevance": "supports",
            "page": 1,
        },
    )
    assert created.status_code == 201
    highlight_id = created.get_json()["id"]

    patched = client.patch(
        f"/api/reader/highlights/{highlight_id}",
        json={
            "note_text": "updated note",
            "question_text": "updated question",
            "relevance": "complicates",
        },
    )
    assert patched.status_code == 200

    fresh_client = create_app(db_path=db).test_client()
    rows = fresh_client.get(f"/api/reader/documents/{doc_id}/highlights").get_json()["highlights"]

    assert [h["id"] for h in rows] == [highlight_id]
    assert rows[0]["selected_text"] == "the exact saved passage"
    assert rows[0]["note_text"] == "updated note"
    assert rows[0]["question_text"] == "updated question"
    assert rows[0]["relevance"] == "complicates"

    conn = sqlite3.connect(db)
    highlight_count = conn.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    observation_count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn.close()

    assert highlight_count == 1
    assert observation_count == 0
