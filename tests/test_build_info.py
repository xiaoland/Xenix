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
