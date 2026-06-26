# Sprint 003 — Coverage Engine Specification
**herm coverage v0.1**  
**Status:** Ratified for Implementation  
**Date:** 2026-06-26  
**Steward Decision:** Ratified — pure engineering, no LLM, no schema changes, deterministic and exhaustively testable

---

## Mission

Determine whether a publication is ready to be compiled — not whether it has already been written.

Coverage answers exactly one question:

> Does every declared requirement have accountable evidence?

Nothing more. Nothing less.

---

## Coverage Invariant

**Coverage measures declared obligations, never inferred obligations.**

This is the single most important engineering rule in the Coverage Engine. If a section declares `required_tags: [figure, replicated]`, Coverage checks whether artifacts tagged `figure` and `replicated` exist in the resolved artifact set. It does not:

- Scan the white paper prose for "figure-like" paragraphs
- Infer that a related tag satisfies an unmet requirement
- Guess that partial evidence is sufficient
- Rewrite requirements to match available evidence

If a requirement is unresolved, the report says: *Requirement unresolved.* That is all.

This discipline makes Coverage an auditor, not an assistant.

---

## Inputs

Exactly three:

```
build.json
    │
compile_manifest.yaml  (path read from build.json.manifest_path)
    │
Blueprint              (path read from manifest.blueprint)
```

### What is NOT an input

```
white_paper.md
```

This is intentional. If Coverage requires the finished paper to tell you what's missing, it is too late. Coverage runs before compilation, not after.

---

## Build Pipeline

```
build.json
    │
    ▼
Load Manifest (path from build.json)
    │
    ▼
Load Blueprint (path from manifest)
    │
    ▼
Resolve Artifact Set (from build.json.source_artifacts)
    │
    ▼
Build Tag Index ({tag → [artifact, ...]})
    │
    ▼
Evaluate Section Requirements
    │
    ▼
Produce Coverage Matrix
    │
    ▼
Emit coverage.json + coverage.md
```

No AI. No LLM. Every step deterministic.

---

## Coverage Matrix

The internal representation before reporting. One row per section, one column per declared requirement type.

```
Section          | Blueprint | Evidence | Figure | Methodology | Status
─────────────────────────────────────────────────────────────────────────
abstract         |     ✓     |    ✓     |   —    |     ✓       | PASS
1-introduction   |     ✓     |    —     |   —    |     ✓       | WARN
5-calibration    |     ✓     |    ✓     |   ✓    |     ✓       | PASS
8-future-work    |     ✓     |    ✓     |   —    |     —       | WARN
```

Each cell resolves to:
- `✓` — required tag present in resolved artifact set with at least one artifact
- `—` — required tag absent from resolved artifact set
- `✗` — tag declared required but artifact at declared path does not exist (FAIL condition)

---

## Section Evaluation Logic

For each section in `manifest.sections`:

```
required_tags: [tag1, tag2, ...]
required_claims: [claim1, claim2, ...]   # recorded but not evaluated in v0.1
```

**Tag resolution:**
```python
for tag in section.required_tags:
    if tag in tag_index and len(tag_index[tag]) > 0:
        result = PASS
    else:
        result = WARN  # or FAIL if tag was marked mandatory
```

**Claim evaluation:** Recorded in coverage.json as `claims_checkable: false` in v0.1. Claims require programmatic Critic evaluation — that is Sprint 004. Coverage records *what* needs checking; it does not attempt to check prose.

**Section outcome:**
- `PASS` — all required tags resolved
- `WARN` — one or more required tags unresolved (but no artifact path failures)
- `FAIL` — declared artifact path does not exist on disk (a build integrity failure)

---

## Coverage Report Format

### coverage.md (human-readable)

```markdown
# Coverage Report
**Build:** white-paper-rc-2
**Generated:** 2026-06-26 …

## Coverage Summary

| Metric | Count |
|--------|-------|
| Sections evaluated | 9 |
| PASS | 7 |
| WARN | 2 |
| FAIL | 0 |
| Overall | 78% |

*Overall = PASS / (PASS + WARN + FAIL). The percentage is informational.
The unresolved requirements are what matter.*

## Section Detail

### abstract — PASS
Required tags: `thesis`, `governing-question`, `calibration`
All tags resolved. ✓

### 8-future-work — WARN
Required tags: `research-program`, `hypothesis`, `future-work`

| Tag | Status | Resolved by |
|-----|--------|-------------|
| research-program | ✓ | docs/research/research_hypotheses.md |
| hypothesis | ✓ | docs/research/research_hypotheses.md |
| future-work | ✗ UNRESOLVED | — |

**Missing:** `future-work`
No artifact in the manifest carries this tag.
Requirement unresolved.

## Claims Status
Claims evaluation requires programmatic Critic (Sprint 004).
Declared claims are recorded in coverage.json for future evaluation.
```

### coverage.json (machine-readable)

```json
{
  "coverage_engine_version": "0.1.0",
  "build_id": "white-paper-rc-2",
  "generated_at": "2026-06-26T…",
  "manifest_path": "docs/builds/white_paper.compile.yaml",
  "blueprint_id": "000001",
  "tag_index": {
    "thesis": ["docs/papers/blueprint_000001.md"],
    "calibration": ["docs/research/experiment_001_english.md", "…"],
    "future-work": []
  },
  "sections": [
    {
      "section": "abstract",
      "status": "PASS",
      "required_tags": ["thesis", "governing-question", "calibration"],
      "tag_results": [
        {"tag": "thesis", "status": "PASS", "resolved_by": ["docs/papers/blueprint_000001.md"]},
        {"tag": "governing-question", "status": "PASS", "resolved_by": ["…"]},
        {"tag": "calibration", "status": "PASS", "resolved_by": ["…"]}
      ],
      "required_claims": ["AI collapses distinct cognitive responsibilities…"],
      "claims_checkable": false,
      "claims_note": "Programmatic claim evaluation deferred to Sprint 004 Critic integration"
    },
    {
      "section": "8-future-work",
      "status": "WARN",
      "required_tags": ["research-program", "hypothesis", "future-work"],
      "tag_results": [
        {"tag": "research-program", "status": "PASS", "resolved_by": ["…"]},
        {"tag": "hypothesis", "status": "PASS", "resolved_by": ["…"]},
        {"tag": "future-work", "status": "WARN", "resolved_by": [], "note": "Requirement unresolved"}
      ],
      "required_claims": ["…"],
      "claims_checkable": false
    }
  ],
  "summary": {
    "sections_evaluated": 9,
    "pass": 7,
    "warn": 2,
    "fail": 0,
    "overall_pct": 78
  },
  "outcome": "warn"
}
```

---

## Failure Conditions

```
Condition                                           Outcome   Exit
───────────────────────────────────────────────────────────────────
build.json not found                                FAIL      1
build.json malformed                                FAIL      1
manifest_path in build.json points to missing file  FAIL      1
manifest YAML malformed                             FAIL      1
Blueprint path not found                            FAIL      1
Artifact in manifest not found on disk              FAIL      1
Required tag absent from all artifacts              WARN      0
Required claim not checkable (v0.1)                 NOTE      0
```

Coverage never invents evidence to resolve a WARN. It reports. The Steward decides.

---

## CLI Interface

```
herm coverage [--build <path>] [--output <dir>] [--verbose]
```

| Flag | Default | Notes |
|------|---------|-------|
| `--build` | `publication/build.json` | Path to build.json from prior `herm build` run |
| `--output` | `publication/` | Directory for coverage.json and coverage.md |
| `--verbose` | off | Print per-section tag resolution detail |

### Expected stdout

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  herm coverage  white-paper-rc-2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Reading build.json...          PASS
  Loading manifest...            PASS
  Loading Blueprint...           PASS
  Building tag index...          PASS  [9 tags across 10 artifacts]
  Checking section requirements  PASS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Coverage: white-paper-rc-2

    9 sections evaluated
    7 PASS
    2 WARNING
    0 FAIL

  coverage.json written.
  coverage.md written.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## New Ontology

None. `herm coverage` introduces no new database tables, no new canonical objects, no new schema.

`coverage.json` and `coverage.md` are compiler outputs — disposable projections, the same as `build.json`. They are not canonical artifacts and are not stored in the constitutional database.

---

## Composability Note

`herm coverage` is a standalone tool. It reads `build.json` but does not call `herm build`. A future version of `herm build` may optionally invoke `herm coverage` as a stage — but that wiring belongs to a future sprint. The tools must be independently useful before they are orchestrated.

---

## What v0.1 Defers

| Deferred | Why | Future sprint |
|----------|-----|---------------|
| Programmatic claim evaluation | Requires Critic integration | Sprint 004 |
| Tag count thresholds (minimum N artifacts per tag) | Requires configurable manifest extension | After v0.1 stable |
| Cross-section dependency checking | Requires Blueprint semantic parsing | Future |
| Differential coverage (what changed since last build) | Requires build.json history | After Preservation Layer |

---

## Why This Sprint Matters

Coverage is the first system that proves the tag-addressed compiler philosophy. The compiler doesn't search filenames. It searches tags. Coverage makes that auditable.

Every line of code in this sprint is deterministic. Every behavior is exhaustively testable without model invocation. That is the engineering character the publication infrastructure should have throughout.
