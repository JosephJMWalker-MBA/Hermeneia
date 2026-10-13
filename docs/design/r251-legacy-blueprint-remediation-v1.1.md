# R-P8-LEGACY-1 remediation contract v1.1 — proposal mode (#251)

**Status:** frozen 2026-10-13, before any implementation, on branch
`r251-proposal-mode`. It is stacked on `r251-legacy-blueprint-remediation`
`d38fdbc` (draft PR #253).

This amends `r251-legacy-blueprint-remediation-v1.md`. It does not replace
it: v1's `legacy`, `governed` and `disabled` behavior and its witness matrix
are unchanged.

**Owner instruction, 2026-10-13:**
- Produce a reviewable remediation that prevents model output from entering
  canonical Blueprint state without explicit human acceptance of the exact
  content.
- Reuse P8's governed candidate and acceptance architecture where
  appropriate, without pretending its generation competence gate has passed.
- Add CI-011 generation provenance where applicable.
- Do not merge, deploy, enable gated generation, close #251, or change
  production defaults without an explicit owner decision.

## 1. The gap v1 leaves

| v1 mode | Model generation available | Model output reaches canonical state without an exact steward decision | CI-011 record |
| --- | --- | --- | --- |
| `legacy` | yes | yes (R4) | none |
| `governed` | yes | yes (R4), with exact references | none |
| `disabled` | no | no | — |

No v1 mode both keeps model-assisted Blueprint drafting and satisfies #214
Decision 3 and CI-011. Every nondeterministic invocation whose output becomes
canonical must persist its complete input, parent identities, provider,
model, configuration, prompt, timestamps, raw output and resulting identity.

## 2. The decision this amendment needs from the owner (D1)

**Where does the CI-011 record and the exact steward decision for
legacy-generated content live?**

| Option | Mechanism | Assessment |
| --- | --- | --- |
| **(a) Reuse the P8 acceptance receipt** (implemented here, non-default) | The legacy generators produce server-held candidates of two new candidate schemas. The existing P8 accept, edit-and-accept and discard routes commit them, writing the existing append-only `blueprint_proposal_acceptances` receipt | The receipt's meaning, origin vocabulary (`model_proposed_steward_accepted` and `…_edited`), Lineage authorship (`accepted_model` and `human`), stale checks, atomic commit, immutability and WBS declaration all already fit. It adds no second acceptance ontology and no new table. **Cost:** P8's receipt validation and verification learn two more candidate schemas (§5) |
| (b) A new legacy acceptance record | A new append-only table and receipt | It duplicates P8's record with the same meaning. It needs a new Lineage projection, a WBS declaration and a verifier. Rejected as unnecessary new canonical state |
| (c) Retire the legacy generators in favor of P8 propose-and-review | The Reader calls P8 | This is the right end state, but P8 generation is release-gated (GENERATION_NOT_READY) and enabling it needs the owner. Not available now |
| (d) Propose-only routes plus steward ratification through `ratify-blueprint` | The steward posts the reviewed content | Exact human acceptance, but CI-011 is lost. Model content becomes `extracted` (Lineage `derived`) with no model identity. Rejected; it remains v1's interim UI patch only |

Option (a) is implemented behind a new, non-default mode so it can be
reviewed. Merging it is the owner's decision.

## 3. New gate value `proposal`

`HERMENEIA_LEGACY_BLUEPRINT_WRITES` and `LEGACY_BLUEPRINT_WRITES` gain one
value. The unset default stays `legacy`, and an unrecognized value still
fails closed to `disabled`.

| `proposal` | Behavior |
| --- | --- |
| `POST /api/architect/generate` | The same legacy evidence selection and prompt, byte for byte. Exact references are required, exactly as in `governed`; failures are 422 `BLUEPRINT_REFERENCE_INVALID`. On success it **writes nothing**: the response is 201 with a server-held candidate (§4) and `canonical_status: "not_persisted"` |
| `POST /api/pipeline/extract-blueprint`, `save: false` | The preview also holds a candidate. The response keeps `proposed_blueprint` and `execution` and adds `candidate` and `canonical_status: "not_persisted"`. The status code stays 200 |
| `POST /api/pipeline/extract-blueprint`, `save: true` | 409 `EXACT_RATIFICATION_REQUIRED`, before any provider call, as in `governed` |
| A placeholder provider (no model ran) | 409 `NO_MODEL_EXECUTED`, before any provider call or candidate, on both routes |
| Acceptance | **Only** through the existing P8 routes: `POST /api/blueprint/proposals/<candidate_id>/accept` with `accept` or `edit_and_accept`, and `…/discard`. Their behavior is unchanged |
| `ratify-blueprint`, `revise-blueprint`, `architect/import` | Unchanged (steward routes) |
| P8 generation (`POST /api/blueprint/proposals`) | Unchanged and still gated by `BLUEPRINT_PROPOSAL_GENERATION` (default `disabled`). This amendment never enables it |

### Refusals specific to `proposal`

Each refusal writes nothing and holds no candidate.

| Code | Status | Condition |
| --- | --- | --- |
| `NO_MODEL_EXECUTED` | 409 | **architect:** the provider's `execution_config()` reports provider `null` or no `model_id`. **extract:** the extractor interface is `placeholder` |
| `EXECUTION_NOT_RECORDABLE` | 409 | **architect:** the provider exposes no `execution_config()`. **extract:** the provider exposes no model identity. CI-011 cannot be met, so no candidate is held |
| `BASIS_INELIGIBLE` | 409 | A record shown in the prompt is not eligible under Study Lineage. The prompt is legacy-selected; Lineage stays the eligibility authority |
| `PROVIDER_FAILED` | 502 | The provider raised. No traceback is returned |
| `PROPOSAL_OUTPUT_UNPARSEABLE` | 422 | **architect:** not one JSON object after legacy fence stripping. **extract:** `BlueprintExtractionError` from the extractor's parser |
| `PROPOSAL_OUTPUT_INVALID` | 422 | **architect:** after legacy parsing, a missing or blank title or thesis, sections that are not a list of objects, or no section with a claim. **extract:** a blank title or thesis |
| `BLUEPRINT_REFERENCE_INVALID` | 422 | As `governed` (v1 §4), itemized |

`legacy`, `governed` and `disabled` keep their v1 behavior, status codes and
bodies.

## 4. Candidates

Both new schemas use P8's candidate frame:
- `schema`, `mode` (`"create"` only), `binding`, `extraction`, `proposal`,
  `candidate_id`;
- `candidate_id` = `blueprint-proposal-candidate:sha256:<hex>` over
  `<schema>\0 ‖ C(candidate without candidate_id)`. For the P8 schema this
  domain is byte-identical to P8's existing domain, so P8 IDs are unchanged.

This keeps every P8 seam that reads candidates working unchanged:
- **stale checks** read `binding.basis.observations` and `.interpretations`,
  `binding.governing_question` and `binding.predecessor`;
- **Lineage receipt eligibility** reads `binding.basis` and `result`.

Basis entries use P8's exact digest conventions:
- an Observation entry is `{label, id, sha256}`, where the digest covers
  `{id, source_document_id, source_extraction_id, page, paragraph, sentence,
  raw_text}`;
- an Interpretation entry is `{label, id, sha256, authorship}`, where the
  digest covers the whole Lineage `record_data` and `authorship` is the
  Lineage label.

Both are computed from one Lineage projection at generation. Neither legacy
prompt uses the governing question, so `governing_question` is
`{status: "absent", text: null, sha256: null}`.

### `hermeneia.legacy-architect-candidate/v1` (`architect/generate`)

| Field | Content |
| --- | --- |
| `binding.directive` | the exact stripped directive used in the prompt, with its SHA-256 (complete input) |
| `binding.basis` | `policy_version` `legacy-architect-basis/v1`. Observations: every sampled Observation shown, labelled `OBS-<n>`. Interpretations: every Interpretation shown, labelled `INTERP-<first 8 of id>` |
| `binding.view` | the exact prompt view: for each shown Observation, `label`, `id`, `page`, `role_note` and `text` (the first 200 characters); for each shown Interpretation, `label`, `id`, `observation_label`, `evidential_status`, `role_note` and `text`; and `observations_total`. `role_note` and the positional numbers are snapshots of state at generation |
| `extraction` | `policy_version` `1.0.0`, `prompt_version` `legacy-architect/v1`, the exact prompt and its digest, `execution` (the adapter's `execution_config()` after the call, plus `provider_id` and `adapter`), `created_at`, `completed_at`, and the raw output and its digest |
| `proposal` | `{blueprint: {title, thesis, sections: [{claim, supporting_observations, supporting_interpretations}]}, model_explanation: null}`. References are resolved exactly to shown records |

### `hermeneia.legacy-extract-candidate/v1` (`extract-blueprint` preview)

| Field | Content |
| --- | --- |
| `binding.source_text` | the exact text submitted, with its SHA-256 (complete input), and `max_input_chars` (40000) |
| `binding.basis` | `policy_version` `legacy-extract-basis/v1`, with empty `observations` and `interpretations`. The extractor sees no workspace evidence |
| `extraction` | `policy_version` `1.0.0` and `prompt_version` `legacy-extract/v1`; the exact `system_prompt` and user `prompt`, each with its digest. `execution` holds the request the extractor actually sent: `provider_id`, `interface`, `model_id`, `max_tokens`, `adapter`, and the adapter's `execution_config()` when present. It also holds `created_at`, `completed_at`, and the raw output and its digest |
| `proposal` | the extractor's parsed Blueprint (sections with empty support), `model_explanation: null` |

The prompt sent and the parsing are exactly the extractor's existing ones;
they are factored out, not changed.

### Holding

Candidates go into P8's server-held candidate store, which is bounded to 100
and evicted oldest first. Restart or eviction means regenerate.

## 5. Changes to the P8 receipt module

The receipt schema, table, triggers, origins, sources, meaning and routes are
unchanged. Three functions change:

- **`candidate_id`:** the domain prefix is the candidate's own schema; P8's
  bytes are identical.
- **`validate_receipt`:**
  - a P8 candidate keeps its existing checks;
  - a candidate of a §4 schema is validated by
    `hermeneia/legacy_blueprint_candidates.py` (shape, versions, digests,
    view-to-basis label and ID agreement);
  - any other schema is invalid.
- **`verify_receipt` `candidate_replay`:** P8 candidates keep P8 replay.
  Legacy candidates:
  1. re-check every bound record's digest against its immutable row;
  2. re-check each view's text fields against those rows;
  3. rebuild the prompt (or, for extract, the system and user request) from
     the bound inputs;
  4. re-parse the raw output to the same proposal.

  The model is never called again.

**Compatibility.** Code without this amendment (current `main`) rejects a
legacy-origin receipt as invalid. Lineage then omits it with a diagnostic,
and its Blueprint projects as `unknown`. It is never misattributed.

**Portability.** It is the same table, so the P8 portability declaration (WBS
`unsupported`) covers these receipts until #252.

## 6. Provenance outcome

An accepted legacy candidate commits through the existing atomic P8
acceptance:
- the Blueprint is labelled `proposal-accepted` or `proposal-edited`;
- its ArchitectPlan is compiled;
- one receipt is written;
- a Lineage check runs;
- all of it commits together or not at all.

Lineage authorship comes **only** from the receipt: `accepted_model` for
exact acceptance, `human` for an edit. Every CI-011 field is in the receipt:

| CI-011 field | Where it is recorded |
| --- | --- |
| complete input | directive or source text, and the prompt |
| direct parent identities | basis IDs and digests |
| provider and model identity, configuration | `execution` |
| prompt or request payload | `prompt`, plus `system_prompt` for extract |
| execution timestamps | `created_at`, `completed_at` |
| provider execution metadata | `execution` |
| raw output | `output` |
| resulting canonical object identity | `result.resulting_blueprint_id` and `plan_id` |
| complete provenance | the candidate, acceptance and Lineage |

A discarded or expired candidate persists nothing. That is P8's reading of
CI-011: the record is persisted when output becomes canonical.

**Competence.** A receipt proves provenance and the exact steward decision.
It does **not** establish that the legacy generators produce good or
supported Blueprints. Neither legacy generator has been evaluated for
competence, and P8's GENERATION_NOT_READY finding is not addressed.

## 7. Witness matrix after this amendment

| Risk | `legacy` | `governed` | `proposal` | `disabled` |
| --- | --- | --- | --- | --- |
| R1 unresolved loss | exposed | repaired | repaired | repaired |
| R2a wrong-type binding | exposed | repaired | repaired | repaired |
| R2b unshown binding | exposed | repaired | repaired | repaired |
| R3 non-atomic | repaired | repaired | repaired (generate writes nothing; acceptance is atomic) | repaired |
| R4 model-direct write | exposed | exposed | **repaired** | repaired |
| R5 unreviewed resample | exposed at the route | repaired | **repaired** (save refused; acceptance commits the exact previewed candidate) | repaired |
| R6 placeholder commit | exposed but labelled | repaired | repaired | repaired |

In `proposal` the witnesses assert the governed outcome: no canonical row,
plus a held candidate where generation succeeds.

## 8. Reader compatibility (USER-FACING; not enabled)

- **The current Reader is not compatible with `proposal`.**
  - On any 2xx from `architect/generate`, "Generate Blueprint →" shows
    `✓ Blueprint created: "<title>"`. A held candidate would therefore be
    misreported as a creation.
  - The onboarding "Ratify & Save" posts `save: true`, which is refused.
- `proposal` must **not** be enabled before a Reader change shows each
  candidate and calls the P8 accept and discard routes. Any such change is
  delivered as an isolated, unapplied patch for owner review. The owner's
  uncommitted `index.html` and navigation-test edits stay untouched.

## 9. Non-goals

- no default change;
- no enabling of P8 generation;
- no competence claim;
- no change to `legacy`, `governed` or `disabled`;
- no change to `ratify-blueprint`, `revise-blueprint` or `architect/import`;
- no rewrite or relabelling of existing rows;
- no new table;
- no WBS change (that is #252);
- no live model;
- no real workspace.

## 10. Acceptance for this amendment

- The legacy prompt is byte-identical before and after factoring, against a
  golden prompt captured from `d38fdbc`.
- The witness matrix (§7) holds in all four modes; v1's markers are
  unchanged.
- **`proposal` tests:**
  - generation writes nothing;
  - exact accept, edit-and-accept, discard and stale refusal through the
    unchanged P8 routes;
  - the receipt verifies (`record_integrity`, `candidate_replay` and
    `result_closure` are `valid` or `verified`);
  - Lineage authorship is `accepted_model` or `human`;
  - every CI-011 field is present;
  - there is no client substitution;
  - provider and network tripwires hold.
- **P8 is unchanged:** its tests pass, and its governance, live-ceiling and
  live phi4-mini datasets reproduce byte for byte.
- The full suite is clean except the inherited Reader baseline.
- The owner's Reader files are byte-identical before and after.
