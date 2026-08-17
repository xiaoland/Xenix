from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.agent_harness._infra.dispatch import (
    benchmark_pytest_arguments,
    safe_check_pytest_options,
)
from tests.e2e.agent_harness._infra.pytest_plugin import _single_model_option
from tests.e2e.agent_harness._infra.runner import dry_run_model, selected_model_key
from xenix.services.llm import LLMProviderConfig, LLMSettings


DEFAULT_MODEL = "offline/default-model"
OVERRIDE_MODEL = "offline/override-model"


def _settings() -> LLMSettings:
    return LLMSettings(
        providers=[
            LLMProviderConfig(
                key="offline",
                api_key="not-a-real-secret",
                models=["default-model", "override-model"],
            )
        ],
        default_fq_model_key=DEFAULT_MODEL,
    )


def _write_settings(path: Path) -> None:
    path.write_text(_settings().model_dump_json(), encoding="utf-8")


class _ModelOptionConfig:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    def getoption(self, name: str) -> list[str]:
        assert name == "agent_harness_models"
        return self._values


def test_default_settings_model_is_selected_without_override(tmp_path: Path) -> None:
    settings_path = tmp_path / "agent-settings.json"
    _write_settings(settings_path)

    assert selected_model_key(_settings()) == DEFAULT_MODEL
    assert dry_run_model(settings_path=settings_path) == DEFAULT_MODEL


def test_one_model_override_replaces_the_default(tmp_path: Path) -> None:
    settings_path = tmp_path / "agent-settings.json"
    _write_settings(settings_path)

    assert selected_model_key(_settings(), OVERRIDE_MODEL) == OVERRIDE_MODEL
    assert (
        dry_run_model(
            settings_path=settings_path,
            requested_model=OVERRIDE_MODEL,
        )
        == OVERRIDE_MODEL
    )
    assert _single_model_option(_ModelOptionConfig([OVERRIDE_MODEL])) == OVERRIDE_MODEL  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "values",
    [
        [DEFAULT_MODEL, OVERRIDE_MODEL],
        [f"{DEFAULT_MODEL},{OVERRIDE_MODEL}"],
    ],
)
def test_model_option_rejects_multiple_models(values: list[str]) -> None:
    with pytest.raises(pytest.UsageError):
        _single_model_option(_ModelOptionConfig(values))  # type: ignore[arg-type]


def test_explicit_case_selector_replaces_the_default_live_root() -> None:
    selector = "tests/e2e/agent_harness/test_ml_cleaning.py::test_ml_cleaning"

    arguments = benchmark_pytest_arguments(["--collect-only", "-q", selector])

    assert selector in arguments
    assert "tests/e2e/agent_harness" not in arguments


def test_offline_check_rejects_selection_or_live_options() -> None:
    assert safe_check_pytest_options(["-q", "--collect-only"]) == ["-q", "--collect-only"]
    with pytest.raises(SystemExit, match="selection is fixed"):
        safe_check_pytest_options(["tests/e2e/agent_harness/test_ml_cleaning.py"])
    with pytest.raises(SystemExit, match="selection is fixed"):
        safe_check_pytest_options(["--run-agent-harness"])
