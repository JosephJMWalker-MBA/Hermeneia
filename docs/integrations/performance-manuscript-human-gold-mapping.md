# PM human-gold mapping — Hermeneia events → Performance Manuscript evidence fields

**Status:** Active integration design (bridge-local, experimental)  
**Captured:** 2026-09-27  
**Parent:** [`performance-manuscript-human-attention-bridge.md`](performance-manuscript-human-attention-bridge.md)  
**Rule:** this document maps fields. It does **not** merge schemas or ontologies.
Hermeneia keeps its own records; PM consumes an explicit export.

## Identity and anchoring

| Hermeneia (`pm_human_attention_events`) | Meaning | PM use |
| --- | --- | --- |
| `source_fingerprint` | SHA-256 of the source document bytes, the same as `source_documents.file_hash` | must equal PM's recorded source fingerprint for the same file (for a PDF, the same bytes) |
| `anchor` | the durable Reader locator of the highlight (`reader-span:v1:…` or an observation locator) at the moment of annotation | Hermeneia-side span identity |
| `page` | the Reader page | coarse alignment |
| `highlight_id` | the existing highlight, which is the visible mark and the anchor | — |
| `span_text` (private JSONL export only, resolved from the highlight) | the selected text | aligned against PM's own extraction; PM and Hermeneia may extract a PDF differently, so alignment is a PM-side derived function |

Events never store manuscript prose. The private JSONL export can resolve the
span text locally for alignment. That file contains manuscript text and is
never Git material.

## Judgment (`annotation_schema = pm-human-gold/1`) → PM evidence protocol

Every field is optional; an annotation needs at least one.

| `pm-human-gold/1` field | PM field | Notes |
| --- | --- | --- |
| `target_form` | `target_form` | the same 7 values |
| `source_class` | `source.source_class` | the same 6 values |
| `source_identity` | `source.surface`, and PM derives `source.roster_match` | Hermeneia does not know PM's roster; PM resolves roster relation and identity with its frozen matchers |
| `point_of_view` | (no PM field yet) | narrative point of view. It is **not** a Hermeneia Perspective |
| `perspective_refs` | (none) | ids of Hermeneia Perspective definitions: an interpretive frame, kept separate |
| `performance.{tone, pace, intensity}` | performance-direction supervision | free text in this version |
| `performance.{emphasis, pauses, pronunciation}` | performance-direction supervision | lists of free-text notes |
| `uncertainty.unresolved` / `.note` | `unresolved` / `human-review` with an ambiguity reason | explicit uncertainty, never inferred from an empty field |
| `note` | editorial / proofreading note | not an attribution signal |

PM's `performance_route` is **not** captured. PM derives it from the source
class under its own rules, so the human record does not carry a
machine-shaped routing decision.

## Provenance → gold status

| Hermeneia | PM interpretation |
| --- | --- |
| `mode = human-gold` and a `gold_pass_id` | blind first-pass human gold: no machine proposal was visible and no model could run |
| `mode = unblinded` | human attention recorded outside a blind pass, or after sealing; **never** counted as independent gold |
| first event of a chain (`action = annotate`) | the **first-pass value** |
| later `revise` / `withdraw` | reconsideration, reported separately and never silently replacing the first pass |
| `modality`, `device_class`, `actor`, `created_at` | capture provenance |

## Organic gold vs validation gold

Organic gold (this bridge) is selected by human attention, so it is **not** a
random sample. It is supervision and diagnostics for PM. PM's preregistered
validation (160 random + 40 challenge items) needs complete labels on its own
sample. That is a separate, later blind validation-completion pass, which
shows no machine answer, no confidence and no sample stratum.
