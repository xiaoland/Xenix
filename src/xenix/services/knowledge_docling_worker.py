from __future__ import annotations

import os
import sys
from pathlib import Path


def main(source_format: str, source_path: str, output_path: str) -> int:
    if source_format not in {"docx", "pdf"}:
        return 2
    try:
        source = Path(source_path).resolve(strict=True)
        output = Path(output_path).resolve()
        if not source.is_file() or output == source or not output.parent.is_dir():
            return 2
        document = _convert(source, source_format=source_format)
        payload = document.model_dump_json().encode("utf-8")
        temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
        temporary.unlink(missing_ok=True)
        try:
            with temporary.open("xb") as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    except Exception:
        return 1
    return 0


def _convert(source_path: Path, *, source_format: str):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = None
    if source_format == "pdf":
        options = {
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=PdfPipelineOptions(do_ocr=False),
            )
        }
    result = DocumentConverter(format_options=options).convert(source_path)
    status = str(getattr(result.status, "value", result.status)).lower()
    if status not in {"success", "partial_success"}:
        raise RuntimeError("Docling conversion failed.")
    return result.document


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
