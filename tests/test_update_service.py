from pathlib import Path
from types import SimpleNamespace

import xenix.services.update_service as module
from xenix.config import AppPaths
from xenix.services.runtime_activity import ApplicationActivityCoordinator
from xenix.services.update_service import UpdateService, UpdateState


def _paths(root: Path) -> AppPaths:
    return AppPaths(root, root / "config", root / "logs", root / "cache", root / "state", root / "temp", root / "artifacts", root / "resources")


class FakeManager:
    def __init__(self, update=None) -> None:
        self.update = update
        self.applied = False

    def check_for_updates(self):
        return self.update

    def download_updates(self, update_info, progress_callback=None):
        if progress_callback:
            progress_callback(100)

    def wait_exit_then_apply_updates(self, update, silent=False, restart=True, restart_args=None):
        self.applied = True


def test_check_download_and_apply(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "APP_UPDATE_FEED_URL", "https://updates.example.test")
    database = tmp_path / "xenix.db"
    import sqlite3
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample(value TEXT)")
    info = SimpleNamespace(TargetFullRelease=SimpleNamespace(Version="1.0.1"))
    manager = FakeManager(info)
    service = UpdateService(_paths(tmp_path), database, manager_factory=lambda _: manager, coordinator=ApplicationActivityCoordinator())
    assert service.check().state is UpdateState.UPDATE_AVAILABLE
    assert service.download().state is UpdateState.READY
    stopped = []
    service.apply(lambda: stopped.append(True))
    assert manager.applied and stopped == [True]
