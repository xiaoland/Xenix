from __future__ import annotations

from collections.abc import MutableMapping
import os


def configure_windows_frozen_process_environment(
    *,
    environment: MutableMapping[str, str] | None = None,
    logical_cpu_count: int | None = None,
) -> None:
    """Install packaged-process defaults before importing worker-heavy modules."""

    target = os.environ if environment is None else environment
    if "LOKY_MAX_CPU_COUNT" in target:
        return
    detected = os.cpu_count() if logical_cpu_count is None else logical_cpu_count
    target["LOKY_MAX_CPU_COUNT"] = str(max(detected or 1, 1))
