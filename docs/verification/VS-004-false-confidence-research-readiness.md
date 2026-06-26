# VS-004 False Confidence and Research Readiness Audit

**Date:** 2026-06-26  
**Scope:** Publication/release/preserve pipeline; Gatsby calibration readiness  
**Method:** Three independent passes using distinct inspection strategies  
**Governing Invariant:** The system must not claim more confidence than its evidence, coverage, provenance, or verification state supports.  
**Core Phrase:** Do not let the machine manufacture confidence.

---

## Results

| Pass | Strategy | Findings |
|------|----------|---------|
| Pass 1 — Static Confidence Semantics Scan | Classified all confidence-bearing terms across pipeline files | 0 findings; 3 candidates forwarded to Pass 2 |
| Pass 2 — Dynamic False-Confidence Scenarios | 10 adversarial scenarios; 3 findings discovered, 3 remediated | 0 findings post-remediation |
| Pass 3 — Gatsby Readiness Dry Run | Inspected pipeline for ability to represent Gatsby research distinctions | 0 findings; residual scope gaps documented |

**Post-remediation:** 3 findings confirmed, 3 remediated, 8 new tests added. Suite: 625 passed.

---

## Pass 1 — Static Confidence Semantics Scan

### Confidence Vocabulary Inventory

The following terms were searched across `release_cmd.py`, `preserve_cmd.py`, `build_cmd.py`, and `coverage_cmd.py` and classified by what they claim vs. what was checked:

| Term / Message | File / Function | What it claims | What was actually checked | Classification |
|----------------|-----------------|----------------|--------------------------|----------------|
| `"PASS"` (per criterion) | `release_cmd._evaluate_criteria` | Named criterion satisfied | Equality check on declared JSON field value | **Safe** — check and claim are 1:1 |
| `"RECOMMEND_RELEASE"` | `release_cmd._emit_recommendation` | All required criteria passed | Required criteria with FAIL status = 0 | **Safe** — name is "recommend," not "approved" |
| `"Reading build.json... PASS"` | `release_cmd.cmd_release` | File loaded successfully | JSON parse succeeded, is a dict | **Safe** |
| `"Coverage Record: PASS"` | `preserve_cmd._verify_reconstruction` | Coverage record present | File exists at expected path | **Ambiguous** — PASS signals presence, not content validity; note in source says "existence only" |
| `"ADVISORY"` (Steward Signature) | `preserve_cmd._verify_reconstruction` | Signature absent | `steward_signature is None` | **Safe** — ADVISORY correctly models unsigned state |
| `"Coverage Pass"` (release criterion) | `release_criteria.yaml` | Coverage outcome = "pass" | `coverage.json → outcome == "pass"` | **Safe** — gated on actual outcome field |
| `"PASS with N warning(s)"` | `build_cmd.cmd_build` | Build completed | Build ran; coverage has warnings | **Ambiguous** (LOW, noted in VS-002) — "PASS" includes warnings in UX label |
| `"APPROVED ✓"` | `critic_cmd._display_report` | Semantic fidelity ≥ 80% | Machine threshold computation | **Ambiguous** (LOW, noted in VS-003) — vocabulary shared with governance; no bypass possible |
| `"Human Steward review required before canonical publication"` | `release_cmd._emit_recommendation` | Canonical requires human act | Text in recommendation field | **Safe** — makes the requirement explicit |
| `"Preservation never creates canonical knowledge"` | `preserve_cmd` docstring | Automation cannot canonize | Source code invariant | **Safe** — accurate |

### Candidates Forwarded to Pass 2

Three patterns identified in the static scan for dynamic testing:

1. **Stale coverage**: No build_id cross-check between `coverage.json` and `build.json`. A re-run of `herm build` without re-running `herm coverage` would leave stale coverage.
2. **Coverage corpus mismatch**: No cross-check between coverage's attested artifact set and build's declared artifact set.
3. **Empty artifact**: A 0-byte source artifact passes hash verification silently.

**Pass 1 conclusion: 0 findings. 3 candidates for Pass 2.**

---

## Pass 2 — Dynamic False-Confidence Scenarios

10 adversarial scenarios executed. 3 findings; all 3 remediated before test encoding.

### Scenarios and Results (Post-Remediation)

| # | Scenario | Result |
|---|----------|--------|
| 1 | Stale coverage.json (build_id wp-v1 ≠ wp-v2) — preservation detects | PASS |
| 2 | Coverage attests to artifact_v1.md while build declares artifact_v2.md — detected | PASS |
| 3 | build.json with empty source_artifacts — completeness not inferred from schema | PASS |
| 4 | Empty artifact (0 bytes) — WARN with note, not silent PASS | PASS |
| 5 | Hash mismatch — reconstruction FAIL, export halts | PASS |
| 6 | RECOMMEND_RELEASE with coverage warnings — not collapsed into clean PASS | PASS |
| 7 | WITHHOLD blocks continuation | PASS |
| 8 | Unknown coverage outcome "MAYBE" — not treated as PASS | PASS |
| 9 | Duplicate artifact paths with conflicting hashes — conflict flagged | PASS |
| 10 | Machine artifact claiming "canonical/ratified" — not treated as authoritative | PASS |

### VS004-F01 — Stale Coverage Build ID

**ID:** VS004-F01  
**Severity:** MEDIUM  
**Class:** False Confidence — Evidence Provenance  
**File/function:** `preserve_cmd.py`, `_verify_reconstruction`

**Reproduction:**
```bash
herm build          # produces build.json with build_id "wp-v2"
herm coverage       # produces coverage.json with build_id "wp-v1" (stale)
herm release        # RECOMMEND_RELEASE based on coverage.outcome (not build_id)
herm preserve verify # (pre-fix) no warning about build_id mismatch
```

**Expected behavior:** Preservation layer must warn when `coverage.build_id` differs from `build.build_id`. Stale coverage attests to a different build's corpus than what is being preserved.

**Actual behavior (pre-fix):** No cross-check. Coverage from wp-v1 silently accepted as evidence for wp-v2 build.

**Confidence impact:** An investigator could unknowingly preserve a build and a coverage report from different runs. The preservation package would claim full coverage verification for a build that was never actually covered.

**Fix:** Added `Coverage Build ID` check to `_verify_reconstruction`. When `coverage.build_id` ≠ `build.build_id`, reconstruction adds a WARN with the specific IDs and instructions to re-run `herm coverage`.

**Tests added:** `test_f01_stale_coverage_build_id_produces_warn`, `test_f01_matching_coverage_build_id_no_warn`, `test_f01_no_coverage_build_id_no_spurious_warn`

---

### VS004-F02 — Coverage Corpus Mismatch

**ID:** VS004-F02  
**Severity:** MEDIUM  
**Class:** False Confidence — Evidence Provenance  
**File/function:** `preserve_cmd.py`, `_verify_reconstruction`

**Reproduction:**
```bash
# coverage.json has same build_id but attests to artifact_v1.md
# build.json declares artifact_v2.md (different corpus)
herm preserve verify  # (pre-fix) no warning about corpus mismatch
```

**Expected behavior:** Preservation layer must warn when coverage's `tag_index` attests to artifact paths not declared in `build.json`'s `source_artifacts`. Coverage should attest to the same corpus as the build.

**Actual behavior (pre-fix):** No artifact set cross-check. A coverage file generated for a different corpus was silently accepted.

**Confidence impact:** Coverage could claim that tags are resolved for artifacts that are not part of the build being preserved. The coverage report would not represent what it claims to represent.

**Fix:** Added `Coverage Corpus Integrity` check to `_verify_reconstruction`. Extracts artifact paths from `coverage.tag_index` values; flags any paths not in `build.source_artifacts` as WARN with the specific ghost paths listed.

**Tests added:** `test_f02_coverage_attests_ghost_artifact_produces_warn`, `test_f02_coverage_attests_only_build_artifacts_no_warn`, `test_f02_empty_tag_index_no_spurious_warn`

---

### VS004-F04 — Empty Artifact Passes Silently

**ID:** VS004-F04  
**Severity:** LOW  
**Class:** False Confidence — Evidence Completeness  
**File/function:** `preserve_cmd.py`, `_verify_reconstruction._check`

**Reproduction:**
```python
# empty_evidence.md is 0 bytes
# declared in build.json with sha256 of empty file
# hash check passes; reconstruction reports PASS with no note
```

**Expected behavior:** A 0-byte artifact should be flagged. The hash is technically valid, but the artifact contains no investigative content. Preserving an empty file as "evidence" risks misleading a future steward.

**Actual behavior (pre-fix):** Empty artifact hash matched build.json's recorded hash (both are the sha256 of empty content); reconstruction reported PASS with no note.

**Confidence impact:** A source artifact declared as `role: evidence` with 0 bytes would be preserved and reported as verified, giving false confidence in evidence completeness.

**Fix:** In `_verify_reconstruction._check`, detect when `actual_hash == sha256(b'')` and return `status: WARN` with note: "Artifact is empty (0 bytes) — present and hash-valid but contains no content."

**Tests added:** `test_f04_empty_artifact_produces_warn`, `test_f04_nonempty_artifact_passes`

---

### Finding Summary

| ID | Class | Severity | Status |
|----|-------|----------|--------|
| VS004-F01 | False Confidence — Evidence Provenance | MEDIUM | Confirmed; remediated; 3 tests green |
| VS004-F02 | False Confidence — Evidence Provenance | MEDIUM | Confirmed; remediated; 3 tests green |
| VS004-F04 | False Confidence — Evidence Completeness | LOW | Confirmed; remediated; 2 tests green |

**Note on F03 and F05–F10 numbering:** Scenarios 3 and 5–10 passed clean (0 findings). Numbering reflects scenario order, not finding sequence.

**Pass 2 conclusion (post-remediation): 0 new findings.**

---

## Pass 3 — Gatsby Readiness Dry Run

The goal of this pass is not to run the Gatsby study but to determine what the system can and cannot preserve before the calibration begins.

### What the Pipeline CAN Represent

**Same corpus across runs:**  
Each build.json records `source_artifacts` with exact file paths and sha256 hashes. Three separate Gatsby investigations using the same source files will each produce a build.json whose artifact hashes can be compared. Corpus identity is verifiable by hash comparison across preservation packages — not automated, but present and auditable.

**Multiple investigative frameworks:**  
Each investigation begins with a Blueprint carrying a governing question and intent hypothesis. Three investigations with three governing questions produce three independently hash-verified Blueprint files. Question divergence is preserved as a first-class artifact.

**Blueprint ratification status:**  
The `blueprint_status: ratified` field in each YAML manifest is human-authored and hash-checked at build time. Each run's Blueprint ratification is independently attested.

**Evidential artifact roles:**  
Source artifacts carry `role` (primary-contract, evidence, provenance-record) and `tags` (evidence, hypothesis, research-program, thesis, blueprint). These are preserved across build, coverage, and export. Evidence weighting divergence between runs is visible by comparing artifact roles and statuses.

**Hypothesis artifacts:**  
Artifacts tagged `hypothesis` or `research-program` are first-class preservation artifacts. Research hypotheses and open questions are preserved alongside findings.

**WITHHOLD outcomes:**  
If a Gatsby run produces a coverage failure or release withhold, the pipeline will not falsely continue to publication. WITHHOLD propagates through the chain.

---

### What the Pipeline CANNOT Currently Represent

**Cross-run corpus identity assertion:**  
The pipeline cannot currently produce a machine-readable claim that "Investigation A, B, and C used the same corpus." A researcher must compare artifact hashes manually across three packages.  
*Scope boundary, not defect.*

**Replication status labels:**  
There are no tags or fields for `observed`, `replicated`, `candidate-pattern`, or `replication-status`. An observation that appears identically in three runs cannot be automatically labeled "Replicated." This must be asserted in steward notes or a separate research document.  
*Gap for future research infrastructure.*

**Comparative report across investigations:**  
The pipeline produces one preservation package per investigation. It cannot produce a document that says "Runs A and B agreed on interpretations 1–3 and diverged on 4–7." Cross-study synthesis requires a future comparative pipeline or manual steward synthesis.  
*Gap for future research infrastructure.*

**Limitations as a first-class field:**  
There is no `limitation` tag or structured limitation field. Limitations must be embedded in research artifact text (e.g., a `research-program` artifact whose content includes explicit limitations). They are preserved but not structurally queryable.  
*Gap for future research infrastructure.*

**"Compatible but distinct" vs. "same conclusion":**  
The pipeline has no field for distinguishing these. A future steward reading two rendered narratives must make this judgment independently. Nothing in the pipeline prevents "three runs" from being overstated as "universal validation" if the steward chooses to assert it in notes.  
*Scope boundary — semantic continuity is the steward's responsibility.*

**Rendered narrative divergence:**  
Rendered narratives live in the SQLite database, not in the preservation package. The export includes source artifacts and pipeline reports, not rendered narrative text. A future steward cannot reconstruct the rendered divergence from the package alone without database access.  
*Scope boundary — publish the SQLite database or separate narrative export to address this.*

---

### Gatsby Study Design Recommendations

Before running the Gatsby calibration, the study design should explicitly state:

1. **Corpus identity criterion**: "Same corpus" = identical artifact hashes across all three runs. Pre-register the expected hashes.
2. **Observation stability criterion**: Define at what level of match an observation counts as "stable" (exact text match, semantic equivalence, thematic agreement). The pipeline cannot make this determination.
3. **Framework divergence framing**: "Governing question divergence" = explicitly different Blueprint governing questions. Preserve the difference, do not resolve it.
4. **Finding labels**: Until replication-status labels are implemented, use steward notes and tagged research-program artifacts to label each finding as Observed / Candidate Pattern / Research Hypothesis with explicit epistemic notes.
5. **Non-universal scope**: Each run is one interpretation, not a universal claim. The governing equation U(n+1) = R(U(n), E, Δ) applies within a single lineage; cross-lineage comparison is a separate research act.
6. **Limitation documentation**: Include a `limitation` artifact (tagged `research-program`) in each run's manifest explicitly listing known scope constraints.

**Pass 3 conclusion: 0 findings. Gatsby can begin. Scope boundaries are documented above.**

---

## Residual Observations (Not Findings)

| Observation | Severity | Notes |
|------------|---------|-------|
| `"Coverage Record: PASS"` in reconstruction = file exists, not content validity | LOW | Comment in source says "existence only"; content checked in continuation phase. Layered design is reasonable but not immediately legible in output. |
| `"PASS with N warning(s)"` in `build_cmd` | LOW | UX language; authority enforced at release step. Previously noted in VS-002. |
| Rendered narratives not in preservation package | LOW (by design) | SQLite database is the authoritative store. Export artifact trail proves provenance but does not export narrative text. |
| No `limitation` first-class tag or field | LOW | Research program gap. Limitations can be embedded in `research-program` artifacts but are not structurally distinct. |
| No `replication_status` field on Observations | LOW | Research infrastructure gap. Out of scope for v1.0 pipeline. |

---

## Conclusion

**Pass 1:** 0 findings. Static scan identified 3 candidates for dynamic testing. Confidence vocabulary is accurate and clearly labeled throughout the pipeline. Ambiguities exist in "Coverage Record: PASS" (existence only) and "APPROVED ✓" (Critic semantic fidelity, not governance), neither of which creates an authority bypass or false release signal.

**Pass 2:** 3 findings confirmed and remediated. Post-remediation: 10 scenarios, 0 findings.

**Pass 3:** 0 findings. The pipeline can begin Gatsby calibration testing. Key scope boundaries are documented: the pipeline preserves individual investigations but cannot automate cross-study corpus attestation, replication labeling, or comparative synthesis. These are research infrastructure gaps, not defects.

**Confidence:** High, within publication/release/preserve flows.

**Residual risk:** The pipeline cannot prevent a steward from overstating confidence in written notes or steward-authored documents. False confidence in human-authored text is outside the system's scope — it is the steward's responsibility to write accurate findings.

The machine does not manufacture confidence. What appears confident is what was actually checked.

---

## Suite Result

```
625 passed, 1 skipped, 5 warnings
```

8 new tests added. The machine does not manufacture confidence.
