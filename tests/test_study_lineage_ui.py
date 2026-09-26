"""Browser-independent checks of the actual Study Lineage UI functions."""
from __future__ import annotations

import json
import re

from test_evidence_board_ui import _base_script, _extract_function, _index, _run_node


def _script(extra: str) -> str:
    source = _index()
    section = source[source.index('// Study Lineage is a read-only view'):source.index('async function _crOpenDoc(docId)')]
    signatures = re.findall(r'(?:async )?function [A-Za-z_]+\(', section)
    functions = '\n'.join(_extract_function(source, signature) for signature in signatures if '_studyLineageReset(' not in signature)
    return _base_script('''
    let _studyLineageOrder = 'oldest';
    let getCalls = [];
    let readerCalls = [];
    let providerCalls = 0;
    function _attnOpen(id, page) { readerCalls.push([id, page]); }
    function lineageHTML(graph) { return JSON.stringify(graph); }
    elements['study-lineage-context'] = makeElement();
    for (const name of ['inventory', 'lineage']) {
      elements['evidence-board-view-' + name] = makeElement();
      elements['evidence-board-view-' + name].setAttribute = function(k, v) { this[k] = v; };
    }
    const item = (table, id, time, origin = 'unknown', event = 'recorded') => ({
      record: {table, key: {id}}, record_type: table.replace(/s$/, ''), event,
      title: table + ' ' + id, content: 'Exact content\u2014not normalized.\n',
      timestamp: {field: 'created_at', value: time, status: time ? 'ordered' : 'unknown', sort_key: time},
      authorship: origin, provenance: {origin: 'as recorded'}, record_data: {id, exact: '  unchanged\n'}, contexts: [],
    });
    function install(items) {
      _evidenceBoardView = 'lineage';
      _studyLineageData = {schema: 'hermeneia.study-lineage/v1', workspace: {id: 'w', name: 'Study'}, items, coverage: {limitations: ['Overwritten history unavailable.']}};
    }
    '''.replace("'Exact content—not normalized.\n'", "'Exact content—not normalized.\\n'").replace("'  unchanged\n'", "'  unchanged\\n'") + functions + '\n' + extra)


def test_lineage_view_renders_without_mutating_inventory_scope_or_records() -> None:
    result = _run_node(_script('''
    install([item('reader_highlights', 'same', null), item('observations', 'same', '2020-01-01T00:00:00Z', 'derived')]);
    _evidenceBoardSelectedHighlightIds = new Set(['candidate']);
    _evidenceBoardAppliedScopeHighlightIds = ['applied'];
    _evidenceBoardData = {highlights: [], counts: {}};
    _crPerspectiveScope = {primary: {text: 'Human scope'}, supporting: {highlights: ['applied']}};
    const before = JSON.stringify([_studyLineageData, _evidenceBoardData, _crPerspectiveScope]);
    _studyLineageRender();
    _studyLineageFilter('authorship', 'derived');
    _studyLineageFilter('type', 'observation');
    _studyLineageFilter('order', 'newest');
    _evidenceBoardSetView('inventory');
    _evidenceBoardSetView('lineage');
    process.stdout.write(JSON.stringify({same: before === JSON.stringify([_studyLineageData, _evidenceBoardData, _crPerspectiveScope]),
      selected: [..._evidenceBoardSelectedHighlightIds], applied: _evidenceBoardAppliedScopeHighlightIds, postCalls, providerCalls,
      body: elements['evidence-board-body'].innerHTML}));
    '''))
    assert result['same'] is True
    assert result['selected'] == ['candidate']
    assert result['applied'] == ['applied']
    assert result['postCalls'] == result['providerCalls'] == 0
    assert 'href="/api/study-lineage/export"' in result['body']
    assert 'Export full lineage JSON' in result['body']
    assert 'Overwritten history unavailable.' in result['body']


def test_record_types_events_and_composite_keys_remain_distinct() -> None:
    result = _run_node(_script('''
    const a = item('reader_highlights', 'same', null, 'unknown', 'current_snapshot');
    const b = item('observations', 'same', null, 'derived');
    const c = item('proposed_interpretations', 'same', null, 'model');
    const d = {...c, event: 'decision'};
    const e = {...a, record: {table: 'supersessions', key: {old_id: 'same', new_id: 'next', reason: 'why', ratified_at: 'then'}}};
    install([a, b, c, d, e]); _studyLineageRender();
    const keys = _studyLineageData.items.map(_studyLineageKey);
    const reorderedKey = _studyLineageKey({...e, record: {table:'supersessions', key: {ratified_at:'then', reason:'why', new_id:'next', old_id:'same'}}});
    process.stdout.write(JSON.stringify({keys, reorderedKey, body: elements['evidence-board-body'].innerHTML}));
    '''))
    assert len(set(result['keys'])) == 5
    assert result['reorderedKey'] == result['keys'][-1]
    assert 'Current snapshot — earlier values are not recorded here' in result['body']
    assert 'Authorship unknown' in result['body']
    assert 'Human-authored' not in result['body'].split('<summary>')[1].split('</summary>')[0]
    assert 'Original stored record' in result['body']


def test_chronology_preserves_ties_unknown_times_and_filters_without_inferred_dates() -> None:
    result = _run_node(_script('''
    const malformed = item('inquiry_notes', 'bad', 'not a time');
    malformed.timestamp = {field: 'created_at', value: 'not a time', status: 'unorderable', sort_key: null};
    install([item('observations', 'b', '2020-01-01T00:00:00Z', 'derived'),
      item('observations', 'a', '2020-01-01T00:00:00Z', 'derived'),
      item('interpretations', 'c', '2021-01-01T00:00:00Z', 'accepted_model'),
      item('reader_highlights', 'unknown', null), malformed]);
    _studyLineageRender();
    const original = elements['evidence-board-body'].innerHTML;
    const oldest = _studyLineageVisibleItems().ordered.map(row => row.record.key.id);
    _studyLineageFilter('order', 'newest');
    const newest = _studyLineageVisibleItems().ordered.map(row => row.record.key.id);
    _studyLineageFilter('authorship', 'accepted_model');
    const accepted = _studyLineageVisibleItems().ordered.map(row => row.record.key.id);
    _studyLineageFilter('authorship', 'unknown');
    const uncertain = _studyLineageVisibleItems().uncertain.map(row => row.record.key.id);
    process.stdout.write(JSON.stringify({oldest, newest, accepted, uncertain, original}));
    '''))
    assert result['oldest'] == ['a', 'b', 'c']
    assert result['newest'] == ['c', 'a', 'b']
    assert result['accepted'] == ['c']
    assert set(result['uncertain']) == {'unknown', 'bad'}
    assert 'Same recorded time; sequence unknown' in result['original']
    assert 'created_at: not a time' in result['original']
    assert 'Time unknown' in result['original']


def test_html_and_handler_arguments_escape_untrusted_ids_content_and_metadata() -> None:
    payload = '\"\'><img src=x onerror=alert(1)>'
    result = _run_node(_script(f'''
    const hostile = {json.dumps(payload)};
    const row = item('observations', hostile, null);
    row.content = hostile; row.provenance = {{hostile}};
    row.contexts = [{{kind:'lineage', epistemic_class:'Observation', object_id:hostile}}];
    install([row]); _studyLineageRender();
    process.stdout.write(JSON.stringify({{body:elements['evidence-board-body'].innerHTML, key:_studyLineageKey(row)}}));
    '''))
    assert '<img' not in result['body']
    assert '&lt;img' in result['body']
    assert payload in result['key']
    assert 'onclick="_studyLineageOpenContext(&quot;' in result['body']


def test_context_opens_only_exact_typed_durable_target_using_get() -> None:
    result = _run_node(_script('''
    async function get(url) { getCalls.push(url); return {root: {class:'Observation', id:'same /?#'}}; }
    const a = item('observations', 'same /?#', null);
    a.contexts = [{kind:'lineage', epistemic_class:'Observation', object_id:'same /?#'}];
    const b = item('reader_highlights', 'same /?#', null);
    b.contexts = [{kind:'reader', document_id:'real-doc', page:7, highlight_id:'same /?#'}];
    install([b, a]);
    (async () => {
      await _studyLineageOpenContext(_studyLineageKey(a), _studyLineageContextKey(a.contexts[0]));
      await _studyLineageOpenContext(_studyLineageKey(b), _studyLineageContextKey(b.contexts[0]));
      await _studyLineageOpenContext(_studyLineageKey(b), _studyLineageContextKey(a.contexts[0]));
      process.stdout.write(JSON.stringify({getCalls, readerCalls, postCalls}));
    })().catch(e => {console.error(e);process.exit(1)});
    '''))
    assert result['getCalls'] == ['/api/lineage/Observation/same%20%2F%3F%23']
    assert result['readerCalls'] == [['real-doc', 7]]
    assert result['postCalls'] == 0


def test_old_workspace_response_cannot_repopulate_lineage_after_reset() -> None:
    result = _run_node(_script('''
    let finish;
    async function get(url) { getCalls.push(url); return new Promise(resolve => {finish = resolve}); }
    _evidenceBoardView = 'lineage';
    const loading = _studyLineageLoad();
    _crResetEvidenceBoardForReaderContextChange();
    finish({schema:'hermeneia.study-lineage/v1', items:[item('observations','old',null)]});
    loading.then(() => process.stdout.write(JSON.stringify({data:_studyLineageData, body:elements['evidence-board-body'].innerHTML, getCalls, postCalls})));
    '''))
    assert result['data'] is None
    assert 'Reader context changed' in result['body']
    assert result['getCalls'] == ['/api/study-lineage']
    assert result['postCalls'] == 0


def test_workspace_reset_clears_filters_that_could_hide_the_new_study() -> None:
    result = _run_node(_script('''
    install([item('blueprints', 'old-study', null, 'human')]);
    _studyLineageFilter('type', 'blueprint');
    _studyLineageFilter('authorship', 'human');
    _studyLineageFilter('order', 'newest');
    _crResetEvidenceBoardForReaderContextChange();
    install([item('observations', 'new-study', null, 'derived')]);
    _studyLineageRender();
    process.stdout.write(JSON.stringify({type:_studyLineageType, authorship:_studyLineageAuthorship,
      order:_studyLineageOrder, ids:_studyLineageVisibleItems().uncertain.map(row=>row.record.key.id),
      body:elements['evidence-board-body'].innerHTML, postCalls}));
    '''))
    assert result['type'] == result['authorship'] == ''
    assert result['order'] == 'newest'
    assert result['ids'] == ['new-study']
    assert '<option value="" selected>All record types</option>' in result['body']
    assert '<option value="" selected>All recorded origins</option>' in result['body']
    assert result['postCalls'] == 0


def test_latest_load_wins_and_switching_inventory_does_not_render_lineage_response() -> None:
    result = _run_node(_script('''
    const pending = [];
    async function get() { return new Promise(resolve => pending.push(resolve)); }
    _evidenceBoardView = 'lineage';
    const first = _studyLineageLoad(); const second = _studyLineageLoad();
    pending[1]({schema:'hermeneia.study-lineage/v1',items:[item('observations','new',null)]});
    second.then(async () => {
      _evidenceBoardData = {highlights:[], counts:{}};
      await _evidenceBoardSetView('inventory');
      pending[0]({schema:'hermeneia.study-lineage/v1',items:[item('observations','old',null)]});
      await first;
      process.stdout.write(JSON.stringify({ids:_studyLineageData.items.map(row=>row.record.key.id), body:elements['evidence-board-body'].innerHTML}));
    });
    '''))
    assert result['ids'] == ['new']
    assert 'What has this study accumulated?' in result['body']
    assert 'Study Lineage shows' not in result['body']


def test_object_context_response_is_discarded_after_workspace_reset() -> None:
    result = _run_node(_script('''
    let finish;
    async function get() { return new Promise(resolve => {finish = resolve}); }
    const row = item('observations','id',null);
    row.contexts = [{kind:'lineage',epistemic_class:'Observation',object_id:'id'}];
    install([row]);
    const loading = _studyLineageOpenContext(_studyLineageKey(row), _studyLineageContextKey(row.contexts[0]));
    _crResetEvidenceBoardForReaderContextChange();
    finish({private:'old workspace graph'});
    loading.then(() => process.stdout.write(JSON.stringify({panel:elements['study-lineage-context'].innerHTML})));
    '''))
    assert 'old workspace graph' not in result['panel']


def test_lineage_bounds_dom_size_and_preserves_all_items_for_export() -> None:
    result = _run_node(_script('''
    install(Array.from({length:205}, (_, i) => item('observations', String(i).padStart(3,'0'), null)));
    _studyLineageRender(); const first = elements['evidence-board-body'].innerHTML;
    _studyLineageChangePage(1); const second = elements['evidence-board-body'].innerHTML;
    _studyLineageChangePage(100); const last = elements['evidence-board-body'].innerHTML;
    process.stdout.write(JSON.stringify({first, second, last, count:_studyLineageData.items.length}));
    '''))
    assert result['first'].count('data-study-lineage-key=') == 100
    assert result['second'].count('data-study-lineage-key=') == 100
    assert result['last'].count('data-study-lineage-key=') == 5
    assert result['count'] == 205
    assert 'Page 3 of 3' in result['last']


def test_stale_inventory_load_cannot_clear_selection_while_lineage_is_open() -> None:
    result = _run_node(_script('''
    let finish;
    async function get() { return new Promise(resolve => {finish = resolve}); }
    _evidenceBoardSelectedHighlightIds = new Set(['retain-candidate']);
    _evidenceBoardAppliedScopeHighlightIds = ['retain-applied'];
    const loading = _evidenceBoardLoad();
    install([item('observations','lineage-item',null)]);
    _studyLineageRender();
    finish({highlights:[]});
    loading.then(() => process.stdout.write(JSON.stringify({
      selected:[..._evidenceBoardSelectedHighlightIds], applied:_evidenceBoardAppliedScopeHighlightIds,
      body:elements['evidence-board-body'].innerHTML
    })));
    '''))
    assert result['selected'] == ['retain-candidate']
    assert result['applied'] == ['retain-applied']
    assert 'Study Lineage shows' in result['body']


def test_unsupported_projection_version_refuses_to_render_and_clears_old_data() -> None:
    result = _run_node(_script('''
    async function get() {return {schema:'hermeneia.study-lineage/v99',items:[]};}
    install([item('observations','previous',null)]);
    _studyLineageLoad().then(() => process.stdout.write(JSON.stringify({
      data:_studyLineageData,body:elements['evidence-board-body'].innerHTML
    })));
    '''))
    assert result['data'] is None
    assert 'Unsupported study lineage projection.' in result['body']


def test_lineage_has_no_write_or_provider_routes_and_is_board_subview() -> None:
    source = _index()
    section = source[source.index('// Study Lineage is a read-only view'):source.index('async function _crOpenDoc(docId)')]
    assert not re.search(r'\b(post|put|del|fetch|runtimeApiFetch)\s*\(', section)
    assert '/api/perspective' not in section
    assert 'id="evidence-board-view-lineage"' in source
    assert "_evidenceBoardSetView('lineage')" in source
