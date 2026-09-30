# Read-only Perspective achievement evaluation v1 — bounded P4

Date: 2026-09-30. Starting commit:
`5217047eb585bbaa3a29d335acd9aaaf04132489`.
Implements only the evaluator packet of
[#215](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/215), under
[#214](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/214) and the unchanged
[frozen rules](perspective-achievement-rules-v1.md). The
[P3 receipt contract](perspective-execution-receipt-v1.md), ADR-0045, Storage and
constitutional read-only/ancestry rules retain authority over the evidence.

**An evaluation is not an award.** No award ID, table, receipt, persisted earned
state, notification, route, UI, badge or WBS component is introduced. The module
does not replace Capability Registry readiness/history or Guided Study Cycle
decisions. It does not mutate receipt semantics or implement later achievement
families, comparison/adjudication, synthesis or coaching.

## Domain seam and evidence boundary

[Evidence adapter](../../hermeneia/perspective_achievement_evidence.py):

```python
evidence = read_perspective_achievement_evidence(conn)
```

`conn` is an existing SQLite connection to the canonical workspace. The adapter
returns frozen `PerspectiveAchievementEvidence` and `RetainedExecutionEvidence`
values. Nested payloads are immutable canonical JSON strings; decoding properties
return fresh values. There is no serialized client-fact ingestion API.

The adapter discovers existing schema, enumerates the full extant receipt category,
uses P3 `receipt_from_row` and `validate_execution_references`, and obtains actual
unfiltered Study Lineage eligibility. It never parses display labels or previews.
It validates the additional frozen built-in/template support, captures typed
dependency row digests and mutable eligibility observations, and derives saved
Perspective families through complete validated ancestry. It neither resolves
Scope again nor reads today's controls as historical execution input.

An owned read transaction spans all queries and ends with rollback. Caller-owned
transactions, including pending work, remain caller-owned. No connection is
created, schema initialized, pragma changed, or DDL/DML executed. Callers can
supply `mode=ro` / `query_only` connections and SQL write guards.

[Pure evaluator](../../hermeneia/perspective_achievements.py):

```python
result = evaluate_perspective_achievements(evidence)
```

It accepts the canonical adapter's typed snapshot, not arbitrary Lineage JSON.
It performs no SQL, filesystem operation, clock capture, provider/model call,
UI action or persistence. Rules are two static versioned declarations exposed by
`perspective_achievement_rules()`, not a generic achievement engine.

The result schema is `hermeneia.perspective-achievement-evaluation/v1`, evaluator
version `1.0.0`. Each item exposes `achievement_id`, `rule_id`, `rule_version`,
qualified `rule_reference`, definition digest, `status`, symbolic `reason_code`,
explanation, exact typed `evidence_refs`, selected `qualifying_receipt_ids`,
coverage, validated dependency/eligibility evidence and deterministic selection
basis. Second Opinion also exposes exact question/Scope comparison bases and
Perspective family/revision/fingerprint/methodology/ancestry evidence.

`rules_sha256` binds static rule metadata, including frozen built-in fingerprints
and template implementation support. `evidence_sha256` binds adapted canonical
receipt bytes, Lineage references, family evidence, required dependency digests,
eligibility observations, classified diagnostics and coverage. These are derived
assessment digests, not award identities or package/release identities. Neither
result duplicates canonical output text. Undisclosed execution configuration and
generic human identity remain unknown.

The released static rule metadata digest is
`sha256:6b0065fac155c40fc25ce5cc62c53a7c250c0595dd4e49554669bab55e56197c`.
Tests pin this definition and ensure callers receive independent metadata copies.

## Exact predicates and support

| Achievement | Rule | Version |
| --- | --- | --- |
| `perspective_explorer` | `achievement.perspective_explorer` | `1.0.0` |
| `second_opinion` | `achievement.second_opinion` | `1.0.0` |

Explorer requires one existing canonical supported P3 receipt that passes every
frozen E(r) check: successful operation, explicit local-steward retention, exact
row/receipt/run and input/output digests, supported immutable Perspective revision,
captured prompt-template binding, durable reference closure, eligible typed
Lineage identity, aware ordered timestamps and extant-category support.

Built-in version `1` support is pinned to the baseline fingerprints for
`close-reader`, `contextual-reader`, `skeptical-reader`; it does not consult a
mutable replacement catalog. Template support pins SHA-256 of the exact UTF-8
source of the actual callable's code for the existing self-contained
`build_perspective_prompt` function:

```text
sha256:26d8533f2d4e9c0235fbfc89f058484b22346b9c08b4139498ae8f4b22432e2e
```

Unavailable or changed template implementation is unsupported before invoking
it. This conservatively prevents today's builder from reinterpreting historical
v1 prompts. Even source edits that preserve behavior require explicit support
review; no semantic-equivalence guess is made. The template's own question trim
is reproduced solely for prompt validation; comparison retains exact captured
question bytes. A changed decorator cannot inherit support by copying the
original function's `__wrapped__` metadata. No duplicate prompt implementation
was introduced.

Second Opinion requires two individually Explorer-valid executions with:

- identical captured UTF-8 question bytes **and** validated question SHA-256;
- identical complete P3 canonical Scope bytes **and** validated Scope SHA-256;
- the supported single-run operation/template, each bound to its captured inputs;
- distinct namespaced families, distinct full definition fingerprints, and
  unequal exact canonical `purpose/questions/challenges/limitations` material.

Saved family keys derive from all existing incoming relation rows back to a
validated frame-v2 root. Missing, cross-type, duplicate, ambiguous or cyclic
ancestry refuses that family comparison; legacy ancestry is unsupported.
Revisions, reversions and sibling revisions share their root. Exact revision
identities remain canonical; the derived root is not a new profile object.
Built-in families use stable namespaced IDs. Model/provider changes alone do
not count. Exact copies, label-only copies and unchanged saved adoptions of a
built-in cannot qualify. Retention does not mean agreement or downstream use.

## Status, coverage and failure handling

The evaluated universe is the full supported **extant eligible retained category**,
never all past activity or a named person's complete history. Missing category or
required reference schema is unsupported; no read creates schema to claim coverage.
An existing supported empty category can return the bounded snapshot negative.
Diagnostics preserve invalid/unsupported/excluded distinctions without copying
excluded text or arbitrary exception messages.

| Status | Meaning |
| --- | --- |
| `earned` | A fully supported independently validated witness exists; no award is written |
| `invalid_evidence` | Required claimed supported evidence is malformed, tampered or contradictory, or source integrity prevents evaluation |
| `unsupported_due_to_missing_coverage` | Required source/category, reference schema, version, eligibility or family support is absent/unknown |
| `not_earned` | No qualifying evidence in this supported, classified extant eligible snapshot under the exact rule version |

Source integrity is checked first. Otherwise a valid existential witness survives
unrelated classified local invalid/unsupported records; those diagnostics stay
visible. Without a witness, known invalidity precedes unsupported coverage, then
the bounded negative. Family-only errors do not invalidate Explorer. For Second
Opinion they prevent a negative when needed to decide an otherwise possible
exact-question/Scope/methodology pair. Already-disproved pairs need no invented
ancestry. Lineage's aggregate omitted count alone never proves absence or
classifies corruption.

If a malformed SQL payload prevents the actual unfiltered Lineage read itself,
the source fails closed globally. In particular a BLOB in the text receipt column
can trigger an existing P3 decoder exception; this adapter returns structured
`invalid_evidence` instead of fabricating a filtered Lineage view or modifying P3.
An otherwise good local pair cannot bypass that missing E(r) visibility proof.

## Deterministic evidence selection

For every E-valid receipt, K is `(retained_at converted to an aware UTC instant,
ASCII receipt ID)`. Original timestamp text is preserved; conversion does not
claim clock accuracy or causal order. Explorer selects minimum K. Second Opinion
enumerates unordered pairs in lexicographic K order and selects the first exact
qualifying pair. Repeated Keep, row insertion order and display filters cannot
inflate evidence or change selection. No interval/session constraint or current
timestamp enters evaluation.

## WBS composition and remaining boundary

No WBS format or code changed. Existing P3 export/restore preserves exact canonical
receipt bytes and required graph references. Integration tests export, restore
through the existing validated transaction, and evaluate the restored database
with the same selected evidence/comparison result. Corrupt claimed receipt
components are refused at the existing bundle-read boundary before use.

This packet has **no direct raw-bundle evaluation API**. `read_bundle` validates
the P3 component/capability/counts but does not by itself validate every generic
dependency file and typed closure. Treating its JSON as canonical adapter facts
would overclaim. No parallel non-SQL Lineage stack or evaluation-time restore was
introduced. Direct bundle evaluation would require its own bounded read-only
dependency/Lineage seam; it is not necessary for canonical-workspace evaluation.

Legacy bundle coverage remains unsupported under its existing contract. Restoring
one may create an empty current receipt table, but that only supports current
extant-category evaluation; it does not reconstruct or upgrade historical coverage.
Zero extant receipts never means the human never used Perspectives.

## Verification

All 36 meaningful frozen matrix classes are represented in **92 new tests** in
[evaluator tests](../../tests/test_perspective_achievements.py) and
[integrity tests](../../tests/test_perspective_achievement_integrity.py). Corruption
fixtures explicitly remove guards only in disposable synthetic databases; no
production append-only rule is weakened.

Before implementation, the initial test collection failed because the new adapter
was absent. The first complete run had 28 passes/48 failures: positive witnesses
exposed tuple data rejected by P3's strict JSON codec; failed canonical executions
also exposed an overly broad unsupported-status classification. Both implementation
errors were repaired without changing frozen rules. A test fixture adding a field
inside P3's exact-key `resolution` object was corrected to use valid captured
Scope material rather than relaxing the codec.

Tests cover exact UTF-8 and complete Scope/order/timestamp differences, saved
revision/branch/reversion ancestry, detectable copies and undetectable paraphrases,
unknown versions, malformed bindings/times, local positive/negative precedence,
source-level refusal, deterministic ties/insertion order, dependency/eligibility
digest binding, WBS composition and unchanged P1/P2 results. A subprocess blocks
provider imports and has no cloud keys; read tests use SQL write guards, read-only
connections, before/after database bytes and logical rows, and caller-transaction
checks. Template drift, including a wrapper carrying the original function's
metadata, is refused without calling the changed builder.

Measured on Python 3.13.5, pytest 9.1.0, Node 22.17.0:

- New evaluator/integrity tests: **92 passed**, 7.01s.
- P1 Capability Registry: **55 passed**.
- P2 Guided Study Cycle: **67 passed**, five existing warnings.
- P3 receipts/API/Lineage/UI/WBS: **123 passed**, five existing warnings.
- Existing Study Lineage: **75 passed**, five existing warnings.
- WBS export/restore/P3 plus download: **58 passed** (52 + 6), five existing
  warnings in the download group.
- Independent untouched starting archive: **2,228 passed, 21 skipped, six Reader
  failures**, five existing warnings, 106.24s. All 624 tracked files retained their
  original SHA-256 bytes. Local loopback was permitted; default test governance
  blocked external networking and cloud credentials.
- Final full implementation suite: **2,320 passed, 21 skipped, the same six
  Reader failures**, five existing warnings, 105.70s. Independent JUnit failure-ID
  comparison matched the untouched starting archive exactly; 92 additional
  passes correspond to the new tests. All 624 pre-existing tracked files also
  retained their starting bytes in the implementation checkout.

Focused command:
`python3 -m pytest -q tests/test_perspective_achievements.py tests/test_perspective_achievement_integrity.py`.
Baseline and implementation full runs used `python3 -m pytest -q` with separate
JUnit XML outputs for the comparison. `git diff --check` and documentation link
checks also passed. Only the two new production modules, two new test files and
this note are included; no existing schema, WBS, UI or history files changed.

The exact independently reproduced baseline failures are:

```text
tests/test_reader_accessibility.py::test_read_page_button_is_rendered_in_page_header_with_accessible_label
tests/test_reader_accessibility.py::test_failed_or_missing_page_cannot_speak_prior_page_source
tests/test_reader_blueprint_workstation.py::test_blueprint_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_record_view.py::test_record_tab_and_panel_present
tests/test_reader_record_view.py::test_record_is_a_workstation_mode_not_a_separate_drawer
tests/test_reader_voice_profile.py::test_voice_is_a_workstation_mode_not_a_separate_drawer
```

## Known limits and next bounded packet

Complete Scope compilation times/progress metadata intentionally cause conservative
non-qualification; they are not stripped. Exact methodology differences cannot
detect paraphrased duplicates or prove intellectual independence. Generic steward
identity and undisclosed execution defaults stay unknown. Validation is synthetic
and provider-free, not live-model or real-study usability evidence. Missing future
catalog/template support must refuse rather than reinterpret history.

Next recommended packet: review the exact append-only award receipt, identity,
historical-version and portability contract against these evaluation evidence
packages. Do that before schema, writes, WBS award coverage or achievement UI.
Do not loosen the frozen predicates, implement deeper achievements or convert
evaluations into durable awards inside this packet.
