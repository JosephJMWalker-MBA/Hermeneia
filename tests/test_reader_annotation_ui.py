from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def test_reader_capture_and_edit_forms_expose_rank_and_theme_bucket_controls():
    index_html = INDEX.read_text()

    assert 'id="cr-rank-input"' in index_html
    assert 'id="cr-theme-input"' in index_html
    assert 'id="cr-edit-rank"' in index_html
    assert 'id="cr-edit-theme"' in index_html
    assert "How much weight should this mark carry?" in index_html
    assert "What kind of meaning does this belong to?" in index_html
    assert "Speculative" in index_html
    assert "Foundational" in index_html
    assert "_crRankOptions(null)" in index_html
    assert "_crRankOptions(h.rank)" in index_html
    assert "theme_bucket: themeBucket" in index_html
    assert "_crReadRankValue('cr-rank-input')" in index_html
    assert "_crReadRankValue('cr-edit-rank')" in index_html


def test_reader_ui_keeps_evidence_bucket_separate_from_theme_bucket():
    index_html = INDEX.read_text()

    assert "theme_bucket: themeBucket" in index_html
    assert "evidence_bucket" not in index_html
    assert "Evidence Bucket" not in index_html


def test_new_observation_candidate_note_starts_empty_with_placeholder():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader annotation UI helper test")

    html = INDEX.read_text()
    harness = (
        "let _crSelText='Selected passage';\n"
        "let _crRelevance='';\n"
        "let _crConcept='';\n"
        "let _crCaptureOpen=false;\n"
        "let _crSelectionRect=null;\n"
        "let _crSelToolbar=null;\n"
        "const elements={"
        "'cr-sel-form':{style:{},innerHTML:''},"
        "'cr-sel-prompt':{style:{},innerHTML:''}"
        "};\n"
        "const selection={text:'Selected passage',rect:{left:0,top:0,right:1,bottom:1}};\n"
        "const window={getSelection(){return {toString(){return _crSelText;}};}};\n"
        "const document={getElementById(id){return elements[id]||null;}};\n"
        "function _dockOpenPanel(){}\n"
        "function _crGetReaderSelection(){return selection;}\n"
        "function _crSetReaderSelectionState(next){_crSelText=next?.text||'';}\n"
        "function _crMarkPending(){}\n"
        "function _crShowToolbar(){_crSelToolbar={innerHTML:'',classList:{add(){}}};}\n"
        "function _crPlaceToolbar(){}\n"
        "function _crRankOptions(){return '<option value=\"\">No rank</option>';}\n"
        "function invLoad(){return {};}\n"
        "function requestAnimationFrame(fn){fn();}\n"
        "function setTimeout(fn){fn();}\n"
        "function x(s){return String(s==null?'':s)"
        ".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}\n"
        + _extract_fn(html, "_crHighlightSelected")
        + "_crHighlightSelected('candidate');\n"
        + "process.stdout.write(_crSelToolbar.innerHTML);\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    generated = result.stdout
    match = re.search(
        r'<textarea id="cr-note-input"[^>]*placeholder="([^"]*)"[^>]*>(.*?)</textarea>',
        generated,
        re.S,
    )
    assert match, generated
    assert match.group(1) == "Candidate for observation."
    assert match.group(2) == ""


def test_existing_highlight_edit_note_loads_saved_note_value():
    index_html = INDEX.read_text()

    assert (
        '<textarea id="cr-edit-note" rows="3" style="margin-top:4px">'
        "${x(h.note_text || '')}</textarea>"
    ) in index_html


def test_rank_theme_glance_only_renders_when_present():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader annotation UI helper test")

    html = INDEX.read_text()
    harness = (
        "function x(s){return String(s==null?'':s)"
        ".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}\n"
        "const _CR_RANK_LABELS={1:'Speculative',2:'Minor',3:'Useful',4:'Strong',5:'Foundational'};\n"
        + _extract_fn(html, "_crRankLabel")
        + _extract_fn(html, "_crAnnotationMetaHtml")
        + "const samples=JSON.parse(process.argv[1]);\n"
        + "process.stdout.write(JSON.stringify(samples.map(_crAnnotationMetaHtml)));\n"
    )
    payload = json.dumps([
        {},
        {"rank": None, "theme_bucket": ""},
        {"rank": 4, "theme_bucket": "aspiration", "evidence_bucket": "draft-1"},
    ])
    out = subprocess.run(
        [node, "-e", harness, "--", payload],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert out.returncode == 0, out.stderr
    empty, unranked, filled = json.loads(out.stdout)
    assert empty == ""
    assert unranked == ""
    assert "Rank 4 — Strong" in filled
    assert "Theme aspiration" in filled
    assert "Evidence" not in filled
