import importlib.util
from pathlib import Path

import pytest

from xenix.build_info import DEVELOPMENT_BUILD_COMMIT, _display_build_commit
from xenix.release_config import ReleaseConfig


def _load_package_app_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "package_app.py"
    spec = importlib.util.spec_from_file_location("xenix_package_app_for_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package_app = _load_package_app_module()


def test_build_commit_display_uses_twelve_character_hash() -> None:
    assert _display_build_commit("abcdef1234567890") == "abcdef123456"
    assert _display_build_commit(DEVELOPMENT_BUILD_COMMIT) == DEVELOPMENT_BUILD_COMMIT


def test_package_build_commit_can_be_supplied_from_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_BUILD_COMMIT", "ABCDEF123456")

    assert package_app._resolve_build_commit(tmp_path) == "abcdef123456"


def test_package_build_commit_rejects_non_hash_environment_value(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_BUILD_COMMIT", "not-a-hash")

    with pytest.raises(ValueError, match="Build commit"):
        package_app._resolve_build_commit(tmp_path)


def test_package_build_info_file_embeds_commit_and_is_removable(tmp_path: Path) -> None:
    commit = package_app._validate_build_commit("ABCDEF1234567890")

    build_info_path = package_app._write_generated_build_info(tmp_path, "1.0.0", commit)

    assert build_info_path == tmp_path / "src" / "xenix" / "_generated_build_info.py"
    content = build_info_path.read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.0.0"' in content
    assert f'BUILD_COMMIT = "{commit}"' in content

    package_app._remove_generated_build_info(tmp_path)

    assert not build_info_path.exists()


def test_windows_version_info_projects_semver(tmp_path: Path) -> None:
    path = package_app._write_windows_version_info(tmp_path, "1.2.3")
    content = path.read_text(encoding="utf-8")

    assert "filevers=(1, 2, 3, 0)" in content
    assert "StringStruct('ProductVersion', '1.2.3')" in content


def test_package_release_config_file_embeds_one_payload_and_is_removable(tmp_path: Path) -> None:
    config = ReleaseConfig(
        releases_oss_public_url="https://downloads.example.test/published",
        trial_llm_base_url="https://trial.example.test/v1",
        trial_llm_api_key="trial-secret",
        trial_llm_model="vendor-real-model",
        trial_lock_days=14,
        trial_lock_state_secret="stable-secret",
        trial_lock_build_id="abcdef123456",
        trial_purchase_url="https://example.test/purchase",
        otel_environment={"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "https://otel.example.test/v1/traces"},
    )

    path = package_app._write_generated_release_config(tmp_path, config)
    content = path.read_text(encoding="utf-8")

    assert path == tmp_path / "src" / "xenix" / "_generated_release_config.py"
    assert "RELEASE_CONFIG =" in content
    assert "https://downloads.example.test/published" in content
    assert "trial-secret" in content
    assert "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT" in content

    package_app._remove_generated_release_config(tmp_path)

    assert not path.exists()
