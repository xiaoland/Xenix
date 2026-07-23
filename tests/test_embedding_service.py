from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.embedding_service import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
    MAX_EMBEDDING_DIMENSIONS,
    MAX_EMBEDDING_TEXT_CHARS,
    EmbeddingSettings,
    EmbeddingSettingsService,
    EmbeddingValidationError,
    OpenAICompatibleEmbeddingService,
)


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]


def _settings_service(monkeypatch, tmp_path: Path) -> EmbeddingSettingsService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    return EmbeddingSettingsService(ensure_app_dirs(get_app_paths()))


def _enabled_settings(**updates: object) -> EmbeddingSettings:
    values = {
        "enabled": True,
        "provider_key": "test-provider",
        "base_url": "https://embedding.example.test",
        "api_key": "top-secret-key",
        "model": "embed-test",
        "batch_size": 64,
    }
    values.update(updates)
    return EmbeddingSettings(**values)


def test_embedding_settings_default_to_disabled_and_use_independent_file(monkeypatch, tmp_path: Path) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    adapter = OpenAICompatibleEmbeddingService(settings_service)

    assert settings_service.settings_path.name == "embedding_settings.json"
    default_settings = settings_service.load()
    assert default_settings.enabled is False
    assert default_settings.batch_size == DEFAULT_EMBEDDING_BATCH_SIZE == 20
    assert adapter.configured_profile() is None
    with pytest.raises(EmbeddingValidationError) as exc_info:
        adapter.embed_texts(["hello"])
    assert exc_info.value.error_code == "embedding_not_enabled"


def test_embedding_api_key_is_user_persisted_but_not_represented_or_fingerprinted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    first = _enabled_settings(api_key="first-secret")
    settings_service.save(first)

    stored = json.loads(settings_service.settings_path.read_text(encoding="utf-8"))
    loaded = settings_service.load()
    first_profile = OpenAICompatibleEmbeddingService(settings_service).configured_profile()
    settings_service.save(first.model_copy(update={"api_key": "second-secret"}))
    second_profile = OpenAICompatibleEmbeddingService(settings_service).configured_profile()

    assert stored["api_key"] == "first-secret"
    assert loaded.api_key == "first-secret"
    assert "first-secret" not in repr(loaded)
    assert first_profile is not None and second_profile is not None
    assert first_profile.profile_fingerprint == second_profile.profile_fingerprint
    assert "first-secret" not in first_profile.profile_fingerprint
    assert "second-secret" not in second_profile.profile_fingerprint


def test_embed_texts_prepares_batches_and_restores_provider_index_order(monkeypatch, tmp_path: Path) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(
        _enabled_settings(
            base_url="https://EMBEDDING.example.test/gateway/v1/",
            batch_size=2,
            dimensions=2,
        )
    )
    requests: list[tuple[urllib.request.Request, int, dict]] = []

    def fake_urlopen(http_request: urllib.request.Request, timeout: int) -> _FakeResponse:
        payload = json.loads(http_request.data.decode("utf-8"))
        requests.append((http_request, timeout, payload))
        data = [
            {"index": index, "embedding": [float(len(text)), float(index)]}
            for index, text in enumerate(payload["input"])
        ]
        return _FakeResponse({"data": list(reversed(data))})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = OpenAICompatibleEmbeddingService(settings_service).embed_texts(
        ["  Ａ  ", "second", "third"]
    )

    assert [request.full_url for request, _, _ in requests] == [
        "https://embedding.example.test/gateway/v1/embeddings",
        "https://embedding.example.test/gateway/v1/embeddings",
    ]
    assert [payload["input"] for _, _, payload in requests] == [["A", "second"], ["third"]]
    assert all(payload["model"] == "embed-test" for _, _, payload in requests)
    assert all(payload["encoding_format"] == "float" for _, _, payload in requests)
    assert all(payload["dimensions"] == 2 for _, _, payload in requests)
    assert all(request.get_header("Authorization") == "Bearer top-secret-key" for request, _, _ in requests)
    assert result.vectors == ((1.0, 0.0), (6.0, 1.0), (5.0, 0.0))
    assert result.embeddings == result.vectors
    assert result.profile.dimensions == 2


def test_embed_texts_appends_v1_and_omits_authorization_without_key(monkeypatch, tmp_path: Path) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(_enabled_settings(base_url="http://localhost:8080/api/", api_key=""))
    configured_profile = OpenAICompatibleEmbeddingService(settings_service).configured_profile()
    captured: list[urllib.request.Request] = []

    def fake_urlopen(http_request: urllib.request.Request, timeout: int) -> _FakeResponse:
        captured.append(http_request)
        return _FakeResponse({"data": [{"index": 0, "embedding": [1, 2, 3]}]})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = OpenAICompatibleEmbeddingService(settings_service).embed_texts(["hello"])

    assert captured[0].full_url == "http://localhost:8080/api/v1/embeddings"
    assert captured[0].get_header("Authorization") is None
    assert result.profile.dimensions is None
    assert result.dimensions == 3
    assert configured_profile is not None
    assert configured_profile.profile_fingerprint == result.profile.profile_fingerprint


def test_embed_texts_uses_one_settings_snapshot_across_all_http_batches(monkeypatch, tmp_path: Path) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(_enabled_settings(model="first-model", batch_size=1, api_key="first-key"))
    payloads: list[dict] = []

    def fake_urlopen(http_request: urllib.request.Request, timeout: int) -> _FakeResponse:
        payloads.append(json.loads(http_request.data.decode("utf-8")))
        if len(payloads) == 1:
            settings_service.save(
                _enabled_settings(
                    model="changed-mid-operation",
                    batch_size=1,
                    api_key="changed-key",
                    dimensions=3,
                )
            )
        assert http_request.get_header("Authorization") == "Bearer first-key"
        return _FakeResponse({"data": [{"index": 0, "embedding": [1.0, 2.0]}]})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    batch = OpenAICompatibleEmbeddingService(settings_service).embed_texts(["one", "two"])

    assert [payload["model"] for payload in payloads] == ["first-model", "first-model"]
    assert all("dimensions" not in payload for payload in payloads)
    assert batch.profile.model == "first-model"
    assert batch.profile.dimensions is None
    assert batch.dimensions == 2


def test_frozen_session_reuses_one_private_settings_snapshot_across_calls(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(
        _enabled_settings(model="first-model", api_key="first-key", dimensions=2)
    )
    requests: list[tuple[str, str | None]] = []

    def fake_urlopen(http_request: urllib.request.Request, timeout: int) -> _FakeResponse:
        payload = json.loads(http_request.data.decode("utf-8"))
        requests.append((payload["model"], http_request.get_header("Authorization")))
        return _FakeResponse({"data": [{"index": 0, "embedding": [1.0, 2.0]}]})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    adapter = OpenAICompatibleEmbeddingService(settings_service)
    session = adapter.freeze()
    assert session is not None
    settings_service.save(
        _enabled_settings(model="second-model", api_key="second-key", dimensions=2)
    )

    session.embed_texts(["document"])
    session.embed_texts(["query"])

    assert requests == [
        ("first-model", "Bearer first-key"),
        ("first-model", "Bearer first-key"),
    ]
    assert session.profile.model == "first-model"


@pytest.mark.parametrize(
    ("texts", "error_code"),
    [
        ([], "embedding_input_empty"),
        (["  "], "embedding_text_empty"),
        (["x" * (MAX_EMBEDDING_TEXT_CHARS + 1)], "embedding_text_too_long"),
    ],
)
def test_embed_texts_rejects_empty_and_oversized_input(
    monkeypatch,
    tmp_path: Path,
    texts: list[str],
    error_code: str,
) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(_enabled_settings())

    with pytest.raises(EmbeddingValidationError) as exc_info:
        OpenAICompatibleEmbeddingService(settings_service).embed_texts(texts)

    assert exc_info.value.error_code == error_code


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        ({"not_data": []}, "embedding_response_invalid_shape"),
        ({"data": []}, "embedding_response_count_mismatch"),
        ({"data": [{"index": 1, "embedding": [1.0]}]}, "embedding_response_invalid_index"),
        ({"data": [{"index": 0, "embedding": ["bad"]}]}, "embedding_response_invalid_vector_type"),
        ({"data": [{"index": 0, "embedding": [float("nan")]}]}, "embedding_response_non_finite"),
    ],
)
def test_embed_texts_rejects_malformed_provider_responses(
    monkeypatch,
    tmp_path: Path,
    payload: object,
    error_code: str,
) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(_enabled_settings())
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _FakeResponse(payload))

    with pytest.raises(EmbeddingValidationError) as exc_info:
        OpenAICompatibleEmbeddingService(settings_service).embed_texts(["hello"])

    assert exc_info.value.error_code == error_code


@pytest.mark.parametrize(
    ("settings", "payload", "error_code"),
    [
        (
            _enabled_settings(),
            {"data": [{"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": [1.0, 2.0]}]},
            "embedding_response_mixed_dimensions",
        ),
        (
            _enabled_settings(dimensions=3),
            {"data": [{"index": 0, "embedding": [1.0, 2.0]}]},
            "embedding_response_dimension_mismatch",
        ),
    ],
)
def test_embed_texts_rejects_mixed_and_expected_dimension_mismatches(
    monkeypatch,
    tmp_path: Path,
    settings: EmbeddingSettings,
    payload: object,
    error_code: str,
) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(settings)
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _FakeResponse(payload))
    texts = ["one", "two"] if error_code.endswith("mixed_dimensions") else ["one"]

    with pytest.raises(EmbeddingValidationError) as exc_info:
        OpenAICompatibleEmbeddingService(settings_service).embed_texts(texts)

    assert exc_info.value.error_code == error_code


def test_http_errors_do_not_expose_provider_body_url_or_key(monkeypatch, tmp_path: Path) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(_enabled_settings(api_key="never-expose-this-key"))
    provider_body = b'{"error":{"message":"body-must-stay-private"}}'

    def fail_request(request: urllib.request.Request, timeout: int):
        raise urllib.error.HTTPError(
            url="https://private-provider.example.test/v1/embeddings",
            code=401,
            msg="provider-message-must-stay-private",
            hdrs=None,
            fp=io.BytesIO(provider_body),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fail_request)

    with pytest.raises(EmbeddingValidationError) as exc_info:
        OpenAICompatibleEmbeddingService(settings_service).embed_texts(["hello"])

    error = exc_info.value
    exposed = f"{error!r} {error} {error.error_code} {error.error_details}"
    assert error.error_code == "embedding_provider_http_error"
    assert error.error_details == {"status_code": 401}
    assert error.__context__ is None
    assert "body-must-stay-private" not in exposed
    assert "private-provider" not in exposed
    assert "never-expose-this-key" not in exposed


def test_provider_response_reader_never_falls_back_to_an_unbounded_read(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(_enabled_settings())

    class _RejectsBoundedRead(_FakeResponse):
        def read(self, size: int = -1) -> bytes:
            if size >= 0:
                raise TypeError("bounded reads unsupported")
            raise AssertionError("an unbounded provider read must never be attempted")

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: _RejectsBoundedRead({"data": []}),
    )

    with pytest.raises(EmbeddingValidationError) as exc_info:
        OpenAICompatibleEmbeddingService(settings_service).embed_texts(["hello"])

    assert exc_info.value.error_code == "embedding_provider_request_failed"


def test_provider_cannot_choose_an_unbounded_vector_dimension(monkeypatch, tmp_path: Path) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(_enabled_settings(dimensions=None))
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(
            {
                "data": [
                    {
                        "index": 0,
                        "embedding": [0.0] * (MAX_EMBEDDING_DIMENSIONS + 1),
                    }
                ]
            }
        ),
    )

    with pytest.raises(EmbeddingValidationError) as exc_info:
        OpenAICompatibleEmbeddingService(settings_service).embed_texts(["hello"])

    assert exc_info.value.error_code == "embedding_response_dimension_too_large"
