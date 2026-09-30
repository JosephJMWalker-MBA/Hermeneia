# Perspective achievement rules v1 — P4 design freeze

Date: 2026-09-30. Evidence baseline:
`33931f4fc01ca32899d90a20b40f2210f597d09b` on `main`.

**GO — P3 evidence is sufficient to implement both v1 rules deterministically.**
This freezes a conservative, exact-record interpretation of Perspective Explorer
and Second Opinion. It does not implement or authorize deployment of P4.
Second Opinion uses option **B**: distinct validated Perspective families **and**
an exact difference in existing immutable methodology fields. No new profile
identity, schema field, semantic similarity, or human-comparison record is needed
for these two narrow claims.

The important restriction is deliberate: same evidence is not necessarily the
same complete Scope receipt. Highlight-backed receipts include compilation times
and reading-progress metadata. Different captured values prevent v1 qualification,
even when selected evidence and provider-visible text are otherwise identical.

## 1. Scope and governing boundaries

This packet follows [#215's P4 sequence](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215),
[#214's steward decisions](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214),
[#212's product direction](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/212),
and the [#213 architecture/derivability audit](capability-coaching-architecture-audit.md).
Constitutional authority resolves through the [Authority Index](../01_Authority_Index.md).
[Constitution](../00_Constitution.md) Articles I, II, X–XIII and
[CI-010–012](../02_Constitutional_Invariants.md) govern ancestry, auditability,
deterministic derivation, human authority, and side-effect-free reads.
[Storage](../15_Storage.md) and [ADR-0045](../adr/ADR-0045-perspective-definition-revisions.md)
govern the underlying records, not this award projection.

Achievements are derived interpretations of durable evidence. UI clicks,
current controls, transient outputs, saved definitions without executions, and
guessed missing history supply no achievement evidence. Retention is an explicit
local human action; it is neither agreement nor Interpretation acceptance.
Retained output remains model-authored. Named human identity is unknown.

This document changes no production code, records, schema, WBS, capability rules,
guide behavior, UI, or tests. It does not define comparison/adjudication or a new
canonical history store. Future award persistence remains a separate P4 contract.

## 2. Actual available evidence and inspected seams

The [P3 contract](perspective-execution-receipt-v1.md) and current code provide:

| Dimension | Exact available evidence | Limit |
| --- | --- | --- |
| Canonical retained record | `perspective_execution_receipts(id, run_id, receipt_json)`; schema 18; payload `schema`, `id`, `run`, `retention` | One receipt owns one output; no generic event history |
| Receipt identity | `perspective-execution-receipt:sha256:<hex>` over canonical payload excluding only `id`; row ID and UUID `run_id` also bound | Execution and retention timestamps are part of identity |
| Saved Perspective revision | `run.perspective.id`, `origin=canonical_saved`, `metadata.identity_scheme=perspective-frame-v2`, full immutable definition/fingerprint and declaration actor/date | The exact ID names a declaration/revision node; `version` is the empty string, not a revision ordinal |
| Saved family | Existing `perspectives` rows plus `supersession_relations(old_id,new_id,reason,ratified_at)` | No stored profile/root field. A family key must be derived from a validated complete predecessor chain |
| Built-in frame | `origin=built_in`, exact `id`, `version`, `definition`, `definition_fingerprint` | Packaged execution frame, not automatically a saved canonical Perspective |
| Question | Exact effective `run.question` and `question_sha256` | No stable question ID/version. API trims before capture; no later normalization is allowed |
| Scope/frame | Complete `run.scope_receipt` and `scope_sha256`; `resolved-scope:v1` plus server materialization | No canonical Scope object/ID; metadata and list order participate in the digest |
| Evidence references | Typed SourceDocument, SourceExtraction and Reader-highlight identities, recorded source hash, Reader span/page/locators | Captured mutable highlight text is historical input, not today's annotation text |
| Output | Exact `run.response` and `response_sha256` | Neither quality nor agreement is recorded by this binding |
| Prompt | Exact `run.prompt`, `prompt_sha256`, `prompt_version=perspective-run/v1` | Prompt equality across distinct Perspectives is inappropriate |
| Execution | Exact `run.execution`; nonblank `provider_id`, `model_id` required | Unexposed model revision, seed, temperature and runtime defaults remain unknown |
| Outcome/retention | `run.operation=perspective_run`, `status=succeeded`; `retention.decision=retain`, `actor=local_steward`, `actor_identity=unknown` | Failed, Room, custom-draft, discarded and unretained activity is not canonical P3 history |
| Times | Aware `created_at`, `completed_at`, `retained_at`; start ≤ completion ≤ retention | Recorded instants only; no session, causality, elapsed-work or clock-synchronization claim |
| Lineage | Typed `record={table:perspective_execution_receipts,key:{id:<receipt-id>}}`, `event=recorded`, `record_type=retained_perspective_execution`, `authorship=model` | Presentation preview is not output evidence; omitted counts do not diagnose why a row was omitted |
| Portability | WBS capability `perspective-retained-execution-v1`, canonical `study/perspective_executions.json`, exact row bytes/IDs, dependencies and counts | Covers extant retained records, including zero; never complete prior Perspective activity |

Verified implementation references at the baseline:

- [Receipt domain](../../hermeneia/perspective_execution_receipts.py):
  `canonical_bytes`, `capture_execution_run`, `validate_receipt`,
  `receipt_from_row`, `execution_references`, `validate_execution_references`,
  `store_retained_execution`, `load_retained_execution`.
- [Perspective identity](../../hermeneia/perspective_identity.py):
  `perspective_frame_v2_id`, `validate_frame_v2_row_identity`,
  `resolution_from_frame_v2_row`; [storage](../../hermeneia/storage/sqlite.py):
  `insert_perspective_revision` and append-only tables/relations.
- [Execution frames/template](../../hermeneia/perspective_runs.py):
  `PERSPECTIVE_DEFINITIONS`, `perspective_definition`, `build_perspective_prompt`;
  [API](../../hermeneia/web/app.py): `api_perspective_run`,
  `POST /api/perspective/executions/<run-id>/retain`,
  `GET /api/perspective/executions/<receipt-id>`.
- [Lineage](../../hermeneia/study_lineage.py): `project_study_lineage` with receipt
  validation, typed reference closure and exclusion eligibility.
- [WBS export](../../hermeneia/workspace/export.py): `_perspective_executions`,
  `build_bundle_files`; [restore](../../hermeneia/workspace/restore.py):
  `_read_perspective_executions`, `_validate_restored_perspective_graph`.
- [Capability evaluator](../../hermeneia/capabilities.py) and packaged
  [v1](../../hermeneia/data/capability-registry-v1.json)/
  [v1.1](../../hermeneia/data/capability-registry-v1.1.json):
  `explore_perspective@1.0.0` retains its unsupported-history contract;
  `explore_perspective@1.1.0` has the eligible retained-execution positive fact.
  That fact alone is not this stricter award predicate.
- [P2](guided-study-cycle-v1.md),
  [domain](../../hermeneia/guided_study_cycle.py):
  `project_guided_study_cycle` consumes capability results without awarding.

## 3. Shared execution-validity predicate: E(r)

An execution is Explorer-valid only when **all** of these conditions hold:

1. It is an existing canonical row of the supported P3 schema
   `hermeneia.perspective-execution-receipt/v1`. `receipt_from_row` validates exact
   canonical stored JSON, duplicate-key/nonfinite refusal, receipt/row/run
   bindings and all captured text, Scope and definition digests. No client
   repost, preview, current UI value or reconstructed historical output qualifies.
2. Operation is `perspective_run`, status is `succeeded`, and explicit retention
   is `retain` by `local_steward`, with identity still `unknown`. The existing
   aware timestamp/order checks pass. Repeat retention of one run is one record.
3. Perspective identity is supported and valid:
   - Saved: exact frame-v2 row, immutable revision identity and captured
     definition/declaration snapshot match under `validate_execution_references`.
     An immediate predecessor must be unambiguous. No current successor is
     substituted for the executed node.
   - Built-in: exact `(id, version, definition, definition_fingerprint)` matches
     a supported, frozen packaged revision. Initial support is the three existing
     IDs `close-reader`, `contextual-reader`, `skeptical-reader`, each version
     `1`, with their baseline definitions. Unknown revisions are unsupported;
     conflicting definitions under a known revision are invalid. Never compare
     an old revision to a silently updated catalog entry.
4. Exact nonblank question, full server-resolved Scope, output, prompt and their
   digests validate. Required immutable source associations and saved Perspective
   bindings close over durable records in the same read snapshot. Unexposed
   execution settings remain unknown; exact recorded `execution` is preserved
   and its required provider/model fields are nonblank.
5. The recorded prompt matches the supported `perspective-run/v1` template
   applied to the **captured** definition, question and materialization, with no
   prior Room readings. This is an additional read-only qualification check,
   not a claim that the P3 codec already checks prompt construction. It requires
   no provider, current source reread or output regeneration. Future template
   versions need explicit support; present code must not reinterpret old prompts.
   The frozen template itself uses `question.strip()` when constructing its
   prompt line. Reproducing that template operation does not normalize the
   stored question or change section 5's exact question-equality test.
6. The exact typed receipt is visible in the unfiltered eligible Lineage snapshot
   as `recorded` / `retained_perspective_execution` / `model`. Excluded ancestors,
   unavailable or ambiguous parents do not qualify. Output previews and labels
   cannot substitute for the canonical row. An arbitrary caller-supplied Lineage
   JSON is not by itself integrity proof.
7. The evaluated source has the supported extant-receipt coverage described in
   section 7. Required receipt/dependency bytes and identities are available for
   audit and supported P3 portability. Evaluation is read-only, over one coherent
   snapshot; it does not initialize schemas or resolve Scope again.

Existing P3 capture checks built-ins against their packaged definitions, but
receipt reads check internal hashes without a catalog lookup. Complete saved
ancestry is likewise not recursively validated by P3 receipt reads. The future
evaluator must perform the qualification checks above and in section 6; those are
derived read checks, not missing record fields or authority changes.

## 4. Perspective Explorer v1

| Contract | Frozen value |
| --- | --- |
| `achievement_id` | `perspective_explorer` |
| `rule_id` | `achievement.perspective_explorer` |
| `rule_version` | `1.0.0` |
| Qualified rule reference | `achievement.perspective_explorer.v1.0.0` |
| Required evidence | One canonical P3 receipt, its required typed dependencies, eligible Lineage identity, supported coverage and frozen frame/template support |
| Predicate | There exists an extant eligible receipt r such that E(r) |
| Future award witness | One deterministic qualifying receipt, its typed Lineage reference and exact underlying receipt ID/run ID, plus section 10's validation/coverage basis |
| Result states | Section 7: `earned`, bounded `not_earned`, `unsupported_due_to_missing_coverage`, `invalid_evidence` |

This proves one successful recorded single-Perspective execution and an explicit
local retention decision with auditable captured inputs/output. It does not
prove agreement, interpretation formation/revision, downstream use, Blueprint
work, learning, mastery, authenticity of a named actor, multiple models or
quality of reasoning. A retained response that the human later ignores or
disagrees with still qualifies.

## 5. Exact same inquiry and execution frame

For two individually Explorer-valid receipts a and b:

```text
same_question(a,b) :=
    a.run.question_sha256 == b.run.question_sha256
    AND UTF8(a.run.question) == UTF8(b.run.question)

same_scope(a,b) :=
    a.run.scope_sha256 == b.run.scope_sha256
    AND canonical_bytes(a.run.scope_receipt)
        == canonical_bytes(b.run.scope_receipt)

same_execution_frame(a,b) :=
    both operation == perspective_run
    AND both prompt_version == perspective-run/v1
    AND both pass the exact captured-input/template checks in E
```

Each digest is recomputed and validated before comparison; a digest claim alone
does not establish equality. `canonical_bytes` is P3's finite JSON codec: sorted
object keys, ASCII escaping, compact separators, UTF-8, **no trailing newline**.
Arrays preserve order. Question/text digests use exact UTF-8, not JSON encoding.
No trimming, Unicode normalization, paraphrase matching, punctuation repair,
locator rewriting, field removal or evidence-set-only comparison is permitted.
The original API's pre-capture trim is already reflected in the effective
question. It does not authorize another normalization of historical records.

There is no stable question or Scope identity to invent. Different run/receipt
IDs and execution/retention times do not prevent equal question/Scope bytes.
The complete Scope comparison includes evidence identities, roles, inclusion and
exclusion flags, exact source/highlight snapshots, locators, materialization and
the whole `study_packet`, when present. Different evidence ordering, mark edits,
metadata, filenames or reading progress can therefore prevent equality.

**Observed conservative limitation:** `_resolve_highlights` in
[Scope resolution](../../hermeneia/scope_resolution.py) supplies the current time
to `compile_synthesis_packet`. Its packet stores `compiled_at` at the top level
and in `provenance`, and includes `reading_trail` metadata. Those fields are
inside `scope_sha256`. The current prompt builder uses primary/supporting text,
not that packet. Equal provider-visible evidence is thus a weaker relationship
than v1's required complete Scope equality.

Provider-free in-memory inspection confirmed this: one synthetic highlight
`h1` on document `d1`, text `Passage`, page 1, locator `p.1`, rank 3, active,
created at `2026-09-30T10:00:00+00:00`; one document `source.pdf`, file hash
`sha256:example`, one page; empty Field Notes/reading progress and document scope
`d1`. Compiling only with `compiled_at=2026-09-30T10:00:01+00:00` versus `...02...`
changed only the packet's two `compiled_at` fields. SHA-256 of P3
`canonical_bytes(packet)` was respectively
`b2c2f0e75e2bc75189319bbf52a1cb81024f9a1a1ceb7602b73a0a73bc3da888` and
`43426bb7e5d7462e5d36620fb62b21b935b2bde494266975f8fe8f431ad5c4ea`.
This is a compiler/codec observation, **not** a full execution, provider, award
test or real-workspace result. The source path establishes its inclusion in Scope.

V1 deliberately returns no qualifying pair when only such metadata differs.
It does not label this unsupported: the recorded Scope difference is known.
Ignoring these fields would require a separately reviewed comparison boundary
and explicit later rule version. This packet neither strips provenance nor repairs
Scope generation. Primary/current-page Scopes without a study packet can still
have identical complete captured bytes across independently timed executions.

Provider/model/configuration need not match across the pair: they describe each
execution, not Perspective methodology. Exact prompt/output digests need not
match either. Distinct frames change prompts and can return identical or different
outputs. Neither output similarity nor difference contributes to qualification.

## 6. Perspective distinctness and Second Opinion v1

### Derived family key, not a new profile object

ADR-0045 names immutable declaration/revision nodes, not a separate stable
`PerspectiveProfile`. V1 derives this comparison key from existing evidence:

- Built-in: `("built_in", <stable built-in id>)`. Version identifies the exact
  executed definition but does not create another family by itself.
- Saved: `("canonical_saved", <validated root Perspective id>)`. Starting at the
  executed node, traverse existing incoming Perspective supersession relations
  to the root. Every visited node must be supported frame-v2 with a valid
  fingerprint and exact identity under its recorded predecessor context.
  Every step has zero or one incoming **relation row**, not a deduplicated set
  of predecessor IDs; two rows are ambiguous even if both name the same parent.
  Require complete endpoints, unambiguous Perspective typing and no cycle.
  A zero-predecessor root must validate using the existing root declaration
  context. A missing edge on a revision cannot be treated as a fresh root: its
  existing ID will not validate under root context.

All visited Perspective rows and exact relation keys are evaluation evidence.
The relevant graph is already exported in `study/perspectives.json` and
`study/perspective_supersessions.json`. A missing schema or legacy ancestor with
insufficient frame-v2 coverage makes family comparison unsupported. A broken
claimed complete graph, contradictory identity, ambiguity or cycle is invalid.
Sibling branches share a root. Current-leaf state, labels, display revision
numbers, declaration date or actor name do not substitute for this traversal.

The root key is a disposable predicate input. It is not persisted as canonical
identity and does not merge nodes or erase distinct human declarations. A saved
adoption of a built-in remains its separate saved declaration; the duplicate
methodology gate below prevents an unchanged adoption from becoming a second
methodological opinion.

### Option B: exact recorded methodological difference

Define `M(r)` as the captured definition object containing only:

```text
purpose, questions, challenges, limitations
```

Compare its exact P3 canonical bytes. Preserve all stored strings, ordering and
duplicates; do not rerun draft normalization or apply linguistic judgments.

```text
distinct_perspective(a,b) :=
    family(a) != family(b)
    AND a.run.perspective.definition_fingerprint
        != b.run.perspective.definition_fingerprint
    AND canonical_bytes(M(a)) != canonical_bytes(M(b))
```

The full fingerprint includes `label` under ADR-0045. This additional award gate
excludes **label-only** differences; it does not remove the label from canonical
Perspective identity or contradict the ADR's rename semantics. Equal definitions
under different declaration actors/root IDs do not qualify. Nor does a renamed
copy with identical methodology fields. Same family under a changed revision or
reversion never qualifies, even if methodology changed. Different families can
qualify with the same provider/model.

This operational distinction proves different declared families with a literal
methodology-field difference. It does **not** prove intellectual distance,
independent thought, originality or substantive disagreement. Punctuation or
paraphrase differences in methodology can pass; semantic duplicates cannot be
detected without a later approved boundary. Ordered-list differences count under
the existing frame-v2 semantics. Detectable exact/label-only duplicates fail;
ambiguous provenance is not resolved by text similarity.

### Frozen rule

| Contract | Frozen value |
| --- | --- |
| `achievement_id` | `second_opinion` |
| `rule_id` | `achievement.second_opinion` |
| `rule_version` | `1.0.0` |
| Qualified rule reference | `achievement.second_opinion.v1.0.0` |
| Required evidence | Two different canonical receipts, each satisfying E; exact question/Scope/frame equality; complete supported family evidence; exact methodology distinction |
| Predicate | There exist distinct a,b with E(a) AND E(b) AND same_question(a,b) AND same_scope(a,b) AND same_execution_frame(a,b) AND distinct_perspective(a,b) |
| Future award witness | Section 8's exact deterministic pair and section 10's equality/distinctness evidence |
| Result states | Section 7, including unsupported family coverage |

There is no required interval, session, causal sequence, downstream use, agreement
or comparison judgment. Two runs of one family are preserved history but cannot
satisfy Second Opinion. Different models alone cannot satisfy it. Two distinct
supported built-in families, two valid saved roots or a built-in/saved pair can
qualify, subject to every gate above.

## 7. Coverage and result semantics

The evaluation universe is the coherent snapshot of **extant, eligible, explicitly
retained P3 records** in one workspace/bundle. It is not all past activity and is
not a named person's career. User filters, pagination and a selected profile must
not restrict that snapshot and then masquerade as workspace-wide coverage.

Minimum source support:

- Local read: existing supported receipt table/columns, all extant rows read in
  one read-only transaction, required reference schemas/rows available, and
  unfiltered Lineage eligibility/omissions accounted for. This establishes current
  extant-category coverage under P3's portability mechanism, not historical
  capture completeness. No evaluation may create the table to manufacture support.
- Bundle read: supported WBS version with required capability
  `perspective-retained-execution-v1`, exactly one canonical manifest entry for
  `study/perspective_executions.json`, valid component hash/rows/IDs/counts and
  complete required dependencies under existing WBS validation. A corrupt claimed
  bundle is refused before evidence use; cherry-picking its good rows is not allowed.
  Additional saved-family closure must be validated for Second Opinion.

P3 `_read_perspective_executions` returns `coverage.perspective_execution_receipts`
with `status=covered`, `extant_records=n` and the explicit no-complete-history
caveat. Without capability/component it returns `status=unsupported`, **not**
zero activity. WBS 1.1/1.2 alone and schema version alone are insufficient.

Restoring a legacy bundle may initialize an empty current receipt table. P3 does
not persist an import-history coverage marker. Direct evaluation of that legacy
bundle stays unsupported. Evaluating the restored current database may describe
its covered **current extant** category; it cannot upgrade the legacy import to
complete historical coverage. Re-export has the same bounded meaning. No rule
backfills old runs or infers that Perspectives were never used.

| Result | Meaning and precedence |
| --- | --- |
| `earned` | A completely validated supported eligible witness/pair exists in a source that passes its integrity boundary. Unrelated excluded, invalid or unsupported local records cannot undo that existential proof, but their diagnostics/limits remain explicit |
| `invalid_evidence` | Without such a witness, a known malformed/tampered/contradictory claimed supported receipt or required binding/graph prevents a trustworthy decision. Fatal source/bundle integrity failure also refuses evaluation; it never becomes `not_earned` |
| `unsupported_due_to_missing_coverage` | Without a witness or known invalidity, required table/columns, profile/template support, family ancestry or source coverage is absent/unknown; unresolved omissions also refuse a negative conclusion |
| `not_earned` | No witness exists in a fully enumerated, classified, supported extant eligible category, with no unresolved invalidity/coverage needed to decide the predicate. Means only “no qualifying retained evidence in this evaluated snapshot under this version” |

Check source-level integrity first. Then independently validated positive
witnesses take precedence over unrelated local-row diagnostics; without a positive,
known invalidity takes precedence over unknown coverage. Negative decisions need
all relevant omissions classified. Lineage's `coverage.omitted` count conflates
exclusion, corruption and missing/ambiguous parents: the count alone may establish
neither `invalid_evidence` nor safe `not_earned`. A future adapter must distinguish
them through read-only supported evidence checks. A valid explicitly excluded
record is outside eligibility, not malformed; exclude its descendants/text too.

Unknown optional runtime metadata or generic human identity does not invalidate
a supported receipt: those limitations are built into E. Unsupported definitions,
receipt/prompt versions or family histories cannot be assumed equivalent. A valid
receipt with unsupported root ancestry may establish Explorer while leaving a
possible Second Opinion pair unsupported. Incomplete unrelated categories such
as coaching or Blueprint history do not block these narrow rules.

Neither `not_earned` nor absence in a covered empty table means “the user never
used Perspectives.” P1/P2's original unknown-history wording is unchanged.

## 8. Deterministic witness selection and timing

For each E-valid receipt define:

```text
K(r) = (retained_at parsed as an aware UTC instant, receipt.id)
```

Receipt IDs are compared in ASCII lexical order. Use the original recorded time,
not file time, database row order, current time, display text or completion time.
Equal instants with different timezone representations tie by identity. Parsing
for ordering does not rewrite the historical timestamp. Recorded chronology does
not prove causal order or clock accuracy.

Explorer selects the minimum K(r). Second Opinion enumerates all qualifying
unordered pairs of different receipt IDs, orders each pair by K, and chooses the
lexicographically minimum `(K(left), K(right))`. This is deterministic among the
validated supported eligible records of the evaluated snapshot, not a claim of
the earliest pair ever used. Three or more receipts produce one exact pair; later
current eligibility may select differently when additional records exist. A
historical award's original witnesses remain unchanged.

Repeated views, filters, duplicate Lineage presentations or repeated Keep of one
run do not inflate counts. Unique canonical receipt/run bindings own the history.

## 9. Edge-case matrix

`EARN` = earned; `NO` = bounded not_earned; `UNSUP` = unsupported coverage;
`INVALID` = invalid_evidence. `C` = supported, validated extant category; `U` =
required coverage missing; `I` = claimed supported evidence invalid. Unless stated,
records pass E, source/closure support is complete, and question/Scope/frame match.
These are frozen design examples, **not tests executed or awards issued**.

| # | Extant evidence scenario | Explorer | Second Opinion | Coverage | Reason |
| --- | --- | --- | --- | --- | --- |
| 1 | One retained Perspective | EARN | NO | C | One supported witness, no pair |
| 2 | Two runs of the same saved root/revision | EARN | NO | C | Repetition is one family |
| 3 | Same saved family, different immutable revision and methodology | EARN | NO | C + validated ancestry | Revision alone does not create a second family |
| 4 | Two distinct families/methodologies, same provider/model | EARN | EARN | C | Provider is not methodology |
| 5 | Same family/revision, different provider/model | EARN | NO | C | Execution change alone does not qualify |
| 6 | Distinct families/methodologies, exact question and complete Scope | EARN | EARN | C | Exact qualifying pair |
| 7 | Distinct families, same question, different Scope evidence | EARN | NO | C | Captured Scope differs |
| 8 | Distinct families, paraphrased questions | EARN | NO | C | Exact question bytes differ |
| 9 | One retained plus one transient run | EARN | NO | C | Transient result is outside canonical evidence |
| 10 | One retained plus one discarded run | EARN | NO | C | Discard creates no durable P3 execution |
| 11 | One failed transient run plus one retained success | EARN | NO | C | Failure does not satisfy E |
| 12 | Legacy workspace/bundle without P3 category support | UNSUP | UNSUP | U | No invented zero/history |
| 13 | Covered extant category with zero rows | NO | NO | C, n=0 | Current retained-evidence result only |
| 14 | Three receipts with exactly one qualifying pair | EARN | EARN | C | Select that exact pair |
| 15 | Distinct saved root IDs/actors, identical full definitions | EARN | NO | C | Duplicate fingerprint/methodology |
| 16 | Verified restored WBS with a qualifying pair and complete graph | EARN | EARN | C | Exact portable receipts/closure survive |
| 17 | Only a malformed/tampered claimed P3 receipt | INVALID | INVALID | I | No validated witness; not negative history |
| 18 | Valid retained response later unused | EARN | NO | C | Use is not required |
| 19 | Qualifying pair whose outputs the human disagreed with | EARN | EARN | C | Retention is not agreement |
| 20 | Qualifying pairs share exactly the same retention instant | EARN | EARN | C | ASCII receipt identity breaks selection ties |
| 21 | Differently labeled copies with identical methodology fields | EARN | NO | C | Label-only difference fails additional gate |
| 22 | Built-in plus its unchanged saved adoption | EARN | NO | C | Different origin/family is insufficient |
| 23 | One supported built-in v1 plus a run claiming another, unsupported version | EARN | UNSUP | C for witness; U for version | No catalog version is fabricated; version change cannot establish a second family |
| 24 | Two valid saved nodes; one has unsupported legacy ancestor | EARN | UNSUP | C for receipts; U for family | Exact node can qualify; stable family comparison cannot |
| 25 | E-valid executed nodes in a local store, but an upstream ancestor has contradictory/cyclic family evidence required for the only possible pair | EARN | INVALID | C for nodes; I for ancestry | Executed-node validity does not validate the complete family |
| 26 | Same highlight inputs, different captured packet compilation time | EARN | NO | C | Full Scope hash/bytes differ despite matching evidence |
| 27 | Same question/Scope, different outputs including identical outputs | EARN | EARN | C, distinct families/M | Output similarity/difference is irrelevant |
| 28 | Complete supported category with only valid excluded receipts | NO | NO | C + classified exclusion | No eligible witness; no copied child evidence leaks |
| 29 | Unknown receipt omissions and no visible witness | UNSUP | UNSUP | U | Aggregate omission count cannot prove absence |
| 30 | Only unknown built-in revision/template | UNSUP | UNSUP | U | No replacement with today's definition |
| 31 | Complete qualifying pair plus unrelated malformed local row | EARN | EARN | C for witnesses; I note | Existential proof survives; malformed evidence stays diagnostic |
| 32 | Claimed WBS component has mismatched manifest hash | INVALID | INVALID | I at source boundary | Refuse whole claimed bundle before evidence use |
| 33 | Reversion and sibling saved revisions share validated root | EARN | NO | C | All belong to one declared family |
| 34 | Distinct roots with literal methodology paraphrase differences | EARN | EARN | C | Exact-field distinction; semantic duplication remains unknown |
| 35 | Prompt digest is valid but prompt conflicts with captured inputs | INVALID | INVALID | I | Hash consistency alone is not E's template binding |
| 36 | Same Scope evidence IDs but changed text/flags/order/metadata | EARN | NO | C | Evidence-set identity alone is insufficient |

An inserted canonical row claiming `status=failed` is invalid P3 evidence rather
than a retained success. Case 11 instead describes the actual supported product
path: failed activity stays transient. Case 31 is a local-source result, not
permission to bypass a corrupt bundle's source-level integrity refusal.

## 10. Future award receipt evidence contract — not implemented

The subsequent packet must define a bounded append-only award representation and
portability before release. This document freezes required evidence content,
not a table, codec, ID derivation, deduplication scheme or write API:

- Immutable `award_id`, `achievement_id`, exact `rule_id` and `rule_version`, and
  truthful `awarded_at` (time the award is recorded, not inferred execution time).
- Exact selected typed Lineage identities with event/type basis, underlying
  Perspective receipt IDs and run IDs. Never substitute a label, model name,
  current successor or duplicated output text.
- Required/observed coverage basis: local snapshot versus verified bundle,
  supported receipt schema/capability, extant enumeration/count, eligible set and
  classified omission/invalid/unknown limits. Preserve the no-complete-history
  qualification. For bundles, retain the exact manifest/component evidence
  identity already validated; do not invent package or release equivalence.
- Deterministic evaluation provenance: frozen rule definition digest, evaluator
  version, supported built-in catalog/template revision evidence, exact source
  record/dependency digests or immutable typed bindings actually validated, and
  the sorted evaluated supported-candidate identities used for witness selection.
  Mutable eligibility observations must be captured as observations at evaluation,
  not later inferred from changed source state. No second canonical event stream.
- Result `earned`, symbolic checks/reason, selected witness ordering keys and
  diagnostics/unsupported limits. Evaluation itself does not award or write.

For Second Opinion additionally retain the ordered exact pair and:

```text
question_basis = exact UTF-8 + validated question_sha256
scope_basis = complete P3 canonical bytes + validated scope_sha256
execution_frame_basis = operation + supported prompt_version/template checks
distinctness_basis = typed family keys + exact full definition fingerprints
                    + exact methodology-field comparison
saved_family_evidence = visited typed Perspective IDs + exact relation keys
```

The canonical execution receipts already own prompt, question, Scope and model
output; an award references them, without duplicating those payloads. Exact
methodology comparison bytes can be derived from the referenced immutable
definitions. Required unknown provenance remains unknown. `awarded_at` is truthful
run-specific history; deterministic evaluation and award-recording time are
separate concerns. Later loss/ineligibility of evidence can make revalidation
unsupported but cannot silently erase or reinterpret a historical award.

## 11. Rule versions and historical meaning

Use the existing ASCII `major.minor.patch` convention without leading zeros,
with a separate rule identity and immutable released definition/digest. The
qualified `.v1.0.0` spelling is a display/reference form, not another rule owner.
The capability registry and this future achievement registry remain separate:
changing an achievement must not silently modify `explore_perspective`.

- Patch: explanatory/editorial corrections or implementation repairs that restore
  the already frozen predicate without changing its meaning. Identify evaluator
  repairs separately and never silently revise a previously issued award.
- Minor: a deliberate backward-compatible extension of supported evidence or
  an additive assessed claim, with an explicit new definition/version. Any
  qualification change still needs review and a new rule version.
- Major: replacement equality/distinctness/coverage meaning, new required
  authority, or a deliberately incompatible predicate. For example, replacing
  complete Scope equality with a metadata-excluding basis changes this boundary.

These are frozen conventions for this profile, not a claim that existing code
already enforces achievement semantic-versioning policy. At minimum **every
predicate-semantic change gets an explicit new rule version**. An old award
remains “earned under v1.0.0” even if v1.1.0/v2 assesses current eligibility
differently. No silent revocation, rewrite, historical recalculation or migration.
Current eligibility and historical award history are different outputs.

## 12. Deferred claims and known limitations

These rules do not establish or define Multiple Lenses, Agreement Mapper, Dissent
Finder, Evidence Split, Assumption Spotter, Minority Report, Perspective Revision,
Perspective Resistance, Triangulator, Perspective Cartographer, Adjudicator, or
Independent Synthesis. Those require later explicit human comparison/adjudication
or other missing evidence. Neither multiple retained outputs nor different text
can replace it. Full Cycle, intent, independence and complete coaching history are
also outside this slice.

Known limits are precise:

- Complete Scope equality can be too restrictive for repeated highlight-backed
  inquiry because compilation/progress metadata differs. V1 exposes that refusal;
  changing the comparison boundary requires later review.
- Family keys are derived from complete supported ancestry, not stored profiles.
  Legacy/missing graphs cannot be normalized into support. Read checks for full
  ancestry, catalog identity and prompt binding remain implementation obligations.
- Exact methodology inequality cannot establish substantive intellectual distance
  or detect paraphrased duplication. It never establishes independent reasoning.
- The local steward is unauthenticated; unexposed execution defaults are unknown.
  Input/output binding is an audit of the stored record and capture contract, not
  provider attestation or a fresh audit of external source files.
- P3 covers extant retained executions, not all previous use, sessions, discarded
  outputs, Room activity or overwritten mutable annotation history. No historical
  completion/failure/absence is inferred from this narrower universe.
- Future award ID/write/portability mechanics are not implemented or fully
  specified here. Award history must receive its own exact reviewed contract;
  this evidence list does not authorize an ad hoc history table.

## 13. Verdict, validation and next bounded packet

**GO — P3 evidence is sufficient to implement both v1 rules deterministically.**
Explorer needs no added history; Second Opinion needs a read-only ancestry
projection and exact-field gates over existing durable records. No missing
immutable field, new canonical profile object, semantic adjudication or schema
change is required to evaluate these narrow predicates. This is sufficient-data
readiness, not a claim of existing evaluator implementation, awards, real-use
validation or the deeper achievement ladder.

Validation in this packet: clean starting tree/required commit; inspected actual
receipt/storage, identity/revision, Scope/prompt, Lineage, WBS, capability v1/v1.1
and P2 names/contracts; provider-free in-memory packet timestamp observation;
documentation reference/field checks and `git diff --check`. No tests or production
files changed. No full suite was run: this is docs-only. The P3 note preserves its
independently measured six-Reader-failure baseline; this packet makes no fresh
regression or provider/real-workspace claim.

Next bounded packet, after review of this freeze: implement only the two versioned
provider-free evaluators and their read-only evidence adapter, with focused
adversarial tests for every gate, coverage status and deterministic selection.
Use the current canonical receipt owner and Lineage eligibility; do not change
P3/WBS/Capability Registry semantics to make a pair qualify. Define the exact
append-only award/portability contract for review before award persistence or UI.
Stop on unsupported ancestry, missing catalog/template support or pressure to
relax Scope/methodology equality rather than silently widening v1. No P4 engine,
award, table, badge or schema is implemented by this packet.
