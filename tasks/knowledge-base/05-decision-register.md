# Knowledge Base Decision Register

## Confirmed Product Direction

| Decision | Status | Rationale |
| --- | --- | --- |
| Reuse SQLModel/SQLAlchemy | confirmed | It is already a direct project dependency and storage uses it. |
| SQLite contents for Knowledge retrieval | under review | Sir requested a retrieval-first redesign; raw source/IR bytes remain outside, but normalized retrieval-unit text/index placement is not yet decided. |
| Reuse `ArtifactService` for stable source identity/activation | confirmed direction | It preserves `artifact://` and avoids path leakage. |
| Keep Document AI separate from `LLMService` | confirmed | OCR/embedding lifecycle, credentials, and transport differ from chat. |
| MVP Library UX | confirmed | One global default library; internal identity remains future-extensible. |
| MVP formats | confirmed | TXT, DOC, DOCX, PDF, JPEG, PNG; no Markdown. |
| Docling content IR | confirmed | `DoclingDocument` is frozen content IR; Xenix lifecycle/provenance is an envelope. |
| External OCR routing | confirmed | User-configured OCR may receive content without per-import consent. |
| OCR MVP provider direction | confirmed direction | PaddleOCR Official API (AI Studio) through an independent service adapter. |
| VLM | confirmed exclusion | No VLM provider, UI, or projection in MVP. |
| Duplicate/encryption policy | confirmed | Same SHA defaults to reuse; passwords are transient and never persisted. |

## Import Decisions and Spike Gates

| Decision | Position | Gate |
| --- | --- | --- |
| Canonical-ready boundary | import publishes envelope + Docling JSON/assets, not chunks/indexes | service/storage tests |
| DOC route | LibreOffice conversion; compare PDF and DOCX intermediates | Chinese fidelity/package spike |
| PDF route | document probe plus page-level native/OCR/hybrid/layout route | per-page fixture/merge spike |
| PDF helper | evaluate pikepdf only as bounded probe/explicit repair support | Windows/QPDF/PyInstaller/license spike |
| TXT route | explicit decoder + `charset-normalizer` candidate evidence; retain sidecar locator | encoding/CJK fixture spike |
| Format detection | Xenix signature/container probe primary; `python-magic` only optional corroboration | libmagic Windows/package spike |
| Local PP-StructureV3 | future structured-document capability, likely sidecar/worker | runtime/model/Python/PyInstaller spike |
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

## Approval Gate

The next executable step is a scoped Impact Handshake for a **spike only**, naming
exact dependencies, package/runtime evidence, fixtures, and no durable/product change
beyond the approved experiment. Product implementation begins only after Sir
explicitly approves that handshake and says to start.
