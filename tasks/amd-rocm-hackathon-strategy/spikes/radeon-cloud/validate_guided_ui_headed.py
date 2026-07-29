"""Headed acceptance helper for the AMD guided Private SSH workflow.

This is intentionally not a pytest.  It opens the production Qt dialog, drives
the real guided command boundary against an isolated Xenix runtime home, and
records only redacted evidence.  A synthetic, algorithm-valid server host key
ensures that a newly reachable target stops at strict host-key verification
rather than mutating the remote machine.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import struct
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from PySide6.QtCore import QObject
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)
from sqlmodel import Session, select

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.amd.composition import build_amd_composition
from xenix.services.embedding_service import (
    create_builtin_embedding_provider_factory_registry,
)
from xenix.services.embedding_settings import EmbeddingSettingsService
from xenix.services.llm.provider_factory import (
    create_builtin_llm_provider_factory_registry,
)
from xenix.services.llm.settings import LLMSettingsService
from xenix.services.ocr.settings import OcrProviderFactoryRegistry, OcrSettingsService
from xenix.services.settings_store import SettingsStore
from xenix.services.storage.database import (
    create_engine_for_path,
    create_session_factory,
)
from xenix.services.storage.migrations import bootstrap_current_schema
from xenix.services.storage.models import AmdInstallationRow, AmdTargetEnrollmentRow
from xenix.ui.amd_deployment_tasks import AmdGuidedTaskResult
from xenix.ui.amd_setup import AmdGuidedSetupDialog

_EXPECTED_SAFE_FAILURES = frozenset(
    {
        "amd_ssh_authentication_failed",
        "amd_ssh_client_unavailable",
        "amd_ssh_connection_failed",
        "amd_ssh_connection_timeout",
        "amd_ssh_host_trust_failed",
        "amd_ssh_target_unavailable",
    }
)
_QtChild = TypeVar("_QtChild", bound=QObject)
_SAFE_LOG_FIELDS = (
    "event_name",
    "operation",
    "succeeded",
    "installation_available",
    "condition",
    "phase",
    "error_code",
    "secondary_error_code",
    "exception_type",
    "input_field",
    "security_enrolled",
)


class _SafeEvidenceFormatter(logging.Formatter):
    """Serialize only the AMD task boundary's approved diagnostic fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname.casefold(),
            "message": record.getMessage(),
            **{
                name: getattr(record, name)
                for name in _SAFE_LOG_FIELDS
                if hasattr(record, name)
            },
        }
        return json.dumps(payload, sort_keys=True)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--user", required=True)
    parser.add_argument("--identity-file", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    return parser.parse_args()


def _synthetic_ed25519_host_key() -> str:
    algorithm = b"ssh-ed25519"
    public_key = bytes(range(32))
    blob = (
        struct.pack(">I", len(algorithm))
        + algorithm
        + struct.pack(">I", len(public_key))
        + public_key
    )
    encoded = base64.b64encode(blob).decode("ascii")
    return f"ssh-ed25519 {encoded} headed-acceptance"


def _required_child(
    dialog: AmdGuidedSetupDialog,
    kind: type[_QtChild],
    name: str,
) -> _QtChild:
    child = dialog.findChild(kind, name)
    if child is None:
        raise RuntimeError(f"Required Qt child is unavailable: {name}")
    return child


def _row_counts(session_factory: Callable[[], Session]) -> tuple[int, int]:
    with session_factory() as session:
        targets = len(tuple(session.exec(select(AmdTargetEnrollmentRow))))
        installations = len(tuple(session.exec(select(AmdInstallationRow))))
    return targets, installations


def _save_dialog(dialog: AmdGuidedSetupDialog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not dialog.grab().save(str(path), "PNG"):
        raise RuntimeError("Qt could not save the headed acceptance screenshot.")


def _wait_for_result(
    app: QApplication,
    results: list[object],
    *,
    timeout_seconds: float,
) -> object:
    deadline = time.monotonic() + timeout_seconds
    while not results and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    if not results:
        raise TimeoutError("AMD guided headed acceptance timed out.")
    return results[-1]


def main() -> int:
    args = _arguments()
    evidence_root = args.evidence_root.resolve(strict=False)
    evidence_root.mkdir(parents=True, exist_ok=True)
    identity_file = args.identity_file.resolve(strict=True)
    paths = ensure_app_dirs(get_app_paths())

    log_path = evidence_root / "guided-ui-headed.jsonl"
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(_SafeEvidenceFormatter())
    task_logger = logging.getLogger("xenix.ui.amd_deployment_tasks")
    previous_level = task_logger.level
    previous_propagate = task_logger.propagate
    task_logger.setLevel(logging.INFO)
    task_logger.propagate = False
    task_logger.addHandler(handler)

    engine = create_engine_for_path(paths.state / "xenix.db")
    bootstrap_current_schema(engine)
    session_factory = create_session_factory(engine)
    settings_store = SettingsStore(paths.config)
    composition = None
    dialog = None
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)

    try:
        composition = build_amd_composition(
            session_factory=session_factory,
            settings_store=settings_store,
            llm_settings_service=LLMSettingsService(
                paths,
                settings_store=settings_store,
            ),
            embedding_settings_service=EmbeddingSettingsService(
                paths,
                settings_store=settings_store,
            ),
            ocr_settings_service=OcrSettingsService(store=settings_store),
            llm_provider_factory_registry=(
                create_builtin_llm_provider_factory_registry()
            ),
            embedding_provider_factory_registry=(
                create_builtin_embedding_provider_factory_registry()
            ),
            ocr_provider_factory_registry=OcrProviderFactoryRegistry(),
            local_cache_root=(paths.cache / "amd-runtime").resolve(strict=False),
            temporary_root=paths.temp.resolve(strict=False),
        )
        dialog = AmdGuidedSetupDialog(composition)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        app.processEvents()

        install_button = _required_child(dialog, QPushButton, "amdInstallButton")
        repair_button = _required_child(dialog, QPushButton, "amdRepairButton")
        remove_button = _required_child(dialog, QPushButton, "amdRemoveButton")
        host_input = _required_child(dialog, QLineEdit, "amdSshHostInput")
        user_input = _required_child(dialog, QLineEdit, "amdSshUserInput")
        port_input = _required_child(dialog, QSpinBox, "amdSshPortInput")
        identity_input = _required_child(dialog, QLineEdit, "amdSshIdentityInput")
        host_key_input = _required_child(dialog, QLineEdit, "amdSshHostKeyInput")
        condition_value = _required_child(dialog, QLabel, "amdConditionValue")
        phase_value = _required_child(dialog, QLabel, "amdPhaseValue")
        support_code_value = _required_child(dialog, QLabel, "amdSupportCodeValue")
        details_value = _required_child(dialog, QLabel, "amdDetailsValue")

        text_widgets = (
            *dialog.findChildren(QLabel),
            *dialog.findChildren(QAbstractButton),
        )
        visible_text = tuple(
            widget.text() for widget in text_widgets if widget.isVisible()
        )
        has_save_action = any(text.strip().casefold() == "save" for text in visible_text)
        has_local_linux = any("local linux" in text.casefold() for text in visible_text)
        if has_save_action or has_local_linux:
            raise AssertionError("The guided UI exposed an unsupported action or placement.")

        install_button.click()
        app.processEvents()
        blank_targets, blank_installations = _row_counts(session_factory)
        blank_settings_documents = len(tuple(paths.config.glob("*.json")))
        blank_code = support_code_value.text()
        blank_condition = condition_value.text()
        focused_object = (
            app.focusWidget().objectName() if app.focusWidget() is not None else ""
        )
        if (
            blank_code != "amd_ssh_host_required"
            or focused_object != "amdSshHostInput"
            or blank_targets != 0
            or blank_installations != 0
            or blank_settings_documents != 0
        ):
            raise AssertionError("Blank-form validation was not read-only and field-aware.")
        validation_screenshot = evidence_root / "guided-ui-validation.png"
        _save_dialog(dialog, validation_screenshot)

        host_input.setText(args.host)
        user_input.setText(args.user)
        port_input.setValue(args.port)
        identity_input.setText(str(identity_file))
        synthetic_host_key = _synthetic_ed25519_host_key()
        host_key_input.setText(synthetic_host_key)
        app.processEvents()

        results: list[object] = []
        dialog._task_runner.finished.connect(results.append)  # noqa: SLF001
        started_at = time.monotonic()
        install_button.click()
        result = _wait_for_result(
            app,
            results,
            timeout_seconds=args.timeout_seconds,
        )
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        if not isinstance(result, AmdGuidedTaskResult):
            raise AssertionError("The guided worker returned an invalid result object.")
        if result.error_code not in _EXPECTED_SAFE_FAILURES:
            raise AssertionError(
                "The real SSH attempt did not produce a stable typed failure."
            )
        if result.succeeded or not result.installation_available:
            raise AssertionError(
                "The failed SSH attempt did not preserve truthful installation state."
            )

        final_targets, final_installations = _row_counts(session_factory)
        if final_targets != 1 or final_installations != 1:
            raise AssertionError("The one guided command did not persist one exact intent.")
        if not details_value.text().strip() or support_code_value.text() != result.error_code:
            raise AssertionError("The guided UI did not render a safe human-readable failure.")
        repair_enabled = repair_button.isEnabled()
        remove_enabled = remove_button.isEnabled()
        if not repair_enabled or not remove_enabled:
            raise AssertionError("A preserved installation cannot be repaired or removed.")

        # Evidence screenshots must never persist endpoint or credential fields.
        host_input.setText("[redacted]")
        user_input.setText("[redacted]")
        port_input.setValue(1)
        identity_input.setText("[redacted]")
        host_key_input.setText("[redacted]")
        app.processEvents()
        result_screenshot = evidence_root / "guided-ui-result.png"
        _save_dialog(dialog, result_screenshot)

        dialog.shutdown()
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
        dialog = AmdGuidedSetupDialog(composition)
        dialog.show()
        app.processEvents()
        restarted_install_button = _required_child(
            dialog,
            QPushButton,
            "amdInstallButton",
        )
        restarted_repair_button = _required_child(
            dialog,
            QPushButton,
            "amdRepairButton",
        )
        restarted_remove_button = _required_child(
            dialog,
            QPushButton,
            "amdRemoveButton",
        )
        restart_recovery_passed = (
            not restarted_install_button.isEnabled()
            and restarted_repair_button.isEnabled()
            and restarted_remove_button.isEnabled()
        )
        if not restart_recovery_passed:
            raise AssertionError(
                "A new guided dialog did not recover the durable installation."
            )

        handler.flush()
        log_text = log_path.read_text(encoding="utf-8")
        prohibited = (
            args.host,
            args.user,
            str(args.port),
            str(identity_file),
            synthetic_host_key,
            "kex_exchange_identification",
            "connection reset by",
        )
        redaction_passed = not any(
            value.casefold() in log_text.casefold() for value in prohibited
        )
        if not redaction_passed:
            raise AssertionError("The guided task log exposed private connection material.")

        evidence = {
            "blank_validation": {
                "condition": blank_condition,
                "error_code": blank_code,
                "focused_object": focused_object,
                "settings_documents": blank_settings_documents,
                "sqlite_installations": blank_installations,
                "sqlite_targets": blank_targets,
            },
            "final_result": {
                "condition": result.condition,
                "elapsed_seconds": elapsed_seconds,
                "error_code": result.error_code,
                "installation_available": result.installation_available,
                "phase": result.phase,
                "repair_enabled": repair_enabled,
                "remove_enabled": remove_enabled,
                "succeeded": result.succeeded,
            },
            "redaction_passed": redaction_passed,
            "restart_recovery_passed": restart_recovery_passed,
            "topology": {
                "has_local_linux": has_local_linux,
                "has_save_action": has_save_action,
                "placement": "private_ssh",
            },
        }
        (evidence_root / "guided-ui-headed.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0
    finally:
        if dialog is not None:
            dialog.shutdown()
            dialog.close()
            dialog.deleteLater()
            app.processEvents()
        if composition is not None:
            composition.close()
        settings_store.close()
        engine.dispose()
        task_logger.removeHandler(handler)
        handler.close()
        task_logger.setLevel(previous_level)
        task_logger.propagate = previous_propagate


if __name__ == "__main__":
    raise SystemExit(main())
