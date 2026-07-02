# Reading Tools & Shell Triage — July 7 Window

*Recorded: 2026-07-02. Triage of the full UI walkthrough audit (see `UI_Walkthrough_Audit_2026-07-02.md`, preserved verbatim) into verified root causes and a July 7 build plan. Every bug claim below was verified against the running app and the code before being logged — findings carry root causes, not just symptoms.*

---

## Verified root causes

### 1. "Text Large" toggle does nothing — CONFIRMED, root cause found

The toggle mechanism **works**: `a11yToggle('textLg')` applies `body.a11y-text-lg` correctly (verified live). The bug is in the CSS it triggers ([index.html:1531–1536](../hermeneia/web/static/index.html)):

- The rule targets `.e10-text`, `.obs-card p`, `.obs-raw-text`, and `p` — but the Reader's page text renders in **`<div>` blocks inside `.cr-page-view`**, which match none of the selectors. Measured live: Reader text is 16px before and after toggle. Zero effect exactly where large text matters most.
- The rule's magnitude is stale: it sets **15.5px** against a body base of **18px** — where it does match, "Large" can *shrink* text. The rule was written for an older, smaller base font and never updated.

**Fix:** retarget to the reading surfaces (`.cr-page-view` and its blocks, `.cr-saved-passage`, saved-highlight text, `.e10-text`) with relative sizing (~1.25em equivalent, e.g. 20px/1.85 on an 18px base), leaving admin/table UI untouched — per the audit: readability of the source, not enlarging the whole system.

Joseph's bug note, preserved:

> Bug: Access Tools "Text Large" toggle appears to change state but does not visibly change reader text size.
> Impact: Accessibility affordance is nonfunctional. This weakens trust in the Access Tools dock and harms users who rely on larger text for close reading.
> Expected: Toggling text size should visibly increase the source text / Reader text blocks, ideally without enlarging the entire system UI.
> Suggested fix: Bind the toggle to a persistent class on the app or Reader container, e.g. `reader-large-text`, and apply font-size/line-height changes to source text, selected passages, and reading panels.

### 2. Calibration override defaults to "approved" — CONFIRMED

[index.html:4813–4818](../hermeneia/web/static/index.html): the override `<select>`'s first option is `approved` with no placeholder, so the browser preselects it. Beside "Calibration: ○ untested," the page visually asserts *untested but approved* — a trust-language contradiction in the governance layer, exactly as the audit diagnosed.

**Fix:** prepend a disabled placeholder (`Choose override…`), reject Apply until a real choice is made (the steward note is already required — good), relabel button "Override" → "Manual override," and use the audit's option labels ("Approve for this role," "Use with caution," "Reject for this role," "Reset to untested").

### 3. "The whole app is one long scroll" — PARTIALLY CORRECTED

Measured live in both default and expert states: **exactly one screen is visible at a time** (`.e10-screen { display: none }` / `.active { display: block }` works; visible-screen check returned one id; page height ~2,200px, not tens of thousands). The audit's page-context readings included `display:none` DOM content, which reads as one long document to text-extraction tools but is not what the viewport renders.

**However, the felt diagnosis stands, with different causes.** What actually produces the "whole operating system at first glance" feeling:

- **Duplicated navigation systems**: top nav (7 pipeline steps) + Guide/Constitution/Lineage buttons + "VIEW CYCLE" + the stage prev/next bar (showing neighboring stage names) + per-screen "Next:" CTAs — five control systems visible at once.
- **"Screen N — X" section labels** ([index.html:1951–2094](../hermeneia/web/static/index.html)): six sections carry internal wizard/debugger labels ("Screen 1 — Corpus Explorer").
- **The Working Thesis header** renders the full question paragraph at display size on every screen.
- **Connections is a top-nav peer** of the interpretive flow.
- **Per-screen guide blocks** ("What is the Corpus?") are fully expanded at the bottom of each screen.

So the P0 is not a shell/routing refactor (the isolation mechanism exists and works) — it is **nav consolidation, label cleanup, and header discipline**. Substantially cheaper, same felt result. The DOM-carries-everything fact is worth one further check post-demo (assistive-tech exposure), but `display:none` content is excluded from the accessibility tree.

### 4. Access Tools dock naming — CONFIRMED

Dock header "Access Tools" ([index.html:1608](../hermeneia/web/static/index.html)); collapsed pill uses ♿ ([index.html:1655](../hermeneia/web/static/index.html)). Joseph's note, preserved:

> UX issue: Accessibility dock uses ♿ icon, which implies disability-only affordances. Replace with a neutral reading/attention icon such as "Aa," "◐," or "✦" and rename dock from "Access Tools" to "Reading Tools" or "Attention Tools."

Decision rule from the audit: **"Attention Tools"** if Focus Mode becomes guided next-step discipline; **"Reading Tools"** while it remains read-aloud + text size + dimming. For July 7 the dock is renamed **Reading Tools** (icon: Aa); the Focus Mode upgrade is post-demo work, and the name can graduate with it.

### 5. Vocabulary collision: pipeline stage "Read" vs. Reader — CONFIRMED

The dashboard pipeline labels stage 05 "Read" (render the report) while "Reader" is the close-reading workspace. Two different acts, one word. Fix: stage 05 → **"Render"** (frontend `fallbackPipeline` label; the server's `/api/project/summary` labels are a small backend copy follow-up).

---

## July 7 build plan — branch `fix/july7-reading-tools-and-trust-language`

Ordered commits, all frontend, all low risk:

1. **fix: Text Large targets the reading surfaces** — retargeted selectors + relative magnitude (root cause #1). Smoke test: measured font-size change in `.cr-page-view` on toggle; admin tables unchanged.
2. **fix: calibration override requires an explicit choice** — placeholder default + Apply validation + relabels (root cause #2).
3. **fix: Reading Tools dock naming** — "Access Tools" → "Reading Tools," ♿ → Aa, popup "Read" → "Read selected text" (root cause #4; the read-selection feature itself is Keep/Strengthen per audit).
4. **fix: remove internal wizard labels** — "Screen N — X" → user-facing names per audit ("Search the Text," "Interpret a Passage," "Review Interpretations," "Fidelity Audit," "Trace Lineage," "Build the Argument"), respecting the two-register pattern (researcher names available at expert register).
5. **fix: Current Question header discipline** — "Working Thesis" → "Current Question," clamped to 2 lines with expand (audit P0).
6. **fix: pipeline stage "Read" → "Render"** — frontend labels (root cause #5).

**Build-if-fast:** action-language "Next:" buttons ("Interpret selected passage →" instead of "Next: Interpretation Lab →").

## Post-demo theme (next spec, not this window)

The audit's larger redesign — held until after July 7, in rough order of leverage:

- **Focus Mode as next-step discipline**, not dimming: "hide everything except the current task, the current question, and the next valid step." Constitutionally grounded in Attention Stewardship. (Audit's definition preserved in the raw document.)
- **Connections demoted to a settings surface** ("Model Connections"), provider cards as summaries, role matrix behind disclosure, roles legend.
- **Nav consolidation**: primary Read/Search/Lab/Reports/Lineage; Corpus-admin/Architect/Critic/Connections/Constitution/Guide behind "More."
- **Per-page hierarchy passes** (each fully specified in the raw audit): Lab as "quiet proposal room" (selected passage as hero, providers behind Advanced); Review as "judgment desk" (proposal first, pipeline actions after decision); Architect readiness gate ("establish interpretations first"); Critic as button-not-CLI ("Run fidelity audit"); Corpus split into Sources/Search; Guide and Constitution progressive disclosure (collapse Why/How-enforced; Supremacy Clause block).
- **Lineage grows Reader Lineage**: the page should show the authorship of attention (pages read → highlights → notes → questions → revisions) even before any report exists — "a history of how understanding formed." This is the Witness surfacing in the UI and belongs in FUTURE_ARCHITECTURE_NOTES as a design note when picked up.

## Deferred / recorded only

Full nav inversion (question-first shell), Help drawer system, multi-entry lineage tracing, provider calibration UX beyond the default fix, guide rewrite ("How Hermeneia Protects Understanding"), Constitution ceremonial close, "3,443 observations" → "passages" vocabulary sweep.
