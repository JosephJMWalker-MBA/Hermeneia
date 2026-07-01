# Sprint 006 — Implementation Principles

These principles emerged during implementation and should govern future sprints in the same family.

---

## Corpus Boundary Principle

**Presence is not authority.**

A source document may exist in the investigation workspace without belonging to the primary evidentiary corpus. Supporting documents may inform inquiry, commentary, context, or exploratory questioning — but their role must remain visible and durable wherever they influence interpretation.

Hermeneia therefore treats corpus role as provenance, not merely display metadata.

> **The keeper:** Corpus role is provenance, not display metadata.
> That is what the Corpus Scope Hardening sprint implemented.

---

## Connections Discipline Principle

**Configuration is provenance. Calibration is evidence. Suitability is role-specific. Connection is not permission.**

A provider's role suitability must be:
- **visible before use** — shown on the provider card before an investigation begins
- **durable after use** — recorded in generation provenance so future stewards know which provider participated
- **testable by calibration** — suitability claims are not assertions; they are conclusions from test outcomes

Do not treat `configured / available / suitable` as the same boolean.

> **The keeper:** The Connections sprint applies the same discipline to provider participation that Corpus Scope Hardening applied to document participation.

---

---

## Accessibility Dock v0.2 — Manual QA Checklist

**Visibility**
- [ ] Dock is visible on the right edge without scrolling on all main investigation screens
- [ ] Dock survives screen navigation (corpus → lab → review etc.) without disappearing
- [ ] Collapsed pill is large enough to click and shows "♿ Access" label
- [ ] Expanding from pill restores full dock

**Controls and states**
- [ ] Each button shows icon + label + state text
- [ ] Read Off → clicking Read turns it On with visible highlight and state reads "On — select text"
- [ ] Focus Off → clicking Focus turns it On, dims background content, dock stays clickable
- [ ] Text Normal → clicking Text makes reading text visibly larger; clicking again restores
- [ ] Stop is visually disabled when not speaking; enabled when speech is playing

**Read flow**
- [ ] With Read On and no text selected: clicking dock Read button shows "Select text first" in status bar
- [ ] With Read On: highlighting text shows floating Read / ✕ toolbar above the selection
- [ ] Clicking Read in the floating toolbar reads only the selected text
- [ ] Speech begins within ~1 second; dock status changes to "Speaking…" in green
- [ ] Stop button cancels speech immediately
- [ ] After Stop: status changes to "Stopped — select text to read again"
- [ ] Toggling Read Off while speaking: speech cancels, tip dismisses, status returns to "Reading off"

**First-use hint**
- [ ] Clicking Read for the first time shows a brief hint: "Turn on Read, highlight any text, then tap Read in the popup"
- [ ] Hint disappears after ~4 seconds
- [ ] Hint does not reappear on subsequent Read toggles

**Boundary conditions**
- [ ] No text is stored, sent to backend, or added to any observation
- [ ] No backend calls are made by any TTS action
- [ ] Selecting button text, nav labels, or dock text does not accidentally trigger read
- [ ] Tab blur (switching windows/tabs) cancels speech

---

## Continuity

These two principles share a structure:

| Domain | The false collapse | The discipline |
|--------|--------------------|---------------|
| Corpus | Uploaded = evidence | Role governs participation, not presence |
| Connections | Configured = suitable | Suitability governs use, not availability |

Both are implementations of the same governing invariant: **provenance must be visible and durable, not inferred from presence.**
