# Onboarding Implementation Spec — July 7 Window

*Recorded: 2026-07-02. Produced under the Interaction Constitution (see FUTURE_ARCHITECTURE_NOTES.md § "The Interaction Constitution") with the 2026-07-02 constitutional UI audit findings as binding constraints.*

**Goal:** The user enters with a text and leaves with a better, grounded question.

**Flow being replaced:** `Declare thesis → purpose/lenses/falsifiability → then read`
**Constitutional flow:** `Read → notice → ask → sharpen`

**Hard constraints honored:** no schema changes; no new ontology objects; no broad redesign; build around the existing highlight form; plain-language prompts promoted, scholarly terms to expert register; no urgency or completion pressure; no hidden readiness scoring.

---

## 1. Screen sequence

```
FIRST RUN, documents present (the demo path):
  Reader (close reader, primary doc auto-opened, first-run banner)
    → notice via existing highlight form (unchanged)
    → Question card in reader sidebar (always present, quiet)
    → [user saves a question]
    → optional "Sharpen your question →" opens Setup (relabeled)
    → Dashboard becomes home thereafter

FIRST RUN, no documents:
  Corpus (upload) with read-first copy → Reader → (as above)

RETURNING USER (question already saved):
  Dashboard (unchanged routing)
```

No screens are added or removed. Setup is demoted from gate to elective; the Reader is promoted to front door.

## 2. Exact user-facing copy

**Boot routing — first-run banner** (top of reader workspace, only when `!invLoad()`, dismissible, never returns after dismissal or after a question is saved):

> **Read first.** Select any passage that catches your eye — everything you notice is kept, nothing is summarized away. When you're ready, we'll help you shape what you've noticed into a question worth investigating.

**Question card** (reader sidebar, below the trail block; always present; static — no pulse, no badge):

- Header: `Your question`
- Before any question is saved, body:
  > What are you trying to understand about this text? You can answer now, or keep reading until a question forms.
  - After ≥ 2 saved highlights, prepend (count comes from the visible trail — no hidden state):
  > You've noticed {n} passages.
  - Textarea placeholder: `I want to understand…`
  - Button: `Keep this question`
- After a question is saved, body shows the question text plus two quiet links:
  > `Sharpen it →`  ·  `Edit`

**Highlight save confirmation** ([index.html:5535](../hermeneia/web/static/index.html)):
- `✓ Highlight saved.` → `✓ Kept — added to your trail.`
- `✓ Saved as observation candidate.` → `✓ Kept as an observation candidate.`

**Setup relabeling** (universal register primary; expert register shown as small sublabel when `_expert`, reusing the `LINEAGE_VOCAB` two-register pattern as a small `SETUP_VOCAB` map):

| Universal label (primary) | Expert sublabel |
|---|---|
| Screen: `Your Question` | `Investigation Setup` |
| `What are you trying to understand?` | `Thesis` |
| `Why does this matter?` | `Purpose` |
| `What perspectives are you bringing?` | `Declared Lenses` |
| `What result would change your mind?` | `Falsifiability` |

- Required-field error: `A thesis is required before beginning.` → `One sentence is enough — what are you trying to understand?`
- Falsifiability helper: `…from "prove my thesis" into "test my thesis"` → `…from "prove my idea" into "test my idea"`
- Submit button: `Begin Investigation ↺` → `Save my question →` (expert register may keep `Begin Investigation`)
- The setup preamble ("Hermeneia does not generate questions…") is kept verbatim — it is already constitutional. When Setup is reached via "Sharpen it →", the first field pre-fills with the saved question.

**Dashboard softening** (BUILD IF FAST):
- `{n} of 6 stages complete` → `Where your investigation stands`
- Dashboard title becomes the user's question when one exists (mechanism exists: `updatePageThesis`).

## 3. State captured at each step

| Step | State | Stored where | User can inspect / correct |
|---|---|---|---|
| Read | none | — | — |
| Notice | highlight: text, page, context, note ("Why this matters"), question ("Question this raises"), relevance (default `unclear`) | server, `/api/reader/highlights` (existing) | highlight list; editable; dismiss preserves as status |
| Ask | `{thesis, created}` | localStorage `hermeneia_investigation` (existing `invSave`) | question card, page header, Setup form |
| Sharpen | `{purpose, lenses, reconsider}` merged into same record | same localStorage record | Setup form, pre-filled, editable anytime |

**Article 8 declaration:** no hidden state is introduced. The only adaptive display — the highlight count in the question card — is computed from data the user already sees in their trail. There is no readiness scoring. Banner dismissal is a single localStorage boolean.

## 4. Functions / components likely touched

1. **Boot router** — `mount(h)` tail, [index.html:2119](../hermeneia/web/static/index.html): replace `e10Go(invLoad() ? 'onboarding' : 'setup')` with: `invLoad()` → `onboarding`; else `h.document` present → `reader`; else → `corpus`. Document presence is already known at boot via `/api/health`. On any doubt, fall back to current behavior.
2. **`e10LoadCloseReader`** — inject first-run banner when `!invLoad()` and not dismissed. Auto-open of primary doc and the empty-corpus message already exist; no change.
3. **New small function `_crRenderQuestionCard()`** — renders into the reader sidebar; called from `e10LoadCloseReader` and `_crRefreshTrail` (so the count refreshes on save). Writes via existing `invSave` / `updatePageThesis`.
4. **`e10LoadSetup` + `setupSubmit`** — label/register swap via a `SETUP_VOCAB` map; error and button copy; pre-fill already works (`invLoad()` round-trip exists). The primary-corpus fail-closed check in `setupSubmit` is kept.
5. **`_crSaveHighlight`** — confirmation copy only.
6. **`e10LoadOnboarding`** — optional copy softening (BUILD IF FAST).

Not touched: schema, API, ontology, pipeline, Steward gate, corpus-boundary checks, the highlight form fields.

## 5. Smallest implementation path (ordered)

1. Setup label/register swap + error/button copy — *copy only* (~30 min)
2. Highlight confirmation copy — (~5 min)
3. Question card in reader sidebar — new DOM in a stable container, reads/writes existing localStorage (~1–2 h)
4. Boot routing with fallback — must be tested against three states: fresh DB, demo DB with documents, returning user with saved question (~1 h)
5. First-run banner — (~20 min)
6. Dashboard copy softening — (~20 min, BUILD IF FAST)

Parallel one-liner from the audit, not part of this flow but same window: truthful Pattern View copy ([index.html:3399](../hermeneia/web/static/index.html)) and expert-register persistence ([index.html:4441](../hermeneia/web/static/index.html)).

## 6. July 7 risk level per step

| Step | Risk | Why |
|---|---|---|
| Setup relabeling | **Low** | Copy and a label map; no logic |
| Confirmation copy | **Low** | One string |
| First-run banner | **Low** | Additive DOM, dismissible, gated on `!invLoad()` |
| Question card | **Low–Medium** | New DOM in the reader sidebar; only risk is layout crowding next to trail/highlight list |
| Boot routing | **Medium** | Touches the entry point; three states to test; mitigated by explicit fallback to current behavior |
| Dashboard softening | **Low** | Copy only; skip without harm if time is short |

**Demo acceptance test (the July 7 sentence, as a script):** open the Gatsby demo DB fresh → land in the Reader on the primary text → highlight a passage, write why it matters → see "✓ Kept — added to your trail" → save "I want to understand what the green light means to Gatsby" in the question card → search "green light" in Corpus → Pattern View (with truthful copy) → send to Lab → generate → Steward review → read report → inspect lineage. No step asks for anything before it is useful; nothing is lost anywhere; no screen rushes.
