# Retained Perspective execution receipt v1 — P3

Implementation packet P3 of [#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215),
governed by the steward boundaries in [#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214),
the Constitution's auditability/read-only/append-only rules, Storage, and
ADR-0045. Starting commit: `7e865a22aa93cecca7432b5e22f9d8a034e1c82a`.

## Decision before implementation

The claim requiring this record is narrow: one exact single-Perspective execution
produced exact output, and a local steward explicitly chose to retain that output
in the study. Existing Field Notes are mutable attention, Interpretations require
distinct adjudication, and rendered narratives belong to expression. None can
truthfully own this retained execution. One domain-specific receipt owns its output
once; there is no generic event store or second output table.

Authority belongs to the existing Perspective execution operation and the local
steward's explicit retention action. Retention does not mean agreement, acceptance
as an Interpretation, comparison, synthesis, intellectual quality, or an award.
The actor is a generic local steward; the system does not authenticate a named
human identity. Model-authored output remains model-authored, with a separate
human-retention decision.

The first slice retains single built-in or saved frame-v2 Perspective executions.
Room remains transient. Custom drafts remain transient in this first profile;
retaining a draft must not silently declare a canonical Perspective. Built-ins
retain their exact packaged ID/version/definition and semantic fingerprint without
inserting a database Perspective. A saved frame-v2 Perspective ID already names
the exact immutable revision; no extra Profile/Revision ontology is introduced.

The receipt binds an opaque run ID; captured frame semantics and revision identity;
the exact execution question; the exact server-resolved Scope and materialization,
including typed source/extraction/highlight references; provider/model/configuration
actually exposed by the adapter; exact prompt and its digest; execution timestamps;
exact response and its digest; and the explicit local retention decision/time.
Question and mutable highlight snapshots are captured inputs, not references to
later current state. Undisclosed model revision, seed, temperature and runtime
defaults remain unknown. Provider/model differences do not establish independence.

Successful runs are held only in workspace-scoped server memory until retained.
The API accepts an explicit retention decision for an exact server-owned run token,
never client-reposted prompt/output or the current controls. A restart/expired token
refuses retention instead of reconstructing a run. Explicit discard removes only
the transient candidate and creates no durable negative/rejection event. Navigation
away is neither retention nor discard.

Storage is one append-only `perspective_execution_receipts` table, with a strict
versioned JSON payload and digest-derived receipt identity, unique run ID and
database-enforced update/delete refusal. One transaction installs the complete
record or nothing. Repeat retention of the same exact run returns the same receipt;
a conflicting run binding refuses. No lifecycle/withdrawal subsystem is added.

Study Lineage validates the receipt and its immutable reference closure before
projecting its typed identity, original execution/retention times, model authorship,
human-retained provenance and available context links. A missing, malformed or
excluded source ancestor omits the entire receipt, including copied input/output
text. Captured mutable highlight text is not compared to a later edited highlight.

WBS adds one narrowly required receipt capability and component using its existing
additive component mechanism. Export/restore preserve exact identities, input/output
digests and required references; restore uses the existing atomic transaction.
Older restorers must refuse the declared capability rather than silently drop it.
Older workspaces/bundles remain valid; absent historical coverage means unsupported,
not zero activity. An empty table after restoring an old bundle does not establish
complete past Perspective coverage. No logs or transient output are backfilled.

Purpose/retention classification: intentionally retained local study evidence of
execution and human retention, portable with study records. It is not product
telemetry, research data, consent history or institutional identity.

P1's existing historical predicate remains unchanged under its original version.
A new explicitly versioned `explore_perspective` rule may use validated retained
receipts. P2 consumes that evaluation without an award or Full Cycle claim.

## Exact receipt and storage contract

`hermeneia/perspective_execution_receipts.py` owns capture, the strict codec,
identity/reference validation, atomic retention and read-only retrieval. Schema
18 adds one table through the existing SQLiteStore/startup initializer:

```text
perspective_execution_receipts
  id            TEXT PRIMARY KEY
  run_id        TEXT NOT NULL UNIQUE
  receipt_json  TEXT NOT NULL
```

There is no separate output object or mutable current-run pointer. SQL triggers
refuse UPDATE, DELETE and replacement by INSERT OR REPLACE. Required reference
closure is checked by domain validation before installation and during reads and
portability. The existing startup initializer adds the empty table to older
workspaces; direct read-only readers discover missing tables without initializing
them. No old transient executions are reconstructed.

The payload fields are exactly `schema`, `id`, `run`, `retention`:

| Object | Required captured fields |
| --- | --- |
| Receipt | `schema=hermeneia.perspective-execution-receipt/v1`, digest-derived `id` |
| Run | Opaque UUID `run_id`, `operation=perspective_run`, `status=succeeded`, `created_at`, `completed_at` |
| Frame | `id`, existing `version`, `origin`, `definition_fingerprint`, exact semantic `definition`, exact original `metadata` |
| Inputs | Exact effective `question`, complete `scope_receipt` and server materialization, exact `prompt`, `prompt_version=perspective-run/v1` |
| Execution | Exact exposed adapter/per-run `execution` configuration; provider/model required, undisclosed details remain undisclosed |
| Output | Exact `response`, stored once; text is not trimmed or normalized by retention |
| Digests | `question_sha256`, `scope_sha256`, `prompt_sha256`, `response_sha256` |
| Retention | `decision=retain`, `actor=local_steward`, `actor_identity=unknown`, original `retained_at` |

A saved frame's immutable Perspective ID is its revision identity. Its existing
execution `version` field may be empty; no revision ordinal is fabricated.
The semantic fingerprint retains the established frame-v2 serialization.

The v1 receipt codec permits only finite JSON values with string object keys,
sorted keys, ASCII escaping, compact separators and UTF-8 encoding, with **no
trailing newline**. Text digests hash the exact UTF-8 text. Scope hashes this
canonical encoding. Digests use `sha256:<lowercase hex>`. The receipt ID is
`perspective-execution-receipt:sha256:<hex>`, hashing the canonical payload with
only `id` removed (including schema, exact run and retention). Stored JSON must
be these exact canonical bytes. Duplicate keys, altered bindings, unsupported
Scope/profile/receipt contracts, missing parents and digest mismatches refuse.

Retention uses BEGIN IMMEDIATE when it owns a transaction and a savepoint in a
caller transaction. A complete row is inserted, reread and validated. Failures
roll back that write; caller pending work is preserved. The web path owns its
transaction, checks Lineage eligibility, commits, then marks the in-memory
candidate retained. A repeated exact run returns the first receipt and original
retention time; conflicting content under one run ID refuses.

## API, UI and read-only context

`POST /api/perspective/run` retains its existing transient result shape with
additive retention support and an opaque run token for supported frames. The
actual prompt and execution times are captured at the provider boundary. The
app instance belongs to one fixed database; its candidate map holds at most 100
recent runs, including retained candidates. Eviction, discard or server restart
makes a lost token unavailable rather than recoverable from browser text.
Room and custom-draft executions receive no retainable token.

```text
POST /api/perspective/executions/<run-id>/retain   {"decision":"retain"}
POST /api/perspective/executions/<run-id>/discard  {"decision":"discard"}
GET  /api/perspective/executions/<receipt-id>
```

Reposted client inputs/output and extra decision fields refuse. Discard removes
only the transient candidate. A retained record cannot be discarded through this
endpoint. No update/delete API is added. The UI binds actions to the displayed
token and workspace/context epoch, shows transient versus kept state and explicit
non-agreement language, and sends no decision during navigation. Failed Keep
remains retryable. GET uses a read-only/query-only transaction and no provider or
store initialization. Eligibility reuses the Lineage projection; a receipt that
Lineage omits cannot leak its captured text through GET.

Lineage adds `retained_perspective_execution`, typed by table and `id`, with
`authorship=model`. Its chronological position uses original
`retention.retained_at`; provenance separately preserves execution start/end and
human retention. The existing origin/type filters and deterministic export apply.
“Open retained execution” reads the full exact frame/question/Scope/output. A
recorded Reader page is also addressable under the existing navigation contract.

A separate saved-profile context link was considered and withheld: the existing
`GET /api/perspective/saved/<id>` initializes SQLiteStore. A synthetic witness
observed its SQLite schema cookie change from 171 to 175 and database bytes change
despite HTTP 200. P3 leaves that old route unchanged and opens captured frame
details only through its new read-only receipt context. No saved successor is
substituted for the executed revision. Reader navigation itself retains its
existing reading-position behavior; opening receipt details is read-only.

## Portability and coverage

WBS adds canonical `study/perspective_executions.json` containing exact stored
rows and declares required capability `perspective-retained-execution-v1`.
The existing WBS 1.1/1.2 version selection remains unchanged; capability refusal
guards the additive component. Presence of the table declares the extant category
even when empty. This means zero **extant retained receipts**, never zero past
Perspective activity or complete intellectual history.

Export validates receipts/reference closure and takes one SQLite read snapshot,
preserving caller-owned transactions. A deterministic two-connection witness
commits a new saved frame and retained execution between dependency and receipt
reads. Without the guard, the bundle contains two receipts but zero saved frames;
one receipt is detached from its exported dependency. With the guard, the first
bundle contains one receipt/zero saved frames, and the next contains two receipts/
one saved frame; both restore. This is a bounded export consistency repair needed
by P3, not a new portability authority or general publication transaction.

Restore validates the component's capability, canonical manifest entry/hash,
root containment, exact row schema, canonical payload, unique IDs/run IDs, counts
and required typed references. It inserts in the existing atomic restore
transaction; failure rolls back all inserted rows. Receipt-only targets are
nonempty. Excluded forensic ancestors and their historical receipts remain
archivable, while access-filtered Lineage/GET omit the entire receipt.

Old bundles without the component/capability remain valid under their prior
contract. Read/preview/restore return explicit `coverage` with `status=unsupported`
and unknown historical activity, without a receipt count that could imply absence.
Initializing an empty new table after restore does not reconstruct past coverage.
New bundles return `status=covered`, extant record count and an explicit incomplete
historical-activity caveat. No destructive migration or historical rewrite occurs.

## Versioned capability result

The original `capability-registry-v1.json` stays byte-identical with its frozen
`explore_perspective@1.0.0` predicate (no durable execution evidence). It remains
loadable explicitly. Default definitions now use `capability-registry-v1.1.json`,
registry/evaluator `1.1.0`, with **only** `explore_perspective` advanced to
definition `1.1.0`. Its narrow historical fact is one eligible validated retained
single-Perspective receipt. Retention can therefore support
`already_exercised_under_supported_evidence`; current readiness remains separate.
No receipt is still unknown historical exercise, including with an empty new table.
The old rule cannot acquire the new fact by silently rewriting its version.

Canonical registry digests:

```text
1.0.0  7ec255a892ed48a6ce42b597cad2e247b6f99d59cb7e6edd41bca15d14074622
1.1.0  eafda6b4081c50bdece9540a45c54c0404d0f7c0e05fcff750cf6f19626c9f75
```

P2 consumes this result naturally. Its presentation version and unrelated P1 rules
are unchanged. There are no awards, badge receipts, comparison or mastery claims.

## Measured verification and remaining boundary

Validation uses isolated synthetic databases and injected providers, never a
live model or real workspace. The integrated API witness runs → explicitly keeps
→ exports ZIP → restores → retrieves the same exact receipt → projects equal
typed Lineage items. Canonical stored receipt bytes and SHA-256 survive exactly.
Read-only restored retrieval/projection preserves workspace byte snapshots with
provider creation forbidden. Saved-frame receipt contexts additionally forbid
SQLiteStore initialization. Domain tests preserve mutable-input snapshots,
immutable frame ancestry, malformed-record refusal and SQL append-only enforcement.

Measured on Python 3.13.5, Node 22.17.0, pytest 9.1.0, macOS 26.6.2 arm64:

- **123 new P3 tests**: 42 codec/storage, 26 API, 9 Lineage/capability integration,
  14 actual-function UI tests and 32 WBS tests.
- Focused P3 plus P1/P2/Lineage/Perspective/Room/Scope/WBS/Companion/vertical-slice
  regression: **525 passed**, five existing dependency warnings, 16.85s.
  Included P1: **55 passed**; P2: **67 passed**; existing Lineage: **75 passed**;
  existing Perspective/Room: **60 passed**; WBS including P3: **58 passed**.
- Additional final-change/schema/Board/concordance/publication regression:
  **257 passed, 14 skipped**, five existing warnings, 7.92s. The skips are
  existing live-provider tests; no opt-in was used.
- Independent untouched starting archive `7e865a2`: **2,105 passed, 21 skipped,
  six Reader failures**, five warnings, 95.70s. All 615 tracked archived files
  retained their SHA-256. Local loopback runtime tests were permitted; external
  networking and cloud credentials remained blocked by default test governance.
- Initial full integration run: **2,223 passed, 21 skipped, ten failures**.
  Four additional failures expected schema 17 or absence of all WBS required
  capabilities. These exact expectations were advanced to schema 18 and the new
  receipt capability; their evidence/search/publication assertions were preserved.
  No established Reader assertion was changed.
- Final full suite: **2,228 passed, 21 skipped, six Reader failures**, five
  existing warnings, 106.29s. Failed test-ID sets match the independent starting
  archive exactly: **no newly introduced failure remains**.
- Wheel build without dependency installation/build isolation passed. Loading
  outside the checkout found both frozen/new registries, the receipt module and
  default registry 1.1.0 with all 11 definitions. Full inline JavaScript parsed,
  and `git diff --check` passed.

The six independently established Reader failures are:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

Remaining limitations: there is no authenticated individual actor; undisclosed
model revision/seed/runtime defaults remain unknown; unretained/draft/Room history
is absent; prior annotation revisions are unavailable; source association is
validated against stored immutable references and recorded source hashes, not a
new external-file audit. Synthetic validation does not establish real-user or
live-provider usability. No lifecycle withdrawal, institution/consent boundary,
comparison, achievements or P4 work is implemented.

Next bounded packet, only after review: P4's explicitly versioned achievement
design/evaluator over retained receipts, with a separate human-reviewed definition
of matching question/Scope and genuinely distinct frame identity. P3 supplies
evidence; it does not decide or award Perspective Explorer or Second Opinion.
