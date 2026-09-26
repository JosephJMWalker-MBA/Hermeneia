# Study Lineage v1: storage inventory and projection boundary

Date: 2026-09-24. Starting revision: `64f3a5b`.

This inventory precedes implementation of [issue #111](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/111)'s Evidence Board →
Lineage view. It describes what existing storage can establish. It does not
ratify a new event store, Blueprint model, or historical reconstruction rule.
The view is a read-only projection, not an additional canonical history.

## Governing authority and inspected implementation

The [Constitution](../00_Constitution.md),
[Authority Index](../01_Authority_Index.md),
[constitutional invariants](../02_Constitutional_Invariants.md), and
[Storage specification](../15_Storage.md) govern evidence identity, provenance,
and read-only behavior. Storage's read-only rule prohibits initialization,
migration, seeding, and timestamp writes during reads. Existing identities and
stored values outrank a convenient timeline narrative.

Inspection covers `hermeneia/storage/sqlite.py`, the write/read paths in
`hermeneia/web/app.py`, `hermeneia/compiler/staging/interpretation.py`,
`hermeneia/perspective_runs.py`, `hermeneia/authoring/store.py`, and workspace
lifecycle/export code. The Evidence Board introduced in [PR #200](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/200) and [PR #201](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/201) already
keeps Reader marks, corpus Field Notes, canonical Observations, and bucket
projections distinct. Its Scope-selection behavior is separate from lineage.
The older `/api/reader/timeline` is an attention feed, not a complete durable
study history. The existing `/api/lineage/<class>/<id>` traces individual
canonical objects rather than chronological workspace activity.

The runtime discovers `build/hermeneia.db` and
`workspaces/*/hermeneia.db`; it has no separate workspace registry database.
Read-only discovery found no databases at these locations in the current
Desktop checkout or the previously used Documents/GitHub checkout. No study
contents or usage frequency are claimed from this audit. The inventory below
is established by schemas and actual persistence paths; fixtures must exercise
the available records without presenting synthetic contents as user history.

## Category inventory

“Reconstructable” means a persisted record or explicit stored transition can
be shown. It does not promise a complete history of all user actions.

| Requested category | Coverage and durable source | Identity, time, and provenance limits |
| --- | --- | --- |
| Reader highlights | Partial history; `reader_highlights` stores the current mark, including dismissed marks | Real `id`, document/locator/page, optional `observation_id`, `created_at` and `updated_at`. Notes, questions, rankings, and bucket labels are fields of this identity, not separate events. Edits overwrite prior field values; do not fabricate earlier versions or their times. Reader capture establishes a mark, not authorship of its selected text or annotation fields; their origin is unknown without stored attribution. |
| Authored notes/questions | Partial; highlight fields, `inquiry_notes`, `observation_reviews`, and `workspace_investigation` | An `inquiry_notes.id` has observation/review references, question text/type, and `created_at`; deleted notes cannot be reconstructed. An observation review has its own `id` and current state with `created_at`/`updated_at`; it has no revision log. The governing question is the mutable `workspace_investigation.id = 'current'` row, not a sequence of saved questions. Preserve these distinctions. |
| Corpus Field Notes | Reconstructable extant snapshots in `investigation_log`, `lane = 'corpus'` | Real `id`, `created_at`, optional document/page, captured governing question, understanding, and pressing questions. Authorship/model origin is not recorded; report unknown. Text inside `pressing_questions` has no independent question identity. Instrument-lane notes remain outside this corpus view. |
| Canonical Observations | Reconstructable in `observations` with `provenance`, `source_extractions`, and `source_documents` | Occurrence `id`, exact `raw_text`, extraction/document identities, source locator, `created_at`; provenance retains source hash, offsets, compiler/run identity and time. Classify as source-derived evidence, not as a human interpretation or model opinion. Never merge occurrences by equal text. |
| Perspective definitions | Reconstructable saved declarations in `perspectives` | `id`, identity scheme, `created_at`; frame-v2 additionally stores fingerprint, `declared_by` and `declared_date`. A definition is not an execution or model identity. Existing supersession relations establish saved revisions. |
| Perspective/Room outputs | Unsupported for transient `/api/perspective/run` and `/api/perspective/room` results | These return `canonical_status = 'not_persisted'` receipts. Browser state, current models, or similar Field Note text cannot supply missing durable run identity or provenance. |
| Model interpretation proposals | Reconstructable in `proposed_interpretations` plus `ai_provenance` | Proposal `id`, observation/Perspective/evidence references, text, `created_at`, and pending/accepted/rejected status. Provenance `id` retains model/version, generation timestamp, prompt reference/type, parent IDs and generation parameters. Preserve both records and their explicit link. |
| Accepted/rejected model participation | Reconstructable when proposal decision fields exist | `decided_at`, `steward_id`, and rationale record a proposal decision. Accepted canonical `interpretations` retain `ai_provenance_id`; acceptance metadata also exists on that provenance row. A decision can be an event view of its existing proposal identity, not a newly minted decision object. Do not infer acceptance from matching text or null fields. |
| Canonical interpretations | Reconstructable in `interpretations` | Real `id`, observation/Perspective/evidence references, `created_at`, exact text, evidential status, and `source`. `steward-authored` and `ai-accepted` are explicit stored distinctions; retain linked model provenance where present. Unknown or inconsistent source metadata stays unknown. |
| Blueprint creation and revision | Reconstructable saved Blueprints and explicit supersessions; transient candidates unsupported | `narrative_blueprints.id`, title/thesis/sections/source/`created_at` plus observation/interpretation links. `source = 'extracted'` establishes derivation, not exact model authorship. Supersession has the real composite primary key `(old_id, new_id, reason, ratified_at)`, not a surrogate ID. Only classify endpoints by actual typed records; ambiguous cross-type ID matches do not establish a Blueprint revision. |
| Architect and rendered outputs | Reconstructable stored outputs; some execution detail partial | `architect_plans.id` links Blueprint identity/hash and deterministic source, with `created_at`. `rendered_narratives.id` links plan/profile and records provider, prompt, text, optional execution configuration, and `created_at`. Keep missing model/version metadata unknown. Current narrative status/rationale fields lack a decision actor/time; do not manufacture dated acceptance/rejection events. |
| Interpretation Critic records | Reconstructable `critic_reports` | Operational report `id`, proposal/observation references, policy, claims/evidence/verdict, `generated_at` and `created_at`. The schema does not record a critic model provenance link. A verdict is a Critic finding, not Steward judgment. |
| Narrative evaluation and stewardship | Reconstructable `validation_reports`, `findings`, `steward_decisions`, `witness_sessions`, and `ratification_records` | Each has its own identity and explicit parent references. Preserve evaluation `created_at`, decision `decided_at`, session `session_date`, and ratification `ratified_at` along with stored creation times. Critic `approved` does not imply human acceptance. Retain actors, methods, evidence and audit snapshots as recorded. |
| Publication Compositor activity | Reconstructable recorded attachment/edit/decision/result/proof facts where the work binds to this workspace | `publication_works.id` records `workspace_id`, `attached_by`, `attached_at`, input/work-root references and root version. The eight authoring tables below retain explicit work and artifact links. Do not infer a release, an export, or a source-document relationship beyond these records. |
| Workspace export / CLI publication events | Unsupported as a study event stream | Downloading a workspace bundle does not persist an export event. CLI build/preservation files are not a durable workspace event registry. Filenames, filesystem modification times and currently available output files do not establish historical study association. |
| Reading sessions, bucket/motif history | Unsupported as an event stream | `reading_progress` retains aggregate/current progress, not sessions or page traversal events. Current highlight bucket labels do not establish durable bucket identity or creation/revision history. No motif-analysis record is invented. |
| Expression configuration and search/readability support | References or derived support, not separate v1 study events | `expression_profiles` contains saved expression constraints referenced by rendered outputs; v1 preserves their recorded IDs on outputs without treating configuration as a Perspective or execution. `observation_derived`, `terms`, and `observation_terms` support derived readability/search, not independent interpretive actions. `schema_version` is infrastructure metadata. |

## Publication records already present

All these tables are append-only. Their presence is discovered, not created,
by the lineage reader.

| Table | Durable identity and time | Recorded association |
| --- | --- | --- |
| `publication_works` | `id`, `attached_at` | `workspace_id`, `attached_by`, `work_root_json`, `inputs_json`, root version and renderer/facade references |
| `publication_artifacts` | `sha256`, `created_at` | `work_id`, kind, relative path and byte length; a stored hash reference is not a fresh verification of artifact bytes |
| `authoring_drafts` | `id`, `created_at` | Work, parent version, unit and draft text; actor is not recorded |
| `authoring_proposals` | `id`, `created_at` | Work, parent version, unit, operation, before/after values, rationale, `proposed_by`, proposal digest and validation record |
| `authoring_decisions` | `id`, `decided_at` | Proposal/digest, workspace, actor, approved/rejected decision, rationale and target version |
| `authoring_requests` | `id`, `created_at` | Decision, work, expected parent, idempotency key, attempt and request artifact digest |
| `authoring_outcomes` | `id`, `created_at` | Request/work, accepted/refused/error status, chain index, result version, receipt/version/ledger/overlay digests and findings |
| `authoring_proofs` | `id`, `created_at` | Work/version, verified/failed/refused/error status, artifact/PDF digests, references and findings |

An actor string preserves the recorded actor; it does not by itself prove
human/model authorship. “Accepted” in a Compositor result concerns a specific
recorded editorial application and must not be relabeled as acceptance of a
model interpretation.

## Projection contract

Each item retains a typed durable identity: source table plus the real key
(including the complete composite key where applicable). An item may describe
creation, current mutable state, or an explicit stored transition. Its event
label does not become a new canonical identity. Separate source types remain
separate even when IDs, text, timestamps, or labels happen to match.

The projection preserves exact historical timestamp strings and identifies
their source fields. Only parseable timezone-aware instants participate in
cross-record chronological ordering. Missing, malformed, date-only, or naive
times remain visible as unorderable records. Equal instants have stable
identity ordering for deterministic presentation, not a claimed causal order.
Current mutable content must be labeled a current snapshot; its original
`created_at` cannot establish that the present text existed at creation.

Authorship filters distinguish only supported classifications. Source-derived
evidence, deterministic derivation, recorded human authorship, recorded model
generation, and accepted model contribution remain separate. Missing or
contradictory provenance yields unknown, with raw recorded metadata retained.
No classifier uses text similarity, provider defaults, current configuration,
or guessed authorship.

Existing excluded-document access boundaries still apply. A new history view
must not reveal excluded evidence or descendants through joins, relationship
payloads, or export. Coverage must explain omissions; exclusion is not proof
that the historical record never existed. Missing tables/columns in older
workspaces are reported as incomplete coverage without initialization or
migration. Missing parents or ambiguous identity references do not license
invented associations.

Read all records from the selected workspace's existing SQLite database in a
single read-only snapshot. Do not initialize workspace identity on a GET. An
absent durable workspace identity stays absent. Rendering, filtering, and
deterministic JSON export must not call providers or write study state.
SQLite may maintain its existing WAL coordination files while a read-only
connection observes committed data; this is not a new history store. Export
includes existing identities, timestamps, supported provenance,
and coverage limits, with stable serialization and no generated current time.
It remains a derived projection, not an authoritative archive or a new event
store.

Open links only where existing context can be addressed by a stable recorded
identity. Do not offer index-based links whose identity changes with sorting,
or silently substitute a similar item when the target is unavailable.

## Implemented surface

Evidence Board now has **Inventory** and **Lineage** views. Lineage provides
oldest/newest chronological ordering, record-type and authorship/origin filters,
100-item presentation pages, explicit unknown chronology, original-record and
provenance disclosures, and links into existing Reader/object-lineage contexts.
Switching workspace/Reader context clears type/origin filters and stale responses;
it cannot transfer selections into Scope. Explicitly opening a source page uses
ordinary Reader navigation, including its existing reading-position update.
Rendering, filtering, object-lineage inspection, and export are read-only.

`GET /api/study-lineage` and `GET /api/study-lineage/export` return the same
`hermeneia.study-lineage/v1` projection. The export is the full current projection,
independent of visible filters. Both read one SQLite snapshot using `mode=ro`,
without store initialization, migrations, identity creation, or provider calls.
Existing application startup migrations are outside this new read path and have
not been changed. An absent database returns 404 rather than creating a study.

The JSON codec uses UTF-8, sorted object keys, compact separators, unescaped
Unicode, no non-finite numbers, and one trailing newline. Arrays have stable
record/relationship ordering. Repeated exports of unchanged stored state have
identical bytes; no export-time timestamp or surrogate event ID is generated.
This is a disposable projection, not a preservation package or a historical
completeness claim. The live study may legitimately change between requests.

See the [implementation verification record](../verification/2026-09-25-study-lineage-v1.md)
for adversarial checks, the independently reproduced baseline, and remaining
limits. Issue #111's wider synthesis/history ambitions remain open.

## Explicit non-goals and stop boundary

No reconstruction of overwritten edits, deleted questions, transient model
runs, unsaved candidates, or unrecorded export actions. No AI synthesis, motif
analysis, durable bucket identity, new Blueprint semantics, publication
authority, or canonical source changes. If an item requires missing provenance
or a new authoritative event store, report that category unsupported and stop
that extension rather than invent history.
