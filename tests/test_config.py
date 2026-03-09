from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths


def test_env_override_controls_app_home(monkeypatch, tmp_path: Path) -> None:
    overridden_home = tmp_path / "xenix-home"
    monkeypatch.setenv("XENIX_APP_HOME", str(overridden_home))

    paths = ensure_app_dirs(get_app_paths())

    assert paths.home == overridden_home
    assert paths.config.is_dir()
    assert paths.logs.is_dir()
    assert paths.cache.is_dir()
