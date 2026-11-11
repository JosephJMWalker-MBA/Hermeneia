/* Author Journal: a quiet workspace-level view over the existing append-only
 * Investigation Log. This does NOT create canonical manuscript content.
 * It deliberately reuses the "corpus" lane so no new ontology, schema,
 * migration, or storage/export contract is introduced (issue #205).
 */
(function () {
  'use strict';

  let previousFocus = null;
  let saving = false;

  function element(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function status(message, isError) {
    const host = element('author-journal-status');
    if (!host) return;
    host.textContent = message || '';
    host.style.color = isError ? 'var(--red, #b23a3a)' : 'var(--dim2)';
  }

  async function load() {
    const host = element('author-journal-entries');
    if (!host) return;
    host.textContent = 'Loading workspace notes…';
    try {
      const response = await fetch('/api/investigation-log?lane=corpus&limit=200');
      if (!response.ok) throw new Error('Could not load workspace notes (' + response.status + ').');
      const payload = await response.json();
      const notes = payload.entries || [];
      if (element('author-journal-count')) {
        element('author-journal-count').textContent = notes.length + ' recent note' + (notes.length === 1 ? '' : 's');
      }
      if (!notes.length) {
        host.textContent = 'No author reflections or Reader notes yet. Your first thought can begin here.';
        return;
      }
      host.innerHTML = notes.map(function (entry) {
        const timestamp = escapeHtml(String(entry.created_at || '').slice(0, 16).replace('T', ' '));
        const location = entry.original_filename
          ? ' · ' + escapeHtml(entry.original_filename) + (entry.page ? ', p. ' + escapeHtml(entry.page) : '')
          : '';
        const thought = entry.understanding
          ? '<p style="white-space:pre-wrap;margin:6px 0">' + escapeHtml(entry.understanding) + '</p>' : '';
        const questions = entry.pressing_questions
          ? '<p style="white-space:pre-wrap;margin:6px 0;color:var(--dim2)">Question: ' +
            escapeHtml(entry.pressing_questions) + '</p>' : '';
        return '<article style="border-top:1px solid var(--border);padding:10px 0">' +
          '<div style="font-size:11px;color:var(--dim2)">' + timestamp + location + '</div>' +
          thought + questions + '</article>';
      }).join('');
    } catch (error) {
      host.textContent = 'Could not load notes. The manuscript and existing notes were not changed.';
      status(error.message || String(error), true);
    }
  }

  window.authorJournalOpen = function () {
    const overlay = element('author-journal-overlay');
    if (!overlay) return;
    previousFocus = document.activeElement;
    if (typeof window._wsCloseMenu === 'function') window._wsCloseMenu();
    overlay.hidden = false;
    status('Reflections are appended to this workspace’s Field Notes—not to the manuscript.');
    load();
    element('author-journal-thought')?.focus();
  };

  window.authorJournalClose = function () {
    if (saving) return;
    const thought = element('author-journal-thought');
    const questions = element('author-journal-questions');
    if ((thought?.value.trim() || questions?.value.trim()) &&
        !window.confirm('Discard the unsaved journal entry?')) return;
    element('author-journal-overlay').hidden = true;
    if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
  };

  window.authorJournalSave = async function () {
    if (saving) return;
    const thought = element('author-journal-thought');
    const questions = element('author-journal-questions');
    const understanding = thought?.value.trim() || '';
    const pressing_questions = questions?.value.trim() || '';
    if (!understanding && !pressing_questions) {
      status('Write a thought or a question before saving.', true);
      thought?.focus();
      return;
    }
    const button = element('author-journal-save');
    saving = true;
    if (button) button.disabled = true;
    status('Preserving this reflection…');
    try {
      const response = await fetch('/api/investigation-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lane: 'corpus', understanding, pressing_questions })
      });
      if (!response.ok) {
        const payload = await response.json().catch(function () { return {}; });
        throw new Error(payload.error || 'Saving the reflection failed.');
      }
      if (thought) thought.value = '';
      if (questions) questions.value = '';
      await load();
      status('Reflection preserved in this workspace’s append-only history.');
    } catch (error) {
      // Preserve the unsaved browser input when a write fails.
      status(error.message || String(error), true);
    } finally {
      saving = false;
      if (button) button.disabled = false;
    }
  };

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !element('author-journal-overlay')?.hidden) {
      event.preventDefault();
      window.authorJournalClose();
    }
  });
}());
