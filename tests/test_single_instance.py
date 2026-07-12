import xenix.single_instance as module


def test_single_instance_guard_is_noop_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(module, "_kernel32", None)
    guard = module.SingleInstanceGuard()
    guard.close()
