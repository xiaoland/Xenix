from __future__ import annotations

import pytest

from xenix.exceptions import ValidationError
from xenix.services.embedding_service import OpenAICompatibleEmbeddingService
from xenix.services.llm import LLMService
from xenix.services.ml.worker_pool import MLWorkerPool
from xenix.services.ml.worker_settings import (
    MLWorkerConfig,
    MLWorkerKind,
    MLWorkerPoolConfig,
    MLWorkerSettings,
    MLWorkerSetupState,
    validation_record,
    MLWorkerValidationStatus,
)


class _FakeWorkerSettingsService:
    def __init__(self, settings: MLWorkerSettings) -> None:
        self._settings = settings

    def load(self) -> MLWorkerSettings:
        return self._settings


class _FakeLLMSettingsSource:
    def __init__(self) -> None:
        self.loaded = False

    def load(self):
        self.loaded = True
        raise AssertionError("A denied live call must not read settings.")


def _remote_capable_settings() -> MLWorkerSettings:
    local = MLWorkerConfig(
        id="local",
        display_name="This computer",
        kind=MLWorkerKind.LOCAL,
        max_concurrent_tasks=1,
        setup_state=MLWorkerSetupState.READY,
    )
    ssh = MLWorkerConfig(
        id="xenix.ssh",
        display_name="Remote box",
        kind=MLWorkerKind.SSH,
        host="example.invalid",
        ssh_alias="xenix.ssh",
        max_concurrent_tasks=8,
        setup_state=MLWorkerSetupState.READY,
        last_validation=validation_record(MLWorkerValidationStatus.SUCCEEDED, "ready"),
    )
    return MLWorkerSettings(
        pool=MLWorkerPoolConfig(enabled=True, max_concurrent_tasks=32),
        workers=[local, ssh],
    )


def test_remote_worker_admission_is_denied_by_capability() -> None:
    settings = _remote_capable_settings()
    allowed = MLWorkerPool(_FakeWorkerSettingsService(settings))
    denied = MLWorkerPool(_FakeWorkerSettingsService(settings), allow_remote_workers=False)

    assert allowed.max_concurrent_tasks == 9
    assert denied.max_concurrent_tasks == 1


def test_live_llm_complete_is_denied() -> None:
    service = LLMService(_FakeLLMSettingsSource(), allow_live=False)

    with pytest.raises(ValidationError) as exc_info:
        service.complete(messages=[], tools=[])
    assert exc_info.value.error_code == "live_llm_denied"


def test_live_llm_stream_is_denied() -> None:
    service = LLMService(_FakeLLMSettingsSource(), allow_live=False)

    with pytest.raises(ValidationError) as exc_info:
        next(service.stream(messages=[], tools=[]))
    assert exc_info.value.error_code == "live_llm_denied"


def test_live_llm_title_and_guard_models_are_unavailable_when_denied() -> None:
    service = LLMService(_FakeLLMSettingsSource(), allow_live=False)

    assert service.thread_title_fq_model_key() is None
    assert service.turn_completion_guard_fq_model_key() is None
    assert service.build_thread_title_provider() is None
    assert service.build_turn_completion_guard_provider() is None


def test_live_embedding_is_unavailable_when_denied() -> None:
    class DeniedEmbeddingSource:
        def load(self):
            raise AssertionError("A denied live edge must not read settings.")

    service = OpenAICompatibleEmbeddingService(DeniedEmbeddingSource(), allow_live=False)

    assert service.freeze() is None
