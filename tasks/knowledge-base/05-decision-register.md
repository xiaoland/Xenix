# Knowledge Base Decision Register

## Confirmed Product Direction

| Decision | Status | Rationale |
| --- | --- | --- |
| Reuse SQLModel/SQLAlchemy | confirmed | It is already a direct project dependency and storage uses it. |
| SQLite contents for Knowledge retrieval | confirmed | SQLite stores lifecycle, bounded Unit text, locators, FTS projection, and current-generation metadata; source/canonical bytes and Lance vectors stay outside. |
| Reuse `ArtifactService` for stable source identity/activation | confirmed direction | It preserves `artifact://` and avoids path leakage. |
| Keep Document AI separate from `LLMService` | confirmed | OCR/embedding lifecycle, credentials, and transport differ from chat. |
| MVP Library UX | confirmed | One global default library; internal identity remains future-extensible. |
| MVP formats | confirmed | TXT, DOC, DOCX, PDF, JPEG, PNG; no Markdown. |
| Docling content IR | confirmed | `DoclingDocument` is frozen content IR; Xenix lifecycle/provenance is an envelope. |
| External OCR routing | confirmed | User-configured OCR may receive content without per-import consent. |
| OCR MVP provider direction | confirmed and implemented | One-click Xenix-owned official Paddle Inference C++ worker archive; externally configured OCR remains an extension of the same independent service boundary. |
| VLM | confirmed exclusion | No VLM provider, UI, or projection in MVP. |
| Duplicate/encryption policy | confirmed | Same SHA defaults to reuse; passwords are transient and never persisted. |

## Import Decisions and Spike Gates

| Decision | Position | Gate |
| --- | --- | --- |
| Canonical-ready boundary | import publishes envelope + Docling JSON/assets, not chunks/indexes | service/storage tests |
| DOC route | LibreOffice DOC→DOCX default; PDF remains a diagnostic alternative | Repeatable 2026-07-22 fidelity spike retained picture/table structure on DOCX and page locators on PDF |
| PDF route | document probe plus page-level native/OCR/hybrid/layout route | per-page fixture/merge spike |
| PDF helper | pikepdf is bounded probe/decrypt/preprocess support; source is never rewritten | boundary, encrypted-flow, and packaged smoke evidence |
| TXT route | explicit decoder + `charset-normalizer` candidate evidence; retain sidecar locator | encoding/CJK fixture spike |
| Format detection | Xenix signature/container probe primary; `python-magic` only optional corroboration | libmagic Windows/package spike |
| Local PP-StructureV3 | future structured-document enrichment; current native worker provides PaddleOCR text extraction only | separate layout/table quality and package spike |
| Docling runtime | pin Docling/core/models and use referenced assets/explicit offline cache | clean Windows/package/license spike |

## Deferred to Storage and Tool Workstreams

- chunk shape and Docling-to-chunk adapter;
- embedding profiles/vector/keyword index implementation and hybrid ranking;
- search readiness, tool parameters/results, citations, and Agent replay;
- global-library expansion UI/scope behavior; and
- deletion/retention/migration/backup policy.

## Out-of-Scope but Relevant Debt

Some current ML paths expose raw local paths and a non-Artifact `artifact_id` shape in
Agent/UI flows. That is a real artifact-boundary mismatch, but it is not folded into
Knowledge Base work because a related Agent/LLM boundary task exists. This work must
not reproduce the leak.

## Current Gate

Local implementation and delivery remediation are authorized and verified through
Slice 01. The remaining acceptance action is the externally configured Phase B live
Agent outcome cell; commits still require Sir's explicit command.
