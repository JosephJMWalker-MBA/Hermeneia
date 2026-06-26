# Hermeneia Authority Index

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-19  
**Ratified by:** Primary Human Steward  
**Authority:** Subordinate only to the Constitution

---

## Purpose

This index is the canonical routing table for Hermeneia authority.

It identifies active authorities, records supersession without erasing history,
and prevents filenames, stale references, or implementation age from being
mistaken for authority.

---

## Authority Hierarchy

Conflicts shall be resolved in this order:

1. [`00_Constitution.md`](00_Constitution.md)
2. this Authority Index
3. ratified documents in [`amendments/`](amendments/)
4. [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md)
5. active Architecture Decision Records
6. active implementation documents and compiler specifications
7. code
8. generated artifacts

No lower layer may contradict a higher layer.

---

## Authority Status

Every indexed authority has one status:

| Status | Meaning |
|---|---|
| `ACTIVE` | Currently authoritative within its scope |
| `SUPERSEDED` | Replaced within a stated scope by a later authority |
| `RETIRED` | Preserved historically but no longer governs implementation |
| `DRAFT` | Proposed and non-authoritative |

Supersession is scoped. A partially superseded document remains active for all
unaffected decisions.

---

## Canonical Authority Records

The conceptual authority record is:

```text
AuthorityEntry
    id
    object_id
    status
```

The conceptual supersession record is:

```text
SupersessionRelation
    old_id
    new_id
    reason
    ratified_at
```

These records define constitutional governance. Their persistent schema shall
be implemented only through a separately ratified storage change.

---

## Active Constitutional Authorities

| ID | Document | Status | Scope |
|---|---|---|---|
| CONST-001 | [`00_Constitution.md`](00_Constitution.md) | ACTIVE | Highest governing law |
| AUTH-001 | [`01_Authority_Index.md`](01_Authority_Index.md) | ACTIVE | Authority routing and supersession |
| LAW-001 | [`02_Constitutional_Invariants.md`](02_Constitutional_Invariants.md) | ACTIVE | Executable constitutional obligations |
| CA-0001 | [`amendments/CA-0001-forensic-evidence-and-identity.md`](amendments/CA-0001-forensic-evidence-and-identity.md) | ACTIVE | Evidence chain and occurrence identity |
| CA-0002 | [`amendments/CA-0002-epistemic-classification.md`](amendments/CA-0002-epistemic-classification.md) | ACTIVE | Epistemic classification |
| CA-0003 | [`amendments/CA-0003-architect-plan-contract.md`](amendments/CA-0003-architect-plan-contract.md) | ACTIVE | ArchitectPlan semantic contract |
| CA-0004 | [`amendments/CA-0004-auditability-and-monotonic-governance.md`](amendments/CA-0004-auditability-and-monotonic-governance.md) | ACTIVE | Auditability and monotonic governance |

---

## Active Implementation Authorities

These documents remain authoritative only where they do not conflict with the
constitutional authorities above:

| Document | Scope |
|---|---|
| [`05_Architecture.md`](05_Architecture.md) | System architecture |
| [`06_Ontology.md`](06_Ontology.md) | Ontology |
| [`07_First_Principles.md`](07_First_Principles.md) | First principles |
| [`15_Storage.md`](15_Storage.md) | Singular `.herm` storage specification |
| [`16_Observation_Compiler.md`](16_Observation_Compiler.md) | Observation compiler |
| [`specs/`](specs/) | Compiler and component specifications |

The Architecture Decision Record index is
[`adr/ADR_README.md`](adr/ADR_README.md).

---

## Supersession Register

| Earlier authority | Status | Successor | Superseded scope | Reason | Ratified |
|---|---|---|---|---|---|
| [`03_Constitution.md`](03_Constitution.md) | SUPERSEDED | CONST-001 | Entire governing role | Incorporated and expanded into the canonical Constitution | 2026-06-19 |
| [`04_Invariants.md`](04_Invariants.md) | SUPERSEDED | LAW-001 | Active constitutional invariant index | Replaced by falsifiable constitutional law | 2026-06-19 |
| [`../RATIFICATION.md`](../RATIFICATION.md) | SUPERSEDED IN PART | CONST-001, AUTH-001 | Governance requiring every constitutional change to be an ADR | Constitution and amendments now govern constitutional change | 2026-06-19 |
| [`adr/ADR-0006-observation-definition.md`](adr/ADR-0006-observation-definition.md) | SUPERSEDED IN PART | CA-0001 | Parser output as Observation; prior identity rule | SourceExtraction now preserves parser output and Observation identity is occurrence-based | 2026-06-19 |
| [`adr/ADR-0012-atomic-provenance-unit.md`](adr/ADR-0012-atomic-provenance-unit.md) | SUPERSEDED IN PART | CA-0001 | Provenance as a competing sentence object and prior identity coupling | Provenance is orthogonal lineage and custody metadata | 2026-06-19 |
| [`adr/ADR-0013-provenance-granularity.md`](adr/ADR-0013-provenance-granularity.md) | SUPERSEDED IN PART | CA-0001 | Prior location and identity rule | Occurrence identity derives from source hash, source locator, and raw text | 2026-06-19 |
| [`adr/ADR-0024-canonical-object-list.md`](adr/ADR-0024-canonical-object-list.md) | SUPERSEDED IN PART | CA-0001, CA-0002 | Canonical list omitting SourceDocument, SourceExtraction, and the complete epistemic stack | Constitutional evidence and epistemic classes now govern | 2026-06-19 |
| [`adr/ADR-0036-narrative-blueprint.md`](adr/ADR-0036-narrative-blueprint.md) | SUPERSEDED IN PART | CA-0003 | NarrativeBlueprint as the direct Artist contract | ArchitectPlan is the canonical compiled semantic contract | 2026-06-19 |
| [`adr/ADR-0040-architect-artist-interaction.md`](adr/ADR-0040-architect-artist-interaction.md) | SUPERSEDED IN PART | CA-0003 | Direct NarrativeBlueprint-to-Artist interface | Artist consumes ArchitectPlan under ExpressionProfile constraints | 2026-06-19 |

The original files remain immutable historical records. The notices placed in
those files are index annotations, not rewrites of their decisions.

---

## Historical Sources

The following remain inspectable as constitutional history:

- [`03_Constitution.md`](03_Constitution.md)
- [`04_Invariants.md`](04_Invariants.md)
- [`../RATIFICATION.md`](../RATIFICATION.md)
- all ADRs marked wholly or partially superseded above

They shall not be deleted merely because their authority has changed.

---

## Reference Rule

New documents and code comments shall cite the active path listed in this
index. Broken, case-mismatched, or obsolete filenames do not convey authority.
