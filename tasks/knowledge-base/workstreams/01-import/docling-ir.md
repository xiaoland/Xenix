# Docling Content IR and Xenix Lifecycle Envelope

## Decision

Use **DoclingDocument** as the content-level intermediate representation (IR) for
the import workstream. Do not invent a parallel Xenix tree of paragraphs, tables,
images, and provenance. Docling already models document hierarchy, reading order,
text, tables, pictures, pages, bounding boxes, and provenance, and supports
lossless JSON serialization. [DoclingDocument concept](https://docling-project.github.io/docling/concepts/docling_document/)
[Supported formats and JSON output](https://docling-project.github.io/docling/usage/supported_formats/)

Use a separate, Xenix-owned **Canonical Document Envelope** for application
lifecycle. The envelope refers to a frozen Docling JSON payload and its assets; it
does not inject app status, import IDs, artifact URIs, secrets, or retrieval state
into Docling's content model.

```text
CanonicalDocumentEnvelope (Xenix-owned, immutable)
  envelope_schema_version
  document_id, canonical_generation_id, import_id
  source: artifact_id, SHA-256, original media type, display name
  content_ir:
    kind = "docling_document"
    docling_version, docling_core_version, schema_name/schema fingerprint
    relative_json_ref, SHA-256
  pipeline_descriptor: probe/normalization/router/parser/OCR versions and profiles
  assets/projection manifest: relative refs + checksums + source relation
  warnings/loss notes and validation summary

docling-document.json (Docling-owned content IR)
  pages, body/furniture/groups, texts, tables, pictures, item provenance/layout
```

The envelope remains the source of application authority; `DoclingDocument` remains
the source of content semantics. SQLite later stores bounded envelope metadata and
file locators, never the full Docling JSON or images.

Docling's own `origin` URI/binary hash and document version are useful subordinate
conversion facts, but cannot substitute for Xenix source identity: an origin may
carry a path-like URI and the binary-hash representation is not Xenix's full SHA-256
authority. Lifecycle state is likewise never added as custom Docling top-level fields
or assumed to survive arbitrary Docling schema/plugin changes.

## Why This Is the Right Split

The proposed split avoids two expensive failures:

1. **Content drift.** A homegrown Canonical Document structure would need to chase
   every new Docling table/picture/page/provenance feature and could silently lose
   content during conversion.
2. **Lifecycle leakage.** Putting retries, user status, library selection, artifact
   identity, or provider configuration inside the Docling model makes a reusable IR
   application-specific and complicates upgrades/replay.

`Canonicalizer` therefore validates and freezes the content IR; it does not
reinterpret headings, tables, page geometry, or reading order. Later chunking should
consume the frozen DoclingDocument through a version-pinned adapter, not reparse the
source file.

## Adapter Rules

`DoclingAdapter` is the primary parser path for DOCX, PDF, JPEG, and PNG. It returns
a `DoclingDocument` plus conversion warnings/provenance. It must pin Docling and
`docling-core` versions, record the selected backend/pipeline options, and serialize
the result immediately while those versions are available.

Not every allowed source can be delegated blindly:

| Source | Primary content path | Required caveat |
| --- | --- | --- |
| DOCX | Docling adapter | Preserve Docling loss notes; do not claim page locator where DOCX has none. |
| TXT | `PlainTextToDoclingAdapter` over Docling's text/Markdown input path | Keep an Xenix byte/line/character sidecar. Current Docling text input is handled through the Markdown/Marko route, so it cannot itself promise pure-text line/character locators. |
| PDF | Docling PDF adapter, under a page-route plan | Docling's standard PDF pipeline can enable OCR by default; explicitly disable/avoid it whenever the selected route delegates OCR to Xenix `OcrService`, so two engines never run silently. |
| JPEG/PNG | Docling image adapter or an OCR-to-Docling adapter | The source image stays authoritative; OCR text is a labelled projection. |
| DOC | Office conversion adapter, then the resulting DOCX/PDF is passed to Docling | Legacy binary DOC is not in Docling's supported-input list. |

Mammoth is a **supplemental diagnostic/fallback adapter** for DOCX semantic HTML/text,
not a second canonical IR: it intentionally favors simple semantic HTML over visual
fidelity and warns that complex documents will not convert perfectly. Its output must
be translated into a DoclingDocument with an explicit loss note if used.
[Mammoth documentation](https://github.com/mwilliamson/python-mammoth)

Pandoc is not an automatic runtime fallback in the initial import path. It is a GPL
external executable whose conversions are valuable for a controlled fidelity spike,
but it enlarges packaging and usually yields an interchange representation rather
than page-level Docling provenance. It can be reconsidered as an explicit, versioned
adapter after the spike and distribution review. [Pandoc licensing](https://pandoc.org/index.html)

## Freeze and Compatibility Contract

Canonical publication must persist all of the following together:

- `docling-document.json`, written with a deterministic **referenced-asset** policy
  rather than embedding page/picture bytes as base64 in a huge JSON payload;
- the envelope and asset/projection manifest, each checksummed;
- Docling/docling-core versions, schema name/fingerprint, parser backend, models,
  normalization/OCR descriptors, and source/intermediate hashes.

Reading an old generation never silently regenerates it with a newer Docling build.
If a future release needs a content migration, it creates a new canonical generation
with a declared migration descriptor and retains the old generation for citation and
replay. A `DoclingDocument` validation failure is an import failure, never a partial
publication.

Every referenced asset must be app-owned staging/final content, relative to the
generation root, containment-checked, and checksummed. Absolute local paths, provider
URLs, and a Docling serializer's default embedded image payload are not canonical
artifact references. Unknown/unsupported Docling fields are a compatibility error or
explicit migration case—not an excuse to attach untyped application metadata.

## Explicit MVP Exclusions

- No VLM capability, provider profile, UI, or content projection in MVP.
- No Markdown import even though Docling can parse it: linked/local/remote resources
  create a different authority and security problem. The input allowlist is the
  product contract, not the complete Docling format list.
- No use of Docling's RAG chunker during import. Chunking is the later storage
  workstream and must preserve the frozen generation's provenance.

## Required Docling Spike

Pin an exact candidate version and prove, on clean Windows development and packaged
runtime:

1. DOCX, native/scanned/mixed PDF, JPEG, PNG, and TXT conversion to Docling JSON;
2. page/bounding-box and table/picture provenance that survives serialization;
3. CPU/RAM/disk/model-download behavior and fully offline rerun after model cache is
   staged at a pinned artifacts path;
4. page-range conversion/merge behavior for the PDF router;
5. no accidental builtin OCR/VLM invocation when Xenix has selected a different
   route; and
6. license/NOTICE and PyInstaller collection behavior for every selected extra/model.

Docling's code license alone is not sufficient evidence that all selected model
weights may be redistributed. The spike must inventory code, native, model, and
artifact licenses separately.
