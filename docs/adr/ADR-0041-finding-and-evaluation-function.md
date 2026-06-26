# ADR-0041: Finding Ratification and Evaluation Function Authorization

**Status:** RATIFIED WITH AMENDMENTS  
**Version:** 1.0  
**Date:** 2026-06-20  
**Supersedes:** None  
**Amends:** [`CA-0003`](../amendments/CA-0003-architect-plan-contract.md) (extends Critic layer definition)  
**Closes:** [`docs/specs/finding.spec.md`](../specs/finding.spec.md), [`docs/specs/evaluation_function.spec.md`](../specs/evaluation_function.spec.md)  
**Constitutional Cost of Error:** High — introduces first canonical machine-generated Evaluation object

---

## Context

[`finding.spec.md`](../specs/finding.spec.md) and [`evaluation_function.spec.md`](../specs/evaluation_function.spec.md) were ratified as Era I provisional specifications. Both were marked NOT AUTHORIZED for implementation. Both required this ADR to answer:

- Is `Finding` ratified as canonical ontology?
- What is the identity formula?
- What fields are constitutionally required?
- What operations and statuses are permitted?
- Does `CriticReport` remain canonical, or is it reclassified?
- How do existing `validation_reports` rows map?
- Which Evaluation Functions are authorized for Sprint E1?

Era II Sprint E1 cannot begin without answers.

The current implementation has a `validation_reports` table and Critic functions in `hermeneia/compiler/critic/`. Those remain unchanged by this ADR except where explicitly stated.

---

## Decision

### 1. Finding is ratified as a canonical ontology object

`Finding` is ratified in the **Evaluation** class.

A Finding is an immutable, traceable record of a machine-observed semantic delta within exactly one orthogonal evaluation dimension.

```text
Finding = one bounded machine-observable epistemic delta
```

Finding is not:
- a dashboard;
- a score;
- a recommendation;
- a governance act;
- a human witness statement; or
- an aggregate.

Finding is the durable boundary between machine evaluation and human stewardship. Deleting a Finding would delete audit history. It is therefore canonical, not derived.

---

### 2. CriticReport is reclassified as a projection

The existing `validation_reports` table and `CriticReport` concept are reclassified from canonical Evaluation object to **legacy projection**.

`CriticReport` was the correct model before `Finding` existed. It is not wrong. It is now superseded as the durable Evaluation unit.

**Migration policy:**

- The `validation_reports` table is **not deleted** and **not renamed**. Existing rows remain inspectable.
- New Critic evaluation work produces `Finding[]` via Evaluation Functions.
- `validation_reports` may be regenerated as a projection from Findings in a future sprint.
- No code may add new rows to `validation_reports` after this ADR without explicit future authority.

This ADR authorizes the `findings` table as the new canonical Evaluation store.

---

### 3. Finding identity formula

Finding identity is **deterministic** for deterministic Evaluation Functions:

```text
finding_id = sha256(
    "finding:" +
    rendered_narrative_id + ":" +
    dimension + ":" +
    clause_ref
)
```

Where:
- `rendered_narrative_id` — the evaluated `RenderedNarrative`
- `dimension` — the orthogonal evaluation dimension (e.g., `"structural"`)
- `clause_ref` — the specific contract clause, paragraph index, or rule identifier being evaluated (e.g., `"paragraph:1:term:green_light"`)

**Rationale:** The same canonical inputs under the same deterministic dimension must produce the same Finding ID. This satisfies INV-10 (Critic Determinism) and makes re-evaluation idempotent (`INSERT OR IGNORE`).

Identity must not derive from: UI position, steward credential, provider reputation, aggregate score, or invocation timestamp.

---

### 4. Required fields

| Field | Constitutional? | Notes |
|---|---|---|
| `id` | Required | sha256 formula above |
| `rendered_narrative_id` | Required | FK → `rendered_narratives` |
| `architect_plan_id` | Required | FK → `architect_plans` |
| `dimension` | Required | Controlled vocabulary; this ADR ratifies `structural` |
| `clause_ref` | Required | Identifies the specific obligation evaluated |
| `operation` | Required | Controlled vocabulary (section 5) |
| `status` | Required | Controlled vocabulary (section 5) |
| `evidence` | Required | JSON; bounded material used to reach Finding |
| `evaluation_method` | Required | Function name + version string |
| `constitution_version` | Required | JSON; same schema as `execution_config.constitutional_profile` |
| `created_at` | Required | ISO 8601 UTC |

---

### 5. Operations and statuses

**Operations** (for Semantic Contract Fulfillment; other dimensions may ratify additional operations via future ADR):

| Operation | Meaning |
|---|---|
| `preservation` | The rendered artifact transmits the evaluated obligation's required structure |
| `omission` | The rendered artifact fails to transmit a required obligation |
| `transformation` | The rendered artifact transmits a changed version of the obligation |
| `injection` | The rendered artifact introduces material not authorized by the contract |
| `not_evaluated` | The obligation was not evaluated in this invocation |

`not_evaluated` is not a success state. It records absence of evaluation, not conformance.

**Statuses** (the primary state of each evaluated obligation):

| Status | Meaning |
|---|---|
| `preserved` | Obligation fulfilled |
| `omitted` | Required obligation absent from rendered text |
| `transformed` | Obligation present but materially altered |
| `injected` | Unsupported material present |
| `not_evaluated` | No authoritative evaluation exists |

One obligation may produce multiple Findings if distinct deltas are observed within the same dimension (e.g., a term omitted and an unsupported claim injected in the same paragraph). Each is a separate Finding with a unique `clause_ref` suffix.

---

### 6. Authorized Evaluation Functions — Sprint E1

This ADR authorizes **one** Evaluation Function for Sprint E1:

#### Structural Evaluation Function

**Dimension:** `structural`

**Inputs:**
- `ArchitectPlan` (specifically `architect_plan_paragraphs.required_terms`)
- `RenderedNarrative.text`

**Method:** For each paragraph in the plan, for each required term in that paragraph's `required_terms` list, perform case-insensitive substring match against the rendered narrative text.

**Output:** One `Finding` per required term per paragraph:
- If term is present in text: `operation=preservation`, `status=preserved`
- If term is absent: `operation=omission`, `status=omitted`

**Properties:**
- Zero LLM dependency
- Deterministic (same inputs → same Finding IDs via formula above)
- Read-only (does not write to any table except `findings`)
- Bounded (one finding per term per paragraph — no synthesis across paragraphs)
- Orthogonal (structural only — makes no claim about semantic accuracy, provenance, or accessibility)

**Limitations (acknowledged):**
- Substring match is necessary but not sufficient for semantic fidelity. A term may appear without its meaning being preserved. This limitation is constitutionally correct — the Structural EF only evaluates structural obligation fulfillment. Semantic accuracy belongs to the Semantic EF (Sprint E3).
- Priority field (`critical` / `recommended`) from `required_terms` may inform future projection views but does not change Finding status in this sprint.

**Implementation location:** `hermeneia/compiler/evaluation_functions/structural.py`

---

### 7. Executable invariants authorized by this ADR

The following invariants are added to the constitutional test suite:

- **INV-EF-1 (Structural EF Determinism):** Running the Structural EF twice on the same `(rendered_narrative_id, architect_plan_id)` pair must produce identical `finding_id` values for identical clause refs.
- **INV-EF-2 (Finding Read-Only):** The Structural EF implementation must contain no write operations except `INSERT OR IGNORE INTO findings`.
- **INV-EF-3 (No Empty Silence):** If an `architect_plan_paragraph` has required terms and the function completes, the Finding set must be non-empty. Silence is not permitted.
- **INV-EF-4 (Orthogonality Boundary):** The Structural EF must not write to `validation_reports`, `rendered_narratives`, `architect_plans`, or any evidence table.

---

### 8. What this ADR does not authorize

- Semantic Evaluation Function (Sprint E3)
- Provenance Evaluation Function (Sprint E3)
- Accessibility Evaluation Function (Sprint E3)
- Constitutional Evaluation Function (Sprint E3)
- Finding supersession behavior (Sprint E2)
- Finding lineage beyond FK references (Sprint E2)
- Projection layer (Sprint E4)
- Any modification to `validation_reports` rows or schema
- Deletion or renaming of `CriticReport` vocabulary in documentation
- Any new API endpoints
- Any UI changes

---

## Consequences

**Positive:**
- The Critic layer is proven to be computational infrastructure, not a conversational agent.
- The first `Finding[]` is a durable machine-generated epistemic object with identity, provenance, and constitutional profile.
- Era II Sprint E1 is now authorized.

**Risks:**
- Substring matching is a weak semantic signal. This risk is constitutionally accepted: the Structural EF is intended to be necessary-but-not-sufficient. It proves the architecture, not semantic fidelity.
- `validation_reports` freeze may surprise callers that expected to accumulate critic output. The freeze is intentional.

**Schema change:** One new table (`findings`). No existing tables modified.

---

## Amendments

Ratified with three amendments by the Primary Human Steward on 2026-06-20.

### Amendment I — Identity derives from canonical obligation identity, not clause labels

**Replaces section 3.**

The identity formula must not depend on document-level references such as `clause_ref` string labels. Suppose the Architect is regenerated under a future version and internal clause numbering changes while the semantics remain identical. The old formula would produce a new identity for an unchanged obligation.

Identity shall derive from the canonical identity of the obligation itself:

```text
finding_id = sha256(
    "finding:"
    + rendered_narrative_id + ":"
    + dimension + ":"
    + obligation_id
)
```

Where `obligation_id` is computed from the ontology of the obligation, not its presentation label:

```text
obligation_id = sha256(
    "obligation:" + dimension + ":"
    + plan_id + ":"
    + str(paragraph_order_idx) + ":"
    + term_text.lower()
)
```

For the Structural EF: `plan_id` is the content-addressable ArchitectPlan ID; `paragraph_order_idx` is the paragraph's position in the plan (stable within a plan version); `term_text` is the required term itself (the semantic obligation content). `.lower()` normalizes case so "Green Light" and "green light" are the same obligation.

`paragraph_order_idx` is stable within a plan because `architect_plan_paragraphs.order_idx` derives from blueprint section order, which is part of the blueprint's content hash.

### Amendment II — Findings preserve observations, not conclusions

**Strengthens the `evidence` field definition in section 4.**

The `evidence` JSON field must preserve the raw machine-observable material. It must not contain evaluative prose, editorial summaries, or natural-language conclusions.

Required:

```json
{
  "contract_obligation": "<the required term or obligation text>",
  "observed_render": "<verbatim excerpt from rendered text, or null if absent>",
  "supporting_trace": ["<canonical IDs used in evaluation>"]
}
```

Forbidden:

```json
{
  "finding": "Meaning preserved."
}
```

The `operation` and `status` fields carry the structured disposition. `evidence` carries only what was observed. The Evaluation Function computes. The Finding records. The Finding does not editorialize.

This keeps Findings maximally reusable for future analytical layers (Shannon entropy, MDL, etc.) that will compute their own interpretations over the raw observations.

### Amendment III — Completeness Invariant

**Replaces INV-EF-3 and elevates it.**

Every Evaluation Function SHALL produce exactly one Finding for every obligation within its declared scope. No obligation may disappear into silence.

```text
For every obligation O in scope:
    exactly one Finding(O) exists in the output
```

This is the **Completeness Invariant**. It turns `Finding[]` into a complete semantic ledger rather than a sparse list of failures.

For the Structural EF: for every `(paragraph, required_term)` pair in the ArchitectPlan, exactly one Finding is produced — `preserved` or `omitted`. No pair may be skipped.

**Consequence:** Given an ArchitectPlan with N obligations, the Structural EF must produce exactly N Findings. Projections (Trust Card, Dashboard, Semantic Inspector) can then be regenerated deterministically from a complete, exhaustive substrate.

**Added invariant: INV-EF-COMPLETENESS**

```text
|Findings produced| == |obligations declared in scope|
```

A conforming implementation must fail — not silently succeed — if this equality cannot be satisfied.

---

## Ratification

Ratified with amendments by the Primary Human Steward on 2026-06-20.

Upon ratification:
- `docs/specs/finding.spec.md` status changes to: **RATIFIED — see ADR-0041**
- `docs/specs/evaluation_function.spec.md` status changes to: **RATIFIED (Structural EF) — see ADR-0041**
- Sprint E1 implementation is authorized
- `validation_reports` is frozen for new writes pending Sprint E2 migration analysis
