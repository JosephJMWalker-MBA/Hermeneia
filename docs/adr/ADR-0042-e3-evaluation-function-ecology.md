# ADR-0042: Evaluation Function Ecology — Sprint E3

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-20  
**Supersedes:** None  
**Extends:** [ADR-0041](ADR-0041-finding-and-evaluation-function.md)  
**Constitutional Cost of Error:** Medium — adds dimensions, does not alter Finding ontology

---

## Context

ADR-0041 ratified the Structural EF and the Finding ontology. It listed four additional
dimensions as pending ADR: `semantic`, `provenance`, `accessibility`, `constitutional`.

Sprint E3 authorizes those four functions. Each must satisfy the
`EvaluationFunctionContract` from `base.py`. Each must be declared in
`RATIFIED_DIMENSIONS` before its tests may run.

The central engineering discipline (established before E3):

> The Semantic EF must not become a synthesizer. It is an evaluator.
> Each obligation → exactly one Finding. The function may use any
> deterministic technique internally, but the output remains obligation-local.

---

## Decision

### Four dimensions are ratified

| Dimension | Obligation source | Method class | LLM? |
|---|---|---|---|
| `provenance` | `required_observations` per paragraph | Existence check — does each cited observation exist in the lineage? | No |
| `observation_coverage` | `required_observations` per paragraph | Presence check — does each observation's raw text appear in the narrative? | No |
| `constitutional` | `execution_config` on `RenderedNarrative` | Schema check — does the artifact carry a valid constitutional profile? | No |
| `accessibility` | `rendered_narratives.text` | Structural heuristics — sentence length, paragraph count | No |

**Note on naming:** The dimension previously called `"semantic"` is ratified as
`"observation_coverage"`. This name is constitutionally honest: the function checks
whether observation content is present in the rendered text — a necessary but not
sufficient condition for semantic fidelity. Calling it `"semantic"` would overstate
what deterministic substring-and-heuristic methods can prove.

True semantic evaluation — verifying that *meaning* (not merely text) survived
transmission — requires either LLM-assisted evaluation with full CI-011 audit
compliance, or a ratified human witness session. Both are deferred to future ADRs.
This ADR does not authorize LLM-backed EFs.

---

### Provenance EF (`provenance`)

**Dimension:** `provenance`  
**Scope:** `["required_observations"]`  
**Guarantees:** `deterministic`, `complete`, `read_only`, `orthogonal`, `zero_llm`

**Method:** For every `required_observation` ID in every paragraph of the ArchitectPlan:
- Query `provenance` table for the observation ID.
- Query `blueprint_observation_links` to confirm the observation is linked to the blueprint.
- If both exist: `operation=preservation`, `status=preserved`
- If observation exists but provenance record is missing: `operation=transformation`, `status=transformed` (observation persists without full provenance — a degraded state)
- If observation does not exist at all: `operation=omission`, `status=omitted`

**Obligation identity:**
```
obligation_id = sha256("obligation:provenance:" + plan_id + ":" + str(order_idx) + ":" + obs_id)
```

**What it proves:** Every observation the Architect cited as required for this paragraph
has a persisted provenance record. If provenance is missing, it cannot be independently
witnessed.

**What it does not prove:** That the observation's meaning was transmitted to the reader.
That is `observation_coverage`'s concern.

---

### Observation Coverage EF (`observation_coverage`)

**Dimension:** `observation_coverage`  
**Scope:** `["required_observations"]`  
**Guarantees:** `deterministic`, `complete`, `read_only`, `orthogonal`, `zero_llm`

**Method:** For every `required_observation` ID in every paragraph:
- Load the observation's `raw_text` from the database.
- Case-insensitive substring check: does any 6-word window from `raw_text` appear in
  the narrative text? (Shorter phrases risk false positives from common words.)
- If any window matches: `operation=preservation`, `status=preserved`
- If no window matches: `operation=omission`, `status=omitted`

**Obligation identity:**
```
obligation_id = sha256("obligation:observation_coverage:" + plan_id + ":" + str(order_idx) + ":" + obs_id)
```

**Acknowledged limitation (constitutional record):** Presence of a text window is
necessary but not sufficient for semantic fidelity. A passage may appear without its
meaning being preserved. This limitation is recorded here, not papered over. Future
LLM-backed or witness-based EFs will address the gap.

---

### Constitutional EF (`constitutional`)

**Dimension:** `constitutional`  
**Scope:** `["execution_config"]`  
**Guarantees:** `deterministic`, `complete`, `read_only`, `orthogonal`, `zero_llm`

**Method:** Examines the `execution_config` JSON field on the `RenderedNarrative`.
Produces one Finding per required constitutional profile field:

Required fields in `execution_config.constitutional_profile`:
- `constitution_version`
- `authority_index_version`
- `invariant_profile`
- `architecture_profile`

For each required field:
- If present and non-empty: `operation=preservation`, `status=preserved`
- If missing or null: `operation=omission`, `status=omitted`

Additionally: one Finding for `execution_config` itself:
- If `execution_config` is non-null and parseable JSON: `preserved`
- If null or unparseable: `omitted`

**What it proves:** The artifact carries the constitutional profile under which it was
produced. A narrative without a constitutional profile cannot be audited for constitutional
conformance.

---

### Accessibility EF (`accessibility`)

**Dimension:** `accessibility`  
**Scope:** `["rendered_text"]`  
**Guarantees:** `deterministic`, `complete`, `read_only`, `orthogonal`, `zero_llm`

**Method:** Heuristic structural analysis of `RenderedNarrative.text`. Produces one
Finding per accessibility obligation:

| Obligation | Check | Preserved if |
|---|---|---|
| `paragraph_structure` | Text contains paragraph breaks (`\n\n`) | ≥1 paragraph break |
| `sentence_length` | Mean words per sentence | ≤ 35 words (approximate readable ceiling) |
| `text_present` | Narrative is non-empty | len(text.strip()) > 0 |

Each obligation uses a fixed rule, not a model. The rules are intentionally conservative —
they are necessary conditions for human readability, not sufficient conditions.

**Obligation identity:** `sha256("obligation:accessibility:" + narrative_id + ":" + obligation_key)`

Note: Accessibility obligations are narrative-level, not paragraph-level, so
`narrative_id` anchors identity rather than `plan_id + order_idx`.

---

### What this ADR does not authorize

- LLM-backed Evaluation Functions of any kind
- A "semantic fidelity score" or aggregate metric
- Any modification to Finding schema
- Any new canonical objects
- Any projection layer work (Sprint E4)

---

## Consequences

**Positive:** Four new orthogonal dimensions produce independent Finding sets.
No dimension's findings can mask another's. A provenance pass cannot cancel an
observation coverage omission.

**Naming honesty:** `observation_coverage` instead of `semantic` preserves the
constitutional record of what deterministic methods can actually prove. Future
auditors will not be misled about the strength of the evidence.

**Completeness:** Each EF satisfies Amendment III — every obligation in scope
produces exactly one Finding, making the full ledger computable for any narrative.

---

## Ratification

Ratified by the Primary Human Steward on 2026-06-20.

Upon ratification:
- `RATIFIED_DIMENSIONS` in `base.py` is updated to include all four new dimensions
- Sprint E3 implementation is authorized for all four EFs
