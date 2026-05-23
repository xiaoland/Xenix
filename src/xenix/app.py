from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEventLoop, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import APP_NAME, APP_ORGANIZATION, ensure_app_dirs, get_app_paths
from .exceptions import install_exception_hooks
from .i18n import TranslationManager
from .logging import setup_logging
from .resources import package_resource_path
from .services.agent import (
    AgentHarnessService,
    AgentToolRegistry,
    ConversationStore,
)
from .services.artifact_service import ArtifactService
from .services.data_cleaning import DataCleaningService
from .services.data_transform import DataQueryInput, DataQueryTransformService, DatasetSqlBinding
from .services.dataset_service import DatasetService
from .services.ml_service import MLService
from .services.ml.worker_settings import MLWorkerSettingsService
from .services.ml_task_service import MLTaskService
from .services.llm import LLMService, LLMSettingsService
from .services.storage import StorageBootstrapService
from .services.storage.layout import database_path
from .ui.main_window import MainWindow
from .ui.startup_splash import StartupSplash, StartupStage

LOGGER = logging.getLogger("xenix.bootstrap")
STARTUP_SPLASH_HOLD_MS = 2200


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    icon_path = package_resource_path("logo.png")
    app.setWindowIcon(QIcon(str(icon_path)))

    return app


def _update_startup_stage(app: QApplication, splash: StartupSplash | None, stage: StartupStage) -> None:
    if splash is None:
        return
    splash.set_stage(stage)
    app.processEvents()


def _close_startup_splash(app: QApplication, splash: StartupSplash | None) -> None:
    if splash is None:
        return
    splash.close()
    splash.deleteLater()
    app.processEvents()


def _hold_startup_splash(app: QApplication, splash: StartupSplash | None, hold_ms: int) -> None:
    if splash is None or hold_ms <= 0:
        return

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < hold_ms:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        QThread.msleep(16)


def build_main_window(
    *,
    show: bool = True,
    show_splash: bool | None = None,
    splash_hold_ms: int = 0,
) -> tuple[QApplication, MainWindow]:
    app = create_application()
    should_show_splash = show if show_splash is None else show_splash
    splash = StartupSplash() if should_show_splash else None

    if splash is not None:
        splash.show_centered()
        _update_startup_stage(app, splash, StartupStage.STARTING)

    try:
        _update_startup_stage(app, splash, StartupStage.PREPARING_APP_DATA)
        paths = ensure_app_dirs(get_app_paths())

        _update_startup_stage(app, splash, StartupStage.INITIALIZING_LOGGING)
        log_path = setup_logging(paths)
        install_exception_hooks()

        translation_manager = TranslationManager(app, paths)
        translation_manager.initialize()
        if splash is not None:
            splash.retranslate_ui()

        _update_startup_stage(app, splash, StartupStage.INITIALIZING_STORAGE)
        context = StorageBootstrapService().initialize(paths)

        _update_startup_stage(app, splash, StartupStage.LOADING_WORKBENCH)
        dataset_service = DatasetService(context.session_factory, paths)
        data_cleaning_service = DataCleaningService(paths)
        data_transform_service = DataQueryTransformService(paths)
        ml_worker_settings_service = MLWorkerSettingsService(paths)
        ml_task_service = MLTaskService(
            context.session_factory,
            paths,
            worker_settings_service=ml_worker_settings_service,
        )
        ml_service = MLService(
            paths,
            context.session_factory,
            dataset_service,
            ml_task_service,
        )
        artifact_service = ArtifactService(context.session_factory)
        conversation_store = ConversationStore(context.session_factory)
        llm_settings_service = LLMSettingsService(paths)
        llm_service = LLMService(llm_settings_service)
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
            tool_registry=agent_tool_registry,
            llm_service=llm_service,
            turn_completion_guard_provider=llm_service.build_turn_completion_guard_provider(),
            thread_title_provider=llm_service.build_thread_title_provider(),
            conversation_store=conversation_store,
        )

        window = MainWindow(
            paths=paths,
            log_path=log_path,
            db_path=database_path(paths),
            translation_manager=translation_manager,
            agent_harness_service=agent_harness_service,
            llm_service=llm_service,
            llm_settings_service=llm_settings_service,
            ml_worker_settings_service=ml_worker_settings_service,
            artifact_service=artifact_service,
            ml_service=ml_service,
        )

        _update_startup_stage(app, splash, StartupStage.READY)
        _hold_startup_splash(app, splash, splash_hold_ms)
        _close_startup_splash(app, splash)
        if show:
            window.show()
            app.processEvents()

        LOGGER.info("Xenix native shell started")
        return app, window
    except Exception:
        _close_startup_splash(app, splash)
        raise


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
    try:
        app, window = build_main_window(
            show=not smoke_test,
            show_splash=not smoke_test,
            splash_hold_ms=0 if smoke_test else STARTUP_SPLASH_HOLD_MS,
        )
    except Exception as exc:
        if smoke_test:
            raise
        app = QApplication.instance() or create_application()
        QMessageBox.critical(
            None,
            QCoreApplication.translate("XenixStartup", "Unable to start Xenix"),
            QCoreApplication.translate(
                "XenixStartup",
                "Xenix could not finish startup.\n\n{error}",
            ).format(error=exc),
        )
        return 1

    if smoke_test:
        _run_smoke_checks(ensure_app_dirs(get_app_paths()))
        window.show()
        app.processEvents()
        window.close()
        LOGGER.info("Xenix smoke test completed")
        return 0
    return app.exec()
