# ADR-0046: An Absent Provenance Record Is Not a Transformation

**Status:** PROPOSED
**Version:** 0.1
**Date:** 2026-10-15
**Supersedes:** ADR-0042 in part, IF RATIFIED. Only the Provenance EF's
missing-provenance branch and its stated meaning are in scope.
**Relies on:** ADR-0041:
- §3 and Amendment I (identity);
- §5 (vocabulary);
- Amendment II (evidence);
- Amendment III (completeness).

**Related:**
- CI-015;
- [#257](https://github.com/JosephJMWalker-MBA/Hermeneia/pull/257) (WBS
  provenance repair) and its 2026-10-15 real-study verification;
- the G2 validation on #255.

**Constitutional cost of error:** Medium. It changes one disposition of one
ratified Evaluation Function. It changes no Finding schema, identity rule or
historical Finding.

Nothing in this ADR is implemented. The evaluator, the Finding store and every
historical Finding are unchanged until the Primary Human Steward ratifies it.
Evidence: `tests/test_adr0042_provenance_absence.py`.

---

## Context

**What ADR-0042 says.** Its Provenance EF classifies an Observation that
exists without a provenance record as `operation=transformation`,
`status=transformed`, "a degraded state".

**Why that contradicts ADR-0041.** ADR-0041 §5 defines:
- `transformation`: "transmits a changed version of the obligation";
- `transformed`: "present but materially altered".

ADR-0042 itself says what absence means: "If provenance is missing, it cannot
be independently witnessed." That is an inability to verify, not evidence of
alteration.

**Real study, 2026-10-15.** The evidence is preserved in #257's verification
and was not accessed again for this proposal.
- **Default bundle.** Restoring `study-d88c4a642956` gave all 2,369
  obligations `preserved`, identical to the source.
- **Earlier-exporter bundle.** It carries the same hash-verified Observations
  but no compile records. Restoring it gave **2,369 `transformed`**. The
  evidence was unchanged; only the custody record was missing.

**Synthetic study.** The same state is reached through the product's own
routes:
- the Source Documents, Extractions and Observations are row-identical;
- the provenance record is absent;
- `provenance-v1.0` reports every cited Observation `transformed`;
- it uses **the same Finding IDs** that report `preserved` in the source.

### The four observable states

Stored records alone distinguish all four states. `provenance-v1.0` does not
distinguish them correctly.

| State | Stored records | `provenance-v1.0` | Honest reading |
| --- | --- | --- | --- |
| Preserved provenance | Observation, and a provenance row whose `verbatim_text` equals `raw_text` | `preservation` / `preserved` | preserved |
| **Missing provenance** | Observation, no provenance row | **`transformation` / `transformed`** | custody unverifiable; the evidence is unaltered |
| **Demonstrated alteration** | Observation, and a provenance row that disagrees with it (`verbatim_text` ≠ `raw_text`) | **`preservation` / `preserved`** | altered custody record |
| Missing Observation | no Observation | `omission` / `omitted` | omitted |

**Two consequences, proved by the truth-table test:**
- In `provenance-v1.0`, absence is the **only** path to `transformed`. A
  demonstrated alteration is classified `preserved`, because the EF checks
  existence, not agreement.
- Every historical `provenance-v1.0` `transformed` Finding is therefore
  **exactly** recognizable from its own evidence:
  `observed_render = {"observation_exists": true, "provenance_exists": false}`.

Today, only the narrative trust summary detects alteration: its
`provenance_failures` compares `verbatim_text` with `raw_text`.

---

## Decision (proposed)

### D-1. Absence is recorded as `not_evaluated`, with the absence in evidence

In the Provenance EF, an Observation that exists without a provenance record
yields:

```text
operation = not_evaluated
status    = not_evaluated
evidence.observed_render = {"observation_exists": true, "provenance_exists": false}   (unchanged)
evaluation_method = "provenance-v1.1"
```

**Every other branch, the obligation identity, the Finding identity formula and
the completeness invariant are unchanged.** Every obligation still has exactly
one Finding.

**Interpretation clause.** In the provenance dimension, an obligation whose
custody record is absent cannot be authoritatively evaluated. ADR-0041's
`not_evaluated` ("No authoritative evaluation exists") is the disposition. The
absence is a machine observation; per Amendment II it belongs in `evidence`,
not in the disposition.

### D-2. Historical Findings are not reclassified

- Every existing Finding keeps its ID, operation, status and evidence.
- No Finding is superseded, rewritten or deleted. The storage triggers refuse
  update and delete in any case.
- Steward decisions stay bound to the Findings they decided.

Projections **may** describe a `provenance-v1.0` `transformed` Finding whose
evidence records `provenance_exists: false` as:

> provenance record absent; recorded as transformed by provenance-v1.0

This is presentation only. It is exact, by the truth table above.

### D-3. A divergent re-evaluation fails closed

**The problem.** Finding identity names the evaluated obligation, not its
result or the method that produced it (ADR-0041 Amendment I). `provenance-v1.1`
will therefore compute IDs that `provenance-v1.0` Findings already hold.
`insert_findings_batch` uses `INSERT OR IGNORE`, so the new result would be
discarded silently and the run would still appear to succeed.

**The rule.** If a computed Finding's ID already exists with a different
`operation`, `status` or `evidence`, the Finding is **not** written and the run
reports the divergence. Differences only in `evaluation_method`,
`constitution_version` or `created_at` are not divergence. Identical
re-evaluation stays idempotent; the Critic route relies on that to complete a
partial ledger.

### Out of scope (recorded, not decided)

- **Alteration detection** (`verbatim_text` ≠ `raw_text`). Detecting a
  demonstrated alteration in the Provenance EF would be a new check. It needs
  its own decision. Until then, only the trust summary detects it.
- **The Blueprint-link check.** ADR-0042's method also requires
  `blueprint_observation_links`, but `provenance-v1.0` does not query it. This
  is a specification/code divergence.
- **The `semantic` EF.** It is not in `RATIFIED_DIMENSIONS`, yet the runner
  executes it and its Findings are persisted. It also uses `transformed` for a
  thin evidential trace.
- **Article VI** says generation shall fail when required provenance cannot be
  established. Whether this applies to provenance-less Observations is
  unexamined.

---

## Alternatives considered

Each alternative is applied to the 2,369 real-study obligations restored from
an earlier-exporter bundle.

| | Remedy | Real study | Ontology or schema change | Decision |
| --- | --- | --- | --- | --- |
| A | Keep `transformation` / `transformed` | 2,369 claimed alterations of unaltered evidence | none | **rejected**: contradicts ADR-0041 §5 |
| **B** | **`not_evaluated` / `not_evaluated`; the absence stays in evidence (D-1)** | 2,369 `not_evaluated`, with the reason recorded in each Finding | **none** | **proposed** |
| C | New explicit status and operation (for example `unverifiable`) | 2,369 under the new status | ADR-0041 §5 vocabulary; table rebuild | fallback (see below) |
| D | Put the method version into Finding identity, then supersede v1.0 Findings | 2,369 new Findings and supersession relations | ADR-0041 Amendment I, for **every** dimension | not now |
| E | `omission` / `omitted` | 2,369 claimed absences of Observations that exist | none | **rejected**: false |
| F | Projection relabelling only | the stored Findings still assert alteration | none | insufficient alone; adopted for history (D-2) |

### Why not a new status (C)?

`finding.spec.md` allows provenance-specific vocabulary when a domain ratifies
it, so C is lawful. Its costs were measured:
1. **ADR-0041 §5 must be amended.** That changes Finding ontology, which
   ADR-0042 explicitly did not authorize ("Any modification to Finding
   schema").
2. **The `findings` CHECK vocabulary must change.** SQLite cannot alter a CHECK
   constraint, so the canonical, trigger-guarded Finding table would have to be
   rebuilt in every workspace. That is a copy of immutable history.
3. **Un-migrated workspaces lose Findings silently.** Tested: the CHECK
   constraint refuses an unknown status, but `INSERT OR IGNORE` also ignores
   CHECK violations. The new Findings would therefore be **dropped without
   error**. That breaks completeness silently, which is the worst failure for a
   ledger.
4. **Projections need changes.** From code reading:
   - `trust_card` counts statuses in a dictionary with fixed keys, so an unknown
     status raises `KeyError`;
   - the audit dashboard's `STATUS_STATES` enumerates the five statuses.

Choose C instead of B only if the Steward judges that ADR-0041's
`not_evaluated` operation ("not evaluated in this invocation") cannot bear the
meaning "evaluated, but no custody record exists to evaluate".

### Is `not_evaluated` honest?

| Test | Result |
| --- | --- |
| Status meaning: "No authoritative evaluation exists" | **holds**: absence of the custody record leaves custody unevaluable |
| Operation meaning: "not evaluated in this invocation" | **stretched**: the function ran and observed the absence. The interpretation clause in D-1 closes this explicitly |
| `not_evaluated` "is not a success state" | holds: no false pass |
| Information loss | none: `observed_render` keeps both booleans, so projections can tell "no custody record" apart from any other `not_evaluated` |
| Precedent | the `semantic` EF already maps an absent evidential chain to `not_evaluated`. It is weak precedent, because that dimension is not ratified |

---

## Compatibility analysis

| Surface | Effect of B (D-1 to D-3) |
| --- | --- |
| Finding schema and CHECK vocabulary | unchanged |
| Finding and obligation identity | unchanged formula. `provenance-v1.0` and `-v1.1` Findings for the same obligation share an ID. Within a workspace, the stored Finding stands and D-3 makes any divergence visible |
| Historical Findings and steward decisions | unchanged (D-2) |
| Completeness invariant | unchanged: one Finding per obligation, tested |
| Trust card | the provenance verdict is the same, `partial`, for all-`transformed` and all-`not_evaluated`. Tested |
| Audit dashboard, Reader fidelity view | already render `not_evaluated`. Counts move from `transformed` to `not_evaluated` |
| WBS | No WBS exporter writes Findings; #255 declares them not carried. There is no cross-workspace collision today. Any future Findings-portability component **must refuse** a bundle whose Finding ID exists in the target with different content: fail closed, as for R1 |
| Older code over a newer workspace | `not_evaluated` is in the old vocabulary and renders. Older code has no D-3 guard: its `transformed` re-evaluation would be discarded silently in favor of the stored `not_evaluated`. That is the same silent path D-3 closes going forward |
| R1 | unaffected. New bundles still refuse restoration by older restorers |
| CI-015, Article I | no evidence is touched; no historical Finding is touched |

**Tests that change when this is implemented:**
- **This file:**
  - the two strict witnesses must show `XPASS(strict)` before their markers are
    removed (both were mutation-checked);
  - the `provenance-v1.0` characterization tests are updated to `v1.1`.
- **#257, if merged first.** `test_wbs_compile_records` asserts `transformed`
  for component-less restores. Its comment cites ADR-0042 as unchanged. It takes
  the ratified disposition.
- **The gap.** `test_era2_sprint_e3` has no test of the missing-provenance
  branch. The truth-table test here covers it.

---

## Recommended migration strategy

1. **Ratify D-1, D-2 and D-3**, or C in place of D-1.
2. **Implement as one bounded packet:**
   - the `provenance-v1.1` branch;
   - the D-3 divergence guard at the Finding-store boundary (the Critic route
     and the CLI both persist through `insert_findings_batch`);
   - the D-2 projection wording.
3. **No data migration, backfill or forced re-evaluation.** Historical
   Findings stay as recorded and are described exactly by D-2.
4. **Re-running the Critic** on a narrative that holds a `provenance-v1.0`
   `transformed` Finding for an absent record is refused under D-3. The Steward
   sees the stored Finding and the divergence. Recording the new disposition
   under a new identity would be Alternative D, a separate decision.
5. **Convert the witnesses** only after `XPASS(strict)`.
6. **Authority Index.** On ratification, add this row to the Supersession
   Register:

   | Earlier authority | Status | Successor | Superseded scope | Reason |
   | --- | --- | --- | --- | --- |
   | ADR-0042 | SUPERSEDED IN PART | ADR-0046 | Provenance EF: the missing-provenance disposition and its stated meaning | An absent custody record makes custody unevaluable; it does not show material alteration (ADR-0041 §5) |

---

## Smallest defensible decision

**D-1 with D-2** corrects the false claim within the existing ontology:
- no new status;
- no schema change;
- no change to the Finding identity formula;
- no historical Finding touched.

**D-3** is the guard that keeps the change from being lost silently under
unchanged IDs. Without it, workspaces that already hold `provenance-v1.0`
Findings would go on showing `transformed`, and nothing would say why.
