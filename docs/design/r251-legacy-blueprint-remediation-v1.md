# R-P8-LEGACY-1 remediation contract v1 (#251)

**Status:** frozen 2026-10-10, before any implementation.

- **Governs:** bounded remediation of the two legacy model-to-canonical
  Blueprint write routes recorded in #251.
- **Authority:**
  - #214 Decision 3: natural language proposes and never silently commits;
    acceptance is explicit and exact-version;
  - #215's P8 gate;
  - CI-011 (Nondeterministic Audit Record);
  - CI-015 ("Can provenance be lost?" must be No);
  - `docs/design/blueprint-proposal-p8-disposition.md` §2.
- **Precedes P9.**

**Owner constraints, 2026-10-10:**
- Preserve legacy historical rows unchanged, and make no retrospective
  human-approval claim.
- Leave the owner's uncommitted `index.html` and navigation-test edits
  untouched. A UI change is delivered as an isolated proposed patch, and work
  stops for integration approval.
- Synthetic workspaces and fake providers only: no real workspace, no live
  model, no P9, no broad UI refactor.
- Implement only independently safe server-side repairs. For any change to
  user-facing route behavior, stop and present the impact before enabling or
  merging.

## 1. Compatibility classes

| Class | Meaning | May ship by default in this packet |
| --- | --- | --- |
| **SAFE** | Every existing success path keeps its status, body and rows. Responses change only additively. A failure path may stop leaving partial state | Yes |
| **USER-FACING** | A caller can observe a different status, outcome or UI behavior | No: implemented behind the containment gate (§6) or as an isolated proposed patch, then stopped |

## 2. Permanent negative regression witnesses

R1–R6 from #251 become `tests/test_r251_legacy_blueprint_witnesses.py`. The
pattern follows `test_architect_generate_null_output.py` and
`test_ratify_draft_candidate.py`:

- Each witness reproduces the exact defect from #251 on a synthetic workspace
  with an in-process fake provider.
- When it observes that defect, it raises a risk-specific `AssertionError`
  subclass. Otherwise it asserts the governed outcome:
  - a refusal or no canonical row;
  - no provider call where one is forbidden;
  - nothing persisted.
- While a risk is exposed in a configuration, the witness is
  `xfail(strict=True, raises=<that class>)`. An unrelated failure is
  therefore never masked.
- A marker is removed only after the repair demonstrates a strict unexpected
  pass in that configuration.
- The expected evidence is never weakened. Each witness keeps the exact
  reproduced values from #251, for example the saved title
  `"Resampled proposal"` and the canned `"Extracted Blueprint"`.

## 3. Exact approval: R5

- **Current.** The onboarding "Ratify & Save Blueprint →" button calls
  `obExtractBlueprint(true)`. That posts `save: true` to
  `/api/pipeline/extract-blueprint`, which **re-runs the extractor** and
  persists the new result.
- **Required.** "Ratify & Save" commits the exact previewed candidate, never a
  second model result.
- **Existing authority.** `/api/pipeline/ratify-blueprint` is the human
  approval boundary. It persists the exact posted candidate, makes no provider
  call, and is already used by the Blueprint workstation. It is pinned by
  `test_blueprint_exact_commit.py` ("commit must not call the Blueprint
  extractor").
- **Smallest migration.**
  - **UI (USER-FACING; an isolated proposed patch, not applied).** The
    onboarding preview keeps its displayed `proposed_blueprint` object.
    "Ratify & Save" posts exactly that object to `ratify-blueprint`. No server
    change is needed for the Reader. The patch adds a Node-run UI test
    modelled on `test_ratify_draft_candidate.py`.
  - **Route containment (USER-FACING; gated).** In `governed` and `disabled`
    (§6), `extract-blueprint` with `save: true` answers 409
    `EXACT_RATIFICATION_REQUIRED` before any provider call. Nothing is
    written.
- **Deferred.** A server-held preview binding, as #231/#235 gave Artist
  drafts, would also stop client substitution and record CI-011 provenance.
  That is a larger change and not the smallest migration.

## 4. Reference integrity: R1, R2a, R2b (`/api/architect/generate`)

- **Current.** Each `obs_refs` entry is reduced to its first digit run and
  matched against a positional `OBS-n` numbering of every eligible
  Observation, while the prompt shows at most 40. `interp_refs` are matched by
  8-character prefix. Anything unmatched is silently dropped.
- **Required in `governed` and `disabled`.** These apply to every reference,
  after stripping surrounding whitespace:
  - `obs_refs` entries must be exactly `OBS-<n>`, where `<n>` has its own
    Observation line in the prompt. Otherwise the reference is `unshown`. The
    model cannot be supported by text it never saw.
  - `interp_refs` entries must be exactly `INTERP-<8 lowercase hex>`, matching
    exactly one Interpretation shown in the prompt. Otherwise it is
    `ambiguous`, `excluded` (it matches an Interpretation not eligible for the
    prompt) or `unknown`.
  - A token of the other kind is `wrong_type`. Anything else is `unresolved`.
  - Any invalid reference gives 422 `BLUEPRINT_REFERENCE_INVALID`, with an
    itemized `invalid_references` list (section, field, ref, reason) and
    `canonical_status: "not_persisted"`. Nothing is written.

  The route's own prompt already requires this: "Each section must cite at
  least one OBS-N from the list above", and "Do not invent observations or
  interpretations not in the lists above".
- **Default `legacy`.** Unchanged. **Class:** USER-FACING, because outputs
  that today persist with silent loss would refuse.
- **Out of scope.** `/api/architect/import` (human-authored import) uses the
  same digit resolver. It is not a model path, so it is recorded here and left
  unchanged.

## 5. Atomicity: R3 (`/api/architect/generate`)

- **Current.** The Blueprint and its links commit before the plan compiles. A
  compile failure answers 500 and leaves a Blueprint without a plan.
- **Required in all configurations.** The Blueprint, its links, the
  ArchitectPlan and its paragraphs commit in one transaction. On any failure
  the transaction rolls back, so nothing persists and the response is still
  500.
- **Required provenance.** This route persists none today. This packet adds
  none, because a CI-011 record for an ungoverned write path would legitimize
  it; the governed path is P8 with its receipts. Any future provenance record
  for this route must join the same transaction.
- **Class: SAFE.** The success path executes the same statements and commits
  once instead of twice. Only the failure path changes: it no longer leaves
  partial state.

## 6. Provider provenance: R6 (`/api/pipeline/extract-blueprint`)

- **Current.** `_call_provider` returns a canned Blueprint for the `null`
  provider (the onboarding UI default) and for any unrecognized client
  interface. The route presents it as a proposal and, with `save: true`,
  commits it as `extracted`.
- **Required:**
  - **All configurations (SAFE, additive).**
    - The extractor gains `provider_interface(provider)`. It returns
      `anthropic`, `openai`, `gemini` or `placeholder`, and `_call_provider`
      selects its branch through it, so the two cannot diverge.
    - Every extract response adds `execution: {provider, interface,
      model_executed, placeholder}`.
    - A placeholder is never labelled as an executed model.
  - **`governed` and `disabled` (USER-FACING).** Placeholder output is refused
    for preview and for save: 409 `NO_MODEL_EXECUTED`. Nothing is written, and
    no canned Blueprint is presented as a proposal.
- **Ratification is unchanged.** `ratify-blueprint` stays a steward commit of
  client-supplied content. It records `source="extracted"`, which Lineage
  projects as `derived` with no model identity, as today. The proposed UI
  patch shows the steward when no model ran.

## 7. Legacy direct-write containment: R4

**Gate:** `LEGACY_BLUEPRINT_WRITES`, set by environment variable
`HERMENEIA_LEGACY_BLUEPRINT_WRITES`. It follows P8's configuration-gate
pattern.

| Value | `architect/generate` | `extract-blueprint save:true` | Placeholder extract output |
| --- | --- | --- | --- |
| `legacy` (**default in this packet**) | Writes; legacy references (R1, R2 exposed); atomic | Re-runs and commits (R5 exposed) | Labelled, still returned and committable (R6 exposed) |
| `governed` | Writes only with exact, shown references; atomic (R4 exposed) | 409 `EXACT_RATIFICATION_REQUIRED` | 409 `NO_MODEL_EXECUTED` |
| `disabled` | 403 `LEGACY_DIRECT_WRITE_DISABLED` before any provider call or write | 409 `EXACT_RATIFICATION_REQUIRED` | 409 `NO_MODEL_EXECUTED` |

Unset means `legacy`; any unrecognized value means `disabled` (fail closed).
The extract preview (`save: false`) and `ratify-blueprint` remain available in
every mode.

**Replacement.** The model-assisted replacement for `architect/generate` is
P8 propose-and-review, using P8's candidates, exact acceptance and receipts.
P8 generation is itself release-gated (GENERATION_NOT_READY). So `disabled`
removes the Reader's model Blueprint generation until P8 is enabled. It does
so explicitly, with a 403 naming the setting, not silently.

**Recommended sequence. Each step needs owner approval:**
1. Integrate the UI patch (§3).
2. Default to `governed`.
3. Default to `disabled` once a P8 Reader surface and enablement exist.

## 8. Expected witness matrix after this packet

| Risk | `legacy` (default) | `governed` | `disabled` |
| --- | --- | --- | --- |
| R1 unresolved loss | exposed | repaired | repaired |
| R2a wrong-type binding | exposed | repaired | repaired |
| R2b unshown binding | exposed | repaired | repaired |
| R3 non-atomic | **repaired** | repaired | repaired |
| R4 model-direct write | exposed | exposed | repaired |
| R5 unreviewed resample | exposed at the route; closed for the Reader once the UI patch is integrated | repaired | repaired |
| R6 placeholder commit | exposed, but labelled | repaired | repaired |

## 9. History and non-goals

**History:**
- Existing `ai-generated` and `extracted` rows are not rewritten or
  relabelled.
- Lineage projection is unchanged (`unknown` and `derived`).
- No retrospective approval is claimed.

**Non-goals:**
- no default change of the gate;
- no merge;
- no applied UI change;
- no change to P8 generation;
- no CI-011 records for legacy routes;
- no change to `architect/import`;
- no live model.

## 10. Acceptance for this packet

- The witnesses match §8 under all three configurations.
- Existing route tests pass unchanged in the default configuration.
- The full suite is clean except the inherited Reader baseline.
- The P5–P8 datasets reproduce.
- The owner's Reader edits are byte-identical before and after.
- The proposed UI patch applies to `main`'s `index.html` (`git apply --check`
  against a scratch copy). Its UI test passes there. Its applicability to the
  owner's working copy is checked without modifying it.
