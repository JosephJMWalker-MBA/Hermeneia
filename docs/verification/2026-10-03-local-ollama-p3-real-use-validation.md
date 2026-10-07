# Local Ollama P3 real-use validation — 2026-10-03

**Result:** The explicitly retained real-study execution validates under the
current P3 receipt contract and appears in its existing read-only projections.
This validates retention and provenance mechanics, not interpretive correctness.

- **Commit tested:** `f1fc3a6159eeaf2cc13af2fa70eadf69e5b7a9d7`
- **Safe study alias:** `study-d88c4a642956`
- **Perspective:** built-in Close Reader, `close-reader`, version `1`
- **Provider/model:** `ollama-local` / `hermeneia-phi4-mini:latest`
- **Transport:** Ollama structured `chat`, request schema `1`, SDK `0.6.2`, loopback

The repeat's read-only model-catalog preflight observed the unchanged manifest
digest `df37b15c99cdc5e29db325ee64cb5e3100f58283d30b7d12cc1cf42ae85ffa0f`.
Previously audited GGUF/blob SHA-256:
`3c168af1dea0a414299c7d9077e100ac763370e5a98b3c53801a958a47f0a5db`.
The blob was not rehashed in this Keep packet. These are separate runtime
observations; no additional model identity field was inferred into the receipt.

## Authorization and execution boundary

The steward supplied the real question, selected Close Reader, and explicitly
authorized RUN. Existing Reader source material supplied the bounded Scope; no
study question, evidence, Perspective definition, or prior history was fabricated.
The legacy Reader mark lacked an occurrence locator, so the prepared selection
used explicit Reader-projection coordinates bound to source-extraction identities
without inventing its historical occurrence association.

Normal startup's two empty P3/award table additions received separate explicit
approval. Existing study rows remained unchanged. The initial transient run
became unavailable when its server ended before a retention decision; it was
never retained or reconstructed. The steward then explicitly authorized one
repeat solely to restore the retention checkpoint, with identical question,
Scope, source text, Perspective, model, and effective prompt bytes.

The repeat used the normal production `/api/perspective/run` route once:
HTTP `201`, `17.978133` seconds. Its 2,733-byte UTF-8 prompt matched the approved
frozen prompt byte for byte. Before Keep, all 35 study tables' rows and columns
were unchanged, retained P3 receipts were `0`, and achievement awards were `0`.
No Reader navigation or saved-frame initialization was used for this validation.

After the exact output was shown, the steward explicitly chose KEEP. Exactly one
normal `/retain` request named the original server-owned run and returned HTTP
`201`; no response or input content was reposted or regenerated. The independent
loopback server was left running for and after the retention checkpoint.

No model registration, model/configuration change, download, remote provider
request, Room execution, different Perspective, or achievement award occurred.
The already-validated Ollama adapter was not re-audited or smoke-tested.

## Retained identity and integrity

- Run: `9314a4a3-69d6-4c55-92c3-3644f698b5f6`
- Receipt: `perspective-execution-receipt:sha256:5870a94e4c6717bd8d71f2c1e1b982f45c2570630f25fac7363f3ac3c3c0c45e`
- Schema: `hermeneia.perspective-execution-receipt/v1`
- Prompt: `sha256:262d694297291d677496177cc4e0d7a445c446e586bedabff6ce6f9c70e0b5ed`
- Question: `sha256:7e25fcd5ad8a46eb5c5be7020089e8f53312e643956327350e38a99a88ab6ddb`
- Scope: `sha256:5b35d63bd0bfc13454212db00db7f78630a5d3cd637bf3877fa2d9bd160ba990`
- Response: `sha256:a13929bbf81dbf4cbfca71dcab6ea8b2a0afca177d2774fcbeb535814037a89a`

Current `validate_receipt`, canonical stored-row decoding, and source-reference
eligibility validation passed. The retained question, complete Scope and
materialization, Perspective semantics, execution provenance, prompt, and exact
response matched the approved inputs and transient response. Two subsequent
read-only receipt retrievals returned identical bytes and the same canonical
receipt. Recorded execution and retention timestamps retained their original
meaning and order.

Only `perspective_execution_receipts` changed: `0 → 1`. The other 34 tables'
rows and columns were unchanged after Keep and all read-only verification calls.
`achievement_awards` remained `0 → 0`.

## Existing projections and assessments

Study Lineage contains exactly one corresponding
`retained_perspective_execution`, with `event=recorded`, `authorship=model`,
the receipt and Reader contexts, and recorded input/output digests. Its chronology
uses `retention.retained_at` while separately preserving execution timestamps.
The retention actor is `local_steward`; named human identity remains `unknown`.
Keep is not agreement, Interpretation acceptance, or ratification. The Lineage
content preview is truncated; full response equality was checked through the
receipt rather than its preview.

Guided Study with the explicit current Close Reader selection reports
`explore_perspective` as `historically_exercised`, with supported history. This
was the only step whose status changed from the pre-Keep projection. Current
availability remains `not_yet_available` because no mutable governing question
was saved; the captured execution question was not promoted into that state.

Read-only Perspective Explorer assessment reports `earned` under rule/evaluator
version `1.0.0`, with this receipt as its sole qualifying evidence. Assessment
package digest
`sha256:5ad385a0263ab96678fc405a7c9fea33c87e7ce751e27ad29d53fc946f047c71`
was independently verified. Coverage is one extant eligible retained receipt;
complete historical activity remains `unknown`. This evaluation creates no award
and establishes neither answer quality nor mastery.

Read-only Second Opinion assessment reports `not_earned`, with no qualifying
pair. No additional execution was created to change that result.

## Focused regression checks

**489 passed, 1 deselected, 5 warnings in 16.79 seconds; exit 0.** Tests used
isolated fixture databases and mocked providers. The adapter-specific
`test_ollama_chat_provenance_and_exact_prompt_survive_retention` was deliberately
deselected because its adapter was already validated. No live generation occurred
in the suite.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest -p no:cacheprovider -q \
  tests/test_perspective_runs.py \
  tests/test_perspective_execution_receipts.py \
  tests/test_perspective_execution_api.py \
  tests/test_perspective_execution_lineage.py \
  tests/test_perspective_execution_ui.py \
  tests/test_study_lineage.py \
  tests/test_study_lineage_api.py \
  tests/test_study_lineage_ui.py \
  tests/test_guided_study_cycle.py \
  tests/test_guided_study_cycle_api.py \
  tests/test_guided_study_cycle_ui.py \
  tests/test_perspective_achievements.py \
  tests/test_perspective_achievement_integrity.py \
  tests/test_achievement_award_api.py \
  tests/test_achievement_client_integration.py \
  -k 'not test_ollama_chat_provenance_and_exact_prompt_survive_retention'
```

The full suite was not rerun for this documentation-only packet. The known Reader
baseline was not exercised or reclassified here. No production code changed.

## Negative result and limits

The model response contains source-fidelity and attribution failures, including
changed quoted words, altered dialogue wording, and unsupported certainty.
Those failures survive verbatim in the retained execution. KEEP preserves the
record of that result; it does not make the result correct. These observations
do not establish a provider transport failure or justify another adapter repair.

This is one real study and one retained execution, not evidence of generally
reliable interpretation. No complete browser workflow, workspace transfer,
restart survival of unretained runs, full historical completeness, or model
reproducibility was established. Raw source text, the full question, prompt,
response, and private workspace paths remain outside this repository note.

The next bounded decision is steward review of the retained source-fidelity
failures before authorizing any further diagnostic or study run. This packet
ends with the server running, one retained receipt, and no award.
