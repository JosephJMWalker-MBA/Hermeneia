# Live Reader Audit — 2026-09-09

This checkpoint records the findings from a live Hermeneia session run on the Orin and driven from the Mac over SSH. It separates defects that are safe to correct immediately from architectural/IA findings that require a deliberate design pass.

## Immediate corrections in `fix/live-reader-audit-2026-09-09`

### 1. Reader page speech transport
**Observed:** `Read page` worked, but once speech started the obvious Stop control lived only in Reader Tools.

**Code truth:** Reader page speech used the Reading Tools speech path, which only tracked a coarse `speaking` state and exposed global stop remotely.

**Correction:** the page-level control now owns the transport it starts:
- Read page
- Pause / Resume
- Stop

Speech state now carries Reader-page source identity so the current page button only controls speech it initiated.

### 2. Workstation content gutters
**Observed:** Perspective, Expression, Record, and related workstation surfaces rendered content flush against shell edges.

**Code truth:** the shared `.cr-fln-body` owns scrolling but no padding. Field Notes and Evidence already supplied their own inner gutters; newer workbench surfaces did not.

**Correction:** apply one scoped shared gutter to Perspective, Blueprint, Render, Critic, Voice, Draft, and Record without double-padding Field Notes or Evidence.

### 3. Local model selection and Ollama Install controls
**Observed:** changing the Local Model dropdown visually did not change the model used by Test Connection; `Install qwen3:4b` appeared clickable but did nothing.

**Code truth:** dynamic provider values were injected into double-quoted inline event attributes using JSON string literals. The resulting generated attributes were malformed. The backend model-selection, connection-test, and Ollama-install routes were intact.

**Correction:** provider-card dynamic controls now use `data-*` attributes plus DOM event listeners for:
- model selection
- Ollama install
- role calibration
- manual override toggle/apply

This removes the defect class rather than patching individual quotes.

### 4. Governing-question affordance
**Observed:** clicking `Set a governing question to guide your reading` returned to Reader but did not expose the editor.

**Code truth:** the click handler rendered/focused the question form after routing to Reader, but the form had moved into a hidden Reader dock panel.

**Correction:** route to Reader, open the Question dock, render edit mode, then focus the question input.

### 5. Return to Reading collision
**Observed:** on legacy/full-page workspace views the floating Return to Reading control was buried beneath the persistent bottom rail.

**Code truth:** both controls were fixed to the bottom; the FAB used `bottom: 18px; z-index: 86`, while the workflow rail occupies the bottom 40px at a higher stacking level.

**Correction:** move the floating fallback above the rail and clear the right Reader dock.

---

## Documented for a deliberate architecture / IA pass

### A. Lineage must distinguish two kinds of lineage

Current Lineage is a read-only artifact-provenance explorer:

```
Rendered Narrative
→ Architect Plan
→ Blueprint
→ Interpretation
→ Observation
→ Source
```

That remains valuable and should not be discarded.

The intended product meaning discussed in live use is broader: a complete, inspectable history of the investigation itself — what the reader did, when, where, with which source/page/object/model, and how long they spent in meaningful surfaces.

The current database cannot reconstruct that truthfully. Existing data includes:
- saved highlights / questions / notes
- Field Notes
- page-level reading progress
- artifact timestamps
- provider execution records

It does **not** provide a durable semantic interaction ledger or trustworthy dwell time. HTTP access logs are not a substitute: they include background requests, omit browser-only activity, and are not durable investigation records.

A future Lineage architecture should preserve both views:

1. **Investigation lineage** — chronological human/tool interaction ledger.
2. **Artifact provenance** — ancestry of governed outputs and claims.

Time spent must be captured explicitly with visibility-aware session/surface enter/leave semantics rather than inferred from request timestamps.

Candidate durable event fields:
- event_id
- workspace_id
- session_id
- occurred_at
- actor
- surface
- action
- source_document_id
- page
- object_type / object_id
- provider / model when applicable
- outcome
- duration_ms where semantically valid
- metadata / provenance reference

### B. Ask the Room belongs in the Companion experience as an entry point

Current implementation places Ask the Room inside the Perspective workstation as a mode beside Single Perspective. That full workbench remains the correct home for:
- building/saving/revising Perspectives
- configuring Room roster and order
- selecting historical/current saved Perspectives
- inspecting explicit scope/model configuration
- revisiting Room receipts

For live reading, however, Ask the Room should also be available directly from the Companion sidebar.

Preferred interaction model:

```
Companion sidebar
├─ Companion
└─ Ask the Room
```

The sidebar should reuse the existing Room execution path and scope/roster machinery; it should not create a second Room implementation.

Companion remains the lightweight conversational mode. Ask the Room is a quick comparative inquiry over explicit Reader context. Perspective remains the full configuration/workbench surface.

---

## Audit disposition

The live audit exposed three useful defect classes rather than isolated cosmetic reports:

- **Refactor wiring regressions** — controls moved but their launch paths were only partially migrated.
- **Legacy/new-shell collisions** — older fixed navigation/chrome persisted underneath the Reader-centered workstation.
- **Generated inline-handler defects** — dynamic data embedded into executable HTML attributes created controls that rendered but did not execute.

The architectural findings above should be implemented only after their durable contracts are agreed, rather than being improvised as one-off UI changes.
