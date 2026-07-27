import xenix.single_instance as module
from xenix.main import _instance_mutex_name


def test_single_instance_guard_is_noop_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(module, "_kernel32", None)
    guard = module.SingleInstanceGuard()
    guard.close()


def test_smoke_mutex_is_runtime_home_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "first"))
    first = _instance_mutex_name(smoke_test=True)
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "second"))
    second = _instance_mutex_name(smoke_test=True)

    assert first.startswith("Local\\dev.lanzhijiang.xenix.smoke.")
    assert first != second
    assert _instance_mutex_name(smoke_test=False) == "Local\\dev.lanzhijiang.xenix.gui"
