# VS-001 Remediation Report

**Sprint:** Verification Sprint 001  
**Date:** 2026-06-26  
**Tag:** `vs-001-remediation-v0.1`  
**Status:** Remediated  
**Confidence:** High  
**Release impact:** Positive  

---

## 1. Initial Findings

Verification Sprint 001 executed two rounds of adversarial testing against the publication infrastructure (Build, Coverage, Release, Preservation). Eight candidate findings were proposed. One critical finding was discovered during execution rather than before it.

| Finding | Class | Severity | Initial Status |
|---------|-------|----------|----------------|
| F01 | Test Methodology | HIGH | Candidate |
| F02 | UX / API Contract | HIGH | Candidate |
| F03 | Behavioral | MEDIUM | Candidate |
| F04 | Code Analysis | MEDIUM | Candidate |
| F05 | Behavioral | LOW | Candidate |
| F06 | UX | MEDIUM | Candidate |
| F07 | UX | LOW | Candidate |
| F08 | UX | LOW | Candidate |
| F09 | **Constitutional** | **CRITICAL** | Discovered during execution |

---

## 2. Confirmed Defects

Five findings survived contact with execution:

**VS001-F09 — CRITICAL — Signed recommendation overwritten by `herm release`**  
Running `herm release` when `publication/release_recommendation.json` already contained a steward signature silently overwrote the signed artifact with an unsigned machine output. The signature was erased without warning.  
Constitutional impact: Automation downgraded a human-ratified artifact. This violates the core authority model — AI proposes, human ratifies, machine preserves the ratification boundary.

**VS001-F03 — MEDIUM — WITHHOLD passes continuation check as PASS**  
`_verify_continuation` evaluated `bool(release)` rather than the actual `outcome` field. A WITHHOLD recommendation was treated as release approval by the continuation check.

**VS001-F02 — MEDIUM — `--build` flag misleading**  
`_load_inputs` hardcoded `project_root / "publication"` for coverage.json and release_recommendation.json regardless of the `--build` argument. The flag appeared to control all input paths but silently controlled only one.

**VS001-F05 — LOW — `preserve export` completes with missing artifacts**  
Missing artifacts were recorded in the manifest as `status: MISSING` but did not trigger the halt condition. A preservation package could be produced and appear complete while containing gaps.

**VS001-F06 — LOW — Premature PASS message**  
`"Loading publication... PASS"` was printed immediately after loading `build.json`, before any artifact verification occurred. The PASS label was attached to a load operation, not a verification result.

---

## 3. Falsified Candidates

Two candidates did not survive contact with reality. A verification process that never falsifies findings is not testing — it is confirming.

**VS001-F01 — CLEARED**  
Initial testing used piped commands (`| grep`, `| head`). The pipe captured `grep`'s exit code, not the Python process exit code. When retested without pipes, `herm preserve verify` correctly exited 1 on reconstruction FAIL. The code at `sys.exit(1)` was correct.

**VS001-F04 — CLEARED**  
Initial code analysis identified `build.get("source_artifacts", [])` as silently accepting a missing key. Deeper inspection revealed that `_load_build_json` in coverage_cmd.py validates `source_artifacts` as a required field before that code is reached. The defense existed; the analysis read the wrong layer.

---

## 4. New Constitutional Finding

**VS001-F09** was not proposed before testing. It was discovered by causing it: running `herm release` during idempotency testing overwrote the signed `publication/release_recommendation.json` that had been produced as part of the first closed constitutional cycle. The artifact was recovered from git.

This is the correct outcome of adversarial falsification: the test did not merely inspect state. It performed the operation and observed the consequence. The finding was confirmed by the harm it caused.

---

## 5. Fixes Applied

All five confirmed defects were addressed. F07 and F08 (UX, LOW) were deferred — both are documentation improvements rather than behavioral defects.

**F09 — `release_cmd.py`: Authority guard before write**  
`_emit_recommendation` now reads any existing `release_recommendation.json` before writing. If `steward_signature` is non-null, it raises `ReleaseError` with an explicit constitutional message and leaves the file byte-for-byte unchanged. An unsigned or missing recommendation may still be written freely. A malformed JSON file is treated as unprotected.

```
Machine may generate.
Machine may recommend.
Machine may verify.
Machine may refuse.

Machine may not silently erase ratification.
```

**F03 — `preserve_cmd.py`: Outcome check in continuation**  
`_verify_continuation` now evaluates `release.get("outcome") == "RECOMMEND_RELEASE"`. A WITHHOLD recommendation produces WARN with a note naming the actual outcome. An absent release file remains WARN.

**F02 — `preserve_cmd.py`: Path derivation from build directory**  
`_load_inputs` now derives `coverage.json` and `release_recommendation.json` from `build_path.parent`. The `--build` flag now coherently controls all three input artifact paths.

**F05 — `preserve_cmd.py`: Missing artifacts halt export**  
`_run_export` tracks `missing_artifacts` separately alongside `hash_mismatches`. If any declared artifact is absent from the filesystem, export halts with `PreservationError`. A preservation package with missing artifacts would misrepresent the investigation.

**F06 — `preserve_cmd.py`: Accurate progress message**  
`"Loading publication... PASS"` renamed to `"Reading build.json... PASS"`, which is what that step actually verifies.

---

## 6. Tests Added

`tests/test_publication_release_authority.py` — 10 tests encoding the governing invariant:

> A signed or steward-ratified recommendation artifact must not be silently overwritten by automation.

| Test | Finding |
|------|---------|
| `test_f09_signed_recommendation_refuses_overwrite` | F09 |
| `test_f09_signed_artifact_byte_for_byte_unchanged` | F09 |
| `test_f09_unsigned_recommendation_may_be_regenerated` | F09 |
| `test_f09_missing_recommendation_allows_first_write` | F09 |
| `test_f03_withhold_outcome_does_not_pass_continuation` | F03 |
| `test_f03_recommend_release_passes_continuation` | F03 |
| `test_f03_withhold_note_references_actual_outcome` | F03 |
| `test_f02_build_path_controls_coverage_and_release_paths` | F02 |
| `test_f05_export_halts_on_missing_artifact` | F05 |
| `test_f05_export_succeeds_with_all_artifacts_present` | F05 |

---

## 7. Final Verification

```
python3 -m pytest tests/test_publication_release_authority.py -v
10 passed in 0.16s

python3 -m pytest tests/test_preservation.py -v
10 passed in 0.08s

python3 -m pytest --tb=short -q
616 passed, 1 skipped, 5 warnings in 27.40s
```

No regressions. Constitutional boundaries that held before VS-001 continue to hold.

**Boundaries that held under adversarial pressure (unchanged from VS-001 findings):**

- Build refuses non-ratified and missing Blueprints
- Release refuses to run without Coverage
- No automated code path produces a signed artifact
- Malformed JSON is rejected at every boundary
- Coverage reports evidence present; never invents evidence absent

---

## 8. Remaining Concerns

**F07 (deferred):** No forward path documented after `herm release` for providing a human signature. The boundary is correctly enforced; the UX leaves it appearing as a dead end. Address before v1.0 RC.

**F08 (deferred):** Intent hypothesis detection uses keyword presence, not structural verification. The check is honest in code (`appear to contain`) but undocumented. Address in onboarding work.

**VS001-O01 (design observation, not defect):** The Release Steward trusts the declared facts in `coverage.json`. A fabricated `coverage.json` claiming `outcome: pass` will result in `RECOMMEND_RELEASE`. The security model depends on pipeline integrity. This is constitutionally correct and should be documented explicitly in the white paper's Limitations section.

**Ongoing principle:** Future release workflows must continue treating signed and steward-ratified artifacts as authority-bearing objects. The guard in `_emit_recommendation` establishes the pattern; any future artifacts that carry human ratification (signed preservation packages, ratified Blueprints, etc.) should receive the same protection.

---

## Tag

`vs-001-remediation-v0.1` — committed 2026-06-26.

The machine can no longer erase the steward.
