# Original C-001 oracle, rerun against the repaired branch

The preserved C-001 archive (`~/Documents/Hermeneia-Evidence/C001/20260913T194701Z`, outside this repository) was **read only**; nothing in it was changed. Its `attempt-03` evaluator files were copied into a scratch directory and checked against the archive's `evaluator-lock.json`:

| File | SHA-256 | Matches lock |
|---|---|---|
| `evaluate.py` | `6d1d63df…e79497` | yes |
| `fixtures.json` (oracle) | `c021664e…5d92052` | yes |
| `render_adapter.js` | `d41be2c8…d93133d` | yes (control and run A) |

The evaluator's target is fixed by layout (`REPO = BASE/'baseline'`), so each run placed a detached checkout at `baseline/`. `evaluate.py` and `fixtures.json` were byte-identical in every run, and no fixture expectation changed.

## Runs

| Run | Target | Adapter | Result |
|---|---|---|---|
| Control | frozen `73bd76a` | unchanged (locked) | **10/18**: API path 10/15, boundary 0/3, positives 5/9. Same fixtures and failures as the archived baseline. |
| A | repaired `de34c1a` | unchanged (locked) | **Did not score.** Crashed on the first fixture with `ReferenceError: _crMachineRangeForBlock is not defined` (see `unchanged-adapter-de34c1a-node-failure.json`). |
| B | repaired `de34c1a` | locked adapter plus 3 function names | **18/18**: API path 15/15, boundary 3/3, positives 9/9. Evaluator controls passed. |

### Why run A cannot score, and what run B changes

`render_adapter.js` copies a **fixed list** of production functions out of `index.html` and runs them verbatim. The repaired renderer calls three new production helpers that the list doesn't include, so the locked adapter cannot load them. This is an extraction-plumbing limit; it says nothing about whether the repaired behaviour is correct or incorrect.

Run B's entire change is one added line (`render_adapter-names.diff`):

```diff
+  '_crProjectSourceBoundary','_crWithoutWhitespace','_crMachineRangeForBlock',
```

These names are extracted **verbatim from the repaired `index.html`**, like every other listed function. The adapter still implements no matching, projection or scoring. The fixtures, expected marks, parser, scorer and controls are unchanged. Even so, run B used a **modified adapter**, so it is reported as its own evidence level. It is not a claim that the locked evaluator ran unchanged.

### Invariants (run B)

Tracked checkout files, canonical rows, and full database bytes were unchanged through reads and rendering. The lens toggle was reversible.

### Reproducibility

Each of the control and run B was executed twice. Across both runs, API responses, rendered output and per-fixture results were byte-identical. `fixture.sqlite`, `database_sha256`/`logical_sha256`, and the path-bearing `node-execution.json` differ between runs, and they do so identically on the frozen control: the same 72 files. That variation comes from the harness, not the repair. Canonical row digests matched.

## Evidence hierarchy for this repair

1. **Original C-001 oracle → repaired branch:** 18/18 with a three-name adapter extraction extension (run B). The locked adapter alone cannot load the repaired renderer (run A).
2. **Independently reconstructed suite → repaired branch:** 15/15 API, 3/3 boundary (`../after_repair.json`).
3. **Browser smoke → repaired branch:** passed (see PR).
