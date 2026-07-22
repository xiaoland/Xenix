# Canonical Document and Ingestion

## Canonical Content Is DoclingDocument

Use `DoclingDocument` as the uniform content IR for parsed TXT, DOCX, PDF, JPEG, and
PNG sources (and DOC after a named conversion route). It represents structured text,
tables, pictures, hierarchy, pages, layout bounding boxes, reading order, and
provenance. Xenix must not maintain a second competing tree of blocks/tables/images.

Docling content is wrapped by an application-owned **Canonical Document Envelope**:

```text
CanonicalDocumentEnvelope
  envelope_schema_version
  document_id, canonical_generation_id, import_id
  source: artifact_id, SHA-256, media type, display name
  content_ir: Docling JSON relative ref, hash, Docling/docling-core/schema versions
  pipeline descriptor: probe, normalizer, router, parser, OCR profiles/versions
  assets/projections: relative refs, checksums, source relation/coordinate transforms
  warnings/loss notes, validation summary

docling-document.json
  DoclingDocument's lossless content, hierarchy, items, pages, tables, pictures,
  layout, and provenance
```

The source snapshot remains provenance authority. The envelope owns Xenix application
identity and lifecycle; Docling owns content semantics. SQLite later holds only bounded
metadata/locators, never the Docling JSON, source bytes, images, or provider payloads.

## Why the Envelope Is Separate

Import attempts, status, retry history, artifact URIs, source hashes, provider
configuration fingerprints, and current-generation pointers are Xenix concerns. They
must not be embedded in or inferred from an external IR. Conversely, Xenix must not
reinterpret a Docling table, picture, page, or item tree into lossy private fields.

Canonicalization therefore means **validate and freeze**, not “convert Docling into
our own block schema.” The canonicalizer writes version-pinned Docling JSON with an
envelope/asset manifest and checksums. A later Docling upgrade creates a new generation
through an explicit migration/reparse descriptor; it never silently rewrites a cited
old generation.

## Format Routing

| Format | Content path | Important rule |
| --- | --- | --- |
| TXT | Explicit decoding and PlainText-to-Docling adapter | Preserve byte/line/character provenance; no replacement-character fiction |
| DOCX | Docling primary adapter | Preserve structural provenance/loss notes; no invented page locator |
| DOC | LibreOffice conversion plan, then Docling PDF/DOCX adapter | Never treat binary DOC as DOCX; retain source + intermediate lineage |
| PDF | Per-page route plan into Docling assembly | Native/OCR/hybrid/complex-layout choices may vary by page |
| JPEG/PNG | Docling image or OCR-to-Docling adapter | Source image is retained; OCR is a labelled text/geometry projection |

Only TXT, DOC, DOCX, PDF, JPEG, and PNG are accepted in MVP. Markdown is deliberately
excluded despite parser support because resolving its resource references needs a
separate security/authority contract. Detailed design is in
[workstreams/01-import](workstreams/01-import/README.md).

## Page and Projection Provenance

Every Docling item or envelope sidecar projection must retain enough provenance for a
later citation to reach original evidence: source artifact, canonical generation,
source/intermediate relation, original page/image coordinate system, item/self-ref or
line range, extraction method, confidence, and transformation descriptor.

For PDF, this means a single DoclingDocument may contain native-text items on page 1,
OCR items on page 2, and a hybrid/native-plus-OCR record on page 3. OCR output does
not overwrite native text invisibly. A future retrieval policy chooses which labelled
projection is searchable/displayed and preserves both when quality is disputed.

## Ingestion State and Recovery

Import ends at canonical-ready:

```text
queued -> snapshotting -> probe -> normalize -> route -> parse/OCR
       -> canonicalize -> validate/publish -> canonical-ready
any nonterminal phase -> cancel-requested -> cancelled
any nonterminal phase -> needs-attention | failed
```

Chunking, embedding, and indexing later consume canonical-ready input and establish
their own readiness. Retry creates a new immutable attempt/generation or resumes a
proven idempotent checkpoint; it never mutates a published canonical generation.

## OCR and VLM Policy

- OCR is conditional and independent from `LLMService`. MVP uses a privately managed
  local PaddleOCR worker, normalized into a typed bounded projection with engine/
  package/protocol/model descriptors, text, confidence, and outcome.
- OCR may receive content through the user-configured profile without a per-import
  confirmation. It may never receive a raw local path, credentials, or unrelated
  document bundle.
- OCR absence/failure leaves a valid image/scanned-page item canonical-ready with a
  visible missing-text warning; it does not fabricate text.
- VLM has no MVP route, configuration, or projection. It is not an ingestion
  prerequisite and has no implicit relationship to the selected chat model.
