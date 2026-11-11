# Working manuscript editor — first real-use pilot

**Status:** Implemented on the draft feature branch. Real Jetson browser and Python regression testing remain pending. This is not a Publication Compositor edition.

## First-use workflow

Hermeneia previously offered a Reader and an Author Journal but no freeform editor. Choose **Write & edit** on the start screen or **Write** in the Reader header to open the dedicated /editor route.

The writing surface now uses a real editable document canvas and an ordinary formatting toolbar: paragraphs, headings, bold/italic/underline/strike, lists, quotes, links, undo/redo, and a focus mode. Import .md/.markdown/.txt to revise an existing book: Markdown is converted by the installed Python markdown library and sanitized. A Reader PDF is NOT silently substituted for the editable manuscript.

Use **Document CSS** to paste your stylesheet. The document is rendered inside a script-disabled sandboxed iframe with CSP; your CSS cannot restyle Hermeneia's navigation and Reader. The default manuscript styling uses Hermeneia's dark/teal palette with book-like serif typography.

Edits autosave after an idle delay or via **Save version** / Cmd+S. Every saved version creates an immutable snapshot and the optimistic expected_revision check prevents silently overwriting another browser's edit. Previous revisions can be loaded and resaved as a new revision. Export HTML includes the manuscript and the working CSS.

## Separate from publication authority

The workspace-local working draft lives under manuscript-draft/current.json and manuscript-draft/revisions/*.json. It does not create a SourceDocument, SourceExtraction, Observation, Compositor editorial version, publication proof, or verified edition. These working revisions must NOT be represented as formally accepted Compositor revisions.

Endpoints:
- GET /api/manuscript-draft: working document and revision.
- POST /api/manuscript-draft: append verified working revision.
- GET /api/manuscript-draft/history and /history/<revision>: history inspection.
- POST /api/manuscript-draft/convert: safe Markdown/plain-text import.
- GET /api/manuscript-draft/export: authored HTML export with custom CSS.

## Real-use limitations

The pilot is NOT full Google Docs or Word parity. Browser contenteditable/execCommand is an interim engine, not the final professional document model. Collaborative editing, tables, tracked changes, complex figure handling, comments, full pagination, and stable Compositor semantic mapping require a maintained schema-based editor and further integration.

The draft directory is NOT YET included in the Hermeneia Workspace Bundle export/restore. Download your HTML regularly and back up the workspace's manuscript-draft folder independently until portability is proven. There is no automatic link from Reader's PDF text or from the Author Journal to an exact manuscript unit. CSS styling in the working canvas is not Compositor's final print/profile CSS. No private-note-safe OBS view exists yet.

## Acceptance before merging

Run Python tests:
    python -m pytest -q tests/test_manuscript_editor_pilot.py tests/test_standard_start_screen.py tests/test_standard_start_screen_browser.py tests/test_author_journal_first_slice.py

Then on the Jetson/Mac browser:
1. Select a new workspace and Write & edit. Confirm typing with a visible caret.
2. Format paragraphs, lists, headings, bold and italic. Save, reload, verify all.
3. Import Toward an Ecology of Intelligence Markdown, review formatting and non-ASCII text.
4. Paste custom CSS, confirm only the document changes. Save/reload.
5. Try two browser tabs and prove stale-save refusal retains local edits.
6. Inspect earlier version, resave, verify old versions remain intact.
7. Export HTML, then make an independent copy of manuscript-draft directory.
8. Switch Gatsby/Reader and verify no sources or Compositor work have been fabricated.

PR remains draft until these checks pass.
