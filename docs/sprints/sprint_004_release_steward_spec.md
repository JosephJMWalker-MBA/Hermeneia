# Sprint 004 — Release Steward Specification
**herm release v0.1**  
**Status:** Ratified for Implementation  
**Date:** 2026-06-26  
**Steward Decision:** Ratified — clean constitutional boundary, no new ontology, deterministic engineering with one intentional null

---

## Mission

The Release Steward answers exactly one question:

> Given what was built and what was measured, does the declared release policy allow a recommendation?

Nothing more. Nothing less.

---

## Constitutional Principles

**The Release Steward may recommend publication, but it may never declare publication.**

The recommendation is the last thing automation can produce. Everything after it is a constitutional act requiring a human signature.

The `steward_signature` field in `release_recommendation.json` is intentionally `null` when emitted. It is not a placeholder. It is a statement about what automation is and is not allowed to do.

---

**Release criteria evaluate declared facts, not executable policy.**

This principle preserves three properties that must never be traded away:

1. **Auditability** — a human can inspect `release_criteria.yaml` and understand every rule in under a minute.
2. **Determinism** — no hidden logic, no embedded scripts, no policy engine.
3. **Authority separation** — the Release Steward evaluates; it never interprets its own criteria.

A corollary: **Release criteria must be inspectable without executing code.**

This rules out predicate functions, embedded scripts, conditional logic, and any form of executable policy. Configuration over scripting. Declaration over inference. Governance over cleverness.

---

## The Three Verbs

```
Build knows.

Coverage measures.

Release recommends.
```

These are different verbs. They are also different artifacts. No single artifact spans two verbs.

---

## Where Release Criteria Live

Release criteria live in `release_criteria.yaml` — a separate file from the compile manifest.

This is not a convenience. It is a constitutional decision.

**Why not `compile_manifest.yaml`?**  
The manifest is a build recipe: what to assemble and how. Release criteria are publication governance: what conditions must hold before the work is presented to the world. These answer different questions. An artifact that answers two questions is a design failure waiting to happen. Changing release standards would require amending the build recipe, coupling two layers that have no business knowing about each other.

**Why not the Blueprint?**  
The Blueprint describes understanding — what the work must establish intellectually. Release criteria describe publication governance — what must be administratively true before recommendation. These are different constitutional layers. Merging them would mean that changing publication standards requires amending the intellectual record of the investigation.

**The clean separation:**

```
Blueprint              — What understanding must exist?
Manifest               — What was assembled to express it?
Coverage               — Was every declared obligation satisfied?
Release Criteria       — What must be true before recommendation?
Release Steward        — Given all of the above: recommend or do not recommend.
```

Every artifact answers one question. No artifact answers two.

---

## Inputs

Exactly three:

```
build.json
    │
coverage.json           (path: publication/coverage.json, or derived from build.json)
    │
release_criteria.yaml   (path: declared in manifest, or convention path)
```

The Release Steward reads these files. It does not re-run the build. It does not re-run coverage. It does not read the white paper prose. It does not read the Blueprint directly. The Blueprint has already been read — its obligations are already captured in `coverage.json`.

### What is NOT an input

```
white_paper.md
Blueprint (directly)
source artifacts
```

By the time Release Steward runs, the relevant facts from all of these have already been extracted into `build.json` and `coverage.json`. The Release Steward trusts the measurement layer.

---

## Release Criteria File

Convention path: `docs/builds/release_criteria.yaml`

The manifest may declare an explicit path via `release_criteria` key. If absent, the convention path is used.

### Schema

Each criterion is self-describing. The criterion's `name` appears verbatim in the recommendation report — no names are invented at evaluation time.

```yaml
# release_criteria.yaml
# Governs what must be true before herm release can recommend publication.
# This file is governance, not a build recipe.
# Every criterion is a declared fact. No executable logic.

criteria_version: "0.1"
applies_to: white-paper  # or a specific build_id pattern

criteria:
  - name: Blueprint Ratified
    source: build.json
    path: blueprint_status
    equals: ratified
    required: true

  - name: Build Pass
    source: build.json
    path: outcome
    equals: pass
    required: true

  - name: Coverage Pass
    source: coverage.json
    path: outcome
    equals: pass
    required: true

  - name: No Coverage Failures
    source: coverage.json
    path: summary.fail
    equals: 0
    required: true

  - name: No Draft Artifacts
    source: build.json
    path: has_draft_artifacts
    equals: false
    required: false
```

### Required vs. Advisory

- **`required: true`** — if unmet, outcome is `WITHHOLD`. No exceptions.
- **`required: false`** — recorded in the recommendation with notes. Does not change the outcome. The human Steward sees it and decides whether it matters.

This distinction preserves the constitutional boundary: automation can report severity, but it cannot decide what to do about it.

### Evaluation model

Each criterion specifies:
- `source` — which artifact to read (`build.json` or `coverage.json`)
- `path` — dot-notation path to the field within that artifact
- `equals` — the exact value that field must equal for the criterion to pass

There is no `greater_than`, no `less_than`, no `contains`, no regex. `equals` only. If a future criterion cannot be expressed as an equality check against a declared field, that is a signal that either the criterion is wrong or the emitted artifact is missing a field it should declare.

---

## Evaluation Algorithm

The algorithm is embarrassingly small. That is a sign of correct design.

```
Read build.json
    │
Read coverage.json
    │
Read release_criteria.yaml
    │
For each criterion:
    resolve source artifact (build.json or coverage.json)
    walk dot-notation path
    compare actual value to declared equals value
    │
    ├─ required: true, mismatch → outcome: WITHHOLD
    ├─ required: true, match    → PASS
    └─ required: false          → ADVISORY (recorded, non-blocking)
    │
All required criteria pass → outcome: RECOMMEND_RELEASE
Any required criterion fails → outcome: WITHHOLD
    │
Emit release_recommendation.json
    │
Stop
```

Not:

```
    │
Approve release
```

Never.

---

## Output: `release_recommendation.json`

The output is called `release_recommendation.json`, not `release_decision.json`.

This naming is not cosmetic. A decision requires a decision-maker. The Release Steward is not a decision-maker. It is a measurement reader that applies declared criteria.

The decision does not exist until someone signs.

```json
{
  "release_engine_version": "0.1.0",
  "generated_at": "2026-06-26T…",
  "build_id": "white-paper-rc-2",
  "publication": "White Paper",

  "inputs": {
    "build_json": "publication/build.json",
    "coverage_json": "publication/coverage.json",
    "release_criteria": "docs/builds/release_criteria.yaml"
  },

  "evaluated": {
    "build_outcome": "pass",
    "coverage_outcome": "pass",
    "blueprint_status": "ratified"
  },

  "criteria_results": [
    {
      "name": "Blueprint Ratified",
      "source": "build.json",
      "path": "blueprint_status",
      "expected": "ratified",
      "actual": "ratified",
      "required": true,
      "status": "PASS"
    },
    {
      "name": "Build Pass",
      "source": "build.json",
      "path": "outcome",
      "expected": "pass",
      "actual": "pass",
      "required": true,
      "status": "PASS"
    },
    {
      "name": "Coverage Pass",
      "source": "coverage.json",
      "path": "outcome",
      "expected": "pass",
      "actual": "pass",
      "required": true,
      "status": "PASS"
    },
    {
      "name": "No Coverage Failures",
      "source": "coverage.json",
      "path": "summary.fail",
      "expected": 0,
      "actual": 0,
      "required": true,
      "status": "PASS"
    },
    {
      "name": "No Draft Artifacts",
      "source": "build.json",
      "path": "has_draft_artifacts",
      "expected": false,
      "actual": true,
      "required": false,
      "status": "ADVISORY",
      "note": "1 artifact carries status: draft — docs/papers/scf_position_paper.md"
    }
  ],

  "outcome": "RECOMMEND_RELEASE",

  "recommendation": "All mandatory release criteria satisfied. Human Steward review required before canonical publication.",

  "steward_signature": null,
  "steward_notes": null,
  "signed_at": null
}
```

### The null fields

`steward_signature`, `steward_notes`, and `signed_at` are declared in the schema and intentionally `null` on emission. They exist so that the Steward's act of signing has a defined place to land — and so that any tool reading `release_recommendation.json` can immediately distinguish between a recommended-but-unsigned and a signed release.

The Release Steward never populates these fields. That is a feature, not a limitation.

---

## CLI Interface

```
herm release [--build <path>] [--coverage <path>] [--criteria <path>] [--output <dir>] [--verbose]
```

| Flag | Default | Notes |
|------|---------|-------|
| `--build` | `publication/build.json` | Path to build.json |
| `--coverage` | `publication/coverage.json` | Path to coverage.json |
| `--criteria` | `docs/builds/release_criteria.yaml` | Path to release criteria |
| `--output` | `publication/` | Directory for release_recommendation.json |
| `--verbose` | off | Print per-criterion evaluation detail |

### Expected stdout

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  herm release  white-paper-rc-2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Reading build.json...          PASS
  Reading coverage.json...       PASS
  Reading release criteria...    PASS  [4 required, 1 advisory]
  Evaluating criteria...

  ✓  Blueprint Ratified
  ✓  Build Pass
  ✓  Coverage Pass
  ✓  No Coverage Failures
  ·  No Draft Artifacts  [advisory — docs/papers/scf_position_paper.md]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Recommendation:
      RECOMMEND_RELEASE

  Release Steward Recommendation written.
  Awaiting human signature.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

When outcome is `WITHHOLD`:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✓  Blueprint Ratified
  ✓  Build Pass
  ✗  Coverage Pass
       Expected: pass
       Actual:   warn  (2 unresolved section requirements)
  ✗  No Coverage Failures
       Expected: 0
       Actual:   2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Recommendation:
      WITHHOLD

  2 required criteria not satisfied.
  Address the flagged items and re-run herm coverage before re-attempting.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Exit codes: `0` for RECOMMEND_RELEASE, `1` for WITHHOLD, `2` for error (missing input, malformed file).

---

## Failure Conditions

```
Condition                                           Outcome   Exit
───────────────────────────────────────────────────────────────────
build.json not found                                ERROR       2
coverage.json not found                             ERROR       2
release_criteria.yaml not found                     ERROR       2
Any input file malformed                            ERROR       2
Any mandatory criterion unmet                       WITHHOLD    1
All mandatory criteria met, advisory items present  RECOMMEND   0
All criteria satisfied                              RECOMMEND   0
```

The Release Steward never invents evidence. It never relaxes a mandatory criterion. It never promotes an advisory to mandatory or demotes a mandatory to advisory. Its job is to read, evaluate, and report.

---

## New Ontology

None. `herm release` introduces no new database tables, no new canonical objects, no new schema.

`release_recommendation.json` is a compiler output — a disposable projection, the same character as `build.json` and `coverage.json`. It is not stored in the constitutional database.

The `release_criteria.yaml` file is a new artifact type, but it is configuration, not ontology. It is a policy declaration. It does not require a new database table.

---

## The Constitutional Boundary

The Release Steward implements a constitutional boundary in code.

Most software systems blur this line: machine decides, human clicks approve. The approval is theatrical — the decision has already been made. Hermeneia inverts this. The machine measures everything measurable and produces the clearest possible summary of what it found. Then it stops. The human receives a complete picture and makes a genuine decision.

This is not a UX consideration. It is an architectural commitment about where accountability lives.

The `steward_signature: null` field is the boundary rendered in JSON.

---

## What v0.1 Defers

| Deferred | Why | Future sprint |
|----------|-----|---------------|
| Multiple release profiles (draft, RC, canonical) | Requires criteria file versioning | After v0.1 stable |
| Signing ceremony (interactive Steward sign-off) | Out of scope for CLI v0.1 | Sprint 005 or later |
| Release history log | Requires Preservation Layer | Sprint 005 |
| Differential release (what changed since last recommendation) | Requires build.json history | After Preservation Layer |

---

## Composability

`herm release` is a standalone tool. It reads `build.json` and `coverage.json` but does not call `herm build` or `herm coverage`. A future orchestration command may chain all three — but the tools must remain independently useful before they are composed.

The full chain, when it exists:

```
herm build && herm coverage && herm release
```

Each step produces its own artifact. Each artifact is independently inspectable. No step consumes another step's process — only its output.

---

## Why This Sprint Matters

Build and Coverage are engineering infrastructure. Release Steward is where the engineering becomes constitutional.

A system that builds and measures but never demands a human decision is a system that has quietly delegated authority to automation. Hermeneia refuses that delegation — not because automation cannot measure well, but because the act of declaring a work ready for publication is an act of taking responsibility. Automation cannot take responsibility. It can only inform the person who does.

The empty `steward_signature` field is not a TODO. It is a design principle.
