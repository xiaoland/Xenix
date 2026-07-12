from __future__ import annotations

import os
import sys
from types import ModuleType

import pytest

from xenix.release_config import ReleaseConfig, apply_frozen_otel_environment, load_release_config


def _formal_environment() -> dict[str, str]:
    return {
        "RELEASES_OSS_PUBLIC_URL": "https://downloads.example.test/published/",
        "XENIX_TRIAL_LLM_BASE_URL": "https://trial.example.test/v1/",
        "XENIX_TRIAL_LLM_API_KEY": "trial-secret",
        "XENIX_TRIAL_LLM_MODEL": "trial-model",
        "XENIX_TRIAL_LOCK_DAYS": "14",
        "XENIX_TRIAL_LOCK_STATE_SECRET": "stable-lock-secret",
        "XENIX_TRIAL_PURCHASE_URL": "https://example.test/purchase/",
        "XENIX_OTEL_EXPORT_TRACES": "true",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "https://otel.example.test/v1/traces",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "authorization=embedded-token",
    }


def test_release_config_normalizes_and_derives_release_urls() -> None:
    config = ReleaseConfig.from_environment(
        _formal_environment(),
        release_build=True,
        public_release_build=True,
        build_commit="abcdef123456",
    )

    assert config.releases_oss_public_url == "https://downloads.example.test/published"
    assert config.update_feed_url == "https://downloads.example.test/published"
    assert config.setup_url == "https://downloads.example.test/published/Xenix-Setup.exe"
    assert config.trial_llm_base_url == "https://trial.example.test/v1"
    assert config.trial_purchase_url == "https://example.test/purchase"
    assert config.trial_lock_build_id == "abcdef123456"


def test_formal_release_requires_every_trial_product_input() -> None:
    environment = _formal_environment()
    environment.pop("XENIX_TRIAL_PURCHASE_URL")

    with pytest.raises(ValueError, match="XENIX_TRIAL_PURCHASE_URL"):
        ReleaseConfig.from_environment(environment, release_build=True)


def test_public_release_requires_https_release_url() -> None:
    environment = _formal_environment()
    environment["RELEASES_OSS_PUBLIC_URL"] = "http://downloads.example.test/published"

    with pytest.raises(ValueError, match="HTTPS.*RELEASES_OSS_PUBLIC_URL"):
        ReleaseConfig.from_environment(environment, public_release_build=True)


def test_otel_families_are_embedded_without_renaming() -> None:
    config = ReleaseConfig.from_environment(_formal_environment())

    assert config.otel_environment == {
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "https://otel.example.test/v1/traces",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "authorization=embedded-token",
        "XENIX_OTEL_EXPORT_TRACES": "true",
    }


def test_frozen_otel_configuration_replaces_runtime_values(monkeypatch) -> None:
    generated = ModuleType("xenix._generated_release_config")
    generated.RELEASE_CONFIG = ReleaseConfig(
        otel_environment={
            "XENIX_OTEL_EXPORT_TRACES": "true",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "https://embedded.example.test/v1/traces",
        }
    ).model_dump(mode="python")
    monkeypatch.setitem(sys.modules, "xenix._generated_release_config", generated)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://runtime.example.test")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "runtime-secret")

    apply_frozen_otel_environment()

    assert load_release_config().otel_environment["XENIX_OTEL_EXPORT_TRACES"] == "true"
    assert os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] == "https://embedded.example.test/v1/traces"
    assert "OTEL_EXPORTER_OTLP_HEADERS" not in os.environ


def test_frozen_product_configuration_ignores_runtime_environment(monkeypatch) -> None:
    generated = ModuleType("xenix._generated_release_config")
    generated.RELEASE_CONFIG = ReleaseConfig(
        releases_oss_public_url="https://embedded.example.test",
        trial_purchase_url="https://embedded.example.test/purchase",
    ).model_dump(mode="python")
    monkeypatch.setitem(sys.modules, "xenix._generated_release_config", generated)
    monkeypatch.setenv("RELEASES_OSS_PUBLIC_URL", "https://runtime.example.test")
    monkeypatch.setenv("XENIX_TRIAL_PURCHASE_URL", "https://runtime.example.test/purchase")

    config = load_release_config()

    assert config.releases_oss_public_url == "https://embedded.example.test"
    assert config.trial_purchase_url == "https://embedded.example.test/purchase"
