from pathlib import Path

from xenix.main import main


def test_smoke_test_bootstraps_runtime_in_fresh_app_home(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    exit_code = main(["--smoke-test"])

    assert exit_code == 0
    assert (runtime_home / "config").is_dir()
    assert (runtime_home / "logs").is_dir()
    assert (runtime_home / "cache").is_dir()
    assert (runtime_home / "state").is_dir()
    assert (runtime_home / "temp").is_dir()
    assert (runtime_home / "artifacts").is_dir()
    assert (runtime_home / "state" / "xenix.db").is_file()
    assert (runtime_home / "logs" / "xenix.log").is_file()
