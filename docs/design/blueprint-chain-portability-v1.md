# P10 — Blueprint dependency chain portability v1 (contract, #252)

**Status:** frozen 2026-10-13, before implementation, on branch
`p10-blueprint-chain-portability` from `main` `09b72cc`. Scope and acceptance
criteria are #252's, frozen by the owner on 2026-10-10. This contract adds
no scope.

> Local durability is not portable recoverability. This packet makes the
> Blueprint dependency chain travel through WBS with its closure intact, or
> declares it unsupported. It never fabricates, relabels, repairs or
> cherry-picks.

## 1. Inventory: what WBS 1.x actually covers today (observed at `09b72cc`)

| Runtime table | Exported today | Spec §6 says | Restore coverage today |
| --- | --- | --- | --- |
| `interpretations` | **no** | `reports/interpretations.json` | not reported |
| `proposed_interpretations` | **no** | `reports/interpretations.json` | not reported |
| `ai_provenance` | **no** | — | not reported |
| `narrative_blueprints` and both link tables | **no** | — (§6.2: declared not exported) | not reported |
| `architect_plans`, `architect_plan_paragraphs` | **no** | — (§6.2) | not reported |
| Blueprint `supersession_relations` | **no** (only Perspective edges are exported) | — (§6.2) | not reported |
| `blueprint_proposal_acceptances` | **no** | — (§6.2) | `unsupported`, with reason |
| `observation_reviews`, `inquiry_notes` | **no** | `study/reviews.json` | not reported |
| `rendered_narratives`, `critic_reports` | **no** | `reports/*` | not reported |
| `steward_decisions`, `findings`, `ratification_records` | **no** | `reports/governance.json` | not reported |

The last three rows are **pre-existing spec discrepancies outside #252's
frozen scope**. This packet corrects the spec text to state that they are
not implemented. It does not implement or declare them, which stays future
work. Consequence: P1 capability decisions that read `inquiry_notes`
(`preserve_question`) do not survive WBS today. The §9 equivalence check is
therefore evaluated on studies without inquiry notes, and the limitation is
reported, not hidden.

Every chain table exists in a fresh schema-21 store, and each has triggers
that refuse UPDATE and DELETE. Product code writes only two kinds of
supersession edge: Perspective→Perspective (storage) and Blueprint→Blueprint
(revision). The generic edge insert has no product caller.

## 2. Component — capability `blueprint-dependency-chain-v1`

The chain is **one all-or-nothing component**: either every file below is
present with intact closure, or none is and the chain is declared
unsupported. There are no per-table partial chains and no cherry-picked
rows. Every file has manifest role `canonical`: it is restored verbatim and
integrity-checked. The role is not authorship; Study Lineage alone projects
authorship.

| Runtime table | Bundle file | Row order |
| --- | --- | --- |
| `ai_provenance` | `reports/ai_provenance.json` | `id` |
| `proposed_interpretations` | `reports/proposed_interpretations.json` | `id` |
| `interpretations` | `reports/interpretations.json` | `id` |
| `narrative_blueprints` | `study/blueprints.json` | `id` |
| `blueprint_observation_links` | `study/blueprint_observation_links.json` | `blueprint_id, observation_id` |
| `blueprint_interpretation_links` | `study/blueprint_interpretation_links.json` | `blueprint_id, interpretation_id` |
| `architect_plans` | `study/architect_plans.json` | `id` |
| `architect_plan_paragraphs` | `study/architect_plan_paragraphs.json` | `plan_id, order_idx` |
| Blueprint→Blueprint `supersession_relations` | `study/blueprint_supersessions.json` | `old_id, new_id, reason, ratified_at` |
| `blueprint_proposal_acceptances` | `study/blueprint_proposal_acceptances.json` | `id` |

- **Rows** are exact `SELECT *` rows. Each table's columns must **equal** the
  frozen column set (the current schema-21 columns, listed in the
  implementation). Fewer columns (an unmigrated store) or more columns (an
  unknown later schema) is not silently narrowed or padded.
- **Encoding** is the existing deterministic `_dumps`: sorted keys, fixed
  indent, UTF-8, trailing newline. Rows are sorted by primary key in ASCII
  order. Identical database state therefore yields a byte-identical bundle.
- **Manifest.**
  - `required_capabilities` includes `blueprint-dependency-chain-v1`;
  - `counts` holds the row count of every chain table, with Blueprint edges
    counted as `blueprint_supersessions`;
  - the WBS version selection is unchanged.

### `reports/interpretations.json` — spec §6 correction (recorded decision)

The §6 row mapping `proposed_interpretations` and `interpretations` to one
`reports/interpretations.json` with role "machine / authored-on-adopt" cannot
be represented: a manifest entry has exactly one role. This contract keeps
the spec's path for `interpretations` and splits the proposals and their
generation provenance into their own files. All three are `canonical`, as
every recent immutable-history component is (P3, P4, P7).

This is the "correcting it through a recorded decision" option of #252
criterion 7. The owner confirms or overrides it on review.

## 3. Export: closure or declared unsupported (#252 criterion 3, "declare partial")

Export reads the chain inside the existing single read snapshot. It then
applies the checks below in order. The first failure declares the whole
chain unsupported and writes **no** chain file and **no** capability:

| Code | Condition |
| --- | --- |
| `CHAIN_SCHEMA_INCOMPLETE` | A chain table is missing, or its columns differ from the frozen set |
| `CHAIN_INTEGRITY_INVALID` | A P8 receipt fails `receipt_from_row` (canonical bytes, identity, candidate binding), or Blueprint `sections` is not a JSON list of section objects |
| `CHAIN_SUPERSESSION_OUT_OF_SCOPE` | A supersession edge touches a chain table (`narrative_blueprints`, `interpretations`, `architect_plans`, `proposed_interpretations`) but is not Blueprint→Blueprint |
| `CHAIN_CLOSURE_INCOMPLETE` | Any reference below does not resolve in the same snapshot |

References that must resolve:

| Record | References |
| --- | --- |
| Interpretation and proposed Interpretation | `observation_id`; `perspective_id` if set; `ai_provenance_id` if set; every ID in `evidence_observation_ids` |
| `ai_provenance` | `staged_object_id` is a proposed Interpretation |
| Blueprint links | both endpoints |
| Blueprint `sections` | every `supporting_observations` and `supporting_interpretations` ID |
| ArchitectPlan | its Blueprint |
| Plan paragraph | its plan |
| Blueprint edge | both Blueprints |
| P8 receipt | resulting Blueprint; its plan, with a matching `blueprint_id`; the predecessor and the exact supersession row (revise); every bound Observation and Interpretation |

The manifest then records the declaration:

```json
"declared_unsupported": {"blueprint-dependency-chain-v1": {"reason_code": "…", "reason": "…"}}
```

The rest of the workspace exports as today. This is the monotone choice:
- today the chain is silently absent;
- after this packet it is either present and closed, or explicitly declared
  absent with a reason.

Refusing the whole export instead would remove backup availability that
exists today. That alternative is recorded and was not chosen.

Excluded documents and their Observations are already exported with their
exclusion state, so exclusion never breaks closure. It round-trips as
state.

## 4. Restore

### `read_bundle` validation, before any write

| Bundle state | Result |
| --- | --- |
| Capability present | **All** ten files are required, each listed exactly once with role `canonical`, a matching SHA-256, and a path inside the bundle root |
| Each file | A JSON list of objects with exactly the frozen columns, unique primary keys and primary-key ASCII order, and a count equal to the manifest `counts` |
| P8 receipts | Each passes `receipt_from_row` |
| `declared_unsupported` present | Any chain file or capability is refused as contradictory. Otherwise coverage is `unsupported`, with the exported reason |
| Neither (WBS 1.0, 1.1 and 1.2 bundles) | Coverage is `unsupported`: "this bundle does not carry the Blueprint dependency chain; its history is unknown". The bundle restores exactly as before |

Any failure raises `RestoreError` before any write.

### `restore_workspace`

The chain is inserted inside the existing single `BEGIN IMMEDIATE`, after
Observations and Perspectives, in this order:
1. `ai_provenance`
2. `proposed_interpretations`
3. `interpretations`
4. `narrative_blueprints`
5. Blueprint links
6. `architect_plans`
7. plan paragraphs
8. Blueprint edges (endpoint triggers active)
9. P8 receipts

- **Columns:** rows are inserted with their exact columns. A target table
  that cannot store a column refuses; there is no generic column filtering.
- **Closure:** after insertion, the §3 closure function runs against the
  target. For each receipt, `verify_blueprint_proposal_acceptance` must give
  `record_integrity: valid` and `result_closure: verified`. Any failure
  rolls back everything.
- **Fresh target:** a covered chain requires a fresh, empty target even with
  `overwrite=True`, as award history does. Immutable history is never merged.
  The chain tables join the occupancy check.
- **Coverage:** `read_bundle`, `preview_restore` and `restore_workspace`
  report `coverage["blueprint_dependency_chain"] = {status,
  extant_records: {table: n}, reason}`.
  - The existing `coverage["blueprint_proposal_acceptances"]` key keeps its
    meaning and mirrors the chain status.
  - Older bundles still report it `unsupported` with P8's original reason.

## 5. History (#252 criterion 6)

- Legacy Blueprint `source` values (`ai-generated`, `extracted`,
  `steward-authored`, `proposal-accepted`, `proposal-edited`), legacy
  Interpretation sources and ADR-0009 provenance all round-trip byte for
  byte.
- No authorship, approval, plan, link or receipt is created, relabelled or
  repaired.
- Lineage recomputes authorship after restore from the same rows, so it must
  equal the source (§7).

## 6. Not changed

- P8's portability gate (`blueprint-proposal-p8-disposition.md` §1). It
  opens **only by owner decision** after this evidence (#252 criterion 9),
  and doing so would not clear P8's other release blockers.
- P8 generation stays disabled by default.
- No ontology change.
- No out-of-scope table (§1, last three rows).
- No WBS version bump.
- No change to the existing components.
- No real workspace: the private-copy validation of #252 criterion 8 needs
  separate owner authorization.

**Stacked work.** Legacy-origin receipts (#254, unmerged) are unknown to the
P8 validator on `main`. A workspace holding them therefore declares the chain
`CHAIN_INTEGRITY_INVALID` until #254 merges; after that, the same validator
covers them.

## 7. Evidence plan (#252 criteria 4, 8)

A laboratory (`tests/blueprint_chain_lab.py`) materializes synthetic studies
through production write boundaries, exports, restores into a fresh target,
and compares. The committed dataset is `research/blueprint_chain_portability/v1`.

### Lawful cases

| Case | Content |
| --- | --- |
| L1 | empty chain (tables present, zero rows) |
| L2 | steward-authored Interpretation, ratified Blueprint and plan |
| L3 | E10 model proposal, accepted (`accepted_model`), plus a rejected and a pending proposal |
| L4 | Blueprint revision (supersession) |
| L5 | P8 exact acceptance (create) |
| L6 | P8 edit-and-accept revision |
| L7 | legacy rows: `ai-generated` (legacy generate) and `extracted` (ratify) |
| L8 | a chain citing a document excluded after it was built |
| L9 | a WBS 1.x-shaped bundle (component stripped): restores, chain `unsupported` |

### Adversarial cases

| Case | Content | Expected |
| --- | --- | --- |
| A1 | tampered receipt in the source | chain declared `CHAIN_INTEGRITY_INVALID`; rest exported |
| A2 | dangling Blueprint link in the source | `CHAIN_CLOSURE_INCOMPLETE` |
| A3 | Interpretation→Blueprint supersession edge in the source | `CHAIN_SUPERSESSION_OUT_OF_SCOPE` |
| A4 | chain file edited (hash mismatch) | restore refused |
| A5 | edited and re-hashed (manifest consistent) bundle with a plan whose Blueprint was removed | restore refused at closure; target unchanged |
| A6 | capability declared, file missing | restore refused |
| A7 | file present without the capability | restore refused |
| A8 | count mismatch | restore refused |
| A9 | duplicate primary key | restore refused |
| A10 | unknown column | restore refused |
| A11 | `declared_unsupported` plus chain files | restore refused |
| A12 | covered chain into an occupied target with `overwrite=True` | restore refused |

### Checks per lawful case

1. byte-identical double export;
2. exact row equality of every chain table, source against restored,
   ordering-independent;
3. Study Lineage items over the chain tables equal: record, event,
   authorship, eligibility and context;
4. P1 capability decisions equal (studies without inquiry notes, §1);
5. `verify_blueprint_proposal_acceptance` verdicts equal, per receipt;
6. coverage declarations as specified;
7. source workspace unchanged by export (logical dump);
8. P5 isolation, no network, no provider at export or restore.

Tests are in `tests/test_blueprint_chain_portability.py`. The full suite must
be clean except the inherited Reader baseline, and existing WBS bundles and
tests must restore unchanged.

## 8. Amendment 1 (2026-10-13, found during implementation): chain export is gated

**Finding.** Exporting the chain unconditionally would make every fresh
export carry `blueprint-dependency-chain-v1`, and `preview_restore` would
then report P8 acceptance history `covered`. That contradicts two
authorities:

- `blueprint-proposal-p8-disposition.md` §1: until the portability gate
  passes, acceptance history is "explicitly declared unsupported by WBS".
- #252 criterion 9: the gate opens "only by owner decision after 1–8 pass".

It also changes P8's committed governance dataset, whose WBS case pins that
declaration. Two P8 tests failed when the export was unconditional. That is
evidence of a conflict, not of a defect in P8.

**Decision recorded here.**

- **Export is off by default.** Chain export is an explicit export option,
  `blueprint_chain=False` by default, in `build_bundle_files`,
  `build_workspace_zip` and `export_workspace_bundle`.
- **Web gate.** The app follows P8's gate pattern: `WBS_BLUEPRINT_CHAIN`,
  default `disabled`, enabled only by
  `HERMENEIA_WBS_BLUEPRINT_CHAIN=enabled`.
- **Disabled means unchanged.** The bundle is byte-identical to the
  pre-#252 exporter: no chain files, no capability, no
  `declared_unsupported`. P8's declaration and dataset are unchanged.
- **Enabled** applies §2–§3 exactly. `declared_unsupported` appears only
  when an enabled export finds a closure, integrity, scope or schema
  failure.
- **Restore** always understands the component (§4). A bundle carrying the
  chain can only come from an enabled export. Restore support alone neither
  implies nor exposes portability for default users.
- **Opening the P8 portability gate** means enabling chain export by
  default. It remains the owner's decision under criterion 9, and it does
  not clear P8's other release blockers.

## 9. Amendment 2 (2026-10-13, owner-directed coverage audit): chain portability is not study portability

**Owner decisions of 2026-10-13.**
- G1 is approved: the §2 spec correction is adopted.
- G3, opening the gate, is deferred.

**Classification.** Each of the 45 runtime tables in a fresh schema-21 store
falls into exactly one class, and a test enforces it:

| Class | Tables |
| --- | --- |
| Exported by WBS files | `source_documents`, `source_extractions`, `observations`, `reader_highlights`, `perspectives`, Perspective `supersession_relations`, `investigation_log`, `workspace_investigation` |
| Carried by capability components | Perspective execution receipts, achievement awards, accepted comparisons, the eight publication/authoring tables (when a publication is attached) |
| Blueprint chain (§2, gated) | the ten chain tables |
| System | `schema_version`, `workspace_identity` (the manifest carries the workspace ID) |
| **Not carried** (`hermeneia/workspace/coverage.py`) | listed below |

The not-carried surfaces are:

| Surface | Tables | Kind |
| --- | --- | --- |
| `study_reviews` | `observation_reviews`, `inquiry_notes` | history |
| `reports` | `rendered_narratives`, `critic_reports`, `validation_reports` | history |
| `governance` | `steward_decisions`, `findings`, `ratification_records`, `witness_sessions` | history |
| `custom_expression_profiles` | `expression_profiles` with `source` not `built-in` | history |
| `reading_progress` | `reading_progress` | state |
| `derived_indexes` | `observation_derived`, `terms`, `observation_terms`, `provenance` | derived and **not rebuilt by restore** |

**Declarations, never repairs.**
- **Export.** Every export records `manifest.not_exported`, counted from its
  read snapshot. When the chain is not exported (gate off, or declared
  unsupported), `blueprint_dependency_chain` is listed with its counts and
  reason. A missing table counts as `null` (unknown).
- **Restore.** `read_bundle`, `preview_restore` and `restore_workspace`
  report:
  - `coverage.study_portability = {status: "partial", …}`, with
    `source_counts` set to `recorded` or `unknown`;
  - `coverage.not_carried[surface]` as `unsupported`, with the source
    counts, or `"unknown"` for older bundles.

  Nothing is reconstructed, backfilled or rebuilt.
- **Reader.**
  - The export drawer says "some record types are not included yet",
    replacing "a portable .zip bundle of your work".
  - The import preview lists every not-carried surface, with its source
    count or "count unknown", and says nothing is recreated.

**Compatibility.** Adding `not_exported` changes the bytes of every default
manifest. This is deliberate: it is additive, older restorers ignore it, and
bundles stay deterministic. Default bundles otherwise carry no chain files,
capability or declaration, so P8's unsupported declaration and dataset are
unchanged.
