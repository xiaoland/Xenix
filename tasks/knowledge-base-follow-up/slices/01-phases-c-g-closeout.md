# Slice 01 / Phases C–G — Local Closeout

**State:** locally implemented and verified on 2026-07-22
**External exception:** credentials are now proven, but two live Phase B cells fail
the grounded final-answer check despite exact Datasets and full integrity.
**Slice disposition:** Slice 01 closed by Sir on 2026-07-22; the exception is carried
to Slice 02 and remains failed evidence.

## Objective

Complete every Slice 01 obligation that can be proven locally, so the only remaining
acceptance item is a passing real-provider Phase B outcome cell. Phase names remain
internal work sequencing; this is not a new slice.

## Impact Handshake

- **Address and object:** canonical envelope/CAS; Knowledge schema/repositories;
  derivation publication; import pipeline, persistent queue, OCR capability and UI;
  generic Tool validation/redaction; PyInstaller collection and packaged smoke;
  durable Product/Deployment contracts, task evidence, and black-box tests.
- **State diff:** source-hash-addressed combined canonical blob and UI-owned import
  threads become an envelope-hash-addressed immutable bundle, independent retrieval
  derivation, and a service-owned durable queue. Promised TXT/DOC/DOCX/PDF/JPEG/PNG
  replaces the unapproved PPT/PPTX set. Advertised Tool schemas become executable.
- **Blast radius:** schema upgrade, new imports and retries, current Knowledge lookup,
  Workspace/Queue presentation, OCR installation/readiness, startup/shutdown,
  dependency lock, frozen application size/startup and smoke time.
- **Invariants:** user files are untouched; SQLite is lifecycle/readiness authority;
  DoclingDocument is content IR; filesystem and Lance content are derived/immutable;
  source/open identity stays in ArtifactService; Import has no Embedding/Lance
  dependency; one minimal canonical ToolResult remains; credentials/passwords/raw
  paths/provider diagnostics never cross persistence, Tool, or UI boundaries;
  historical conversation values are not rewritten.
- **Verification:** fresh and v15/v16/v17/v18 migration fixtures plus ORM reads;
  canonical tamper/content-identity tests; queue close/reopen/recovery tests; atomic
  failure injection; all promised format routes including encrypted PDF/DOC(X) and
  image OCR/no-OCR states; generic Tool-schema/path tests; OCR manifest/health/model
  tests; bilingual UI lifecycle tests; real installed Lance/Docling/PDF/OCR-resource
  smoke; PyInstaller package and packaged smoke; full repository regression; final
  Import/Storage/Tool topology review.

## Target Authority Topology

```text
user file reference (transient)
  -> durable import attempt (queued; no raw path)
  -> app-owned source snapshot + Artifact row
  -> FileProbe -> FormatNormalizer -> ParserRouter -> ParseExecutor
  -> DoclingDocument + route/OCR descriptors
  -> Canonicalizer
  -> immutable envelope-hash-addressed bundle
  -> one SQLite transaction publishes generation + document pointer + canonical_ready

canonical_ready event
  -> independent KnowledgeDerivationService
  -> one SQLite transaction publishes current Units + FTS + retrieval_ready
  -> optional semantic generation remains query-owned/rebuildable
```

The source snapshot may be durable before canonical publication so a password repair
or retry can reuse it. The atomic boundary is the canonical generation, current
document pointer, and import terminal state; retrieval publication is deliberately a
later transaction with its own readiness state.

## Canonical Bundle

One immutable generation directory is addressed by SHA-256 of deterministic envelope
bytes and contains bounded `manifest.json`, `canonical-envelope.json.zst`, and
`docling-document.json.zst`. The envelope identifies document/import/generation,
source artifact/hash/media/display name, Docling/schema versions and IR hash,
probe/normalization/router/parser/OCR descriptors, warnings/assets, and validation
summary. Existing targets are reopened and fully verified; content mismatch is an
integrity failure, never reuse.

SQLite v19 adds immutable canonical-generation metadata and the minimum import queue
and document readiness fields. Legacy v18 columns remain readable for compatibility
but new publication resolves through the generation row and relative contained path.
SQLite v20 adds the deterministic `(planned_document_id, attempt_number)` uniqueness
edge needed by durable retries and repairs duplicate historical attempt numbers in a
fixed migration before installing the constraint.

## Import and Format Routing

`KnowledgeImportService` owns one serialized worker queue. Enqueue persists `queued`
before any worker runs; UI only submits and polls immutable views. Interrupted rows
with a source artifact are re-queued on startup; rows interrupted before snapshot
become a safe reselection-needed state instead of disappearing. Retry creates a new
attempt with the same planned logical document ID. Passwords exist only in the work
item and normalization stack frame.

The product registry admits TXT, DOC, DOCX, PDF, JPEG, and PNG. Signatures/container
facts drive routing; PPT/PPTX are rejected. Encrypted PDF uses a short-lived pikepdf
working copy; encrypted DOC/DOCX uses a short-lived msoffcrypto working copy. Images
produce a valid Docling picture item even without OCR; local Paddle OCR adds a
labelled text projection when ready. PDF native/OCR choice remains page-scoped and is
recorded in the envelope.

## Runtime, Tool, and Delivery Closure

- OCR readiness requires exact worker protocol/package versions plus the installed
  manifest and its recorded model markers; a stale manifest cannot report ready.
- UI maps internal status/phase/error keys through Qt translation, owns polling timer
  shutdown, and never starts import threads or renders raw exceptions.
- `AgentToolRegistry` validates calls against the advertised JSON Schema before
  invocation. Unexpected exceptions become one generic bounded failure; useful
  domain diagnostics must be returned explicitly as `ToolFailure`.
- Frozen smoke exercises Docling/PDFium, pikepdf, Zstandard canonical round-trip,
  LanceDB write/search, and packaged Paddle worker resource resolution. Smoke uses a
  runtime-home-scoped mutex so a developer's interactive instance is not disturbed.

## Completion Rule

Phases C–F were verified only after their black-box and delivery evidence passed.
Phase G then cross-checked Import, Storage, Retrieval, Tool, UI, and package topology
as one system and updated every KB-F01..F17 disposition. At the time, the only unmet
acceptance was Phase B's live outcome; Sir later closed Slice 01 and carried that
failed evidence to Slice 02 as `KB2-F01`.

## Locally Verified Outcome

- Canonical publication uses a deterministic envelope plus independently hashed
  Docling IR and bounded assets. Existing CAS targets are reopened and checked;
  source aliases such as `.jpeg`/`.jpg` converge to one content identity.
- The serialized Import service persists queued attempts before execution, snapshots
  sources without persisting raw input paths or passwords, reclaims interrupted
  attempts at startup, and publishes canonical identity atomically. Derivation is a
  separate state machine and the only production writer of Units/FTS readiness.
- Units are independently bounded to the Embedding protocol limit even when Unicode
  normalization expands text. Keyword excerpts center on the useful query hit;
  semantic lexical misses retain a bounded head excerpt. Page anchors become
  `page N`; other sources receive honest `passage N` locations.
- The format registry and UI agree on TXT, DOC/DOCX, PDF, JPEG, and PNG. The
  repeatable legacy-DOC spike selected DOC→DOCX because both routes retained body
  markers/table data, DOCX alone retained the picture, and PDF only added page
  anchors. Images remain canonical-ready without OCR and become retrieval-ready when
  the local OCR projection exists.
- OCR status validates the installed worker and model markers. Queue/workspace/error
  state is service-owned and translated; visual captures prove readable Chinese and
  English Workspace/Queue surfaces and a masked Embedding credential field.
- The Agent registry enforces JSON Schema before execution and emits bounded safe
  failures. Benchmark setup now uses real Import→Derivation rather than a production
  retrieval write seam; its oracle still grades final deliverables only.
- Packaged Knowledge smoke exercises Zstandard canonical round-trip, Docling/PDFium,
  pikepdf, LanceDB write/search, and the private Paddle worker resource without
  disturbing an interactive Xenix process.

## Global Import / Storage / Tool Cross-review

```text
transient user path
  -> durable Import attempt
  -> source Artifact + source CAS
  -> immutable canonical bundle
  -> SQLite current canonical pointer
  -> independent bounded Units + FTS publication
  -> optional immutable Lance generation over current Unit IDs
  -> one current Unit match
  -> one path-safe {source, location?, excerpt} Tool result
  -> canonical Conversation value copied unchanged to replay and UI
```

The review found one authority per fact: Import owns attempts/source/canonical
publication; SQLite owns mutable current/readiness state and Unit text; Lance owns
only rebuildable vectors; Knowledge retrieval is read-only; the Tool owns only public
validation/projection; Conversation owns the one result value. No Import dependency
on Embedding/Lance, no second ToolResult plane, and no benchmark-only production
write path remains.

## Final Local Verification Evidence

- `pdm run check` — Skill catalog generation/check and Python compilation passed.
- `pdm run test` — 607 non-UI tests passed, 2 explicit conditional tests skipped;
  all 58 UI tests passed.
- Reverse-order native integration (`Knowledge packaged smoke` before graph SVG) —
  22 tests passed. This caught and closed Docling's process-wide ElementTree SVG
  namespace side effect rather than hiding it as an unrelated full-suite failure.
- `pdm run benchmark-agent-harness -- --collect-only` — all 3 cases collected with
  no Provider access.
- `pdm run smoke` — development runtime completed the Knowledge native/data exercise.
- `pdm run package` — the fresh Windows/Python 3.14 PyInstaller build completed.
- `pdm run smoke-package` — the newly built `dist/xenix/xenix.exe` passed packaged
  smoke, including Docling worker, PDFium, pikepdf, Zstandard, LanceDB, and Paddle
  worker-resource checks.
- The repeatable DOC fidelity report and bilingual UI captures are documented in
  [DOC fidelity evidence](../../knowledge-base/evidence/doc-fidelity-spike.md) and
  [UI visual evidence](../../knowledge-base/evidence/ui-visual-qa.md).

## Explicit Non-blocking Follow-ups

1. Add the richer document list/detail/open-source surface and enqueue-time preflight
   to the Workspace after the current import-control slice.
2. Add hierarchy-aware neighboring context and richer table/OCR projection beyond
   the current item/page/passage bounded Units only after retrieval evaluation.
3. Add immediate retry for a failed post-commit derivation notification; current
   restart reconciliation is correct but may delay freshness until restart/manual
   scheduling.
4. Add a bounded retention policy for superseded healthy Lance generations; current
   cleanup safely removes proven orphans/staging but never risks deleting authority.

These items were product/performance refinements rather than unresolved KB-F01..F17
correctness or delivery gaps. The document-list improvement is now admitted to Slice
02, along with process/log, settings, index-control, and multimodal work. Phase B's
grounded final-answer failure is carried as `KB2-F01` rather than rewritten as pass.
