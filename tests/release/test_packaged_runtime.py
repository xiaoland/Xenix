from __future__ import annotations

from xenix.packaged_runtime import configure_windows_frozen_process_environment


def test_packaged_runtime_supplies_joblib_cpu_bound() -> None:
    environment: dict[str, str] = {}

    configure_windows_frozen_process_environment(
        environment=environment,
        logical_cpu_count=12,
    )

    assert environment == {"LOKY_MAX_CPU_COUNT": "12"}


def test_packaged_runtime_preserves_operator_cpu_bound() -> None:
    environment = {"LOKY_MAX_CPU_COUNT": "3"}

    configure_windows_frozen_process_environment(
        environment=environment,
        logical_cpu_count=12,
    )

    assert environment == {"LOKY_MAX_CPU_COUNT": "3"}


def test_packaged_runtime_falls_back_to_one_cpu() -> None:
    environment: dict[str, str] = {}

    configure_windows_frozen_process_environment(
        environment=environment,
        logical_cpu_count=0,
    )

    assert environment == {"LOKY_MAX_CPU_COUNT": "1"}
