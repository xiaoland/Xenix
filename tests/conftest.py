from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from xenix.config import AppPaths
    from xenix.services.storage.bootstrap import StorageContext


# Registration is global because pytest 9 forbids pytest_plugins in a nested
# conftest. The plugin is inert unless a test explicitly requests ui_artifacts.
pytest_plugins = ["pytester", "tests.ui.pytest_plugin"]


@pytest.fixture(scope="session")
def qapp_args(pytestconfig: pytest.Config) -> list[str]:
    # Scope the default to pytest-qt's QApplication. The headed Agent Harness
    # creates its own app, and native smoke explicitly selects the windows QPA.
    args = [pytestconfig.getini("qt_qapp_name")]
    if "QT_QPA_PLATFORM" not in os.environ:
        args.extend(("-platform", "offscreen"))
    return args


@pytest.fixture
def app_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AppPaths:
    """An opt-in runtime home, resolved through the production configuration."""
    from xenix.config import ensure_app_dirs, get_app_paths

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    return ensure_app_dirs(get_app_paths())


@pytest.fixture
def storage(app_paths: AppPaths) -> Iterator[StorageContext]:
    """Production migrations with guaranteed disposal, including assertion failures.

    Fixtures owning workers must depend on this fixture and stop those workers
    during their own teardown, before the database engine is disposed.
    """
    from xenix.services.storage import StorageBootstrapService

    context = StorageBootstrapService().initialize(app_paths)
    try:
        yield context
    finally:
        context.engine.dispose()
