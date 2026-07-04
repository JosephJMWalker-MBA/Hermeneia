# Storage & Data Safety Audit — Hermeneia

**Status:** Audit (docs-only; describes current behavior, recommends follow-ups)
**Scope:** Where user work lives, what leaves the machine, what can be lost, exported, or deleted.

> This is not just a privacy document. It is a **trust map**. Hermeneia is going
> to hold your thinking. You should know exactly where that thinking lives
> before you depend on it.

Findings below are marked **[verified]** (read from the code at audit time) or
**[recommendation]** (proposed, not yet built). Follow-up issues are listed in
§10. This audit changed no storage behavior.

---

## 0. The short version

- Your work lives in **one SQLite file** (default `build/hermeneia.db`) plus
  **your uploaded PDFs** (`build/uploads/`). Both are local and **git-ignored**.
- A few things live **only in your browser** (localStorage) — most importantly
  your **governing question / investigation**. Clearing browser data loses them.
- A few things are **never stored at all** — the Companion chat transcript is
  in-memory and gone on reload.
- **Nothing is sent to an AI provider automatically.** Provider context is sent
  only when you pick a provider and click Ask/Generate, and only the context
  boxes you check.
- There is currently **no one-click export or "delete my workspace"**. The
  backup unit today is "copy the `build/` folder." (§6, §7, §10.)

---

## 1. What user work exists, and where it is stored  [verified]

Storage surfaces:

- **DB** — SQLite, default `build/hermeneia.db` (`create_app(db_path=...)`,
  `app.py:104`). CLI default `build/hermeneia.db` (`_resolve_db`).
- **FS** — filesystem under the DB's parent (`build/`): `uploads/`, `*.herm`
  bundles, `calibration.json`.
- **Browser** — `localStorage` (keys prefixed `hermeneia_`).
- **Runtime** — computed on demand, never persisted.
- **Provider** — sent to an external/local model only on explicit action (§4).

| User work | Where | Surface | Notes |
|-----------|-------|---------|-------|
| Uploaded source PDF | `build/uploads/<stem>_<rand><suffix>` | FS | Saved via temp file, `delete=False`; kept unless compile fails (`app.py:4786`) |
| Source documents (metadata) | `source_documents` | DB | id = file hash |
| Source extractions (parser output) | `source_extractions` | DB | Exact parser text — canonical |
| Observations | `observations`, `observation_terms`, `observation_derived` | DB | Extraction-derived, canonical |
| Observation reviews / inquiry notes | `observation_reviews`, `inquiry_notes` | DB | Steward rulings + questions |
| Reader highlights (+ notes, questions, ranks, theme/evidence buckets, tags) | `reader_highlights` | DB | User-authored |
| Reading progress / trail | `reading_progress` | DB | Pages read per document |
| Field Notes | `investigation_log` | DB | Lane = corpus/instrument; user-authored |
| Governing / current question (thesis, purpose, lenses) | `localStorage['hermeneia_investigation_v1']` (source of truth); snapshotted into `investigation_log.governing_question` per Field Note | **Browser** (+ incidental DB snapshots) | Authoritative copy is browser-only; DB only holds it if Field Notes were saved carrying it (§5) |
| Companion context flags | `localStorage['hermeneia_companion_context']` | Browser | Which boxes are checked |
| Companion provider choice | `localStorage['hermeneia_companion_provider']` | Browser | |
| Companion chat transcript | `_cmpTranscript` (JS array) | **Runtime** | **Never persisted** — lost on reload (§5) |
| Adopted/saved Companion output | `investigation_log` (as a Field Note) | DB | Packet notes: draft origin not preserved |
| Proposed / accepted interpretations | `proposed_interpretations`, `interpretations` | DB | Machine proposals + accepted |
| Narrative blueprints / architect plans | `narrative_blueprints`, `architect_plans`, `*_links` | DB | |
| Rendered reports / narratives | `rendered_narratives` | DB | Machine output |
| Critic reports | `critic_reports`, `validation_reports` | DB | `normalized=0` until steward review |
| Steward decisions / findings / ratification | `steward_decisions`, `findings`, `ratification_records` | DB | Governance records |
| Synthesis packet | — | **Runtime** | Computed by `/api/study/compile`; not persisted |
| Lineage | — | **Runtime** | Inside the packet (issue #62) |
| Evaluation scorer reports | — | **Runtime** | `hermeneia/study/evaluation/`; not persisted |
| Provider/model choice, register, reader theme, focus scroll, lens, banner dismissed, active bp/plan | `localStorage['hermeneia_*']` | Browser | UI state |
| Calibration | `<db parent>/calibration.json` | FS | |
| Compiled bundles | `build/<stem>.herm` | FS | Compiler artifact |
| Logs / temp / cache | `build/uploads/` temp files, OS temp | FS | See §5 |

Full localStorage key set **[verified]**: `hermeneia_investigation_v1`,
`_companion_context`, `_companion_provider`, `_register`, `_reader_theme`,
`_focus_scroll`, `_machine_lens`, `_reader_banner_dismissed`, `_fieldnotes_last`,
`_active_bp_id`, `_active_plan_id`.

---

## 2. Canonical vs derived  [verified]

The architecture's core promise is that canonical records are immutable and
everything else is traceable back to them.

- **Canonical source / import**: `source_documents`, `source_extractions` — the
  exact parser output, never rewritten.
- **Canonical extraction-derived**: `observations` (+ terms) — immutable.
- **Reader projections**: the drop-cap-merged reading view (issue #62) — a
  disposable display projection; it never mutates `source_extractions`.
- **User-authored**: `reader_highlights`, `investigation_log` (Field Notes),
  `observation_reviews`, `inquiry_notes`, the governing question (browser).
- **Machine suggestions**: `proposed_interpretations`, page-brief machine
  observations, Companion responses — proposals, not record until adopted.
- **Adopted machine output**: an interpretation accepted into `interpretations`,
  or Companion text saved as a Field Note.
- **Compiled (runtime, derived)**: synthesis packet, lineage — deterministic,
  provider-free, no canonical object created (`compile_synthesis_packet`).
- **Evaluation (runtime, derived)**: scorer verdicts + report — read-only over
  the packet; `canonical_evidence_modified: false` by construction.

Rule of thumb: **DB rows in `source_*`/`observations` are canonical; nearly
everything else is either your authorship or a derivation you can regenerate.**

---

## 3. What leaves the machine  [verified]

Two paths call external providers: the **Companion** (`/api/companion/ask`) and
**Artist rendering** (blueprint → report generation).

**Nothing is sent automatically.** A provider call happens only when you:
1. choose a provider (Anthropic, OpenAI, Grok/xAI, Gemini, or local Ollama), and
2. take an explicit action (Ask / Generate).

Choosing the **Stub** provider performs no AI call at all.

### Companion context gates  [verified] (`app.py:5933–6010`)

Context is assembled **only from the boxes you check** (`context_flags`):

| Flag | What is sent | Bound |
|------|--------------|-------|
| `governing_question` | Your governing question text | — |
| `selected_passage` | The passage you selected | — |
| `current_page` | The current page's extracted text | first 6000 chars |
| `saved_highlights` | Your saved highlights + notes + questions | up to 20, 160 chars each |
| `reading_trail` | Pages-read counts / trail summary | — |

Plus the message you type. So yes — **source text, highlights, field-note-style
notes, questions, and your governing question can be sent to a provider**, but
each only when its box is checked and you press Ask. Unchecked context is not
sent; a checked-but-empty context is reported as "requested, but none set" and
sends nothing.

**Local models stay local** [verified]: Ollama uses `OLLAMA_HOST` (a local
service); no API key leaves for the local path.

**[recommendation]** Surface the exact outbound payload preview before an
Ask/Generate, so "what leaves" is visible at the moment of sending, not only in
this doc.

---

## 4. Secrets  [verified]

Provider keys are read from environment variables, passed straight to the SDK
client, and **never written to the database or any Hermeneia file**:

- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`, `GEMINI_API_KEY`
- `OLLAMA_HOST` (local service location, not a secret)

Findings:
- Keys are held in process memory only (`os.environ.get(...)` at client
  construction, `artist_providers.py`). **[verified]**
- No key is persisted to `*.db`, `localStorage`, or a config file. **[verified]**
- **[recommendation / follow-up]** Audit log/exception paths to guarantee a key
  can never be echoed in an error message or stack trace surfaced to the UI.
- **[recommendation]** Ship a `.env.example` (keys blank) and confirm `.env` is
  git-ignored, so setup never encourages committing a real key. (`.gitignore`
  already ignores `*.db`, `build/`, `uploads/`, `__pycache__/`.)

---

## 5. What can be lost  [verified risks]

Ordered by likelihood × surprise:

1. **Governing question's authoritative copy is browser-only.** The
   investigation (thesis, purpose, lenses) lives in
   `localStorage['hermeneia_investigation_v1']`. It is *incidentally* snapshotted
   into `investigation_log.governing_question` **only** when you save a Field
   Note carrying it (`app.py:6089`) — so a user who set a question but saved no
   field notes has it **only in the browser**. Clearing browser data, switching
   browsers, or private mode loses the authoritative copy; highlights and Field
   Notes survive in the DB. **High.**
2. **Companion transcript is never persisted.** `_cmpTranscript` is an in-memory
   array; a reload or navigation discards the conversation. Only text you
   explicitly save (as a Field Note) survives. **Medium.**
3. **Single local SQLite file, git-ignored.** Everything canonical + authored is
   in `build/hermeneia.db`. It is not backed up, not committed, and a deleted
   `build/` directory takes all of it. **High impact.**
4. **Uploaded PDFs kept under randomized temp names.** Originals are saved to
   `build/uploads/<stem>_<rand>` (temp file, `delete=False`). They persist, but
   the mapping to a clean filename lives in the DB — losing the DB orphans the
   files. **Medium.**
5. **Runtime-only derivations.** Synthesis packet, lineage, and evaluation
   reports are recomputed on demand — safe to lose (regenerable), *provided* the
   underlying DB records survive.
6. **Worktree confusion.** Multiple git worktrees exist under
   `.claude/worktrees/`; a `build/` in the wrong worktree can look "empty."
   Confirm which working directory's `build/` is live. **Low, but real.**
7. **Schema drift / migrations.** `schema_version` exists; a DB created by an
   older/newer schema than the running code is a corruption risk. **Low.**

---

## 6. What can be exported or backed up

**[verified]** There is **no user-facing "export my workspace" command or API**
found. The compiler emits `.herm` bundles (`build/<stem>.herm`) but these are
compilation artifacts, not a study export. The synthesis packet is retrievable
as JSON via `/api/study/compile` but is a derivation, not a full backup.

**Minimum safe backup strategy today [recommendation]:**
- Back up the whole `build/` directory (the DB **and** `uploads/`) together.
  They are only meaningful as a pair (see §5.4).
- Because SQLite is a single file, `cp build/hermeneia.db backups/…` while the
  app is idle is a valid snapshot; include `uploads/`.

**[recommendation / follow-up]** Add an explicit export: a workspace archive
(DB + uploads + a manifest) and/or a per-investigation JSON export (governing
question + field notes + highlights + synthesis packet + lineage). The lineage
work (#62) already makes such an export self-describing.

---

## 7. What can be deleted  [verified]

Existing delete paths:
- Reader highlight: `DELETE /api/reader/highlights/<id>` **[verified]**
- Inquiry note: `DELETE /api/observations/<id>/inquiry/<note_id>` **[verified]**
- Documents can be **muted / excluded** (`excluded_from_analysis`) but this is a
  boundary flag, **not deletion** — the rows and files remain.

Missing / gaps **[recommendation]**:
- No delete for **source documents** (rows + the `uploads/` file).
- No delete for **Field Notes** found in the API surface reviewed.
- No delete/clear for **Companion records** (they aren't persisted anyway).
- No **"delete workspace"** / reset that clears the DB + uploads + localStorage.
- No **retention policy** for temp files in `build/uploads/` (failed or orphaned
  uploads).

---

## 8. What the UI should eventually show  [recommendation]

A future **"Storage & Privacy"** page, phrased as reassurance, answering:

- **Your work is stored here** — show the resolved DB path (`/api/setup/state`
  already returns `db_path`) and the data folder (`build/`).
- **This data is local** — DB + uploads never leave the machine on their own.
- **This may be sent to a provider only when you choose** — list the context
  gates from §3 and the currently selected provider.
- **Export backup** — download a workspace archive (§6).
- **Delete workspace** — clear DB + uploads + localStorage, with confirmation.
- **Clear provider settings** — reset provider choice + context flags.
- **View database path** / **Open data folder** — the two locations in §1.
- **Heads-up: your governing question is stored in this browser** — until §5.1
  is addressed, tell the user plainly.

---

## 9. Constitutional alignment

This audit supports, and is bounded by, the existing invariants:
- Canonical evidence is immutable; derivations are traceable (§2, lineage #62).
- The machine points; the steward decides — machine output is not record until
  adopted (§2).
- Corpus boundary integrity — excluded documents are flagged, not silently used
  (`corpus_boundary` scorer, `test_corpus_scope_boundary.py`).

The audit adds a fourth expectation to make explicit: **the user should be able
to see, export, and delete their own work, and know what leaves the machine.**

---

## 10. Recommended follow-up issues

1. **Persist the governing question** to the DB (or make its browser-only nature
   explicit in the UI). Addresses §5.1 — highest-value fix.
2. **Workspace export** — archive (DB + uploads + manifest) and per-investigation
   JSON export. §6.
3. **Delete/reset controls** — source-document delete (row + file), Field Note
   delete, "delete workspace," temp-upload retention. §7.
4. **Storage & Privacy UI page** — surface path, local-first guarantee, context
   gates, export/delete. §8.
5. **Outbound payload preview** before any provider Ask/Generate. §3.
6. **Secret-safety hardening** — verify keys can never be logged; add
   `.env.example`. §4.
7. **Optional Companion transcript persistence** (opt-in), so conversations
   aren't silently lost. §5.2.

None of these are implemented here. This document is the map; the routes come
next, one small PR at a time.
