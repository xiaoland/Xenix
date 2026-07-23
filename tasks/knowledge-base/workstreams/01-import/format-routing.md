# Format Routing Policy

## Product Allowlist and Detection Rule

The MVP accepts only TXT, DOC, DOCX, PPT, PPTX, PDF, JPEG, and PNG. The allowlist is a product
decision, not a mirror of every format supported by Docling. Markdown is deliberately
rejected in MVP, because links, included resources, and local/remote resolution need
their own authority/security design.

The authoritative route begins only after an app-owned snapshot is made. `FileProbe`
compares suffix, magic bytes, container structure, and format-specific safety facts;
a mismatch is a bounded preflight/import error, never an optimistic parser fallback.

| Claimed source | Recognition evidence | Normalized parser input | Primary IR path | Locator policy |
| --- | --- | --- | --- | --- |
| TXT | binary/control check plus BOM/encoding candidates | decoded Unicode text + byte/line map | PlainText-to-Docling adapter | line + character/byte range |
| DOCX | ZIP plus OOXML content/relationship entries | validated OOXML descriptor | Docling DOCX adapter | structural item/section/table cell; no invented page number |
| DOC | CFB signature | versioned Office PDF or DOCX intermediate | Docling route for intermediate | source DOC + intermediate/page/region provenance |
| PPTX | ZIP plus OOXML presentation/content entries | validated OOXML descriptor | Docling PPTX adapter | slide + structural item/table cell; no invented PDF page locator |
| PPT | CFB signature | versioned LibreOffice PPTX intermediate | Docling PPTX adapter | source PPT + intermediate/slide/item provenance |
| PDF | `%PDF-` plus bounded document/page inspection | PDF page inventory / optional named derived input | per-page Docling/OCR plan | original page + bounding box |
| JPEG | JPEG signature and safe image metadata | orientation/pixel transform | Docling image/OCR adapter | source pixel bounding box |
| PNG | PNG signature and safe image metadata | orientation/pixel transform | Docling image/OCR adapter | source pixel bounding box |

## TXT: Decode Before Semantics

TXT has no trustworthy charset declaration by default. The normalizer follows this
policy:

1. respect a valid BOM/declared encoding;
2. attempt strict UTF-8/UTF-16 and configured allowed fallbacks such as GB18030;
3. use `charset-normalizer` candidates only within that allowed set and record its
   confidence/ambiguity;
4. if candidates are materially ambiguous, show the chosen encoding in preflight and
   permit an explicit selection before enqueue; and
5. preserve original bytes, byte-to-character/line mapping, newline style, control
   character policy, and overflow/maximum-line limits.

Never decode with replacement characters merely to manufacture searchable evidence.
The plain-text adapter then constructs a DoclingDocument using its builder API and
keeps the textual locator in envelope/provenance side data. The exact Docling version
must prove raw-TXT support or the adapter remains Xenix-owned at this seam.

## DOCX: Docling First, Supplements Are Explicit

Use Docling as the primary DOCX-to-DoclingDocument parser. It provides the common IR
and avoids a second private tree. Its loss notes stay visible in the envelope.

Mammoth may be a diagnostic/fallback route when a semantic HTML/text comparison is
valuable, but it intentionally ignores much visual formatting and does not supply
page geometry; its output is not itself canonical. Pandoc is retained only for a
controlled external conversion/fidelity spike until packaging, GPL distribution, and
provenance consequences are accepted. Neither can silently replace the primary
Docling route.

## Legacy DOC: Conversion Is a Named Normalization

Legacy binary DOC is not parsed as DOCX. `FormatNormalizer` emits an
`OfficeConversionCapability` plan. The current candidate is a version-pinned
LibreOffice headless conversion to PDF, then a Docling PDF route; a DOCX control route
is part of the agreed fidelity spike.

The intermediate is attempt-local and checksummed. Its converter/runtime/options and
the original source artifact relation go into the envelope. The converter uses a
unique temporary profile, bounded subprocess, and cancellation policy. It never
rewrites the source snapshot.

## PPTX and Legacy PPT: One Presentation IR Route

PPTX uses Docling's PowerPoint backend after bounded OOXML package validation. Legacy
PPT uses a named, checksummed LibreOffice conversion to PPTX before the same parser
route. Both retain original source format and normalization provenance; neither is
treated as PDF, and embedded picture bytes never become searchable text Units.

## PDF: Route Per Page

PDF routing is described in [pdf-ocr-design.md](pdf-ocr-design.md). In short, an
outer `PdfDocumentProbe` assesses container/encryption/safety; a `PageProbe` produces
features for every page; `ParserRouter` selects native, OCR, hybrid, or complex-layout
routes per page; `ParseExecutor` merges the results into one DoclingDocument with
original page locators.

`pikepdf` is a candidate probe/preprocessor—not a hidden text parser. It can help
inspect encrypted/damaged documents and apply parser limits, but source repair only
creates an explicit derived input with provenance after a package spike.

## JPEG and PNG: Preserve Image, Add OCR Projection

The original image snapshot is the source authority. Normalization validates pixel
and decompression limits and computes orientation/coordinate transforms without
overwriting it. OCR text, polygons, language, confidence, and provider descriptor are
added as a labelled projection through `OcrService`; a missing OCR profile still
allows a canonical image item with `text_projection=unavailable`.

## Routing Requirements for Every New Format

A future format cannot be added just by expanding a file dialog filter. It needs:

1. signature/container probe and resource safety limits;
2. a deterministic normalization descriptor/intermediate rule;
3. a registered route and `ParseResult -> DoclingDocument` adapter;
4. locator/provenance and asset retention policy;
5. cancellation/recovery and error taxonomy; and
6. representative fixtures, package smoke, and user-visible preflight language.
