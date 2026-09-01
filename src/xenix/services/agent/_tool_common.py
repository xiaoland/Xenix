from __future__ import annotations

from ...exceptions import ValidationError


def _raise_if_cancelled(ml_service, context, *, ml_task_ids=None) -> None:
    if not context.cancel_requested():
        return
    if ml_task_ids:
        for task_id in ml_task_ids:
            try:
                ml_service.cancel_task(task_id)
            except Exception:
                continue
    raise ValidationError("Agent run was cancelled.")


__all__ = ["_raise_if_cancelled"]
