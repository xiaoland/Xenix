from __future__ import annotations

import codecs
import unicodedata
from dataclasses import dataclass
from typing import Any

from charset_normalizer import from_bytes

from ...exceptions import ValidationError
from .contracts import IO_CHUNK_BYTES, MAX_TEXT_LINE_CHARS, TEXT_ENCODING_ALLOWLIST

_TEXT_FALLBACK_ENCODINGS = TEXT_ENCODING_ALLOWLIST - {
    "utf-8",
    "utf-16-le",
    "utf-16-be",
}
_TEXT_MAX_CANDIDATE_CHAOS = 0.1
_TEXT_MIN_CANDIDATE_SEPARATION = 0.05


@dataclass(frozen=True)
class DecodedText:
    text: str
    encoding: str
    bom: str
    newline: str
    selection: str


def probe_text(
    payload: bytes,
    facts: dict[str, Any],
    *,
    sample_is_complete: bool,
) -> None:
    decoded = decode_text_payload(
        payload,
        allow_truncated_tail=not sample_is_complete,
    )
    facts["encoding_candidate"] = decoded.encoding
    facts["encoding_selection"] = decoded.selection
    facts["bom"] = decoded.bom != "none"
    facts["bom_kind"] = decoded.bom
    facts["newline"] = decoded.newline
    facts["control_character_count"] = 0


def decode_text_payload(
    payload: bytes,
    *,
    allow_truncated_tail: bool = False,
) -> DecodedText:
    if not payload:
        raise ValidationError(
            "TXT contains no decodable text.",
            error_code="knowledge_text_encoding_unknown",
        )
    bom_encoding, bom_size = _text_bom(payload)
    if bom_encoding in {"utf-32-le", "utf-32-be"}:
        raise ValidationError(
            "TXT encoding is outside the supported allowlist.",
            error_code="knowledge_text_encoding_unknown",
        )
    if bom_encoding is not None:
        text = _strict_decode_text(
            payload[bom_size:],
            encoding=bom_encoding,
            allow_truncated_tail=allow_truncated_tail,
        )
        selection = "bom"
        encoding = bom_encoding
    else:
        try:
            text = _strict_decode_text(
                payload,
                encoding="utf-8",
                allow_truncated_tail=allow_truncated_tail,
            )
            encoding = "utf-8"
            selection = "strict_utf8"
        except ValidationError:
            matches = tuple(from_bytes(payload))
            best = matches[0] if matches else None
            candidate = _canonical_encoding_name(
                str(best.encoding) if best is not None and best.encoding else ""
            )
            best_chaos = float(best.chaos) if best is not None else 1.0
            ambiguous = any(
                _canonical_encoding_name(str(other.encoding or "")) != candidate
                and float(other.chaos) - best_chaos < _TEXT_MIN_CANDIDATE_SEPARATION
                for other in matches[1:]
            )
            if (
                candidate not in _TEXT_FALLBACK_ENCODINGS
                or best_chaos > _TEXT_MAX_CANDIDATE_CHAOS
                or ambiguous
            ):
                raise ValidationError(
                    "TXT encoding could not be determined with sufficient confidence.",
                    error_code="knowledge_text_encoding_unknown",
                ) from None
            encoding = candidate
            selection = "bounded_charset_candidate"
            text = _strict_decode_text(
                payload,
                encoding=encoding,
                allow_truncated_tail=allow_truncated_tail,
            )
    reject_unsafe_text_controls(text)
    if not text and not allow_truncated_tail:
        raise ValidationError(
            "TXT contains no decodable text.",
            error_code="knowledge_text_encoding_unknown",
        )
    return DecodedText(
        text=text,
        encoding=encoding,
        bom=encoding if bom_encoding is not None else "none",
        newline=_newline_style(text),
        selection=selection,
    )


def normalize_text(raw_text: str) -> str:
    reject_unsafe_text_controls(raw_text)
    pieces: list[str] = []
    pending_cr = ""
    current_line_chars = 0
    for start in range(0, len(raw_text), IO_CHUNK_BYTES):
        chunk = pending_cr + raw_text[start : start + IO_CHUNK_BYTES]
        if chunk.endswith("\r"):
            chunk, pending_cr = chunk[:-1], "\r"
        else:
            pending_cr = ""
        chunk = chunk.replace("\r\n", "\n").replace("\r", "\n")
        lines = chunk.split("\n")
        if len(lines) == 1:
            current_line_chars += len(lines[0])
        else:
            if current_line_chars + len(lines[0]) > MAX_TEXT_LINE_CHARS:
                raise ValidationError(
                    "TXT contains a line longer than the supported limit.",
                    error_code="knowledge_text_line_too_long",
                )
            if any(len(line) > MAX_TEXT_LINE_CHARS for line in lines[1:-1]):
                raise ValidationError(
                    "TXT contains a line longer than the supported limit.",
                    error_code="knowledge_text_line_too_long",
                )
            current_line_chars = len(lines[-1])
        if current_line_chars > MAX_TEXT_LINE_CHARS:
            raise ValidationError(
                "TXT contains a line longer than the supported limit.",
                error_code="knowledge_text_line_too_long",
            )
        pieces.append(chunk)
    if pending_cr:
        pieces.append("\n")
    return "".join(pieces)


def reject_unsafe_text_controls(text: str) -> None:
    if "\ufffd" in text or any(
        unicodedata.category(character) in {"Cc", "Cs"}
        and character not in {"\t", "\n", "\r"}
        for character in text
    ):
        raise ValidationError(
            "TXT contains unsupported control or binary characters.",
            error_code="knowledge_text_controls_invalid",
        )


def _text_bom(payload: bytes) -> tuple[str | None, int]:
    markers = (
        (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xff\xfe\x00\x00", "utf-32-le"),
        (b"\xef\xbb\xbf", "utf-8"),
        (b"\xfe\xff", "utf-16-be"),
        (b"\xff\xfe", "utf-16-le"),
    )
    for marker, encoding in markers:
        if payload.startswith(marker):
            return encoding, len(marker)
    return None, 0


def _strict_decode_text(
    payload: bytes,
    *,
    encoding: str,
    allow_truncated_tail: bool,
) -> str:
    try:
        return payload.decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        truncated_tail = (
            allow_truncated_tail
            and exc.end == len(payload)
            and ("unexpected end" in exc.reason or "truncated" in exc.reason)
        )
        if truncated_tail:
            return payload[: exc.start].decode(encoding, errors="strict")
        raise ValidationError(
            "TXT bytes are invalid for the selected encoding.",
            error_code="knowledge_text_encoding_invalid",
        ) from None


def _canonical_encoding_name(raw: str) -> str:
    if not raw:
        return ""
    try:
        return codecs.lookup(raw).name.replace("_", "-")
    except LookupError:
        return ""


def _newline_style(text: str) -> str:
    crlf_count = text.count("\r\n")
    without_crlf = text.replace("\r\n", "")
    styles = [
        name
        for name, count in (
            ("crlf", crlf_count),
            ("cr", without_crlf.count("\r")),
            ("lf", without_crlf.count("\n")),
        )
        if count
    ]
    if not styles:
        return "none"
    return styles[0] if len(styles) == 1 else "mixed"
