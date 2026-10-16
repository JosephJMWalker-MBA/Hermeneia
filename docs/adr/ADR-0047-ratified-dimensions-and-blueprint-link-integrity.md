# ADR-0047: Only Ratified Dimensions Write Findings; Blueprint-Link Integrity Is Enforced and Still Detected

**Status:** PROPOSED (ratification candidate)
**Version:** 0.1
**Date:** 2026-10-16
**Extends:** ADR-0042. Nothing in ADR-0042 is superseded or weakened.
**Depends on:**
- ADR-0046:
  - D-3, the ledger write guard, which this ADR extends with the dimension
    check;
  - D-1 (U), which L2-b's disposition uses.
- ADR-0041 §5.

**Investigation:** `docs/design/ef-ratification-divergences-2026-10-16.md`,
with witnesses in `tests/test_ef_ratification_divergences.py`.

**Steward recommendations, 2026-10-16** (an engineering brief; it confers no
authority):
- adopt S1;
- revise L2: enforce link integrity on write and restore, but **keep explicit
  read-time detection** of inconsistent historical records, and do not
  silently weaken ADR-0042's ratified requirement.

**Authority arises only from the ratification record below.**

---

## S1: only ratified dimensions produce new Findings

**Context.** Measured on `main`:
- The runner registers `semantic`, which is not in `RATIFIED_DIMENSIONS`.
  ADR-0042 ratified that function as `observation_coverage`, and declined the
  name "semantic" as overstating what deterministic methods can prove.
- The Critic route and the CLI persist its Findings into the canonical,
  immutable ledger.

**Decision (proposed):**
1. **The runner** executes only Evaluation Functions whose dimension is in
   `RATIFIED_DIMENSIONS`. `semantic` is removed from the registration. A
   request naming an unratified dimension runs nothing for it, and the run
   result reports that the dimension was refused.
2. **The ledger write guard** (ADR-0046 D-3) refuses a Finding whose dimension
   is not ratified (`unsupported_value`). The runner is the first defense; the
   write guard is the boundary.
3. **Historical `semantic` Findings stay** exactly as recorded: Finding
   immutability, and ADR-0046 D-2.
   - They remain inspectable through the existing Finding reads.
   - Projections label them **unratified dimension (historical)**, with their
     `evaluation_method`.
   - They are **excluded from the overall trust-card verdict** and shown
     separately, so a verdict never rests on an unauthorized evaluation.
4. **The module stays in the repository** as unratified research code. Making
   it canonical again requires a new ADR with an honest name and dispositions
   consistent with ADR-0041 and ADR-0046. A renamed dimension produces new
   Finding identities.
5. **`test_evaluation_runner`'s expectation that `semantic` runs** is changed
   to this decision. Under CA-0004 Amendment IV, a test confers no authority.

## L2 (revised): Blueprint-link integrity

ADR-0042 requires the Provenance EF to confirm, per obligation, that the
Observation is linked to the plan's Blueprint. `provenance-v1.0` never does.
ADR-0042 also leaves the disposition undefined when the link is missing.

### L2-a. Enforced at write and restore boundaries (new)

**The invariant.** Every Observation an ArchitectPlan cites in
`required_observations` is linked to that plan's Blueprint in
`blueprint_observation_links`.

| Boundary | Today | Required |
| --- | --- | --- |
| Product routes: ratify, revise, import, extract, P8 accept, legacy generate | links and plan obligations come from the same sections (ratify, revise and import tested; the rest by code reading) | unchanged; the invariant is asserted |
| The store API (`insert_blueprint(row, obs_ids, …)` followed by `insert_architect_plan`) | accepts links that differ from the sections. No product caller | **refuse** a plan whose obligations are not all linked |
| WBS chain export and restore (#255) | the closure checks existence, not this invariant | export **declares** the chain unsupported (an integrity code) rather than carry an inconsistent chain. Restore **refuses** one |

### L2-b. Read-time detection is retained (ADR-0042 is not weakened)

Historical, imported or corrupted records can violate an invariant that
today's writers keep. The Provenance EF therefore **checks the link for every
obligation**, as ADR-0042 already requires. It records the observation in
`evidence.observed_render.blueprint_link_exists`. **It never reports
`preserved` for an obligation whose link is missing.**

**Disposition for a missing link: an explicit decision is required.**

| Option | Reading | Assessment |
| --- | --- | --- |
| **`unverifiable`** (ADR-0046 U) | the Observation and its custody exist, but the obligation's relationship to the Blueprint, which is needed to verify it, is absent | **recommended**: the same meaning U ratifies ("the record required to verify is absent"); no new vocabulary |
| `omitted` | the obligation's Observation is absent | false: it exists |
| `transformed` | material alteration | false |
| `not_evaluated` | not evaluated in this invocation | false: the check ran (ADR-0046 rejects this for the same reason) |

**Precedence within one obligation.**
1. Observation missing → `omitted`.
2. Otherwise, custody record missing → `unverifiable`.
3. Otherwise, link missing → `unverifiable`.
4. Otherwise → `preserved`.

Both booleans are always recorded, so the reading (ADR-0046 D-2) shows which
record was absent.

**Version.** L2-b and ADR-0046 U activate together as `provenance-v1.1`, behind
ADR-0046's activation gate. If U is not ratified, L2-b cannot be implemented
honestly, and its witnesses stay strict-xfail.

**Existing inconsistent records.** They are never rewritten. Opening a
workspace that contains them is not refused: only **new** writes are. They
are surfaced by read-time detection, and by an integrity listing of plans
with unlinked obligations.

## Witnesses (`tests/test_ef_ratification_divergences.py`)

| Witness (strict xfail) | Boundary |
| --- | --- |
| `UnratifiedDimensionPersisted` | S1: a Critic run persists only ratified dimensions |
| `UnlinkedObligationWritten` | L2-a write: the store API refuses a plan with unlinked obligations |
| `UnlinkedChainRestored` | L2-a restore: an inconsistent chain is neither exported as covered nor restored. It needs #255's chain component and is skipped where that is absent |
| `BlueprintLinkNotChecked` | L2-b: an unlinked obligation is not `preserved` |
| `LinkAbsenceNotRecorded` | L2-b: the evidence records `blueprint_link_exists: false` |

Passing tests pin:
- the normal writers (ratify, revise, import) keep the invariant;
- the runner and route behavior that S1 changes;
- the `semantic` function's use of ratified dispositions outside their
  meanings.

## Implementation packets

1. **S1 alone.** It is stacked on the ADR-0046 D-3 packet and needs no
   schema change. `UnratifiedDimensionPersisted` converts.
2. **L2-a.** The store-API and chain export/restore checks; no schema change.
3. **L2-b,** together with ADR-0046's U activation (`provenance-v1.1`). Never
   before it.

---

## Ratification record

To be completed **only** by the Primary Human Steward.

| Field | Value |
| --- | --- |
| Decision | ☐ ratified in full ☐ ratified in part (list) ☐ returned |
| Scope ratified | ☐ S1 ☐ L2-a ☐ L2-b, with disposition: ______ |
| Ratified by | |
| Date | |
| Ratified proposal HEAD | |
| Amendments at ratification | |
