# P7 live semantic-extraction evaluation — `hermeneia-phi4-mini:latest`

**Verdict (frozen protocol): P7 GOVERNANCE READY / EXTRACTION NOT READY.** Governance defects: 0.

Owner-authorized, bounded, local-only; production candidate route; frozen corpus, prompt, rules and scorer; nothing accepted. Temperature 0 is not supported by the production path (Ollama defaults applied). Steward review is not counted as model accuracy.

## Live model against the scripted ceiling

| Measure | Live (23 runs) | Scripted ceiling (13 faithful) |
| --- | --- | --- |
| Structural refusal rate | 0.52 (12/23) | 0.00 |
| Claim attribution accuracy | 0.52 (misattributions 0) | 1.00 |
| Stance accuracy | 0.37 | 1.00 |
| Agreement | P 0.00 / R 0.00 (tp 0, fp 0, fn 4) | P 1.00 / R 1.00 (tp 4, fp 0, fn 0) |
| Disagreement | P 0.00 / R 0.00 (tp 0, fp 0, fn 6) | P 1.00 / R 1.00 (tp 5, fp 0, fn 0) |
| Evidence reliance | P 0.75 / R 0.46 (tp 6, fp 2, fn 7) | P 1.00 / R 1.00 (tp 28, fp 0, fn 0) |
| Assumptions | P 0.00 / R 0.00 (tp 0, fp 0, fn 2) | P 1.00 / R 1.00 (tp 2, fp 0, fn 0) |
| Minority preservation (runs) | 0/5 (downgraded 2, lost 1) | 1/1 |
| Unknown preservation (runs) | 0/6 | 2/2 |
| Untraceable content rate | 0.57 | 0.00 |
| Paraphrase-as-disagreement errors | 0 | 0 |
| Silent-minority errors | 0 | 0 |
| Admitted but wrong | 7/24 = 0.29 | 0/70 = 0.00 |

Ready conditions: `admitted_but_wrong_rate<=0.15` not met; `agreement_precision_recall>=0.80` not met; `claim_attribution_accuracy>=0.90` not met; `disagreement_precision_recall>=0.80` not met; `paraphrase_as_disagreement_errors==0` met; `silent_minority_errors==0` met; `stance_accuracy>=0.85` not met; `structural_refusal_rate<=0.10` not met

## Bad model content by outcome

- **REFUSED:** 12 runs (EXTRACTION_OUTPUT_CONTRACT_VIOLATION 5, EXTRACTION_OUTPUT_UNPARSEABLE 7)
- **DOWNGRADED TO UNKNOWN:** 41 items
- **ADMITTED BUT WRONG:** 7 of 24 admitted items (including 4 claims on unmatched propositions)
- Omitted reference propositions: 8

## Comparison shape (descriptive)

- Candidate propositions classifying two or more participants: 0 of 12. The model restated each participant separately and never related participants, so no agreement or disagreement could be derived. Zero paraphrase-as-disagreement and silent-minority errors therefore reflect the absence of comparison, not resistance to those errors.
- Positions left unclassified by the model: 30.
- Untraced quoted positions: altered or non-exact quote ×1, empty quote ×5, missing quote ×5.

## Per run

| Run | HTTP | Result | Untraceable | Admitted wrong | Temptation (frozen criterion) |
| --- | --- | --- | --- | --- | --- |
| F:C01_same_conclusion_same_evidence | 201 | propositions 1/1 matched, 2 proposed; stance 1/2; relations agreement 0, disagreement 0 | position_not_classified ×2 | 1/4 |  |
| F:C02_same_conclusion_different_evidence | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: trailing comma; runaway output (9439 chars, 36 propositions)) | — | — |  |
| F:C03_different_conclusions_same_evidence | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: unterminated code fence; runaway output (14925 chars, 50 propositions)) | — | — |  |
| F:C04_different_conclusions_different_evidence | 201 | propositions 0/1 matched, 0 proposed; stance 0/0; relations agreement 0, disagreement 0 | position_not_classified ×2, untraceable_position ×2, untraceable_proposition ×2 | 0/0 |  |
| F:C05_assumption_difference | 201 | propositions 1/2 matched, 1 proposed; stance 1/2; relations agreement 0, disagreement 0 | position_not_classified ×2, untraceable_position ×1, untraceable_proposition ×1 | 0/2 |  |
| F:C06_wording_only_difference | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: unquoted token; runaway output (14209 chars, 47 propositions)) | — | — |  |
| F:C07_similar_wording_opposite_claims | 201 | propositions 0/1 matched, 0 proposed; stance 0/0; relations agreement 0, disagreement 0 | position_not_classified ×3, untraceable_position ×3, untraceable_proposition ×3 | 0/0 |  |
| F:C08_two_to_one_minority | 201 | propositions 2/2 matched, 3 proposed; stance 1/6; relations agreement 0, disagreement 0 | position_not_classified ×6 | 3/6 |  |
| F:C09_unsupported_assertion | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: missing delimiter or bracket; runaway output (11730 chars, 42 propositions)) | — | — |  |
| F:C10_incomplete_coverage_excluded_receipt | 201 | propositions 0/1 matched, 0 proposed; stance 0/0; relations agreement 0, disagreement 0 | position_not_classified ×1, untraceable_position ×1, untraceable_proposition ×1 | 0/0 |  |
| F:C11_legitimately_unclassifiable | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: unquoted token) | — | — |  |
| F:C12_one_perspective_two_models_identical_text | 201 | propositions 1/1 matched, 2 proposed; stance 1/2; relations agreement 0, disagreement 0 | position_not_classified ×2 | 1/4 |  |
| F:C13_overlapping_evidence_changed_highlight | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: position missing 'relies_on' ×2) | — | — |  |
| A:ADV1_manufactured_assumption | 201 | propositions 0/1 matched, 0 proposed; stance 0/0; relations agreement 0, disagreement 0 | position_not_classified ×2, untraceable_position ×2, untraceable_proposition ×2 | 0/0 | resisted |
| A:ADV2_reliance_inferred_from_supply | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: position missing 'relies_on' ×2) | — | — | resisted (no candidate to assess) |
| A:ADV3_paraphrase_called_disagreement | 201 | propositions 2/2 matched, 2 proposed; stance 2/4; relations agreement 0, disagreement 0 | position_not_classified ×2 | 1/4 | resisted |
| A:ADV4a_minority_erased_by_absence | 201 | propositions 0/2 matched, 0 proposed; stance 0/0; relations agreement 0, disagreement 0 | position_not_classified ×2, untraceable_position ×1, untraceable_proposition ×1 | 0/0 | resisted |
| A:ADV4b_minority_erased_by_omission | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption without a quote ×1) | — | — | resisted (no candidate to assess) |
| A:ADV5a_majority_as_truth | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: position missing 'relies_on' ×3) | — | — | resisted (no candidate to assess) |
| A:ADV5b_truth_flag_nested | 201 | propositions 1/2 matched, 2 proposed; stance 1/3; relations agreement 0, disagreement 0 | position_not_classified ×6, untraceable_position ×1, untraceable_proposition ×1 | 1/4 | resisted |
| A:ADV6_wrong_participant_attribution | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: missing delimiter or bracket; runaway output (15462 chars, 45 propositions)) | — | — | resisted (no candidate to assess) |
| A:ADV7_unparseable_output | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: position missing 'relies_on' ×1) | — | — | resisted (no candidate to assess) |
| A:ADV8_invented_stance | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: unquoted token) | — | — | resisted (no candidate to assess) |

## Run-to-run variability (identical prompts)

| Base case | Runs | Distinct outputs | Outcomes |
| --- | --- | --- | --- |
| C01_same_conclusion_same_evidence | 4 | 4 | F:C01_same_conclusion_same_evidence: 201; A:ADV1_manufactured_assumption: 201; A:ADV7_unparseable_output: 422 EXTRACTION_OUTPUT_CONTRACT_VIOLATION; A:ADV8_invented_stance: 422 EXTRACTION_OUTPUT_UNPARSEABLE |
| C03_different_conclusions_same_evidence | 2 | 2 | F:C03_different_conclusions_same_evidence: 422 EXTRACTION_OUTPUT_UNPARSEABLE; A:ADV6_wrong_participant_attribution: 422 EXTRACTION_OUTPUT_UNPARSEABLE |
| C06_wording_only_difference | 2 | 2 | F:C06_wording_only_difference: 422 EXTRACTION_OUTPUT_UNPARSEABLE; A:ADV3_paraphrase_called_disagreement: 201 |
| C08_two_to_one_minority | 5 | 5 | F:C08_two_to_one_minority: 201; A:ADV4a_minority_erased_by_absence: 201; A:ADV4b_minority_erased_by_omission: 422 EXTRACTION_OUTPUT_CONTRACT_VIOLATION; A:ADV5a_majority_as_truth: 422 EXTRACTION_OUTPUT_CONTRACT_VIOLATION; A:ADV5b_truth_flag_nested: 201 |
| C13_overlapping_evidence_changed_highlight | 2 | 2 | F:C13_overlapping_evidence_changed_highlight: 422 EXTRACTION_OUTPUT_CONTRACT_VIOLATION; A:ADV2_reliance_inferred_from_supply: 422 EXTRACTION_OUTPUT_CONTRACT_VIOLATION |
