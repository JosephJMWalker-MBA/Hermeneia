# ADR-0046: An Absent Provenance Record Is Not a Transformation

**Status:** PROPOSED
**Version:** 0.2
**Date:** 2026-10-16
**Supersedes:** ADR-0042 in part, IF RATIFIED. Only the Provenance EF's
missing-provenance disposition and its stated meaning are in scope.
**Relies on:**
- ADR-0041 §5 and its extension clause ("other dimensions may ratify additional
  operations via future ADR");
- ADR-0041 Amendments I to III;
- `finding.spec.md` §5 ("Provenance … may require other operations or
  statuses").

**Related:** [#257](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/257)
(real-study evidence).
**Constitutional cost of error:** Medium.

**Steward review, 2026-10-16:**
- v0.1 D-1 **revise**: compare an explicit `unverifiable` with an amended
  `not_evaluated`;
- D-2 **principle accepted**: presentation must name the evaluator version and
  what its evidence established;
- D-3 **principle accepted**: strengthen it.

**Nothing in this ADR is implemented.** The evaluator, the Finding store, the
schema, every historical Finding, ADR-0041, ADR-0042 and the Authority Index
are unchanged.

**Evidence:**
- `tests/test_adr0042_provenance_absence.py`: 13 pinned facts and 6 strict
  witnesses;
- `tests/test_adr0046_unverifiable_rehearsal.py`: 5 measurements of the
  option-U migration on test databases.

---

## Context

**ADR-0042's rule.** It classifies an Observation that exists without a
provenance record as `transformation` / `transformed`.

**ADR-0041 §5's definitions.** `transformed` means "present but materially
altered", and `transformation` "transmits a changed version". ADR-0042 itself
says a missing record means the Observation "cannot be independently
witnessed".

**Real study** (#257 verification; not accessed again):
- An earlier-exporter restore gave **2,369 `transformed`** for 2,369 unaltered
  Observations.
- A default restore gave 2,369 `preserved`.

**Synthetic study**, built through the product's own routes:
- the documents, extractions and Observations are row-identical;
- the provenance record is absent;
- `provenance-v1.0` reports `transformed` under the **same Finding IDs** that
  report `preserved` in the source.

### The four observable states

| State | Stored records | `provenance-v1.0` records |
| --- | --- | --- |
| Preserved provenance | Observation, and a record whose `verbatim_text` equals `raw_text` | `preservation` / `preserved` |
| **Missing provenance** | Observation, no record | **`transformation` / `transformed`** |
| **Demonstrated alteration** | Observation, and a record that disagrees with it | **`preservation` / `preserved`** |
| Missing Observation | no Observation | `omission` / `omitted` |

Absence is the only path to `transformed`, and `provenance-v1.0` never compares
the record with the Observation. Both are tested.

---

## D-1 (revised): the disposition for an absent custody record

### The two candidates

**U: an explicit `unverifiable`, scoped to the provenance dimension.**

| Value | Meaning |
| --- | --- |
| operation `unverifiable` | The function examined the obligation and found that the record required to verify it is absent |
| status `unverifiable` | The evidence exists but cannot be verified; neither preservation nor alteration is established |

- **Ratified meanings:** none change. U is added under ADR-0041 §5's own
  extension clause.
- **Scope:** the provenance dimension only. Other dimensions need their own
  ratification. The D-3 guard enforces the scope.

**N: amend the ratified meaning of `not_evaluated`.**
- The operation's meaning changes from "not evaluated in this invocation" to
  "no authoritative disposition was reached; evidence records why".
- This supersedes ADR-0041 §5 in part, for a token that every dimension
  shares.
- **N′**, a fallback, scopes the amendment to the provenance dimension.

### Comparison (measured where marked)

| Criterion | U: `unverifiable` | N / N′: amended `not_evaluated` |
| --- | --- | --- |
| Operation meaning honest | yes, by definition | only by redefinition; the check did run |
| Status meaning honest | yes | yes ("No authoritative evaluation exists") |
| Vocabulary | one token, one state | one token, two senses; only `evidence` tells them apart |
| Ratified meanings changed | **none** (additive) | ADR-0041 §5 `not_evaluated`: every dimension under N, provenance under N′ |
| Effect on existing Findings | none | **measured:** today the only producer of `not_evaluated` is the **unratified** `semantic` dimension, which already uses it in the "basis absent" sense. N would retroactively legitimize that use before the Steward decides on `semantic`. N′ avoids this |
| Presentation | `unverifiable` is shown as such | every surface says "Not evaluated" for a check that ran, unless projections read the evidence |
| Schema | `findings` CHECK vocabulary, which can only change by **rebuilding the table** | none |
| Migration (**rehearsed**) | a one-time rebuild per workspace in one transaction, with foreign keys off. Every Finding row is identical; all other schema objects are identical; integrity and foreign keys check clean; immutability and supersession guards still enforce; steward decisions and supersession relations still join. It **requires legacy rename mode**: without it, SQLite rejects the rename because the supersession guards name `findings`, and the transaction rolls back whole | none |
| Projections (**measured**) | `trust_card` and `audit_dashboard` raise `KeyError` on `unverifiable` and must learn the value. The Reader's Critic views follow | wording only. The trust card verdict is unchanged (`partial`) |
| Older builds on a migrated workspace (**measured**) | their projections fail. Their store silently **rewrites the schema marker down** to their own version and does not refuse | unaffected |
| A store that is not migrated (**measured**) | `INSERT OR IGNORE` drops the new value silently. Under D-3 it is refused instead | n/a |

### Recommendation: U, scoped to the provenance dimension

U is the smallest **constitutionally honest** alternative:
- it changes no ratified meaning;
- it states exactly what the evidence established;
- it settles nothing about other dimensions.

Its costs are mechanical, and the rehearsal measured them. N is smaller only
in schema. Its honesty depends on redefining a ratified cross-dimension term
and on every projection reading evidence. N would also settle the `semantic`
question by implication.

U requires these preconditions, in order:
1. **P1: D-3 lands first.** A build that cannot store `unverifiable` must refuse
   it, not drop it.
2. **P2: a newer-schema refusal.** `SQLiteStore` refuses a workspace whose
   schema version exceeds its own. It should ship at least one release before
   the migration.
   - **Separate authorization.** This changes startup behavior for every
     workspace, so P2 needs its own decision.
   - **Residual risk.** Builds that predate P2 would still open a migrated
     workspace: they would downgrade its version marker and fail in
     projections. They lose no Findings, because the rows and triggers are
     intact.
3. **P3: projections learn `unverifiable`.**
   - **Trust card rule.** `unverifiable` is not success. As with `transformed`
     today, a dimension is `pass` only when every Finding is preserved.
   - **Reader views.** They render the value. Changes to the Reader's
     `index.html` must be coordinated with the owner's uncommitted edits there.
4. **P4: scope is enforced at the write guard.** The rebuilt CHECK admits the
   token for every dimension (rehearsed), so the D-3 guard holds the
   per-dimension vocabulary.

**If the Steward declines a schema migration now,** N′ is the only honest
fallback, provided that:
- it is scoped to the provenance dimension;
- every projection presents an `evidence.provenance_exists = false` Finding as
  "custody record absent", not "Not evaluated".

**Choose once.** Adopting N′ and later U would leave three historical senses
for one state.

---

## D-2 (principle accepted): historical presentation

- **No Finding is rewritten, reclassified, superseded or deleted.** Steward
  decisions stay bound to the Finding as recorded. Tested: an update and a
  delete are refused, and a decision still joins its `transformed` Finding.
- **Every presentation of a Finding names its `evaluation_method`** and states
  what its evidence **established** and what it **did not establish**.
  - The reading is a pure function of the Finding's own `evaluation_method`,
    `operation`, `status` and `evidence`; it needs no live lookup.
  - The disposition is attributed, not restated: "recorded as transformed by
    provenance-v1.0".
- **Mixed ledgers** show each Finding's method. No aggregate may hide that a
  narrative's Findings come from different evaluator versions.

**The `provenance-v1.0` readings.** They are total over all four combinations
of `observed_render`. Tested exact and unambiguous.

| Recorded | Evidence | Established | Not established |
| --- | --- | --- | --- |
| `preservation` / `preserved` | Observation ✓, record ✓ | the Observation existed; a provenance record existed | that the record agrees with the Observation; that the Observation is linked to the plan's Blueprint |
| `transformation` / `transformed` | Observation ✓, record ✗ | the Observation existed; no provenance record existed | **any alteration**; the Observation's custody |
| `omission` / `omitted` | Observation ✗ (record ✗ or ✓) | no Observation with this ID existed (and whether a record did) | — |

The `preserved` row matters too. A v1.0 "preserved" Finding never compared
the record with the Observation. The demonstrated-alteration state reads
exactly like the preserved one, which is tested.

---

## D-3 (principle accepted, strengthened): the ledger write guard

The guard sits at the **single Finding persistence boundary**,
`SQLiteStore.insert_findings_batch`, which both the Critic route and the CLI
use. It classifies every computed Finding.

| Class | Condition | Outcome |
| --- | --- | --- |
| Identical retry | ID stored; `operation`, `status`, `evidence`, `evaluation_method` and `constitution_version` all equal | nothing written; counted `identical`; **success** (idempotent) |
| **Retained older evaluator version** | ID stored; `operation`, `status` and `evidence` equal; `evaluation_method` or `constitution_version` differs | nothing written; the stored Finding stands; **reported** as `retained` with both methods; success |
| **Divergent result** | ID stored; `operation`, `status` or `evidence` differs | **refused** |
| **Unsupported value** | the operation, status or their pair is not ratified for the dimension | **refused** |
| **Failed insertion** | a write did not produce exactly the computed row, for any reason: constraint, trigger or driver | **refused** |

- **All or nothing.** A refusal writes nothing, together with the Critic report
  in the same transaction. It names the class and the IDs. `created_at` is
  never compared.
- **Return contract:** `{inserted, identical, retained}`. Each `retained` entry
  carries `id`, `stored_method` and `computed_method`.
- **Feasible without any schema change.** A reference guard (applied
  temporarily, not committed) made all five D-3 witnesses show
  `XPASS(strict)`. Under it, the Critic route's idempotency test and the E1–E5
  Evaluation Function suites passed: 107 passed. The only failures were the
  five "today" characterizations, as expected.
- **Dependency.** Checking the dimension against `RATIFIED_DIMENSIONS` would
  refuse the `semantic` dimension's Findings. They are persisted today,
  although the dimension is unratified (see the separate investigation). That
  check must be enabled together with the Steward's `semantic` decision. Until
  then, the guard checks operation, status and pair only, as the reference
  guard did.

| Witness (strict xfail) | Class |
| --- | --- |
| `ProvenanceAbsenceReadAsAlteration` | D-1 (XPASS under U or N; mutation-checked) |
| `DivergentReevaluationDiscarded` | divergent, including writing nothing beside it |
| `UnsupportedValueAccepted` ×2 | unknown status (dropped today); unratified pair (stored today) |
| `FailedInsertionUnreported` | NOT NULL violation (dropped today) |
| `RetainedOlderVersionUnreported` | retained older version |

`test_an_identical_reevaluation_is_idempotent` must keep passing.

---

## Alternatives considered

| | Remedy | Decision |
| --- | --- | --- |
| A | Keep `transformation` / `transformed` | rejected: contradicts ADR-0041 §5 |
| **U** | **`unverifiable`, provenance-scoped** | **recommended** |
| N | Amend `not_evaluated` for every dimension | rejected: cross-dimension and retroactive; blesses the unratified `semantic` use |
| N′ | Amend `not_evaluated` for provenance only | fallback, if no schema migration now |
| D | Method-versioned Finding identity, plus supersession | not now: changes ADR-0041 Amendment I for every dimension |
| E | `omission` / `omitted` | rejected: the Observation exists |
| F | Relabel in projections only | insufficient: new Findings would still assert alteration. Kept for history (D-2) |

---

## Compatibility analysis (U with D-2 and D-3)

| Surface | Effect |
| --- | --- |
| Finding and obligation identity | unchanged formula. v1.0 and v1.1 Findings for an obligation share an ID. The stored one stands; D-3 refuses divergence and reports retention |
| Historical Findings, steward decisions, supersession relations | unchanged; the rehearsal preserves every row and relation |
| Completeness invariant | unchanged: one Finding per obligation |
| Schema | `findings` CHECK only, by a rehearsed rebuild; schema version 21 → 22 |
| Projections and Reader | must learn `unverifiable` (P3). Today they raise `KeyError` |
| Older builds | they open a migrated workspace without refusing, downgrade the marker and fail in projections. P2 closes this for later builds |
| WBS | no exporter writes Findings; #255 declares them not carried. Any future Findings component must refuse an ID collision with different content (fail closed, as for R1) |
| R1 | unaffected |
| CI-015, Article I | no evidence and no historical Finding is touched |

**Tests that change on implementation:**
- **This branch:** each witness must show `XPASS(strict)` before its marker is
  removed. The "today" characterizations become regressions of the new
  behavior.
- **#257, if merged first:** `test_wbs_compile_records` asserts `transformed`
  for component-less restores, and takes the ratified disposition.
- **The runner suite:** `test_evaluation_runner` pins `semantic` as a
  registered dimension, which bears on the `semantic` decision.

---

## Recommended migration strategy

1. **Ratify** U, D-2 and D-3. Authorize P2 separately.
2. **Release A** needs no schema change:
   - the D-3 guard (operation, status and pair, divergence, read-back,
     retained report);
   - P2;
   - D-2 presentation.

   Witnesses W2 to W5 convert.
3. **Release B:**
   - the schema-22 rebuild, using the rehearsed procedure: one transaction,
     foreign keys off, legacy rename, `foreign_key_check`, a row-identity
     assertion before commit, rollback on any failure;
   - `provenance-v1.1` emitting `unverifiable`;
   - the projection and Reader updates (P3);
   - the guard admitting `unverifiable` for provenance only (P4).

   W1 converts.
4. **No backfill, re-evaluation or historical rewrite.** Re-running the Critic
   over a v1.0 `transformed` Finding is refused as divergent and reported.
5. **Authority Index, on ratification:**
   - ADR-0042 becomes SUPERSEDED IN PART by ADR-0046, for the missing-record
     disposition.
   - ADR-0041 is **not** superseded under U, which is additive under §5. Under
     N′ it would be superseded in part, for the provenance dimension.

---

## Smallest defensible decision

**Ratify U (`unverifiable`, provenance-scoped), D-2 and D-3, with P2 authorized
separately.**
- It uses ADR-0041's existing extension clause, so no ratified meaning
  changes.
- Finding identity semantics are unchanged.
- No historical Finding is touched.
- The one schema change is a rehearsed, row-preserving rebuild, guarded by D-3
  and preceded by P2.

**D-3 is independent of the D-1 choice**, needs no schema change, and can land
first.
