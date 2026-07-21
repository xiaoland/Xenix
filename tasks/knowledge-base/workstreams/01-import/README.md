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

**Implemented MVP slice; packaging verification remains open.** The executable
contract is TXT, DOC/DOCX, PPT/PPTX, and PDF into a DoclingDocument envelope, with
page-level PDF text probing and a private local PaddleOCR deployment. Storage and
Agent lookup are reviewed in their own workstreams.

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

**To:** one global default library accepts TXT, DOC, DOCX, PPT, PPTX, and PDF
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
- Import publishes retrieval units only after the canonical envelope is durable; the
  lookup implementation remains owned by the storage/tool workstreams.

## Decisions Consumed

- The product exposes one global default Library in MVP. Its internal identity and
  service boundary retain a future multiple-library extension path.
- MVP source formats are TXT, DOC, DOCX, PPT, PPTX, and PDF.
- SQLite owns bounded metadata; large source/canonical bytes remain filesystem-owned.
- Existing `ArtifactService` owns registered user-openable artifacts.
- `DoclingDocument` is the unified content IR; Xenix lifecycle/import state is a
  separate envelope.
- OCR is an independent service. MVP uses a one-click private local PaddleOCR
  runtime; VLM and remote OCR profiles are outside this slice.
- Same SHA-256 content in the global library defaults to reuse/deduplication.
- Encrypted documents are in MVP; a password exists only in process memory for the
  active attempt and is never persisted.
- DOC conversion is selected only after the agreed PDF-versus-DOCX fidelity spike.

## Open Questions

1. Can the complete Docling dependency graph be packaged within an acceptable build
   time and application size on Windows?
2. What concrete file/page and subprocess limits fit target desktop hardware?
3. Which encrypted-document adapters can honor the temporary-password contract
   without persisting the password?

## Verification Plan

- Review the service, extensible pipeline, Docling IR, PDF/OCR, UI, and durable-doc
  plan against the invariants above and the existing Artifact/Qt boundaries.
- Run a pinned Docling/Windows package spike and a DOC conversion spike on Chinese
  paragraphs, tables, images, and pagination; compare `DOC -> PDF` against a
  `DOC -> DOCX` control before selecting the adapter implementation.
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

## Next Action

Complete packaged-runtime verification, then promote the stable contracts into the
durable PRD/TDD owners named by this packet.

## Packet Map

- [Service topology and lifecycle](service-design.md)
- [Extensible pipeline contract](pipeline-contract.md)
- [Docling content IR and lifecycle envelope](docling-ir.md)
- [Format routing and document-AI policy](format-routing.md)
- [PDF page routing and Paddle OCR service](pdf-ocr-design.md)
- [Import workspace and interaction design](ui-design.md)
- [Decision register](decision-register.md)
- [Durable-document promotion plan](durable-docs-plan.md)
