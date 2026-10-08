# P7 semantic extraction v1.1 — `hermeneia-phi4-mini:latest`

**Decision (frozen rule): model_limited.** Verdict (frozen thresholds): P7 GOVERNANCE READY / EXTRACTION NOT READY. Governance defects: 0.

Same production route, same local model, same sampling as the v1 baseline (`92475b1`, immutable); only the frozen v1.1 policy differs. Nothing accepted. Scripted output is not counted as model accuracy.

| Measure | v1 baseline | v1.1 | v1.1 scripted ceiling |
| --- | --- | --- | --- |
| Structural refusal rate | 0.52 | 0.87 | 0.00 |
| Multi-participant proposition rate | 0/12 | 1/1 | 10/19 |
| Cross-participant invariant (applicable runs) | 0/18 | 1/18 | 9/9 |
| Agreement recall | 0.00 | 0.00 | 1.00 |
| Disagreement recall | 0.00 | 1.00 | 1.00 |
| Relation recall, all runs (decision rule) | 0/18 | 1/18 | 9/9 |
| Minority preservation (runs) | 0/5 | 0/5 | 1/1 |
| Stance accuracy | 0.37 | 1.00 | 1.00 |
| Evidence reliance P / R | 0.75 / 0.46 | 1.00 / 0.50 | 1.00 / 1.00 |
| Assumption recall | 0.00 | 1.00 | 1.00 |
| Unknown preservation (runs) | 0/6 | 0/6 | 2/2 |
| Admitted but wrong | 7/24 | 0/3 | 0/70 |
| Untraceable content rate | 0.57 | 0.53 | 0.00 |

## Per run

| Run | HTTP | Result | Multi-participant propositions | Admitted wrong |
| --- | --- | --- | --- | --- |
| F:C01_same_conclusion_same_evidence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification missing 'relies_on' ×4) | — | — |
| F:C02_same_conclusion_different_evidence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification missing 'relies_on' ×1, assumption shape or quote ×1) | — | — |
| F:C03_different_conclusions_same_evidence | 201 | matched 1/1, stance 2/2, agreement tp 0, disagreement tp 1, untraceable 0 | 1/1 | 0/3 |
| F:C04_different_conclusions_different_evidence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification missing 'relies_on' ×1, assumption shape or quote ×1) | — | — |
| F:C05_assumption_difference | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×2) | — | — |
| F:C06_wording_only_difference | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification value 'oposes' ×1) | — | — |
| F:C07_similar_wording_opposite_claims | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification value 'oposes' ×1, assumption shape or quote ×1) | — | — |
| F:C08_two_to_one_minority | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification missing 'quote' ×2, classification missing 'relies_on' ×2, participant label 'unknown' ×2) | — | — |
| F:C09_unsupported_assertion | 201 | matched 0/2, stance 0/0, agreement tp 0, disagreement tp 0, untraceable 6 | 0/0 | 0/0 |
| F:C10_incomplete_coverage_excluded_receipt | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×1) | — | — |
| F:C11_legitimately_unclassifiable | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×1) | — | — |
| F:C12_one_perspective_two_models_identical_text | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×1) | — | — |
| F:C13_overlapping_evidence_changed_highlight | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification missing 'quote' ×3, classification value '' ×3, participant label 'unknown' ×3) | — | — |
| A:ADV1_manufactured_assumption | 201 | matched 0/1, stance 0/0, agreement tp 0, disagreement tp 0, untraceable 6 | 0/0 | 0/0 |
| A:ADV2_reliance_inferred_from_supply | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: Illegal trailing comma before end of array at char 352) | — | — |
| A:ADV3_paraphrase_called_disagreement | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification missing 'relies_on' ×1) | — | — |
| A:ADV4a_minority_erased_by_absence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×1) | — | — |
| A:ADV4b_minority_erased_by_omission | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: Expecting value at char 615) | — | — |
| A:ADV5a_majority_as_truth | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×1) | — | — |
| A:ADV5b_truth_flag_nested | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: classification missing 'quote' ×2, classification missing 'relies_on' ×2, participant label 'unknown' ×2) | — | — |
| A:ADV6_wrong_participant_attribution | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×2) | — | — |
| A:ADV7_unparseable_output | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: Illegal trailing comma before end of object at char 377) | — | — |
| A:ADV8_invented_stance | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×1) | — | — |
