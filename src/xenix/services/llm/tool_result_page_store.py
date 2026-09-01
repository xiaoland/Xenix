"""Filesystem-backed store for large (paged) Tool results.

This module is deliberately self-contained: it only touches the runtime state
directory, has no domain imports, and exposes one primitive — persist a long
string once, then read it back by character range. Pagination is character
(Unicode code point) based, never byte based, so multi-byte CJK output is never
split mid-codepoint.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from ...exceptions import ValidationError


_RESULT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class ToolResultPage:
    text: str
    total_chars: int
    has_more: bool


class ToolResultPageStore:
    """Store one ToolResult string as a UTF-8 text file plus a small metadata sidecar."""

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        *,
        thread_id: str,
        tool_call_message_id: str | None,
        text: str,
    ) -> str:
        result_id = uuid.uuid4().hex
        (self._root_dir / f"{result_id}.txt").write_text(text, encoding="utf-8")
        (self._root_dir / f"{result_id}.meta.json").write_text(
            json.dumps(
                {
                    "thread_id": thread_id,
                    "tool_call_message_id": tool_call_message_id,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return result_id

    def read_page(
        self,
        result_id: str,
        *,
        offset: int,
        limit: int,
    ) -> ToolResultPage:
        self._validate_result_id(result_id)
        text_path = self._root_dir / f"{result_id}.txt"
        if not text_path.is_file():
            raise ValidationError("Unknown paged result id.")
        text = text_path.read_text(encoding="utf-8")
        total_chars = len(text)
        start = max(0, offset)
        end = min(total_chars, start + limit)
        return ToolResultPage(
            text=text[start:end],
            total_chars=total_chars,
            has_more=end < total_chars,
        )

    def delete_for_thread(self, thread_id: str) -> int:
        removed = 0
        for meta_path in self._root_dir.glob("*.meta.json"):
            result_id = meta_path.name.removesuffix(".meta.json")
            if not _RESULT_ID_PATTERN.fullmatch(result_id):
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if meta.get("thread_id") == thread_id:
                self._delete_pair(result_id)
                removed += 1
        return removed

    def collect_garbage(self, *, max_age_seconds: int) -> int:
        deadline = time.time() - max_age_seconds
        removed = 0
        for text_path in self._root_dir.glob("*.txt"):
            result_id = text_path.name.removesuffix(".txt")
            if not _RESULT_ID_PATTERN.fullmatch(result_id):
                continue
            try:
                if text_path.stat().st_mtime >= deadline:
                    continue
            except OSError:
                continue
            self._delete_pair(result_id)
            removed += 1
        return removed

    def _delete_pair(self, result_id: str) -> None:
        (self._root_dir / f"{result_id}.txt").unlink(missing_ok=True)
        (self._root_dir / f"{result_id}.meta.json").unlink(missing_ok=True)

    @staticmethod
    def _validate_result_id(result_id: str) -> None:
        if not isinstance(result_id, str) or not _RESULT_ID_PATTERN.fullmatch(result_id):
            raise ValidationError("Invalid paged result id.")


__all__ = ["ToolResultPage", "ToolResultPageStore"]
