# Infrastructure Gap Analysis v1.0

**Status:** Infrastructure Sprint 001 deliverable  
**Authority:** Non-authoritative analysis  
**Scope:** Build discipline, preservation verification, release engineering,
packaging recommendations, and reproducibility reporting

## Mission

Build infrastructure that serves constitutional lineage.

Success is measured by:

- reproducibility;
- durability;
- verification; and
- operational simplicity.

Success is not measured by new capabilities.

## Standing Question

Every Sprint 001 proposal should answer:

> Does this make Hermeneia easier to trust, easier to reproduce, easier to
> preserve, or easier to steward?

If the answer is no to all four, the work is probably outside this
infrastructure sprint.

## Authority Boundary

This document does not ratify:

- new ontology;
- new pipeline stages;
- renamed constitutional objects;
- new storage authority;
- changed Steward authority; or
- new canonical artifact types.

If any infrastructure task requires one of those changes, implementation must
stop and produce an ADR or design note before code.

## Sprint Priority

```text
P1 Build System
P2 Preservation Verification
P3 Release Engineering
P4 Packaging Research
P5 Reproducibility Report
```

The first real deliverable is this gap analysis. Code comes later.

## Summary Table

| Capability | Current | Target | Blocker | Authority Required |
|---|---|---|---|---|
| Build | Partial white-paper-specific artifacts | Generic `herm build` discipline | Generic manifest schema and build artifact convention | No |
| Preservation Verify | Draft design only | Read-only CLI verifier | Verification rule specification | No |
| Restore | None | Planned restore workflow | Original source bytes are not yet resolved inside or beside `.herm` | Yes |
| Release | Manual white-paper RC log and release decision | Automated release-candidate discipline with steward decision handoff | Release semantics and signing scope | No |
| Packaging | Basic Python package metadata | Multi-platform recommendations and later packages | Packaging policy and platform matrix | No |
| Reproducibility Report | Partial metadata in build docs and runtime records | Generic reproducibility report for every investigation build | Required field set and source of each field | No |

## P1: Build System

### Current

The white paper has a manual build convention:

```text
docs/builds/white_paper.compile.yaml
docs/builds/white_paper_coverage_report.md
docs/builds/white_paper_rc_log.md
docs/builds/white_paper_release_decision.md
```

The compile manifest explicitly states that it is a build recipe, not
canonical knowledge. That is the right boundary.

There is no generic `herm build` command today.

### Target

Generalize the white-paper pattern into a build discipline usable by any
investigation:

```text
Blueprint
    -> Compile Manifest
    -> Coverage Analysis
    -> Critic
    -> Release Decision
    -> Canonical Artifact
```

Proposed future command:

```text
herm build <build-manifest>
```

Expected outputs:

```text
compile_manifest.yaml
coverage_report.md
release_decision.md
build_metadata.json
```

The target is generic build infrastructure, not a white-paper-specific script.

### Gap

The repo has the example artifacts but not the generalized rules:

- no generic build manifest schema;
- no standard output directory convention;
- no generic coverage report schema;
- no generic build metadata schema;
- no machine-readable boundary between build measurement and Steward decision;
- no CLI surface.

### Blocker

None at the constitutional level, as long as build artifacts remain
non-canonical infrastructure and Steward authority remains human.

### Next Design Work

1. Define the minimum generic build manifest.
2. Define required build outputs.
3. Define `build_metadata.json`.
4. Define how coverage analysis records PASS, WARNING, and FAIL without
   replacing Critic or Steward judgment.
5. Define when a rendered artifact may be called canonical: after Steward
   release decision, not after automation.

## P2: Preservation Verification

### Current

[`Preservation_Layer_Design.md`](Preservation_Layer_Design.md) is the baseline.

The active storage specification defines the authoritative `.herm` shape:

```text
bundle.herm/
    context.json
    hermeneia.db
```

The CLI has no `herm preserve verify` command today.

### Target

Build the verifier before export or restore.

Proposed future command:

```text
herm preserve verify <investigation.herm>
```

Checks:

- hashes;
- lineage;
- schema version;
- missing bytes;
- corruption;
- provenance completeness;
- `.herm` shape;
- SQLite integrity;
- foreign keys;
- immutable triggers; and
- source-byte completeness status.

### Gap

The design exists, but executable verification rules do not.

Missing pieces:

- hash-tree format;
- read-only database open discipline;
- schema compatibility table;
- trigger-presence checklist;
- lineage completeness query set;
- provenance completeness query set;
- missing-source-byte detection;
- fatal versus warning classification;
- machine-readable verification report.

### Blocker

No authority blocker for read-only verification.

Restore remains blocked by the unresolved source-byte question. Verification
can and should report the gap without solving it.

### Next Design Work

1. Define `verification_report.json`.
2. Define fatal checks versus warnings.
3. Define Source-Complete, Corpus-Complete, Build-Complete, and
   Target-Replicated verification states.
4. Define read-only SQLite verification helpers.
5. Define a no-repair rule for failed verification.

## P3: Release Engineering

### Current

The white paper has manual release engineering artifacts:

```text
white_paper_rc_log.md
white_paper_release_decision.md
```

These correctly separate measurements from Steward judgment.

There are no generic release commands today.

### Target

Build release discipline without publishing.

Proposed future command family:

```text
herm release candidate
herm release sign
herm release verify
```

No publishing in Sprint 001.

### Gap

Release semantics are not yet generalized:

- no generic RC status vocabulary;
- no release candidate directory convention;
- no signing scope;
- no release verification report;
- no standard checksum list;
- no standard link from release decision to artifact digest;
- no policy for failed versus superseded release candidates.

### Blocker

No constitutional blocker if automation only prepares, signs, and verifies
release materials. Automation must not authorize release.

### Next Design Work

1. Define RC-1, RC-2, and later candidate semantics.
2. Define allowed release statuses.
3. Define signed material scope.
4. Define release verification report fields.
5. Define how Steward release decisions reference checksums.

## P4: Packaging Research

### Current

The project has basic Python package metadata:

```text
pyproject.toml
```

It defines:

- package name `hermeneia`;
- Python requirement `>=3.11`;
- CLI entry point `herm`;
- optional provider dependencies; and
- package data for static web assets.

There is no Homebrew formula, Docker image, Windows packaging guidance, or
release bundle policy.

### Target

Produce engineering recommendations only.

Targets to research:

- `pip`;
- `brew`;
- Docker;
- Windows;
- macOS; and
- Linux.

No packaging implementation in Sprint 001.

### Gap

Missing recommendations:

- supported Python version range;
- dependency extras policy;
- provider SDK packaging policy;
- local model packaging policy;
- web/static asset packaging verification;
- platform support matrix;
- Docker inclusion/exclusion policy;
- release bundle contents;
- offline verification requirements.

### Blocker

No constitutional blocker for research.

Implementation should wait until build, preservation verification, and release
verification are better defined.

### Next Design Work

1. Produce a packaging recommendations document.
2. Identify package targets and order.
3. Define what each package must verify after install.
4. Define what must never be bundled, especially secrets.
5. Define how package metadata reports Hermeneia version and build provenance.

## P5: Reproducibility Report

### Current

Reproducibility information exists across several places:

- build manifests;
- rendered narrative execution metadata;
- provider configuration;
- Critic output;
- source hashes;
- `.herm` context;
- release decisions.

There is no generic reproducibility report today.

### Target

Every investigation build should eventually produce a reproducibility report.

Candidate fields:

- Hermeneia version;
- Provider;
- Model;
- Prompt revision;
- Blueprint;
- Critic version;
- Evaluation Functions;
- Checksums;
- Build timestamp;
- source document hashes;
- `.herm` schema version;
- build manifest digest;
- rendered artifact digest;
- release decision digest; and
- known non-reproducible external dependencies.

### Gap

Missing pieces:

- canonical field list;
- source of truth for each field;
- deterministic report ordering;
- JSON and human-readable forms;
- policy for unavailable provider metadata;
- distinction between deterministic reproduction and auditability;
- tests proving report generation does not mutate storage.

### Blocker

No constitutional blocker if the report remains an infrastructure artifact and
does not become a canonical epistemic object.

### Next Design Work

1. Define `reproducibility_report.json`.
2. Define required and optional fields.
3. Define unavailable-value semantics.
4. Define deterministic ordering and checksums.
5. Tie the report to build, preservation, and release verification outputs.

## Prohibited Work For Sprint 001

The infrastructure engineer may not:

- invent ontology;
- invent pipeline stages;
- rename constitutional objects;
- create storage authority;
- change Steward authority;
- create new canonical artifacts;
- implement restore before the source-byte question is resolved;
- publish packages before release verification exists; or
- let automation decide release authority.

If any prohibited work appears necessary:

```text
STOP
Write ADR or design note
Do not code around the authority gap
```

## Sprint 001 Deliverables

### Required

1. Infrastructure Gap Analysis v1.0.
2. Generic build manifest design.
3. Preservation verification design.
4. Release candidate semantics design.
5. Packaging recommendations.
6. Reproducibility report design.

### Not Required

- Code;
- schema changes;
- CLI implementation;
- restore;
- publishing;
- package release;
- new canonical objects; or
- constitutional amendments.

## Recommended Order

1. Build manifest design.
2. Reproducibility report design.
3. Preservation verification design.
4. Release candidate semantics.
5. Packaging recommendations.

Build and reproducibility come first because they define what preservation and
release verification must be able to prove.

## Sprint Exit Criteria

Sprint 001 is complete when a future implementation engineer can answer:

1. What files does a generic build produce?
2. Which build facts are machine-measured?
3. Which facts require Steward decision?
4. What does preservation verification check?
5. Which verification failures are fatal?
6. What does a release candidate mean?
7. What should be signed?
8. What packaging targets are recommended?
9. What must a reproducibility report contain?
10. Which tasks require new authority before code?

Until those answers exist, implementation would create operational ambiguity.
