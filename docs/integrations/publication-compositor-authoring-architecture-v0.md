# Hermeneia and Publication Compositor: authoring architecture v0

**Status:** Phase-1 architecture proposal; ready for coherence review, not ratified ontology or implemented behavior.

**Owner:** Astra. **Implementation handoff:** Claude, after review and approval of a bounded slice.

**Task authority:** [Hermeneia #205](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/205), Phase 1 only.

**Inspected:** 2026-09-14 UTC, clean current-main checkouts: Hermeneia `82300fbed9d691c63e269896f2075bab3e322523`; Publication Compositor `7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2`.

## 1. Decision and scope

Use **Compositor's existing source-derived `CanonicalPublication` plus its `EditorialCanonicalVersion` family as publication-content authority**. Hermeneia owns the Reader, author interaction, investigation records, approval/rationale, and links into that versioned work. Hermeneia must not maintain an independently editable copy of the publication semantic model.

Connect them through **versioned, hash-verified local artifacts and a bounded local Compositor process**. Reuse the Python package and its builders/verifiers behind that boundary. No HTTP service, shared SQLite connection, monorepo, Google Docs dependency, or second editor is needed.

The smallest useful authoring slice is one existing verified publication in one Hermeneia workspace, eligible plain-text unit edits, explicit human approval, a new editorial version, one regenerated 6×9 PDF, and a verified link from proof evidence back to that unit. A second edit of the same unit must work without resetting to the original source. Semantic-role, heading-depth, and paragraph-topology edits follow as separately approved extensions. **The first slice does not satisfy all three Chapter 7 corrections.** Section 9 traces that full target and identifies its missing prerequisites.

This recommendation extends Compositor's existing editorial architecture. It does not authorize changes to Hermeneia's constitutional object list, forensic identity, or source evidence. Proposed integration records below are references, authored relationships, and execution receipts; they are not newly ratified epistemic object types. Names and version changes are proposed contracts, not APIs that already ship.

## 2. Current state and reuse inventory

Pinned source references are collected in section 15. “Present” means inspected on the SHAs above; it does not mean every end-to-end workflow has been freshly run.

| Repository / surface | Present on inspected main | Reuse and actual limitation |
|---|---|---|
| Hermeneia forensic store | SourceDocument byte hashes; parser/version-bound SourceExtraction IDs; occurrence-bound Observation IDs; immutable evidence/provenance | Preserve them unchanged. They identify a particular source/extraction, not the evolving manuscript. [H1], [H2] |
| Hermeneia Reader | Derived readable blocks with contributing extraction IDs and source-offset maps; Machine Lens now consumes `canonical_span` | Reuse the identity-first rule. A page/extraction projection is not an editable publication model. The C-001 frozen commit is not the current-main baseline for this spike. [H3] |
| Human attention and inquiry | `reader_highlights`, notes/questions, `investigation_log`, Perspective/Scope and stewardship workflows | Preserve original anchors and authored state. `reader_highlights.source_document_id` is a required forensic FK; inserting Compositor unit IDs there would be invalid. [H2] |
| Workspace lifecycle | Persistent workspace UUID independent of corpus fingerprint; workspace database selection | Reuse for local association/access scope, not publication identity. [H4] |
| Workspace exchange | WBS 1.1 exporter and restore read a defined set of corpus/study files | Existing code does not export/import a Compositor work, revision history, or manuscript anchors. An arbitrary adjacent directory would be omitted. [H5] |
| Publication governance | `herm build`, release recommendations, preservation checks, Edition eligibility/designation | Reuse governance boundaries, not a claim of an existing Compositor integration. The build path is manifest/Blueprint-oriented; an imported author-owned manuscript must not receive fabricated Architect/Artist lineage. [H6] |
| Compositor source | `DocumentIR`, original artifact/evidence hashes, character/span/line/block graph, source verifier | Reuse exact source accounting. Compositor and Hermeneia extractors need not produce the same blocks or IDs. [P1] |
| Compositor canonical work | `CanonicalPublication`, schema 0.8.0; ordered content, roles, source dispositions, transformations, text/semantic hashes | Preserve as immutable source-derived C0. Verification checks correspondence with Source IR; do not insert edited text into C0. [P2] |
| Structure / heading depth | `CanonicalStructureProjection` 0.2.0 and source-derived `HeadingDepthEvidence` 0.1.0 | Reuse hierarchy/navigation machinery. Author-assigned heading depth is not evidence of source font size and needs an explicit authored overlay. [P3] |
| Editorial ledger | `EditorialRevisionLedger` 0.1.0; replacement, partial deletion, unit insertion, semantic-role proposals and decisions | Binds to one original `CanonicalPublication`; at most one record per base unit, including proposed/rejected records. `parent_ledger_sha256` is recorded/hashed, not a verified revision-chain replay mechanism. [P4] |
| Editorial version | `EditorialCanonicalVersion` 0.1.0; approved-only replay, new result hashes, retained source/revision lineage | Unchanged unit IDs survive; changed units receive new deterministic `e-…` IDs. Insertions have revision provenance, no fake source blocks. Locked edits and deletion of a whole unit are refused. The builder accepts C0, not an editorial parent. [P5] |
| Editorial construction | `EditorialConstructionOverlay` 0.1.0 over unchanged source construction | Only replacement/partial deletion in ordinary one-to-one source-backed instructions. Refuses inserted units, role changes, grouped regions, source-derived inline runs, list geometry, and preserved geometry. [P6] |
| Editorial Typst rendering | **Absent on main** | [PR #154](https://github.com/JosephJMWalker-MBA/publication-compositor/pull/154), head `04df2e17ee518fe10d3f03ce73a78c093ed29f1e`, remains open. Its reported adapter/tests are prior art to review, not shipped capability. Main's source-derived compile/proof APIs must not be passed editorial payloads under old hashes. [P7] |
| Source-derived output | Verified construction, profiles, font environment, Typst/PDF, DOCX, EPUB, HTML, source islands | Reuse rendering policy and assets. Source-derived multi-format support does not imply editorial multi-format support. DOCX edit reconciliation remains #107. [P8] |
| Proof diagnostics | Source findings may identify block IDs; role-aware findings identify instruction IDs; general rendered findings may identify only a page | Reuse `TypstRenderProof` instruction locations and existing report identities. Universal canonical backlinks and an editorial proof verifier do not yet exist. [P9] |
| CLI/package | Python package, JSON-capable models, `probe`, `extract-ir`, `verify-source`, `analyze`, `canonicalize`, `benchmark` | No existing general authoring/rebuild job command. Add a small Compositor-owned facade; do not pretend an analysis CLI already performs the full job. [P10] |

### Observed verification

On the inspected Compositor main, the existing suites `test_editorial_revisions.py`, `test_editorial_versions.py`, and `test_editorial_construction.py` passed: **20 passed, 0 skipped**. These include rejection of duplicate base targets, target drift, missing human-decision provenance, whole-unit erasure, inserted construction, and role-changing construction. Command:

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 ../environment/bin/python -m pytest -q -p no:cacheprovider \
  tests/unit/test_editorial_revisions.py \
  tests/unit/test_editorial_versions.py \
  tests/unit/test_editorial_construction.py \
  --junitxml=../evidence/compositor-editorial-tests.xml
```

Environment: Python 3.13.5, with declared runtime dependencies installed into an external environment. Initial collection failed because that environment lacked `fontTools`; after installing dependencies, all 20 ran successfully. This was an environment setup failure, not a product failure. No new tests or product code were written. No fresh full suite, private manuscript run, PDF compilation, Jetson/browser smoke, or hosted CI verification is claimed. PR #154's CI status/history was inspected, not independently re-executed or treated as a semantic verdict.

## 3. Authority and ownership

| State | Authority / storage responsibility | Allowed transition |
|---|---|---|
| Original uploaded bytes | Original source artifact, content-addressed; both systems may reference the same byte hash | Preserve. A different upload creates another source lineage. |
| Hermeneia SourceExtraction / Observation | Hermeneia's constitutional evidence store | Never rewrite for an edit or repagination. |
| Compositor Source IR | Compositor's immutable parser evidence and verification | A different parser/evidence graph creates a new versioned source artifact. |
| Source-derived publication C0 | Compositor `CanonicalPublication`, verified against Source IR | Immutable root for the editorial work. |
| Editable current manuscript | The selected verified Compositor editorial version; C0 before any approved revision | New approved revision creates a successor. Browser text is a draft until accepted. |
| Approval and rationale | One explicit Hermeneia human action, preserved with actor, decision, target version, exact delta and rationale | Compositor ledger references that action. Its copied actor/reference fields are not a second independent approval. |
| Semantic author intent | Approved text/role/structure/inline-intent revisions under the Compositor version contract | Changes the appropriate semantic/intent identities, never Source IR. |
| Publication layout/profile | Compositor profile, resolved layout, furniture and renderer environment | New profile/build; manuscript identity stays fixed when content/intent does not change. |
| Investigation records | Hermeneia, anchored to their original evidence or explicitly versioned manuscript target | Append relationships/reviews; do not transfer the authority of an old observation to revised wording. |
| Proof, preflight and delivery | Compositor rendition/report artifacts | Rebuildable; acceptance evidence is preserved. A clean proof is not human release approval. |
| Release / Edition | Hermeneia's existing stewardship rules | Separate human decision. “6×9 proof” does not mean Hermeneia “Edition” or platform-ready submission. |

Rejected alternatives: an editable Hermeneia publication AST duplicates Compositor's roles, hashes and verifiers; DOCX/Google Docs as authority turns interchange into a second state owner; editing `CanonicalPublication` in place falsifies source lineage. The shared contract contains references to the existing publication model and approval events, rather than another independently writable text model.

The constitutional route is `docs/00_Constitution.md` → `docs/01_Authority_Index.md` → active amendments/invariants/storage authority. Articles I–VI, X–XV and CI-001–007, CI-010–013, CI-015–016 govern ancestry, evidence fidelity, audit/reproduction, stewardship, read-only behavior, storage and testing in this design. Article IX still governs generated narratives; this integration does not reclassify imported authorial work as Artist output.

**Storage authority issue to resolve before implementation:** active `docs/15_Storage.md` says `.herm` contains `context.json` and authoritative `hermeneia.db`; the lower-authority WBS design note uses competing “canonical exchange” wording. This spike does not ratify that wording or replace `.herm`. Use WBS as the existing transport adapter and Compositor files as referenced external publication artifacts. Any normative storage extension must be reviewed under the Authority Index before schema/format changes. Preserve the existing files; do not silently rewrite either specification.

## 4. Minimum shared identity contract

Use explicit namespaces and version-bound references. Proposed field names below describe the exchange contract; they are not columns being added in Phase 1.

| Reference | Minimum binding and behavior |
|---|---|
| `workspace_id` | Existing Hermeneia UUID. Authorizes association with this local workspace; not a document/content ID. |
| `work_root` | Immutable root reference to original artifact SHA, Source IR evidence SHA/schema, and exact C0 artifact digest plus canonical text/semantic hashes. Its digest is the work key for this integration. It remains fixed across editorial revision and repagination. |
| `version_ref` | Exact root/C0 or `EditorialCanonicalVersion` digest and schema, plus its text/semantic hashes and, for an editorial version, approved-ledger digest. Future hierarchy/inline-intent digests must also be bound. No “latest” in a stored target. |
| `unit_ref` | `work_root + version_ref + content_unit_id`, with expected unit text/semantic hashes. IDs are opaque; never recover meaning by parsing `c…` or `e-…`. |
| `origin_ref` | For an unchanged/replaced source-backed unit, the root C0 content ID reached through verified editorial ancestry. This is a stable navigation relation, **not** a promise that a changed unit retains its content-addressed ID. For insertion, use the creating revision and its output-unit identity. |
| `source_ref` | Original bytes hash, extractor/schema identity, evidence-graph hash, and exact source block/character IDs where provided. Hermeneia extraction/Observation IDs remain a separate typed namespace. |
| `span_ref` | Exact `unit_ref`, half-open `[start,end)` in Unicode scalar values, selected text and whole-unit text hash; optional prefix/suffix are corroboration only. Browser UTF-16 positions must be converted explicitly. Never normalize evidence to make a range fit. |
| Semantic intent | Existing role plus separately versioned hierarchy/heading depth and inline intent when supported. Current role/text/locked hashes do not cover every hierarchy/formatting choice; bind additional intent digests into the editorial version/build identity rather than redefining existing hashes silently. |
| Revision lineage | Parent version digest, ordered approved revision IDs, approval-event digest/reference, exact before-state bindings, successor digest and explicit unit/span correspondences. A parent hash without replay/ancestry checks is insufficient. |
| Proof reference | Work/version, profile/environment/build digest, output PDF hash, verifier/report hash and instruction/target mapping. Page/geometry are locations within that proof only. |

No separate mutable global manuscript UUID service is necessary. A deliberate import with a new source or canonicalization root starts another `work_root`; explicitly link it to an earlier work when appropriate. Exact source-byte deduplication does not grant cross-workspace access.

### Crossing the two source graphs

Matching original artifact hashes establishes shared bytes, not identical extraction boundaries. Hermeneia uses parser-version/location/text IDs; Compositor has its own page/block/character graph. An optional bridge may record verified relations between both exact graphs using the original artifact hash, parser identities, source coordinates and exact occurrence evidence. Repeated equal text is insufficient. A many-to-one canonical assembly must retain all contributing source references.

If a unique bridge cannot be proved, display the source and publication unit separately and allow a human-authored relation labeled as such. Do not call that relation parser equality. The first slice may open the Compositor manuscript projection by unit identity without automatically mapping every old Reader highlight. It must not imply that an unresolved bridge is complete.

### Split, join and run identity

Replacement retains a navigable origin relationship and creates a new immutable unit version. Split creates explicit one-to-many successor edges and exact span maps; join records many-to-one parents and separator decisions. Neither can masquerade as an unchanged unit. Deleted material remains accessible at its old version, with a deletion correspondence rather than a fabricated current range.

There is no need to invent permanent run IDs for plain-text replacement. When semantic emphasis/citations/notes are added, use versioned run/span records tied to the owning unit and approved revision; preserve existing verified source runs as source evidence. Split/merge mappings carry run ancestry. Typography coordinates and proof pages never identify a run.

## 5. Revision semantics and historical investigation

### Required state transitions

```text
local draft against exact version N
→ proposed delta + rationale
→ explicit human approval/rejection
→ verified approved ledger against version N
→ independently replayed successor N+1
→ append accepted-version receipt
→ build one or more proofs against that exact successor
```

Proposal/rejection stays audit history and does not change the manuscript. Imported ledger role strings are not authentication; current verifiers check declared provenance fields, not whether a person actually authorized a UI action. Hermeneia must bind its approval action to the exact proposal hash and active workspace/version. Imported external approvals require explicit local adoption before changing the active work. Model suggestions use the same proposal route and never self-approve.

**Compositor extension required in #106:** current 0.1 builders cannot directly apply a ledger to an `EditorialCanonicalVersion`. Extend the existing ledger/version family with explicit parent-version support and replay verification. Keep C0 and all earlier versions intact. Target the actual parent unit ID/hash and exact before text; carry root source ancestry and accumulated revision ancestry through later edits. Recompute the latest eligible text overlay against the original verified construction plan, proving it from the complete approved chain. Do not cast an edited version to source-derived C0 or silently flatten approved history into a new upload.

The first extension remains text-only and permits one operation per parent unit per transaction. Sequential edits use successive transactions. This preserves the existing bounded verifier while making a second edit possible. A later multi-target transaction is required for paragraph split/join and combined semantic operations. Parent-ledger links alone, unchecked concatenation of old ledgers, or a Hermeneia-only patch engine do not implement this contract. Schema changes belong in Compositor with explicit compatibility rules, not in renderer-specific code.

### Atomicity and failure

Compositor is the only writer of accepted publication versions. Hermeneia writes an immutable human-decision receipt and submits a request binding `work_root`, expected parent, proposal/decision digests and an idempotency key. Under a per-work lock, Compositor verifies the parent and decision references, stages a fully replay-verified successor, and atomically appends its accepted-version receipt. A rebuildable selected-head pointer may reference that receipt; it is not a second text authority.

Two writers against one parent cannot both silently become current. A stale request is refused with its draft/approval preserved for explicit reconciliation. An identical retry returns the recorded result; it does not create another approved edit. There is no distributed database transaction: the immutable decision/request/result chain supports explicit recovery. A pending decision is not proof that a version was accepted.

Rendering is a separate retryable step after acceptance. If rendering fails, show **“Manuscript saved; proof not updated”**, retain the approved revision and last proof with its old version label, and retry generation without asking the author to repeat the edit. If version verification fails, the parent remains active. Draft recovery, jobs, and interrupted results must never mutate from a read-only GET.

### What happens to annotations

| Existing target | After a revision |
|---|---|
| Forensic Observation / source highlight | Remains attached to the original source/extraction/occurrence, including its original page. Its wording and evidence status do not change. |
| Manuscript unit unchanged in a verified successor | Original annotation retains its old target; the UI may show a derived current-view correspondence after hash verification. |
| Selected span unaffected by a text edit elsewhere in the unit | An exact replay-produced span map may project its display position. Preserve the original anchor and mapping provenance. |
| Target wording changed/deleted, or split/join ambiguous | Show changed/deleted/needs-review status and the historical passage. Do not silently claim the annotation now supports the replacement. |
| Question/rationale concerning the work generally | Retain the question and explicit revision links. An edit does not answer or resolve it. |
| Evidence or Perspective/Scope referring to old observations | Remains about that evidence. New manuscript text is not automatically admitted into Scope or canonized as an Observation. |

Store manuscript target bindings as appended typed relationships to existing authored records, using a reviewed Hermeneia persistence extension. Do not stuff Compositor IDs into the forensic FK or overwrite `source_locator`. New manuscript-only notes can use existing authored-note interaction with an explicit versioned target; they cannot become canonical Observations without a lawful compilation lineage. A generated proof becomes new forensic evidence only through an explicit import/compile action, and even then its PDF page is not manuscript identity.

## 6. Authoring interaction and edit classes

Keep Reader primary. Add an explicit **Authoring** mode for the selected publication work, with source reading/history still available. Its displayed text/roles come from the selected verified Compositor version. It is not `contenteditable` over forensic Reader HTML. Opening a source-linked unit or proof finding retains the investigation context and makes any unresolved source/publication mapping visible.

The initial interaction is a unit editor, exact before/after review, rationale, and an explicit **Approve revision** action. Draft autosave does not approve. **Preview proof** regenerates from the accepted version and saved profile; it does not require reapplying styles. Keyboard selection and return-to-reading should preserve the unit target and scroll context.

| Author action | Owning change | Present capability / sequencing |
|---|---|---|
| Replace wording; insert/delete characters within a nonempty plain-text unit | Editorial text revision | Existing replacement/partial-deletion primitives; insertion within a unit can be expressed as an explicitly reviewed replacement of a containing range. First slice; no whole-unit erasure. |
| Insert/delete a paragraph; split/join paragraphs | Editorial topology and text/separator decisions | Insertion exists at version level but not construction; deletion/split/join need verified topology, successor/span maps and construction support. Later #106 slice. |
| Mark a block quote, list, caption, equation, note or reference | Semantic-role intent | Existing ledger can represent a role change; construction/rendering currently refuse it. Extend Compositor and all affected derived plans before exposing the action. |
| Change heading level / section organization | Authored hierarchy intent | Distinct from changing a generic `section_heading` role. Must recompute structure, TOC/navigation, section/furniture targets. Never fabricate source-derived `HeadingDepthEvidence`. |
| Bold/italic/emphasis | Semantic inline intent when authorial; profile style when only house typography | New approved intent contract over exact spans is needed for authorial emphasis. Existing source-derived script runs are not an arbitrary rich-text editor. Later slice. |
| Fix a soft line wrap in the display | Derived projection/layout | No manuscript edit if it is purely a display artifact. |
| Remove an authorial paragraph/section break | Structural editorial revision | Cannot hide it as PDF layout or silently concatenate source evidence. |
| Correct a page break, heading orphan, font or margin | Compositor profile/layout unless the author changes semantic intent | Rebuild downstream artifacts; preserve manuscript identity. |
| Approve/reject a compositor suggestion | Hermeneia decision referencing one exact finding/proposal | Approval applies a supported typed revision or profile change; rejection preserves the finding and leaves content unchanged. |

Unsupported or locked content remains visible with an explicit reason and a safe route to the source/profile review. Do not offer a control that silently saves a change Compositor cannot regenerate.

## 7. Repository, process and artifact boundary

| Option | Benefit | Cost / decision |
|---|---|---|
| In-process Python dependency | Existing builders are immediately callable; least invocation code | Couples Flask lifetime and dependencies to native PDF/font/render operations. Useful for pure contract validation, but not the default long-running render boundary. |
| Explicit versioned JSON contract | Inspectable, independently verifiable, replayable, no database sharing | Chosen persistent/exchange boundary. Reuse existing model schemas and add a thin envelope for work/parent/job/results. |
| Shared SQLite schema/connection | One apparent transaction | Rejected: neither public Compositor storage API nor shared authority exists; migrations and writes would become coupled. |
| Local service/API | Separate runtime; could later support many clients | Unnecessary listener, service lifecycle, authentication and network failure surface for one local author. Deferred. |
| Shared workspace artifact bundle | Portable exact inputs/results; supports retries and backup | Chosen local handoff material. A bundle is transport/reference containment, not another Hermeneia evidence format. |
| Existing CLI plus a local process facade | Uses existing package/model/verifier code; bounded lifetime and dependency version | Chosen execution mechanism. Existing CLI cannot yet rebuild editorial PDFs, so add the small facade in Compositor under #109, not shell scripts duplicating compositor policy in Hermeneia. |

The proposed facade has only the operations needed by the slice: inspect/verify a work and supported edit envelope, validate/apply a declared approved revision, and build/verify a proof from an exact accepted version/profile. These are conceptual operation names, not claims that commands/routes already exist. Freeze a small schema and command interface in the Compositor task before Hermeneia calls it. A protocol-version mismatch must fail before any write.

Hermeneia selects a configured, pinned Compositor executable/environment and invokes an argument array with a manifest path, never a shell-interpolated manuscript string. Each request declares all inputs, their schemas/hashes, the output directory, resource limits and expected parent. Only scoped local artifact paths may be resolved; network fetches, arbitrary paths from imported manifests, and provider calls are not implicit dependencies. Renderer/font versions and asset hashes are part of the build, not host defaults. Relative artifact paths must resist traversal/symlink escape; no credentials or manuscript text in process arguments/logs.

### Proposed stored artifact graph

The following are logical entries in a workspace-managed publication area. Final paths and storage registration require the compatibility decision in section 12; this is not a second `.herm` specification.

| Artifact | Writer and identity | Retention |
|---|---|---|
| Source bytes, exact Source IR + verification | Existing source owner / Compositor; original bytes and evidence hashes | Immutable; required for reconstruction. |
| C0 + canonical verification, source construction, source assets | Compositor; exact model/plan and asset digests | Immutable input foundation. |
| Work association | Hermeneia; existing workspace UUID → `work_root` | Authored association, scoped access; no text copy. |
| Draft/proposal and human decision receipt | Hermeneia; exact parent/proposal hash, actor, choice, rationale, related investigation IDs | Draft recoverable; submitted proposals and decisions retained as authored history. |
| Revision ledger, parent chain, editorial version, correspondence map, verification reports | Compositor; schema-qualified digests | Immutable accepted history. Failed proposals/results remain distinguishable from accepted versions. |
| Accepted-version receipt / selected head | Compositor publishes immutable receipt; selected-head cache is rebuildable | Receipt binds request, parent, decision and result. No independent Hermeneia manuscript head. |
| Profile/intent configuration, resolved layout, construction overlay, generated plans | Compositor; hash-bound to version/profile | Preserve chosen configuration and accepted build inputs; derived plans regenerable. |
| Build request/result, Typst source, PDF, proof/finding reports | Compositor; exact version/profile/environment/output digests | Preserve viewed/accepted proof evidence; unaccepted intermediate assets may be disposable under explicit retention policy. |
| Annotation/revision relationships and finding dispositions | Hermeneia; typed original targets + relation/decision history | Authored; survive workspace export/restore. |

The shared envelope must bind exact serialized artifacts as well as domain hashes. Text hashes alone do not identify a version: Compositor's lexical hash intentionally ignores unit boundaries, and unchanged text may have changed roles, structure or provenance. Do not invent a new JSON canonicalization rule independently in each repo; Compositor owns serialization/version validation for its models, and Hermeneia hashes the exact supplied bytes.

## 8. Edit → rebuild sequence

This diagram describes the proposed approved workflow, including the missing Compositor extensions. It is not a depiction of current shipped integration.

```mermaid
sequenceDiagram
    actor Author
    participant H as Hermeneia Reader and authoring
    participant A as Authored decision history
    participant C as Local Compositor process
    participant W as Verified publication artifacts
    Author->>H: Edit unit at exact version N
    H->>C: Validate proposed delta and supported envelope
    C-->>H: Exact before and after, or refusal
    Author->>H: Approve delta with rationale
    H->>A: Append proposal and decision bound to N
    H->>C: Apply request with expected N and idempotency key
    C->>W: Verify root, parent chain, decision and unit hashes
    alt Invalid or stale parent
        C-->>H: Refuse; keep draft and original head
    else Valid approved successor
        C->>W: Stage and verify ledger, version N+1 and mappings
        C->>W: Atomically append accepted-version receipt
        C-->>H: Accepted N+1 and immutable result reference
        H->>A: Append investigation-to-revision links
        H->>C: Build proof for N+1 with saved 6x9 profile
        C->>W: Verify construction, layout, fonts and render inputs
        C->>W: Render PDF and verify editorial proof and findings
        alt Proof verified
            C-->>H: PDF hash, version, profile and finding references
            H-->>Author: New proof; continue at the same unit
        else Build failed
            C-->>H: Saved N+1; failure evidence and retryable request
            H-->>Author: Manuscript saved; proof not updated
        end
    end
```

A successful proof does not call `herm edition designate`, sign a release recommendation, import itself into the source corpus, or admit revised content into investigation Scope.

## 9. Chapter 7 acceptance: fix three problems once

This is the **full formatting milestone**, after the narrower first slice. It requires Compositor editorial role/hierarchy/topology support; source-derived role recognition is not enough.

1. Bind the open Reader/Authoring view to one work and accepted version N. Preserve its original source relation and current investigation record. Resolve the three targets to versioned unit IDs; if mapping is uncertain, the author selects the actual manuscript units rather than relying on page 7 or equal wording.
2. Record one transaction containing: body → block-quote intent; the explicit desired heading depth; and a join of the two adjacent paragraphs separated by the unwanted break. The join names both ordered parents and the exact separator to retain/insert/delete. If removing the break would introduce or remove lexical characters, include that exact textual delta; do not normalize implicitly.
3. Show one review containing all three operations, exact before-state hashes, affected structures and rationale. Hermeneia appends one explicit approval receipt for the transaction. No separate approval in a Compositor UI is needed.
4. Compositor validates that all targets belong to N, that the transaction has no inconsistent overlapping operations, and that every operation is supported. Apply all three or none; append the ledger/semantic-intent records, successor N+1, parent/successor correspondence and verification. This requires extending the current single-target operation vocabulary under #106.
5. Rebuild the affected construction topology, hierarchy/navigation, section targets and presentation contracts against N+1. Retain original Source IR, C0 and source construction as historical proof. A human heading-depth override must never be serialized as observed source typography. Bind role/hierarchy/inline-intent identities into the version and build.
6. Reuse the same saved 6×9 profile, typography and verified unchanged assets; recompute layout, pagination and generated furniture. Emit Typst source, PDF, editorial verification, instruction/target proof map, diagnostic report, and a result manifest binding every digest.
7. Hermeneia displays that proof labeled N+1, links findings back to N+1 units, and preserves N's proof and investigation targets. The author never reapplies the quote, heading or paragraph correction in another application. Later profile changes regenerate those corrections from the same approved state.

A screenshot with correct formatting is insufficient acceptance. The stored transaction, version, derived plans, PDF and proof map must establish that the corrections originated in one approved revision and survived regeneration.

## 10. Proof findings → responsible edit

### Finding/backlink envelope

Compositor owns a versioned finding envelope around existing diagnostic records. Preserve the original finding; do not replace the verifier's result with a UI interpretation.

Required bindings: report schema and detector/rule version; report artifact digest and finding index; `work_root`; exact manuscript version; build/profile/environment references; PDF digest when a proof exists; finding code/severity; typed target(s); responsible layer; and evidence references. The finding ID is a deterministic digest of the envelope/report identity and record index, so duplicate codes remain distinct. It identifies one finding in one report, not an eternal defect across revisions. An optional comparison fingerprint may group later findings but cannot auto-resolve them.

Typed targets include source block, versioned content unit/span, construction instruction, generated-layout item, or profile key. Resolution follows verified edges:

```text
proof finding
→ exact proof/build
→ verified instruction identity
→ editorial content identity or unchanged C0 content identity
→ exact manuscript unit/version in Hermeneia
```

For source analysis before construction, use the exact Source IR block target and resolve its canonical disposition if one exists. Generated furniture maps to its generation/profile inputs; it does not acquire an authorial text target. The external envelope supplies the missing work/version/report identity without pretending current findings all already contain it.

| Defect | Route |
|---|---|
| Orphaned/low heading caused by keep-with-next, spacing or pagination | Compositor profile/layout review; rebuild. The author may separately choose to revise a long heading, but that is an explicit editorial decision. |
| Wrong semantic heading depth or quote role | Exact versioned manuscript unit in Hermeneia; supported approved semantic revision. |
| Unsupported equation | Exact source/canonical unit, visibly locked when applicable. Preserve/source-island or refuse; no automatic equation reconstruction or generic text editor over locked geometry. |
| Bad page break | Profile/layout unless an explicit authorial section/paragraph boundary is responsible; classify from recorded evidence, not merely the finding's wording. |
| Human-noticed defect in a proof | Save a human-authored proof annotation bound to that PDF/build. Resolve through the verified proof map; a page-only note stays page-only until an unambiguous unit is selected. |
| Only page-level diagnostics available | Open the exact proof page and show candidate units. Do not fabricate a single canonical backlink or select text by coincidence. |

Current `TypstRenderProof` supplies instruction anchor positions, not a universal pixel-to-character selection map. A proof click is exact only where the map supports it. Ambiguous/overlapping/grouped regions require explicit selection. Findings against an old version open that version; a link to the current successor is a separately verified correspondence, never a silent redirect.

```mermaid
sequenceDiagram
    actor Author
    participant H as Hermeneia proof review
    participant C as Compositor reports and mappings
    participant A as Authoring at exact version
    Author->>H: Open a finding or mark a proof defect
    H->>C: Resolve finding with report and PDF hashes
    C->>C: Verify build, target namespace and mapping
    alt One author-editable manuscript target
        C-->>H: Exact work, version, unit and evidence
        H->>A: Open target with investigation context
        Author->>A: Propose and approve a supported revision
        A-->>H: Accepted successor; request a new proof
    else Layout or generated-furniture target
        C-->>H: Profile or construction concern
        H-->>Author: Review layout change; preserve manuscript
    else Locked, absent or ambiguous target
        C-->>H: Explicit limitation with original proof/source
        H-->>Author: Inspect or choose a target; no guessed edit
    end
```

A rejection/dismissal is an authored disposition linked to the finding, not erasure of the diagnostic. Changing wording does not automatically prove a finding resolved; evaluate the new proof and link the evidence.

## 11. First useful vertical slice and explicit non-goals

**Slice S1: repeated plain-text revision and one 6×9 proof.** Attach one prepared, verified Compositor work to one existing Hermeneia workspace. Show its canonical unit list/current text within Authoring mode; retain access to source Reader and investigation context. Permit exact wording edits and partial deletion on eligible source-backed units only. Support N → N+1 → N+2 for the same unit, explicit human receipts and rationale, one saved 6×9 profile, and a proof/finding backlink to the exact unit. Preserve prior versions, original annotations, and all reconstruction inputs through a verified export/restore.

Why start here: existing #106 builders and open #154 provide substantial prior work, while role changes, heading depth and joins require new topology verification. Demonstrating those three changes together before the text/revision/proof boundary is trustworthy would hide several independent defects. The private Ecology manuscript is the eventual live-use pressure; use synthetic plain-body fixtures first and report how much of the actual selected work falls inside the eligible envelope. No claim of useful private coverage is made in Phase 1.

S1 is not complete with a one-shot edit that cannot be edited again, a stale PDF displayed as current, a reference-only backup with missing editorial payloads, or a simulated proof link. At least one positive end-to-end fixture must render approved changed text into the PDF, and a later build must reproduce it without re-entering edits.

Non-goals: full rich-text editor; collaboration/CRDTs; generic Word fidelity; DOCX round-trip as a prerequisite; EPUB/HTML/DOCX editorial rendering in S1; semantic-role/heading-depth/paragraph topology in S1; arbitrary equation editing; automatic manuscript rewriting; model-selected approval; source normalization; universal annotation migration; network services; platform upload; automatic release/Edition designation; broad Compositor V1 completion; or any product implementation in Phase 1.

## 12. Migration and backward compatibility

- Preserve all existing `.herm` evidence identities, immutable rows and Reader anchors. New publication bindings are opt-in. Opening a legacy workspace must not migrate its schema or initialize a publication work via GET.
- Compositor 0.1 ledger/version/overlay artifacts remain readable and verifiable with their original rules. Add new schema versions for parent-version replay, cumulative text-overlay provenance, and later semantic topology. Reject unknown versions; do not add fields to old payloads or weaken their verifiers.
- C0 remains the verified original work. An existing 0.1 editorial version may become a validated parent in the new contract only after resolving and verifying its root and ledger; never strip it down to a fake source-derived C0.
- Existing content IDs and their hash algorithms retain their meaning. Cross-version navigation uses explicit relations. Unit ordinals, page numbers and equal lexical hashes are not migration identities.
- Extend Hermeneia's reviewed storage/exchange contract to retain work association, exact external Compositor artifacts, human decision receipts and manuscript relations. Existing WBS 1.1 fixed readers do not handle these. Exporters must refuse to advertise a complete integrated backup if this data would be omitted; restorers must reject unsupported required components instead of silently dropping them. A newer bundle version/required capability must make that distinction visible.
- Restore must verify artifact hashes, source/parent closure and relation targets in a fresh workspace before activation. A cached current version or proof can be rebuilt only from preserved history. Foreign workspace IDs or stale paths cannot authorize access. Keep the forensic `.herm` authority intact; external Compositor artifact containment is not a competing forensic representation.
- Do not reuse an old signed release/Edition designation for a new manuscript version. Retain old release evidence and show the successor as requiring its own applicable review. A Compositor “edition variant” is a rendering profile; Hermeneia “Edition” is a governed designation.
- Keep the private Ecology text, source files, generated proofs and human comments out of GitHub. Commit synthetic fixtures, code and non-content validation metadata only.

## 13. Tests, risks and stop criteria

### Required Phase-2 fixtures

| Fixture | Required result |
|---|---|
| Original upload, Source IR, C0, Hermeneia extractions/observations before and after revisions/builds | Exact bytes/hashes unchanged; immutable persistence rejects mutation. CI-001–007. |
| Two equal paragraphs in one work; identical source in a different workspace | Exact unit/version target only; no cross-occurrence or cross-workspace edit. |
| Stale parent or wrong unit hash/quote/range | Refuse before acceptance; preserve draft and original active version. |
| Proposed/rejected suggestion, forged/imported decision reference | No accepted text change without the bound local human decision; no authority from a role string alone. |
| Two edits to the same unit across N, N+1, N+2 | Independently replayable chain; both approvals and before-states retained; only latest accepted text in the current proof. |
| Duplicate request; crash before/after acceptance; render failure | No double edit; deterministic recovery; saved manuscript survives renderer failure; old proof labeled old. |
| Eligible body replacement → Typst compile → PDF extraction | Positive approved wording appears, old wording at that target disappears; no all-refusal “pass.” |
| Same version/profile/environment rebuilt | Identical declared deterministic artifacts or explicit diagnosed environment failure; no inflated PDF determinism claim. |
| Repagination with unchanged version; repeated text; Unicode outside BMP | Same versioned unit targets; correct scalar/UTF-16 conversion; no page-based or quote-search identity. |
| Existing annotation, unaffected range, replaced/deleted range | Original target stays intact; exact correspondence or explicit needs-review; no automatic Scope admission. |
| Instruction-linked, page-only, source-island and generated-furniture findings | Correct typed routing; exact PDF/version; ambiguous targets remain ambiguous. |
| Unsupported role/inline/list/locked/topology edit | Refuse visibly before presenting a usable editing control; no raw renderer bypass. |
| Work export/restore with one missing, tampered or unknown-required artifact | Complete reconstruction on success; explicit refusal on loss; no silently orphaned authored history. |
| Full Chapter 7 quote/depth/join transaction, after its later approval | All three applied once or none; correct regenerated 6×9 proof; old work/history reconstructable. |
| Preview, successful verification, accepted edit | None automatically signs a release, becomes an Edition, or changes forensic evidence authority. |

Reuse Compositor's existing destructive verifier tests and Hermeneia's `test_publication_release_authority.py`, `test_edition_eligibility.py`, Reader projection and workspace round-trip tests. Add contract-level fixtures before broad UI changes. Prefer deterministic local tests and preserved local execution evidence; distinguish infrastructure failure from content failure. Manual live-use and hosted CI are additional evidence levels, not substitutes for missing proof.

### Risks / kill criteria

| Risk | Stop or reduce scope when |
|---|---|
| Duplicate publication authority | Hermeneia needs its own editable text/role model or directly writes Compositor internal state. Revisit the boundary before implementation. |
| Source lineage falsification | Edited/inserted content requires fake source blocks, reused source hashes, or mutated C0. Reject the approach. |
| Revision chain too weak | Second edits cannot be independently replayed, or old approval history is flattened away. S1 cannot be declared complete. |
| Narrow overlay coverage | The actual chosen Ecology passage is grouped, inline-geometry-heavy, locked or otherwise unsupported. Report the coverage/refusal, select another legitimate pilot unit, or stop for a separately approved capability; do not silently widen the editor. |
| PR #154 / editorial proof gap | Current renderer/proof APIs cannot distinguish editorial hashes and metadata. Treat renderer review/verification as a dependency; never relabel an editorial PDF as source-derived proof. |
| Storage authority ambiguity | Durable publication/annotation records require changes not covered by the reviewed storage contract. Obtain the scoped authority decision before persistence work. |
| Annotation overclaim | Only fuzzy text/page matching can attach an old annotation or proof finding. Preserve unresolved state; no automatic transfer. |
| Lost work on failure | A failed rebuild loses approved edits, or restore omits the revision history. Stop the authoring rollout until durability is proven. |
| Integration expansion | The slice requires an HTTP daemon, monorepo, collaboration system or all #109 features merely to make one edit/proof work. Reassess the local package/artifact boundary. |
| Publication confidence overclaim | Internal verification is being labeled platform-ready or human-approved release. Separate #110 delivery rules and existing stewardship gates. |

## 14. Ordered Phase-2 tasks for Claude

Phase 2 remains blocked until this artifact is reviewed for coherence and the first slice is explicitly approved. Re-inspect the exact referenced code at implementation time. The rows are bounded increments, ordered from contract checks toward progressively larger behavior. Complete S1 through task 8, then stop for live-use review; tasks 9–11 are not implicit permission to expand S1.

| Order | Repository / issue | Exact task and acceptance boundary |
|---|---|---|
| 0 | Both; Hermeneia #205 | Review authority split, parent-version semantics, durable storage/transport treatment and S1 exclusions. Distill the accepted contract. Resolve the `.herm`/WBS wording conflict only in its necessary scope; no general storage rewrite. |
| 1 | Compositor #106; existing PR #154 | Inspect the pinned open adapter, reconcile with current main, run its existing unit and real Typst/PDF integration proof. Establish the supported text envelope and editorial-aware compile/proof path. Do not rebuild the adapter independently or treat an open PR as merged. Merge/release decisions require their own authorized review. |
| 2 | Compositor #106 | Extend the existing ledger/version contracts for exact editorial parents and N→N+1→N+2 plain-text replay; retain original C0 and all decisions. Add schema compatibility, stale-target, same-unit second-edit and immutable-ancestor tests. No role, split/join or rich text yet. |
| 3 | Compositor #106 / #109 | Extend the text-only overlay and editorial proof binding to the verified complete revision chain. Add a minimal versioned local job facade over existing builders/verifiers, declared file manifests, capability/refusal output, parent CAS and idempotent result receipt. Prove crash/retry behavior without Hermeneia or network service. |
| 4 | Compositor #109; #110 boundary | Add the typed finding/result envelope and instruction→editorial-unit backlinks using existing source/construction/render-proof evidence. Keep page-only diagnostics unresolved and generated/layout issues routed to profile review. No platform certification or broad diagnostic expansion. |
| 5 | Hermeneia #205 | Add reviewed workspace association and durable external-artifact/decision/target references, plus version-aware export/restore. Use synthetic data; prove complete history retention and old-workspace compatibility before accepting real edits. No duplicate manuscript schema. |
| 6 | Hermeneia #205 | Read-only Authoring projection for one attached work; select exact unit/version and show supported edit envelope and historical-source relations. Execute the local facade with scoped paths, pin validation and stale-response checks. No editable forensic Reader DOM. |
| 7 | Hermeneia #205 | Add the bounded plain-text editor, draft recovery, exact delta/rationale approval and persisted decision→request→accepted-version links. Support two sequential edits and surfaced conflicts/refusals. Retain old annotations and visibly separate unresolved current-view correspondences. |
| 8 | Both; Hermeneia #205 / Compositor #109 | Connect one saved 6×9 profile, proof generation/retry, exact-version proof display and finding return-to-unit. Run the synthetic positive/negative matrix, verify export/restore, then use a supported private Ecology unit without committing its text. Preserve observed friction and stop for S1 review. |
| 9 | Compositor #106, then Hermeneia #205 | Separately approve and implement semantic-role construction/render support and authored heading-depth/structure overrides. Recompute navigation, section/furniture targets and intent identities; only then enable those controls. |
| 10 | Compositor #106, then Hermeneia #205 | Separately approve multi-target atomic split/join/paragraph operations and exact successor/span mappings. Execute the full Chapter 7 three-correction scenario with source immutability and proof verification. |
| 11 | Compositor #106 / #107 / #110 as individually approved | Inline emphasis, lists/notes/equations, editorial multi-format output, DOCX reconciliation, and platform-specific delivery are later capability slices. Keep #107 optional for S1; keep #110 preflight separate from manuscript authority. No broad V1 rollout by inference. |

### Cross-repository issue routing

- [Compositor #106](https://github.com/JosephJMWalker-MBA/publication-compositor/issues/106): parent-version replay, revision ancestry, text-overlay/proof continuation, later role/hierarchy/topology contracts. The open #154 is existing renderer prior art and a dependency to review.
- [Compositor #109](https://github.com/JosephJMWalker-MBA/publication-compositor/issues/109): the narrow local artifact/job facade, capability envelope, same-session regeneration, typed proof finding/backlink contract. This is a bounded upstream consumer requirement, not implementation of its entire V1 inventory.
- [Compositor #107](https://github.com/JosephJMWalker-MBA/publication-compositor/issues/107): DOCX edit/reimport remains a later optional editing surface that must enter the same revision/approval contract. It must not create a separate current manuscript.
- [Compositor #110](https://github.com/JosephJMWalker-MBA/publication-compositor/issues/110): platform preflight/delivery remains downstream and separately versioned. A 6×9 preview is not a KDP/Ingram readiness claim.
- [Hermeneia #205](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/205): architecture review, workspace association/preservation, authoring UX, human approval, investigation links and orchestration. Keep it open; Phase-1 completion does not close the integration or authorize Phase 2.

Phase 1 ends with this committed document and linked issue updates. No product code, persistence migration, renderer change, manuscript edit, deployment or private manuscript content belongs in this commit.

## 15. Pinned source references

All implementation links below identify the inspected main commits, so later changes cannot silently change this architecture's evidence. Reference names are repository-local labels, not new domain terms.

[H1]: https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/docs/15_Storage.md
[H2]: https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/storage/sqlite.py
[H3]: https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/web/static/index.html
[H4]: https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/workspace/identity.py
[H5]: https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/workspace/export.py
[H6]: https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/cli/edition_cmd.py
[P1]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/ir/models.py
[P2]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/canonical/models.py
[P3]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/canonical/structure_models.py
[P4]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/editorial_revisions.py
[P5]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/editorial_versions.py
[P6]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/editorial_construction.py
[P7]: https://github.com/JosephJMWalker-MBA/publication-compositor/pull/154
[P8]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/README.md
[P9]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/renderers/typst/render_proof.py
[P10]: https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/cli.py

Additional inspected implementation evidence:

- Hermeneia [hashing](https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/storage/hashing.py), [Reader projection and canonical span](https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/web/reader_projection.py), [Reader API](https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/web/app.py), [workspace restore](https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/workspace/restore.py), [build](https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/hermeneia/cli/build_cmd.py), and [release-authority tests](https://github.com/JosephJMWalker-MBA/Hermeneia/blob/82300fbed9d691c63e269896f2075bab3e322523/tests/test_publication_release_authority.py).
- Compositor [canonical source verifier](https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/canonical/verify.py), [canonical hash semantics](https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/canonical/hashing.py), [source heading-depth evidence](https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/canonical/heading_depth_models.py), [Typst compilation](https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/renderers/typst/compile.py), [role-aware findings](https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/analyze/typst_rendered.py), [page-level findings](https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/src/publication_compositor/analyze/rendered.py), and [editorial control metadata boundary](https://github.com/JosephJMWalker-MBA/publication-compositor/blob/7c671c7f1479d4d0c82e7e383b8bb6c00ae10dc2/docs/editorial-control-metadata.md).
