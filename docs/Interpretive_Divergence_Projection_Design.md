# Interpretive Divergence Projection Design

**Status:** Implementation design  
**Authority:** ADR-0043  
**Scope:** Phase 1 read-only comparison of two existing Interpretations

## Purpose

The Interpretive Divergence Projection answers:

- What stayed the same?
- What changed?
- Why did it change?

It does so without creating ontology, persisting comparison results, or treating
expressive differences as interpretive differences.

## Classification

The feature is a Pure Projection delivered through a read-only Inspection
Surface.

It is not:

- a canonical object;
- a derived epistemic object;
- an Evaluation Function;
- a Finding;
- a pipeline stage; or
- a ratifiable artifact.

## Projection Inputs

The projection accepts exactly two existing Interpretation IDs:

```text
Interpretation A ID
Interpretation B ID
```

For each Interpretation, the projection reads:

- `id`;
- `text`;
- `perspective`;
- `perspective_id`;
- `evidential_status`;
- `confidence`;
- `observation_id`;
- `evidence_observation_ids`; and
- the referenced Perspective and Observation records.

The Interpretation's primary `observation_id` is always included in its
supporting evidence set. This preserves the existing lineage even when an older
row has an empty `evidence_observation_ids` JSON array.

## Projection Outputs

The projection returns:

### Shared Claims

Interpretation references whose normalized claim text is exactly equal.
Normalization is limited to Unicode case folding and whitespace collapse. It is
a comparison convenience, not canonical text and not semantic inference.

### Distinct Claims

Canonical Interpretation references whose normalized claim text is not exactly
equal. Each Interpretation remains visible verbatim with its Perspective and
evidential status.

Distinct canonical claims are not automatically declared contradictory.

### Contradictory Claims

Phase 1 returns:

```json
{
  "status": "not_computed",
  "claims": [],
  "reason": "No ratified deterministic Interpretation contradiction rule exists."
}
```

This prevents lexical difference, negation heuristics, or model judgment from
being promoted to constitutional fact.

### Evidence Differences

The projection computes exact set operations over canonical Observation IDs:

- evidence shared by both Interpretations;
- evidence unique to Interpretation A; and
- evidence unique to Interpretation B.

Every evidence item includes its canonical Observation ID and verbatim
`raw_text`.

### Interpretive Summary

The summary is deterministic structured text assembled only from:

- exact claim equality or inequality;
- Perspective identity equality or inequality;
- evidence-set equality, overlap, or disjointness; and
- evidential-status equality or inequality.

It does not infer cultural priors, metaphor systems, authorial intent, truth,
quality, or correctness.

## Interpretive vs. Expressive Divergence

This surface accepts Interpretation IDs, not RenderedNarrative IDs or
ExpressionProfile IDs.

Therefore:

- differences between canonical Interpretation records are reported as
  interpretive claim differences;
- differences between ExpressionProfiles, providers, languages, rhetoric, or
  narrative wording are outside this projection; and
- the payload explicitly states that expressive divergence was not evaluated.

If two narratives differ while their underlying Interpretation inputs are the
same, this projection must not classify that difference as interpretive.

## Regeneration Path

```text
Interpretation A ─┬─ Perspective A
                  └─ Observation ancestry A

Interpretation B ─┬─ Perspective B
                  └─ Observation ancestry B

          exact deterministic comparison
                       |
                       v
       Interpretive Divergence Projection
```

The projection is regenerated on every request. It has:

- no ID;
- no timestamp;
- no table;
- no insert, update, or delete operation;
- no cache requirement; and
- no independent provenance.

The same database state and Interpretation IDs produce the same payload.

## Lineage Implications

The projection creates no lineage node and cannot become a parent of any
canonical object.

Every claim and evidence result retains direct canonical references to:

- Interpretation;
- Perspective, when registered; and
- Observation.

Missing Perspective or Observation ancestry causes the request to fail rather
than being repaired or inferred.

## Inspection Surface

The HTTP surface is:

```text
GET /api/divergence/interpretations/<interpretation_a_id>/<interpretation_b_id>
```

The endpoint:

- opens SQLite in read-only mode;
- performs no schema initialization;
- returns `404` for missing Interpretations;
- returns `409` for broken required lineage; and
- returns a disposable JSON projection.

## Constitutional Justification

- Constitution Article VII: Interpretation remains the Claim; Perspective
  remains the Frame.
- ADR-0011: no separate Claim object is introduced.
- ADR-0015: Interpretation comparison preserves Perspective scope and
  Observation ancestry.
- ADR-0043: the aggregate comparison is a Pure Projection through an Inspection
  Surface.
- CI-016: comparison metadata is fully disposable and regenerable.
- Regeneration Principle: deleting the response changes no constitutional
  history.
- Human Stewardship: the projection exposes differences without deciding which
  Interpretation is correct.

## Phase 1 Limits

Phase 1 does not:

- perform semantic similarity;
- extract claims from RenderedNarratives;
- detect contradiction through heuristics or an LLM;
- compute an authoritative divergence score;
- compare ExpressionProfiles;
- persist results; or
- create Findings.

