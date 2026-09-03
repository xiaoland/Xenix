from __future__ import annotations

import logging
import os
import json
import weakref

from PySide6.QtCore import QObject, QTimer
from shiboken6 import isValid

from .diagnostics.snapshot import capture_ui_snapshot

LOGGER = logging.getLogger("xenix.ui.layout_debug")


def dump_layout_if_enabled(root: QObject, *, reason: str, settle_ticks: int = 3) -> None:
    if os.environ.get("XENIX_LAYOUT_DEBUG", "").lower() not in {"1", "true", "yes"}:
        return

    _schedule_dump(root, reason=reason, remaining_ticks=max(0, settle_ticks))


def _schedule_dump(root: QObject, *, reason: str, remaining_ticks: int) -> None:
    root_reference = weakref.ref(root)
    _schedule_dump_reference(root_reference, reason=reason, remaining_ticks=remaining_ticks)


def _schedule_dump_reference(
    root_reference: weakref.ReferenceType[QObject],
    *,
    reason: str,
    remaining_ticks: int,
) -> None:
    root = root_reference()
    if root is None or not isValid(root):
        return
    if remaining_ticks == 0:
        dump_layout_tree(root, reason=reason)
        return
    QTimer.singleShot(
        0,
        lambda: _schedule_dump_reference(
            root_reference,
            reason=reason,
            remaining_ticks=remaining_ticks - 1,
        ),
    )


def dump_layout_tree(root: QObject, *, reason: str) -> None:
    snapshot = capture_ui_snapshot(root)
    LOGGER.info(
        "Qt layout dump: %s\n%s",
        reason,
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
    )
