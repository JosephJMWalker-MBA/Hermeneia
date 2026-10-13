# Performance Manuscript Human-Attention Bridge

**Status:** Active integration design  
**Captured:** 2026-09-27  
**Implementation authority:** Experimental / bounded  
**Repository rule:** Hermeneia and Performance Manuscript remain separate systems with explicit handoff artifacts.

## Activation

The previously deferred convergence hypothesis is now active at one narrow seam:

> **Performance Manuscript observes the manuscript exhaustively; Hermeneia gives a human a place to direct attention over time.**

This does not authorize a repository merge, ontology merge, or shared canonical database.

The first bridge should prove that normal reading, proofreading, listening, highlighting, and annotation can produce higher-value human supervision than a separate audit interface.

## Responsibility split

```text
Performance Manuscript
  machine observation
  attribution proposal
  performance-direction proposal
  render / QC observation
          ↓ explicit sidecar
Hermeneia Reader
  read / listen
  highlight
  notice
  annotate
  Perspective
  performance guidance
  ratify / correct / reject / unresolved
          ↓ explicit sidecar
Performance Manuscript
  governed correction / ratification adapter
  selective regeneration
```

Hermeneia does not become the canonical audiobook-production engine.

Performance Manuscript does not become Hermeneia's canonical interpretation ontology.

## Human attention is an event, not an overwrite

The durable record should preserve:

```text
machine proposal
→ human attention
→ human judgment
→ later canonical outcome
```

A correction must not erase the observation that preceded it.

A user merely seeing or passing a passage is **not** ratification. Explicit action is required for governance.

Human outcomes relevant to the bridge:

- **ratification** — explicitly accept a machine observation;
- **correction** — replace a machine observation with a human judgment;
- **elaboration** — add interpretation or performance information without necessarily contradicting the machine;
- **unresolved** — explicitly preserve uncertainty.

## Reader interaction

The bridge should feel like Hermeneia, not a specialist annotation console.

The user reads the work normally. Machine observations may appear quietly as optional overlays or badges. The user can select text and record only the attention that feels warranted.

Selection actions should progressively include:

- highlight;
- note / question;
- speaker or source identity;
- source class;
- Perspective;
- tone;
- pace;
- intensity;
- emphasis;
- pause;
- pronunciation;
- ratify / reject / unresolved.

These remain distinct where their semantics differ. A Perspective is not merely a tone preset. A performance direction is not an interpretation. A source correction is not a manuscript edit.

## Bridge artifact

The first integration should use an append-only `HumanAttentionEvent` sidecar rather than a new canonical Hermeneia ontology.

Minimum shape:

```json
{
  "event_id": "hae-...",
  "work_id": "work-...",
  "source_fingerprint": "sha256:...",
  "anchor": {
    "segment_id": "seg-...",
    "start": 0,
    "end": 0
  },
  "machine_observation_ref": "obs-... or null",
  "modality": "touch|keyboard|voice|audio-review",
  "action": "highlight|note|ratify|correct|reject|unresolved|set-perspective|set-performance",
  "human": {
    "source_identity": null,
    "perspective_refs": [],
    "note": null
  },
  "performance": {
    "tone": null,
    "pace": null,
    "intensity": null,
    "emphasis": [],
    "pause": [],
    "pronunciation": []
  },
  "provenance": {
    "actor": "owner",
    "created_at": "...",
    "device_class": "desktop|tablet|phone|unknown"
  }
}
```

This is a bridge contract to test through use. It should not be promoted into the constitutional ontology merely because the UI needs it.

## Field Notes proofread

The first intended real-use case is the owner's first full proofread of *Field Notes From Beneath the Soil*.

The workflow should eventually allow:

```text
read manuscript
→ encounter PM observation
→ keep reading if nothing deserves attention
→ highlight when something does
→ correct identity / add Perspective / add tone or pacing
→ preserve event
→ continue reading
```

Validation-set membership, when present for Performance Manuscript research, must remain invisible to the Reader.

Private manuscript prose must not be committed to Git. Bridge development may commit schemas, hashes, aggregate counts, tests, and synthetic fixtures.

## Tablet / iPad product target

The bridge should be built so the interaction can later move naturally to iPad.

### Touch-first reading

- Reader remains the dominant canvas.
- Standard iPad text selection and Apple Pencil selection/highlighting should be supported.
- Annotation controls appear contextually from the selection instead of occupying permanent screen space.
- Large touch targets, dark mode, large-text support, and clean return-to-reading behavior are requirements.
- The same anchor must work while reading or proof-listening.

### Voice annotation

A selected passage should eventually support a short voice instruction such as:

> “Nolan. Dry. Slower. Pause after ‘ordinary biology.’”

The system may transcribe and structure that into a proposal, but:

```text
raw spoken note
!= transcript
!= structured annotation
!= ratified performance instruction
```

The user confirms or edits before authority is granted.

Runtime choice for transcription must be explicit. Local processing is preferred when available; any external provider must respect Hermeneia Scope and provenance boundaries.

### Offline-first behavior

Tablet use should not require a live provider connection merely to read or annotate.

Attention events should be queueable locally and export/synchronize later. A connection failure must not block the reading session or lose an annotation.

## Thin implementation path

1. **Synthetic contract fixtures.** Define PM observation-sidecar and Hermeneia attention-event fixtures without real manuscript text.
2. **PM overlay import.** Hermeneia can load an observation sidecar and align observations to stable Reader anchors.
3. **Selection-to-event.** Existing highlight/annotation interaction can emit an explicit attention event.
4. **Performance annotation.** Add a lightweight selection surface for tone / pace / emphasis / pause without turning the Reader into a production dashboard.
5. **Round-trip export.** Export PM-relevant attention events separately from the broader Hermeneia workspace record.
6. **Governed PM adapter.** PM validates those events and routes eligible changes through its existing correction/ratification machinery.
7. **Proof-listening alignment.** Audio playback and Reader selections share anchors.
8. **Tablet pass.** Touch-first selection, contextual controls, voice notes, local queue.

## Success criteria

The bridge should be evaluated through sustained use, not feature count.

Useful measures include:

- corrections discovered during ordinary reading/listening rather than dedicated audit sessions;
- time outside the Reader required to resolve an observation;
- ratio of ratification / correction / elaboration / unresolved attention events;
- performance annotations that survive into a rendered take;
- selective-regeneration savings after correction;
- human attention events per hour of uninterrupted reading;
- tablet/voice annotation completion rate when implemented.

Do not optimize for more annotations. The aim is to make **valuable human attention easy to capture when it naturally occurs**.

## Architectural boundary

The bridge is active.

The merger is not.

The governing loop is:

```text
machine observation
→ human attention
→ governed judgment
→ derived performance
→ listening
→ new human attention
↺
```

This is the first implementation seam to test between Hermeneia and Performance Manuscript.
