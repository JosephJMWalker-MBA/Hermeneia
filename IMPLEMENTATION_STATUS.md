# Implementation Status

**Last updated:** 2026-09-01
**Status:** Validation Phase — active development
**Reference main commit at synchronization:** `519599e632bce9061056951f34998f87b782efe1`

> This file is an operational status summary, not constitutional authority. When a status statement conflicts with governing architecture, resolve authority through `docs/01_Authority_Index.md`.

---

## Current Product Reality

Hermeneia is no longer in the original architecture-freeze implementation phase. The constitutional foundation is stable enough to support sustained product validation, real-corpus use, and bounded expansion without treating every new capability as an architectural rewrite.

The current operating model is:

```text
Reader holds attention
    ↓
Question governs investigation
    ↓
Human + machine attention records accumulate
    ↓
Scope / Perspective / evidence organization support inquiry
    ↓
Blueprint records current synthesis
    ↓
Architect compiles semantic obligations
    ↓
Artist renders under explicit expression constraints
    ↓
Critic evaluates
    ↓
Human Steward ratifies, revises, rejects, or preserves uncertainty
```

Generated content, deterministic projections, machine suggestions, and human judgments remain distinguishable throughout the system.

---

## Implemented Foundation

### Constitutional and provenance infrastructure

- SourceDocument → SourceExtraction → Observation evidence lineage
- occurrence-aware observation identity and provenance
- constitutional authority, amendments, invariants, and compliance checks
- append-only / monotonic governance boundaries for canonical records
- deterministic hashing and integrity utilities
- preservation, release, and ratification artifacts
- workspace identity and isolated runtime lifecycle
- Workspace Bundle export, preview/import, restore, and preservation infrastructure

### Reading workbench

- Reader-centered application shell
- docked Companion and Reader-side support tools
- in-place Corpus Search and literal concordance
- attention timeline and Field Notes
- bottom workstation modes for synthesis and downstream work
- durable highlights and reopenable annotations
- explicit capture intents for highlight, note, question, concept, and observation candidate
- governing-question / thesis compass visible in the Reader
- Focus mode, large-text support, inline read-aloud, and page read-aloud
- first-run PDF upload and recovery flow
- reading-first Guide and question-relative Corpus/Lab language

### Investigation and synthesis

- machine observations alongside human close reading
- questions, notes, highlights, concepts, buckets, and investigation records
- question-relative investigation framing
- deterministic synthesis / lineage infrastructure
- Perspective definitions and append-only Perspective revision identity
- governed Perspective-run infrastructure and comparison surfaces
- NarrativeBlueprint workflows
- append-only committed Blueprint revisions and supersession lineage
- deterministic ArchitectPlan compilation
- provider-neutral Artist rendering
- Critic evaluation and findings
- Draft preview → Ratify → Record workflow
- voice / ExpressionProfile capture and witness-oriented Critic checks

### Provider and runtime infrastructure

- provider registry and model catalogs
- cloud and local runtime connection handling
- explicit credential-source boundaries
- machine-local Connections settings
- Ollama discovery / governed local-model management foundations
- model selection separated from Perspective identity

**Not yet on `main`:** saved reusable model configurations from draft PR #165. That branch contains useful bounded work but diverged substantially from current main and should be reconciled against current code rather than merged unchanged.

---

## Validation Evidence

Recent merged Reader/product slices have repeatedly run the unrestricted full test suite. The latest merged PR at this synchronization point, PR #197, reports:

```text
1460 passed, 3 skipped
```

The README intentionally avoids a permanent hard-coded test count because the suite changes continuously. This dated status file may record a point-in-time count as validation evidence.

Recent live-use validation has included local browser checks and selected exact-head Jetson/Orin smoke tests where the changed surface materially involved that runtime.

---

## Current Priority Lanes

### P1 — Real-use Reader validation

Continue using real corpora and manuscripts to expose friction before redesigning from imagination.

Important open work includes:

- #120 — *The Second Sale* live-use validation umbrella
- #121 — readable projection for layout-derived line breaks / spacing
- #129 — authored chapter/section structure
- #133 — source-locator Reader progress / semantic checkpoints

The coherent bottom workstation and governed Blueprint lifecycle work from #154/#156 are now implemented. The next Reader-adjacent synthesis slice should not re-open those foundations unless live-use evidence exposes a concrete defect.

### P1 — Whole-study synthesis

The strongest remaining workflow gap is moving from accumulated reading work to study-level organization and synthesis.

- #110 — synthesize from the whole accumulated study record
- #111 — Evidence Board and true study lineage
- #152 — visible bucket lenses / thematic reading projections

### P1/P2 — Connections execution control

Issue #159 defines the current provider/runtime control-plane direction:

```text
Connection
  → provider/runtime
  → model catalog
  → model configuration
  → default / assignment / per-run selection
```

Continue in bounded slices. Preserve the separation between provider, model, model version, configuration, Perspective, and investigation identity.

The conservative next-development sequence is:

```text
completed governed Blueprint lifecycle
  → explicit Scope boundary (#157)
  → whole-study synthesis / Evidence Board (#110/#111)
  → live-use validation
  → Connections execution-control completion (#159 / reconcile useful #165 work)
  → Model Observatory (#158) later
```

### P2 — Model Observatory

Issue #158 is accepted as a derived analytics/research surface over auditable execution history. It should consume trustworthy run lineage rather than driving premature architecture or replacing ordinary Reader work.

### P2 — Human developer/support channel

Issue #160 records a product-level human Developer channel for support, feedback, questions, and optional external tips. It remains outside the constitutional epistemic pipeline.

---

## Release Status

| Area | Status |
|---|---|
| Constitutional foundation | Stable under validation |
| Reader-centered workbench | Implemented; active live-use refinement |
| Workspace lifecycle / WBS | Implemented |
| Explorer / Architect / Artist / Critic / Steward chain | Implemented in bounded forms |
| Perspective infrastructure | Implemented and evolving under explicit identity rules |
| Provider/runtime control plane | Partially implemented; active work |
| Evidence Board / whole-study synthesis | Open |
| Live demonstration video | Pending |
| Pitch deck | Pending |
| Stable v1.0 release candidate | Target, not yet claimed |

---

## Operating Rule

```text
Use the product first.
Record friction when it appears.
Do not redesign from imagination.
Fix recurring, high-value problems in small green slices.
```

The architecture is stable against preference, not against evidence.
