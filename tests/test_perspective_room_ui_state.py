"""Selectable Ask-the-Room roster transient UI state."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


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


def _room_ui_js() -> str:
    source = _index()
    signatures = [
        "function _wsApplyCurrentWorkspace(",
        "function _wsWorkspaceMatches(",
        "function _crPopulateSavedPerspectiveSelect(",
        "function _crResetPerspectiveRoomStateForWorkspaceChange(",
        "function _crRoomParticipantId(",
        "function _crRoomParticipantLabel(",
        "function _crRoomParticipantTitle(",
        "function _crRoomDefaultRoster(",
        "function _crRoomResetDefaultRoster(",
        "function _crReconcilePerspectiveRoomRosterMetadata(",
        "function _crRoomSavedChoices(",
        "function _crRoomBuiltInChoice(",
        "function _crRoomSavedChoice(",
        "function _crRenderRoomAddChoices(",
        "function _crRenderPerspectiveRoomPlan(",
    ]
    return "\n".join(_extract_function(source, signature) for signature in signatures)


def _node_base() -> str:
    return f"""
    function makeElement(hidden = false) {{
      return {{
        hidden,
        checked: false,
        value: '',
        innerHTML: '',
        textContent: '',
        dataset: {{}},
        title: '',
        attrs: {{}},
        setAttribute(k, v) {{ this.attrs[k] = String(v); }},
      }};
    }}
    const elements = {{
      'runtime-workspace-chip': makeElement(true),
      'runtime-workspace-name': makeElement(false),
      'cr-perspective-room-plan': makeElement(false),
      'cr-perspective-room-add-select': makeElement(false),
      'cr-perspective-room-add-kind': makeElement(false),
      'cr-perspective-room-show-historical': makeElement(false),
      'cr-perspective-saved-select': makeElement(false),
      'cr-perspective-saved-detail': makeElement(false),
    }};
    const document = {{ getElementById(id) {{ return elements[id] || null; }} }};
    function x(value) {{
      return String(value ?? '').replace(/[&<>"']/g, ch => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
      }}[ch]));
    }}
    function _runtimeApplyWorkspaceDraftScope() {{}}
    function _wsRenderWorkspaceCatalog() {{}}
    function _crRenderSavedPerspectiveDetail() {{}}
    function showAppError(message) {{ globalThis.lastAppError = message; }}
    let _wsCurrentWorkspace = null;
    let _crPerspectiveDefinitions = [];
    let _crPerspectiveRoomDefinitions = [];
    let _crPerspectiveRoomRoster = [];
    let _crPerspectiveRoomRosterDirty = false;
    let _crPerspectiveSavedDefinitions = [];
    {_room_ui_js()}
    """


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Perspective Room UI tests")
    result = subprocess.run(
        [node, "-e", _node_base() + script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_custom_room_roster_clears_only_on_workspace_identity_change() -> None:
    result = _run_node(
        r"""
        const a = { id:'workspace-a', slug:'gatsby', kind:'managed', name:'Gatsby' };
        const sameA = { id:'workspace-a', slug:'gatsby-renamed', kind:'managed', name:'Gatsby renamed' };
        const b = { id:'workspace-b', slug:'second-sale', kind:'managed', name:'The Second Sale' };
        _wsApplyCurrentWorkspace(a);
        _crPerspectiveRoomRoster = [
          {kind:'built_in', perspective_id:'close-reader', label:'Close Reader'},
          {kind:'built_in', perspective_id:'skeptical-reader', label:'Skeptical Reader'},
        ];
        _crPerspectiveRoomRosterDirty = true;
        _wsApplyCurrentWorkspace(sameA);
        const sameWorkspace = {
          length: _crPerspectiveRoomRoster.length,
          dirty: _crPerspectiveRoomRosterDirty,
        };
        _wsApplyCurrentWorkspace(b);
        process.stdout.write(JSON.stringify({
          sameWorkspace,
          changedLength: _crPerspectiveRoomRoster.length,
          changedDirty: _crPerspectiveRoomRosterDirty,
        }));
        """
    )

    assert result == {
        "sameWorkspace": {"length": 2, "dirty": True},
        "changedLength": 0,
        "changedDirty": False,
    }


def test_saved_room_chair_metadata_refreshes_without_successor_substitution() -> None:
    result = _run_node(
        r"""
        _crPerspectiveDefinitions = [
          {id:'close-reader', label:'Close Reader', version:'1'},
          {id:'skeptical-reader', label:'Skeptical Reader', version:'1'},
        ];
        _crPerspectiveSavedDefinitions = [
          {
            id:'perspective-frame-v2:p1',
            identity_scheme:'perspective-frame-v2',
            label:'Trust Reader',
            is_current_leaf:true,
            definition_fingerprint:'sha256:old',
            declared_by:'Primary Human Steward',
            declared_date:'2026-08-27T12:00:00+00:00',
          },
        ];
        _crPerspectiveRoomRoster = [
          {kind:'built_in', perspective_id:'skeptical-reader', label:'Old Skeptical Label', version:'old'},
          {kind:'saved', perspective_id:'perspective-frame-v2:p1', label:'Trust Reader', is_current_leaf:true, definition_fingerprint:'sha256:old'},
        ];
        _crPerspectiveRoomRosterDirty = true;
        _crPerspectiveSavedDefinitions = [
          {
            id:'perspective-frame-v2:p2',
            identity_scheme:'perspective-frame-v2',
            label:'Trust Reader',
            is_current_leaf:true,
            definition_fingerprint:'sha256:new',
            declared_by:'Primary Human Steward',
            declared_date:'2026-08-27T12:30:00+00:00',
          },
          {
            id:'perspective-frame-v2:p1',
            identity_scheme:'perspective-frame-v2',
            label:'Trust Reader',
            is_current_leaf:false,
            definition_fingerprint:'sha256:old',
            declared_by:'Primary Human Steward',
            declared_date:'2026-08-27T12:00:00+00:00',
          },
        ];
        _crReconcilePerspectiveRoomRosterMetadata();
        process.stdout.write(JSON.stringify({
          ids: _crPerspectiveRoomRoster.map(item => item.perspective_id),
          labels: _crPerspectiveRoomRoster.map(item => item.label),
          currentFlags: _crPerspectiveRoomRoster.map(item => item.is_current_leaf ?? null),
          fingerprints: _crPerspectiveRoomRoster.map(item => item.definition_fingerprint || ''),
          dirty: _crPerspectiveRoomRosterDirty,
        }));
        """
    )

    assert result["ids"] == ["skeptical-reader", "perspective-frame-v2:p1"]
    assert result["labels"] == ["Skeptical Reader", "Trust Reader"]
    assert result["currentFlags"] == [None, False]
    assert result["fingerprints"] == ["", "sha256:old"]
    assert result["dirty"] is True


def test_room_renderer_preserves_show_historical_filter_across_rerender() -> None:
    result = _run_node(
        r"""
        _crPerspectiveDefinitions = [
          {id:'close-reader', label:'Close Reader', version:'1'},
          {id:'skeptical-reader', label:'Skeptical Reader', version:'1'},
        ];
        _crPerspectiveRoomDefinitions = _crPerspectiveDefinitions;
        elements['cr-perspective-room-add-kind'].value = 'saved';
        elements['cr-perspective-room-show-historical'].checked = true;
        _crPerspectiveSavedDefinitions = [{
          id:'perspective-frame-v2:old',
          identity_scheme:'perspective-frame-v2',
          label:'Historical Reader',
          is_current_leaf:false,
          definition_fingerprint:'sha256:old',
        }];
        _crRoomResetDefaultRoster();
        _crPerspectiveRoomRosterDirty = true;
        _crRenderPerspectiveRoomPlan();
        process.stdout.write(JSON.stringify({
          checked: elements['cr-perspective-room-show-historical'].checked,
          addOptions: elements['cr-perspective-room-add-select'].innerHTML,
        }));
        """
    )

    assert result["checked"] is True
    assert "Historical Reader" in result["addOptions"]
