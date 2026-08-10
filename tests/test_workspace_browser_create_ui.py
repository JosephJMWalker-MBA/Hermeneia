"""Browser workspace creation flow (issue #125 Slice B)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX_HTML = (
    Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
)


def _index() -> str:
    return INDEX_HTML.read_text()


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


def _workspace_create_js() -> str:
    source = _index()
    signatures = [
        "function _wsApplyCurrentWorkspace(",
        "function _wsRenderWorkspaceCatalog(",
        "async function _wsRefreshWorkspaceCatalog(",
        "function _wsSetCreateStatus(",
        "function _wsShowCreateForm(",
        "function _wsHideCreateForm(",
        "function _wsCreateErrorMessage(",
        "async function _wsCreateWorkspace(",
    ]
    return "\n".join(_extract_function(source, signature) for signature in signatures)


def _node_base() -> str:
    return f"""
    function makeElement(hidden = false) {{
      return {{
        hidden,
        value: '',
        textContent: '',
        innerHTML: '',
        dataset: {{}},
        disabled: false,
        focused: false,
        attrs: {{}},
        focus() {{ this.focused = true; }},
        setAttribute(k, v) {{ this.attrs[k] = String(v); }},
        getAttribute(k) {{ return this.attrs[k]; }},
      }};
    }}
    const elements = {{
      'workspace-create-form': makeElement(true),
      'workspace-create-name': makeElement(false),
      'workspace-create-status': makeElement(true),
      'workspace-create-submit': makeElement(false),
      'workspace-catalog': makeElement(false),
      'runtime-workspace-chip': makeElement(true),
      'runtime-workspace-name': makeElement(false),
    }};
    const document = {{
      getElementById(id) {{ return elements[id] || null; }},
    }};
    function x(value) {{
      return String(value ?? '').replace(/[&<>"']/g, (ch) => ({{
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }}[ch]));
    }}
    class RuntimeEndpointError extends Error {{
      constructor(message = 'lost') {{
        super(message);
        this.endpointUnreachable = true;
      }}
    }}
    class RuntimeHttpError extends Error {{
      constructor(message, response, data = null) {{
        super(message || `HTTP ${{response?.status || ''}}`.trim());
        this.status = response?.status || 0;
        this.data = data;
      }}
    }}
    function _runtimeIsEndpointError(error) {{
      return !!error?.endpointUnreachable || error instanceof RuntimeEndpointError;
    }}
    let draftScope = 'managed:ws-a';
    let draftScopeApplyCalls = 0;
    function _runtimeApplyWorkspaceDraftScope(workspace) {{
      draftScopeApplyCalls += 1;
      if (workspace?.runtime_scope) draftScope = workspace.runtime_scope;
      return true;
    }}
    let _wsCurrentWorkspace = null;
    let _wsCatalog = [];
    let _wsCatalogLoading = false;
    let _wsCreateInFlight = false;
    let runtimeApiFetch;
    let get;
    {_workspace_create_js()}
    """


def _run_node(script: str) -> dict:
    if shutil.which("node") is None:  # pragma: no cover - environment guard
        pytest.skip("node runtime not available")
    result = subprocess.run(
        ["node", "-e", _node_base() + script],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_workspace_create_form_opens_and_closes():
    out = _run_node(
        """
        _wsShowCreateForm();
        const opened = elements['workspace-create-form'].hidden === false
          && elements['workspace-create-name'].focused === true
          && elements['workspace-create-status'].hidden === true;
        elements['workspace-create-name'].value = 'Research Notes';
        _wsSetCreateStatus('Problem', 'error');
        _wsHideCreateForm();
        const closed = elements['workspace-create-form'].hidden === true
          && elements['workspace-create-name'].value === ''
          && elements['workspace-create-status'].hidden === true;
        console.log(JSON.stringify({ opened, closed }));
        """
    )

    assert out == {"opened": True, "closed": True}


def test_workspace_create_success_posts_refreshes_catalog_and_keeps_current_chip():
    out = _run_node(
        """
        (async () => {
          const posts = [];
          const gets = [];
          runtimeApiFetch = async (url, options) => {
            posts.push({ url, options });
            return {
              ok: true,
              status: 201,
              json: async () => ({
                workspace: {
                  id: 'ws-b',
                  name: 'Research Notes',
                  slug: 'research-notes',
                  kind: 'managed',
                  managed: true,
                  is_active: false,
                },
              }),
            };
          };
          get = async (url) => {
            gets.push(url);
            return {
              workspaces: [
                { name: 'The Second Sale', slug: 'the-second-sale', is_active: true },
                { name: 'Research Notes', slug: 'research-notes', is_active: false },
              ],
            };
          };
          _wsApplyCurrentWorkspace({ name: 'The Second Sale', slug: 'the-second-sale', kind: 'managed' });
          elements['workspace-create-name'].value = 'Research Notes';
          await _wsCreateWorkspace();
          const postedBody = JSON.parse(posts[0].options.body);
          const created = _wsCatalog.find((workspace) => workspace.slug === 'research-notes');
          console.log(JSON.stringify({
            postUrl: posts[0].url,
            method: posts[0].options.method,
            postedName: postedBody.name,
            getUrls: gets,
            chip: elements['runtime-workspace-name'].textContent,
            currentSlug: _wsCurrentWorkspace.slug,
            inputCleared: elements['workspace-create-name'].value === '',
            status: elements['workspace-create-status'].textContent,
            createdInactive: created && created.is_active === false,
            draftScope,
            draftScopeApplyCalls,
            catalogHtml: elements['workspace-catalog'].innerHTML,
          }));
        })();
        """
    )

    assert out["postUrl"] == "/api/workspaces"
    assert out["method"] == "POST"
    assert out["postedName"] == "Research Notes"
    assert out["getUrls"] == ["/api/workspaces"]
    assert out["chip"] == "The Second Sale"
    assert out["currentSlug"] == "the-second-sale"
    assert out["draftScope"] == "managed:ws-a"
    assert out["draftScopeApplyCalls"] == 1
    assert out["inputCleared"] is True
    assert out["createdInactive"] is True
    assert "Workspace created: Research Notes." in out["status"]
    assert "Current workspace remains: The Second Sale." in out["status"]
    assert "Research Notes" in out["catalogHtml"]


def test_workspace_create_endpoint_loss_keeps_name_and_does_not_auto_replay():
    out = _run_node(
        """
        (async () => {
          let posts = 0;
          let gets = 0;
          runtimeApiFetch = async () => {
            posts += 1;
            throw new RuntimeEndpointError('lost');
          };
          get = async () => {
            gets += 1;
            return { workspaces: [] };
          };
          elements['workspace-create-name'].value = 'Research Notes';
          await _wsCreateWorkspace();
          console.log(JSON.stringify({
            posts,
            gets,
            retained: elements['workspace-create-name'].value,
            status: elements['workspace-create-status'].textContent,
          }));
        })();
        """
    )

    assert out["posts"] == 1
    assert out["gets"] == 0
    assert out["retained"] == "Research Notes"
    assert "not confirmed" in out["status"]
    assert "Workspace created" not in out["status"]


def test_workspace_create_duplicate_error_is_clear_and_retains_name():
    out = _run_node(
        """
        (async () => {
          let gets = 0;
          runtimeApiFetch = async () => ({
            ok: false,
            status: 409,
            json: async () => ({
              error: 'workspace already exists: research-notes',
              workspace: {
                name: 'Research Notes',
                slug: 'research-notes',
                is_active: false,
              },
            }),
          });
          get = async () => {
            gets += 1;
            return { workspaces: [] };
          };
          elements['workspace-create-name'].value = 'Research Notes';
          await _wsCreateWorkspace();
          console.log(JSON.stringify({
            gets,
            retained: elements['workspace-create-name'].value,
            status: elements['workspace-create-status'].textContent,
          }));
        })();
        """
    )

    assert out["gets"] == 0
    assert out["retained"] == "Research Notes"
    assert out["status"] == "Workspace already exists: Research Notes."
