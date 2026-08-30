> **Product direction:** Read [`docs/FROZEN_PRODUCT_DIRECTION.md`](docs/FROZEN_PRODUCT_DIRECTION.md)
> first for the Reader-centered experience. Read [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)
> for the dated operational state. Constitutional authority always resolves through
> [`docs/01_Authority_Index.md`](docs/01_Authority_Index.md).

# ARCHITECTURE FREEZE v1.0 — LIFTED

**Status:** Validation Phase — active development  
**Freeze lifted:** 2026-06-25  
**Orientation synchronized:** 2026-08-29

The constitutional architecture demonstrated sufficient stability through implementation, testing, and repeated experimental execution to continue building without treating every new product finding as a foundational rewrite.

This does not mean Hermeneia is finished. It means the foundation is stable enough to be pressure-tested through real use.

---

## Validation Phase

The governing engineering posture is:

```text
stable against preference
not stable against evidence
```

New architectural ideas do not acquire authority merely because they are useful or attractive. Product findings should first be implemented, when possible, as bounded projections, configuration, workflow, or derived infrastructure over established primitives. If evidence demonstrates a genuine architectural insufficiency, route the question through the constitutional process.

### Current validation goals

- Validate Hermeneia through sustained use on additional real corpora and manuscripts.
- Keep the Reader as the center of gravity while tools unfold around the work.
- Strengthen whole-study synthesis from accumulated highlights, questions, notes, observations, buckets, and Perspectives.
- Preserve question-relative investigation framing and explicit Scope/provider/model boundaries.
- Continue provider/runtime work without confusing Connection, Provider, Model, Model Version, Configuration, Perspective, or epistemic identity.
- Improve onboarding, accessibility, recovery, and workflow coherence based on observed friction.
- Preserve exact provenance for nondeterministic execution and human stewardship.
- Prepare a stable v1.0 release candidate only after the product survives real-use validation.
- Complete live demonstration and communication materials after the demonstrated product state is stable enough to show honestly.

The dated operational state lives in `IMPLEMENTATION_STATUS.md`; do not reconstruct current completion from old roadmap checkboxes.

---

## Stable Cognitive Responsibilities

```text
Explorer       surfaces candidate interpretations from evidence
Architect      reconstructs semantic obligations from stewarded understanding
Artist         realizes understanding in a chosen expressive form
Critic         evaluates whether expression preserved declared obligations
Steward        exercises judgment that cannot be reduced to computation
```

These are cognitive responsibilities, not merely software modules.

`Witness` remains under active investigation as attention-before-interpretation. Witness-oriented interfaces and experiments may exist without making Witness a new canonical epistemic class merely through implementation.

---

## Epistemic / Expression Boundary

The operational lineage remains explicit:

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
    ↓
Candidate Interpretation     ← machine assistance may propose
    ↓
Interpretation               ← human stewardship
    ↓
NarrativeBlueprint           ← governed synthesis
    ↓
ArchitectPlan                ← semantic contract
    ↓
ExpressionProfile            ← audience / language / voice / rhetorical constraints
    ↓
RenderedNarrative            ← Artist execution
    ↓
Finding[]                    ← bounded Critic evaluation
    ↓
Stewardship / Ratification   ← human authority
```

Perspective is an interpretive frame used during inquiry and execution. Provider/model/configuration is execution identity. Neither should be silently collapsed into the other or into the semantic identity of the evidence.

The Constitution, amendments, invariants, active ADRs, and implementation specifications remain authoritative over this orientation summary.

---

## Product Reality at This Synchronization Point

The following are existing product reality, not future roadmap assumptions:

- Reader-centered workbench and docked Companion
- in-place Corpus Search, attention timeline, Field Notes, and bottom workstation
- workspace lifecycle, isolated named workspaces, and WBS export/import/restore
- Blueprint → Architect → Artist → Critic → Draft Preview → Ratify → Record chain
- durable Reader annotations and explicit capture modes
- question compass and question-relative Corpus/Lab framing
- Perspective definitions/revisions and governed Perspective-run infrastructure
- accessibility/focus/read-aloud work
- provider registry, credential-source boundaries, model catalogs, and local-runtime foundations

Do not schedule these as if they are unimplemented merely because an older roadmap says they are next.

---

## Current High-Leverage Work

### Real-use Reader validation

Use real reading and editing sessions to discover friction. Important open work includes Reader projection/readability, meaningful structural checkpoints, trustworthy Reader position, workstation coherence, and sustained manuscript workflows.

### Whole-study synthesis

The accumulated study—not one observation at a time—should become the useful unit of synthesis. Evidence Board / true study lineage work is a major open product lane.

### Connections execution control

Issue #159 defines the accepted provider/runtime control-plane direction. Continue in bounded slices. Saved model configurations in draft PR #165 are **not on main** and should be reconciled against current main before landing.

### Derived analytics later

Issue #158 (Model Observatory) is a derived analytics/research surface over trustworthy run history. It must not become a substitute for improving the underlying Reader, lineage, execution receipts, or stewardship flows.

---

## Original Exit Criteria — Current Interpretation

- [x] Critic implemented
- [x] Multi-profile Artist rendering
- [x] End-to-end traceability
- [x] Semantic fidelity reporting
- [x] Reader-centered product direction embodied in working software
- [x] Durable workspace lifecycle and preservation infrastructure
- [ ] Whole-study synthesis validated through sustained use
- [ ] Provider/runtime configuration path completed and integrated cleanly
- [ ] Live demonstration video
- [ ] Pitch deck / communication package
- [ ] Stable v1.0 release candidate

---

## What the Freeze Accomplished

The freeze prevented architectural churn. More valuably, it forced discovery of the architecture rather than continuous redesign of it.

The subsequent Reader/workbench phase demonstrated a second lesson: stable architecture does not remove the need for product discovery. It makes product discovery safer because observed friction can usually be solved without changing evidence identity, authority, provenance, or the canonical epistemic stack.

The correct sequence now is:

```text
use
→ observe friction
→ classify the problem
→ implement the smallest bounded correction
→ test
→ use again
```

Not:

```text
imagine feature
→ expand architecture
→ hope use justifies it later
```

Hermeneia remains a research environment whose architecture is allowed to change when evidence demands it. Preference alone is not sufficient evidence.
