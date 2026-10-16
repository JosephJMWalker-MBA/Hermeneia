# Evaluation Function ratification divergences: investigation (2026-10-16)

**Status:** investigation record. The decisions are proposed in
**ADR-0047** (ratification candidate), written after the Steward's review
of 2026-10-16. **Nothing here is changed or decided.** Evaluators, the runner, the Finding store and every
historical Finding are as on `main`.

**Origin.** This came out of the ADR-0046 review (#259), and is kept
independent of it.

**Evidence.** `tests/test_ef_ratification_divergences.py`:
- 5 passing tests pin the current behavior;
- 2 strict-xfail witnesses pin the ratified text.
- **Mutation-checked.** Applying each remedy, temporarily and uncommitted,
  makes its witness show `XPASS(strict)`.

**Authority order (Constitution Art. XV; Authority Index).** ADRs govern code.
Tests "do not possess authority to weaken or reinterpret" constitutional
guarantees (CA-0004 Amendment IV).

---

## 1. ADR-0042's Blueprint-link check is not implemented

**Ratified text.** ADR-0042, Provenance EF, method:
- "Query `provenance` table for the observation ID."
- "Query `blueprint_observation_links` to confirm the observation is linked to
  the blueprint."
- "If both exist: `operation=preservation`, `status=preserved`."

**Code.** `provenance-v1.0` (`compiler/evaluation_functions/provenance.py`)
queries `observations` and `provenance` only. Its evidence records
`observation_exists` and `provenance_exists`. No link fact is checked or
recorded.

### Witness

A plan obligation cites an Observation that exists and has provenance, but is
**not linked** to the plan's Blueprint.
- `provenance-v1.0` classifies it `preservation` / `preserved` (pinned).
- **`BlueprintLinkNotChecked`** (strict xfail) requires that it not be
  `preserved`.

### Reachability: the divergence is latent

| Writer | Plan obligations and links derived from |
| --- | --- |
| `/api/pipeline/ratify-blueprint`, `/api/pipeline/revise-blueprint` | the same `sections` (**tested**: every plan's cited Observations ⊆ its Blueprint's links) |
| Legacy AI generation (`app.py`), `blueprinter` CLI, `bootstrap` CLI | the same `sections` (code reading) |
| `SQLiteStore.insert_blueprint(row, obs_ids, …)` | **separate** arguments. It has no product caller; only test fixtures use it |

The plan compiler reads `required_observations` from the Blueprint's
`sections`. So no product route on `main` writes a cited-but-unlinked
obligation. The state arises only from constructed or imported data. The
witness constructs it directly, as the existing `test_era2_sprint_e3`
phantom-obligation test does.

### Authority implications

- **The code under-implements a ratified method.** "Preserved" asserts less
  than ADR-0042 says. ADR-0046 D-2's reading of v1.0 `preserved` already lists
  "linked to the plan's Blueprint" as **not established**.
- **ADR-0042 has a gap.** It does not define the disposition when the
  Observation and provenance exist but the link does not. A faithful
  implementation would therefore need a new decision anyway.
- **No historical Finding is wrong about what it recorded.** Its evidence
  never claimed a link.

### Proposed remedies (independent of ADR-0046)

| | Remedy | Consequence |
| --- | --- | --- |
| **L1** | Implement the per-Finding link check | needs a ratified disposition for "not linked", which ADR-0042 lacks. Adds a link fact to `evidence`. A new `evaluation_method`. Subject to ADR-0046 D-3 (divergence and retention) |
| L2 (first proposal) | Replace the per-Finding check with an **executable invariant** enforced at Blueprint/plan write and restore | **superseded by the Steward's revision** (2026-10-16): historical, imported or corrupted records can violate an invariant that current writers keep, so the evaluator must still detect it |
| **L2 revised (ADR-0047)** | Enforce the invariant at write and restore (L2-a) **and** keep read-time detection: the EF checks the link, records `blueprint_link_exists`, and never reports `preserved` without it (L2-b) | ADR-0042 is extended, not weakened. The missing-link disposition is an explicit decision; `unverifiable` is recommended |
| L3 | Record and defer | the ratified text keeps claiming a check the code does not make |

---

## 2. The `semantic` dimension runs and is persisted without ratification

**Ratified text:**
- **ADR-0042.** It listed `semantic` as pending, then ratified that function as
  **`observation_coverage`**: "Calling it `"semantic"` would overstate what
  deterministic … methods can prove."
- **Registration rule.** "Each must be declared in `RATIFIED_DIMENSIONS` before
  its tests may run."
- **`RATIFIED_DIMENSIONS`** (`base.py`) lists `structural`, `provenance`,
  `observation_coverage`, `constitutional` and `accessibility`.

**Code (pinned):**
- `runner._load_efs` registers `semantic` (`semantic-v1.0`). It is the only
  registered dimension outside the registry.
- `validate_ef_contract` does not consult the registry, so `semantic`
  validates clean.
- **The product Critic route** (`/api/pipeline/run-critic`) and **the CLI**
  persist `semantic` Findings into the canonical, immutable `findings` table.
  The trust card reports a `semantic` dimension verdict, which feeds the
  overall verdict.
- **Its dispositions differ from ADR-0041 §5** (pinned):
  - `transformed` means "interpretation exists but observation trace thin"
    (no alteration);
  - `not_evaluated` means "no interpretation chain" (the function ran).
  - It is the **only** producer of `not_evaluated` today (measured on #259).
- **`test_evaluation_runner`** pins `semantic` as a registered dimension. Under
  CA-0004 IV, that confers no authority.
- **History.** `semantic.py` and its runner registration predate this
  repository's first commit (2026-06-26, after ADR-0042's ratification on
  2026-06-20). Their origin is not recoverable here.

### Witness

**`UnratifiedDimensionPersisted`** (strict xfail) requires that a Critic run
persist only ratified dimensions.

### Authority implications

- **Unauthorized canonical objects.** ADR-0041 makes Findings canonical and
  immutable. An unratified function has been writing canonical Findings, under
  the name ADR-0042 rejected as overstating.
- **The history cannot be removed, and should not be.** The storage triggers
  refuse deletion. Historical `semantic` Findings stay as recorded and should
  be presented as "from an unratified dimension" (consistent with ADR-0046
  D-2).
- **Identity.** Finding identity includes the dimension. Ratifying the function
  under another name would give its future Findings new identities; the
  historical ones keep theirs.
- **Interplay with ADR-0046:**
  - amending `not_evaluated` (its option N) would retroactively bless
    `semantic`'s usage;
  - D-3's dimension-registry check would refuse `semantic` Findings.

  Both make this decision a prerequisite.

### Proposed remedies

| | Remedy | Consequence |
| --- | --- | --- |
| **S1 (recommended now)** | **Fail closed on the registry.** The runner executes, and the persistence guard accepts, only `RATIFIED_DIMENSIONS`. Historical `semantic` Findings stay and are labelled unratified | restores the authority order; reversible. **Changes Critic output**: fewer Findings, and no `semantic` verdict on the trust card. `test_evaluation_runner` must be updated. Needs authorization |
| S2 | Ratify the function through a new ADR, with an honest name and dispositions consistent with ADR-0041 (or ADR-0046) | a research decision about what the function proves. A renamed dimension gives new Finding identities |
| S3 | Quarantine: compute it as a projection only, never persisted | keeps the signal, but no longer as a ledger entry. Needs a projection design |

**Recommended order:**
1. S1 (now, if authorized);
2. S2 or S3 as a later, deliberate decision;
3. then enable ADR-0046 D-3's dimension check.

---

## Not done here

- No evaluator, runner, store or test expectation outside the new file was
  changed.
- No Finding was rewritten.
- No remedy is enabled.
