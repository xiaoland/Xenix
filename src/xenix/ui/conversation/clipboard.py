from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData


MIME_TYPE = "application/vnd.xenix.message+json"


def message_clipboard(text: str, paths: tuple[str, ...]) -> QMimeData:
    mime = QMimeData()
    mime.setText(text)
    mime.setData(MIME_TYPE, QByteArray(json.dumps({
        "version": 1, "text": text, "attachments": [{"path": path} for path in paths],
    }, ensure_ascii=False).encode("utf-8")))
    return mime


def read_message_clipboard(mime: QMimeData) -> tuple[str, list[str]] | None:
    if not mime.hasFormat(MIME_TYPE):
        return None
    try:
        payload = json.loads(bytes(mime.data(MIME_TYPE).data()))
    except (UnicodeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return None
    text = payload.get("text")
    attachments = payload.get("attachments")
    if not isinstance(text, str) or not isinstance(attachments, list):
        return None
    paths = []
    for item in attachments:
        path = item.get("path") if isinstance(item, dict) else None
        if isinstance(path, str) and "\0" not in path and Path(path).is_absolute():
            paths.append(path)
    return text, paths
