# Technology-Stack Proposal

## Decision Principle

Adopt **Docling as the core document parser and DoclingDocument as the content IR**,
but do not turn it into lifecycle/storage authority. Xenix keeps an envelope around
the frozen IR, a source artifact/snapshot, and independent document-AI capability
ports. No RAG framework, vector database, generic AI orchestrator, or VLM is needed
for the import MVP.

Every candidate must pass compatible Python 3.12–3.14 Windows wheels, clean
PyInstaller/package smoke, model/artifact licensing, offline behavior, Chinese
text/table/scan/image quality, and bounded resource tests before becoming a product
dependency.

## Import Stack Candidates

| Need | Candidate / role | Position |
| --- | --- | --- |
| Content IR/parser | Docling + pinned `docling-core` | Core proposal; version/model/package spike required |
| TXT detection/decoding | stdlib BOM/strict decoder + direct `charset-normalizer` use | Recommended; preserve byte/line sidecar |
| File signatures | Xenix signature/container probe | MVP core; `python-magic` only optional corroboration after DLL spike |
| DOCX | Docling primary; Mammoth diagnostic fallback | Recommended primary/supplement separation |
| Pandoc | Explicit fidelity/repair experiment only | Not automatic MVP runtime fallback |
| Legacy DOC | Pinned LibreOffice headless conversion capability | Required comparative PDF-vs-DOCX spike |
| PDF probe/repair | `pikepdf` / QPDF candidate | Optional, bounded/preprocessor only; package spike |
| PDF native/layout/render | Docling PDF adapter under Xenix page route; selected renderer/probe helpers after spike | Core route, not one whole-file pipeline |
| Remote OCR | PaddleOCR Official API (AI Studio) adapter under `OcrService` | MVP direction; real API/schema/package spike |
| Local structured OCR | PP-StructureV3 sidecar/worker/self-hosted service | Future only; not GUI-process dependency |
| VLM | None | Explicitly excluded from MVP |

No dependency is added by this packet.

## Docling: Core IR With Explicit Runtime Discipline

Docling supports the principal target family—PDF, DOCX, JPEG/PNG and current
plain-text pathways—and serializes a DoclingDocument to lossless JSON. Its document
model supplies hierarchy, tables, pictures, pages, layout, and provenance.
[Supported formats](https://docling-project.github.io/docling/usage/supported_formats/)
[DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/)

However, it is not a zero-cost library. PDF/image pipelines use model assets and
native/ML dependencies; offline execution requires prefetching at a pinned artifacts
path. The code license does not automatically license model-weight redistribution.
The standard PDF configuration can invoke OCR, so Xenix must explicitly disable or
avoid it on pages delegated to `OcrService`. Docling `page_range` permits selected
pages but is an execution primitive, not a native/scanned route policy and cannot be
assumed equivalent to a full-document pass. [Docling installation](https://docling-project.github.io/docling/getting_started/installation/)
[Docling converter reference](https://docling-project.github.io/docling/reference/document_converter/)

Persist Docling JSON with referenced app-owned assets, checksums, and exact
Docling/core/backend/model descriptors. Do not use its origin URI/hash or metadata as
Xenix source/lifecycle authority, and do not embed lifecycle fields/custom top-level
state into the external schema.

## Text, DOCX, and DOC

`charset-normalizer.from_bytes` is appropriate evidence for encoding candidates, but
not a blind decoder; choose within a documented allowed set and retain the choice and
line/byte sidecar. [charset-normalizer API](https://charset-normalizer.readthedocs.io/en/latest/api.html)

`python-magic` is not the accepted-format authority in MVP. It wraps libmagic,
requires DLLs on Windows, and warns its `Magic` object is not thread-safe. A local
signature/container registry covers the MVP formats deterministically; libmagic can
be added only if clean package evidence shows net value. [python-magic](https://pypi.org/project/python-magic/)

Docling is the DOCX path. Mammoth is a supplemental semantic HTML/text comparator:
it intentionally favors simple semantic output and admits complex DOCX will not be
perfect. Pandoc is GPL and an external executable, useful in a controlled conversion
spike but not silently run in the desktop pipeline. [Mammoth](https://github.com/mwilliamson/python-mammoth)
[Pandoc licensing](https://pandoc.org/index.html)

Legacy binary DOC still requires a versioned LibreOffice headless conversion
capability. The spike compares `DOC -> PDF` and `DOC -> DOCX` for Chinese paragraphs,
tables, images, headers/footers, and citations. The original DOC stays the source
artifact; every intermediate is checksummed and attempt-local. [LibreOffice command line](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html?DbPAR=BASIC&System=WIN)

## PDF: Per-Page Policy

`pikepdf` is a candidate for encryption/page/syntax/limit evidence and explicit
derived repair, powered by QPDF. It is neither the text/layout parser nor renderer,
and it must never silently rewrite the source. Its native packaging/licensing still
needs a Windows/PyInstaller spike. [pikepdf tutorial](https://pikepdf.readthedocs.io/en/latest/tutorial.html)
[pikepdf installation](https://pikepdf.readthedocs.io/en/stable/installation.html)

The route is document probe → per-page quality probe → native, OCR, hybrid, or
complex-layout Docling route → one provenance-preserving IR assembly. A page rendered
for OCR must retain a coordinate transform and page identity. Native and OCR text are
kept as labelled projections when they conflict; a later retrieval policy chooses
search visibility.

## OCR: Paddle API First, Local Structure Later

`OcrService` is an independent service, not a Docling/LLM convenience function. Its
first candidate adapter submits selected image/page bytes to the configured PaddleOCR
Official API (AI Studio), handles asynchronous submit/poll/download within a bounded
budget, normalizes text/polygon/confidence/language/version results, and records a
non-secret profile descriptor. A direct HTTP adapter versus official SDK decision
must be made by a clean-package/schema spike; an API SDK can still pull substantial
native dependencies. [PaddleOCR Official API](https://www.paddleocr.ai/main/en/version3.x/inference_deployment/serving/paddleocr_official_api/overview.html)

PP-StructureV3 belongs to a future `StructuredDocumentCapability`, not the MVP OCR
adapter: it performs layout/table/document analysis, has model/runtime complexity, and
should run in a sidecar, worker, or self-hosted service rather than inside the GUI
process unless a dedicated package/Python/runtime spike proves otherwise.
[PP-StructureV3](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/PP-StructureV3.html)

## Later Retrieval Stack

Storage/tool workstreams will decide chunks, embeddings, keyword/vector persistence,
hybrid ranking, and Agent contract. They must consume frozen Docling/envelope
generations and retain the existing SQLite-metadata-only rule. No index/vector
dependency is selected by this import workstream.

## Mandatory Spikes Before Product Implementation

1. Pinned Docling/core/model/assets: all MVP fixtures, JSON referenced assets,
   page-range/merge behavior, offline artifact path, model licenses, clean package.
2. TXT/DOCX/DOC: CJK decode/line map; Mammoth/Pandoc comparison only where useful;
   LibreOffice PDF-vs-DOCX fidelity/cancellation/distribution.
3. PDF: native/scanned/mixed/OCR-layer/broken-font/complex-layout per-page route,
   pikepdf encrypted/damaged behavior, coordinate/manifest correctness.
4. Paddle AI Studio: upload/submit/poll/download/schema/error/quota/page mapping,
   token redaction, CJK quality, cancellation semantics, SDK-vs-HTTP packaging.
5. PP-StructureV3: separate CPU/GPU/sidecar/worker/Python/package/model-disk proof;
   no commitment follows merely from a Python demo.
