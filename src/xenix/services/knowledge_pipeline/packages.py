"""Validate bounded ZIP containers and format-specific package identity."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

from ...exceptions import ValidationError
from .contracts import _format_mismatch


MAX_PACKAGE_ENTRIES = 20_000
MAX_PACKAGE_ENTRY_BYTES = 128 * 1024 * 1024
MAX_PACKAGE_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_PACKAGE_COMPRESSION_RATIO = 200
MAX_PACKAGE_MEMBER_NAME_BYTES = 512
MAX_PACKAGE_MEMBER_DEPTH = 32
_PACKAGE_RATIO_CHECK_MIN_BYTES = 1024 * 1024


@dataclass(frozen=True)
class _ZipPackageProfile:
    source_format: str
    display_name: str
    main_part: str


_DOCX_PACKAGE = _ZipPackageProfile("docx", "DOCX", "word/document.xml")
_PPTX_PACKAGE = _ZipPackageProfile("pptx", "PPTX", "ppt/presentation.xml")
_OOXML_PACKAGE_PROFILES = {
    "docx": _DOCX_PACKAGE,
    "pptx": _PPTX_PACKAGE,
}


def _package_error(
    profile: _ZipPackageProfile,
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


def _verify_mimetype_zip_package(
    path: Path,
    *,
    source_format: str,
    expected_mimetype: str,
) -> dict[str, int]:
    profile = _ZipPackageProfile(
        source_format="package",
        display_name=source_format.upper(),
        main_part="mimetype",
    )
    try:
        with ZipFile(path) as package:
            entries, names, expanded_bytes, maximum_ratio = _verify_zip_package_entries(
                package,
                profile=profile,
            )
            if "mimetype" not in names:
                raise _package_error(profile, "package_invalid", "has no package media type")
            mimetype_entry = package.getinfo("mimetype")
            if mimetype_entry.file_size > 256:
                raise _package_error(profile, "package_invalid", "has an invalid package media type")
            actual_mimetype = package.read(mimetype_entry).decode("ascii", errors="strict")
            if actual_mimetype != expected_mimetype:
                raise _format_mismatch()
    except ValidationError:
        raise
    except (BadZipFile, OSError, UnicodeError, KeyError) as exc:
        raise _package_error(profile, "package_invalid", "is not a valid package") from exc
    return {
        "container_entry_count": len(entries),
        "container_expanded_bytes": expanded_bytes,
        "container_max_compression_ratio": maximum_ratio,
    }


def _verify_ooxml_package(
    path: Path,
    profile: _ZipPackageProfile,
) -> dict[str, int]:
    try:
        with ZipFile(path) as package:
            entries, names, expanded_bytes, maximum_ratio = _verify_zip_package_entries(
                package,
                profile=profile,
            )
            if profile.main_part not in names or "[Content_Types].xml" not in names:
                raise _package_error(
                    profile,
                    "package_invalid",
                    "has the wrong Office package type",
                )
    except (BadZipFile, OSError) as exc:
        raise _package_error(
            profile,
            "package_invalid",
            "is not a valid Office package",
        ) from exc
    return {
        "container_entry_count": len(entries),
        "container_expanded_bytes": expanded_bytes,
        "container_max_compression_ratio": maximum_ratio,
    }


def _verify_zip_package_entries(
    package: ZipFile,
    *,
    profile: _ZipPackageProfile,
) -> tuple[list[Any], set[str], int, int]:
    entries = package.infolist()
    if len(entries) > MAX_PACKAGE_ENTRIES:
        raise _package_error(profile, "entry_limit", "contains too many package entries")
    names: set[str] = set()
    casefold_names: set[str] = set()
    expanded_bytes = 0
    maximum_ratio = 1
    for entry in entries:
        _validate_package_member_path(
            entry.filename,
            profile=profile,
            is_directory=entry.is_dir(),
        )
        folded = entry.filename.casefold()
        if entry.filename in names or folded in casefold_names:
            raise _package_error(profile, "entries_ambiguous", "contains ambiguous package entries")
        names.add(entry.filename)
        casefold_names.add(folded)
        if entry.flag_bits & 0x1:
            raise _package_error(profile, "entry_encrypted", "contains encrypted package entries")
        mode = (entry.external_attr >> 16) & 0xFFFF
        if mode and stat.S_ISLNK(mode):
            raise _package_error(profile, "entry_unsafe", "contains an unsafe package entry")
        if entry.file_size < 0 or entry.compress_size < 0:
            raise _package_error(profile, "size_invalid", "has invalid package sizes")
        if entry.file_size > MAX_PACKAGE_ENTRY_BYTES:
            raise _package_error(profile, "entry_too_large", "package entry is too large")
        expanded_bytes += entry.file_size
        if expanded_bytes > MAX_PACKAGE_EXPANDED_BYTES:
            raise _package_error(profile, "expansion_limit", "expands beyond the supported limit")
        ratio = (
            entry.file_size
            if entry.compress_size == 0
            else (entry.file_size + entry.compress_size - 1) // entry.compress_size
        )
        maximum_ratio = max(maximum_ratio, ratio)
        if entry.file_size >= _PACKAGE_RATIO_CHECK_MIN_BYTES and ratio > MAX_PACKAGE_COMPRESSION_RATIO:
            raise _package_error(profile, "compression_ratio", "compression ratio is unsafe")
    return entries, names, expanded_bytes, maximum_ratio


def _validate_package_member_path(
    name: str,
    *,
    profile: _ZipPackageProfile,
    is_directory: bool,
) -> None:
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or len(name.encode("utf-8")) > MAX_PACKAGE_MEMBER_NAME_BYTES
    ):
        raise _package_error(
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
        raise _package_error(
            profile,
            "path_unsafe",
            "contains an unsafe package path",
        )
