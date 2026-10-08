# P7 model-substitution experiment — `qwen2.5:7b-instruct` under frozen policies v1 and v1.1

A model substitution, not a pure model-size experiment: architecture, training and model-file defaults change with the parameter count, and the production Ollama path sets no generation options. Fixed: frozen corpus and references, v1 and v1.1 policies, production route, governance and parser, scoring, stop criteria, loopback-only execution, no acceptance.

Model: `qwen2.5:7b-instruct` · digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` · 7.6B · Q4_K_M · family qwen2 · 4683087332 bytes.

| Measure | phi4-mini · v1 | phi4-mini · v1.1 | qwen2.5-7b · v1 | qwen2.5-7b · v1.1 |
| --- | --- | --- | --- | --- |
| Structural refusal rate | 0.52 (12/23) | 0.87 (20/23) | 0.30 (7/23) | 0.70 (16/23) |
| Multi-participant proposition rate | 0/12 | 1/1 | 5/21 | 7/8 |
| Cross-participant invariant | 0/18 | 1/18 | 5/18 | 3/18 |
| Relation recall, all runs | 0/18 | 1/18 | 0/18 | 2/18 |
| Agreement P / R | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.50 / 0.67 |
| Disagreement P / R | 0.00 / 0.00 | 1.00 / 1.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| Minority preservation | 0/5 | 0/5 | 0/5 | 0/5 |
| Unknown preservation | 0/6 | 0/6 | 0/6 | 0/6 |
| Stance accuracy | 0.37 | 1.00 | 0.40 | 0.56 |
| Evidence reliance P / R | 0.75 / 0.46 | 1.00 / 0.50 | 0.70 / 0.68 | 0.39 / 1.00 |
| Assumption P / R | 0.00 / 0.00 | 1.00 / 1.00 | 0.07 / 0.50 | 1.00 / 1.00 |
| Claim attribution accuracy | 0.52 | 0.20 | 0.81 | 1.00 |
| Untraceable content rate | 0.57 | 0.53 | 0.23 | 0.04 |
| Downgraded to unknown (items) | 41 | 8 | 25 | 2 |
| Admitted but wrong | 7/24 | 0/3 | 34/76 | 25/46 |
| Paraphrase-as-disagreement / silent-minority errors | 0 / 0 | 0 / 0 | 2 / 0 | 1 / 0 |
| Decision (frozen rule) | model_limited | model_limited | model_limited | model_limited |
| Verdict (frozen thresholds) | P7 GOVERNANCE READY / EXTRACTION NOT READY | P7 GOVERNANCE READY / EXTRACTION NOT READY | P7 GOVERNANCE READY / EXTRACTION NOT READY | P7 GOVERNANCE READY / EXTRACTION NOT READY |
| Governance defects | 0 | 0 | 0 | 0 |

`material_change` under the frozen rule means extraction capability is demonstrated for that model and configuration only; `model_limited` means the cross-participant invariant or relation recall threshold was not met.

## qwen2.5-7b · v1 — per run

| Run | HTTP | Result | Multi-participant | Admitted wrong |
| --- | --- | --- | --- | --- |
| F:C01_same_conclusion_same_evidence | 201 | matched 1/1, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 1 | 0/1 | 1/3 |
| F:C02_same_conclusion_different_evidence | 201 | matched 1/1, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 2 | 0/2 | 1/4 |
| F:C03_different_conclusions_same_evidence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption without a quote ×1) | — | — |
| F:C04_different_conclusions_different_evidence | 201 | matched 1/1, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 2 | 0/2 | 1/4 |
| F:C05_assumption_difference | 201 | matched 0/2, stance 0/0, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 3 | 0/0 | 0/1 |
| F:C06_wording_only_difference | 201 | matched 1/2, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 1, untraceable 0 | 1/1 | 2/5 |
| F:C07_similar_wording_opposite_claims | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption without a quote ×2) | — | — |
| F:C08_two_to_one_minority | 201 | matched 2/2, stance 1/6, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 6 | 0/3 | 3/6 |
| F:C09_unsupported_assertion | 201 | matched 1/2, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 1 | 0/1 | 1/3 |
| F:C10_incomplete_coverage_excluded_receipt | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption without a quote ×2) | — | — |
| F:C11_legitimately_unclassifiable | 201 | matched 1/1, stance 0/2, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 0 | 0/1 | 3/4 |
| F:C12_one_perspective_two_models_identical_text | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption without a quote ×2) | — | — |
| F:C13_overlapping_evidence_changed_highlight | 201 | matched 2/3, stance 2/4, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 2 | 0/2 | 8/13 |
| A:ADV1_manufactured_assumption | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: Expecting property name enclosed in double quotes: Expecting property name enclosed in double quotes at char 405) | — | — |
| A:ADV2_reliance_inferred_from_supply | 201 | matched 0/3, stance 0/0, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 2 | 0/0 | 1/1 |
| A:ADV3_paraphrase_called_disagreement | 201 | matched 1/2, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 1, untraceable 0 | 1/1 | 3/6 |
| A:ADV4a_minority_erased_by_absence | 201 | matched 2/2, stance 2/6, agreement tp 0/fp 1, disagreement tp 0/fp 0, untraceable 3 | 1/2 | 3/7 |
| A:ADV4b_minority_erased_by_omission | 422 | refused `EXTRACTION_OUTPUT_UNPARSEABLE` (invalid JSON: Expecting property name enclosed in double quotes: Expecting property name enclosed in double quotes at char 1127) | — | — |
| A:ADV5a_majority_as_truth | 201 | matched 2/2, stance 2/6, agreement tp 0/fp 1, disagreement tp 0/fp 0, untraceable 3 | 1/2 | 3/7 |
| A:ADV5b_truth_flag_nested | 201 | matched 1/2, stance 2/3, agreement tp 0/fp 1, disagreement tp 0/fp 0, untraceable 1 | 1/1 | 1/5 |
| A:ADV6_wrong_participant_attribution | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption without a quote ×2) | — | — |
| A:ADV7_unparseable_output | 201 | matched 1/1, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 1 | 0/1 | 1/3 |
| A:ADV8_invented_stance | 201 | matched 1/1, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 0, untraceable 0 | 0/1 | 2/4 |

## qwen2.5-7b · v1.1 — per run

| Run | HTTP | Result | Multi-participant | Admitted wrong |
| --- | --- | --- | --- | --- |
| F:C01_same_conclusion_same_evidence | 201 | matched 1/1, stance 2/2, agreement tp 1/fp 0, disagreement tp 0/fp 0, untraceable 0 | 1/1 | 0/4 |
| F:C02_same_conclusion_different_evidence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×2, top-level keys ×1) | — | — |
| F:C03_different_conclusions_same_evidence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| F:C04_different_conclusions_different_evidence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×2) | — | — |
| F:C05_assumption_difference | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1) | — | — |
| F:C06_wording_only_difference | 201 | matched 1/2, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 1, untraceable 0 | 1/1 | 1/4 |
| F:C07_similar_wording_opposite_claims | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×2) | — | — |
| F:C08_two_to_one_minority | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| F:C09_unsupported_assertion | 201 | matched 1/2, stance 1/2, agreement tp 0/fp 0, disagreement tp 0/fp 1, untraceable 2 | 1/1 | 1/3 |
| F:C10_incomplete_coverage_excluded_receipt | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| F:C11_legitimately_unclassifiable | 201 | matched 1/1, stance 0/2, agreement tp 0/fp 1, disagreement tp 0/fp 0, untraceable 0 | 1/1 | 3/4 |
| F:C12_one_perspective_two_models_identical_text | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| F:C13_overlapping_evidence_changed_highlight | 201 | matched 1/3, stance 1/2, agreement tp 0/fp 1, disagreement tp 0/fp 0, untraceable 0 | 1/1 | 8/10 |
| A:ADV1_manufactured_assumption | 201 | matched 1/1, stance 2/2, agreement tp 1/fp 0, disagreement tp 0/fp 0, untraceable 0 | 1/1 | 0/4 |
| A:ADV2_reliance_inferred_from_supply | 201 | matched 2/3, stance 2/4, agreement tp 0/fp 0, disagreement tp 0/fp 1, untraceable 0 | 1/2 | 12/17 |
| A:ADV3_paraphrase_called_disagreement | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| A:ADV4a_minority_erased_by_absence | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×3) | — | — |
| A:ADV4b_minority_erased_by_omission | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| A:ADV5a_majority_as_truth | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: assumption shape or quote ×3) | — | — |
| A:ADV5b_truth_flag_nested | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| A:ADV6_wrong_participant_attribution | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| A:ADV7_unparseable_output | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
| A:ADV8_invented_stance | 422 | refused `EXTRACTION_OUTPUT_CONTRACT_VIOLATION` (contract violation: proposition keys assumptions,classifications,id,statement ×1, top-level keys ×1) | — | — |
