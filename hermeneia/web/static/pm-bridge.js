/* PM human-attention bridge — Reader surface (bridge-local, experimental).
 *
 * Authority: docs/integrations/performance-manuscript-human-attention-bridge.md.
 * Reading stays primary: an "Annotate" intent on the selection toolbar opens a compact
 * panel; nothing navigates away. While a human-gold pass is open, machine surfaces
 * (Companion, Ask, Perspective runs, the machine-observation lens and panel) are hidden
 * here and model execution is refused by the server. Every field is optional.
 *
 * The bridge UI appears when a pass exists or after opening the Reader once with
 * ?pm-bridge=1 (remembered in this browser).
 */
(function () {
  'use strict';

  const FORMS = ['spoken-dialogue', 'direct-thought', 'character-authored-text', 'embedded-quoted-text',
    'narrator-prose', 'structural-or-metadata', 'other'];
  const SOURCES = ['roster-member', 'named-person-missing-from-roster', 'descriptive-non-roster-source',
    'narrator', 'structural', 'unresolved'];
  const LABEL = {
    'spoken-dialogue': 'Spoken dialogue', 'direct-thought': 'Direct thought',
    'character-authored-text': 'Character-authored text', 'embedded-quoted-text': 'Embedded quotation',
    'narrator-prose': 'Narrator prose', 'structural-or-metadata': 'Structural / metadata', other: 'Other',
    'roster-member': 'Canonical character', 'named-person-missing-from-roster': 'Named person, not in roster',
    'descriptive-non-roster-source': 'Descriptive / unnamed source', narrator: 'Narrator',
    structural: 'Structural', unresolved: 'Unresolved',
  };

  const PM = { passes: [], open: null, enabled: false, pointer: 'keyboard', annotations: [] };

  try {
    if (new URLSearchParams(location.search).get('pm-bridge') === '1') localStorage.setItem('hermeneia_pm_bridge', '1');
    PM.enabled = localStorage.getItem('hermeneia_pm_bridge') === '1';
  } catch (e) { /* storage unavailable: the bridge still shows once a pass exists */ }

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const docId = () => (typeof _crDocId !== 'undefined' ? _crDocId : null);

  document.addEventListener('pointerdown', e => {
    PM.pointer = (e.pointerType === 'touch' || e.pointerType === 'pen') ? 'touch' : 'keyboard';
  }, true);
  function deviceClass() {
    const touch = (navigator.maxTouchPoints || 0) > 0;
    if (!touch) return 'desktop';
    return Math.min(screen.width || 0, screen.height || 0) < 600 ? 'phone' : 'tablet';
  }

  window._pmGoldOpen = () => !!PM.open;

  function passForDoc(id) {
    const mine = PM.passes.filter(p => p.source_document_id === id);
    return mine.find(p => p.status === 'GOLD_OPEN') || mine[mine.length - 1] || null;
  }

  async function load() {
    try {
      const r = await fetch('/api/bridge/pm/gold-passes');
      const data = await r.json();
      PM.passes = data.passes || [];
      PM.open = data.open || null;
      if (PM.passes.length) PM.enabled = true;
    } catch (e) { PM.passes = []; PM.open = null; }
    document.body.classList.toggle('pm-gold-open', !!PM.open);
    if (typeof _crApplyLens === 'function') { try { _crApplyLens(); } catch (e) { /* page not rendered yet */ } }
    renderSlot();
    syncToolbar();
  }

  // ── Header slot: pass state, open / seal ─────────────────────────────────
  function renderSlot() {
    const head = document.querySelector('#cr-page-view .cr-page-header');
    if (!head) return;
    let slot = head.querySelector('.pm-gold-slot');
    if (!slot) { slot = document.createElement('div'); slot.className = 'pm-gold-slot'; head.appendChild(slot); }
    if (!PM.enabled || !docId()) { slot.innerHTML = ''; return; }
    const p = passForDoc(docId());
    if (PM.open && PM.open.source_document_id !== docId()) {
      slot.innerHTML = '<span class="pm-chip pm-chip-open">Human-gold pass open on another document</span>';
    } else if (p && p.status === 'GOLD_OPEN') {
      slot.innerHTML = '<span class="pm-chip pm-chip-open" title="Machine proposals, confidence and model execution are off until you seal this pass">Human-gold pass open</span>'
        + '<button type="button" class="pm-btn" onclick="_pmSealPass()">Seal pass…</button>';
    } else if (p) {
      slot.innerHTML = `<span class="pm-chip">Human-gold pass sealed ${esc((p.seal && p.seal.at || '').slice(0, 10))}</span>`;
    } else if (!PM.open) {
      slot.innerHTML = '<button type="button" class="pm-btn" onclick="_pmOpenPass()">Open human-gold pass</button>';
    } else {
      slot.innerHTML = '';
    }
  }

  window._pmOpenPass = async function () {
    const ok = confirm('Open a human-gold pass on this document?\n\n'
      + '• Machine proposals, confidence, Companion and Perspective runs are hidden.\n'
      + '• All model execution in this workspace is refused, local models included.\n'
      + '• It stays open until you seal it; sealing cannot be undone.\n\n'
      + 'Use a dedicated workspace in which no model has produced output.');
    if (!ok) return;
    try {
      await requestJSON('/api/bridge/pm/gold-passes', { method: 'POST', body: { source_document_id: docId() } });
    } catch (e) { return; }
    await load();
  };

  window._pmSealPass = async function () {
    if (!PM.open) return;
    const typed = prompt('Seal this human-gold pass? After sealing, no new first-pass gold can be added to it; '
      + 'later changes are recorded as revisions, and machine-assisted work may follow.\n\nType SEAL to confirm.');
    if ((typed || '').trim().toUpperCase() !== 'SEAL') return;
    try {
      await requestJSON(`/api/bridge/pm/gold-passes/${encodeURIComponent(PM.open.gold_pass_id)}/seal`,
        { method: 'POST', body: { confirm: 'seal' } });
    } catch (e) { return; }
    await load();
  };

  // ── Selection toolbar ────────────────────────────────────────────────────
  function syncToolbar() {
    const btn = document.querySelector('#cr-sel-toolbar .pm-annotate-btn');
    if (btn) btn.hidden = !(PM.enabled && docId());
  }

  const select = (id, values, cur) => `<select id="${id}" class="pm-input"><option value="">—</option>${values.map(v =>
    `<option value="${v}"${v === cur ? ' selected' : ''}>${esc(LABEL[v] || v)}</option>`).join('')}</select>`;
  const input = (id, label, val, ph) => `<label class="pm-field"><span>${label}</span><input id="${id}" class="pm-input" value="${esc(val || '')}" placeholder="${esc(ph || '')}"></label>`;

  function panelHtml(j, title, saveLabel, onSave) {
    j = j || {};
    const perf = j.performance || {}, unc = j.uncertainty || {};
    const list = v => (v || []).join('; ');
    return `
      <div class="pm-panel" role="form" aria-label="${esc(title)}">
        <div class="pm-panel-title">${esc(title)}${PM.open ? ' <span class="pm-chip pm-chip-open">blind</span>' : ''}</div>
        <div class="pm-help">Fill only what you noticed. Every field is optional.</div>
        <div class="pm-grid">
          <label class="pm-field"><span>Textual form</span>${select('pm-form', FORMS, j.target_form)}</label>
          <label class="pm-field"><span>Source / voice</span>${select('pm-source', SOURCES, j.source_class)}</label>
        </div>
        ${input('pm-identity', 'Who / what (name or description)', j.source_identity, 'e.g. Simone, or “the man at the gate”')}
        ${input('pm-pov', 'Point of view (narrative)', j.point_of_view, '')}
        <details class="pm-details"${(perf.tone || perf.pace || perf.intensity || list(perf.emphasis) || list(perf.pauses) || list(perf.pronunciation)) ? ' open' : ''}>
          <summary>Performance</summary>
          <div class="pm-grid">
            ${input('pm-tone', 'Tone', perf.tone)}${input('pm-pace', 'Pace', perf.pace)}
          </div>
          ${input('pm-intensity', 'Intensity', perf.intensity)}
          ${input('pm-emphasis', 'Emphasis (separate with ;)', list(perf.emphasis))}
          ${input('pm-pauses', 'Pauses (separate with ;)', list(perf.pauses))}
          ${input('pm-pron', 'Pronunciation (separate with ;)', list(perf.pronunciation))}
        </details>
        <label class="pm-check"><input type="checkbox" id="pm-unresolved"${unc.unresolved ? ' checked' : ''}> Unresolved — I can’t decide from what is shown</label>
        ${input('pm-unc-note', 'What is missing or conflicting', unc.note)}
        <label class="pm-field"><span>Note (proofreading / editorial)</span><textarea id="pm-note" class="pm-input" rows="2">${esc(j.note || '')}</textarea></label>
        <div class="pm-actions">
          <button type="button" class="btn-primary pm-save" onclick="${onSave}">${esc(saveLabel)}</button>
          <button type="button" class="cr-capture-cancel" onclick="_pmCancel()">Cancel</button>
        </div>
        <div id="pm-msg" class="pm-msg" aria-live="polite"></div>
      </div>`;
  }

  function readJudgment() {
    const v = id => (document.getElementById(id)?.value || '').trim();
    const items = id => v(id).split(';').map(s => s.trim()).filter(Boolean);
    const j = {};
    if (v('pm-form')) j.target_form = v('pm-form');
    if (v('pm-source')) j.source_class = v('pm-source');
    if (v('pm-identity')) j.source_identity = v('pm-identity');
    if (v('pm-pov')) j.point_of_view = v('pm-pov');
    const perf = {};
    if (v('pm-tone')) perf.tone = v('pm-tone');
    if (v('pm-pace')) perf.pace = v('pm-pace');
    if (v('pm-intensity')) perf.intensity = v('pm-intensity');
    if (items('pm-emphasis').length) perf.emphasis = items('pm-emphasis');
    if (items('pm-pauses').length) perf.pauses = items('pm-pauses');
    if (items('pm-pron').length) perf.pronunciation = items('pm-pron');
    if (Object.keys(perf).length) j.performance = perf;
    const unresolved = !!document.getElementById('pm-unresolved')?.checked;
    if (unresolved || v('pm-unc-note')) j.uncertainty = { unresolved, note: v('pm-unc-note') || null };
    if (v('pm-note')) j.note = v('pm-note');
    return j;
  }

  function msg(text, bad) {
    const m = document.getElementById('pm-msg');
    if (m) { m.textContent = text; m.style.color = bad ? 'var(--red)' : 'var(--dim2)'; }
  }

  window._pmAnnotateSelected = function () {
    const selection = _crGetReaderSelection({ refresh: !_crSelText, fallback: true });
    const text = selection?.text || _crSelText;
    if (!text) return;
    _crSelText = text;
    _crCaptureOpen = true;
    if (typeof _crMarkPending === 'function') _crMarkPending();
    if (!_crSelToolbar) _crShowToolbar(_crSelectionRect);
    const tb = _crSelToolbar;
    if (!tb) return;
    tb.classList.add('capture-open');
    tb.innerHTML = `<div class="cr-capture-shell"><div class="cr-capture-scroll">
        <div class="cr-capture-evidence"><div class="cr-capture-evidence-label">Selected passage</div>
        <blockquote class="cr-selection-preview">${esc(text)}</blockquote></div>
        ${panelHtml(null, 'Annotate', 'Save annotation', '_pmSaveNew()')}</div></div>`;
    requestAnimationFrame(() => _crPlaceToolbar(tb, _crSelectionRect));
    setTimeout(() => document.getElementById('pm-form')?.focus?.(), 50);
  };

  window._pmSaveNew = async function () {
    const judgment = readJudgment();
    if (!Object.keys(judgment).length) { msg('Add at least one thing you noticed.', true); return; }
    const selection = _crGetReaderSelection({ refresh: false, fallback: true });
    const selectedText = selection?.text || _crSelText;
    const full = _crPageReadingText();
    const idx = full.indexOf(selectedText);
    msg('Saving…');
    let highlight;
    try {
      highlight = await requestJSON('/api/reader/highlights', {
        method: 'POST', body: {
          source_document_id: docId(), page: _crPage, source_locator: _crEncodeReaderSpanLocator(selection),
          selected_text: selectedText,
          context_before: idx > 0 ? full.slice(Math.max(0, idx - 100), idx).trim() : '',
          context_after: idx > -1 ? full.slice(idx + selectedText.length, idx + selectedText.length + 100).trim() : '',
          relevance: 'unclear', tags: ['pm-annotation'],
        },
      });
      await requestJSON('/api/bridge/pm/annotations', {
        method: 'POST', body: { highlight_id: highlight.id, judgment, modality: PM.pointer, device_class: deviceClass() },
      });
    } catch (e) {
      msg(highlight ? 'The highlight was kept, but the annotation was refused: ' + e.message : e.message, true);
      return;
    }
    _crCaptureOpen = false;
    _crHideToolbar(true);
    if (typeof _crClearPending === 'function') _crClearPending();
    if (typeof _crClearReaderSelectionState === 'function') _crClearReaderSelectionState();
    _crSelText = '';
    await _crLoadHighlightList();
    _crRenderPage();
    if (typeof _crRefreshTrail === 'function') _crRefreshTrail();
    _crShowHighlightDetail(highlight.id);
  };

  window._pmCancel = function () {
    if (typeof _crCancelHighlight === 'function') _crCancelHighlight();
  };

  // ── Highlight detail: current annotation, first pass, revise / withdraw ─
  async function renderDetail(highlightId) {
    const form = document.getElementById('cr-sel-form');
    if (!form || !docId()) return;
    let data;
    try {
      const r = await fetch(`/api/bridge/pm/annotations?document_id=${encodeURIComponent(docId())}`);
      data = await r.json();
    } catch (e) { return; }
    const a = (data.annotations || []).find(x => x.highlight_id === highlightId);
    form.querySelector('.pm-detail')?.remove();
    if (!a) return;
    PM.annotations = data.annotations;
    const cur = a.current, j = cur.judgment || {}, first = a.first_pass;
    const perf = j.performance || {};
    const line = (k, v) => v ? `<div class="pm-kv"><span>${k}</span><b>${esc(v)}</b></div>` : '';
    const revised = a.history.length > 1;
    const div = document.createElement('div');
    div.className = 'pm-detail';
    div.innerHTML = `
      <div class="pm-panel-title">PM annotation <span class="pm-chip${first.mode === 'human-gold' ? ' pm-chip-open' : ''}">${first.mode === 'human-gold' ? 'human gold' : 'unblinded'}</span></div>
      ${a.withdrawn ? '<div class="pm-help">Withdrawn — kept in history.</div>' : `
        ${line('Form', LABEL[j.target_form])}${line('Source', LABEL[j.source_class])}${line('Who / what', j.source_identity)}
        ${line('Point of view', j.point_of_view)}${line('Tone', perf.tone)}${line('Pace', perf.pace)}${line('Intensity', perf.intensity)}
        ${line('Emphasis', (perf.emphasis || []).join('; '))}${line('Pauses', (perf.pauses || []).join('; '))}
        ${line('Pronunciation', (perf.pronunciation || []).join('; '))}
        ${j.uncertainty && j.uncertainty.unresolved ? line('Unresolved', j.uncertainty.note || 'yes') : ''}${line('Note', j.note)}`}
      ${revised ? `<details class="pm-details"><summary>First pass (${esc(first.created_at.slice(0, 16).replace('T', ' '))}) · ${a.history.length - 1} later change${a.history.length > 2 ? 's' : ''}</summary>
        <pre class="pm-pre">${esc(JSON.stringify(first.judgment, null, 1))}</pre></details>` : ''}
      ${a.withdrawn ? '' : `<div class="pm-actions">
        <button type="button" class="pm-btn" onclick="_pmRevise('${esc(cur.id)}')">Revise</button>
        <button type="button" class="pm-btn" onclick="_pmWithdraw('${esc(cur.id)}', '${esc(highlightId)}')">Withdraw</button></div>`}`;
    form.prepend(div);
  }

  window._pmRevise = function (eventId) {
    const a = PM.annotations.find(x => x.current.id === eventId);
    const form = document.getElementById('cr-sel-form');
    if (!a || !form) return;
    form.querySelector('.pm-detail').innerHTML = panelHtml(a.current.judgment, 'Revise annotation', 'Save revision',
      `_pmSaveRevision('${esc(eventId)}', '${esc(a.highlight_id)}')`);
  };

  window._pmSaveRevision = async function (eventId, highlightId) {
    const judgment = readJudgment();
    if (!Object.keys(judgment).length) { msg('Add at least one thing, or withdraw instead.', true); return; }
    try {
      await requestJSON(`/api/bridge/pm/annotations/${encodeURIComponent(eventId)}/revise`, {
        method: 'POST', body: { judgment, modality: PM.pointer, device_class: deviceClass() },
      });
    } catch (e) { msg(e.message, true); return; }
    renderDetail(highlightId);
  };

  window._pmWithdraw = async function (eventId, highlightId) {
    if (!confirm('Withdraw this annotation? It stays in the history as withdrawn.')) return;
    try {
      await requestJSON(`/api/bridge/pm/annotations/${encodeURIComponent(eventId)}/withdraw`, {
        method: 'POST', body: { modality: PM.pointer, device_class: deviceClass() },
      });
    } catch (e) { return; }
    renderDetail(highlightId);
  };

  // ── Hooks into the Reader (wrap, never replace behaviour) ────────────────
  function after(name, fn) {
    const orig = window[name];
    if (typeof orig !== 'function') return;
    window[name] = function (...args) {
      const out = orig.apply(this, args);
      Promise.resolve(out).then(() => fn(...args));
      return out;
    };
  }
  function guard(name) {
    const orig = window[name];
    if (typeof orig !== 'function') return;
    window[name] = function (...args) {
      if (PM.open) { showAppMessage?.('Machine assistance is off while the human-gold pass is open.'); return; }
      return orig.apply(this, args);
    };
  }
  after('_crRenderPage', () => renderSlot());
  after('_crShowToolbar', () => syncToolbar());
  after('_crShowHighlightDetail', id => renderDetail(id));
  guard('_crAskCompanion');
  guard('_crPerspectiveFromSelection');
  guard('_crToggleLens');

  const style = document.createElement('style');
  style.textContent = `
    body.pm-gold-open .cr-companion-dock, body.pm-gold-open #cr-lens-toggle, body.pm-gold-open #cr-page-brief,
    body.pm-gold-open .dock-rail-btn[data-panel="observations"], body.pm-gold-open .cr-sel-btn.pm-machine,
    body.pm-gold-open .cr-tool-row[onclick*="'observations'"] { display: none !important; }
    .pm-gold-slot { display: inline-flex; gap: 8px; align-items: center; margin-left: auto; }
    .pm-chip { font: 11px var(--mono, monospace); padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border2); color: var(--dim2); }
    .pm-chip-open { border-color: var(--accent); color: var(--accent); }
    .pm-btn { font: inherit; font-size: 13px; min-height: 36px; padding: 6px 12px; border-radius: var(--r, 6px);
              border: 1px solid var(--border2); background: none; color: var(--fg2, inherit); cursor: pointer; }
    .pm-panel, .pm-detail { display: grid; gap: 8px; margin-top: 8px; }
    .pm-detail { padding: 10px; border: 1px solid var(--border2); border-radius: var(--r, 6px); margin-bottom: 10px; }
    .pm-panel-title { font-weight: 600; display: flex; gap: 8px; align-items: center; }
    .pm-help { font-size: 12px; color: var(--dim2); }
    .pm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    @media (max-width: 520px) { .pm-grid { grid-template-columns: 1fr; } }
    .pm-field { display: grid; gap: 3px; font-size: 12px; color: var(--dim2); }
    .pm-input { font: inherit; font-size: 14px; min-height: 40px; padding: 6px 8px; border-radius: var(--r, 6px);
                border: 1px solid var(--border2); background: var(--bg2, transparent); color: var(--fg, inherit); }
    textarea.pm-input { min-height: 56px; }
    .pm-check { display: flex; gap: 8px; align-items: center; font-size: 13px; min-height: 36px; }
    .pm-check input { width: 20px; height: 20px; }
    .pm-details summary { cursor: pointer; font-size: 13px; min-height: 32px; display: flex; align-items: center; }
    .pm-actions { display: flex; gap: 8px; }
    .pm-actions .btn-primary { flex: 1; min-height: 40px; }
    .pm-kv { display: flex; gap: 8px; font-size: 13px; } .pm-kv span { color: var(--dim2); min-width: 96px; }
    .pm-pre { font-size: 11px; white-space: pre-wrap; margin: 6px 0 0; }
    .pm-msg { font-size: 12px; }`;
  document.head.appendChild(style);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load);
  else load();
})();
