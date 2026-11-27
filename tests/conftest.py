from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from xenix.config import AppPaths
    from xenix.services.storage.bootstrap import StorageContext


# Registration is global because pytest 9 forbids pytest_plugins in a nested
# conftest. The plugin is inert unless a test explicitly requests ui_artifacts;
# QPA selection remains scoped to tests/ui/conftest.py.
pytest_plugins = ["pytester", "tests.ui.pytest_plugin"]


@pytest.fixture(scope="session")
def _migrated_template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build one clean, production-migrated SQLite template DB per test session.

    Per-test ``storage`` fixtures clone this template instead of re-running 29
    sequential DDL commits on every test, keeping isolated per-test databases
    while cutting fixture setup from ~2.5s to milliseconds. Full 0->current
    bootstrap and migration paths remain directly verified under tests/storage/.
    """
    from xenix.config import ensure_app_dirs, get_app_paths
    from xenix.services.storage import StorageBootstrapService
    from xenix.services.storage.layout import database_path

    template_home = tmp_path_factory.mktemp("xenix-template-home")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("XENIX_APP_HOME", str(template_home))
        paths = ensure_app_dirs(get_app_paths())
        context = StorageBootstrapService().initialize(paths)
        try:
            return database_path(paths)
        finally:
            context.engine.dispose()


@pytest.fixture
def app_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AppPaths:
    """An opt-in runtime home, resolved through the production configuration."""
    from xenix.config import ensure_app_dirs, get_app_paths

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    return ensure_app_dirs(get_app_paths())


@pytest.fixture
def storage(app_paths: AppPaths, _migrated_template_db: Path) -> Iterator[StorageContext]:
    """Isolated production-schema database with guaranteed engine disposal.

    Fixtures owning workers must depend on this fixture and stop those workers
    during their own teardown, before the database engine is disposed.
    """
    from xenix.services.storage import StorageBootstrapService
    from xenix.services.storage.layout import database_path

    target_db = database_path(app_paths)
    target_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_migrated_template_db, target_db)

    context = StorageBootstrapService().initialize(app_paths)
    try:
        yield context
    finally:
        context.engine.dispose()
