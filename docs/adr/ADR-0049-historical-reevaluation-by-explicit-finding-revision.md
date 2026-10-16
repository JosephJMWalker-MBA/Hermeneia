# ADR-0049: Historical Re-evaluation by Explicit Finding Revision

**Status:** PROPOSED (research; a distinct constitutional problem, not part of
ADR-0046)
**Version:** 0.1
**Date:** 2026-10-16
**Would amend:**
- ADR-0041 Amendment I, **additively**: one identity rule for revision
  Findings only;
- ADR-0046 D-3, **additively**: an explicit, authorized revision path beside
  the unchanged fail-closed write path.

**Research:** `docs/design/historical-reevaluation-research-2026-10-16.md`,
with evidence in `tests/test_reevaluation_research.py`.

**Nothing here is implemented, and nothing confers authority.** ADR-0046 D-3
remains authoritative: a divergent result under an existing Finding ID is
refused.

---

## Context

**The problem.** Finding identity names the obligation evaluated, not its
determination. So a ratified, revised evaluator (for example
`provenance-v1.1` under ADR-0046) computes the same ID as the historical
Finding, and D-3 refuses the new result. The earlier conclusion is preserved,
but the authorized correction cannot be recorded.

> A later correction must be allowed to improve understanding without erasing
> the evidence of an earlier conclusion. (Steward, 2026-10-16)

## Decision (proposed)

1. **A revision is a new Finding.** It records the revised determination under
   the identity:

   ```text
   revision_id = sha256("finding-revision:" + predecessor_finding_id + ":" + evaluation_method)
   ```

   Ordinary (first-evaluation) identity is unchanged for every dimension.
2. **Supersession.** Each revision is linked to its predecessor by an
   append-only `SupersessionRelation` (`old_id` → `new_id`):
   - the `reason` names the authorizing method change;
   - `ratified_at` is the date of the authorizing ratification.

   The predecessor and its steward decisions are never changed.
3. **When a revision is allowed.** Only under a ratified method change whose
   ADR names the dispositions it supersedes. A revision is an explicit, recorded
   act, never a side effect of re-running the Critic. The revision and its
   relation are written in one transaction, through the D-3 guard. Outside that
   path, D-3 is unchanged: divergence is refused.
4. **"Current" is the head of the supersession chain.** There is exactly one
   per obligation; this restates ADR-0041's completeness invariant. Verdicts
   count heads only, and superseded Findings remain visible as history.
5. **Steward decisions.** A revision begins undecided. Prior decisions stay
   attached to the Finding they reviewed, and are shown as context.

## Alternatives (measured on five obligations, two of them changed)

| Option | Result |
| --- | --- |
| A. Method-versioned identity | +5 Findings, because every obligation is duplicated. Identity changes for every dimension, two identity rules coexist permanently, and D-3 no longer detects divergence |
| B. Append-only occurrences | A new canonical object and table. A steward decision is left on a thread whose current determination it never reviewed |
| **C. Explicit revision (this ADR)** | +2 Findings and +2 relations. Originals are byte-identical, decisions stay bound to what they reviewed, there is one head per obligation, re-runs are idempotent, there is no schema change, and D-3 is intact |

## Not decided here

- **Revision trigger.** Revise on a changed disposition only, or on any
  recorded difference? A newer method that records more facts (ADR-0047
  L2-b) differs in evidence on **every** obligation. The research recommends
  disposition plus a D-3 refinement for evidence-only differences. That
  refinement needs its own authority.

- Who may trigger a revision batch (proposed: the Steward, explicitly).
- How a future Findings-portability component carries revisions and their
  relations.
- Whether ADR-0046 U activation should be followed by a revision pass. Any
  such pass would need this ADR ratified first.

---

## Ratification record

To be completed **only** by the Primary Human Steward.

| Field | Value |
| --- | --- |
| Decision | ☐ ratified ☐ ratified with amendments ☐ returned ☐ deferred |
| Ratified by | |
| Date | |
| Ratified proposal HEAD | |
| Amendments at ratification | |
