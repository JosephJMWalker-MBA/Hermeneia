# Frozen-witness repair campaign — 2026-10-06

**Result:** The campaign repaired all 21 defects it was authorized to repair:
#216, the 20 open bugs #220–#238 from the `bdf280a` investigation, and #239,
which was found during the campaign. Each repair followed a committed strict
expected-failure witness. After each fix, the witness showed strict unexpected
passes and was promoted to a regression test. A second new defect, #240, was
filed and classified but not repaired. *(Superseded: see the merge-readiness
audit addendum below; #235 was completed and #240 repaired.)*

Final verification gave these results:

- all 121 campaign regression tests pass;
- every filed reproduction now shows the repaired behavior;
- the full suite fails only the six static Reader baselines that also fail at
  `bdf280a`;
- the protected-copy real-study round trip remains exactly equivalent.

- **Frozen baseline:** `bdf280a`, preserved unchanged with the filed issues as
  historical witnesses.
- **Branch:** `repair-campaign` at `242a826`. Local only; not pushed or merged.
- **Inventory:** the repair map from the `bdf280a` investigation, with seven
  clusters: source-artifact binding, schema readiness, route hygiene,
  governed-candidate binding, execution identity, Scope enforcement and CLI
  resolution.
- **Safe study alias:** `study-d88c4a642956`

## Method

Every packet followed the same steps:

1. reproduce the filed witness;
2. commit the smallest deterministic strict-xfail witness (a `test:` commit);
3. confirm the governing authority;
4. make the smallest correction (a `fix:` commit);
5. show `XPASS(strict)`, then remove the markers and record the witness commit
   in the test docstring;
6. run focused and neighboring tests;
7. rerun the issue's reproduction;
8. comment on the issue with the evidence.

No contract or existing assertion was weakened to make a test pass. Race
witnesses use barriers or injected faults at real seams, not timing luck.
Providers were fakes or the offline `null` adapter, and no external call was
made.

## Bug → frozen witness → repair → regression test → final result

| Bug | Frozen witness | Repair | Regression test | Final result |
| --- | --- | --- | --- | --- |
| #216 hybrid `perspectives` schema crashes WBS export | `c4d4f27` | `5171faf` | `test_workspace_export_hybrid_schema.py` | **Fixed.** Reproduction exports. Real-study round trip is exactly equivalent. |
| #237 write routes leak open transactions | `683ae5d` | `1acb5ba` | `test_route_write_transaction_lifecycle.py` (10 routes) | **Fixed.** Teardown rolls back and closes. |
| #236 reading-progress race loses pages / first-visit 500 | `d814812` | `90aae9f` | `test_reader_progress_atomicity.py` | **Fixed.** `BEGIN IMMEDIATE` upsert. |
| #226 first 100% post never sets `completed_at` | `d814812` | `90aae9f` | `test_reader_progress_atomicity.py` | **Fixed.** Reproduction records `completed_at`. |
| #225 CLI silently uses `./build/hermeneia.db` | `04a574d` | `7a4bcff` | `test_cli_target_resolution.py` | **Fixed.** A missing target exits 1 with "Database not found", and `--db` reads exactly the named file. |
| #222 same-filename upload discards source bytes | `3b1caca` | `180adab` | `test_upload_source_binding.py` | **Fixed.** Both documents keep their bytes. |
| #223 `original_filename` records a temporary name | `3b1caca` | `180adab` | `test_upload_source_binding.py` | **Fixed.** Records `My Study.pdf`; bytes are stored under their SHA-256. |
| #224 re-upload applies role to a different document | `3b1caca` | `180adab` | `test_upload_source_binding.py` | **Fixed.** The role lands on the uploaded document. |
| #239 client filename becomes a storage path *(found in 4a)* | `3b1caca` | `180adab` | `test_upload_source_binding.py` | **Fixed.** Nothing is written outside `uploads/`. |
| #229 export packages any file in `uploads/` as canonical | `39fcb0b` | `3c35441` | `test_export_source_bytes.py` | **Fixed.** Only SourceDocument bytes are canonical. |
| #238 export reads uploads outside its snapshot | `39fcb0b` | `3c35441` | `test_export_source_bytes.py` | **Fixed.** Uploads are read inside the snapshot, and missing bytes are classified in the manifest. |
| #221 failed compile leaves partial evidence chain | `6e45298` | `ca1aaa4` | `test_compile_atomicity.py` | **Fixed.** Returns 500, writes 0 rows and keeps the source bytes. |
| #234 E10 attributes template text to unconnected models | `b9d615e` | `ee231a1` | `test_e10_execution_identity.py` | **Fixed.** Returns 409 with no proposals; `generating_model` comes from the executing adapter. |
| #231 UI claims verbatim recording of unsaved text | `4738bbf` | `f98e1d0` | `test_ratify_draft_candidate.py` | **Fixed.** The response reports `matches_submitted`, and the Reader shows "Draft not saved". The immutability rule is unchanged. |
| #235 ratified drafts lose the CI-011 record | `4738bbf` | `f98e1d0` | `test_ratify_draft_candidate.py` | **Fixed for the Reader path,** through the server-held candidate. *(Superseded: fully repaired by `f22fc2a`; see addendum.)* |
| #232 Blueprint accepts excluded evidence | `4d520a9` | `cfa9423` | `test_blueprint_exclusion_scope.py` | **Fixed.** Returns 403 `excluded_from_analysis`, with 0 Blueprints and 0 prompts containing muted text. The Artist refuses plans whose evidence was excluded later. |
| #230 transient EF failure leaves a report with no Findings | `9e71daa` | `f21c593` | `test_critic_ledger_atomicity.py` | **Fixed.** A faulted run returns 500 and records nothing. The retry returns 201 with 18/18 Findings, and legacy empty ledgers are completed. |
| #220 proof PDF returns HTML 500 without authoring tables | `90c1acb` | `0ea9873` | `test_read_paths_without_ddl.py` | **Fixed.** Returns 404 `NO_PROOF_PDF`. |
| #233 `herm trace` / `herm profile` create schema, fail read-only | `90c1acb` | `0ea9873` | `test_read_paths_without_ddl.py` | **Fixed.** Both exit 0 on a mode-0444 workspace and create nothing on older ones. |
| #228 non-object JSON body returns 500 on 20 routes | `02f4013` | `242a826` | `test_malformed_request_inputs.py` (40 cases) | **Fixed.** Structured 400. |
| #227 non-integer `limit` returns 500 | `02f4013` | `242a826` | `test_malformed_request_inputs.py` | **Fixed.** Falls back to the default. |
| #240 JSON `null` profile becomes slug `"None"` *(found in 5b)* | — | — | — | **Filed, not repaired.** *(Superseded: repaired by `09b94b2`, witness `38beb7a`; see addendum.)* |

## Bug fixed, known limitation, architectural improvement

**Bugs fixed (21):** #216, #220–#239.

**Known limitations, kept and disclosed:**

- *(Withdrawn by the addendum: not a permitted limitation.)* **#235, text-only API path.** `ratify-draft` without `candidate_id` still
  records only `{provider, source}`. The server holds no execution for
  arbitrary submitted text. The issue's original snippet uses this path and
  so still shows the reduced record. The Reader always sends the candidate.
- **Preview candidates are in memory.** Server-held Artist preview candidates
  are bounded at 100, like Perspective execution candidates. After a restart
  or eviction, ratify returns 404 and the steward previews again.
- **#231, immutability unchanged.** A different second draft for the same
  (plan, provider, profile) is still not saved. It is now reported rather
  than silently confirmed.
- **#232, status codes.** The commit-time refusal is 403. The Artist-side
  defense-in-depth refusal surfaces as 400 (`ExcludedEvidenceError`, an
  `ArtistRenderError`).
- **#230, behavior change.** A Critic run whose Evaluation Function fails
  persistently now fails visibly instead of storing a partial ledger
  (ADR-0042 completeness).
- **#217–#219.** Closed earlier as KNOWN: already disclosed in the frozen #213
  audit.
- **Round-trip count differences.** Derived tables, `workspace_identity`,
  `reading_progress` and absent authoring tables differ in counts. This is
  unchanged from the packet 0 rerun and is existing bundle scope, not a
  campaign effect.

**Architectural improvements introduced by repairs.** These are the
mechanisms that made the repairs possible, not features:

- request-scoped write connections with teardown rollback;
- content-addressed upload storage, with the client filename kept only as
  metadata;
- SourceDocument-driven source-bytes export with manifest classification;
- `SQLiteStore.atomic()` / `Repository.transaction()`, reused by the Critic
  ledger;
- one CLI database-target resolver;
- up-front participant adapter construction with adapter-reported model
  identity;
- server-held Artist preview candidates;
- one shared excluded-evidence rule (`excluded_evidence_ids`);
- `_json_body` / `_int_arg` request helpers.

No constitutional ontology or authority changed.

## Final verification

1. **Witnesses.**
   - All 13 campaign regression files (121 tests) pass together, and no
     xfail markers remain.
   - The 17 filed Python reproductions were rerun at `242a826` with outbound
     sockets blocked. Each showed the repaired behavior, except #240
     (unrepaired) and the #235 text-only path (the known limitation).
   - #232's snippet stops at its now-refused ratify (403).
   - #225 and #233 were reproduced through `python -m hermeneia.cli.main`.
   - #236, #237 and #238 have no standalone snippet; their deterministic
     regression witnesses cover them.
2. **Full suite.** 2802 passed, 21 skipped, 6 failed. The six failures are
   static Reader UI checks:
   - `test_reader_accessibility` (2);
   - `test_reader_blueprint_workstation`;
   - `test_reader_record_view` (2);
   - `test_reader_voice_profile`.

   They fail identically on the frozen `bdf280a` copy (6 failed, 58 passed in
   those four files). The run included two unrelated uncommitted
   working-tree edits by others (Reader corpus-search navigation in
   `index.html` and its test). Those edits were not committed by this
   campaign.
3. **Real-study protected-copy round trip** (`242a826`). The seven original
   files were copied with filesystem reads only. The copy was verified
   byte-identical before any database access. All captures were read-only on
   the copy, and outbound sockets were blocked. No award was issued.
   - Copy and identity checks:
     - the original was unchanged after the copy and at the end;
     - receipt, run, package digest and alias all match the 2026-10-03 state;
     - the copy's bytes, logical dump and counts were unchanged by export.
   - Export: WBS 1.1, 1 receipt, 0 awards, `source_bytes` = 1 document,
     0 missing, and exactly one upload in the bundle. Restore covered both
     categories.
   - Comparison: Explorer `earned` → `earned`, Second Opinion `not_earned` →
     `not_earned`. Evidence, package digest, receipt bytes, Lineage item,
     coverage and diagnostics are all equal, with no dependency drift.
   - Decision: **`exact_equivalence`.** Every A/B field is identical to the
     packet 0 rerun; only the new `source_bytes` fields were added.
4. **Issue states.**
   - #216 and #220–#239 are open, each with a campaign comment naming its
     witness and repair commits. They stay open until the branch is merged.
   - #240 is open and unrepaired.
   - #217–#219 are closed as not planned (KNOWN).
5. **Comparison against `bdf280a`.** At `242a826`, before this note: 41 files changed, +2286/−315.
   - Production code:
     - `web/app.py`, `web/authoring_api.py`, `web/static/index.html`
       (`_crPreviewArtistDraft` / `_crRatifyDraft` only);
     - `workspace/export.py`, `compiler/compiler.py`;
     - `storage/sqlite.py`, `storage/repository.py`;
     - `narrative/artist_service.py`, `authoring/service.py`;
     - twelve CLI modules plus the new `cli/target.py`.
   - Tests: 13 new test files.
   - Five pre-existing tests were modified, none weakened:
     - **Three export/restore fixtures.** The seeded SourceDocument id is now
       the SHA-256 of the seeded bytes, matching the content-addressed
       identity contract (WBS §4, `15_Storage.md`).
     - **`test_explorer_discovery.py` and
       `test_e10_vertical_slice_api.py`.** These relied on the #234 null
       fallback to create proposals for unconnected participants. They now
       use in-process fake connected providers, and their assertions are
       unchanged.
   - No constitution, invariant, ADR or specification changed. `bdf280a` and
     its frozen copy are untouched.

## Not done

- P5–P10 feature work: stopped as instructed.
- #240 repair.
- Pushing, merging, or closing issues after merge.

Raw source text, private paths and workspace identity remain outside this
note.

## Merge-readiness audit addendum — 2026-10-06

**#235 contract check.** `docs/06_Ontology.md` § RenderedNarrative defines a
RenderedNarrative as expression produced by an ArtistProvider from the
ArchitectPlan, ExpressionProfile and ArtistProvider invocation metadata, and
requires it to preserve that execution context. Constitution Art. II and
CI-011 require the same record for nondeterministic objects and invocations.
A direct API ratification without a server-held preview has no observed
invocation, so the "known limitation" above is withdrawn. Witness `4eb0970`;
repair `f22fc2a`: `ratify-draft` requires `candidate_id` (400, nothing
persisted), and `ratify_draft` refuses to persist without the observed
`execution_config`. No provenance is constructed. Tests that ratified
arbitrary text now ratify real preview candidates; no assertion was removed.

**#240.** Witness `38beb7a`; repair `09b94b2`: `_optional_text()` treats
absent, null and blank Artist preview/ratify fields as "not given".

**#241 (new).** `revise-blueprint` with `reason: null` records the rationale
"None". Filed and classified BUG; not repaired. The same
`str(payload.get(k, ""))` idiom elsewhere was not individually audited.

**Audit results at `09b94b2`.**

- Every production hunk since `bdf280a` maps to a campaign witness or its
  supporting change.
- No constitution, invariant, ADR or specification changed; only the two
  verification notes were added under `docs/`.
- Seven pre-existing tests were modified (setup only); no assertion line was
  removed.
- Campaign regressions: 125 passed (the original 121 plus 2 for #235 and 2
  for #240), with no xfail markers left.
- Full suite on a clean detached worktree of HEAD: 2805 passed, 21 skipped,
  6 failed. On the working tree: 2806 passed, because of one unrelated
  uncommitted test. The six failures are the static Reader baselines, which
  fail identically at `bdf280a`.
- Protected-copy real-study round trip at `09b94b2`: `exact_equivalence`,
  with original guards intact. It is identical to the `242a826` run except
  for the HEAD hash.
- The unrelated Reader edits in `index.html` and
  `tests/test_reader_context_navigation.py` remain uncommitted and are absent
  from every campaign commit.

## Null-normalization audit and #241 — 2026-10-07

The campaign as audited above was pushed at `abe253e` and opened for review as
PR #242. Afterwards, #241 was repaired and one bounded audit was run, limited
to request- or provider-JSON conversions of the form `str(x.get(k[, d]))`
where JSON `null` becomes the string `"None"`.

**#241 repaired.** Witness `7e645ff`, repair `b6c8fd4`. `revise-blueprint`
now reads `reason` through `_optional_text()`, so a `null` reason gets the
existing 400 "revision reason is required" and nothing is persisted. The
witness's controls pin the absent and blank refusals and the verbatim
recording of a stated reason. Blueprint and governance neighbors: 483
passed.

**Audit inventory.** There are 31 unguarded conversions in
`hermeneia/web/app.py` and none in `authoring_api.py`. Helpers using
`str(v or "")` are null-safe; Perspective revision reasons, for example,
already were. Other unguarded conversions outside `app.py` read database
rows, bundle manifests or internal runtime JSON, so they are outside this
scope.

| Class | Sites (field) | Disposition |
| --- | --- | --- |
| Harmless / caught | provider key `api_key` (fails the 8-character check); steward `status` (not in the allowed set); voice-preview `text` and `profile_slug` (read-only) | none |
| Input-validation weakness | E10 `observation_id`; E10 critic `proposal_id`; revise `predecessor_id`; run-artist `plan_id`, `obs_ref`, `provider`, `profile`; run-artist-all-profiles `plan_id`, `provider`; run-critic `narrative_id`, `obs_ref`; architect/generate `directive`, `provider`; extract-blueprint `text`, `provider` | a misleading error or a bypassed "required" check, with no persisted `"None"`; not filed |
| Canonical-data corruption | Blueprint candidate `title`, `thesis`, `claim` (ratify, revise, extract-save) and architect/import `title`, `thesis`, `claim` | **#243** filed; *repaired 2026-10-07 (see below)* |
| Canonical-data corruption (machine output) | architect/generate provider `title`, `thesis`, `claim` | **#244** filed; *repaired 2026-10-07 (see below)* |
| Provenance / identity | preview/ratify `provider` and `profile` | fixed earlier as #240; no other persisted identity found |
| Governance state | revise `reason` | **#241 repaired** |
| Governance state | provider role calibration `note` (API-only) | **#245** filed; *repaired 2026-10-07 (see below)* |
| Governance state | narrative steward `rationale` | cannot persist, because the route always fails; see #246 |

**Incidental finding.** Filed as **#246**, not repaired. `PATCH
/api/reader/narratives/<id>/steward` always returns 500 "RenderedNarrative
immutable": it UPDATEs a table whose trigger forbids every update. This is a
specification/implementation conflict that needs an authority decision.

All four new issues were reproduced on `bdf280a` and at `b6c8fd4`, and each
reproduction was verified as written. Campaign regressions at `b6c8fd4`: 130
passed (the 125 above plus 5 for #241). #243–#246 are reported, not
implemented, because the narrow #241 boundary does not resolve them.

## Final normalization packet: #243–#245, and #246 adjudication — 2026-10-07

All three repairs use the existing `_optional_text()` boundary helper, because
they share its meaning exactly: JSON `null` is "not given", the same as an
absent key. Every route keeps its existing refusal, skip or default, and no
replacement content is introduced.

| Bug | Witness | Repair | Regression test | Result |
| --- | --- | --- | --- | --- |
| #243 null Blueprint title/thesis/claim | `b27b4e8` | `d03a81b` | `test_blueprint_null_fields.py` (13) | Ratify, revise and extract-save refuse a null field; import refuses a null title or thesis and skips a null-claim section, as it skips a blank one. The extractor's provider-reply check counts null as missing (422). Filed reproduction: 400 "title is required", 0 Blueprints holding `"None"`. |
| #244 provider null in architect/generate | `23c6438` | `bfa6c09` | `test_architect_generate_null_output.py` (5) | A null thesis gets "AI response missing thesis or sections"; a null claim is skipped (only-null claims get "No valid sections"); a null title takes the existing absent-title default. Blank titles are unchanged. Filed reproduction: 500, nothing committed. |
| #245 null calibration note | `74883be` | `68b40b7` | `test_calibration_note_null.py` (5) | A null note is stored as no note (null), like absent and blank notes. Filed reproduction: `steward_note` is null. |

**Test-isolation fix (`aaa4cc4`).** In `cfa9423` (#232),
`_validate_blueprint_references` imported `artist_service` lazily. If that
first import happened inside a test that had patched
`artist_providers.get_provider`, the patched function stayed bound for the
rest of the process, and
`pytest tests/test_blueprint_exact_commit.py tests/test_blueprint_exclusion_scope.py`
failed 2 tests at `42cbac5`. The full suite hid this because another module
imports `artist_service` during collection. The rule is now imported with
`app.py`. There is no behavior change, and every file that patches the
provider lookup passes in isolation.

**#246 adjudication (not repaired).** Classification (1):
- RenderedNarrative is append-only (Constitution Art. I and X;
  `06_Ontology.md` table; CI-005), so the trigger is correct and the route's
  in-place UPDATE does not conform.
- The mutable `narrative_status` design appears only in the explicitly
  non-authoritative `FUTURE_ARCHITECTURE_NOTES.md`.
- No ratified object records a narrative-level rejection, so a conforming
  repair needs an owner decision: either `ratification_records` for
  acceptance only, or a new ADR-ratified append-only narrative
  steward-decision record.
- The route fails closed, so no state is corrupted. It is pre-existing (root
  commit `b3441b5`) and outside this merge.

**Final gate at `68b40b7`.**

- Campaign regressions: 153 passed across 18 files, with no xfail markers
  left.
- Clean full suite on a detached worktree: 2833 passed, 21 skipped, 6
  failed. The six are the inherited static Reader baselines, identical to
  `bdf280a`.
- The real-study round trip was not rerun: these repairs change only
  request and provider input normalization, not persistence, export or
  ratification semantics.
- The unrelated Reader edits remain uncommitted and are absent from every
  commit.
