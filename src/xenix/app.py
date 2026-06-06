from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Literal

from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEventLoop, QThread, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import APP_NAME, APP_ORGANIZATION, ensure_app_dirs, get_app_paths
from .exceptions import StorageBootstrapError, install_exception_hooks
from .i18n import TranslationManager
from .logging import setup_logging
from .observability import flush_observability, record_counter, setup_observability, start_span
from .resources import package_resource_path
from .ui.startup_splash import StartupSplash, StartupStage

if TYPE_CHECKING:
    from .ui.main_window import MainWindow

LOGGER = logging.getLogger("xenix.bootstrap")
STARTUP_SPLASH_HOLD_MS = 2200
StorageRecoveryAction = Literal["quarantine", "open", "exit"]


def __getattr__(name: str) -> object:
    if name == "MainWindow":
        from .ui.main_window import MainWindow

        globals()[name] = MainWindow
        return MainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


def quarantine_database(db_path: Path, *, timestamp: datetime | None = None) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    resolved_timestamp = timestamp or datetime.now()
    stamp = resolved_timestamp.strftime("%Y%m%d-%H%M%S")
    candidate = db_path.with_name(f"{db_path.stem}.corrupt-{stamp}{db_path.suffix}")
    suffix = 1
    while candidate.exists():
        candidate = db_path.with_name(f"{db_path.stem}.corrupt-{stamp}-{suffix}{db_path.suffix}")
        suffix += 1
    db_path.replace(candidate)
    return candidate


def _storage_recovery_detail(exc: BaseException) -> str:
    cause = exc.__cause__ or exc
    return str(cause) or cause.__class__.__name__


def _prompt_storage_recovery(
    *,
    db_path: Path,
    exc: BaseException,
) -> StorageRecoveryAction:
    message_box = QMessageBox()
    message_box.setIcon(QMessageBox.Critical)
    message_box.setWindowTitle(
        QCoreApplication.translate("XenixStartup", "Local database recovery")
    )
    message_box.setText(
        QCoreApplication.translate(
            "XenixStartup",
            "Xenix could not initialize the local database.",
        )
    )
    message_box.setInformativeText(
        QCoreApplication.translate(
            "XenixStartup",
            "The database may belong to an unsupported development build or may be damaged. "
            "You can back it up and rebuild a fresh database now.",
        )
    )
    message_box.setDetailedText(
        QCoreApplication.translate(
            "XenixStartup",
            "Database: {path}\n\nReason: {reason}",
        ).format(path=db_path, reason=_storage_recovery_detail(exc))
    )
    rebuild_button = message_box.addButton(
        QCoreApplication.translate("XenixStartup", "Back up and rebuild"),
        QMessageBox.AcceptRole,
    )
    open_button = message_box.addButton(
        QCoreApplication.translate("XenixStartup", "Open data folder"),
        QMessageBox.ActionRole,
    )
    exit_button = message_box.addButton(
        QCoreApplication.translate("XenixStartup", "Exit"),
        QMessageBox.RejectRole,
    )
    message_box.setDefaultButton(rebuild_button)
    message_box.exec()

    clicked_button = message_box.clickedButton()
    if clicked_button is rebuild_button:
        return "quarantine"
    if clicked_button is open_button:
        return "open"
    if clicked_button is exit_button:
        return "exit"
    return "exit"


def _recover_storage_bootstrap(
    *,
    app: QApplication,
    runtime: SimpleNamespace,
    paths,
    initial_error: StorageBootstrapError,
):
    db_path = runtime.database_path(paths)
    error: StorageBootstrapError = initial_error
    while db_path.exists():
        action = _prompt_storage_recovery(db_path=db_path, exc=error)
        if action == "exit":
            raise error
        if action == "open":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(db_path.parent)))
            app.processEvents()
            continue

        quarantined_path = quarantine_database(db_path)
        LOGGER.warning(
            "Quarantined local database after startup storage failure: %s -> %s",
            db_path,
            quarantined_path,
        )
        try:
            return runtime.StorageBootstrapService().initialize(paths)
        except StorageBootstrapError as exc:
            error = exc
            LOGGER.exception("Storage bootstrap retry failed after database quarantine")

    raise error


def _load_runtime_imports() -> SimpleNamespace:
    from .services.agent import (
        AgentHarnessService,
        AgentToolRegistry,
        ConversationStore,
    )
    from .services.artifact_service import ArtifactService
    from .services.data_cleaning import DataCleaningService
    from .services.data_transform import DataQueryTransformService
    from .services.dataset_service import DatasetService
    from .services.llm import LLMService, LLMSettingsService
    from .services.ml.worker_settings import MLWorkerSettingsService
    from .services.ml_service import MLService
    from .services.ml_task_service import MLTaskService
    from .services.storage import StorageBootstrapService
    from .services.storage.layout import database_path

    return SimpleNamespace(
        AgentHarnessService=AgentHarnessService,
        AgentToolRegistry=AgentToolRegistry,
        ArtifactService=ArtifactService,
        ConversationStore=ConversationStore,
        DataCleaningService=DataCleaningService,
        DataQueryTransformService=DataQueryTransformService,
        DatasetService=DatasetService,
        LLMService=LLMService,
        LLMSettingsService=LLMSettingsService,
        MLService=MLService,
        MLTaskService=MLTaskService,
        MLWorkerSettingsService=MLWorkerSettingsService,
        StorageBootstrapService=StorageBootstrapService,
        database_path=database_path,
    )


def _load_runtime_imports_with_events(
    app: QApplication,
    splash: StartupSplash | None,
) -> SimpleNamespace:
    if splash is None:
        return _load_runtime_imports()

    completed = threading.Event()
    result: SimpleNamespace | None = None
    error: BaseException | None = None

    def load() -> None:
        nonlocal error, result
        try:
            result = _load_runtime_imports()
        except BaseException as exc:
            error = exc
        finally:
            completed.set()

    thread = threading.Thread(target=load, name="xenix-startup-imports", daemon=True)
    thread.start()
    while not completed.is_set():
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        completed.wait(0.016)
    thread.join()
    app.processEvents()

    if error is not None:
        raise error
    if result is None:
        raise RuntimeError("Runtime imports did not produce a result.")
    return result


def build_main_window(
    *,
    show: bool = True,
    show_splash: bool | None = None,
    splash_hold_ms: int = 0,
) -> tuple[QApplication, MainWindow]:
    app = create_application()
    paths = get_app_paths()
    translation_manager = TranslationManager(app, paths)
    translation_manager.initialize()
    should_show_splash = show if show_splash is None else show_splash
    splash = StartupSplash() if should_show_splash else None

    if splash is not None:
        splash.show_centered()
        _update_startup_stage(app, splash, StartupStage.STARTING)

    startup_scope = None
    startup_span_active = False
    try:
        _update_startup_stage(app, splash, StartupStage.PREPARING_APP_DATA)
        paths = ensure_app_dirs(paths)

        _update_startup_stage(app, splash, StartupStage.LOADING_RUNTIME)
        runtime = _load_runtime_imports_with_events(app, splash)
        from .ui.main_window import MainWindow

        _update_startup_stage(app, splash, StartupStage.INITIALIZING_LOGGING)
        log_path = setup_logging(paths)
        observability = setup_observability(paths)
        startup_scope = start_span("app.startup")
        startup_scope.__enter__()
        startup_span_active = True
        install_exception_hooks()
        LOGGER.info(
            "Observability initialized",
            extra={
                "event_name": "app.observability.initialized",
                "otlp_enabled": observability.otlp_enabled,
                "otlp_log_export_enabled": observability.log_export_enabled,
            },
        )

        if splash is not None:
            splash.retranslate_ui()

        _update_startup_stage(app, splash, StartupStage.INITIALIZING_STORAGE)
        try:
            with start_span("storage.bootstrap"):
                context = runtime.StorageBootstrapService().initialize(paths)
                record_counter(
                    "xenix.storage.bootstrap.count",
                    attributes={
                        "storage.schema_version": context.schema_version,
                        "status": "succeeded",
                    },
                )
        except StorageBootstrapError as exc:
            record_counter(
                "xenix.storage.bootstrap.count",
                attributes={"status": "failed", "error.type": exc.__class__.__name__},
            )
            if not show or not runtime.database_path(paths).exists():
                raise
            _close_startup_splash(app, splash)
            splash = None
            context = _recover_storage_bootstrap(
                app=app,
                runtime=runtime,
                paths=paths,
                initial_error=exc,
            )

        _update_startup_stage(app, splash, StartupStage.LOADING_WORKBENCH)
        dataset_service = runtime.DatasetService(context.session_factory, paths)
        data_cleaning_service = runtime.DataCleaningService(paths)
        data_transform_service = runtime.DataQueryTransformService(paths)
        ml_worker_settings_service = runtime.MLWorkerSettingsService(paths)
        ml_task_service = runtime.MLTaskService(
            context.session_factory,
            paths,
            worker_settings_service=ml_worker_settings_service,
        )
        ml_service = runtime.MLService(
            paths,
            context.session_factory,
            dataset_service,
            ml_task_service,
        )
        artifact_service = runtime.ArtifactService(context.session_factory)
        conversation_store = runtime.ConversationStore(context.session_factory)
        llm_settings_service = runtime.LLMSettingsService(paths)
        llm_service = runtime.LLMService(llm_settings_service)
        agent_tool_registry = runtime.AgentToolRegistry(
            paths=paths,
            dataset_service=dataset_service,
            data_cleaning_service=data_cleaning_service,
            data_transform_service=data_transform_service,
            ml_service=ml_service,
            artifact_service=artifact_service,
        )
        agent_harness_service = runtime.AgentHarnessService(
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
            db_path=runtime.database_path(paths),
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
        record_counter("xenix.app.startup.count", attributes={"status": "succeeded"})
        startup_scope.__exit__(None, None, None)
        startup_span_active = False
        flush_observability()
        return app, window
    except Exception:
        record_counter("xenix.app.startup.count", attributes={"status": "failed"})
        if startup_span_active and startup_scope is not None:
            startup_scope.__exit__(*sys.exc_info())
            startup_span_active = False
        flush_observability()
        _close_startup_splash(app, splash)
        raise


def _run_smoke_checks(paths) -> None:
    from .services.analysis_graph import AnalysisGraphService, GraphDatasetInput
    from .services.data_transform import (
        DataQueryInput,
        DataQueryTransformService,
        DatasetSqlBinding,
    )

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

    graph_smoke_path = paths.temp / "graph-smoke.csv"
    graph_smoke_path.write_text("label,value\nA,1\nB,2\n", encoding="utf-8")
    graph_result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(graph_smoke_path.resolve()),
            dataset_name="Graph smoke",
            spec={
                "mark": "bar",
                "encoding": {
                    "x": {"field": "label", "type": "nominal"},
                    "y": {"field": "value", "type": "quantitative"},
                },
                "title": "Graph smoke",
            },
        )
    )
    graph_output = Path(graph_result.output_path)
    if not graph_output.is_file() or not graph_output.read_text(encoding="utf-8").lstrip().startswith("<svg"):
        raise RuntimeError("Vega-Lite graph smoke render failed.")


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
        try:
            _run_smoke_checks(ensure_app_dirs(get_app_paths()))
            window.show()
            app.processEvents()
            window.close()
            LOGGER.info("Xenix smoke test completed")
            flush_observability()
            return 0
        except Exception:
            LOGGER.exception("Xenix smoke test failed")
            window.close()
            flush_observability()
            return 1
    return app.exec()
