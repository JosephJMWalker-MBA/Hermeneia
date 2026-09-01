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
    brace = source.index("{", source.index(")", start))
    depth = 0
    i = brace
    quote: str | None = None
    escaped = False
    while i < len(source):
        ch = source[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces extracting {signature!r}")


def _evidence_board_js() -> str:
    source = _index()
    signatures = [
        "function _crResetEvidenceBoardForReaderContextChange(",
        "async function _evidenceBoardLoad(",
        "function _evidenceBoardCountsHtml(",
        "function _evidenceBoardNormalizeBucketValue(",
        "function _evidenceBoardBucketButton(",
        "function _evidenceBoardOpenBucket(",
        "function _evidenceBoardClearBucket(",
        "function _evidenceBoardVisibleHighlights(",
        "function _evidenceBoardHighlightById(",
        "function _evidenceBoardToggleHighlight(",
        "function _evidenceBoardClearSelection(",
        "function _evidenceBoardSelectedIds(",
        "function _evidenceBoardScopeHighlightsPayload(",
        "function _evidenceBoardAppliedHighlightsPayload(",
        "function _evidenceBoardApplySelectionToScope(",
        "function _evidenceBoardHighlightRow(",
        "function _evidenceBoardFieldNoteRow(",
        "function _evidenceBoardObservationRow(",
        "function _evidenceBoardRender(",
        "function _crPerspectiveCurrentPageScope(",
        "function _crPerspectiveScopeFromSelection(",
        "function _crPerspectiveSyncScopeControls(",
        "function _crPerspectiveRenderScope(",
    ]
    return "\n".join(_extract_function(source, signature) for signature in signatures)


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Evidence Board UI tests")
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _base_script(extra: str) -> str:
    return f"""
    function makeElement() {{
      return {{
        innerHTML: '',
        textContent: '',
        hidden: false,
        checked: false,
        disabled: false,
        value: '',
        dataset: {{}},
        classList: {{ toggle() {{}} }},
      }};
    }}
    const elements = {{
      'evidence-board-body': makeElement(),
      'evidence-board-meta': makeElement(),
      'cr-perspective-scope-chip': makeElement(),
      'cr-perspective-include-governing': makeElement(),
      'cr-perspective-governing-state': makeElement(),
      'cr-perspective-include-page': makeElement(),
      'cr-perspective-page-state': makeElement(),
    }};
    const document = {{
      getElementById(id) {{ return elements[id] || null; }},
      querySelectorAll() {{ return []; }},
    }};
    function x(value) {{
      return String(value ?? '').replace(/[&<>"']/g, ch => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
      }}[ch]));
    }}
    function showAppError(message) {{ globalThis.lastAppError = message; }}
    let postCalls = 0;
    async function post() {{ postCalls += 1; return {{}}; }}
    let _crBottomMode = 'evidence';
    let _crDocId = 'doc-a';
    let _crPage = 2;
    let _crCurrentExtractions = [];
    let _crPerspectiveWorkspaceEpoch = 0;
    let _crPerspectiveScope = null;
    let _evidenceBoardData = null;
    let _evidenceBoardSelectedHighlightIds = new Set();
    let _evidenceBoardSelectionDocId = '';
    let _evidenceBoardAppliedScopeHighlightIds = [];
    let _evidenceBoardAppliedScopeDocId = '';
    let _evidenceBoardActiveBucket = null;
    let _evidenceBoardLoadSeq = 0;
    let _evidenceBoardEpoch = 0;
    function _crReaderBlockContext() {{ return {{ source_locators: [], extraction_ids: [] }}; }}
    function _crUniqueStringList(values) {{ return Array.from(new Set((values || []).filter(Boolean))); }}
    function _crGetReaderSelection() {{
      return {{
        valid: true,
        text: 'Primary selected passage.',
        source_document_id: 'doc-a',
        page: 2,
        source_locators: ['page:2:block:1'],
        extraction_ids: ['ex-a-1'],
      }};
    }}
    function _crEncodeReaderSpanLocator() {{ return 'reader-span:v1:test'; }}
    {_evidence_board_js()}
    {extra}
    """


def test_evidence_board_selection_is_transient_and_sets_exact_scope_ids() -> None:
    result = _run_node(
        _base_script(
            """
            _evidenceBoardData = {
              counts: {highlights: 3, field_notes: 0, observations: 0, question_bearing_records: 0, theme_buckets: 1, evidence_buckets: 1, uncategorized_highlights: 0},
              theme_buckets: [{bucket: 'theme-a', kind: 'theme_bucket', count: 2, highlight_ids: ['hl-a', 'hl-b']}],
              evidence_buckets: [],
              highlights: [
                {id: 'hl-a', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'A', relevance: 'supports', theme_bucket: 'theme-a', status: 'saved_highlight'},
                {id: 'hl-b', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'B', relevance: 'unclear', theme_bucket: 'theme-a', status: 'saved_highlight'},
                {id: 'hl-c', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'C', relevance: 'complicates', theme_bucket: 'theme-c', status: 'saved_highlight'},
              ],
              field_notes: [],
              observations: [],
            };
            _evidenceBoardRender();
            _evidenceBoardToggleHighlight('hl-b');
            _evidenceBoardToggleHighlight('hl-a');
            const selectedBeforeApply = _evidenceBoardSelectedIds();
            const freshScopeBeforeApply = _crPerspectiveScopeFromSelection();
            _evidenceBoardApplySelectionToScope();
            const scopeIds = _crPerspectiveScope.supporting.highlights.ids;
            const included = _crPerspectiveScope.included.highlights;
            _evidenceBoardClearSelection();
            _evidenceBoardToggleHighlight('hl-c');
            const scopeIdsAfterSelectionChange = _crPerspectiveScope.supporting.highlights.ids;
            _evidenceBoardApplySelectionToScope();
            const scopeIdsAfterSecondApply = _crPerspectiveScope.supporting.highlights.ids;
            _evidenceBoardClearSelection();
            process.stdout.write(JSON.stringify({
              selectedBeforeApply,
              freshScopeHighlightsBeforeApply: freshScopeBeforeApply.supporting.highlights,
              scopeIds,
              included,
              scopeIdsAfterSelectionChange,
              scopeIdsAfterSecondApply,
              selectedAfterClear: _evidenceBoardSelectedIds(),
              postCalls,
              chip: elements['cr-perspective-scope-chip'].innerHTML,
            }));
            """
        )
    )

    assert result["selectedBeforeApply"] == ["hl-a", "hl-b"]
    assert result["freshScopeHighlightsBeforeApply"] == {"include": False, "ids": []}
    assert result["scopeIds"] == ["hl-a", "hl-b"]
    assert result["included"] is True
    assert result["scopeIdsAfterSelectionChange"] == ["hl-a", "hl-b"]
    assert result["scopeIdsAfterSecondApply"] == ["hl-c"]
    assert result["selectedAfterClear"] == []
    assert result["postCalls"] == 0
    assert "1 Reader highlight" in result["chip"]


def test_evidence_board_cross_document_highlight_cannot_enter_current_scope() -> None:
    result = _run_node(
        _base_script(
            """
            _evidenceBoardData = {
              counts: {},
              theme_buckets: [],
              evidence_buckets: [],
              highlights: [
                {id: 'hl-cross', source_document_id: 'doc-b', scope_eligible: false, scope_ineligibility_reason: 'Different source document; not eligible for current single-document Scope.', selected_text: 'X'},
              ],
              field_notes: [],
              observations: [],
            };
            _evidenceBoardToggleHighlight('hl-cross');
            process.stdout.write(JSON.stringify({
              selected: _evidenceBoardSelectedIds(),
              error: globalThis.lastAppError || '',
              postCalls,
            }));
            """
        )
    )

    assert result["selected"] == []
    assert "Different source document" in result["error"]
    assert result["postCalls"] == 0


def test_evidence_board_bucket_filter_does_not_change_current_scope() -> None:
    result = _run_node(
        _base_script(
            """
            _evidenceBoardData = {
              counts: {},
              theme_buckets: [{bucket: 'theme-a', count: 1}, {bucket: 'theme-b', count: 1}],
              evidence_buckets: [],
              highlights: [
                {id: 'hl-a', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'A', theme_bucket: ' theme-a '},
                {id: 'hl-b', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'B', theme_bucket: 'theme-b'},
              ],
              field_notes: [],
              observations: [],
            };
            _crPerspectiveScope = { primary: { text: 'Primary', source_document_id: 'doc-a' }, supporting: {}, included: {} };
            _evidenceBoardOpenBucket('theme_bucket', 'theme-a');
            const visible = _evidenceBoardVisibleHighlights().map(row => row.id);
            process.stdout.write(JSON.stringify({
              visible,
              scopeHighlights: _crPerspectiveScope.supporting.highlights || null,
              selected: _evidenceBoardSelectedIds(),
              postCalls,
            }));
            """
        )
    )

    assert result["visible"] == ["hl-a"]
    assert result["scopeHighlights"] is None
    assert result["selected"] == []
    assert result["postCalls"] == 0


def test_evidence_board_unselecting_after_apply_does_not_mutate_scope() -> None:
    result = _run_node(
        _base_script(
            """
            _evidenceBoardData = {
              counts: {},
              theme_buckets: [],
              evidence_buckets: [],
              highlights: [
                {id: 'hl-a', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'A'},
                {id: 'hl-b', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'B'},
              ],
              field_notes: [],
              observations: [],
            };
            _evidenceBoardToggleHighlight('hl-a');
            _evidenceBoardToggleHighlight('hl-b');
            _evidenceBoardApplySelectionToScope();
            _evidenceBoardToggleHighlight('hl-a');
            _evidenceBoardClearSelection();
            process.stdout.write(JSON.stringify({
              selected: _evidenceBoardSelectedIds(),
              scopeIds: _crPerspectiveScope.supporting.highlights.ids,
              appliedIds: _evidenceBoardAppliedScopeHighlightIds,
              appliedDoc: _evidenceBoardAppliedScopeDocId,
            }));
            """
        )
    )

    assert result["selected"] == []
    assert result["scopeIds"] == ["hl-a", "hl-b"]
    assert result["appliedIds"] == ["hl-a", "hl-b"]
    assert result["appliedDoc"] == "doc-a"


def test_evidence_board_context_reset_invalidates_selection() -> None:
    result = _run_node(
        _base_script(
            """
            _evidenceBoardData = {
              highlights: [{id: 'hl-a', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'A'}],
              field_notes: [],
              observations: [],
            };
            _evidenceBoardToggleHighlight('hl-a');
            _crResetEvidenceBoardForReaderContextChange();
            process.stdout.write(JSON.stringify({
              selected: _evidenceBoardSelectedIds(),
              data: _evidenceBoardData,
              body: elements['evidence-board-body'].innerHTML,
            }));
            """
        )
    )

    assert result["selected"] == []
    assert result["data"] is None
    assert "Reader context changed" in result["body"]


def test_evidence_board_copy_does_not_claim_field_note_authorship_or_collected_observations() -> None:
    result = _run_node(
        _base_script(
            """
            _evidenceBoardData = {
              counts: {highlights: 0, field_notes: 1, observations: 1, question_bearing_records: 1},
              theme_buckets: [],
              evidence_buckets: [],
              highlights: [],
              field_notes: [
                {id: 'fn-a', lane: 'corpus', understanding: 'A study note.', origin_status: 'not_recorded'},
              ],
              observations: [
                {id: 'obs-a', content: 'Canonical observation.', review_status: 'approved', epistemic_status: 'canonical source-derived observation'},
              ],
            };
            _evidenceBoardRender();
            process.stdout.write(JSON.stringify({ body: elements['evidence-board-body'].innerHTML }));
            """
        )
    )

    assert "Question-bearing records" in result["body"]
    assert "origin not recorded" in result["body"]
    assert "human-authored field note" not in result["body"]
    assert "What have I actually collected" not in result["body"]
    assert "canonical observations are source-derived evidence available to the study" in result["body"]


def test_stale_evidence_board_load_cannot_overwrite_newer_context() -> None:
    result = _run_node(
        _base_script(
            """
            let resolveLoad;
            async function get() {
              return new Promise(resolve => { resolveLoad = resolve; });
            }
            const running = _evidenceBoardLoad();
            _crResetEvidenceBoardForReaderContextChange();
            resolveLoad({
              counts: {highlights: 1},
              highlights: [{id: 'old', source_document_id: 'doc-a', scope_eligible: true, selected_text: 'Old'}],
              field_notes: [],
              observations: [],
            });
            running.then(() => {
              process.stdout.write(JSON.stringify({
                data: _evidenceBoardData,
                body: elements['evidence-board-body'].innerHTML,
                selected: _evidenceBoardSelectedIds(),
              }));
            }).catch(error => {
              console.error(error && error.stack ? error.stack : error);
              process.exit(1);
            });
            """
        )
    )

    assert result["data"] is None
    assert "Reader context changed" in result["body"]
    assert result["selected"] == []
