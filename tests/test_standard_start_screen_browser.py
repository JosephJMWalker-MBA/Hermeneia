"""Browser-free runtime witness for the workspace-first UI.

Exercises the actual JavaScript event handlers with a small DOM stand-in.
A GitHub file diff alone does not prove the workspace handoff works.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "hermeneia/web/static/start_screen.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not available")
def test_start_screen_workspace_handoff_enters_selected_mode():
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const script = fs.readFileSync(process.argv[1], 'utf8');

function instance(initial, session) {
  const events = {}, elements = new Map(), calls = [];
  const state = { current: initial };
  const workspaces = [
    { id: 'gatsby-id', slug: 'gatsby', kind: 'legacy', name: 'Gatsby' },
    { id: 'book-id', slug: 'new-book', kind: 'managed', name: 'New Book' }
  ];

  function node(tag) {
    return {
      tag, children: [], hidden: false, disabled: false, dataset: {},
      value: '', textContent: '', listeners: {},
      addEventListener(e, fn) { this.listeners[e] = fn; },
      append(...children) { this.children.push(...children); },
      appendChild(child) { this.children.push(child); },
      replaceChildren(...children) { this.children = children; },
      focus() {}
    };
  }

  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, node('div'));
      return elements.get(id);
    },
    createElement: node,
    querySelector(s) {
      return s.includes('herm-start-mode') ? { value: 'journal' } : null;
    },
    addEventListener(e, fn) { events[e] = fn; }
  };

  let reloaded = false, journals = 0;
  const window = {
    e10Go(mode) { calls.push(mode); },
    authorJournalOpen() { journals++; },
    location: { reload() { reloaded = true; } }
  };

  async function fetch(url, opts = {}) {
    let result;
    if (url === '/api/runtime/workspace') {
      result = { workspace: state.current, capabilities: { workspace_switch: true } };
    } else if (url === '/api/workspaces') {
      result = { workspaces };
    } else if (url.endsWith('/open') && opts.method === 'POST') {
      state.current = workspaces[1];
      result = { workspace: state.current, changed: true };
    } else {
      throw Error('Unexpected route: ' + url);
    }
    return { ok: true, status: 200, json: async () => result };
  }

  const sessionStorage = {
    getItem(k) { return session[k] || null; },
    setItem(k, v) { session[k] = v; },
    removeItem(k) { delete session[k]; }
  };

  new Function('document', 'window', 'fetch', 'sessionStorage', script)(
    document, window, fetch, sessionStorage
  );
  return {
    events, elements, calls, state,
    get reloaded() { return reloaded; },
    get journals() { return journals; }
  };
}

(async function () {
  const session = {};
  const first = instance({
    id: 'gatsby-id', slug: 'gatsby', kind: 'legacy', name: 'Gatsby'
  }, session);

  first.events.DOMContentLoaded();
  for (let i = 0; i < 12; i++) await Promise.resolve();

  const list = first.elements.get('herm-start-workspaces');
  const radio = list.children
    .find(label => label.children[0]?.value === 'new-book')?.children[0];
  assert.ok(radio, 'non-current workspace appears in the chooser');
  radio.listeners.change();
  await first.elements.get('herm-start-continue').listeners.click();

  assert.equal(first.reloaded, true, 'switch must reload the old Reader shell');
  assert.equal(first.state.current.slug, 'new-book');
  assert.equal(session['hermeneia:start:one-time-mode'], 'journal');

  const second = instance({
    id: 'book-id', slug: 'new-book', kind: 'managed', name: 'New Book'
  }, session);
  second.events.DOMContentLoaded();
  assert.deepEqual(second.calls, ['reader']);
  assert.equal(second.journals, 1);
  assert.equal(second.elements.get('herm-start-screen').hidden, true);
  assert.equal(session['hermeneia:start:one-time-mode'], undefined);
  process.stdout.write('start-screen workspace and mode handoff passed\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(
        ["node", "-e", harness, str(SCRIPT)],
        cwd=SCRIPT.parents[3], capture_output=True, text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
