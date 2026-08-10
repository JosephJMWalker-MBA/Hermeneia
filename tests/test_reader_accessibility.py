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


def _reader_selection_harness() -> str:
    html = INDEX.read_text()
    functions = [
        "_a11yGetSelectedText",
        "_a11yCacheReaderSelection",
        "_a11yGetDockReadText",
        "a11yDismissTip",
        "a11yClickRead",
        "a11yReadSelection",
        "_crNodeElement",
        "_crSelectionInsideReader",
        "_crCleanSelectionText",
        "_crReaderBlockInfo",
        "_crSelectionBlockInfos",
        "_crUsableRect",
        "_crRangeRect",
        "_crCreateReaderSelectionFromRange",
        "_crResolveReaderSelection",
        "_crSetReaderSelectionState",
        "_crClearReaderSelection",
        "_crShowA11ySelectionTip",
        "_crShowReaderSelectionAffordances",
        "_crResolveAndCacheReaderSelection",
        "_crGetReaderSelection",
        "_crCurrentReaderSelectionText",
        "_crHandleSelection",
        "_crReaderSelectionControlTarget",
        "_crHandleReaderSelectionPointerDown",
        "speakSelectedReaderText",
        "_crPlaceToolbar",
        "_crShowToolbar",
        "_crHideToolbar",
    ]
    return (
        "const Node={ELEMENT_NODE:1};\n"
        "function rect(left,top,width,height){return {left,top,width,height,right:left+width,bottom:top+height};}\n"
        "function makeEl(opts={}){const el={nodeType:1,id:opts.id||'',dataset:opts.dataset||{},"
        "classes:new Set(opts.classes||[]),parentElement:null,children:[],style:{},"
        "offsetWidth:opts.offsetWidth||390,offsetHeight:opts.offsetHeight||120,"
        "getBoundingClientRect(){return opts.rect||rect(20,20,120,20);},"
        "contains(node){let cur=node&&node.nodeType===3?node.parentElement:node;while(cur){if(cur===el)return true;cur=cur.parentElement;}return false;},"
        "closest(sel){let cur=el;while(cur){if(matches(cur,sel))return cur;cur=cur.parentElement;}return null;},"
        "querySelector(sel){return this.children.find(c=>matches(c,sel))||null;},"
        "classList:{add(c){el.classes.add(c);},remove(c){el.classes.delete(c);},toggle(c,on){on?el.classes.add(c):el.classes.delete(c);}},"
        "remove(){el.removed=true;if(globalThis._lastToolbar===el)globalThis._lastToolbar=null;}};"
        "return el;}\n"
        "function matches(el,sel){if(!el)return false;return sel.split(',').some(raw=>{const s=raw.trim();"
        "if(s.startsWith('#'))return el.id===s.slice(1);"
        "if(s.startsWith('.'))return el.classes&&el.classes.has(s.slice(1));"
        "const m=s.match(/^\\[data-cr-block=\"?(\\d+)\"?\\]$/);"
        "if(m)return String(el.dataset&&el.dataset.crBlock)===m[1];"
        "return false;});}\n"
        "const pageView=makeEl({id:'cr-page-view',classes:['cr-page-view'],rect:rect(0,0,600,600)});\n"
        "const tip=makeEl({id:'a11y-selection-tip'});\n"
        "const outside=makeEl({id:'outside'});\n"
        "const toolbarControl=makeEl({id:'toolbar-button'});\n"
        "const blocks=[];\n"
        "function addBlock(index,locator,textRect){const block=makeEl({classes:['cr-text-block'],dataset:{crBlock:String(index),crLocator:locator},rect:textRect});"
        "const textEl=makeEl({classes:['cr-page-text'],rect:textRect});const textNode={nodeType:3,parentElement:textEl};"
        "textEl.parentElement=block;block.children.push(textEl);block.parentElement=pageView;pageView.children.push(block);"
        "blocks[index]={block,textEl,textNode};return blocks[index];}\n"
        "addBlock(0,'p.1.s.1',rect(100,100,300,24));addBlock(1,'p.1.s.2',rect(100,140,340,24));\n"
        "toolbarControl.parentElement=null;\n"
        "let selection={rangeCount:0,isCollapsed:true,toString(){return '';}};\n"
        "function makeRange(start,end,rangeRect,clientRects){return {startContainer:start.textNode,endContainer:end.textNode,commonAncestorContainer:start===end?start.textEl:pageView,"
        "cloneRange(){return this;},getBoundingClientRect(){return rangeRect;},getClientRects(){return clientRects||[rangeRect];}};}\n"
        "function setSelection(text,startIndex,endIndex,rangeRect,clientRects){const range=makeRange(blocks[startIndex],blocks[endIndex],rangeRect,clientRects);"
        "selection={rangeCount:1,isCollapsed:false,toString(){return text;},getRangeAt(){return range;}};}\n"
        "function collapseSelection(){selection={rangeCount:1,isCollapsed:true,toString(){return '';},getRangeAt(){return makeRange(blocks[0],blocks[0],rect(0,0,0,0));}};}\n"
        "function setOutsideSelection(){const textNode={nodeType:3,parentElement:outside};const range={startContainer:textNode,endContainer:textNode,commonAncestorContainer:outside,"
        "cloneRange(){return this;},getBoundingClientRect(){return rect(5,5,30,10);},getClientRects(){return [rect(5,5,30,10)];}};"
        "selection={rangeCount:1,isCollapsed:false,toString(){return 'Outside text';},getRangeAt(){return range;}};}\n"
        "const window={getSelection(){return selection;},innerWidth:900,innerHeight:700,scrollY:0};\n"
        "const document={body:{classList:{toggle(){}},appendChild(el){globalThis._lastToolbar=el;}},"
        "getElementById(id){if(id==='cr-page-view')return pageView;if(id==='a11y-selection-tip')return tip;if(id==='a11y-status')return statusEl;return null;},"
        "querySelector(sel){const m=sel.match(/^\\[data-cr-block=\"?(\\d+)\"?\\]$/);return m?blocks[Number(m[1])]?.block:null;},"
        "createElement(){return makeEl({id:'cr-sel-toolbar'});}};\n"
        "const statusEl={textContent:'',className:''};\n"
        "const _a11y={read:false,speaking:false};let _a11yHintShown=true;let _a11yHintTimer=null;let _a11yLastReaderSelection='';\n"
        "let _crReaderSelectionState=null;let _crReaderSelectionGeneration=0;let _crSelectionResolveTimer=null;"
        "let _crDocId='doc-1';let _crPage=1;let _crCurrentExtractions=[{id:'ex-1',source_locator:'p.1.s.1',region:'body'},{id:'ex-2',source_locator:'p.1.s.2',region:'body'}];"
        "let _crSelText='';let _crSelRange=null;let _crSelectionRect=null;let _crSelToolbar=null;let _crCaptureOpen=false;"
        "let spoken=[];let fetchCalls=0;\n"
        "function _cmpRenderContextRows(){}function _a11ySync(){}function _a11ySetStatus(message,cls){statusEl.textContent=message;statusEl.className=cls||'';}"
        "function a11ySpeak(text){spoken.push(text);a11yDismissTip();}function setTimeout(fn){fn();}function clearTimeout(){}"
        "function fetch(){fetchCalls++;return Promise.resolve({ok:true,json(){return Promise.resolve({});}});}\n"
        + "".join(_extract_fn(html, name) for name in functions)
    )


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Reader selection behavior test")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_reader_selection_resolver_drives_toolbar_for_natural_selection_shapes():
    script = _reader_selection_harness() + """
function snap(label){
  return {
    label,
    text:_crReaderSelectionState?.text||'',
    start:_crReaderSelectionState?.start?.block_index,
    end:_crReaderSelectionState?.end?.block_index,
    locators:_crReaderSelectionState?.source_locators||[],
    extractions:_crReaderSelectionState?.extraction_ids||[],
    generation:_crReaderSelectionState?.generation||0,
    toolbar:!!_crSelToolbar,
    toolbarHasRead:!!(_crSelToolbar&&_crSelToolbar.innerHTML.includes('speakSelectedReaderText()')),
    tip:tip.style.display||'none'
  };
}
const cases=[];
setSelection('partial drag selection',0,0,rect(120,100,100,24));_crHandleSelection({clientX:150,clientY:105});cases.push(snap('partial'));
setSelection('word',0,0,rect(130,100,36,24));_crHandleSelection({clientX:140,clientY:105});cases.push(snap('word'));
setSelection('whole logical span',0,0,rect(0,0,0,0),[rect(100,100,300,24)]);_crHandleSelection({clientX:200,clientY:105});cases.push(snap('whole-span'));
setSelection('first block second block',0,1,rect(100,100,340,64));_crHandleSelection({clientX:180,clientY:120});cases.push(snap('multi-block'));
const repeated=[];
for(let i=0;i<4;i++){setSelection('repeated word',0,0,rect(140,100,80,24));_crHandleSelection({clientX:160,clientY:105});repeated.push(snap('repeat-'+i));}
process.stdout.write(JSON.stringify({cases,repeated,fetchCalls}));
"""
    behavior = _run_node(script)

    assert [case["label"] for case in behavior["cases"]] == [
        "partial",
        "word",
        "whole-span",
        "multi-block",
    ]
    assert all(case["toolbar"] and case["toolbarHasRead"] for case in behavior["cases"])
    assert all(case["tip"] == "flex" for case in behavior["cases"])
    assert behavior["cases"][0]["extractions"] == ["ex-1"]
    assert behavior["cases"][3]["extractions"] == ["ex-1", "ex-2"]
    assert behavior["cases"][3]["start"] == 0 and behavior["cases"][3]["end"] == 1
    assert [case["text"] for case in behavior["repeated"]] == ["repeated word"] * 4
    assert len({case["generation"] for case in behavior["repeated"]}) == 4
    assert behavior["fetchCalls"] == 0, "Selecting text must not persist a highlight"


def test_reader_read_surfaces_share_cached_selection_after_native_collapse():
    script = _reader_selection_harness() + """
setSelection('shared selected passage',0,0,rect(120,100,190,24));_crHandleSelection({clientX:150,clientY:105});
const cachedBeforeCollapse=_crReaderSelectionState.text;
collapseSelection();
const semantic=speakSelectedReaderText();
a11yClickRead();
a11yReadSelection();
process.stdout.write(JSON.stringify({
  cachedBeforeCollapse,
  semantic,
  spoken,
  dockText:_a11yGetDockReadText(),
  selectedTextNow:_a11yGetSelectedText(),
  status:statusEl.textContent,
  cache:_a11yLastReaderSelection
}));
"""
    behavior = _run_node(script)

    assert behavior["cachedBeforeCollapse"] == "shared selected passage"
    assert behavior["semantic"] is True
    assert behavior["spoken"] == ["shared selected passage"] * 3
    assert behavior["dockText"] == "shared selected passage"
    assert behavior["selectedTextNow"] == ""
    assert behavior["cache"] == "shared selected passage"


def test_selection_outside_reader_does_not_populate_reader_selection_state():
    script = _reader_selection_harness() + """
setSelection('reader text',0,0,rect(120,100,90,24));_crHandleSelection({clientX:150,clientY:105});
const before={text:_crReaderSelectionState?.text||'',toolbar:!!_crSelToolbar};
setOutsideSelection();_crHandleSelection({clientX:10,clientY:10});
process.stdout.write(JSON.stringify({
  before,
  afterText:_crReaderSelectionState?.text||'',
  afterToolbar:!!_crSelToolbar,
  afterTip:tip.style.display||'none',
  dockText:_a11yGetDockReadText(),
  fetchCalls
}));
"""
    behavior = _run_node(script)

    assert behavior["before"] == {"text": "reader text", "toolbar": True}
    assert behavior["afterText"] == ""
    assert behavior["afterToolbar"] is False
    assert behavior["afterTip"] == "none"
    assert behavior["dockText"] == ""
    assert behavior["fetchCalls"] == 0


def test_reader_selection_controls_do_not_clear_cached_selection_on_pointerdown():
    script = _reader_selection_harness() + """
setSelection('control cached passage',0,0,rect(120,100,160,24));_crHandleSelection({clientX:150,clientY:105});
const toolbar=makeEl({id:'toolbar-child'});toolbar.parentElement=makeEl({id:'cr-sel-toolbar'});
_crHandleReaderSelectionPointerDown({target:toolbar});
const kept=_crReaderSelectionState?.text||'';
_crHandleReaderSelectionPointerDown({target:outside});
process.stdout.write(JSON.stringify({kept,cleared:_crReaderSelectionState?.text||''}));
"""
    behavior = _run_node(script)

    assert behavior == {"kept": "control cached passage", "cleared": ""}
