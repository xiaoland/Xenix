import importlib.util
from pathlib import Path

import pytest

from xenix.build_info import DEVELOPMENT_BUILD_COMMIT, _display_build_commit


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

    build_info_path = package_app._write_generated_build_info(tmp_path, commit)

    assert build_info_path == tmp_path / "src" / "xenix" / "_generated_build_info.py"
    assert f'BUILD_COMMIT = "{commit}"' in build_info_path.read_text(encoding="utf-8")

    package_app._remove_generated_build_info(tmp_path)

    assert not build_info_path.exists()


def test_package_trial_llm_file_embeds_environment_values_and_is_removable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_TRIAL_LLM_BASE_URL", "https://trial.example.test")
    monkeypatch.setenv("XENIX_TRIAL_LLM_API_KEY", "trial-secret")
    monkeypatch.setenv("XENIX_TRIAL_LLM_MODEL", "vendor-real-model")

    trial_llm_path = package_app._write_generated_trial_llm(tmp_path)

    assert trial_llm_path == tmp_path / "src" / "xenix" / "_generated_trial_llm.py"
    content = trial_llm_path.read_text(encoding="utf-8")
    assert "TRIAL_LLM_BASE_URL = 'https://trial.example.test'" in content
    assert "TRIAL_LLM_API_KEY = 'trial-secret'" in content
    assert "TRIAL_LLM_MODEL = 'vendor-real-model'" in content

    package_app._remove_generated_trial_llm(tmp_path)

    assert not trial_llm_path.exists()


def test_package_trial_llm_file_allows_missing_api_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XENIX_TRIAL_LLM_API_KEY", raising=False)

    trial_llm_path = package_app._write_generated_trial_llm(tmp_path)
    content = trial_llm_path.read_text(encoding="utf-8")

    assert "TRIAL_LLM_API_KEY = ''" in content


def test_package_trial_lock_days_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("XENIX_TRIAL_LOCK_DAYS", raising=False)

    assert package_app._resolve_trial_lock_days() == 0


def test_package_trial_lock_days_rejects_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("XENIX_TRIAL_LOCK_DAYS", "three")

    with pytest.raises(ValueError, match="XENIX_TRIAL_LOCK_DAYS"):
        package_app._resolve_trial_lock_days()

    monkeypatch.setenv("XENIX_TRIAL_LOCK_DAYS", "-1")

    with pytest.raises(ValueError, match="XENIX_TRIAL_LOCK_DAYS"):
        package_app._resolve_trial_lock_days()


def test_package_trial_lock_file_embeds_days_secret_and_build_id(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_TRIAL_LOCK_DAYS", "14")
    monkeypatch.delenv("XENIX_TRIAL_LOCK_STATE_SECRET", raising=False)

    trial_lock_path = package_app._write_generated_trial_lock(tmp_path, "abcdef123456")

    assert trial_lock_path == tmp_path / "src" / "xenix" / "_generated_trial_lock.py"
    content = trial_lock_path.read_text(encoding="utf-8")
    assert "TRIAL_LOCK_DAYS = 14" in content
    assert "TRIAL_LOCK_STATE_SECRET = ''" not in content
    assert "TRIAL_LOCK_BUILD_ID = 'abcdef123456'" in content

    package_app._remove_generated_trial_lock(tmp_path)

    assert not trial_lock_path.exists()


def test_package_trial_lock_file_uses_fixed_state_secret(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_TRIAL_LOCK_DAYS", "60")
    monkeypatch.setenv("XENIX_TRIAL_LOCK_STATE_SECRET", "stable-secret-for-test-wave")

    trial_lock_path = package_app._write_generated_trial_lock(tmp_path, "abcdef123456")
    content = trial_lock_path.read_text(encoding="utf-8")

    assert "TRIAL_LOCK_DAYS = 60" in content
    assert "TRIAL_LOCK_STATE_SECRET = 'stable-secret-for-test-wave'" in content


def test_package_trial_lock_disabled_file_omits_state_secret(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_TRIAL_LOCK_DAYS", "0")
    monkeypatch.setenv("XENIX_TRIAL_LOCK_STATE_SECRET", "unused-secret")

    trial_lock_path = package_app._write_generated_trial_lock(tmp_path, "abcdef123456")
    content = trial_lock_path.read_text(encoding="utf-8")

    assert "TRIAL_LOCK_DAYS = 0" in content
    assert "TRIAL_LOCK_STATE_SECRET = ''" in content
