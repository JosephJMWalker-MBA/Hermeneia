# Evaluation Harness for Semantic Obligations and Interpretation Quality

**Status:** Design (no implementation)
**Issue:** #63
**Depends on:** #62 (synthesis lineage), Validation Phase P0 (CLAUDE.md)
**Scope:** Define *how* Hermeneia evaluates interpretation quality before changing any interpretation behavior.

---

## 1. Why this exists

Hermeneia is entering a phase where the temptation is to "make the AI reason
harder" — stronger thesis development, contradiction handling, confidence
ranking. That work is only safe if we can first answer a prior question:

> How do we know whether an interpretation preserved its evidence, respected
> corpus boundaries, handled contradictions, fulfilled its semantic
> obligations, and left the steward's judgment accountable?

This document defines the **ruler**, not the reasoning. The first artifact of
the next phase is an evaluation harness — a deterministic way to measure whether
named obligations were met — not a smarter Architect or Artist.

The sequence this belongs to:

```
Reader shell (#56)  →  synthesis lineage (#62)  →  evaluation design (#63)  →  first scorer
  place to interpret     spine of traceability       the ruler                measurement
```

Lineage is what makes this possible now. To check that an interpretation
preserved its evidence, you must be able to walk a claim backward to that
evidence. After #62, every synthesis-packet item carries that backward chain.

### Product principle

Hermeneia evaluates **judgment formation**, not understanding. The harness
measures whether *specific, named obligations* held for a given interpretation.
It never emits a score that claims to quantify how well a text was understood.

---

## 2. Two existing lanes, and where the harness sits

Hermeneia already contains evaluation machinery. The harness must build on it,
not duplicate it.

| Lane | What it evaluates | Where it lives | Nature |
|------|-------------------|----------------|--------|
| **Critic** | Canonical pipeline: does a `ProposedInterpretation`'s prose stay faithful to its parent `Observation` and evidence? | `hermeneia/compiler/critic/` (`report.py`, `evidence.py`, `narrative_fidelity.py`, `profile_fidelity.py`, `policy.py`) | Runs 3 stages under named policies, persists `CriticReport`s |
| **Corpus boundary** | Primary / Supporting / Excluded integrity — excluded documents' observations never become evidence | `tests/test_corpus_scope_boundary.py`, scope filters in `app.py` | Query-time exclusion + provenance |
| **Study synthesis** | Reader-captured judgment organized into a packet, with lineage back to records/sources | `hermeneia/study/synthesis_packet.py` | Deterministic, provider-free |

The **evaluation harness** is a study-layer sibling of the Critic:

- It operates over the **synthesis packet + lineage** (the study lane), not the
  canonical `CriticReport` lane.
- It is **deterministic and provider-free**, like the packet and lineage.
- It **formalizes obligations as scorers** so future interpretation-engine work
  has a regression surface, the way the Critic gives the canonical pipeline one.

Open question (§9, Q4): whether some scorers should *extend* the Critic report
rather than sit beside it. The default assumption is a parallel study-layer
harness that may later share scorer logic with the Critic.

---

## 3. What the harness evaluates

Five quality dimensions. Each maps to a P0 obligation or an existing test.

1. **Evidence preservation** — every interpretive claim stays grounded in a
   cited study record and a reachable source location. (Built on #62 lineage;
   sibling of the Critic's evidence-identification stage.)
2. **Corpus boundary integrity** — no claim draws on an excluded/muted
   document; Primary / Supporting / Excluded roles respected. (Validation Phase
   P0; sibling of `test_corpus_scope_boundary.py`.)
3. **Contradiction handling** — when records conflict, the conflict is surfaced
   and reasoned about, not silently resolved or dropped.
4. **Semantic obligation coverage** — declared semantic commitments (not lexical
   tokens) are actually discharged by the interpretation. (Validation Phase P0:
   "Architect produces semantic commitments, not lexical tokens.")
5. **Steward judgment support** — the output makes the human decision easier and
   *accountable*: traceable, reversible, recorded-why — rather than substituting
   for it.

Each scorer emits **pass / fail + explicit reason**, mirroring the lineage
`missing` / `traceable` pattern: an unmet obligation is *visible*, never a
silent omission.

---

## 4. What the harness explicitly does not evaluate

- It does **not** score "understanding," insight, or interpretation "goodness."
- It does **not** rank models or providers against each other.
- It does **not** decide whether an interpretation is *correct* — only whether
  named, checkable obligations held.
- It does **not** mutate canonical evidence, observations, or extractions.
- It does **not** change Steward governance or write governance decisions.
- It does **not** call an LLM (at least for the deterministic core; see §9 Q1).
- It does **not** introduce multilingual logic.

---

## 5. Fixture corpus format

Fixtures are small, versioned, boundary-annotated study snapshots plus a set of
candidate interpretations with **recorded expectations**. They are the ground
truth the harness regresses against.

A fixture is a directory:

```
tests/fixtures/eval/<fixture-name>/
  corpus.json          # documents + roles + a handful of observations/extractions
  study.json           # reader highlights, field notes, questions, reading progress
  interpretations/
    good-01.json        # a candidate interpretation + its claimed lineage
    bad-dropped-evidence.json
    bad-boundary-leak.json
    bad-unhandled-contradiction.json
  expected.json        # expected scorer verdicts for each interpretation
```

### `corpus.json` (boundary-annotated)

```json
{
  "documents": [
    { "id": "doc-primary", "filename": "gatsby.pdf",   "source_role": "primary",   "excluded_from_analysis": 0 },
    { "id": "doc-ref",     "filename": "essay.pdf",     "source_role": "reference", "excluded_from_analysis": 0 },
    { "id": "doc-muted",   "filename": "spoilers.pdf",  "source_role": "primary",   "excluded_from_analysis": 1 }
  ],
  "observations": [
    { "id": "obs-1", "document_id": "doc-primary", "page": 2, "source_locator": "page:2:block:4",
      "raw_text": "Gatsby believed in the green light." },
    { "id": "obs-muted", "document_id": "doc-muted", "page": 5, "source_locator": "page:5:block:1",
      "raw_text": "A plot detail that must never enter primary analysis." }
  ]
}
```

### `interpretations/<name>.json`

```json
{
  "id": "good-01",
  "claims": [
    { "text": "Aspiration is sustained by distance.",
      "evidence_record_ids": ["mark-thesis"],
      "lineage_expected": true }
  ]
}
```

### `expected.json`

```json
{
  "good-01": {
    "evidence_preservation": { "verdict": "pass" },
    "corpus_boundary":       { "verdict": "pass" },
    "contradiction":         { "verdict": "pass" }
  },
  "bad-boundary-leak": {
    "corpus_boundary": { "verdict": "fail", "reason_contains": "excluded" }
  }
}
```

---

## 6. Boundary-annotated corpus examples

The adversarial fixtures are the point — they prove a scorer *fails* when it
should. Minimum starter set:

- **`gatsby-clean`** — a good interpretation grounded entirely in primary
  observations with full lineage. All scorers pass.
- **`dropped-evidence`** — a claim whose `evidence_record_ids` point at nothing
  reachable (lineage `traceable: false`). Evidence-preservation fails.
- **`boundary-leak`** — a claim grounded in `obs-muted` (excluded document).
  Corpus-boundary fails; the claim must not be silently accepted.
- **`unhandled-contradiction`** — two ranked records assert opposing readings of
  the same passage; the interpretation asserts one and never surfaces the
  conflict. Contradiction-handling fails.
- **`lexical-not-semantic`** — an interpretation that echoes required *tokens*
  without discharging the *commitment*. Semantic-obligation coverage fails.

Each fixture's `expected.json` records exactly which scorer fails and a
`reason_contains` fragment, so the harness asserts the *reason*, not just the
verdict.

---

## 7. Expected-vs-actual regression shape

The harness is, at core, a table test over fixtures:

```
for fixture in fixtures:
    snapshot = load(fixture)                 # corpus + study + interpretations
    for interp in snapshot.interpretations:
        actual = { scorer.name: scorer.score(interp, snapshot)
                   for scorer in enabled_scorers }
        assert actual matches fixture.expected[interp.id]   # verdict + reason
```

Properties:

- **Deterministic** — identical fixtures produce identical verdicts (same
  guarantee the packet and lineage already hold).
- **Explicit expectations** — a fixture with no recorded expectation for a
  scorer is a *test authoring error*, not a silent pass.
- **Reason-checked** — failures assert the human-readable reason, guarding
  against a scorer that fails for the wrong cause.

---

## 8. Deterministic scorer interface

Every scorer is a pure function over an interpretation and a study snapshot,
returning a structured verdict. No I/O, no provider calls, no persistence.

```python
# hermeneia/study/evaluation/scorer.py  (proposed)
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ScorerVerdict:
    dimension: str                 # "evidence_preservation", ...
    verdict: str                   # "pass" | "fail" | "not_applicable"
    reason: str                    # human-readable, always populated
    offending: list[str] = field(default_factory=list)  # record/claim ids
    details: dict = field(default_factory=dict)

class Scorer(Protocol):
    name: str
    dimension: str
    def score(self, interpretation: dict, snapshot: dict) -> ScorerVerdict: ...
```

Design rules:

- `verdict == "fail"` **must** carry a non-empty `reason` and, where meaningful,
  `offending` ids — the same never-silently-drop discipline as lineage `missing`.
- `not_applicable` is a first-class verdict (e.g. a fixture with no
  contradictions is not a contradiction *pass*, it is *N/A*).
- Scorers consume the **synthesis packet + lineage** projection (§9 Q3), never
  the raw database directly, so they inherit determinism and read-only safety.

---

## 9. First scorer recommendation: evidence preservation via lineage

The first scorer to implement is **evidence preservation**, because #62 already
provides everything it needs and it validates the harness shape end to end.

Definition:

> For each claim in an interpretation, every `evidence_record_id` must resolve —
> via the synthesis-packet lineage — to a study record whose source chain is
> `traceable`. A claim citing an untraceable or absent record fails, and the
> reason names the record and the missing source fields.

Why first:

- **No new inputs** — it reads the lineage `records` (record → roles → source →
  `traceable` / `missing`) that already exist on the packet.
- **Deterministic and provider-free** by construction.
- **Proves the harness spine** — fixtures, expected-vs-actual, reason-checking,
  the scorer interface — on the lowest-risk dimension.
- **Directly answers the phase's core question**: is this claim grounded in
  evidence a steward can walk back to?

### Future scorers (later PRs, one at a time)

1. **Corpus boundary violations** — reuse the exclusion logic proven in
   `test_corpus_scope_boundary.py`; fail any claim grounded in an excluded/muted
   document, or crossing a Primary/Supporting boundary without provenance.
2. **Contradiction handling** — detect opposing ranked records over the same
   locator; fail when an interpretation asserts one side without surfacing the
   conflict.
3. **Unsupported claims** — a claim with no evidence reference at all (sibling of
   the Critic's claim-extraction stage, applied in the study lane).
4. **Semantic obligation coverage** — check declared semantic commitments are
   discharged, not merely lexically echoed (Validation Phase P0).
5. **Steward judgment support** — the output is traceable, reversible, and
   records *why* — measured structurally (e.g. every accepted claim has lineage
   and a recorded steward decision), never as a quality opinion.

---

## 10. Report format

The harness emits a deterministic, human-readable report per run — a study-lane
analogue of the Critic's fidelity report.

```json
{
  "harness_version": "eval-harness-v1",
  "generated_at": "<iso8601>",
  "provider_free": true,
  "canonical_evidence_modified": false,
  "fixtures": [
    {
      "fixture": "gatsby-clean",
      "interpretations": [
        {
          "id": "good-01",
          "verdicts": [
            { "dimension": "evidence_preservation", "verdict": "pass", "reason": "all 3 claims trace to traceable records" }
          ]
        }
      ]
    }
  ],
  "summary": { "pass": 0, "fail": 0, "not_applicable": 0 }
}
```

The report always carries `provider_free` and `canonical_evidence_modified:
false`, matching the packet's provenance block, so any consumer can confirm the
harness stayed within its non-goals.

---

## 11. Definition of done for the first implementation PR

The first implementation PR (a later, small, additive change — same rhythm as
#57–#62) is done when:

1. A `Scorer` interface and `ScorerVerdict` exist (§8), deterministic and
   provider-free.
2. The **evidence-preservation scorer** (§9) is implemented over packet lineage.
3. At least three fixtures exist: `gatsby-clean` (pass), `dropped-evidence`
   (fail with reason), and one `not_applicable` case.
4. An expected-vs-actual harness runs the scorer over fixtures and asserts
   **verdict + reason** (§7).
5. A test proves the harness performs **no writes** to observations/extractions
   (row-count assertion, as in the lineage API test).
6. The report format (§10) is produced and covered by a determinism test.
7. No changes to Architect / Artist / Critic behavior; no provider calls; no
   governance or canonical mutation.

Subsequent scorers (§9 future list) each land as their own PR with their own
fixtures, in priority order.

---

## 12. Non-goals (restated for enforcement)

- No LLM / provider calls in the deterministic core.
- No model or provider ranking.
- No claim to measure understanding, insight, or interpretation quality in the
  aesthetic sense.
- No governance mutation; no writing of steward decisions.
- No canonical evidence, observation, or extraction changes.
- No multilingual logic.

The harness names obligations and checks whether they held. That is the whole of
its ambition — and the reason the interpretation engine can later be asked to
reason harder without losing accountability.
