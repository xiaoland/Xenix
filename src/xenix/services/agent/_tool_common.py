from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ...exceptions import ValidationError, report_exception


def _raise_if_cancelled(
    ml_service: Any,
    context: Any,
    *,
    ml_task_ids: Iterable[int] | None = None,
) -> None:
    if not context.cancel_requested():
        return
    if ml_task_ids:
        for task_id in ml_task_ids:
            try:
                ml_service.cancel_task(task_id)
            except Exception as exc:
                report_exception(exc)
                continue
    raise ValidationError("Agent run was cancelled.")


__all__ = ["_raise_if_cancelled"]
