from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_function(source: str, signature: str) -> str:
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


def _extract_workspace_state_block(source: str) -> str:
    start = source.index("let _workspaceDatabaseAvailable = null;")
    end = source.index("// ── Runtime connectivity and local authored drafts", start)
    return source[start:end]


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node runtime not available")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _navigation_harness() -> str:
    html = INDEX.read_text()
    return (
        r"""
function makeClassList(){return {items:[],toggle(c,on){on?this.add(c):this.remove(c);},add(c){if(!this.items.includes(c))this.items.push(c);},remove(c){this.items=this.items.filter(x=>x!==c);}};}
function makeEl(id){
  return {
    id,
    _html:'',
    style:{},
    classList:makeClassList(),
    textContent:'',
    scrolled:false,
    set innerHTML(v){this._html=String(v);},
    get innerHTML(){return this._html;},
    scrollIntoView(){this.scrolled=true;},
  };
}
const elements={};
[
  'setup','onboarding','corpus','lab','review','reports','reader','critic','lineage','architect','guide','constitution','firstrun',
  'setup-panel','onboarding-panel','results','selected-observation','review-canon-panel','reader-panel','reader-workspace',
  'critic-picker-panel','lineage-explorer','architect-panel','guide-panel','constitution-panel','firstrun-panel',
  'reader-home-btn','return-reader-fab',
].forEach(id => elements[id] = makeEl(id));
const navButtons = ['corpus','reader','lab','review','architect','reports','critic'].map(id => {
  const el = makeEl(`navstep-${id}`);
  elements[el.id] = el;
  return el;
});
const screens = ['setup','onboarding','corpus','lab','review','reports','reader','critic','lineage','architect','guide','constitution','firstrun'].map(id => elements[id]);
const document = {
  body:{classList:makeClassList()},
  querySelectorAll(sel){
    if(sel === '.e10-screen') return screens;
    if(sel === '.nav-step') return navButtons;
    return [];
  },
  getElementById(id){return elements[id] || null;},
};
const window = {scrolls:[], scrollTo(opts){this.scrolls.push(opts);}};
function requestAnimationFrame(fn){fn();}
function updateNavCycle(id){calls.push(['cycle', id]);}
function refreshNavCycleStatuses(){calls.push(['refresh']); return Promise.resolve();}
function _updateStageNavBar(id){calls.push(['stage', id]);}
let calls=[];
let _expert = false;
let _obCanUploadDocuments = true;
"""
        + _extract_workspace_state_block(html)
        + _extract_function(html, "function _updateReaderReturnUI(")
        + _extract_function(html, "function _e10ApplyRouteChrome(")
        + _extract_function(html, "function _e10RenderMissingWorkspaceRecovery(")
        + r"""
function e10LoadFirstRun(){calls.push(['loader','firstrun']); elements['firstrun-panel'].innerHTML='FIRST RUN';}
function e10LoadSetup(){calls.push(['loader','setup']);}
function e10LoadOnboarding(){calls.push(['loader','onboarding']);}
function e10LoadDocumentScope(){calls.push(['loader','corpus-document-scope']);}
function renderScopeBannerInto(id){calls.push(['loader','scope-banner',id]);}
function e10LoadLabParticipants(){calls.push(['loader','lab-participants']);}
function e10LoadScopeSummary(){calls.push(['loader','scope-summary']);}
function e10LoadArchitect(){calls.push(['loader','architect']);}
function e10LoadLineageExplorer(){calls.push(['loader','lineage']);}
function e10LoadCriticExplorer(){calls.push(['loader','critic']);}
function e10LoadReview(){calls.push(['loader','review']);}
function e10LoadReader(){calls.push(['loader','reports']);}
function e10LoadCloseReader(){calls.push(['loader','reader']);}
function e10LoadGuide(){calls.push(['loader','guide']); elements['guide-panel'].innerHTML='GUIDE';}
function e10LoadConstitution(){calls.push(['loader','constitution']);}
"""
        + _extract_function(html, "function e10Go(")
    )


@pytest.mark.parametrize(
    "route",
    [
        "architect",
        "corpus",
        "reports",
        "reader",
        "review",
        "critic",
        "lineage",
    ],
)
def test_missing_workspace_protected_navigation_routes_to_first_run_without_loader(
    route: str,
) -> None:
    script = (
        _navigation_harness()
        + f"""
_setWorkspaceDatabaseAvailable(false);
e10Go({json.dumps(route)});
process.stdout.write(JSON.stringify({{
  firstRunHtml: elements['firstrun-panel'].innerHTML,
  loaderCalls: calls.filter(c => c[0] === 'loader'),
  allCalls: calls,
  active: screens.filter(s => s.classList.items.includes('active')).map(s => s.id),
}}));
"""
    )

    out = _run_node(script)

    assert out["loaderCalls"] == [["loader", "firstrun"]]
    assert ["refresh"] not in out["allCalls"]
    assert out["active"] == ["firstrun"]
    assert out["firstRunHtml"] == "FIRST RUN"


def test_missing_workspace_corpus_surface_is_not_interactable_after_navigation() -> None:
    script = (
        _navigation_harness()
        + """
_setWorkspaceDatabaseAvailable(false);
e10Go('corpus');
if (elements['corpus'].classList.items.includes('active')) {
  e10LoadObservations();
}
process.stdout.write(JSON.stringify({
  loaderCalls: calls.filter(c => c[0] === 'loader'),
  active: screens.filter(s => s.classList.items.includes('active')).map(s => s.id),
  corpusActive: elements['corpus'].classList.items.includes('active'),
}));
"""
    )

    out = _run_node(script)

    assert out["loaderCalls"] == [["loader", "firstrun"]]
    assert out["active"] == ["firstrun"]
    assert out["corpusActive"] is False


def test_static_guide_remains_available_before_workspace_creation() -> None:
    script = (
        _navigation_harness()
        + """
_setWorkspaceDatabaseAvailable(false);
e10Go('guide');
process.stdout.write(JSON.stringify({
  loaderCalls: calls.filter(c => c[0] === 'loader'),
  allCalls: calls,
  guideHtml: elements['guide-panel'].innerHTML,
  active: screens.filter(s => s.classList.items.includes('active')).map(s => s.id),
}));
"""
    )

    out = _run_node(script)

    assert out["loaderCalls"] == [["loader", "guide"]]
    assert ["refresh"] not in out["allCalls"]
    assert out["guideHtml"] == "GUIDE"
    assert out["active"] == ["guide"]


def test_first_run_route_does_not_refresh_cycle_status_when_workspace_is_absent() -> None:
    script = (
        _navigation_harness()
        + """
_setWorkspaceDatabaseAvailable(false);
e10Go('firstrun');
process.stdout.write(JSON.stringify({
  loaderCalls: calls.filter(c => c[0] === 'loader'),
  allCalls: calls,
  active: screens.filter(s => s.classList.items.includes('active')).map(s => s.id),
}));
"""
    )

    out = _run_node(script)

    assert out["loaderCalls"] == [["loader", "firstrun"]]
    assert ["refresh"] not in out["allCalls"]
    assert out["active"] == ["firstrun"]


def test_successful_workspace_creation_clears_navigation_guard() -> None:
    script = (
        _navigation_harness()
        + """
_setWorkspaceDatabaseAvailable(false);
_setWorkspaceDatabaseAvailable(true);
e10Go('architect');
process.stdout.write(JSON.stringify({
  loaderCalls: calls.filter(c => c[0] === 'loader'),
  allCalls: calls,
  available: _workspaceDatabaseAvailable,
  canUpload: _obCanUploadDocuments,
}));
"""
    )

    out = _run_node(script)

    assert out["loaderCalls"] == [["loader", "architect"]]
    assert ["refresh"] in out["allCalls"]
    assert out["available"] is True
    assert out["canUpload"] is True


def test_real_loader_error_is_not_rewritten_when_workspace_state_is_unknown() -> None:
    script = (
        _navigation_harness()
        + """
function e10LoadArchitect(){throw new Error('corrupt workspace diagnostic');}
let message = '';
try { e10Go('architect'); } catch (e) { message = e.message; }
process.stdout.write(JSON.stringify({
  message,
  recoveryHtml: elements['architect-panel'].innerHTML,
}));
"""
    )

    out = _run_node(script)

    assert out["message"] == "corrupt workspace diagnostic"
    assert "Workspace not created yet" not in out["recoveryHtml"]
