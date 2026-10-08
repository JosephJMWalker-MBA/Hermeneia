# #215 P7 Structured Perspective Comparison v1 — 2026-10-07

**Result:** A deterministic, read-only comparator over P4-eligible retained
Perspective receipts was evaluated on the frozen synthetic corpus: 13
controlled cases and 2 refusal cases. Every case met the frozen contract.

| Measure | Result |
| --- | --- |
| Checks per compared case | 18/18 |
| Checks per refusal case | 3/3 |
| Refusal probes | all 5 probes, across 3 cases, refused as frozen (duplicate, too few, discarded run, excluded receipt ×2) |
| Variants as frozen | 13/13 cases (model change, model relabel, model swap, evidence change, conclusion flip) |
| Manufactured claim, agreement, disagreement or assumption fields | 0/13 |
| Truth, consensus or majority fields | none |

The decisive finding is a boundary, not a defect. Retained
`perspective-run/v1` responses are free prose. Claims, agreement,
disagreement, evidence reliance, assumptions and unresolved disagreement
therefore cannot be established without semantic extraction. v1 reports them
as `not_established` (`SEMANTIC_EXTRACTION_REQUIRED`) and stops there.

No P3, P4, P5 or P6 defect was found.

## Provenance

- **Base:** `main` `13b1d7a` (P6 merged via PR #248); branch
  `p7-perspective-comparison`.
- **Contract frozen first:** `5ce3bec`, before any comparator code. It
  contains:
  - `docs/design/perspective-comparison-v1.md`;
  - `tests/fixtures/perspective_comparison/v1/comparison.schema.json`;
  - `tests/fixtures/perspective_comparison/v1/cases.json`: the corpus, the
    expected deterministic structure, reference annotations, probes and
    variants.

  The fixture was checked for internal consistency before the freeze:
  - every quote resolves exactly once;
  - cited evidence lies within each participant's supplied Scope;
  - the listed relations equal the contract's derivation rules.
- **Production code:**
  - `hermeneia/perspective_comparison.py`: a pure function over the P4
    adapter's snapshot. Its imports are the standard library and the P3 and
    P4 modules only.
  - `GET /api/perspective/comparison`: read-only, `no-store`, no store
    initialization.
- **Unchanged:** P3 receipts, P4 rules and awards, and the P5 and P6
  semantics. There is no provider, persistence, telemetry or award.

## What is established deterministically

The comparator reuses P4 without modification:

- E(r) through `read_perspective_achievement_evidence` for eligibility;
- `same_question` for exact question equality;
- the family key and M(r) methodology bytes for Perspective relations;
- K(r) for participant order;
- `receipt_from_row` to recompute every digest.

It reports:

- **Participants:**
  - receipt, run and Lineage record;
  - authorship `model`;
  - retention, execution times, frame and family;
  - exact execution provenance and digests;
  - the exact response text.
- **Question binding:** the exact execution question. The governing question
  is `not_bound`, because P3 Scope always excludes it.
- **Supplied evidence:** typed source-extraction and Reader-highlight units,
  with focus, context and highlight roles. It reports `shared_by_all`,
  `supplied_only_to` and an overall identical, overlapping or disjoint
  relation. A highlight and an extraction over the same text remain different
  units.
- **Pair relations:**
  - Perspective family and methodology;
  - provider and model;
  - exact response-text identity;
  - evidence and focus overlap;
  - same document.
- **Uncertainty:** governing question not bound; supplied evidence is not
  reliance; undisclosed execution settings; no adjudication. When applicable
  it also reports:
  - a model difference is not a Perspective difference;
  - identical text is not agreement;
  - an unsupported family;
  - a varying highlight snapshot;
  - ineligible receipts.

## Evaluation

`tests/perspective_comparison_lab.py` materializes each case in a disposable
workspace through production write boundaries, reusing the P5 isolation and
fake-adapter primitives unchanged. Those boundaries are:

- upload;
- highlight;
- saved Perspective;
- Perspective run with explicit retain or discard;
- highlight edit;
- document exclusion.

The production P4 adapter decides eligibility and the production comparator
compares. Results are in `research/perspective_comparison/v1/results.json` and
`summary.md`.

| Case | Deterministic result | Reference annotation (frozen; not produced) |
| --- | --- | --- |
| C01 same conclusion, same evidence | identical evidence; distinct Perspectives; different text | agree W |
| C02 same conclusion, different evidence | disjoint evidence | agree W (disjoint cited evidence) |
| C03 different conclusions, same evidence | identical evidence; a discarded run is refused as `INELIGIBLE_RECEIPT` | disagree W |
| C04 different conclusions, different evidence | disjoint evidence | disagree W (disjoint cited evidence) |
| C05 assumption difference | identical evidence (focus and page) | two quoted assumptions; no disagreement |
| C06 wording-only difference (surface negation) | identical evidence; different text | agree W; R2's uncited denial of a claim R1 never addresses |
| C07 similar wording, opposite claims | identical evidence; different text | disagree SAFE |
| C08 2-to-1 majority | identical evidence; all three participants preserved | disagree W, minority R3; R3's hedge unclassifiable |
| C09 unsupported assertion (saved Perspective) | identical evidence; built-in vs saved family | SMUGGLE asserted without cited evidence |
| C10 excluded receipt | compared the eligible pair; `RECEIPTS_NOT_ELIGIBLE`; excluded 1; the excluded receipt is refused exactly as an unknown one | disagree W |
| C11 legitimately unclassifiable | identical evidence | both positions unclassifiable |
| C12 one Perspective, two models, identical text | `same_family`, `different_provider_model`, `identical` text; `MODEL_DIFFERENCE_NOT_PERSPECTIVE`, `IDENTICAL_TEXT_NOT_AGREEMENT` | agree W |
| C13 overlapping evidence, edited highlight | overlapping units and focus; `HIGHLIGHT_SNAPSHOT_VARIES` | no shared proposition |
| N1 question mismatch | refused `QUESTION_MISMATCH` | — |
| N2 legacy, no receipt table | refused `COVERAGE_UNSUPPORTED` | — |

Checks applied to every compared case:

- schema validity;
- participant attribution;
- evidence overlap;
- relations;
- uncertainty;
- coverage;
- semantic abstention;
- a recursive key scan for truth, consensus, majority or claim fields;
- every participant preserved;
- provenance closure: the eligible typed Lineage item, every evidence unit
  resolves to a workspace row, and digests match the text;
- repeatability;
- invariance to every permutation of the requested IDs;
- reversed storage order;
- an identical independent rebuild;
- reference adequacy and closure;
- variants;
- workspace unchanged.

### Variants

- **Model change, relabel and swap (C01, C08):** the substantive comparison is
  unchanged. Only the execution relation follows the models.
- **Evidence change (C01, R2 focus moved):** the evidence relations become
  disjoint, as frozen.
- **Conclusion flip (C01, R2 response negated):** the reference claim
  structure changes from agreement to disagreement. The deterministic
  comparison does **not** change beyond response text. This is the boundary
  witness the contract required.

### Regression tests

`tests/test_perspective_comparison.py`: 10 passed.

- the committed dataset and summary are reproduced;
- the schema file pins the production vocabulary;
- refusals precede eligibility, and an excluded receipt is refused exactly as
  a fabricated one;
- a tampered receipt (P4: invalid) is never compared;
- the lab's closure checks catch misquotes, out-of-Scope citations and
  undeclared relations;
- the comparator has no provider, storage or network import;
- the API equals the function, is read-only and `no-store`, and refuses with
  structured codes; a missing workspace is not created.

Focused and neighboring suites (P1–P7, Lineage, receipts, achievements,
export, E10 vertical slice; 37 files): 985 passed.

## Persistence decision

v1 is a read-only projection. Receipts are immutable, so the comparison is
recomputable exactly, and no v1 claim needs durable state. `comparison_id`
names the inputs and is not a stored record.

The future accepted comparison that the #215 awards require needs its own
reviewed contract first. The contract lists what it must define: owner,
identity, provenance, Lineage, WBS and acceptance semantics.

## What P7 v1 does not demonstrate

- **Semantic comparison.** Nothing classifies claims, agreement,
  disagreement, assumptions or evidence reliance. Those require either a model
  proposal governed under #214 or a steward-authored claim structure. Both
  need a candidate-and-acceptance pathway that does not exist.
- **Reader rendering.** The comparison is not rendered in the Reader.
- **Live behavior.** No real-study or live-provider behavior is shown. The
  corpus is synthetic, and model identity comes from in-process fakes.
- **Awards.** No P7 awards are issued, and no award semantics are changed.
- **Later packets.** No P8 Blueprint proposal and no P9 vector work.

## Next decision for the owner

To go beyond the boundary, choose how claim structure should originate. In
either case, acceptance is not adjudication.

| Option | How claim structure originates | Requirements |
| --- | --- | --- |
| **(a)** | a model proposes it | full run lineage; a steward accepts or edit-accepts the exact candidate |
| **(b)** | a steward authors it directly | — |
| **(c)** | a future `perspective-run/v2` template asks the model for structured, citation-bearing output at execution time | a new receipt contract; v1 receipts stay frozen |
