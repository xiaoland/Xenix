"""Background commands for the removable AMD guided setup surface.

The task runner deliberately accepts only explicit user commands.  It does not
poll, reconnect, or reconcile an installation outside an Install, Repair, or
Remove request.  Results carry redacted lifecycle projections rather than
transport details or exception text, so they remain safe to render in the UI.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from shiboken6 import isValid

from ..services.amd.composition import AmdComposition
from ..services.amd.deployment import (
    AmdDeploymentError,
    AmdInstallationSpec,
    AmdPrivateTargetSpec,
)
from ..services.amd.ssh_security import AmdSshSecurityError, parse_pinned_host_key


_SAFE_CODE_PATTERN = re.compile(r"[a-z0-9_]{1,128}")
_RETIRE_INSTALLATION_APPEAR_RETRY_SECONDS = 0.1


class AmdGuidedPlacement(StrEnum):
    """The two product-owned targets offered by the guided setup."""

    LOCAL_LINUX = "local_linux"
    PRIVATE_SSH = "private_ssh"


class AmdGuidedOperation(StrEnum):
    """Explicit forward-only commands exposed by the guided setup."""

    INSTALL = "install"
    REPAIR = "repair"
    REMOVE = "remove"


@dataclass(frozen=True, slots=True)
class AmdGuidedInstallRequest:
    """One user-authored install request.

    Private SSH input remains intentionally absent from ``repr``.  The UI owns
    collection of that input; this value passes it straight to AMD-owned
    enrollment APIs and never logs or displays it.
    """

    installation_id: str
    placement: AmdGuidedPlacement
    target_id: str | None = field(repr=False)
    host: str | None = field(repr=False)
    user: str | None = field(repr=False)
    port: int | None = field(repr=False)
    identity_file: Path | None = field(repr=False)
    pinned_host_key: str | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class AmdGuidedTaskResult:
    """A render-safe operation result with no endpoint or exception message."""

    operation: AmdGuidedOperation
    installation_id: str
    succeeded: bool
    condition: str
    phase: str
    error_code: str | None


@dataclass(frozen=True, slots=True)
class _AmdGuidedCommand:
    operation: AmdGuidedOperation
    installation_id: str
    install_request: AmdGuidedInstallRequest | None = field(default=None, repr=False)


class _AmdGuidedTaskError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class AmdDeploymentTaskRunner(QObject):
    """Run one forward AMD command plus an independent retirement request.

    Retirement is a short desired-state control request, so it must be able to
    run while an install or repair worker is still active.  ``shutdown``
    prevents delivery of either eventual result; it intentionally does not
    pretend to cancel work that has already crossed the service boundary.
    """

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

    def start_install(self, request: AmdGuidedInstallRequest) -> bool:
        return self._start(
            _AmdGuidedCommand(
                operation=AmdGuidedOperation.INSTALL,
                installation_id=request.installation_id,
                install_request=request,
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
        threading.Thread(
            target=self._run_retirement_request,
            args=(installation_id,),
            name="xenix-amd-remove-request",
            daemon=True,
        ).start()
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
        threading.Thread(
            target=self._run,
            args=(command,),
            name=f"xenix-amd-{command.operation.value}",
            daemon=True,
        ).start()
        return True

    def _run(self, command: _AmdGuidedCommand) -> None:
        try:
            result = self._execute(command)
        except Exception as exc:
            result = AmdGuidedTaskResult(
                operation=command.operation,
                installation_id=command.installation_id,
                succeeded=False,
                condition="failed",
                phase="failed",
                error_code=_error_code_for(exc),
            )
        with self._lock:
            self._active = False
            self._active_command = None
            completion = self._install_completion.pop(command.installation_id, None)
            if command.operation is AmdGuidedOperation.INSTALL and completion is not None:
                completion.set()
            should_deliver = not self._closed
        if should_deliver and isValid(self):
            self.finished.emit(result)

    def _run_retirement_request(self, installation_id: str) -> None:
        try:
            request = self._request_retirement_when_installation_exists(installation_id)
            result = _project_retirement_request(installation_id, request)
        except Exception as exc:
            result = AmdGuidedTaskResult(
                operation=AmdGuidedOperation.REMOVE,
                installation_id=installation_id,
                succeeded=False,
                condition="failed",
                phase="failed",
                error_code=_error_code_for(exc),
            )
        with self._lock:
            self._retirement_active = False
            should_deliver = not self._closed
        if should_deliver and isValid(self):
            self.retirement_finished.emit(result)

    def _request_retirement_when_installation_exists(self, installation_id: str):
        """Bridge only the tiny UI race before a newly accepted install is stored.

        ``prepare`` persists the installation before it enters target I/O, but
        the background worker may still be recording its local SSH enrollment
        when a user immediately presses Remove.  Retrying that local absence is
        not a target retry and never invents a durable intent; as soon as the
        row exists, the service performs the authoritative retirement commit.
        """

        while True:
            try:
                return self._composition.deployment.request_retirement(installation_id)
            except AmdDeploymentError as exc:
                if exc.error_code != "amd_installation_not_found":
                    raise
                completion = self._pending_install_completion(installation_id)
                if completion is None:
                    raise
                # The pending intent belongs to this UI command, not to the
                # target.  It survives arbitrary SSH-enrollment duration and
                # becomes a single authoritative service request as soon as
                # ``prepare`` commits the installation row.  If installation
                # fails before that point, the final retry honestly reports
                # that no durable deployment existed to retire.
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
            request = command.install_request
            if request is None:
                raise _AmdGuidedTaskError("amd_request_invalid")
            status = _install(self._composition, request)
        elif command.operation is AmdGuidedOperation.REPAIR:
            status = self._composition.deployment.repair(command.installation_id)
        else:
            raise _AmdGuidedTaskError("amd_request_invalid")
        return _project_status(command.operation, command.installation_id, status)


def _install(composition: AmdComposition, request: AmdGuidedInstallRequest):
    target_id: str | None = None
    if request.placement is AmdGuidedPlacement.PRIVATE_SSH:
        target_id = _enroll_private_target(composition, request)
    elif request.placement is not AmdGuidedPlacement.LOCAL_LINUX:
        raise _AmdGuidedTaskError("amd_request_invalid")

    profile = _single_profile(composition)
    return composition.deployment.prepare(
        AmdInstallationSpec(
            installation_id=request.installation_id,
            placement=request.placement.value,
            profile_digest=profile.manifest_digest,
            target_id=target_id,
        )
    )


def _single_profile(composition: AmdComposition):
    profiles = composition.catalog.profiles
    if len(profiles) != 1:
        raise _AmdGuidedTaskError("amd_profile_catalog_invalid")
    return profiles[0]


def _enroll_private_target(
    composition: AmdComposition,
    request: AmdGuidedInstallRequest,
) -> str:
    if (
        request.target_id is None
        or request.host is None
        or request.user is None
        or request.port is None
        or request.identity_file is None
        or request.pinned_host_key is None
    ):
        raise _AmdGuidedTaskError("amd_request_invalid")

    host_key = parse_pinned_host_key(request.pinned_host_key)
    identity_file_reference, pinned_host_key_reference = composition.ssh_security.record(
        target_id=request.target_id,
        identity_file=request.identity_file,
        host_key=host_key,
    )
    composition.deployment.enroll_private_target(
        AmdPrivateTargetSpec(
            target_id=request.target_id,
            host=request.host,
            user=request.user,
            port=request.port,
            pinned_host_key=pinned_host_key_reference,
            identity_file_reference=identity_file_reference,
        )
    )
    return request.target_id


def _project_status(
    operation: AmdGuidedOperation,
    installation_id: str,
    status: object,
) -> AmdGuidedTaskResult:
    components = tuple(getattr(status, "components", ()))
    failed_component = next(
        (component for component in components if getattr(component, "error_code", None)),
        None,
    )
    active_component = failed_component or next(
        (component for component in components if getattr(component, "phase", None) != "registered"),
        None,
    )
    if active_component is None and components:
        active_component = components[0]

    component_error = (
        getattr(active_component, "error_code", None) if active_component is not None else None
    )
    compatibility_issues = tuple(getattr(status, "compatibility_issues", ()))
    error_code = _safe_code(component_error)
    if error_code is None:
        error_code = next((_safe_code(issue) for issue in compatibility_issues if _safe_code(issue)), None)

    condition_value = getattr(getattr(status, "condition", None), "value", None)
    phase_value = getattr(active_component, "phase", None) if active_component is not None else None
    return AmdGuidedTaskResult(
        operation=operation,
        installation_id=installation_id,
        succeeded=True,
        condition=_safe_code(condition_value, fallback="unknown"),
        phase=_safe_code(phase_value, fallback="unknown"),
        error_code=error_code,
    )


def _project_retirement_request(
    installation_id: str,
    request: object,
) -> AmdGuidedTaskResult:
    """Project only the service's bounded retirement-request acknowledgement."""

    request_installation_id = getattr(request, "installation_id", None)
    if request_installation_id != installation_id:
        raise _AmdGuidedTaskError("amd_request_invalid")
    return AmdGuidedTaskResult(
        operation=AmdGuidedOperation.REMOVE,
        installation_id=installation_id,
        succeeded=True,
        condition="retiring",
        phase=_safe_code(getattr(request, "phase", None), fallback="retirement_requested"),
        error_code=None,
    )


def _error_code_for(exc: Exception) -> str:
    if isinstance(exc, _AmdGuidedTaskError):
        return _safe_code(exc.error_code, fallback="amd_operation_failed")
    if isinstance(exc, AmdDeploymentError):
        return _safe_code(exc.error_code, fallback="amd_operation_failed")
    if isinstance(exc, AmdSshSecurityError):
        return "amd_ssh_security_invalid"
    if isinstance(exc, (TypeError, ValueError)):
        return "amd_request_invalid"
    return "amd_operation_failed"


def _safe_code(value: object, *, fallback: str | None = None) -> str | None:
    if isinstance(value, str) and _SAFE_CODE_PATTERN.fullmatch(value):
        return value
    return fallback


__all__ = [
    "AmdDeploymentTaskRunner",
    "AmdGuidedInstallRequest",
    "AmdGuidedOperation",
    "AmdGuidedPlacement",
    "AmdGuidedTaskResult",
]
