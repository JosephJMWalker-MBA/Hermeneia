# Explorer Phase 1 — Release Note
**Date:** 2026-06-26  
**Status:** Ratified  
**Verdict:** Explorer Phase 1 is sufficient to support investigator workflows and future research.

---

## What Was Built

Explorer Phase 1 implements the discovery cognitive responsibility in Hermeneia's six-role pipeline:

```
Witness → Explorer → Architect → Artist → Critic → Steward
```

Explorer's constitutional mandate: *"What evidence belongs together before we know what it means?"*

Explorer does not interpret. It discovers. Interpretation belongs to the Architect.

### Implementation

**`hermeneia/explorer/bucketer.py`**  
Groups a set of observations into ephemeral thematic clusters via a single LLM call. Buckets are compiler internals — never stored. They function as an Abstract Syntax Tree: built to structure work, discarded after interpretation is produced.

**`hermeneia/explorer/interpreter.py`**  
Generates one speculative interpretation per bucket. The stored artifact is always the interpretation and its `evidence_observation_ids` — not the bucket.

**`hermeneia/cli/explorer_cmd.py`**  
`herm explorer discover` — runs the full discovery pass and prints an inspection report. The report answers: *are the buckets any good?*

**`hermeneia/web/app.py`**  
`POST /api/e10/interpretations/discover` — web endpoint for bucket discovery with idempotency.

### Constitutional Compliance

| Constraint | Status |
|-----------|--------|
| No new tables | ✓ |
| No new canonical objects | ✓ |
| Buckets ephemeral | ✓ |
| Output via existing `proposed_interpretations` staging | ✓ |
| `evidential_status = 'speculative'` | ✓ |
| Steward decides everything that follows | ✓ |

---

## What Was Validated

Three calibration runs on a clean Gatsby corpus (2,823 observations, 193 pages, single source document):

| Run | Observations | Buckets | Singletons | Cross-corpus absurdity | All interpretations defensible |
|-----|------------:|--------:|-----------:|:---------------------:|:-----------------------------:|
| A | 20 (frontmatter + Ch. 1 opening) | 3 | 0 (0%) | No | Yes |
| B | 15 (curated literary content) | 4 | 1 (7%) | No | Yes |
| C | 50 (Ch. 1 full) | 13 | 11 (85%) | No | Yes |

The pattern is consistent across all three runs. No cross-corpus absurdity in any clean run.

### The Run C Finding

Run C's 85% singleton rate is not a bucketing failure. The first 50 observations of the Gatsby corpus are frontmatter, epigraph fragments, and sentence-level cuts from Chapter 1. Those observations genuinely do not belong together. Explorer correctly declined to group them.

This distinction matters:

> "The bucketer isn't good enough."  
> vs.  
> "The corpus segment itself contains many observations that genuinely do not belong together."

Hermeneia prevented optimizing the wrong thing.

### The Contamination Finding

Prior to clean calibration, runs were executed against a contaminated corpus (gatsby.herm contained ProHammer Classic Core Rules pages interspersed starting at page 3).

| Metric | Contaminated A | Clean A |
|--------|:--------------:|:-------:|
| Buckets | 14 | 3 |
| Singletons | 10 (71%) | 0 (0%) |
| Cross-corpus absurdity | Yes | No |

Explorer did not generate convincing nonsense. It faithfully reflected the quality of the evidence it was given. When the corpus was repaired, Explorer immediately became coherent.

**Explorer refused to lie. That is the behavior you want from an instrument built for disciplined inquiry.**

---

## What This Does Not Establish

Explorer Phase 1 does **not** claim:

- Optimal clustering algorithms
- Cross-domain generality beyond literary corpora
- Embedding quality or semantic distance metrics
- Bucket ranking or confidence scoring
- Corpus-scale navigation (4,000+ observations)
- qwen3:4b or reasoning model compatibility for bucketing (known limitation)

Those belong to future iterations. Each has a baseline now.

---

## Baseline for Future Comparison

Explorer Phase 1 is frozen at this calibration state. Every future Explorer improvement must answer:

> "Did Explorer actually improve over the Phase 1 baseline?"

Without this freeze, that question cannot be answered.

**Calibration database:** `build/hermeneia.db` (clean Gatsby corpus, 2,823 observations)  
**Calibration report:** `docs/explorer_calibration_report.md`

---

## Progression

```
Explorer
↓
Interesting idea          [Sprint E-I]

Explorer
↓
Implementation            [Sprint E-II / E-III-1]

Explorer
↓
Calibrated instrument     [Phase 1 close — 2026-06-26]
```

That is a fundamentally different status. The implementation earned trust through evidence.
