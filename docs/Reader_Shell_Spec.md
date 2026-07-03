# The Reader Shell — Implementation Specification

*Recorded: 2026-07-03. Design pass only — no code in this PR. Reconciles the merged design record (PR #30 / FUTURE_ARCHITECTURE_NOTES: Workflow-Cycle Shell wireframe v4), issue #12 and its live-testing comments (Field Notes footer, machine page brief + lens, bucketing-before-interpretation), issue #26 (reduce pipeline overwhelm), and everything shipped in PRs #22–#27 into one coherent shell.*

**The goal is to make Hermeneia feel obvious.** Not simpler — obvious: at any moment, the reader knows where they are, what the next meaningful act is, and how to get back to the book.

---

## 0. Governing statement and principle map

> **The book is the workspace. Everything else is a tool at its edges.**
> Tools change; the book never moves. The machine points; the human decides.
> The question is the compass; the shell keeps it in view.

The twelve principles, each with its mechanism in this spec:

| # | Principle | Mechanism (region) |
|---|-----------|--------------------|
| 1 | Reader is always the center | Region B — the Book owns the center column at every breakpoint; every other surface is a rail, tray, bar, or overlay |
| 2 | Thesis/question always visible above the book | Region A — Question Bar |
| 3 | Workflow cycle at the bottom; steps change tools, not the book | Region G — Cycle Bar swaps the Tool Rail and opens overlays; never navigates away |
| 4 | Companion always available everywhere | Region E — dockable Companion (docked panel ↔ floating bubble), shell-level, not Reader-only |
| 5 | Field Notes = Reader footer / footnote tray | Region F — the tray; the timed capture prompt merges into it |
| 6 | Machine observations = page brief + optional lens | Region C — Page Brief accordion + Machine Lens toggle |
| 7 | Observation bucketing happens while reading | Regions C+D — brief actions and selection actions feed the Evidence Bucket in the Tool Rail |
| 8 | Provider/model selection = interpretation settings | Interpretation Sheet (overlay), settings step *after* the bucket exists; Connections → global Settings |
| 9 | Side rails compact and glanceable | Region D — one Tool Rail of chips/counts/one-line glances; details on tap |
| 10 | Large explanatory text collapses behind Help | Help drawer (`?`), absorbing per-screen guide blocks, Guide, Constitution |
| 11 | Active page identity always obvious | Region A shows document · page X of Y at all times |
| 12 | Return to Reading always available | Persistent control in Region A whenever the book is not the focused surface |

---

## 1. Shell specification

The shell is five fixed regions plus two floating elements. Nothing else exists at the top level; every current screen either becomes a region, an overlay summoned by the Cycle Bar, or a drawer.

```
┌─ A · QUESTION BAR ────────────────────────────────────────────────┐
│  Hermeneia · [Current Question, 1 line, expandable]               │
│  Gatsby · p.4 / 193 · [Return to Reading]   [?] [⚙] [Companion ◉] │
├──────────────┬─────────────────────────────────────┬──────────────┤
│              │  C · PAGE BRIEF (accordion)         │              │
│  (breathing  │  ▸ The machine thinks these may     │  D · TOOL    │
│   margin /   │    matter on this page · 9 obs      │      RAIL    │
│   optional   ├─────────────────────────────────────┤  (step-      │
│   session    │                                     │   scoped,    │
│   glance on  │  B · THE BOOK                       │   compact)   │
│   wide       │  warm paper / dark · Focus Scroll   │              │
│   screens)   │  selection toolbar · machine lens   │  E · COMPANION│
│              │                                     │  (docked or  │
│              │                                     │   floating)  │
├──────────────┴─────────────────────────────────────┴──────────────┤
│  F · FIELD NOTES TRAY  · "+ Field note"  (expands upward)         │
├────────────────────────────────────────────────────────────────────┤
│  G · CYCLE BAR  Question→Read→Segment→Ask→Compare→Steward→        │
│                 Build→Render→Audit→Trace     (click = tools swap)  │
└────────────────────────────────────────────────────────────────────┘
```

Floating: the Companion bubble (when undocked) and transient overlays (Interpretation Sheet, Steward Sheet, Trace Sheet…), which slide over the book, dimming it — the book remains visible beneath, honoring "changes tools, not the book."

---

## 2. Region-by-region layout

### A · Question Bar (top, persistent everywhere)

- Left: wordmark (small) · **Current Question**, one line, click-to-expand (the clamp behavior already shipped). If no question yet: *"What are you trying to understand?"* as a quiet input (the question card's behavior, promoted).
- Center-right: **active page identity** — `The Great Gatsby · p.4 of 193` — always present, even under overlays (principle 11). Tapping it is **Return to Reading** (principle 12); the same control renders as an explicit `← Return to Reading` button whenever an overlay or non-book surface has focus.
- Far right: `?` Help drawer · `⚙` Settings (Connections/providers/models/#29 live here) · Companion dock toggle.
- Absorbs: the current `page-thesis` header, the question card's ask/edit behavior, `Guide/Constitution/Lineage/Connections` nav buttons (→ Help and Settings), and the stage prev/next bar (deleted; the Cycle Bar replaces it).

### B · The Book (center, dominant)

- Everything already shipped: warm paper / dark modes, Focus Scroll, selection toolbar (Highlight · + Note · ? Question · ✦ Concept · → Observation · ⁘ Ask · ▶ Read), pending-capture marking, register-gated locators.
- Adds only: the **Machine Lens** rendering layer (subtle inline marking of machine-observed segments, CSS Custom Highlight API — same non-destructive technique as pending-capture; visually distinct from human highlights: human = accent fill, machine = dotted underline/soft wash). Lens off by default; toggled from the Page Brief or Tool Rail.
- Reading Tools dock (Read aloud/Stop/Focus/Text) dissolves into Tool Rail chips on the Read step; read-selection stays on the selection toolbar.

### C · Page Brief (accordion, directly above the book)

- Collapsed (default): `▸ The machine thinks these may matter on this page · 9 observations · 1 possible boilerplate`.
- Expanded: grouped rows (likely important / repeated language / thesis-relevant / possible boilerplate / unclear), each with steward actions: **Approve · Edit · ? Question · Reject · Boilerplate · Defer**, plus `show in page` (flashes the segment via the lens).
- Copy rule (verbatim, constitutional): *"Hermeneia noticed these possible points of attention. Read the page yourself, then approve, edit, question, or reject them."*
- Approve/Reject/Defer feed the **Evidence Bucket** (see D) and the ObservationRuling store when it lands (issue #11); until then, the safest existing pattern per the Codex prompt on #12.
- Absorbs and retires: the "Machine Observations — This Page" sidebar list as a primary surface.

### D · Tool Rail (single right rail; contents swap with the cycle step)

Always compact: chips, counts, one-line glances; anything longer opens a sheet. Per step:

- **Read**: session glance (`Ch.1 · 42% · continue → p.5`) · trail counts (`7 ✎ · 3 ? · 2 ✓`) · Reading Tools chips (Aloud / Focus Scroll / Paper / Text) · Machine Lens toggle.
- **Segment**: mark-as chips (theme · question · tension · term — the wireframe's chips) · recent highlights (3, one line each) · concept list glance.
- **Ask**: open questions (count + top 3) · "+ attach question to selection."
- **Compare**: my highlights vs machine observations for this page (counts + `open comparison sheet`) · Pattern View entry (search chip).
- **Steward**: pending decisions count · `open Steward Sheet` · evidence-status legend (supports/complicates/challenges/redirects).
- **Build / Render / Audit / Trace**: each shows readiness ("1 established interpretation · bucket: 6 items") and one primary action that opens its Sheet.
- The **Evidence Bucket** is pinned at the rail's foot on every step: `Bucket · 6 items → Interpret`. Bucketing while reading (principle 7) means: approve in the brief, promote a highlight, or tag a selection — each lands here, visibly.

### E · Companion (dockable, shell-level)

- Two states: **docked** (right panel under/beside the Tool Rail) and **floating bubble** (bottom-right, Clippy's heir — opens a compact chat card). State persists; available on every surface including overlays (principle 4).
- Everything shipped stays: explicit context checkboxes, `context used` disclosure, provider picker incl. Stub, ⁘ Ask from selection. Project Lineage becomes the seventh context checkbox when its store exists (#10).
- The bubble never speaks unprompted (Article 7); at most a quiet badge when it has a pending proposal from an explicit ask.

### F · Field Notes Tray (the Reader footer)

- Collapsed: a slim bar under the book: `+ Field note — What is your current understanding?`
- Expanded (upward): lane pills (About the text / About Hermeneia) · understanding textarea · pressing-questions behind a small disclosure · Keep. Exactly the shipped composer, relocated.
- The timed capture prompt (shipped footer bar) **merges into the tray**: when the disclosed rule fires, the tray glows gently and pre-opens its placeholder — one surface, not two.
- Mobile: the tray sits directly above the keyboard — the thumb zone (the point of the correction).
- Absorbs and retires: the Field Notes side panel and the separate `fln-footer` bar.

### G · Cycle Bar (bottom, persistent)

- Ten nodes: `Question · Read · Segment · Ask · Compare · Steward · Build · Render · Audit · Trace`, states: done / current / available (the wireframe's ring vocabulary). One-line caption under the bar names the current act ("Read the corpus. Mark what matters.").
- **Clicking a node swaps the Tool Rail and (for the pipeline-tail steps) offers its Sheet. It never unmounts the book.** Sheets slide over a dimmed book; `Esc`/Return-to-Reading closes them.
- Question node: opens the question editor (Refine / Fork later).
- Replaces: the top pipeline nav, `_STAGE_ORDER` prev/next marching, the VIEW CYCLE mini nav, and the dashboard's stage grid as *navigation* (the dashboard's narration content migrates to #9's Where-You-Are, glanceable in the rail).

### Sheets (overlays summoned by the cycle; the book stays beneath)

- **Comparison Sheet** (Compare): page-by-page human ↔ machine reconciliation (issue #12 part 3: link / adopt / reject / gap).
- **Interpretation Sheet** (Steward/Build entry): the bucket's contents → *then* interpretation settings (providers, response mode, boundary) → run. This is the bucketing-before-settings correction from #12's live synthesis: settings appear only after the curated bucket exists (principle 8).
- **Steward Sheet** (Steward): proposals awaiting judgment — the "judgment desk" hierarchy from the walkthrough audit.
- **Build / Render / Audit / Trace Sheets**: today's Architect, Reports, Critic, Lineage screens, presented as overlays with their existing loaders — absorbed, not rewritten.

---

## 3. Desktop behavior (≥ 1200px)

- All regions visible. Book column 680–760px measure, centered between rails; on very wide screens (≥1600px, the "reader much bigger" amendment) the book may widen to ~840px with Focus Scroll's clamp scaling accordingly.
- Left margin: breathing room; on ≥1440px an optional **Session glance** (Where You Are digest — 4 lines max) may occupy it, collapsible to nothing.
- Tool Rail 280–300px; Companion docks beneath it or floats.
- Sheets open as right-anchored panels (60% width max) over the dimmed book.
- Keyboard: `Esc` = Return to Reading; `⌘K` reserved for the future command palette (recorded, not built).

## 4. Tablet behavior (768–1199px)

- Book full-width minus 24px margins. Tool Rail collapses to an **edge tab strip** (icons + counts); tapping opens the rail as a slide-over.
- Companion defaults to bubble. Page Brief and Field Tray unchanged (they're vertical-stack friendly).
- Cycle Bar condenses: current step full label, others icons; horizontal scroll if needed.
- Sheets become full-height slide-overs (85% width), book edge visible.

## 5. Mobile behavior (< 768px)

The app currently has **no mobile breakpoint** (verified finding: the reading column crushes below ~500px). The shell fixes this by decree:

- **Only Region A (one line: question · page identity), Region B, and Region F exist by default.** The book is the screen.
- Cycle Bar becomes a bottom **sheet handle** (current step name + grip); swiping up reveals the ten steps; choosing one opens its tools as a bottom sheet.
- Page Brief: collapsed pill above the book; expands full-screen.
- Field Tray: pinned above the keyboard; opening it scrolls the book to keep the last-read line visible.
- Companion: bubble only.
- Selection toolbar: OS-selection-anchored action row (same six actions, two rows if needed).

## 6. Interaction flow — one complete reading pass

1. **Arrive.** Question Bar shows the compass and `Gatsby · p.4 of 193`. The Book is already there (first-run flows from #20 land here). Cycle Bar: Read is current.
2. **Glance the brief.** `▸ 9 observations · 1 possible boilerplate` — expand, reject the Planet-eBook artifact (ruling recorded), leave the rest for after reading. Collapse.
3. **Read.** Focus Scroll carries attention; a phrase catches — select → toolbar → `? Question`, form opens with the passage held (pending mark), compass line beneath; save. Trail count ticks in the rail.
4. **Segment.** Cycle: Segment. Rail swaps to mark-as chips; tag the epigraph `tension`. Toggle Machine Lens briefly to see what the machine marked near it; one machine observation matches your reading — `Approve` from the brief → **Bucket · 3 items**.
5. **Ask/Compare.** Cycle: Compare. Rail shows `yours 4 ↔ machine 9`; open the Comparison Sheet, link one pair, note one gap, reject one duplicate. Book dims but never leaves. `Esc` — back to reading.
6. **Field note.** The tray glows (rule satisfied): *"What is your current understanding?"* — two sentences into the corpus lane; Keep. Reading continues on the same breath.
7. **Steward → Interpret.** Days later, bucket at 9: Cycle: Steward → Interpretation Sheet shows the bucket first, *then* asks providers/mode/boundary → run → proposals arrive in the Steward Sheet → establish two, contest one (rationale captured).
8. **Build → Render → Audit → Trace** — each a Sheet over the book; Trace ends at the passage where it began. **Return to Reading.** The cycle repeats as the thesis sharpens — `Refine` on the Question Bar records the evolution.

Every step of Notice → Mark → Name → Question → Cluster → Interpret → Challenge → Revise → Ratify → Render happens without the book ever leaving the screen.

## 7. Panel disposition table

| Current surface | Fate |
|---|---|
| Top pipeline nav (Corpus…Critic) | **Retire** → Cycle Bar |
| Stage prev/next bar, VIEW CYCLE mini | **Retire** → Cycle Bar |
| Guide / Constitution nav buttons | **Move** → Help drawer (content intact; #17 rewrites it separately) |
| Connections nav + screen | **Move** → Settings (⚙); providers become Interpretation-Sheet settings (#12 synthesis); model management (#29) lives here |
| Dashboard / onboarding pipeline grid | **Merge** → Where-You-Are glance (rail/left margin) + Question Bar; first-run Welcome (#20) unchanged |
| Setup ("Your Question") | **Merge** → Question Bar expand (Sharpen fields intact) |
| Corpus screen: search + Pattern View | **Move** → Compare step (rail entry + full Sheet); Pattern View unchanged inside it |
| Corpus screen: upload/scope admin | **Move** → Settings › Sources (library, not home) |
| Lab | **Merge** → Interpretation Sheet (bucket first, settings second) |
| Review | **Merge** → Steward Sheet |
| Architect / Reports / Critic / Lineage screens | **Absorb** → Build / Render / Audit / Trace Sheets (existing loaders, overlay presentation) |
| Reader: doc picker | **Move** → page-identity dropdown in Question Bar |
| Reader: Reading Trail panel | **Collapse** → rail glance; details in a sheet |
| Reader: question card | **Merge** → Question Bar |
| Reader: Field Notes panel + fln-footer | **Merge** → Field Notes Tray (F) |
| Reader: Companion panel | **Move** → dockable Companion (E) |
| Reader: Highlight Inspector | **Keep** — anchored in the rail area on selection (unchanged behavior) |
| Reader: Saved Highlights list | **Collapse** → rail glance + sheet |
| Reader: Machine Observations list | **Retire as primary** → Page Brief + Lens (C) |
| Reading Tools dock | **Merge** → Read-step rail chips (read-selection stays on the selection toolbar) |
| Per-screen "What is…" guide blocks | **Collapse** → Help drawer |

Nothing is deleted from the record; retired surfaces disappear from navigation, their capabilities relocated. All e10 screen ids and loaders remain callable during migration.

## 8. Migration plan — minimal breakage

**Mechanism: the shell is additive, then absorbing.** A `shell-v2` body class gates the new layout; every existing screen keeps working underneath until the phase that absorbs it. No data changes anywhere — this is entirely presentation. Codex's in-flight `body.reader-mode` / workspace-drawer work (#26 WIP) is the seed of exactly this and should be treated as Phase 1 in progress, not parallel effort.

- **Phase 1 — Frame** (flag off by default): Question Bar; Cycle Bar (rendering + rail swapping only — nodes for Build→Trace still `e10Go` to their screens); Return to Reading. Old nav still present.
- **Phase 2 — Reader edges**: Field Tray (Codex-queued); Page Brief + Lens (Codex-queued); Tool Rail v1 (Read/Segment steps); Companion dock/bubble.
- **Phase 3 — Sheets**: pipeline-tail screens presented as overlays; old top nav hidden behind the flag; flag defaults ON, `Legacy shell` toggle in Settings for one release.
- **Phase 4 — Consolidation**: Settings absorbs Connections/Sources; Help drawer absorbs guides; dashboard merges into Where-You-Are; retire stage bars.
- **Phase 5 — Responsive**: tablet + mobile breakpoints; remove legacy toggle.

Rollback at any phase = flip the flag. Every phase leaves the test suite green and the Reader loop unbroken; the standing persistence regression tests guard the record throughout.

## 9. Prioritized implementation sequence (small PRs)

| # | PR | Size | Depends on | Owner note |
|---|----|----|------------|-----------|
| 1 | Question Bar (question + page identity + Return to Reading; question card merges) | S | — | |
| 2 | Field Notes Tray | S | — | **Codex-queued (#12)** |
| 3 | Page Brief + Machine Lens | M | — | **Codex-queued (#12)** |
| 4 | Cycle Bar + Tool Rail v1 (Read/Segment), stage bars hidden behind flag | M | 1 | |
| 5 | Evidence Bucket (rail foot; brief/selection actions feed it) | M | 3,4 | pairs with #11 rulings |
| 6 | Companion dock ↔ bubble | S | 1 | restyling note (Atlas) applies here |
| 7 | Comparison Sheet (Compare step) | M | 4 | issue #12 part 3 |
| 8 | Interpretation Sheet (bucket-first Lab absorption) + Steward Sheet | L | 5 | |
| 9 | Build/Render/Audit/Trace as Sheets; flag ON by default | M | 4 | |
| 10 | Settings consolidation (Connections, Sources, #29 model mgmt UI) | M | 9 | |
| 11 | Help drawer (guides collapse; #17's rewritten Guide lands here) | S | 9 | after #17 |
| 12 | Tablet + mobile breakpoints | M | 2,3,4 | fixes the no-breakpoint finding |
| 13 | Retire legacy shell | S | all | |

Sequencing logic: PRs 1–6 are independent-ish and each visibly improves the live app; the Sheets (7–9) are the structural absorption; 10–13 are consolidation. At no point is the Reader loop — read, notice, ask, keep — interrupted.

---

*Constraints honored: no index.html changes, no features, no Guide rewrite, no provider architecture. This document is the deliverable.*
