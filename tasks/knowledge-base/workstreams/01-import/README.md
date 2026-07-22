# Knowledge Base — Import Workstream Packet

## Objective & Hypothesis

Define the first independently implementable boundary of Knowledge Base: turn a
user-selected MVP file into an immutable, reviewable **Canonical Document Envelope**
that freezes a **DoclingDocument** content IR. The import service and its workspace
UI must remain useful before chunking, embedding, indexing, and Agent lookup exist.

The working hypothesis is that import completes at **canonical-ready**, not at
retrieval-ready. This makes source handling, parsing, OCR quality, failure recovery,
and user trust independently testable. Later storage and tool workstreams consume a
published canonical generation through a narrow port.

## Status

**Locally verified after follow-up remediation.** The executable path accepts TXT,
DOC/DOCX, PDF, JPEG, and PNG through one format registry, publishes an immutable
DoclingDocument bundle at canonical-ready, and hands retrieval work to an independent
derivation service. The follow-up packet owns final Slice acceptance and evidence.

## Durable Owners / Blast Radius

| Claim | Intended durable owner when approved | Main affected surfaces |
| --- | --- | --- |
| Import commands, lifecycle, recovery | Knowledge Base service design | service composition, storage migrations, background runner |
| Source snapshot/open identity | Artifact and storage ownership | `ArtifactService`, LinkRouter, filesystem lifecycle |
| Format adapters and document-AI routing | Knowledge Base / Document AI capability contracts | provider settings, package/runtime validation |
| Import workspace and queue | UI design | `MainWindow`, Settings, translation, Qt background updates |
| Retrieval readiness and citations | Later storage/tool workstreams | no change in this packet |

## State Diff (From -> To)

**From:** Xenix can register non-tabular bytes as artifacts, but has no document
import lifecycle, canonical projection, persistent import queue, or document-AI
configuration surface.

**To:** one global default library accepts TXT, DOC, DOCX, PDF, JPEG, and PNG
sources; it snapshots each source, produces a versioned Docling
IR/envelope generation when possible, and exposes bounded, persistent status in a
secondary workspace. The internal library identity remains extensible to multiple
instances, but no multiple-library UI or selection is exposed in MVP.
Canonical-ready deliberately does not imply searchable or Agent-available.

## Invariants

- The user's original file is never modified, moved, or deleted.
- A source snapshot is app-owned, immutable, content-hashed, and registered through
  `ArtifactService` only after it has a stable app-owned location.
- A partial or unverified canonical generation is never current or user-visible.
- Retries create a new immutable attempt/generation; they never alter a previously
  published canonical generation in place.
- UI code does not construct storage paths, open provider clients, or receive raw
  provider diagnostics; source opening uses `artifact://` identity.
- OCR runs through Xenix's independently managed local PaddleOCR capability. Its
  private runtime and model cache are installed by an explicit one-click action.
- VLM is out of MVP scope: no provider profile, route, UI, or projection is created.
- Markdown is out of MVP scope even though a parser may support it; external-resource
  semantics must not be imported accidentally.
- Import never publishes retrieval Units. It emits canonical-ready identity to the
  independently recoverable derivation service after the canonical transaction.

## Decisions Consumed

- The product exposes one global default Library in MVP. Its internal identity and
  service boundary retain a future multiple-library extension path.
- MVP source formats are TXT, DOC, DOCX, PDF, JPEG, and PNG.
- SQLite owns bounded metadata; large source/canonical bytes remain filesystem-owned.
- Existing `ArtifactService` owns registered user-openable artifacts.
- `DoclingDocument` is the unified content IR; Xenix lifecycle/import state is a
  separate envelope.
- OCR is an independent service. MVP uses a one-click private local PaddleOCR
  runtime; VLM and remote OCR profiles are outside this slice.
- Same SHA-256 content in the global library defaults to reuse/deduplication.
- Encrypted documents are in MVP; a password exists only in process memory for the
  active attempt and is never persisted.
- DOC normalizes to DOCX by default. The repeatable fidelity spike found equivalent
  body/table recall, DOCX picture retention, and PDF-only page locators.

## Explicit Follow-ups

1. Tune format/resource limits against broader production corpora without weakening
   the current fail-closed bounds.
2. Add document list/detail/open-source and enqueue-time preflight UX in a later UI
   slice; the current approved surface is Workspace + modeless durable queue.
3. Evaluate structured PP-StructureV3 enrichment separately from the current OCR
   text service and preserve the no-VLM MVP boundary.

## Verification Plan

- Review the service, extensible pipeline, Docling IR, PDF/OCR, UI, and durable-doc
  plan against the invariants above and the existing Artifact/Qt boundaries.
- Keep the pinned Docling/Windows packaged exercise and repeatable DOC fidelity spike
  on Chinese paragraphs, tables, images, and pagination as regression evidence for
  the selected `DOC -> DOCX` adapter.
- Maintain real fixtures for all six format families and page-level PDF OCR routing.
- Add encrypted-document and resource-limit fixtures before those promises become
  release gates.

## Verification Run Log

- 2026-07-14: read-only repository scan confirmed `ArtifactService`, SQLModel,
  filesystem/SQLite ownership, the existing dataset-only attachment path, MainWindow
  composition, Qt translation behavior, and the absence of a document-import service.
- 2026-07-14: packet validation passed for 19 Markdown files: all relative packet
  links resolve, all required control headings are present, and no trailing
  whitespace was found.
- 2026-07-22: the repeatable DOC comparison selected DOC→DOCX; bilingual Workspace/
  Queue and Embedding settings captures passed visual review. See
  [DOC fidelity evidence](../../evidence/doc-fidelity-spike.md) and
  [UI visual evidence](../../evidence/ui-visual-qa.md).

## Next Action

Import-local acceptance is complete. Two live Phase B cells prove the real
Import→Derivation path and exact Dataset but fail grounded final-answer wording; that
remaining repair belongs to Agent outcome acceptance, not Import.

## Packet Map

- [Service topology and lifecycle](service-design.md)
- [Extensible pipeline contract](pipeline-contract.md)
- [Docling content IR and lifecycle envelope](docling-ir.md)
- [Format routing and document-AI policy](format-routing.md)
- [PDF page routing and Paddle OCR service](pdf-ocr-design.md)
- [Import workspace and interaction design](ui-design.md)
- [Decision register](decision-register.md)
- [Durable-document promotion plan](durable-docs-plan.md)
