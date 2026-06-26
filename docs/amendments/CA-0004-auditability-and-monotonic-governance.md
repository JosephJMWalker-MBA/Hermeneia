# CA-0004 — Auditability and Monotonic Governance

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-19  
**Ratified by:** Primary Human Steward

---

## Amendment I — Auditability Over Determinism

Deterministic objects shall be reproducible from immutable ancestors.

Nondeterministic objects shall preserve the complete inputs, provider identity,
model identity, configuration, execution metadata, output, and provenance
necessary for independent audit and evaluation.

Provider evolution does not excuse a missing audit record. Byte-for-byte
reproduction is not required where the producing system is inherently
stochastic or externally mutable.

---

## Amendment II — Monotonic Knowledge

Hermeneia shall append new objects and relations rather than mutate existing
ones.

A new parser creates a new SourceExtraction. A new Perspective creates a new
Interpretation. A new Artist invocation creates a new RenderedNarrative. A new
Critic invocation creates a new CriticReport.

Prior objects remain inspectable.

---

## Amendment III — Constitutional Governance

The Constitution obeys its own append-only rule.

Authority status shall be represented conceptually by:

```text
AuthorityEntry
    id
    object_id
    status
```

where status is one of:

```text
ACTIVE
SUPERSEDED
RETIRED
DRAFT
```

Supersession shall be represented conceptually by:

```text
SupersessionRelation
    old_id
    new_id
    reason
    ratified_at
```

The original authority remains immutable. The relation records that a later
authority governs a specified scope.

---

## Amendment IV — Executable Law

Constitutional tests are executable law.

Implementation compliance requires the executable invariants to pass. Tests
operationalize constitutional guarantees; they do not possess authority to
weaken or reinterpret them.

