# Knowledge document intelligence

## Goal

Strengthen the local Knowledge Library by learning from DocQ's document-first design
without embedding DocQ itself. Use a maintained local Rust parser boundary, preserve
document structure in canonical content, and improve retrieval units.

## Decisions

- Use `firecrawl-anydoc` 0.2.4 as the packaged Rust-backed document parser.
- Keep Xenix's immutable format registry and DoclingDocument canonical IR.
- Parse DOC/DOCX, PPT/PPTX, RTF, EPUB, ODT, and ODP through one AnyDoc provider.
- Validate container identity, paths, entry counts, expansion, and compression before
  parsing ZIP-based formats.
- Preserve headings as retrieval context and use bounded sentence-aware overlap.
- Do not run LibreOffice or embed DocQ as a subprocess/service.

## Acceptance

- Existing Office imports remain locally parsed and source bytes remain immutable.
- RTF, EPUB, ODT, and ODP are admitted through explicit format capabilities.
- Parser failures produce stable, content-free error codes.
- Packaged builds include the AnyDoc extension and distribution metadata.
- Packaged smoke executes the real Rust parser.
- Retrieval units carry heading paths, obey the normalized size limit, and make
  progress for unbroken text.
- Unit tests cover routing, probes, unsafe packages, Markdown adaptation, structure,
  overlap, and Unicode normalization.

## Verification

Run formatting/linting, the focused Knowledge tests, the packaged-smoke unit tests,
and the complete test suite before release packaging.
