# Historical re-evaluation: preserving an earlier Finding while a ratified revision becomes inspectable

**Status:** research packet, 2026-10-16.
- **Not implemented, not ratified.** Finding identity, the canonical ontology,
  the schema and product behavior are unchanged.
- **ADR-0046 D-3 stays authoritative** for implementation planning: a
  divergent result under an existing Finding ID is refused.
- **Proposed decision:** ADR-0049 (PROPOSED).

**Evidence:** `tests/test_reevaluation_research.py`, 7 tests. They prototype
each option on test databases built from real product data.

## The problem

A Finding's identity names the evaluated obligation, not its determination or
the method that produced it (ADR-0041 Amendment I). After ADR-0046 U is
activated:

| Case | Method | Disposition | Finding ID |
| --- | --- | --- | --- |
| Historical | `provenance-v1.0` | `transformed` (stored; a steward decision may be attached) | X |
| Re-evaluated | `provenance-v1.1` | `unverifiable` (computed) | X, the same |

D-3 refuses the second result and keeps the first. That is correct today. But
the newer, properly authorized determination then cannot be recorded at all.

> Governing rule (Steward, 2026-10-16): a later correction must be allowed to
> improve understanding without erasing the evidence of an earlier conclusion.

## Requirements

| # | Requirement |
| --- | --- |
| Q1 | The original Finding stays byte-identical, under its original ID |
| Q2 | Steward decisions stay bound to the determination they reviewed |
| Q3 | The revised determination is separately inspectable |
| Q4 | Exactly one **current** determination per obligation, restating the completeness invariant |
| Q5 | Deterministic and idempotent: re-running the same authorized revision writes nothing new |
| Q6 | Only an authorized method change revises. An accidental divergence is still refused (D-3 intact) |
| Q7 | The smallest change to ontology, identity and schema |
| Q8 | Growth proportional to what changed |

## Scenario (measured)

The scenario uses a restored study with five provenance obligations:
- **under v1.0:** two `transformed` (absent records), two `preserved` and one
  `omitted`, with a steward decision on one `transformed` Finding;
- **under v1.1:** two `unverifiable`; the other three are unchanged;
- **IDs:** both evaluations compute the same five IDs.

**Baseline (D-3).** The v1.1 batch is refused as `divergent_result` for
exactly the two changed obligations. The original rows and the decision are
unchanged.

## Options compared

| | A. Method-versioned identity | B. Append-only evaluation occurrences | **C. Explicit revision with supersession** |
| --- | --- | --- | --- |
| Mechanism | Finding ID includes `evaluation_method` | A new canonical object records each determination of a Finding; the Finding becomes a thread | A **revision Finding**, with ID `sha256("finding-revision:" + predecessor_id + ":" + method)`, plus a `SupersessionRelation` from old to new |
| New rows (5 obligations, 2 changed) | **+5 Findings**: every obligation is duplicated, including the 3 unchanged | **+5 occurrences** in a new table | **+2 Findings, +2 relations** |
| Q1 originals unchanged | yes | yes | yes, byte-identical |
| Q2 decision bound to what it reviewed | yes | **no**: the decision sits on a thread whose current determination it never reviewed (it accepted "transformed"; the thread now says "unverifiable") | **yes**; the revision carries no decision until reviewed |
| Q3 revision inspectable | yes | yes | yes, as an ordinary Finding |
| Q4 one current per obligation | needs a new "current" rule; every obligation holds 2 | latest occurrence | **the head of the supersession chain**: exactly one per obligation, measured, including a second, later revision |
| Q5 idempotent | yes | needs keys | **yes**: the same revision computes the same ID and is `identical` under D-3 |
| Q6 D-3 intact | no: no collision ever occurs, so a divergence goes unnoticed | partly | **yes**: the ordinary write path still refuses the divergent result |
| Q7 identity and ontology change | **identity changes for every dimension**; stored v1.0 IDs no longer follow the formula (two rules coexist permanently) | **ontology change** (Finding is no longer "one bounded delta", ADR-0041 §1), a new table, and decisions would need rebinding | **additive**: ordinary identity is unchanged; one identity rule for revisions only |
| Schema | none | new table | **none**: the existing `findings` table and `supersession_relations` triggers accept it unchanged (measured) |
| Q8 growth | the whole ledger, per method change | every re-evaluation | changed obligations only |

## Recommendation: C, explicit revision with supersession

- **Identity.** A revision's identity is derived from its predecessor and the
  authorizing method. It is deterministic, unique, chainable, and leaves every
  existing and future first-evaluation ID unchanged.
- **Authority.** It reuses the existing append-only `SupersessionRelation`.
  The reason names the method change, and `ratified_at` is the date of the
  authorizing ratification.
- **"Current" is a projection rule:** the head of the chain. History stays
  whole.
- **D-3 still governs ordinary writes.** Revision is a separate, explicit act,
  never a side effect of re-running the Critic.

## Open questions for the decision

1. **Which method changes may revise?** Proposed: only a ratified method
   change whose ADR names the dispositions it supersedes. For ADR-0046, that
   is v1.0 `transformed` with `provenance_exists: false` → v1.1
   `unverifiable`.
2. **Who triggers a revision?** Proposed: an explicit steward act, or a
   ratified, recorded batch per workspace. Never automatic on Critic re-run.
3. **Decisions.** A revision starts undecided. Projections show the prior
   decision as context, attributed to the Finding it reviewed.
4. **Cross-workspace identity.** A workspace that first evaluates under v1.1
   gets an ordinary ID. One that revises gets a revision ID. Both are correct
   locally, but a future Findings-portability component must carry the
   supersession relations and must not equate the two.
6. **What triggers a revision: disposition, or any recorded difference?**
   This was found at integration with ADR-0047 L2-b.
   - **The cause.** L2-b's v1.1 records one more fact (`blueprint_link_exists`)
     for every obligation.
   - **The effect.** After activation, all five obligations diverge from v1.0
     on evidence, while only two change disposition. D-3, which compares
     evidence, refuses all five.
   - **Proposed:** revise when the disposition changes. Report an evidence-only
     difference as `retained`, with the newer facts named, under a D-3
     refinement that compares only the facts both methods record. That
     refinement would amend ADR-0046 D-3 and needs authority. Tested in
     `test_a_method_that_records_more_facts_diverges_on_evidence_alone`.
7. **Verdicts.** The trust card and dashboards should count heads only, and
   show superseded Findings as history.
