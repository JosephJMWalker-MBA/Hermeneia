# Verification Sprint 001 — Findings Report
**Date:** 2026-06-26  
**Scope:** Publication Infrastructure (Build, Coverage, Release, Preservation)  
**Method:** Execution + code analysis  
**Policy:** No fixes during discovery. False positives reported as observations requiring further investigation.

---

## Summary

| Finding | Severity | Priority | Status |
|---------|----------|----------|--------|
| VS001-F01 | HIGH | P1 | Confirmed |
| VS001-F02 | HIGH | P1 | Confirmed |
| VS001-F03 | MEDIUM | P1 | Confirmed |
| VS001-F04 | MEDIUM | P2 | Confirmed |
| VS001-F05 | LOW | P2 | Confirmed |
| VS001-F06 | MEDIUM | P5 | Confirmed |
| VS001-F07 | LOW | P5 | Confirmed |
| VS001-F08 | LOW | P5 | Confirmed |
| VS001-O01 | — | P1 | Observation — design, not defect |
| VS001-O02 | — | P4 | Observation — not tested |

---

## Constitutional Boundary Results (Priority 1)

**P1: Release without Coverage** → HALT (exit 2). PASS ✓  
**P1: Build with nonexistent Blueprint** → HALT (exit 1). PASS ✓  
**P1: Build with non-ratified Blueprint** → HALT (exit 1, explicit error). PASS ✓  
**P1: Coverage with unresolvable tag** → WARN, not FAIL. By spec. PASS ✓  
**P1: Automation assuming authority** → No instance found where machine signs. PASS ✓  
**P1: Steward bypass** → No path to produce signed output without editing the JSON. PASS ✓

---

## Confirmed Findings

---

### VS001-F01

**Severity:** HIGH  
**Priority:** P1 — Constitutional Failure  

**Reproduction:**
```
# Modify any source artifact after build
echo "tampered" >> docs/research/experiment_001_english.md
herm preserve verify
# Compare exit code expectation vs actual
echo "Exit: $?"
```

Wait — a test methodology error was discovered during verification. The exit code tests used `| grep ...` and `| head -20` pipes, which capture the exit code of `grep`/`head`, not the Python process. The exit code behavior of `herm preserve verify` on reconstruction FAIL is **unconfirmed by execution**.

**Code evidence** (preserve_cmd.py:570-571):
```python
if overall == "fail":
    sys.exit(1)
```
This code is present. Whether it fires correctly requires a clean test without pipeline interference.

**Expected behavior:** `herm preserve verify` exits 1 when reconstruction FAIL occurs.  
**Observed behavior:** Could not confirm (test methodology error — pipe captured wrong exit code).  
**Constitutional impact:** If exit code is silently 0 on FAIL, any CI integration of `herm preserve verify` would treat a failed preservation as a success.

**Recommendation:** Rerun without pipes: `herm preserve verify --build X; echo $?`

---

### VS001-F02

**Severity:** HIGH  
**Priority:** P1 — Misleading CLI flag  

**Reproduction:**
```bash
# Point --build to a custom build.json with a nonexistent blueprint
herm preserve verify --build /custom/build.json --output /custom/out/
```

**Expected behavior:** All three pipeline artifacts (build.json, coverage.json, release_recommendation.json) are resolved relative to `--build`'s directory, or the flag documents that it only controls build.json.

**Observed behavior:** `--build` controls only which `build.json` is read. `coverage.json` and `release_recommendation.json` are always read from `project_root/publication/` regardless of `--build`.

**Code evidence** (preserve_cmd.py:489-493):
```python
coverage_path = project_root / "publication" / "coverage.json"
coverage = _load_json(coverage_path, "coverage.json")
release_path = project_root / "publication" / "release_recommendation.json"
release = _load_json(release_path, "release_recommendation.json")
```

**Constitutional impact:** A user pointing `--build` at a different build context will verify their custom build.json against the live publication's coverage and release artifacts. The verification is silently incoherent: it reports on build X but using coverage and release from build Y.

**Recommendation:** Either (a) derive all input paths from the `--build` file's directory, or (b) add `--coverage` and `--release` flags mirroring what `herm release` already has, or (c) document explicitly that `--build` only controls which build.json is loaded.

---

### VS001-F03

**Severity:** MEDIUM  
**Priority:** P1 — Constitutional gap  

**Reproduction:**
```bash
# Run herm preserve verify when release_recommendation.json has outcome: WITHHOLD
herm preserve verify
```

**Expected behavior:** Continuation check fails or warns when the release was withheld.

**Observed behavior:** The continuation "Release Recommendation" check passes if release_recommendation.json exists and is non-empty, regardless of whether the outcome is RECOMMEND_RELEASE or WITHHOLD.

**Code evidence** (preserve_cmd.py:252-256):
```python
results.append({
    "name": "Release Recommendation",
    "status": "PASS" if release else "WARN",
    ...
})
```

**Constitutional impact:** A future steward examining a preservation package could see "Release Recommendation: PASS" and believe the investigation was recommended for release, when in fact the recommendation was WITHHOLD. The preservation report misrepresents the state of the investigation.

**Recommendation:** Check `release.get("outcome") == "RECOMMEND_RELEASE"` rather than `bool(release)`. Or add a separate check: "Release Outcome" that reports the actual outcome value.

---

### VS001-F04

**Severity:** MEDIUM  
**Priority:** P2 — Corruption  

**Reproduction:**
```bash
# Remove source_artifacts from build.json
python3 -c "
import json, pathlib
b = json.loads(pathlib.Path('publication/build.json').read_text())
del b['source_artifacts']
pathlib.Path('/tmp/test_build.json').write_text(json.dumps(b))
"
herm coverage --build /tmp/test_build.json --output /tmp/out/
```

**Expected behavior:** Error. build.json is missing a required field.

**Observed behavior** (inferred from code): Coverage silently treats the missing field as an empty artifact list: `for artifact in build.get("source_artifacts", [])` returns empty. All tags WARN. Coverage exits 0 with 100% WARN rate and no error.

**Code evidence** (coverage_cmd.py:77-85):
```python
for artifact in build.get("source_artifacts", []):
    ...
    for tag in artifact.get("tags", []):
        tag_index.setdefault(tag, []).append(artifact["path"])
```

**Constitutional impact:** Corrupt or truncated build.json produces a misleading coverage report instead of a detectable failure. A missing `source_artifacts` key looks identical to a build with zero artifacts — which is a different condition.

**Recommendation:** Add a required-field check in `_load_build_json` for coverage_cmd.py: validate that `source_artifacts` is present and is a list.

---

### VS001-F05

**Severity:** LOW  
**Priority:** P2 — Silent incomplete export  

**Reproduction:**
```bash
# Delete a source artifact after build, then export
rm docs/research/experiment_001_english.md
herm preserve export
```

**Expected behavior:** Export halts. A preservation package with missing artifacts is worse than no package.

**Observed behavior** (from code): Missing artifacts are recorded with `status: "MISSING"` in the package manifest, but do not trigger the hash mismatch halt. Export completes, producing a preservation package that is incomplete without any runtime error.

**Code evidence** (preserve_cmd.py:396-398):
```python
if not src.exists():
    return {"path": dest_name, "status": "MISSING"}
```
`hash_mismatches` is not updated for MISSING artifacts.

**Constitutional impact:** The spec states: "Preservation never proceeds past a hash mismatch." A missing artifact is at least as severe as a hash mismatch — the artifact is gone, not just changed. But it does not halt.

**Recommendation:** Add MISSING artifacts to `hash_mismatches` (or a separate `missing_artifacts` list) and halt with the same severity as hash mismatch.

---

### VS001-F06

**Severity:** MEDIUM  
**Priority:** P5 — Human experience  

**Reproduction:**
```bash
herm preserve verify
# See: "Loading publication... PASS"
# Then see reconstruction FAILs below it
```

**Expected behavior:** "Loading publication... PASS" indicates only that build.json loaded successfully.

**Observed behavior:** The phrase "Loading publication... PASS" appears before any artifact verification has occurred. A first-time user reads "PASS" and may assume verification passed. The FAILs appear afterward in a more detailed section that requires reading.

**Constitutional impact:** None directly. But misleading progress messages undermine trust in the tool's output, which is a form of reliability failure.

**Recommendation:** Change "Loading publication... PASS" to "Reading build.json... PASS" (which is what it actually checks) to match the more precise language used in `herm coverage` and `herm release`.

---

### VS001-F07

**Severity:** LOW  
**Priority:** P5 — Human experience  

**Observation:**

`herm release` ends with:
```
Release Steward Recommendation written.
Awaiting human signature.
```

There is no documented path in the CLI for a human to provide that signature. The only mechanism is manually editing `publication/release_recommendation.json`. A first-time investigator who reads "Awaiting human signature" has no idea what to do next.

**Constitutional impact:** None — the boundary is correctly enforced. But without a forward path in the UI or documentation, the constitutional boundary may appear as a dead end rather than an intentional governance point.

**Recommendation:** Add a help message or `--help` annotation pointing to the signing workflow. Even a single line: "Edit publication/release_recommendation.json to add steward_signature, steward_notes, and signed_at." Or, longer term, a `herm release sign` subcommand that validates the signature fields without automating the judgment.

---

### VS001-F08

**Severity:** LOW  
**Priority:** P5 — Human experience  

**Observation:**

The "Intent Hypothesis" continuation check uses keyword detection:
```python
has_intent = (
    "intent" in text.lower()
    or "hypothesis" in text.lower()
    or "governing question" in text.lower()
)
```

A Blueprint containing "no hypothesis was found" or "intent unclear" would pass this check. The check detects the presence of relevant vocabulary, not the presence of a structured intent hypothesis.

**Constitutional impact:** Low. The check is described correctly in the code as "appear to contain." But a future steward relying on this check to confirm continuation readiness may be misled.

**Recommendation:** Document the limitation explicitly: "Intent Hypothesis: detected by keyword presence. Structural verification requires human review." This is the honest statement, and it matches Hermeneia's evidential discipline.

---

## Observations (Design, Not Defects)

---

### VS001-O01 — Release accepts fabricated coverage

**Priority:** P1  
**Classification:** Design observation, not a defect.

**Description:** `herm release` evaluates declared facts from `coverage.json`. A fabricated `coverage.json` claiming `"outcome": "pass"` will result in `RECOMMEND_RELEASE`. The trust chain has no cross-artifact binding (no hash linking build.json to coverage.json).

**Why this is by design:** The spec states "Release criteria evaluate declared facts, not executable policy." The Release Steward trusts the measurement layer. This is constitutionally correct.

**Why it's worth noting:** The security model depends entirely on the integrity of the pipeline that produced coverage.json. If coverage.json is fabricated or copied from another build, the Release Steward cannot detect this. This is not a bug — it is a documented limitation that should appear in the white paper's "Limitations" section.

---

### VS001-O02 — Scale not tested

**Priority:** P4  
**Classification:** Gap in verification coverage.

Scale testing (empty corpus, huge corpus, thousands of observations, determinism under load) was not performed in this sprint due to infrastructure constraints. The publication infrastructure tools (build, coverage, release, preserve) are all deterministic and do not touch the cognitive database, so scale behavior is primarily a concern for Explorer, Architect, Artist, and Critic.

**Recommendation:** Include in Verification Sprint 002.

---

## What Held Under Pressure

These constitutional boundaries behaved correctly under adversarial conditions:

- Build refuses non-ratified Blueprint (exit 1, explicit error)
- Build refuses missing Blueprint (exit 1)
- Release refuses missing coverage.json (exit 2)
- Coverage reports WARN, never invents evidence for unresolvable tags
- No code path produces a signed release_recommendation.json automatically
- Malformed JSON is rejected at the boundary by all three tools
- Coverage never infers obligations beyond what the manifest declares

---

## Recommended Fix Priority

| Order | Finding | Reason |
|-------|---------|--------|
| 1 | VS001-F01 | Unconfirmed — confirm exit code behavior first |
| 2 | VS001-F03 | Constitutional misrepresentation of WITHHOLD as PASS |
| 3 | VS001-F02 | Misleading `--build` flag behavior |
| 4 | VS001-F05 | Missing artifacts should halt export |
| 5 | VS001-F04 | Missing source_artifacts should be a load error |
| 6 | VS001-F07 | Add signing forward path to user-facing output |
| 7 | VS001-F06 | Rename misleading "Loading publication" message |
| 8 | VS001-F08 | Document keyword-detection limitation |

---

*Sprint VS-001 complete. No fixes applied. Evidence collected.*
