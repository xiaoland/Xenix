"""Background commands for the removable AMD guided setup surface.

The runner schedules only explicit user commands.  Cross-authority enrollment
belongs to the AMD guided service, while this Qt boundary projects redacted
results and emits structured diagnostics that contain no endpoint, credential,
path, host key, SSH output, or exception message.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from enum import StrEnum

from PySide6.QtCore import QObject, Signal
from shiboken6 import isValid

from ..services.amd.composition import AmdComposition
from ..services.amd.deployment import AmdDeploymentError
from ..services.amd.guided import (
    AmdGuidedDeploymentError,
    AmdGuidedInputField,
    AmdGuidedPrivateInstallation,
    AmdGuidedRetirementInstallation,
    AmdPrivateSshInstallCommand,
)
from ..services.amd.ssh_security import AmdSshSecurityError


LOGGER = logging.getLogger(__name__)
_SAFE_CODE_PATTERN = re.compile(r"[a-z0-9_]{1,128}")
_RETIRE_INSTALLATION_APPEAR_RETRY_SECONDS = 0.1


class AmdGuidedOperation(StrEnum):
    """Explicit forward-only commands exposed by the guided setup."""

    INSTALL = "install"
    REPAIR = "repair"
    REMOVE = "remove"


@dataclass(frozen=True, slots=True)
class AmdGuidedTaskResult:
    """A render-safe operation result with no endpoint or exception message."""

    operation: AmdGuidedOperation
    installation_id: str
    succeeded: bool
    installation_available: bool | None
    condition: str
    phase: str
    error_code: str | None
    input_field: AmdGuidedInputField | None = None
    security_enrolled: bool = False


@dataclass(frozen=True, slots=True)
class _AmdGuidedCommand:
    operation: AmdGuidedOperation
    installation_id: str
    install_command: AmdPrivateSshInstallCommand | None = field(
        default=None,
        repr=False,
    )


class _AmdGuidedTaskError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class AmdDeploymentTaskRunner(QObject):
    """Run one forward AMD command plus an independent retirement request."""

    finished = Signal(object)
    retirement_finished = Signal(object)

    def __init__(self, composition: AmdComposition, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._composition = composition
        self._lock = threading.Lock()
        self._active = False
        self._active_command: _AmdGuidedCommand | None = None
        self._install_completion: dict[str, threading.Event] = {}
        self._retirement_active = False
        self._closed = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def validate_install(self, command: AmdPrivateSshInstallCommand) -> None:
        """Run pure field validation synchronously before scheduling."""

        with self._lock:
            if self._closed:
                raise AmdGuidedDeploymentError("amd_deployment_closed")
        self._composition.guided.validate_private_fields(command)

    def private_inventory(
        self,
    ) -> tuple[
        tuple[AmdGuidedPrivateInstallation, AmdGuidedTaskResult],
        ...,
    ]:
        """Restore all durable Private identities without target/filesystem I/O."""

        with self._lock:
            if self._closed:
                raise AmdGuidedDeploymentError("amd_deployment_closed")
        try:
            restored_inventory = self._composition.guided.private_inventory()
        except Exception as exc:
            _log_inventory_exception(exc)
            raise
        projected = tuple(
            (
                restored,
                _project_inventory_installation(
                    restored.installation_id,
                    restored.status,
                    desired_presence=restored.desired_presence,
                    lifecycle_state=restored.lifecycle_state,
                    inventory_error_code=restored.inventory_error_code,
                    security_enrolled=restored.security_enrolled,
                ),
            )
            for restored in restored_inventory
        )
        for restored, result in projected:
            _log_inventory_projection(
                result,
                secondary_error_code=restored.inventory_error_code,
            )
        return projected

    def retirement_inventory(
        self,
    ) -> tuple[
        tuple[AmdGuidedRetirementInstallation, AmdGuidedTaskResult],
        ...,
    ]:
        """Restore every actionable identity for a retirement-only build."""

        with self._lock:
            if self._closed:
                raise AmdGuidedDeploymentError("amd_deployment_closed")
        try:
            restored_inventory = self._composition.guided.retirement_inventory()
        except Exception as exc:
            _log_inventory_exception(exc)
            raise
        projected = tuple(
            (
                restored,
                _project_inventory_installation(
                    restored.installation_id,
                    restored.status,
                    desired_presence=restored.desired_presence,
                    lifecycle_state=restored.lifecycle_state,
                    inventory_error_code=restored.inventory_error_code,
                    security_enrolled=False,
                ),
            )
            for restored in restored_inventory
        )
        for restored, result in projected:
            _log_inventory_projection(
                result,
                secondary_error_code=restored.inventory_error_code,
            )
        return projected

    def start_install(self, command: AmdPrivateSshInstallCommand) -> bool:
        return self._start(
            _AmdGuidedCommand(
                operation=AmdGuidedOperation.INSTALL,
                installation_id=command.installation_id,
                install_command=command,
            )
        )

    def start_repair(self, installation_id: str) -> bool:
        return self._start(
            _AmdGuidedCommand(
                operation=AmdGuidedOperation.REPAIR,
                installation_id=installation_id,
            )
        )

    def start_remove(self, installation_id: str) -> bool:
        with self._lock:
            if self._closed or self._retirement_active:
                return False
            self._retirement_active = True
        worker = threading.Thread(
            target=self._run_retirement_request,
            args=(installation_id,),
            name="xenix-amd-remove-request",
            daemon=True,
        )
        try:
            worker.start()
        except RuntimeError:
            with self._lock:
                self._retirement_active = False
            LOGGER.error(
                "AMD guided worker is unavailable",
                extra={
                    "event_name": "amd.guided.worker_unavailable",
                    "operation": AmdGuidedOperation.REMOVE.value,
                },
            )
            return False
        LOGGER.info(
            "AMD guided operation started",
            extra={
                "event_name": "amd.guided.operation.started",
                "operation": AmdGuidedOperation.REMOVE.value,
            },
        )
        return True

    def shutdown(self) -> None:
        """Suppress completion delivery without claiming to cancel remote work."""

        with self._lock:
            self._closed = True

    def _start(self, command: _AmdGuidedCommand) -> bool:
        with self._lock:
            if self._closed or self._active:
                return False
            self._active = True
            self._active_command = command
            if command.operation is AmdGuidedOperation.INSTALL:
                self._install_completion[command.installation_id] = threading.Event()
        worker = threading.Thread(
            target=self._run,
            args=(command,),
            name=f"xenix-amd-{command.operation.value}",
            daemon=True,
        )
        try:
            worker.start()
        except RuntimeError:
            with self._lock:
                self._active = False
                self._active_command = None
                completion = self._install_completion.pop(command.installation_id, None)
                if completion is not None:
                    completion.set()
            LOGGER.error(
                "AMD guided worker is unavailable",
                extra={
                    "event_name": "amd.guided.worker_unavailable",
                    "operation": command.operation.value,
                },
            )
            return False
        LOGGER.info(
            "AMD guided operation started",
            extra={
                "event_name": "amd.guided.operation.started",
                "operation": command.operation.value,
            },
        )
        return True

    def _run(self, command: _AmdGuidedCommand) -> None:
        try:
            result = self._execute(command)
        except Exception as exc:
            result = AmdGuidedTaskResult(
                operation=command.operation,
                installation_id=command.installation_id,
                succeeded=False,
                installation_available=_installation_available(
                    self._composition,
                    command.installation_id,
                ),
                condition="failed",
                phase="failed",
                error_code=_error_code_for(exc),
                input_field=_input_field_for(exc),
                security_enrolled=_security_enrolled(
                    self._composition,
                    command.installation_id,
                ),
            )
            LOGGER.warning(
                "AMD guided operation raised",
                extra={
                    "event_name": "amd.guided.operation.raised",
                    "operation": command.operation.value,
                    "error_code": result.error_code,
                    "exception_type": type(exc).__name__,
                },
            )
        with self._lock:
            self._active = False
            self._active_command = None
            completion = self._install_completion.pop(command.installation_id, None)
            if command.operation is AmdGuidedOperation.INSTALL and completion is not None:
                completion.set()
            should_deliver = not self._closed
        _log_result(result)
        if should_deliver and isValid(self):
            self.finished.emit(result)

    def _run_retirement_request(self, installation_id: str) -> None:
        try:
            request = self._request_retirement_when_installation_exists(installation_id)
            if getattr(request, "phase", None) == "already_removed":
                result = _project_retirement_request(installation_id, request)
            else:
                status = self._composition.deployment.retire(
                    installation_id,
                    drain_timeout_seconds=None,
                )
                result = _project_retirement_status(installation_id, status)
        except Exception as exc:
            result = AmdGuidedTaskResult(
                operation=AmdGuidedOperation.REMOVE,
                installation_id=installation_id,
                succeeded=False,
                installation_available=_installation_available(
                    self._composition,
                    installation_id,
                ),
                condition="failed",
                phase="failed",
                error_code=_error_code_for(exc),
                input_field=_input_field_for(exc),
                security_enrolled=_security_enrolled(
                    self._composition,
                    installation_id,
                ),
            )
            LOGGER.warning(
                "AMD guided operation raised",
                extra={
                    "event_name": "amd.guided.operation.raised",
                    "operation": AmdGuidedOperation.REMOVE.value,
                    "error_code": result.error_code,
                    "exception_type": type(exc).__name__,
                },
            )
        with self._lock:
            self._retirement_active = False
            should_deliver = not self._closed
        _log_result(result)
        if should_deliver and isValid(self):
            self.retirement_finished.emit(result)

    def _request_retirement_when_installation_exists(self, installation_id: str):
        """Bridge only the local race before a newly accepted install is stored."""

        while True:
            try:
                return self._composition.deployment.request_retirement(installation_id)
            except AmdDeploymentError as exc:
                if exc.error_code != "amd_installation_not_found":
                    raise
                completion = self._pending_install_completion(installation_id)
                if completion is None:
                    raise
                completion.wait(_RETIRE_INSTALLATION_APPEAR_RETRY_SECONDS)
                if completion.is_set():
                    return self._composition.deployment.request_retirement(installation_id)

    def _pending_install_completion(self, installation_id: str) -> threading.Event | None:
        with self._lock:
            command = self._active_command
            if (
                not self._closed
                and self._active
                and command is not None
                and command.operation is AmdGuidedOperation.INSTALL
                and command.installation_id == installation_id
            ):
                return self._install_completion.get(installation_id)
            return None

    def _execute(self, command: _AmdGuidedCommand) -> AmdGuidedTaskResult:
        if command.operation is AmdGuidedOperation.INSTALL:
            request = command.install_command
            if request is None:
                raise _AmdGuidedTaskError("amd_request_invalid")
            status = self._composition.guided.install_private(request)
        elif command.operation is AmdGuidedOperation.REPAIR:
            status = self._composition.deployment.repair(command.installation_id)
        else:
            raise _AmdGuidedTaskError("amd_request_invalid")
        return _project_status(
            command.operation,
            command.installation_id,
            status,
            security_enrolled=_security_enrolled(
                self._composition,
                command.installation_id,
            ),
        )


def _project_inventory_installation(
    installation_id: str,
    status: object | None,
    *,
    desired_presence: bool,
    lifecycle_state: str,
    inventory_error_code: str | None,
    security_enrolled: bool,
) -> AmdGuidedTaskResult:
    if status is None:
        if not desired_presence or lifecycle_state in {"retiring", "removed"}:
            removed = lifecycle_state == "removed"
            return AmdGuidedTaskResult(
                operation=AmdGuidedOperation.REMOVE,
                installation_id=installation_id,
                succeeded=removed,
                installation_available=not removed,
                condition="removed" if removed else "retiring",
                phase="inventory",
                error_code=(
                    None
                    if removed
                    else _safe_code(
                        inventory_error_code,
                        fallback="amd_status_unavailable",
                    )
                ),
                security_enrolled=security_enrolled,
            )
        return AmdGuidedTaskResult(
            operation=AmdGuidedOperation.REPAIR,
            installation_id=installation_id,
            succeeded=False,
            installation_available=True,
            condition="needs_attention",
            phase="inventory",
            error_code=_safe_code(
                inventory_error_code,
                fallback="amd_status_unavailable",
            ),
            security_enrolled=security_enrolled,
        )
    condition = getattr(getattr(status, "condition", None), "value", None)
    if condition in {"retiring", "removal_blocked", "removed"}:
        result = _project_retirement_status(
            installation_id,
            status,
            security_enrolled=security_enrolled,
        )
    else:
        result = _project_status(
            AmdGuidedOperation.REPAIR,
            installation_id,
            status,
            security_enrolled=security_enrolled,
        )
    if (
        inventory_error_code is None
        or result.condition in {"retiring", "removal_blocked", "removed"}
    ):
        return result
    return AmdGuidedTaskResult(
        operation=result.operation,
        installation_id=result.installation_id,
        succeeded=False,
        installation_available=result.installation_available,
        condition="needs_attention",
        phase="inventory",
        error_code=_safe_code(
            inventory_error_code,
            fallback="amd_status_unavailable",
        ),
        security_enrolled=security_enrolled,
    )


def _project_status(
    operation: AmdGuidedOperation,
    installation_id: str,
    status: object,
    *,
    security_enrolled: bool = False,
) -> AmdGuidedTaskResult:
    if getattr(status, "installation_id", None) != installation_id:
        raise _AmdGuidedTaskError("amd_status_invalid")

    components = tuple(getattr(status, "components", ()))
    failed_component = next(
        (component for component in components if getattr(component, "error_code", None)),
        None,
    )
    active_component = failed_component or next(
        (
            component
            for component in components
            if getattr(component, "phase", None) != "registered"
        ),
        None,
    )
    if active_component is None and components:
        active_component = components[0]

    target_observation_error = _safe_code(
        getattr(status, "target_observation_error_code", None)
    )
    component_error = (
        getattr(active_component, "error_code", None)
        if active_component is not None
        else None
    )
    compatibility_issues = tuple(getattr(status, "compatibility_issues", ()))
    error_code = target_observation_error or _safe_code(component_error)
    if error_code is None:
        error_code = next(
            (
                safe_issue
                for issue in compatibility_issues
                if (safe_issue := _safe_code(issue)) is not None
            ),
            None,
        )

    condition = _safe_code(
        getattr(getattr(status, "condition", None), "value", None),
        fallback="unknown",
    )
    phase = _safe_code(
        getattr(active_component, "phase", None)
        if active_component is not None
        else None,
        fallback="unknown",
    )
    succeeded = condition == "operational" and bool(
        getattr(status, "profile_usable", False)
    )
    if not succeeded and error_code is None:
        error_code = {
            "incompatible": "amd_compatibility_failed",
            "degraded": "amd_deployment_degraded",
            "installing": "amd_deployment_incomplete",
            "not_materialized": "amd_not_materialized",
            "retiring": "amd_installation_retiring",
            "removal_blocked": "amd_removal_blocked",
        }.get(condition, "amd_operation_failed")

    return AmdGuidedTaskResult(
        operation=operation,
        installation_id=installation_id,
        succeeded=succeeded,
        installation_available=True,
        condition=condition,
        phase=phase,
        error_code=None if succeeded else error_code,
        security_enrolled=security_enrolled,
    )


def _project_retirement_request(
    installation_id: str,
    request: object,
) -> AmdGuidedTaskResult:
    """Project only the service's bounded retirement-request acknowledgement."""

    request_installation_id = getattr(request, "installation_id", None)
    if request_installation_id != installation_id:
        raise _AmdGuidedTaskError("amd_request_invalid")
    phase = _safe_code(
        getattr(request, "phase", None),
        fallback="retirement_requested",
    )
    already_removed = phase == "already_removed"
    return AmdGuidedTaskResult(
        operation=AmdGuidedOperation.REMOVE,
        installation_id=installation_id,
        succeeded=True,
        installation_available=not already_removed,
        condition="removed" if already_removed else "retiring",
        phase=phase,
        error_code=None,
    )


def _project_retirement_status(
    installation_id: str,
    status: object,
    *,
    security_enrolled: bool = False,
) -> AmdGuidedTaskResult:
    if getattr(status, "installation_id", None) != installation_id:
        raise _AmdGuidedTaskError("amd_status_invalid")
    condition = _safe_code(
        getattr(getattr(status, "condition", None), "value", None),
        fallback="unknown",
    )
    components = tuple(getattr(status, "components", ()))
    active_component = next(
        (
            component
            for component in components
            if getattr(component, "lifecycle_state", None) != "removed"
        ),
        components[0] if components else None,
    )
    phase = _safe_code(
        getattr(active_component, "phase", None)
        if active_component is not None
        else condition,
        fallback=condition,
    )
    component_error = _safe_code(
        getattr(active_component, "error_code", None)
        if active_component is not None
        else None,
    )
    succeeded = condition in {"retiring", "removed"}
    error_code = None
    if condition == "removal_blocked":
        error_code = component_error or "amd_removal_blocked"
    elif not succeeded:
        error_code = "amd_operation_failed"
    return AmdGuidedTaskResult(
        operation=AmdGuidedOperation.REMOVE,
        installation_id=installation_id,
        succeeded=succeeded,
        installation_available=condition != "removed",
        condition=condition,
        phase=phase,
        error_code=error_code,
        security_enrolled=security_enrolled,
    )


def _installation_available(
    composition: AmdComposition,
    installation_id: str,
) -> bool | None:
    try:
        exists = composition.deployment.has_installation(installation_id)
    except Exception:
        return None
    if not exists:
        return False
    try:
        status = composition.deployment.status(installation_id)
        return getattr(status, "lifecycle_state", None) != "removed"
    except Exception:
        # Durable existence was already proven.  A status read failure must not
        # erase the identity or turn unknown into "safe to create another".
        return True


def _security_enrolled(
    composition: AmdComposition,
    installation_id: str,
) -> bool:
    try:
        return composition.guided.security_enrolled(installation_id)
    except Exception:
        return False


def _error_code_for(exc: Exception) -> str:
    if isinstance(exc, (_AmdGuidedTaskError, AmdGuidedDeploymentError)):
        return _safe_code(exc.error_code, fallback="amd_operation_failed")
    if isinstance(exc, AmdDeploymentError):
        return _safe_code(exc.error_code, fallback="amd_operation_failed")
    if isinstance(exc, AmdSshSecurityError):
        return _safe_code(exc.error_code, fallback="amd_ssh_security_invalid")
    if isinstance(exc, (TypeError, ValueError)):
        return "amd_request_invalid"
    return "amd_operation_failed"


def _input_field_for(exc: Exception) -> AmdGuidedInputField | None:
    if isinstance(exc, AmdGuidedDeploymentError):
        return exc.field
    return None


def _log_result(result: AmdGuidedTaskResult) -> None:
    log = LOGGER.info if result.succeeded else LOGGER.warning
    log(
        "AMD guided operation completed",
        extra={
            "event_name": "amd.guided.operation.completed",
            "operation": result.operation.value,
            "succeeded": result.succeeded,
            "installation_available": result.installation_available,
            "condition": result.condition,
            "phase": result.phase,
            "error_code": result.error_code or "none",
            "input_field": (
                result.input_field.value
                if result.input_field is not None
                else "none"
            ),
            "security_enrolled": result.security_enrolled,
        },
    )


def _log_inventory_projection(
    result: AmdGuidedTaskResult,
    *,
    secondary_error_code: str | None,
) -> None:
    safe_secondary_error = _safe_code(secondary_error_code)
    if result.error_code is None and safe_secondary_error is None:
        return
    LOGGER.warning(
        "AMD guided inventory item needs attention",
        extra={
            "event_name": "amd.guided.inventory.item",
            "condition": result.condition,
            "phase": result.phase,
            "error_code": result.error_code or "none",
            "secondary_error_code": safe_secondary_error or "none",
            "security_enrolled": result.security_enrolled,
        },
    )


def _log_inventory_exception(exc: Exception) -> None:
    LOGGER.warning(
        "AMD guided inventory read raised",
        extra={
            "event_name": "amd.guided.inventory.raised",
            "error_code": _error_code_for(exc),
            "exception_type": type(exc).__name__,
        },
    )


def _safe_code(value: object, *, fallback: str | None = None) -> str | None:
    if isinstance(value, str) and _SAFE_CODE_PATTERN.fullmatch(value):
        return value
    return fallback


__all__ = [
    "AmdDeploymentTaskRunner",
    "AmdGuidedDeploymentError",
    "AmdGuidedInputField",
    "AmdGuidedOperation",
    "AmdGuidedPrivateInstallation",
    "AmdGuidedRetirementInstallation",
    "AmdGuidedTaskResult",
    "AmdPrivateSshInstallCommand",
]
