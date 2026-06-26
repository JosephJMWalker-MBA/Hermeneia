# Sprint 005 — Preservation Layer Specification
**herm preserve v0.1**  
**Status:** Ratified for Implementation  
**Date:** 2026-06-26  
**Steward Decision:** Ratified — two distinct constitutional responsibilities, no new ontology, deterministic engineering

---

## Purpose

The Preservation Layer exists to ensure that understanding can be responsibly reconstructed and responsibly continued across time.

This is not backup software. Backup software preserves bytes. The Preservation Layer preserves the conditions under which understanding can continue.

---

## The Two Responsibilities

Preservation has exactly two constitutional responsibilities. They are not variations of the same task. They answer different questions. They look in different directions.

### Responsibility 1 — Reconstruction

**Question:** Can I prove how this understanding came to exist?

Reconstruction is backward-facing. It verifies lineage, integrity, and provenance. Given a published artifact, a future steward should be able to retrace the complete chain:

```
Corpus
    ↓
Blueprint
    ↓
Evidence artifacts (tagged, hashed)
    ↓
Build record (build.json)
    ↓
Coverage record (coverage.json)
    ↓
Release recommendation (release_recommendation.json)
    ↓
Steward signature
```

Nothing in this chain is reconstructed from memory. Every step is traceable to a declared artifact with a declared hash. Reconstruction succeeds if — and only if — the lineage can be verified without inference.

Reconstruction corresponds to recovering `U(n)` in the governing equation. It answers: what was the understanding at the time of publication?

### Responsibility 2 — Continuation

**Question:** Can another steward responsibly continue this investigation?

Continuation is forward-facing. It is not replaying history. It is beginning the next edition. A future steward — someone who was not present for any previous decision — must be able to:

1. Understand the current intent hypothesis (what reading of the corpus drove the Blueprint)
2. Read the current Blueprint and understand its obligations
3. Know which questions are open and which are resolved
4. Know what constitutional commitments have been made (StewardDecisions, ratification states)
5. Resume investigation without inadvertently violating the constitutional lineage

Continuation corresponds to preparing `R(...)` so that someone else can produce `U(n+1)`. It answers: what must survive for the evolution of understanding to continue?

---

## What Distinguishes Hermeneia from Backup Software

| Backup | Preservation |
|--------|-------------|
| Preserves bytes | Preserves the conditions for understanding |
| Restores a state | Enables continuation of an investigation |
| Customer: same system | Customer: a future steward |
| Succeeds if files are intact | Succeeds if investigation is continuable |
| No constitutional concept | Preserves constitutional lineage |

---

## The Minimum Viable Preservation Set

The smallest set of artifacts required for another steward to responsibly continue the investigation:

```
Ratified Blueprint
    +
Source Corpus (or verifiable reference to it)
    +
Evidence Trail (tagged source artifacts, hashed)
    +
Publication Lineage (build.json, coverage.json, release_recommendation.json)
    +
Steward Decisions (ratification records, StewardDecision log)
    +
Intent Hypothesis (the reading that made the Blueprint what it is)
    =
Continuable Investigation
```

Every item on this list is already produced by the existing pipeline. Preservation does not create new content. It assembles, verifies, and packages what already exists — with a verification pass that confirms no artifact has been silently altered.

---

## Preservation Invariants

**Invariant 1 — Preservation never creates new understanding.**  
The Preservation Layer assembles and verifies. It does not interpret, revise, or supplement. If a preserved artifact is missing content, the preservation report says so. It does not fill the gap.

**Invariant 2 — Every preserved artifact has a hash.**  
No artifact enters the preservation package without a recorded SHA-256 hash. A future steward must be able to verify every artifact independently of the preservation system itself.

**Invariant 3 — Reconstruction and continuation are separately verifiable.**  
The preservation package must contain enough to verify lineage (Reconstruction) even if continuation is not yet possible. These responsibilities are independent. Partial preservation is permitted; it must be labeled.

**Invariant 4 — Preservation never modifies preserved artifacts.**  
The package may include annotations, indexes, and verification records. It may not amend, correct, or supplement any artifact it preserves. The artifacts are what they are.

**Invariant 5 — The customer is a future steward, not the current system.**  
Every output must be legible to someone who has never seen this system. This rules out internal IDs as sole identifiers, format assumptions without schemas, and any artifact that requires Hermeneia to be running in order to read.

---

## Inputs

```
build.json                       (publication/build.json)
    +
coverage.json                    (publication/coverage.json)
    +
release_recommendation.json      (publication/release_recommendation.json)
    +
compile manifest                 (path from build.json)
    +
Blueprint                        (path from manifest)
    +
source artifacts                 (paths from manifest, hashed at build time)
```

The Preservation Layer reads the full pipeline output. It does not re-run any stage. It trusts declared hashes and verifies them.

---

## Outputs

### `preservation_package/` directory

```
preservation_package/
    manifest.json           — index of all preserved artifacts with hashes
    LINEAGE.md              — human-readable reconstruction chain
    CONTINUATION.md         — human-readable continuation guide
    verification.json       — hash verification results for all artifacts
    artifacts/
        blueprint.md        — copy of ratified Blueprint
        build.json          — copy of build record
        coverage.json       — copy of coverage record
        release_recommendation.json
        [source artifacts]  — copies of all declared source artifacts
```

### `manifest.json`

The machine-readable index. Every artifact has:
- `path` — original path within the project
- `sha256_at_preservation` — hash at time of preservation
- `sha256_at_build` — hash recorded in build.json (for drift detection)
- `hash_match` — boolean: do they agree?

### `LINEAGE.md`

Human-readable. No Hermeneia required to read it. Walks the reconstruction chain step by step. Any future reader — with no tooling beyond a text editor — should be able to follow the chain from corpus to signature.

### `CONTINUATION.md`

Human-readable. Written for a steward who arrives in the future with no prior context. Answers:

1. What investigation is this?
2. What is the current intent hypothesis?
3. What does the Blueprint commit to?
4. What questions are open?
5. What has the Steward decided, and why?
6. What is the next natural step?

This document is not generated by LLM inference. It is assembled from ratified, declared content: the Blueprint intent hypothesis, StewardDecisions, open research hypotheses, and the current ratification state. The structure is templated; the content is sourced from authoritative artifacts.

---

## CLI Interface

```
herm preserve [--build <path>] [--output <dir>] [--verbose]
```

| Flag | Default | Notes |
|------|---------|-------|
| `--build` | `publication/build.json` | Entry point; everything else is resolved from this |
| `--output` | `preservation/` | Directory for preservation package |
| `--verbose` | off | Print per-artifact verification detail |

### Expected stdout

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  herm preserve  white-paper-rc-2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Loading build record...        PASS
  Loading pipeline outputs...    PASS  [3 artifacts]
  Loading source artifacts...    PASS  [10 artifacts]
  Verifying hashes...            PASS  [13/13 match]
  Assembling LINEAGE.md...       PASS
  Assembling CONTINUATION.md...  PASS
  Writing preservation package   PASS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Preservation complete.

    13 artifacts preserved
    0 hash mismatches
    Reconstruction chain: verified
    Continuation guide: assembled

  preservation/ written.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If any hash mismatches are found:

```
  Verifying hashes...            WARN  [1 mismatch]
    → docs/research/experiment_001_english.md
      at build:   a3f7...
      at present: 9c2b...
      Artifact has been modified since build. Preservation halted.
```

Hash mismatch is not a warning. It is a halt. A preservation package that contains a silently modified artifact is worse than no preservation package — it creates false confidence.

---

## Failure Conditions

```
Condition                                           Outcome   Exit
───────────────────────────────────────────────────────────────────
build.json not found                                FAIL        1
Pipeline output not found                           FAIL        1
Source artifact not found at declared path          FAIL        1
Hash mismatch (artifact modified since build)       HALT        1
Blueprint not ratified                              FAIL        1
Manifest missing required field                     FAIL        1
```

Preservation never proceeds past a hash mismatch. The preservation package is either complete and verified, or it is not written.

---

## New Ontology

None. `herm preserve` introduces no new database tables, no new canonical objects, no new schema.

`LINEAGE.md` and `CONTINUATION.md` are assembled from existing ratified content. They are compiler outputs — structured views of what already exists. They do not create new canonical facts.

---

## What v0.1 Defers

| Deferred | Why | Future |
|----------|-----|--------|
| Cryptographic signing of preservation package | Requires key infrastructure | Post v1.0 |
| Remote / offsite preservation targets | Scope: v0.1 is local | Future sprint |
| Automated continuation quality check | Requires investigator review | Human-in-loop by design |
| Differential preservation (what changed since last package) | Requires preservation history | After first package exists |

---

## Why This Sprint Matters

Every previous sprint served today's investigator, today's publication, today's release.

Sprint 005 serves the future steward.

That is a different kind of customer. A future steward may arrive years from now, with no access to the people who made these decisions, no memory of the conversations that shaped the investigation, and no way to ask questions. What they have is what was preserved. The Preservation Layer determines whether that is enough.

The governing equation frames this precisely. Reconstruction recovers `U(n)`. Continuation prepares `R(...)` so that `U(n+1)` is possible. An investigation that cannot be continued is not an investigation — it is a record. Hermeneia is not trying to produce records. It is trying to produce understanding that evolves.

Preservation is therefore not the last step. It is the step that makes all future steps possible.

---

## The Complete Chain

When Sprint 005 is complete, the full command sequence is:

```
herm build && herm coverage && herm release && herm preserve
```

Producing:

```
publication/
    build.json
    coverage.json
    release_recommendation.json

preservation/
    manifest.json
    LINEAGE.md
    CONTINUATION.md
    verification.json
    artifacts/
        ...
```

The machine has done everything it can. Understanding can now be reconstructed. The investigation can be continued. A future steward has what they need.

What the machine cannot do — what it has never tried to do — is make the investigation matter. That has always been the investigator's responsibility.
