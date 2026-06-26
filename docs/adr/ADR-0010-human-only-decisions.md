# ADR-0010: Constitutionally Reserved Human-Only Decisions

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P6-001 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** Existential

---

## Context

Hermeneia is an AI-augmented system. Language models participate in generating Interpretations, Perspectives, Concept graphs, Narrative Blueprints, and entity proposals. The system is designed to maximize the epistemic value of AI assistance while preserving the authority of human stewards.

This creates a constitutional question: which decisions can AI systems make, and which decisions are constitutionally reserved for humans? Without a clear boundary, AI systems may gradually acquire effective final authority over decisions that should require human judgment — not through malice, but through the path of least resistance.

This ADR closes Q-P6-001 from `EPISTEMIC_BACKLOG.md` and defines the constitutional boundary.

---

## Decision

The following categories of decision are **constitutionally reserved for human stewards**. No AI system may have final authority over them. AI may propose, summarize, compare, or simulate — but it must not possess or exercise final constitutional authority.

**"AI may propose, summarize, compare, or simulate, but it must not possess final constitutional authority."**

---

## The Seven Constitutionally Reserved Categories

### 1. Ratification of Ontology Definitions

The formal definition of any canonical ontology object — what it is, what its fields mean, what qualifies as an instance, what does not — is a human decision. AI may propose candidate definitions. AI may enumerate edge cases. AI may perform constitutional compatibility checks. But the ratification decision — the act of writing `Status: RATIFIED` — is a human act.

This includes every ADR in the `docs/adr/` directory. Every ADR is ratified by a human steward, not by an AI system.

**Enforcement:** No ADR may carry `Status: RATIFIED` without a `Ratified by:` field identifying a human steward.

---

### 2. Acceptance or Rejection of Constitutional Amendments

Any proposal to amend a ratified decision — superseding an existing ADR, changing an ontology definition, modifying the provenance chain structure — requires human acceptance. AI may draft the superseding ADR. AI may identify constitutional conflicts and incompatibilities. But the decision to accept or reject the amendment is human.

**Enforcement:** The amendment process defined in `RATIFICATION.md` Part II requires human sign-off at each stage. No automated pipeline may declare an amendment accepted.

---

### 3. Promotion of Interpretations to Canonical Status

An Interpretation produced by an AI system (via the Architect agent or any other pipeline) begins in a staging state. Promotion to canonical status — the act of moving it from `proposed_interpretations` to canonical `interpretations` — requires human steward acceptance.

This is not a quality gate. It is a constitutional gate. The steward accepts responsibility for the canonical corpus by accepting an Interpretation into it. That responsibility cannot be delegated to an AI system.

**Enforcement:** The staging protocol in ADR-0009 implements this requirement. No row in the canonical `interpretations` table may exist without a linked AI Provenance record carrying `accepting_steward` and `acceptance_timestamp`.

---

### 4. Resolution of Epistemic Conflicts Where Multiple Valid Perspectives Exist

The Hermeneutic Field is designed to preserve genuine epistemic conflict: two valid Perspectives on the same corpus that cannot be reconciled without a value judgment. When such a conflict exists, the resolution — which Perspective is canonical, whether both are canonical, whether the conflict itself is the finding — is a human decision.

AI may enumerate the conflicting Perspectives. AI may articulate the grounds of conflict. AI may propose resolutions. But when the conflict involves genuinely competing values (e.g. a feminist reading vs. a formalist reading, a Marxist vs. a liberal interpretation), no algorithm has authority to resolve it. The human steward decides what the canonical representation of the conflict is.

**Enforcement:** The data model must support "unresolved conflict" as a first-class epistemic state. A conflict field on Perspectives, or a ConflictRecord object, allows the system to preserve genuine disagreement without forcing algorithmic resolution.

---

### 5. Deletion or Legal Suppression Actions

No object in `hermeneia.db` may be deleted, suppressed, redacted, or made inaccessible without a human steward decision. AI may flag objects for potential deletion review (e.g. "this Observation appears to contain personal information"). But the deletion or suppression action itself is human-only.

This applies even in cases where deletion would be legally required (GDPR right to erasure, court order). The legal obligation is fulfilled by a human steward executing the action after human review, with the action recorded in an append-only audit log. The audit log records that the deletion occurred and who authorized it; it does not record what was deleted (the contents are gone) but records the fact of the deletion.

**Enforcement:** No `DELETE` statement may be issued by any automated pipeline. The database schema must enforce this through trigger-based guards or application-layer constraints. Deletion and suppression must be implemented through a human-gated administrative interface, not an API endpoint callable by AI agents.

---

### 6. Assignment of Ethical or Moral Judgments

Hermeneia may be used to analyze corpora that include morally contested content: historical atrocities, ideological texts, politically charged arguments, discriminatory works. The system may generate Observations about such content. It may generate Interpretations from multiple Perspectives. But the assignment of a moral or ethical judgment — "this work is harmful," "this claim is false and dangerous," "this text is a primary source for a crime" — is a human decision.

AI may generate Perspectives that include moral frameworks (e.g. a feminist ethical reading, a rights-based analysis). These are valid epistemic contributions. But a moral judgment assigned by the system as a final verdict, rather than as a Perspective among Perspectives, must be made by a human steward.

**Enforcement:** No field in any canonical ontology object schema may have a name that implies final moral authority (e.g. `is_harmful`, `is_false_and_dangerous`). Moral assessments are represented as Interpretations within Perspectives, not as fields on canonical objects. A steward-assigned moral judgment is recorded as a steward-authored Interpretation with human provenance.

---

### 7. Final Publication or Certification of Knowledge Artifacts

When a corpus analysis reaches a state where it is ready to be published, certified, or otherwise designated as a final authoritative product — a published reading of a novel, a certified historical reconstruction, a released knowledge base — that certification is a human act.

AI may generate the content of the artifact. AI may verify its internal consistency. AI may check its conformance against ADRs. But the act of declaring the artifact complete, published, or certified is performed by a human steward and recorded with human provenance.

**Enforcement:** A `published` or `certified` state on any top-level corpus object requires a steward ID and timestamp. No automated pipeline may transition a corpus to a published or certified state.

---

## What AI May Do

Within the constitutionally reserved categories, AI may:

- **Propose** — Draft candidate definitions, candidate Interpretations, candidate amendments, candidate resolutions to conflicts.
- **Summarize** — Present the state of a decision space, enumerate competing options, describe the epistemic content of a corpus.
- **Compare** — Identify similarities and differences between Perspectives, between candidate definitions, between proposed amendments.
- **Simulate** — Model what the consequences of a decision might be, what objects would be affected, what constitutional constraints would be implicated.
- **Flag** — Identify potential problems for human review: possible duplicates, potential deletions, possible conflicts, possible constitutional violations.

AI may not:

- **Finalize** — Complete any of the seven reserved categories without human action.
- **Declare** — Mark any reserved decision as made without human sign-off.
- **Suppress** — Hide, archive, or make inaccessible any canonical object without human authorization.
- **Certify** — Mark any artifact as final, published, or canonical without human steward action.

---

## Serialization Rules

The human-only status of a decision must be representable in the data model. The following fields are reserved to enforce this:

| Field | Location | Purpose |
|---|---|---|
| `ratified_by` | ADR header | Human steward who ratified this ADR |
| `accepting_steward` | AI Provenance record | Human steward who accepted an AI-generated object |
| `published_by` | Corpus top-level record | Human steward who published/certified the corpus |
| `deletion_authorized_by` | Audit log record | Human steward who authorized a deletion or suppression action |
| `conflict_resolution_by` | ConflictRecord | Human steward who resolved an epistemic conflict |

No automated pipeline may write to any of these fields. They are populated exclusively through human-gated interfaces.

---

## Validation Rules

```python
# Every ratified ADR must have a human steward identified
assert adr.ratified_by is not None and is_human_steward(adr.ratified_by)

# Every canonical AI-generated object must have a human acceptor
assert ai_provenance.accepting_steward is not None
assert is_human_steward(ai_provenance.accepting_steward)

# No automated pipeline may write to human-reserved fields
assert not written_by_automated_pipeline(record.ratified_by)
assert not written_by_automated_pipeline(record.accepting_steward)
assert not written_by_automated_pipeline(record.published_by)

# Deletion audit log must identify a human authorizer
assert deletion_log.authorized_by is not None
assert is_human_steward(deletion_log.authorized_by)
```

---

## Migration Policy

This definition may be amended only by a human ratification decision (per the process it defines). Amendments that narrow the set of human-reserved decisions require special justification: the default direction is expansion, not contraction. Reducing the set of human-reserved decisions requires explicit constitutional cost-of-error analysis.

---

## Constitutional Alignment

- **Article I** (Reality precedes interpretation): Human stewards are positioned at the interpretation and certification layers, precisely where judgment is required.
- **Article II** (Provenance mandatory): Human-only fields are themselves provenance records — they permanently record which human made which decision.
- **Article IV** (if applicable): Any article governing the role of human judgment is directly satisfied.
- **Axiom 5** (Separation of concerns): Human judgment belongs at the interpretive and certification layers, not the observation layer. This ADR maps that separation to specific decisions.

---

## Consequences

**Positive:**
- The epistemic authority of human stewards is constitutionally protected. No AI system can accumulate final authority through gradual scope expansion.
- Every canonical object and every published artifact has a traceable human decision in its provenance chain.
- The system can be audited for unauthorized AI autonomy: any canonical object lacking required human-only fields is a constitutional violation detectable by `validation/invariants.py`.

**Negative:**
- Human-only decision requirements create unavoidable bottlenecks. A large corpus with many AI-generated Interpretations requires significant steward time for acceptance decisions.
- The system cannot fully automate corpus production. There is an irreducible human-in-the-loop requirement for every canonical object and every published artifact.
- Defining `is_human_steward()` requires a steward identity and authentication system, which is infrastructure the system must provide.

---

## Alternatives Considered

**Alternative: Human oversight on a sampling basis — humans review 10% of AI outputs**  
Rejected. Sampling-based oversight does not provide constitutional guarantees. The 90% unreviewed objects carry no human provenance. If systematic error exists in the AI-generated outputs, the unreviewed objects propagate that error into the canonical corpus without detection.

**Alternative: AI systems may have final authority over low-stakes decisions**  
Rejected. The definition of "low-stakes" is itself a judgment call that tends to expand under optimization pressure. The constitutional boundary must be crisp and non-negotiable. Introducing a stake-based carve-out creates a governance surface that will be contested and eroded over time. The seven categories are defined by the nature of the decision, not the perceived consequence.

**Alternative: A trust-level system where AI systems can be promoted to human-equivalent authority through track record**  
Rejected. Track record is evidence of past performance, not a guarantee of future performance. A model that has produced 10,000 correct Interpretations can still produce a systematically biased output on the 10,001st. Constitutional authority is not earned by track record; it is assigned by constitutional position. AI systems are constitutionally positioned as contributors, not authorities.
