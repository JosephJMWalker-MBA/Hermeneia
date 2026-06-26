# Hermeneia Infrastructure Engineering Track

**Status:** Non-authoritative infrastructure work plan  
**Authority:** Implementation planning only  
**Scope:** Build system, preservation, release engineering, and packaging

## Mission

Build infrastructure that serves constitutional lineage.

## Standing Question

Before every infrastructure proposal, ask:

> Does this make Hermeneia easier to trust, easier to reproduce, easier to
> preserve, or easier to steward?

If the answer is no to all four, the proposal probably belongs somewhere else,
often the cognitive engineering track. Infrastructure should optimize the
system's trustworthiness, reproducibility, preservation, and stewardship
surface without redesigning the methodology.

## Purpose

This document defines the infrastructure lane for Hermeneia.

The lane exists to make the project durable, reproducible, verifiable, and
installable without changing Hermeneia's ontology or constitutional behavior.

It is deliberately implementation-adjacent:

- close enough to code to guide engineering;
- restrained enough not to become architecture;
- explicit enough to keep build, preservation, release, and packaging work from
  drifting into epistemic authority.

## Authority Boundary

This document does not ratify:

- a new canonical object;
- a new epistemic class;
- a new pipeline stage;
- a new storage format;
- a new CLI command;
- a new release status;
- a package distribution policy; or
- a constitutional invariant.

All infrastructure work remains subordinate to:

1. [`00_Constitution.md`](00_Constitution.md);
2. [`01_Authority_Index.md`](01_Authority_Index.md);
3. ratified amendments in [`amendments/`](amendments/);
4. [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md);
5. active ADRs;
6. active implementation specifications; and
7. the active `.herm` storage specification.

If infrastructure needs a new authority, it must say so and stop before code.

## Operating Principle

```text
Infrastructure makes constitutional truth reproducible.
It does not create constitutional truth.
```

Infrastructure may compile, verify, package, copy, sign, and report. It may not
invent ontology, weaken invariants, select meaning, ratify artifacts, or make a
storage location authoritative.

## Engineering Philosophy

Infrastructure exists to make constitutional truth:

- repeatable;
- verifiable;
- portable; and
- durable.

Infrastructure never determines constitutional truth.

Automation may measure.

Automation may verify.

Automation may package.

Automation may preserve.

Automation may not decide.

Every infrastructure improvement should reduce operational friction without
reducing epistemic discipline.

## Lane Map

```text
Build System
    Compile artifacts from ratified inputs
    Measure coverage
    Produce release decision materials

Preservation
    Verify .herm
    Export archives
    Restore archives
    Check integrity and future compatibility

Release Engineering
    Define RC semantics
    Sign steward-authorized releases
    Prove reproducibility
    Verify release archives

Packaging
    pip package
    Homebrew formula
    Docker image
    Release bundles
```

These are infrastructure responsibilities, not cognitive responsibilities.

## Track 1: Build System

### Current Evidence

The white paper build artifacts already demonstrate a pattern:

```text
white_paper.compile.yaml
    -> white_paper_coverage_report.md
    -> white_paper_rc_log.md
    -> white_paper_release_decision.md
    -> rendered paper
```

This pattern should be generalized before it is automated.

### Proposed Surface

```text
herm build <build-manifest>
```

Proposed output set:

```text
builds/<build-id>/
    compile_manifest.yaml
    coverage_report.md
    rc_log.md
    release_decision.md
    artifacts/
```

### Responsibilities

- Read a declared build manifest.
- Identify ratified and non-ratified inputs.
- Produce a compile manifest.
- Produce or update a coverage report.
- Preserve release-candidate history.
- Prepare a release decision artifact for human stewardship.
- Keep the rendered artifact separate from the decision that authorizes it.

### Non-Responsibilities

- Do not ratify the artifact.
- Do not choose meaning.
- Do not mutate source evidence.
- Do not rewrite prior release candidates.
- Do not declare "canonical" without a human steward decision.

### First Design Questions

1. What is the minimum generic build manifest schema?
2. Which build artifacts are required for every publication?
3. What does `canonical artifact` mean operationally when the authority remains
   a human release decision?
4. Can coverage be deterministic before Critic output is fully canonical?
5. How are build artifacts preserved without making them new ontology?

## Track 2: Preservation

### Current Evidence

[`Preservation_Layer_Design.md`](Preservation_Layer_Design.md) is the baseline.

It establishes:

- `.herm` remains the only authoritative portable artifact;
- preservation envelopes are verification aids;
- backup targets never become authoritative;
- Source-Complete restore is blocked until source-byte storage is resolved; and
- preservation is infrastructure, not a pipeline stage.

### Proposed Surfaces

```text
herm preserve verify <bundle.herm | archive>
herm preserve export <bundle.herm | hermeneia.db> --out <archive-dir>
herm preserve restore <archive> --to <destination>
```

### Responsibilities

- Verify `.herm` shape.
- Verify SQLite integrity and foreign keys.
- Verify immutable triggers.
- Verify checksums.
- Verify lineage completeness.
- Export without changing authority.
- Restore without mutating the source archive.
- Report completeness levels: Corpus-Complete, Source-Complete,
  Build-Complete, Target-Replicated.

### Non-Responsibilities

- Do not create a competing authoritative archive format.
- Do not repair broken lineage.
- Do not run migrations during verification.
- Do not claim Source-Complete status without original source bytes.
- Do not make GitHub, S3, Dropbox, a USB drive, or any target authoritative.

### First Design Questions

1. Should source bytes live inside `.herm` or in a preservation envelope?
2. What hash-tree format should be stable for decades?
3. Which schema versions are readable, restorable, or migration-required?
4. Which verification failures are fatal versus warning-level?
5. What target adapters belong in v1?

## Track 3: Release Engineering

### Purpose

Release engineering defines how Hermeneia moves from reproducible build outputs
to steward-authorized public artifacts.

It answers questions such as:

- What does RC-1 mean?
- What does canonical release mean?
- How does a release point back to constitutional authority?
- How does a user verify that an archive is the one the steward approved?
- How do releases remain reproducible after dependencies change?

### Proposed Release Sequence

```text
Build manifest
    -> rendered artifact
    -> coverage report
    -> release candidate log
    -> steward release decision
    -> signed release bundle
    -> verification report
```

### Responsibilities

- Define release-candidate semantics.
- Keep release candidates immutable.
- Preserve why one candidate superseded another.
- Produce signed release bundles.
- Record checksums.
- Verify release archives.
- Document reproducibility inputs.

### Non-Responsibilities

- Do not let automation authorize release.
- Do not replace Steward judgment with coverage.
- Do not collapse "passes checks" into "canonical."
- Do not delete failed release candidates.

### First Design Questions

1. What statuses are allowed for release candidates?
2. What makes a release candidate superseded rather than failed?
3. What exactly is signed: artifact, `.herm`, preservation envelope, or all of
   them?
4. Which signing mechanism is appropriate for local, public, and institutional
   releases?
5. What minimum evidence must a release verification report include?

## Track 4: Packaging

### Purpose

Packaging makes Hermeneia installable without changing what Hermeneia is.

Packaging should be boring, reproducible, and downstream from release
engineering.

### Proposed Targets

```text
pip install hermeneia
brew install hermeneia
docker run hermeneia
release bundle download
```

### Responsibilities

- Package the CLI and runtime dependencies.
- Produce reproducible build artifacts where practical.
- Document supported platforms.
- Separate development install from user install.
- Verify packaged commands against the same test suite.
- Include version and provenance metadata.

### Non-Responsibilities

- Do not change constitutional behavior for packaging convenience.
- Do not hide required runtime dependencies.
- Do not bundle secrets.
- Do not make one packaging target the authoritative distribution.
- Do not release packages before release engineering can verify them.

### First Design Questions

1. What is the supported Python version range?
2. Which optional provider SDKs are extras?
3. Should local model support be optional packaging metadata?
4. What does a Docker image include and exclude?
5. What release bundle is sufficient for offline restoration and verification?

## Sequencing

Infrastructure Sprint 001 is tracked by
[`Infrastructure_Gap_Analysis_v1.md`](Infrastructure_Gap_Analysis_v1.md).

The safest order is:

1. Document the generic build artifact convention.
2. Design `herm build` without implementing it.
3. Finish preservation verification design.
4. Implement read-only verification primitives.
5. Define release-candidate semantics.
6. Add signing and release verification.
7. Package only after releases are verifiable.

Packaging comes last because distribution multiplies any ambiguity still
present in build, preservation, or release semantics.

## Verification Discipline

Infrastructure work should end with explicit evidence:

- exact command run;
- exact artifact generated;
- exact checksum or digest where relevant;
- exact test result;
- exact verification report;
- explicit statement of what was not verified; and
- explicit boundary between automation result and human stewardship.

If an infrastructure command cannot produce this evidence, the command is not
ready.

## Infrastructure Engineer Role

The infrastructure engineer is a discipline role, not a tool identity.

Appropriate infrastructure engineering work:

- write implementation-adjacent design documents;
- generalize existing build artifacts into repeatable conventions;
- implement deterministic verification helpers after design is stable;
- add focused tests for build, preservation, release, and packaging behavior;
- inspect packaging metadata and propose reproducibility fixes;
- produce release checklists and verification reports; and
- keep every change subordinate to ratified authority.

Inappropriate infrastructure engineering work:

- invent new ontology;
- promote provisional documents to authority;
- change constitutional invariants;
- declare releases canonical;
- make storage locations authoritative;
- add hidden state to satisfy packaging convenience; or
- turn aspiration into specification without explicit approval.

## Success Criteria

This lane succeeds when a future steward can:

1. build a declared artifact from declared inputs;
2. inspect the coverage and release decision;
3. verify the `.herm` corpus and preservation envelope;
4. restore the corpus without changing canonical IDs;
5. verify the release archive against signed checksums;
6. install Hermeneia from a package target; and
7. distinguish every automated check from every human judgment.

That is infrastructure in service of constitutional lineage.
