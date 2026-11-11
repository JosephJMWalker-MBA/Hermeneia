/* Hermeneia start: choose workspace and working mode without knowing runtime flags.
 * The server remains the sole authority for which workspace is active.
 * This screen has no manuscript, KDP, or publication-canonical write path.
 */
(function () {
  'use strict';

  const RETURN_MODE_KEY = 'hermeneia:start:one-time-mode';
  const state = {
    current: null,
    workspaces: [],
    switching: false,
    canSwitch: false,
    selected: '',
    mounted: false
  };

  const el = (id) => document.getElementById(id);

  function notice(message, error = false) {
    const host = el('herm-start-status');
    if (!host) return;
    host.textContent = message || '';
    host.dataset.error = error ? 'true' : 'false';
  }

  function busy(active) {
    state.switching = active;
    for (const id of ['herm-start-continue', 'herm-start-create']) {
      if (el(id)) el(id).disabled = active;
    }
  }

  async function json(url, options) {
    const response = await fetch(url, options);
    let body = {};
    try { body = await response.json(); } catch (_) { /* report HTTP status */ }
    if (!response.ok) throw new Error(body.error || 'Request failed (HTTP ' + response.status + ').');
    return body;
  }

  function selector(workspace) {
    return String(workspace?.slug || workspace?.id || '').trim();
  }

  function isSame(a, b) {
    if (!a || !b) return false;
    if (a.id && b.id) return a.id === b.id;
    return a.kind === b.kind && selector(a) === selector(b);
  }

  function renderWorkspaces() {
    const host = el('herm-start-workspaces');
    if (!host) return;
    host.replaceChildren();
    if (!state.workspaces.length) {
      const empty = document.createElement('p');
      empty.className = 'herm-start-empty';
      empty.textContent = 'No workspaces yet. Create your first workspace below.';
      host.appendChild(empty);
      return;
    }
    for (const ws of state.workspaces) {
      const name = selector(ws);
      if (!name) continue;
      const label = document.createElement('label');
      label.className = 'herm-start-choice';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'herm-start-workspace';
      input.value = name;
      input.checked = state.selected === name;
      input.addEventListener('change', () => { state.selected = name; });
      const copy = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = ws.name || name;
      const detail = document.createElement('small');
      const docs = Number(ws.document_count || 0);
      detail.textContent =
        (isSame(ws, state.current) ? 'Open now · ' : '') +
        (docs ? docs + ' document' + (docs === 1 ? '' : 's') : 'Empty workspace');
      copy.append(title, detail);
      label.append(input, copy);
      host.appendChild(label);
    }
  }

  async function refresh(preferred) {
    notice('Loading your workspaces…');
    const [runtime, catalog] = await Promise.all([
      json('/api/runtime/workspace'),
      json('/api/workspaces')
    ]);
    state.current = runtime.workspace || null;
    state.canSwitch = runtime.capabilities?.workspace_switch === true;
    state.workspaces = catalog.workspaces || [];
    const wanted = preferred || state.selected;
    state.selected = state.workspaces.some((ws) => selector(ws) === wanted)
      ? wanted
      : selector(state.current) || selector(state.workspaces[0]) || '';
    renderWorkspaces();
    notice(state.canSwitch
      ? 'Select a workspace, then choose what to do.'
      : 'This server session cannot switch workspaces. Restart Hermeneia with the standard launcher (herm serve) to enable selection.',
      !state.canSwitch);
  }

  function mode() {
    return document.querySelector('input[name="herm-start-mode"]:checked')?.value || 'read';
  }

  function launchMode(selectedMode) {
    const target = selectedMode === 'journal' ? 'journal' : 'read';
    const go = () => {
      if (!el('reader')) return false;
      if (typeof window.e10Go !== 'function') return false;
      el('herm-start-screen').hidden = true;
      window.e10Go('reader');
      if (target === 'journal' && typeof window.authorJournalOpen === 'function') {
        window.authorJournalOpen();
      }
      return true;
    };
    if (!go()) {
      // Boot and workspace selection happen concurrently; never route against
      // an unmounted Reader or guess a workspace from the URL.
      document.addEventListener('hermeneia:mounted', go, { once: true });
    }
  }

  async function choose(target, selectedMode) {
    if (state.switching) return;
    if (!target) {
      notice('Choose a workspace or create one.', true);
      return;
    }
    busy(true);
    try {
      const current = state.current;
      const desired = state.workspaces.find((ws) => selector(ws) === target);
      if (!desired) throw new Error('Workspace was not found. Refresh and choose again.');
      if (!isSame(current, desired)) {
        if (!state.canSwitch) throw new Error('Switching is disabled in this server session. Relaunch Hermeneia using its standard launcher.');
        // Reuse the existing authored-draft scope guard, so switching from the
        // start screen cannot silently carry a draft into another workspace.
        if (typeof _runtimeFlushActiveDraftsForScope === 'function' &&
            typeof _runtimeDraftWorkspaceScope !== 'undefined') {
          _runtimeFlushActiveDraftsForScope(_runtimeDraftWorkspaceScope);
        }
        if (typeof window._wsCurrentDraftLabels === 'function' &&
            typeof window._wsConfirmOpenWithDrafts === 'function' &&
            !window._wsConfirmOpenWithDrafts(window._wsCurrentDraftLabels(), desired.name || target)) {
          notice('Workspace selection canceled. Nothing was changed.');
          return;
        }
        notice('Opening ' + (desired.name || target) + '…');
        const opened = await json('/api/workspaces/' + encodeURIComponent(target) + '/open', { method: 'POST' });
        const verified = await json('/api/runtime/workspace');
        if (!isSame(verified.workspace, opened.workspace || desired)) {
          throw new Error('Workspace switch was not confirmed by the running server.');
        }
        // A full reload removes all previous workspace-dependent Reader
        // projections and in-memory model state. The mode is one-time only.
        try { sessionStorage.setItem(RETURN_MODE_KEY, selectedMode); } catch (_) {}
        window.location.reload();
        return;
      }
      launchMode(selectedMode);
    } catch (error) {
      // If a switch succeeded but confirmation failed, refresh backend truth
      // without obscuring the actionable failure message.
      await refresh().catch(() => {});
      notice(error.message || String(error), true);
    } finally {
      busy(false);
    }
  }

  async function continueSelected() {
    await choose(state.selected, mode());
  }

  async function createWorkspace(event) {
    if (event) event.preventDefault();
    if (state.switching) return;
    const name = (el('herm-start-name')?.value || '').trim();
    if (!name) {
      notice('Enter a name for the new workspace.', true);
      el('herm-start-name')?.focus();
      return;
    }
    if (!state.canSwitch) {
      notice('This server session cannot open a newly created workspace. Relaunch with the standard Hermeneia launcher.', true);
      return;
    }
    busy(true);
    let created;
    try {
      notice('Creating ' + name + '…');
      created = await json('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      await refresh(selector(created.workspace));
      if (el('herm-start-name')) el('herm-start-name').value = '';
    } catch (error) {
      notice(error.message || String(error), true);
      return;
    } finally {
      busy(false);
    }
    await choose(selector(created.workspace), mode());
  }

  window.hermStartOpen = async function () {
    const host = el('herm-start-screen');
    if (!host) return;
    host.hidden = false;
    try {
      await refresh();
    } catch (error) {
      notice('Could not load workspace choices: ' + (error.message || error), true);
    }
    el('herm-start-continue')?.focus();
  };

  function init() {
    el('herm-start-continue')?.addEventListener('click', continueSelected);
    el('herm-start-create-form')?.addEventListener('submit', createWorkspace);

    let resumed = '';
    try {
      resumed = sessionStorage.getItem(RETURN_MODE_KEY) || '';
      sessionStorage.removeItem(RETURN_MODE_KEY);
    } catch (_) {}

    if (resumed === 'read' || resumed === 'journal') {
      // A validated workspace handoff just happened. Do not force a second
      // chooser interaction; the new child is authoritative after reload.
      launchMode(resumed);
      return;
    }
    window.hermStartOpen();
  }

  document.addEventListener('DOMContentLoaded', init);
}());
