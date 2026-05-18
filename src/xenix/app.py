from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .config import APP_NAME, APP_ORGANIZATION, ensure_app_dirs, get_app_paths
from .exceptions import install_exception_hooks
from .i18n import TranslationManager
from .logging import setup_logging
from .resources import package_resource_path
from .services.agent import (
    AgentHarnessService,
    AgentSettingsService,
    AgentToolRegistry,
    ConversationStore,
)
from .services.artifact_service import ArtifactService
from .services.data_cleaning import DataCleaningService
from .services.data_transform import DataQueryInput, DataQueryTransformService, DatasetSqlBinding
from .services.dataset_service import DatasetService
from .services.ml_service import MLService
from .services.ml_task_service import MLTaskService
from .services.storage import StorageBootstrapService
from .services.storage.layout import database_path
from .ui.main_window import MainWindow

LOGGER = logging.getLogger("xenix.bootstrap")


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    icon_path = package_resource_path("logo.png")
    app.setWindowIcon(QIcon(str(icon_path)))

    return app


def build_main_window(*, show: bool = True) -> tuple[QApplication, MainWindow]:
    paths = ensure_app_dirs(get_app_paths())
    log_path = setup_logging(paths)
    install_exception_hooks()
    context = StorageBootstrapService().initialize(paths)

    dataset_service = DatasetService(context.session_factory, paths)
    data_cleaning_service = DataCleaningService(paths)
    data_transform_service = DataQueryTransformService(paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        ml_task_service,
    )
    artifact_service = ArtifactService(context.session_factory)
    conversation_store = ConversationStore(context.session_factory)
    agent_settings_service = AgentSettingsService(paths)
    agent_tool_registry = AgentToolRegistry(
        paths=paths,
        dataset_service=dataset_service,
        data_cleaning_service=data_cleaning_service,
        data_transform_service=data_transform_service,
        ml_service=ml_service,
        artifact_service=artifact_service,
    )
    agent_harness_service = AgentHarnessService(
        session_factory=context.session_factory,
        provider=agent_settings_service.build_provider(),
        tool_registry=agent_tool_registry,
        conversation_store=conversation_store,
    )

    app = create_application()
    translation_manager = TranslationManager(app, paths)
    translation_manager.initialize()
    window = MainWindow(
        paths=paths,
        log_path=log_path,
        db_path=database_path(paths),
        translation_manager=translation_manager,
        agent_harness_service=agent_harness_service,
        agent_settings_service=agent_settings_service,
        artifact_service=artifact_service,
    )
    if show:
        window.show()

    LOGGER.info("Xenix native shell started")
    return app, window


def _run_smoke_checks(paths) -> None:
    duckdb_smoke_path = paths.temp / "duckdb-smoke.csv"
    duckdb_smoke_path.write_text("value\n1\n2\n", encoding="utf-8")
    result = DataQueryTransformService(paths).query(
        DataQueryInput(
            bindings=[
                DatasetSqlBinding(
                    alias="input",
                    dataset_id="smoke-dataset",
                    source_path=str(duckdb_smoke_path.resolve()),
                )
            ],
            sql="SELECT SUM(value) AS total FROM input",
            limit=1,
        )
    )
    if not result.rows or result.rows[0].get("total") != 3:
        raise RuntimeError("DuckDB smoke query failed.")


def run(*, smoke_test: bool = False) -> int:
    app, window = build_main_window(show=not smoke_test)
    if smoke_test:
        _run_smoke_checks(ensure_app_dirs(get_app_paths()))
        window.show()
        app.processEvents()
        window.close()
        LOGGER.info("Xenix smoke test completed")
        return 0
    return app.exec()
