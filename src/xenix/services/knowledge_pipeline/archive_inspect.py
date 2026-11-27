from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

import msoffcrypto
import pikepdf

from ...exceptions import ValidationError
from .contracts import (
    MAX_PACKAGE_COMPRESSION_RATIO,
    MAX_PACKAGE_ENTRIES,
    MAX_PACKAGE_ENTRY_BYTES,
    MAX_PACKAGE_EXPANDED_BYTES,
    MAX_PACKAGE_MEMBER_DEPTH,
    MAX_PACKAGE_MEMBER_NAME_BYTES,
    PACKAGE_RATIO_CHECK_MIN_BYTES,
    NormalizationRequest,
    ZipPackageProfile,
    format_mismatch,
)

DOCX_PACKAGE = ZipPackageProfile("docx", "DOCX", "word/document.xml")
PPTX_PACKAGE = ZipPackageProfile("pptx", "PPTX", "ppt/presentation.xml")
OOXML_PACKAGE_PROFILES = {
    "docx": DOCX_PACKAGE,
    "pptx": PPTX_PACKAGE,
}


def inspect_office_file(path: Path) -> tuple[str | None, bool]:
    try:
        with path.open("rb") as stream:
            office = msoffcrypto.OfficeFile(stream)
            office_kind = {
                "Doc97File": "doc",
                "Ppt97File": "ppt",
                "OOXMLFile": "ooxml",
            }.get(type(office).__name__)
            return office_kind, bool(office.is_encrypted())
    except msoffcrypto.exceptions.FileFormatError:
        return None, False


def office_source(request: NormalizationRequest) -> Path:
    if not request.probe.encrypted:
        return request.probe.source_path
    assert request.password is not None
    target = request.work_dir / f"decrypted.{request.probe.source_format}"
    try:
        with request.probe.source_path.open("rb") as stream:
            office = msoffcrypto.OfficeFile(stream)
            office.load_key(password=request.password)
            with target.open("wb") as output:
                office.decrypt(output)
    except Exception as exc:
        raise ValidationError(
            "The document password was not accepted.",
            error_code="knowledge_password_invalid",
            retryable=True,
        ) from exc
    return target


def decrypt_pdf(
    source: Path,
    *,
    password: str,
    work_dir: Path,
) -> Path:
    target = work_dir / "decrypted.pdf"
    try:
        with pikepdf.Pdf.open(source, password=password) as document:
            document.save(target)
    except (pikepdf.PasswordError, pikepdf.PdfError) as exc:
        raise ValidationError(
            "The document password was not accepted.",
            error_code="knowledge_password_invalid",
            retryable=True,
        ) from exc
    return target


def package_error(
    profile: ZipPackageProfile,
    category: str,
    detail: str,
) -> ValidationError:
    error_code = (
        "knowledge_package_invalid"
        if profile.source_format == "package" and category == "package_invalid"
        else f"knowledge_{profile.source_format}_{category}"
    )
    return ValidationError(
        f"The selected {profile.display_name} {detail}.",
        error_code=error_code,
    )


def verify_mimetype_zip_package(
    path: Path,
    *,
    source_format: str,
    expected_mimetype: str,
) -> dict[str, int]:
    profile = ZipPackageProfile(
        source_format="package",
        display_name=source_format.upper(),
        main_part="mimetype",
    )
    try:
        with ZipFile(path) as package:
            entries, names, expanded_bytes, maximum_ratio = verify_zip_package_entries(
                package,
                profile=profile,
            )
            if "mimetype" not in names:
                raise package_error(profile, "package_invalid", "has no package media type")
            mimetype_entry = package.getinfo("mimetype")
            if mimetype_entry.file_size > 256:
                raise package_error(profile, "package_invalid", "has an invalid package media type")
            actual_mimetype = package.read(mimetype_entry).decode("ascii", errors="strict")
            if actual_mimetype != expected_mimetype:
                raise format_mismatch()
    except ValidationError:
        raise
    except (BadZipFile, OSError, UnicodeError, KeyError) as exc:
        raise package_error(profile, "package_invalid", "is not a valid package") from exc
    return {
        "container_entry_count": len(entries),
        "container_expanded_bytes": expanded_bytes,
        "container_max_compression_ratio": maximum_ratio,
    }


def verify_ooxml_package(
    path: Path,
    profile: ZipPackageProfile,
) -> dict[str, int]:
    try:
        with ZipFile(path) as package:
            entries, names, expanded_bytes, maximum_ratio = verify_zip_package_entries(
                package,
                profile=profile,
            )
            if profile.main_part not in names or "[Content_Types].xml" not in names:
                raise package_error(
                    profile,
                    "package_invalid",
                    "has the wrong Office package type",
                )
    except (BadZipFile, OSError) as exc:
        raise package_error(
            profile,
            "package_invalid",
            "is not a valid Office package",
        ) from exc
    return {
        "container_entry_count": len(entries),
        "container_expanded_bytes": expanded_bytes,
        "container_max_compression_ratio": maximum_ratio,
    }


def verify_zip_package_entries(
    package: ZipFile,
    *,
    profile: ZipPackageProfile,
) -> tuple[list[Any], set[str], int, int]:
    entries = package.infolist()
    if len(entries) > MAX_PACKAGE_ENTRIES:
        raise package_error(profile, "entry_limit", "contains too many package entries")
    names: set[str] = set()
    casefold_names: set[str] = set()
    expanded_bytes = 0
    maximum_ratio = 1
    for entry in entries:
        validate_package_member_path(
            entry.filename,
            profile=profile,
            is_directory=entry.is_dir(),
        )
        folded = entry.filename.casefold()
        if entry.filename in names or folded in casefold_names:
            raise package_error(profile, "entries_ambiguous", "contains ambiguous package entries")
        names.add(entry.filename)
        casefold_names.add(folded)
        if entry.flag_bits & 0x1:
            raise package_error(profile, "entry_encrypted", "contains encrypted package entries")
        mode = (entry.external_attr >> 16) & 0xFFFF
        if mode and stat.S_ISLNK(mode):
            raise package_error(profile, "entry_unsafe", "contains an unsafe package entry")
        if entry.file_size < 0 or entry.compress_size < 0:
            raise package_error(profile, "size_invalid", "has invalid package sizes")
        if entry.file_size > MAX_PACKAGE_ENTRY_BYTES:
            raise package_error(profile, "entry_too_large", "package entry is too large")
        expanded_bytes += entry.file_size
        if expanded_bytes > MAX_PACKAGE_EXPANDED_BYTES:
            raise package_error(profile, "expansion_limit", "expands beyond the supported limit")
        ratio = (
            entry.file_size
            if entry.compress_size == 0
            else (entry.file_size + entry.compress_size - 1) // entry.compress_size
        )
        maximum_ratio = max(maximum_ratio, ratio)
        if entry.file_size >= PACKAGE_RATIO_CHECK_MIN_BYTES and ratio > MAX_PACKAGE_COMPRESSION_RATIO:
            raise package_error(profile, "compression_ratio", "compression ratio is unsafe")
    return entries, names, expanded_bytes, maximum_ratio


def validate_package_member_path(
    name: str,
    *,
    profile: ZipPackageProfile,
    is_directory: bool,
) -> None:
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or len(name.encode("utf-8")) > MAX_PACKAGE_MEMBER_NAME_BYTES
    ):
        raise package_error(
            profile,
            "path_unsafe",
            "contains an unsafe package path",
        )
    normalized = name[:-1] if is_directory and name.endswith("/") else name
    raw_parts = normalized.split("/")
    relative = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or relative.is_absolute()
        or len(raw_parts) > MAX_PACKAGE_MEMBER_DEPTH
        or any(part in {"", ".", ".."} or ":" in part for part in raw_parts)
    ):
        raise package_error(
            profile,
            "path_unsafe",
            "contains an unsafe package path",
        )
