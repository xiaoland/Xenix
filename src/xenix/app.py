from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEventLoop, QThread, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .application_lifetime import ApplicationLifetime
from .application_services import ApplicationServices
from .config import APP_NAME, APP_ORGANIZATION, AppPaths, ensure_app_dirs, get_app_paths
from .exceptions import StorageBootstrapError, install_exception_hooks
from .i18n import TranslationManager
from .logging import setup_logging, shutdown_logging
from .observability import (
    flush_observability,
    record_counter,
    setup_observability,
    start_span,
)
from .resources import package_resource_path
from .smoke_checks import run_smoke_checks
from .trial_lock import TrialLockCheck, check_trial_lock, trial_purchase_url
from .ui.startup_splash import StartupSplash, StartupStage

if TYPE_CHECKING:
    from .ui.main_window import MainWindow
    from .services.storage.bootstrap import StorageContext

LOGGER = logging.getLogger("xenix.bootstrap")
STARTUP_SPLASH_HOLD_MS = 2200
STARTUP_TIMING_ENV = "XENIX_STARTUP_TIMING"
_STARTUP_TIMING_T0 = time.perf_counter()
StorageRecoveryAction = Literal["quarantine", "open", "exit"]


class TrialLockStartupExit(Exception):
    pass


def _startup_timing_enabled() -> bool:
    return os.environ.get(STARTUP_TIMING_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _emit_startup_timing(event: str, start: float | None = None, **attributes: object) -> None:
    if not _startup_timing_enabled():
        return
    fields = [
        "XENIX_STARTUP_TIMING",
        event,
        f"since_app_import_ms={(time.perf_counter() - _STARTUP_TIMING_T0) * 1000:.3f}",
    ]
    if start is not None:
        fields.append(f"elapsed_ms={(time.perf_counter() - start) * 1000:.3f}")
    for key, value in attributes.items():
        fields.append(f"{key}={value}")
    print("\t".join(fields), file=sys.stderr, flush=True)


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
    message_box.setWindowTitle(QCoreApplication.translate("XenixStartup", "Local database recovery"))
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


def _prompt_trial_lock(check: TrialLockCheck) -> None:
    purchase_url = trial_purchase_url()
    message_box = QMessageBox()
    message_box.setIcon(QMessageBox.Warning)
    message_box.setWindowTitle(QCoreApplication.translate("XenixStartup", "Xenix test build locked"))
    message_box.setText(
        QCoreApplication.translate(
            "XenixStartup",
            "This Xenix test build is locked.",
        )
    )
    message_box.setInformativeText(
        QCoreApplication.translate(
            "XenixStartup",
            "Please purchase a license or download a licensed Xenix build from {url}.",
        ).format(url=purchase_url)
    )
    expires_at = check.expires_at_utc.isoformat() if check.expires_at_utc is not None else "-"
    message_box.setDetailedText(
        QCoreApplication.translate(
            "XenixStartup",
            "Reason: {reason}\nTrial expired at: {expires_at}\nState file: {state_path}",
        ).format(
            reason=check.reason.value,
            expires_at=expires_at,
            state_path=check.state_path,
        )
    )
    buy_button = message_box.addButton(
        QCoreApplication.translate("XenixStartup", "Buy license"),
        QMessageBox.AcceptRole,
    )
    exit_button = message_box.addButton(
        QCoreApplication.translate("XenixStartup", "Exit"),
        QMessageBox.RejectRole,
    )
    message_box.setDefaultButton(buy_button)
    message_box.exec()

    clicked_button = message_box.clickedButton()
    if clicked_button is buy_button and purchase_url:
        QDesktopServices.openUrl(QUrl(purchase_url))
    elif clicked_button is exit_button:
        return


def _recover_storage_bootstrap(
    *,
    app: QApplication,
    paths: AppPaths,
    initial_error: StorageBootstrapError,
) -> StorageContext:
    from .services.storage import StorageBootstrapService
    from .services.storage.layout import database_path

    db_path = database_path(paths)
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
            return StorageBootstrapService().initialize(paths)
        except StorageBootstrapError as exc:
            error = exc
            LOGGER.exception("Storage bootstrap retry failed after database quarantine")

    raise error


def _load_runtime_imports(*, module_loaded: Callable[[], None] | None = None) -> None:
    """Warm heavy imports on the Qt application thread at visible progress boundaries."""
    runtime_start = time.perf_counter()
    for module_name in (
        "xenix.services.agent.composition",
        "xenix.services.embedding_service",
        "xenix.services.job_service",
        "xenix.services.knowledge_import_service",
        "xenix.services.knowledge_derivation_service",
        "xenix.services.knowledge_document_lifecycle_service",
        "xenix.services.knowledge_index_service",
        "xenix.services.knowledge_workspace_service",
        "xenix.services.paddle_ocr_service",
        "xenix.services.llm",
        "xenix.services.ml.worker_settings",
        "xenix.services.storage",
    ):
        module_start = time.perf_counter()
        import_module(module_name)
        _emit_startup_timing("runtime_import.module", module_start, module=module_name)
        if module_loaded is not None:
            module_loaded()
    _emit_startup_timing("runtime_import.total", runtime_start)


def _load_runtime_imports_with_events(
    app: QApplication,
    splash: StartupSplash | None,
) -> None:
    if splash is None:
        load_start = time.perf_counter()
        _load_runtime_imports()
        _emit_startup_timing("runtime_import.no_splash_wait", load_start)
        return

    load_start = time.perf_counter()

    def process_module_boundary() -> None:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)

    _load_runtime_imports(module_loaded=process_module_boundary)
    app.processEvents()
    _emit_startup_timing("runtime_import.splash_wait", load_start)


def build_main_window(
    *,
    show: bool = True,
    show_splash: bool | None = None,
    splash_hold_ms: int = 0,
    flush_startup_observability: bool = False,
    on_services_ready: Callable[[ApplicationServices], None] | None = None,
) -> tuple[QApplication, MainWindow]:
    build_start = time.perf_counter()
    _emit_startup_timing("build_main_window.start")
    step_start = time.perf_counter()
    app = create_application()
    _emit_startup_timing("create_application", step_start)
    step_start = time.perf_counter()
    paths = get_app_paths()
    _emit_startup_timing("get_app_paths", step_start)
    step_start = time.perf_counter()
    translation_manager = TranslationManager(app, paths)
    translation_manager.initialize()
    _emit_startup_timing("translation.initialize", step_start)
    should_show_splash = show if show_splash is None else show_splash
    step_start = time.perf_counter()
    splash = StartupSplash() if should_show_splash else None
    _emit_startup_timing("splash.create", step_start, enabled=splash is not None)

    if splash is not None:
        step_start = time.perf_counter()
        splash.show_centered()
        _update_startup_stage(app, splash, StartupStage.STARTING)
        _emit_startup_timing("splash.show", step_start)

    startup_scope = None
    startup_span_active = False
    lifetime = ApplicationLifetime()
    try:
        _update_startup_stage(app, splash, StartupStage.PREPARING_APP_DATA)
        step_start = time.perf_counter()
        paths = ensure_app_dirs(paths)
        _emit_startup_timing("ensure_app_dirs", step_start)

        step_start = time.perf_counter()
        trial_lock_check = check_trial_lock(paths)
        _emit_startup_timing(
            "trial_lock.check",
            step_start,
            enabled=trial_lock_check.enabled,
            locked=trial_lock_check.locked,
            reason=trial_lock_check.reason.value,
        )
        if trial_lock_check.locked:
            _close_startup_splash(app, splash)
            splash = None
            if show:
                _prompt_trial_lock(trial_lock_check)
                app.processEvents()
            raise TrialLockStartupExit(trial_lock_check.reason.value)

        _update_startup_stage(app, splash, StartupStage.LOADING_RUNTIME)
        step_start = time.perf_counter()
        _load_runtime_imports_with_events(app, splash)
        _emit_startup_timing("load_runtime_imports", step_start)
        step_start = time.perf_counter()
        from .services.storage import StorageBootstrapService
        from .services.storage.layout import database_path

        _update_startup_stage(app, splash, StartupStage.INITIALIZING_LOGGING)
        step_start = time.perf_counter()
        log_path = setup_logging(paths)
        lifetime.add_cleanup("logging", shutdown_logging)
        observability = setup_observability(paths)
        lifetime.add_cleanup("observability", flush_observability)
        startup_scope = start_span("app.startup")
        startup_scope.__enter__()
        startup_span_active = True
        install_exception_hooks()
        LOGGER.info(
            "Observability initialized",
            extra={
                "event_name": "app.observability.initialized",
                "otlp_enabled": observability.otlp_enabled,
                "otlp_trace_export_enabled": observability.trace_export_enabled,
                "otlp_metric_export_enabled": observability.metric_export_enabled,
                "otlp_log_export_enabled": observability.log_export_enabled,
            },
        )
        _emit_startup_timing("logging_observability.initialize", step_start)

        if splash is not None:
            step_start = time.perf_counter()
            splash.retranslate_ui()
            _emit_startup_timing("splash.retranslate", step_start)

        _update_startup_stage(app, splash, StartupStage.INITIALIZING_STORAGE)
        try:
            step_start = time.perf_counter()
            with start_span("storage.bootstrap"):
                context = StorageBootstrapService().initialize(paths)
                lifetime.add_cleanup("database", context.engine.dispose)
                record_counter(
                    "xenix.storage.bootstrap.count",
                    attributes={
                        "storage.schema_version": context.schema_version,
                        "status": "succeeded",
                    },
                )
            _emit_startup_timing("storage.bootstrap", step_start)
        except StorageBootstrapError as exc:
            record_counter(
                "xenix.storage.bootstrap.count",
                attributes={"status": "failed", "error.type": exc.__class__.__name__},
            )
            if not show or not database_path(paths).exists():
                raise
            _close_startup_splash(app, splash)
            splash = None
            context = _recover_storage_bootstrap(
                app=app,
                paths=paths,
                initial_error=exc,
            )
            lifetime.add_cleanup("database", context.engine.dispose)

        runtime_shutdown_connected = False

        def shutdown_runtime() -> None:
            nonlocal runtime_shutdown_connected
            if runtime_shutdown_connected:
                app.aboutToQuit.disconnect(shutdown_runtime)
                runtime_shutdown_connected = False
            lifetime.close()

        _update_startup_stage(app, splash, StartupStage.LOADING_WORKBENCH)
        step_start = time.perf_counter()
        from .application_composition import build_workbench_window

        window = build_workbench_window(
            paths=paths,
            context=context,
            translation_manager=translation_manager,
            log_path=log_path,
            lifetime=lifetime,
            on_services_ready=on_services_ready,
        )
        _emit_startup_timing("workbench.construct", step_start)
        app.aboutToQuit.connect(shutdown_runtime)
        runtime_shutdown_connected = True
        window.closing.connect(shutdown_runtime)

        _update_startup_stage(app, splash, StartupStage.READY)
        _hold_startup_splash(app, splash, splash_hold_ms)
        _close_startup_splash(app, splash)
        if show:
            step_start = time.perf_counter()
            window.show()
            app.processEvents()
            _emit_startup_timing("window.show", step_start)

        LOGGER.info("Xenix native shell started")
        record_counter("xenix.app.startup.count", attributes={"status": "succeeded"})
        startup_scope.__exit__(None, None, None)
        startup_span_active = False
        if flush_startup_observability:
            flush_observability()
        _emit_startup_timing("build_main_window.total", build_start)
        return app, window
    except Exception:
        record_counter("xenix.app.startup.count", attributes={"status": "failed"})
        if startup_span_active and startup_scope is not None:
            startup_scope.__exit__(*sys.exc_info())
            startup_span_active = False
        lifetime.close()
        _close_startup_splash(app, splash)
        raise


def run(*, smoke_test: bool = False) -> int:
    try:
        app, window = build_main_window(
            show=not smoke_test,
            show_splash=not smoke_test,
            splash_hold_ms=0 if smoke_test else STARTUP_SPLASH_HOLD_MS,
            flush_startup_observability=smoke_test,
        )
    except TrialLockStartupExit:
        return 1
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
            run_smoke_checks(ensure_app_dirs(get_app_paths()))
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
