/* Working manuscript editor; true editable HTML, working revisions, CSS.
 * No Compositor acceptance is implied. Sandboxed canvas cannot execute scripts.
 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {revision:null,loaded:false,dirty:false,saving:false,timer:null,savedSnapshot:''};
  const doc = () => $('writer-frame').contentDocument;
  const canvas = () => doc()?.getElementById('writer-document');

  function status(message, error = false) {
    $('writer-save-status').textContent = message;
    $('writer-save-status').dataset.state = error ? 'error' : '';
  }
  function error(message) {
    $('writer-warning').textContent = message || '';
    $('writer-warning').hidden = !message;
    if (message) status('Needs attention', true);
  }
  async function api(url,options) {
    let response;
    try { response = await fetch(url,options); }
    catch { throw new Error('Connection lost. Your changes remain in the editor.'); }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const failure = new Error(data.error || 'Request failed (HTTP ' + response.status + ').');
      failure.code = data.code;
      throw failure;
    }
    return data;
  }
  function initCanvas() {
    const frame = $('writer-frame');
    const src = [
      '<!doctype html><html lang="en"><head><meta charset="utf-8">',
      '<meta http-equiv="Content-Security-Policy" content="default-src &apos;none&apos;; style-src &apos;self&apos; &apos;unsafe-inline&apos;; img-src data:; font-src data:; form-action &apos;none&apos;">',
      '<link rel="stylesheet" href="/static/manuscript_canvas.css">',
      '<style id="writer-custom-style"></style></head><body>',
      '<article id="writer-document" contenteditable="true" spellcheck="true" aria-label="Editable manuscript text"></article>',
      '</body></html>'
    ].join('');
    return new Promise(resolve => {
      frame.addEventListener('load', () => {
        const writing = canvas();
        writing.addEventListener('input', changed);
        writing.addEventListener('paste', safePaste);
        writing.addEventListener('keyup', inspect);
        writing.addEventListener('mouseup', inspect);
        resolve();
      }, {once:true});
      frame.srcdoc = src;
    });
  }
  function payload() {
    return {title:$('writer-title').value.trim(),html:canvas()?.innerHTML || '',style_css:$('writer-css').value};
  }
  function snapshot() { return JSON.stringify(payload()); }
  function applyCss() {
    const target = doc()?.getElementById('writer-custom-style');
    if (target) target.textContent = $('writer-css').value;
  }
  function render(value) {
    $('writer-title').value = value.title || '';
    canvas().innerHTML = value.html || '<p><br></p>';
    $('writer-css').value = value.style_css || '';
    applyCss();
    inspect();
  }
  function inspect() {
    const text = canvas()?.innerText || '';
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    $('writer-count').textContent = words + ' word' + (words === 1 ? '' : 's');
    const host = $('writer-outline');
    host.replaceChildren();
    const headings = Array.from(canvas()?.querySelectorAll('h1,h2,h3') || []);
    if (!headings.length) {
      const note = document.createElement('p');
      note.className='writer-muted';
      note.textContent='Add a heading to build an outline.';
      host.append(note);
    }
    for (const heading of headings) {
      const button = document.createElement('button');
      button.type='button';
      button.textContent=heading.textContent.trim() || '(heading)';
      button.style.paddingLeft=(10+(Number(heading.tagName.slice(1))-1)*15)+'px';
      button.addEventListener('click', () => heading.scrollIntoView({behavior:'smooth',block:'center'}));
      host.append(button);
    }
  }
  function changed() {
    if (!state.loaded) return;
    inspect();
    state.dirty = snapshot() !== state.savedSnapshot;
    status(state.dirty ? 'Unsaved changes' : 'All changes saved');
    clearTimeout(state.timer);
    if (state.dirty && payload().title) state.timer=setTimeout(save,1800);
  }
  async function save() {
    clearTimeout(state.timer);
    if (!state.loaded || state.saving || !state.dirty) return;
    const data = payload();
    if (!data.title) {
      status('Enter a title before saving',true);
      $('writer-title').focus();
      return;
    }
    state.saving=true; $('writer-save').disabled=true; status('Saving…');
    const sent=JSON.stringify(data);
    try {
      const saved=await api('/api/manuscript-draft',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({...data,expected_revision:state.revision})
      });
      state.revision=saved.revision;
      // The server canonicalizes safe HTML. Do not replace a live DOM selection
      // while the author is typing: compare what was sent to detect new edits.
      state.savedSnapshot=sent;
      state.dirty=snapshot()!==sent;
      error('');
      status(state.dirty ? 'New changes pending' : 'Saved version '+saved.number);
      await loadHistory().catch(() => {});
    } catch (failure) {
      error(failure.message || String(failure));
      // No local edits are discarded on network, validation, or stale-head errors.
    } finally {
      state.saving=false; $('writer-save').disabled=false;
      if (state.dirty && snapshot()!==sent && payload().title) {
        clearTimeout(state.timer);state.timer=setTimeout(save,1800);
      }
    }
  }
  async function loadHistory() {
    const data=await api('/api/manuscript-draft/history');
    const host=$('writer-history');host.replaceChildren();
    if (!data.revisions?.length) {
      const p=document.createElement('p');p.className='writer-muted';
      p.textContent='No saved revisions yet.';host.append(p);return;
    }
    data.revisions.forEach(rev=>{
      const button=document.createElement('button');
      button.type='button';
      button.className='writer-version'+(rev.revision===state.revision?' is-current':'');
      button.textContent='Version '+rev.number+' · '+new Date(rev.updated_at).toLocaleString();
      button.addEventListener('click',()=>viewRevision(rev.revision));
      host.append(button);
    });
  }
  async function viewRevision(revision) {
    if (state.dirty && !confirm('Discard unsaved changes to open an earlier version?')) return;
    try {
      const previous=await api('/api/manuscript-draft/history/'+encodeURIComponent(revision));
      if (!confirm('Load version '+previous.number+'? Saving afterward creates a new revision.')) return;
      render(previous);
      changed();
      status('Earlier version '+previous.number+' loaded. Save to create a new revision.');
    } catch (failure) {error(failure.message || String(failure));}
  }
  function command(action,value) {
    const d=doc();canvas().focus();
    d.execCommand('styleWithCSS',false,false);
    d.execCommand(action,false,value);
    changed();
  }
  function makeLink() {
    const url=prompt('Paste a URL (https:// or mailto:)');
    if (url===null) return;
    if (!/^(https?:\/\/|mailto:)/i.test(url)) {
      error('Enter a link starting with https://, http://, or mailto:.');return;
    }
    command('createLink',url);
  }
  function safePaste(event) {
    const text=event.clipboardData?.getData('text/plain') || '';
    const markup=event.clipboardData?.getData('text/html') || '';
    if (!text && !markup) return;
    event.preventDefault();
    if (markup) {
      const incoming=new DOMParser().parseFromString(markup,'text/html');
      const allow=new Set(['P','DIV','BR','H1','H2','H3','UL','OL','LI',
        'BLOCKQUOTE','B','STRONG','I','EM','U','S','DEL','CODE','PRE','HR','A','SPAN','SUP','SUB']);
      const block=new Set(['SCRIPT','STYLE','SVG','MATH','IFRAME','OBJECT','FORM','INPUT']);
      function copy(source,destination) {
        if (source.nodeType===Node.TEXT_NODE) {
          destination.append(doc().createTextNode(source.textContent));return;
        }
        if (source.nodeType!==Node.ELEMENT_NODE || block.has(source.nodeName)) return;
        const permitted=allow.has(source.nodeName);
        const node=permitted?doc().createElement(source.nodeName.toLowerCase()):destination;
        if (source.nodeName==='A' && permitted) {
          const href=source.getAttribute('href') || '';
          if (/^(https?:\/\/|mailto:)/i.test(href)) node.setAttribute('href',href);
        }
        Array.from(source.childNodes).forEach(child=>copy(child,node));
        if (permitted) destination.append(node);
      }
      const holder=doc().createElement('div');
      Array.from(incoming.body.childNodes).forEach(node=>copy(node,holder));
      doc().execCommand('insertHTML',false,holder.innerHTML);
    } else doc().execCommand('insertText',false,text);
    changed();
  }
  function toggleStyles(open) {
    $('writer-styles').hidden=!open;
    document.body.classList.toggle('writer-styles-open',open);
    $('writer-styles-toggle').setAttribute('aria-expanded',String(open));
    if (open) $('writer-css').focus();
  }
  async function importFile() {
    const file=$('writer-file').files?.[0];
    $('writer-file').value='';
    if (!file) return;
    if ((state.dirty || canvas()?.innerText?.trim()) &&
        !confirm('Replace the visible manuscript with this file? Saved versions will remain available.')) return;
    try {
      const text=await file.text();
      const result=await api('/api/manuscript-draft/convert',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({format:/\.(md|markdown)$/i.test(file.name)?'markdown':'text',content:text})
      });
      canvas().innerHTML=result.html || '<p><br></p>';
      if (!$('writer-title').value.trim()) $('writer-title').value=file.name.replace(/\.(md|markdown|txt)$/i,'');
      changed();
      status('Imported. Review the text and save.');
      canvas().focus();
    } catch(failure){error(failure.message || String(failure));}
  }
  async function exportHtml() {
    if (state.dirty) await save();
    if (state.dirty || !state.revision) {
      error('Save a manuscript version before exporting.');return;
    }
    window.location.assign('/api/manuscript-draft/export');
  }
  async function boot() {
    try {
      await initCanvas();
      const [runtime,saved]=await Promise.all([
        api('/api/runtime/workspace'),api('/api/manuscript-draft')
      ]);
      $('writer-workspace').textContent='Workspace: '+(runtime.workspace?.name || 'Current');
      render(saved);
      if (!$('writer-title').value.trim())
        $('writer-title').value=runtime.workspace?.name || 'Untitled manuscript';
      state.revision=saved.revision;
      state.savedSnapshot=snapshot();state.loaded=true;
      status(saved.revision?'Saved version '+saved.number:'New working manuscript');
      await loadHistory().catch(()=>{});
      canvas().focus();
    }catch(failure){
      error('Cannot open manuscript editor: '+(failure.message || failure));
      $('writer-save').disabled=true;
    }
  }
  document.addEventListener('DOMContentLoaded',()=>{
    document.querySelectorAll('[data-command]').forEach(button=>{
      button.addEventListener('mousedown',event=>event.preventDefault());
      button.addEventListener('click',()=>command(button.dataset.command));
    });
    $('writer-block').addEventListener('change',event=>{
      command('formatBlock','<'+event.target.value+'>');
      event.target.value='p';
    });
    $('writer-link').addEventListener('click',makeLink);
    $('writer-save').addEventListener('click',save);
    $('writer-title').addEventListener('input',changed);
    $('writer-styles-toggle').addEventListener('click',()=>toggleStyles($('writer-styles').hidden));
    $('writer-styles-close').addEventListener('click',()=>toggleStyles(false));
    $('writer-css').addEventListener('input',()=>{applyCss();changed();});
    $('writer-reset-css').addEventListener('click',()=>{
      $('writer-css').value='';applyCss();changed();
    });
    $('writer-focus').addEventListener('click',event=>{
      const focus=!document.body.classList.contains('writer-focus');
      document.body.classList.toggle('writer-focus',focus);
      event.target.setAttribute('aria-pressed',String(focus));
      canvas()?.focus();
    });
    $('writer-import').addEventListener('click',()=>$('writer-file').click());
    $('writer-file').addEventListener('change',importFile);
    $('writer-export').addEventListener('click',exportHtml);
    document.addEventListener('keydown',event=>{
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase()==='s') {
        event.preventDefault();save();
      }
    });
    window.addEventListener('beforeunload',event=>{
      if (state.dirty) {event.preventDefault();event.returnValue='';}
    });
    boot();
  });
})();
