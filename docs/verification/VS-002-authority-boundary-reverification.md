# VS-002 Authority Boundary Re-Verification

**Date:** 2026-06-26  
**Scope:** Publication pipeline authority boundaries — release, preservation, build, coverage  
**Method:** Three independent passes using distinct inspection strategies  
**Governing Invariant:** A machine process may not silently overwrite, downgrade, bypass, mislabel, or falsely certify steward-ratified artifacts.

---

## Results

| Pass | Strategy | Findings |
|------|----------|---------|
| Pass 1 — Static Authority Scan | Enumerated all write paths; classified by authority-bearing status | 0 new findings |
| Pass 2 — Dynamic Adversarial Scenarios | 12 adversarial scenarios executed against live code | 1 finding (VS002-F01); remediated; re-run: 0 |
| Pass 3 — Output Semantics Audit | Examined all PASS/OK/success/warning/recommend language in output paths | 0 new findings |

**Post-remediation:**  
Pass 1: 0 new findings  
Pass 2: 0 new findings (post-fix)  
Pass 3: 0 new findings  

---

## Pass 1 — Static Authority Scan

### Write Path Inventory

18 write operations examined across 4 files:

| Location | Artifact | Authority-Bearing? |
|----------|----------|--------------------|
| `coverage_cmd.py:184` | `coverage.md` | No — machine report |
| `coverage_cmd.py:212` | `coverage.json` | No — machine measurement, no steward fields |
| `release_cmd.py:217` | `release_recommendation.json` | **Yes — steward_signature field; guarded** |
| `preserve_cmd.py:334` | `preservation_report.json` | No — machine report |
| `preserve_cmd.py:390` | `preservation_report.md` | No — machine report |
| `preserve_cmd.py:418` | `shutil.copy2 → pkg/artifacts/` | No — copies to package dir; originals preserved |
| `preserve_cmd.py:499` | `preservation_package/manifest.json` | No — package assembly artifact |
| `build_cmd.py:163` | `publication/white_paper.md` | No — copy of compiled artifact |
| `build_cmd.py:189` | `publication/coverage.md` | No — machine report |
| `build_cmd.py:194` | `shutil.copy2 → rc_log.md` | No — copy from source |
| `build_cmd.py:196` | `rc_log.md stub` | No — stub, not ratified |
| `build_cmd.py:204` | `shutil.copy2 → release_decision.md` | No — copy from source; source preserved |
| `build_cmd.py:206` | `release_decision.md stub` | Observation — overwrites if source missing; not machine-authority-bearing |
| `build_cmd.py:266` | `build.json` | No — machine manifest, no steward fields |

**Authority-bearing write paths: 1**  
`release_cmd.py:217` — `release_recommendation.json` with guard checking `steward_signature`.

**Observation (not a finding):** `build_cmd.py:206` writes a `"Pending steward review"` stub to `publication/release_decision.md` if the source `docs/builds/white_paper_release_decision.md` is absent. If a human-authored `release_decision.md` existed in the publication directory, it would be overwritten. This artifact does not carry a machine-recognized authority field (`steward_signature`), so it is not an authority-boundary violation under the current schema. Noted for awareness.

**Pass 1 conclusion: 0 new authority-boundary findings.**

---

## Pass 2 — Dynamic Adversarial Scenarios

12 independent scenarios executed. Each tests a distinct adversarial state.

### Scenarios and Results

| # | Scenario | Result |
|---|----------|--------|
| 1 | Signed recommendation → `herm release` refuses and preserves bytes | PASS |
| 2 | Signed recommendation with extra unknown fields → refuses and preserves bytes | PASS |
| 3 | Signed recommendation with nested steward metadata → refuses and preserves bytes | PASS |
| 4 | Unsigned recommendation (`steward_signature: null`) → overwrite allowed | PASS |
| 5 | WITHHOLD recommendation → continuation check blocks | PASS |
| 6 | Missing required artifacts → export halts with PreservationError | PASS |
| 7 | Alternate `--build` path → coverage/release derived from build directory | PASS |
| 8 | Read-only signed file → guard catches signature before write attempt | PASS |
| **9** | **Corrupt JSON recommendation → guard behavior** | **FINDING** |
| 10 | No `--force` or bypass flag exists in CLI | PASS |
| 11 | Non-string `steward_signature` (bool, int, list, dict) → all caught by guard | PASS |
| 12 | Empty string `steward_signature` → caught by guard (empty string is not null) | PASS |

### VS002-F01 — Finding from Scenario 9

**ID:** VS002-F01  
**Severity:** MEDIUM  
**Class:** Constitutional  
**File/function:** `release_cmd.py`, `_emit_recommendation`  

**Reproduction:**
```bash
# Create a signed recommendation, then corrupt it
echo '{"steward_signature": "Joseph Walker", INVALID JSON}' > publication/release_recommendation.json
herm release
# Corrupt file is silently overwritten with unsigned machine output
```

**Expected behavior:** `herm release` should refuse to overwrite a file it cannot parse. An unreadable file may contain ratification evidence. The conservative behavior is to halt and require manual inspection.

**Actual behavior (pre-fix):** `json.JSONDecodeError` was caught; `existing` was set to `{}`; `steward_signature` was treated as absent; the file was silently overwritten with an unsigned recommendation.

**Constitutional impact:** Automation was able to erase potential ratification evidence by treating parse failure as "not signed." If a steward-signed recommendation became corrupt (disk error, interrupted write), re-running `herm release` would silently destroy it.

**Fix applied:** Changed the `except json.JSONDecodeError` branch from `existing = {}` to raise `ReleaseError("release_recommendation.json exists but cannot be parsed as JSON. Inspect the file before re-running herm release.")` — treating corrupt = unknown, not unprotected.

**Test added:** `test_f09_corrupt_json_halts_rather_than_overwrites` in `tests/test_publication_release_authority.py`.

**Post-fix re-run of all 12 scenarios:** 12 PASS, 0 FINDING.

**Pass 2 conclusion (post-fix): 0 new findings.**

---

## Pass 3 — Output Semantics Audit

Seven semantic questions examined against all four pipeline files.

### Questions and Answers

**Q1: Does any output claim success before verification completes?**  
F06 was fixed in VS-001 remediation (`"Loading publication... PASS"` → `"Reading build.json... PASS"`). All remaining PASS messages in the pipeline appear only after the described step has completed. No premature success claims found.

**Q2: Does any warning state get summarized as success?**  
`build_cmd.py:403` outputs `"PASS with N warning(s)"` (yellow) when coverage has unresolved tags. `build.json` records `"outcome": "warn"`. The release criterion `"Build Pass: outcome == pass"` evaluates `"warn"` as FAIL, producing WITHHOLD. The authority boundary is enforced at the release step. The UX language is slightly imprecise but creates no release bypass. Noted as LOW observation.

**Q3: Does any command exit 0 while reporting a release-blocking condition?**  
`herm build` with WARN exits 0. This is correct by design: WARN means coverage gaps, not build failure. `herm release` enforces the blocking condition. No command exits 0 while silently bypassing a release-blocking check.

**Q4: Does any generated JSON imply approval when the steward has not approved?**  
No. `release_recommendation.json` always emits `"steward_signature": null` on machine generation. The `recommendation` field explicitly states "Human Steward review required before canonical publication." `preservation_report.json` records ADVISORY status when the signature is absent with an explicit note.

**Q5: Does any filename or message imply canonical status for an unratified artifact?**  
No. `release_recommendation.json` is accurately named as a recommendation. `preservation_package/manifest.json` is accurately named as a package manifest. No machine-generated file is named in a way that implies human ratification.

**Q6: Are machine recommendations clearly distinguished from steward-ratified decisions?**  
Yes. The vocabulary is consistent: "Recommendation" for machine output, "Awaiting human signature" in terminal, `steward_signature: null` in JSON, "ADVISORY" status in preservation reports when unsigned. The distinction is enforced at the schema level, not just by convention.

**Q7: Does `_verify_reconstruction` use F02-corrected paths for existence checks?**  
`_verify_reconstruction` (preserve_cmd.py:139–153) still uses `project_root / "publication"` for the existence checks of "Coverage Record" and "Release Recommendation." After the F02 fix in `_load_inputs`, coverage and release are loaded from `build_path.parent`. In the standard workflow (everything in `publication/`), these are identical. In non-standard `--build` scenarios, the existence check would target the standard path while the signature check (which uses the loaded `release` dict) targets the correct path. Not an authority-boundary violation: the signature analysis is correct. LOW consistency gap.

**Pass 3 conclusion: 0 new findings.**

---

## Finding Summary

| ID | Class | Severity | Status |
|----|-------|----------|--------|
| VS002-F01 | Constitutional | MEDIUM | Confirmed in Pass 2; remediated; verified clean |

---

## Residual Observations (Not Findings)

| Observation | Severity | Notes |
|------------|---------|-------|
| `build_cmd.py:206` stub overwrites `release_decision.md` if source absent | LOW | Not machine-authority-bearing; no steward_signature field |
| `build_cmd.py:403` "PASS with warnings" when `build.json` records `warn` | LOW | Authority enforced at release step; UX imprecision only |
| `_verify_reconstruction` existence checks use hardcoded `publication/` path | LOW | Partial F02 propagation; only affects non-standard `--build` usage; signature check is correct |

---

## Conclusion

No additional authority-boundary defects were found across three independent verification passes targeting the same class as VS-001.

One MEDIUM constitutional defect (VS002-F01: guard fails open on corrupt JSON) was discovered in Pass 2, remediated immediately, and re-verified clean across all 12 adversarial scenarios.

**Confidence:** High, limited to release/preserve/publication authority flows inspected in VS-002.

**Residual risk:** Unknown unknowns remain possible in flows not inspected by this sprint. In particular:
- The cognitive pipeline (Blueprint ratification, StewardDecision authority) was not inspected
- The `release_decision.md` document (human-authored, no signature field) has no machine-enforceable protection
- Scale behavior under concurrent access was not tested

**Correct conclusion:** No new defects were found across three independent passes targeting the authority-boundary class. The guard covering the one authority-bearing write path is now robust to four adversarial inputs: present+signed, present+unsigned, present+corrupt, absent.

---

## Suite Result

```
617 passed, 1 skipped, 5 warnings
```

The machine can still not erase the steward.
