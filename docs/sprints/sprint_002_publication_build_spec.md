# Sprint 002 — Publication Build Specification
**herm build v0.1**  
**Status:** Ratified for Implementation  
**Date:** 2026-06-26  
**Steward Decision:** Ratified — scope appropriately constrained, no ontology expansion, compiler scaffold separated from AI orchestration

---

## Purpose

`herm build` makes the answer to "why is this the current white paper?" executable.

Today that answer lives in conversations and memory. After this sprint, the answer is a reproducible build: given the same inputs, produce the same outputs, with the same provenance record, every time.

The compiler doesn't ask: *which document is newest?*  
It asks: *what is the newest ratified understanding, and how do I faithfully render it?*

---

## Build Invariants

These conditions must remain true across every future version of `herm build`. They are the constitutional axioms of the build system. Any implementation that violates them is wrong, regardless of how useful the violation seems.

**Invariant 1 — A build never changes authoritative understanding. It only renders it.**  
The build reads from the Blueprint, manifest, and source artifacts. It does not modify them. If a build reveals that the Blueprint needs revision, that revision is a constitutional act — not a build side effect.

**Invariant 2 — A build is reproducible from its manifest.**  
Given the same Blueprint, manifest, and source artifact hashes, the same build must be reproducible. Nondeterministic stages (Artist rendering) must be explicitly recorded in build.json with provider, model, and generation parameters, so that nondeterminism is auditable even when it cannot be eliminated.

**Invariant 3 — Every emitted artifact has a provenance record.**  
No anonymous outputs. build.json records the source artifact, hash, and stage that produced each output. An output without a traceable provenance record is a build failure.

**Invariant 4 — Build failure never mutates authoritative artifacts.**  
If compilation fails at any stage, the Blueprint, manifest, and source artifacts remain untouched. Partial outputs are not written. The publication directory either contains a complete build or nothing.

**Invariant 5 — Release status is descriptive, not generative.**  
The build reports readiness. It never declares canonical authority. A build that passes all checks produces a recommendation, not a decision. Only the Steward makes the release decision. build.json records that the decision is pending until the Steward signs.

---

## What This Is Not

- A PDF generator
- A document formatter
- A publishing pipeline in the editorial sense

It is a **compiler** in the engineering sense: deterministic transformation of declared inputs into declared outputs, with machine-readable provenance of every decision made along the way.

---

## Build Inputs

All inputs must be explicitly declared in the compile manifest. No hidden inputs. No directory scanning. No "whatever happens to be in the repo."

### Required inputs

| Input | Source | Notes |
|-------|--------|-------|
| Compile manifest | `--manifest <path>` or convention path | YAML; defines everything below |
| Blueprint | `manifest.blueprint` | Must have `status: ratified` |
| Source artifacts | `manifest.source_artifacts[]` | Each must exist at declared path |

### Manifest-declared inputs (already specified in existing manifest)

```yaml
build_id:           # unique identifier for this build
compiled_artifact:  # path to the target publication file
blueprint:          # path to the ratified Blueprint
blueprint_id:       # e.g. "000001"
blueprint_status:   # must be "ratified" for a release build
source_artifacts:   # list of tagged inputs
sections:           # section requirements (required_tags, required_claims)
critics:            # critic configuration
artist:             # artist provider + expression profile
```

### Allowable artifact roles

```
blueprint           — primary contract
evidence            — experiment data, observations, analysis
research-program    — hypotheses and future work
provenance-record   — methodological history
process-definition  — writing protocol
related-work        — comparative/reference material
```

No artifact may be included that is not listed in the manifest. No artifact may be excluded that is listed.

---

## Build Outputs

Every build produces exactly this directory structure:

```
publication/
    white_paper.md          # rendered publication
    coverage.md             # section coverage report
    rc_log.md               # release candidate history
    release_decision.md     # steward decision (may be pending)
    build.json              # machine-readable build provenance
```

All five files must exist for a build to be considered complete. A build that produces four of five has failed.

### build.json schema

```json
{
  "build_id": "white-paper-rc-2",
  "build_timestamp": "2026-06-26T04:00:00Z",
  "hermeneia_version": "0.1.0",
  "blueprint_id": "000001",
  "blueprint_status": "ratified",
  "manifest_path": "docs/builds/white_paper.compile.yaml",
  "manifest_hash": "<sha256>",
  "source_artifacts": [
    {
      "path": "docs/papers/blueprint_000001.md",
      "sha256": "<hash>",
      "tags": ["blueprint", "..."],
      "status": "ratified",
      "role": "primary-contract",
      "resolved": true
    }
  ],
  "stages": [
    {
      "stage": "load_manifest",
      "status": "pass",
      "elapsed_ms": 12
    }
  ],
  "coverage": {
    "sections_evaluated": 9,
    "sections_pass": 7,
    "sections_warn": 2,
    "sections_fail": 0,
    "missing_tags": [],
    "missing_claims": []
  },
  "critic": {
    "enabled": false,
    "note": "v0.1: critic pass is manual; future versions integrate programmatic critic"
  },
  "outcome": "pass",
  "release_status": "pending_steward",
  "outputs": {
    "white_paper": "publication/white_paper.md",
    "coverage": "publication/coverage.md",
    "rc_log": "publication/rc_log.md",
    "release_decision": "publication/release_decision.md",
    "build_json": "publication/build.json"
  }
}
```

`build.json` is the canonical provenance record. It is what a future steward reads to answer: *what went into this build and what decisions were made?*

---

## Build Stages

```
1. Load Manifest
   │  Read and validate the compile manifest YAML.
   │  Fail if manifest is missing, malformed, or blueprint_status ≠ ratified.
   ↓

2. Resolve Tags
   │  For each source artifact: verify file exists, compute SHA-256, extract tags.
   │  Fail if any declared artifact is missing.
   │  Fail if any required tag is not covered by any artifact.
   ↓

3. Collect Evidence
   │  Group resolved artifacts by tag.
   │  Produce a tag index: {tag → [artifact_path, ...]}
   │  No LLM. No inference. Pure resolution.
   ↓

4. Coverage Analysis
   │  For each section in manifest.sections:
   │    Check required_tags → all must appear in resolved artifacts
   │    Check required_claims → record for Critic evaluation
   │  Produce coverage.md with PASS / WARNING / FAIL per section.
   │  WARNING if required tags missing for a section.
   │  FAIL if Blueprint required claims cannot be checked at all (no artifacts).
   ↓

5. Compile Sections
   │  v0.1: copy existing compiled_artifact to publication/white_paper.md.
   │  Record which artifact was used and its hash.
   │  Future versions: drive Artist to render from Blueprint + evidence.
   ↓

6. Critic Pass
   │  v0.1: Critic pass is human-in-the-loop. Build records critic status
   │  as "manual" and notes what would be evaluated programmatically.
   │  Future versions: programmatic critic against required_claims.
   ↓

7. Steward Report
   │  Copy or generate release_decision.md with:
   │    - current RC status
   │    - coverage summary
   │    - critic status
   │    - open conditions for next RC
   │    - steward signature field (human fills in)
   ↓

8. Emit Build
      Write build.json.
      Write all outputs to publication/.
      Print summary to stdout.
      Exit 0 on pass, exit 1 on fail.
```

This is the **engineering pipeline**, not the cognitive pipeline. It serves the cognitive pipeline — it does not replace it.

---

## Build Failure Conditions

```
Condition                               Outcome     Exit
────────────────────────────────────────────────────────
Manifest file not found                 FAIL        1
Manifest YAML malformed                 FAIL        1
Blueprint not found                     FAIL        1
Blueprint status ≠ "ratified"           FAIL        1
Blueprint ID mismatch                   FAIL        1
Source artifact file not found          FAIL        1
Required tag has zero covering artifacts WARN       0
Section has uncoverable required claims WARN        0
Coverage < required (configurable)      WARN        0
Critic pass not complete                WARN        0
Steward decision pending                NOTE        0 (informational)
Output directory not writable           FAIL        1
build.json cannot be written            FAIL        1
```

Distinction:
- **FAIL**: build cannot proceed. No output emitted.
- **WARN**: build completes. Warning recorded in build.json and coverage.md.
- **NOTE**: informational. Does not affect outcome.

A build with WARNings is a valid build. It is not a release build. The steward decides whether warnings are acceptable.

---

## CLI Interface

```
herm build [--manifest <path>] [--output <dir>] [--dry-run] [--verbose]
```

| Flag | Default | Notes |
|------|---------|-------|
| `--manifest` | `docs/builds/white_paper.compile.yaml` | Path to compile manifest |
| `--output` | `publication/` | Output directory |
| `--dry-run` | off | Resolve and check; do not write outputs |
| `--verbose` | off | Print per-stage detail |

### Expected stdout (normal run)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  herm build  white-paper-rc-2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Loading manifest...            PASS
  Blueprint 000001 (ratified)    PASS
  Resolving 10 artifacts...      PASS
  Coverage analysis...           PASS  [7 PASS  2 WARN  0 FAIL]
  Compiling publication...       PASS
  Critic pass...                 MANUAL (v0.1)
  Steward report...              PENDING

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Publication Build Complete

  Outputs written to: publication/
    white_paper.md
    coverage.md
    rc_log.md
    release_decision.md
    build.json

  Build status:  PASS with 2 warnings
  Release status: Pending steward decision

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Expected stdout (failure)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  herm build  white-paper-rc-2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Loading manifest...            PASS
  Blueprint 000001 (ratified)    PASS
  Resolving 10 artifacts...      FAIL

  ERROR: artifact not found
    docs/research/experiment_003_mandarin.md

  Build aborted. No outputs written.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## What build.json Enables

`build.json` is the machine-readable answer to: *"Why is this the current white paper?"*

It enables:
- **Reproducibility**: same manifest + same artifact hashes → same build
- **Audit**: any artifact change is detectable via hash comparison
- **Coverage Engine** (Sprint 002 follow-on): reads build.json to report missing evidence before prose generation
- **Release Steward** (Sprint 003): reads build.json to generate release recommendations
- **Preservation Layer** (Sprint 004): uses build.json as the manifest for what to archive

Each later sprint consumes the previous sprint's output. This is the compiler pipeline.

---

## What v0.1 Defers

v0.1 does not implement:

| Deferred | Why | Future sprint |
|----------|-----|---------------|
| Programmatic Artist rendering | Requires Artist + Expression Profile wiring | Sprint 002 v0.2 |
| Programmatic Critic pass | Requires claim-extraction against publication text | Coverage Engine sprint |
| Multi-manifest builds | Only one publication supported | After v0.1 is stable |
| Differential builds | Detect which artifacts changed since last build | After build.json baseline exists |
| CI integration | Requires stable build.json schema first | After v0.1 ships |

v0.1 establishes the scaffold. It proves the stages are right. It produces a real build.json. Everything else builds on that.

---

## New Ontology

None. `herm build` introduces no new database tables, no new canonical objects, no new schema.

`build.json` and the `publication/` directory are compiler outputs — disposable projections, the same as a rendered narrative. They are not canonical artifacts. They are not stored in the constitutional database.

The compile manifest is already a first-class artifact (`docs/builds/white_paper.compile.yaml`). No new file format is introduced.

---

## Constitutional Compliance

| Principle | Compliance |
|-----------|------------|
| Automation may measure, verify, package, preserve | Build pipeline measures and packages only |
| Automation shall not decide | Steward decision field is left for human completion |
| Nothing emitted unless provenance can be explained | build.json records provenance of every input |
| No new ontology | Confirmed — no new tables, objects, or schema |
| Immutable evidence layer untouched | Build reads; never writes to the constitutional DB |

---

## Readiness Gate

`herm build v0.1` is ready to implement when this specification is ratified by the steward.

Implementation begins with: `hermeneia/cli/build_cmd.py` and `herm build` registration in `hermeneia/cli/main.py`.

The first test is: `herm build --manifest docs/builds/white_paper.compile.yaml --dry-run` produces no errors against the existing white paper artifacts.
