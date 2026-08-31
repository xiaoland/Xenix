from __future__ import annotations

from collections.abc import MutableMapping
import os


def configure_windows_frozen_process_environment(
    *,
    environment: MutableMapping[str, str] | None = None,
    logical_cpu_count: int | None = None,
) -> None:
    """Pin the process-wide joblib/loky worker cap before any worker-heavy import.

    loky reads LOKY_MAX_CPU_COUNT when its backend is imported, so this must run
    before loky/joblib is imported by ML/text modules or the setting is ignored.
    An already-set value (a caller override) wins, and the detected CPU count is
    clamped to at least 1.
    """

    target = os.environ if environment is None else environment
    if "LOKY_MAX_CPU_COUNT" in target:
        return
    detected = os.cpu_count() if logical_cpu_count is None else logical_cpu_count
    target["LOKY_MAX_CPU_COUNT"] = str(max(detected or 1, 1))
