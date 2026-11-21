"""Knowledge import pipeline and compatibility exports for its original module path."""

from .contracts import (
    MAX_SOURCE_BYTES as MAX_SOURCE_BYTES,
    _ProviderT as _ProviderT,
    _ANYDOC_PROVIDER_ID as _ANYDOC_PROVIDER_ID,
    FileProbeResult as FileProbeResult,
    NormalizedSource as NormalizedSource,
    ParsePlanUnit as ParsePlanUnit,
    ParsePlan as ParsePlan,
    ParseResult as ParseResult,
    FormatProbeFacts as FormatProbeFacts,
    FormatProbeProvider as FormatProbeProvider,
    NormalizationRequest as NormalizationRequest,
    FormatNormalizerProvider as FormatNormalizerProvider,
    ParserRouteProvider as ParserRouteProvider,
    ParserExecutionContext as ParserExecutionContext,
    ParsedContent as ParsedContent,
    DocumentParserProvider as DocumentParserProvider,
    _provider_map as _provider_map,
    _format_mismatch as _format_mismatch,
)

from .probe import (
    MAX_IMAGE_PIXELS as MAX_IMAGE_PIXELS,
    _CFB_SIGNATURE as _CFB_SIGNATURE,
    _TextProbeProvider as _TextProbeProvider,
    _CfbOfficeProbeProvider as _CfbOfficeProbeProvider,
    _OoxmlOfficeProbeProvider as _OoxmlOfficeProbeProvider,
    _PdfProbeProvider as _PdfProbeProvider,
    _ImageProbeProvider as _ImageProbeProvider,
    _RtfProbeProvider as _RtfProbeProvider,
    _ZipMimetypeProbeProvider as _ZipMimetypeProbeProvider,
    FileProbe as FileProbe,
    _probe_text as _probe_text,
    _probe_pdf as _probe_pdf,
    _probe_image as _probe_image,
    _inspect_office_file as _inspect_office_file,
    _read_prefix as _read_prefix,
)

from .packages import (
    MAX_PACKAGE_ENTRIES as MAX_PACKAGE_ENTRIES,
    MAX_PACKAGE_ENTRY_BYTES as MAX_PACKAGE_ENTRY_BYTES,
    MAX_PACKAGE_EXPANDED_BYTES as MAX_PACKAGE_EXPANDED_BYTES,
    MAX_PACKAGE_COMPRESSION_RATIO as MAX_PACKAGE_COMPRESSION_RATIO,
    MAX_PACKAGE_MEMBER_NAME_BYTES as MAX_PACKAGE_MEMBER_NAME_BYTES,
    MAX_PACKAGE_MEMBER_DEPTH as MAX_PACKAGE_MEMBER_DEPTH,
    _PACKAGE_RATIO_CHECK_MIN_BYTES as _PACKAGE_RATIO_CHECK_MIN_BYTES,
    _ZipPackageProfile as _ZipPackageProfile,
    _DOCX_PACKAGE as _DOCX_PACKAGE,
    _PPTX_PACKAGE as _PPTX_PACKAGE,
    _OOXML_PACKAGE_PROFILES as _OOXML_PACKAGE_PROFILES,
    _package_error as _package_error,
    _verify_mimetype_zip_package as _verify_mimetype_zip_package,
    _verify_ooxml_package as _verify_ooxml_package,
    _verify_zip_package_entries as _verify_zip_package_entries,
    _validate_package_member_path as _validate_package_member_path,
)

from .text_decoding import (
    MAX_TEXT_LINE_CHARS as MAX_TEXT_LINE_CHARS,
    _IO_CHUNK_BYTES as _IO_CHUNK_BYTES,
    _TEXT_ENCODING_ALLOWLIST as _TEXT_ENCODING_ALLOWLIST,
    _TEXT_FALLBACK_ENCODINGS as _TEXT_FALLBACK_ENCODINGS,
    _TEXT_MAX_CANDIDATE_CHAOS as _TEXT_MAX_CANDIDATE_CHAOS,
    _TEXT_MIN_CANDIDATE_SEPARATION as _TEXT_MIN_CANDIDATE_SEPARATION,
    _DecodedText as _DecodedText,
    _read_bytes as _read_bytes,
    _read_text as _read_text,
    _write_text as _write_text,
    _normalize_text as _normalize_text,
    _decode_text_payload as _decode_text_payload,
    _text_bom as _text_bom,
    _strict_decode_text as _strict_decode_text,
    _canonical_encoding_name as _canonical_encoding_name,
    _reject_unsafe_text_controls as _reject_unsafe_text_controls,
    _newline_style as _newline_style,
)

from .normalize import (
    _TextNormalizerProvider as _TextNormalizerProvider,
    _DocumentNormalizerProvider as _DocumentNormalizerProvider,
    _PdfNormalizerProvider as _PdfNormalizerProvider,
    _ImageNormalizerProvider as _ImageNormalizerProvider,
    FormatNormalizer as FormatNormalizer,
    _office_source as _office_source,
    _decrypt_pdf as _decrypt_pdf,
    _normalization_descriptor as _normalization_descriptor,
)

from .routing import (
    ParserRouter as ParserRouter,
    _TextRouteProvider as _TextRouteProvider,
    _AnyDocRouteProvider as _AnyDocRouteProvider,
    _PdfRouteProvider as _PdfRouteProvider,
    _ImageRouteProvider as _ImageRouteProvider,
)

from .parse import (
    _ANYDOC_DISTRIBUTION as _ANYDOC_DISTRIBUTION,
    ParseExecutor as ParseExecutor,
    _TextParserProvider as _TextParserProvider,
    _AnyDocParserProvider as _AnyDocParserProvider,
    _PdfParserProvider as _PdfParserProvider,
    _ImageParserProvider as _ImageParserProvider,
)

from .docling_adapters import (
    MAX_ANYDOC_MARKDOWN_BYTES as MAX_ANYDOC_MARKDOWN_BYTES,
    MAX_ANYDOC_BLOCKS as MAX_ANYDOC_BLOCKS,
    _ANYDOC_ERROR_CODES as _ANYDOC_ERROR_CODES,
    _MARKDOWN_HEADING as _MARKDOWN_HEADING,
    _MARKDOWN_LIST_ITEM as _MARKDOWN_LIST_ITEM,
    _MARKDOWN_FENCE as _MARKDOWN_FENCE,
    _plain_text_docling_document as _plain_text_docling_document,
    _anydoc_convert as _anydoc_convert,
    _anydoc_diagnostic_code as _anydoc_diagnostic_code,
    _markdown_to_docling_document as _markdown_to_docling_document,
    _bounded_markdown_lines as _bounded_markdown_lines,
    _image_docling_document as _image_docling_document,
    _docling_convert as _docling_convert,
    _docling_diagnostic_code as _docling_diagnostic_code,
)

from .ocr import (
    MAX_OCR_RESULT_BYTES as MAX_OCR_RESULT_BYTES,
    _OCR_PROJECTION_FAILURES as _OCR_PROJECTION_FAILURES,
    _OcrBatchResult as _OcrBatchResult,
    _ocr_status as _ocr_status,
    _recognize_projection as _recognize_projection,
    _ocr_runtime_payload as _ocr_runtime_payload,
    _append_paddle_ocr_pages as _append_paddle_ocr_pages,
    _append_ocr_text as _append_ocr_text,
    _paddle_text_boxes as _paddle_text_boxes,
    _polygon_bbox as _polygon_bbox,
)

from .provenance import (
    MAX_HASHABLE_IR_BYTES as MAX_HASHABLE_IR_BYTES,
    _sha256_file_bounded as _sha256_file_bounded,
    _runtime_package as _runtime_package,
    _installed_package as _installed_package,
    _bounded_json_sha256 as _bounded_json_sha256,
    _docling_document_sha256 as _docling_document_sha256,
    _redact_path_values_for_hash as _redact_path_values_for_hash,
    _combined_projection_sha256 as _combined_projection_sha256,
)
