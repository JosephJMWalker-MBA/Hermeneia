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

**As implemented (2026-09-27).**

- **Storage.** Two bridge-local, append-only tables in `hermeneia.db`:
  `pm_gold_pass_events` and `pm_human_attention_events`. Database triggers
  forbid `UPDATE` and `DELETE` and enforce the gold lifecycle below.
- **Why not a JSONL sidecar.** The active storage specification allows JSONL
  only as a labelled derived export. Human gold is irreducible, so it lives in
  the authoritative store, and JSONL is produced only as an export.
- **Vocabulary.** The PM vocabulary is kept under `domain = performance-manuscript`,
  `annotation_schema = pm-human-gold/1`: 7 target forms and 6 source classes,
  every field optional. It is not promoted into Hermeneia's general
  annotation ontology.
- **What an event stores.** The source fingerprint, the durable Reader anchor
  (the highlight and its locator), the human judgment and provenance —
  actor, timestamp, modality, device class. No manuscript prose: the
  existing highlight already anchors the exact span.
- **Revisions.** A revision or withdrawal is a successor event. The first
  pass is never overwritten.
- **Implementation:** `hermeneia/integrations/pm_human_gold.py`; HTTP in
  `hermeneia/web/pm_bridge_api.py`; Reader surface in
  `hermeneia/web/static/pm-bridge.js`. Field mapping to PM in
  [`performance-manuscript-human-gold-mapping.md`](performance-manuscript-human-gold-mapping.md).

## Human-gold pass — gold first, machine comparison after (amendment 2026-09-27)

Independent human observation comes **before** any machine comparison.

- **Gold pass.** A blind, bounded pass over one document, with a stable
  `gold_pass_id` and recorded open / seal provenance (actor, time, note).
- **Review workflow.** The overlay of machine observations described above
  follows only **after** the gold pass is sealed.

```text
GOLD_OPEN
→ GOLD_SEALED
→ machine-assisted review may occur afterward
```

**Opening.** Only in a workspace in which no model has produced output: no
`ai_provenance`, proposed interpretations, renders, Critic reports, findings or
authoring proposals.

**While `GOLD_OPEN`:**

- **All provider / model execution is refused, local models included.** The
  web app's provider registry refuses everything but the deterministic `null`
  provider. Every web call site resolves through it, and so do the CLI
  commands that call providers.
- Machine proposals, the machine-observation lens and panel, the page brief,
  Companion, Ask and Perspective runs are hidden. No machine suggestion is
  preselected, and confidence and validation-set membership are never shown.
- Only first-pass human-gold events (`annotate`, `revise`, `withdraw`) on the
  pass's document are accepted. They carry no machine reference. `ratify`,
  `correct` and `reject` are refused, because there is no visible machine
  proposal. No other document may be annotated, and no unblinded event may
  be written.

**Sealing** is an explicit, append-only human act (`{"confirm": "seal"}`).

**After `GOLD_SEALED`:**

- no new first-pass gold can be created for that pass;
- prior gold records stay immutable;
- later reconsiderations are successor events in `unblinded` mode, linked to
  the pass, never edits;
- machine-assisted comparison / review may then be enabled without changing
  the gold record.

### Two gold products

1. **Organic human gold** — annotations produced naturally while reading,
   proofreading or listening. Human attention decides what is annotated. The
   owner is never asked to annotate every passage.
2. **Validation gold** — complete labels for a preregistered PM sample (the
   160 random + 40 challenge items of the third-source design).

Organic gold is selected by attention, so it is not a random sample, and it is
never substituted for validation gold. A later **blind validation-completion
pass** may present sampled items still lacking required fields, after the
ordinary proofread and before any machine comparison. It shows no machine
answer, no confidence and no sample stratum. (Not yet implemented.)

## Field Notes proofread

The first intended real-use case is the owner's first full proofread of *Field Notes From Beneath the Soil*.

The workflow should eventually allow:

```text
open a human-gold pass (dedicated workspace, no machine output)
→ read manuscript — no PM observation visible
→ keep reading if nothing deserves attention
→ select and Annotate when something does
   (form / source / identity / point of view / tone / pace / pauses / uncertainty / note)
→ preserve first-pass event
→ continue reading
→ seal the pass
→ only then: load PM observations for comparison / review
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

Status (2026-09-27):

- **Done, for the human-gold pass only:** 1 (synthetic fixtures and tests),
  3 (selection → event), 4 (performance annotation) and 5 (export: a JSON
  export of human annotations only; a private JSONL export that can resolve
  span text for cross-extraction matching).
- **Deliberately not yet:** 2 (PM overlay import), 6, 7 and 8, and the
  validation-completion pass.

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
