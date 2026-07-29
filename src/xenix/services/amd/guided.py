"""One application command for the guided Private SSH AMD workflow.

Qt collects intent; this service owns the cross-authority sequence.  Validation
is read-only and field-aware.  Installation then advances through monotonic,
exact-idempotent checkpoints: one discoverable SQLite target/installation
transaction, SettingsStore security handles, and forward reconciliation.  No
compensation or rollback journal is required after a partial attempt.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from .deployment import (
    AmdAiDeploymentService,
    AmdDeploymentError,
    AmdInstallationSpec,
    AmdPrivateInstallationEnrollment,
    AmdPrivateTargetSpec,
)
from .manifests import ExecutionProfileManifest, ManifestCatalog
from .placements.ssh import (
    PinnedHostKey,
    SshTargetEnrollment,
    SshTargetResolutionError,
)
from .ssh_security import (
    AmdSshSecurityError,
    AmdSshSecurityStore,
    parse_pinned_host_key,
)
from .status import AmdInstallationStatus


class AmdGuidedInputField(StrEnum):
    """Focusable user-authored fields in the Private SSH guided form."""

    HOST = "host"
    USER = "user"
    PORT = "port"
    IDENTITY_FILE = "identity_file"
    PINNED_HOST_KEY = "pinned_host_key"


class AmdGuidedDeploymentError(RuntimeError):
    """A safe guided-command failure suitable for UI projection."""

    def __init__(
        self,
        error_code: str,
        *,
        field: AmdGuidedInputField | None = None,
    ) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.field = field


@dataclass(frozen=True, slots=True)
class AmdPrivateSshInstallCommand:
    """One user-approved enrollment plus deployment intent.

    Endpoint and local security fields never participate in ``repr``.  The
    command carries no password, key bytes, endpoint binding, or bearer token.
    """

    installation_id: str
    target_id: str
    host: str = field(repr=False)
    user: str = field(repr=False)
    port: int = field(repr=False)
    identity_file: Path | None = field(repr=False)
    pinned_host_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AmdGuidedPrivateInstallation:
    """Safe restart projection for one guided Private SSH installation."""

    installation_id: str
    target_id: str
    host: str = field(repr=False)
    user: str = field(repr=False)
    port: int = field(repr=False)
    security_enrolled: bool
    desired_presence: bool = True
    lifecycle_state: str = "active"
    status: AmdInstallationStatus | None = field(default=None, repr=False)
    inventory_error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AmdGuidedRetirementInstallation:
    """One discovered non-removed installation in retirement-only mode."""

    installation_id: str
    placement: str
    desired_presence: bool = True
    lifecycle_state: str = "active"
    status: AmdInstallationStatus | None = field(default=None, repr=False)
    inventory_error_code: str | None = None


@dataclass(frozen=True, slots=True)
class _ValidatedPrivateInstall:
    command: AmdPrivateSshInstallCommand = field(repr=False)
    identity_file: Path = field(repr=False)
    host_key: PinnedHostKey = field(repr=False)
    profile: ExecutionProfileManifest


class AmdGuidedDeploymentService:
    """Deep AMD-only facade for one guided Private SSH install command."""

    def __init__(
        self,
        *,
        catalog: ManifestCatalog,
        deployment: AmdAiDeploymentService,
        ssh_security: AmdSshSecurityStore,
    ) -> None:
        self._catalog = catalog
        self._deployment = deployment
        self._ssh_security = ssh_security
        self._lock = threading.RLock()

    def private_inventory(self) -> tuple[AmdGuidedPrivateInstallation, ...]:
        """Restore every non-removed Private installation without target I/O."""

        enrollments = tuple(
            enrollment
            for enrollment in self._deployment.private_installations()
            if enrollment.lifecycle_state != "removed"
        )
        restored: list[AmdGuidedPrivateInstallation] = []
        for enrollment in enrollments:
            security_error_code: str | None = None
            try:
                security_enrolled = self._ssh_security.contains_target(
                    enrollment.target_id
                )
            except AmdSshSecurityError as exc:
                security_enrolled = False
                security_error_code = exc.error_code
            status, status_error_code = self._status_or_error(
                enrollment.installation_id
            )
            restored.append(
                AmdGuidedPrivateInstallation(
                    installation_id=enrollment.installation_id,
                    target_id=enrollment.target_id,
                    host=enrollment.host,
                    user=enrollment.user,
                    port=enrollment.port,
                    security_enrolled=security_enrolled,
                    desired_presence=enrollment.desired_presence,
                    lifecycle_state=enrollment.lifecycle_state,
                    status=status,
                    inventory_error_code=security_error_code or status_error_code,
                )
            )
        return tuple(restored)

    def security_enrolled(self, installation_id: str) -> bool:
        """Resolve only whether one durable installation has local SSH handles."""

        matches = tuple(
            enrollment
            for enrollment in self._deployment.private_installations()
            if enrollment.installation_id == installation_id
        )
        if not matches:
            return False
        if len(matches) != 1:
            raise AmdGuidedDeploymentError("amd_installation_inventory_conflict")
        try:
            return self._ssh_security.contains_target(matches[0].target_id)
        except AmdSshSecurityError as exc:
            raise AmdGuidedDeploymentError(exc.error_code) from None

    def retirement_inventory(
        self,
    ) -> tuple[AmdGuidedRetirementInstallation, ...]:
        """Restore all actionable historical identities without target I/O."""

        installations = tuple(
            installation
            for installation in self._deployment.installations()
            if installation.lifecycle_state != "removed"
        )
        return tuple(
            AmdGuidedRetirementInstallation(
                installation_id=installation.installation_id,
                placement=installation.placement,
                desired_presence=installation.desired_presence,
                lifecycle_state=installation.lifecycle_state,
                status=status,
                inventory_error_code=error_code,
            )
            for installation in installations
            for status, error_code in (
                self._status_or_error(installation.installation_id),
            )
        )

    def _status_or_error(
        self,
        installation_id: str,
    ) -> tuple[AmdInstallationStatus | None, str | None]:
        try:
            return self._deployment.status(installation_id), None
        except AmdDeploymentError as exc:
            return None, exc.error_code
        except Exception:
            return None, "amd_status_unavailable"

    def validate_private_fields(self, command: AmdPrivateSshInstallCommand) -> None:
        """Validate pure form syntax on the UI thread without filesystem I/O."""

        self._validate_private(command, require_identity_available=False)

    def validate_private(self, command: AmdPrivateSshInstallCommand) -> None:
        """Validate the complete form without any durable mutation."""

        self._validate_private(command, require_identity_available=True)

    def install_private(
        self,
        command: AmdPrivateSshInstallCommand,
    ) -> AmdInstallationStatus:
        """Enroll and reconcile one exact Private SSH intent."""

        with self._lock:
            validated = self._validate_private(
                command,
                require_identity_available=True,
            )
            self._require_available_private_identity(command)
            try:
                identity_reference, host_key_reference = (
                    self._ssh_security.references_for_target(command.target_id)
                )
            except AmdSshSecurityError as exc:
                raise AmdGuidedDeploymentError(exc.error_code) from None
            target = AmdPrivateTargetSpec(
                target_id=command.target_id,
                host=command.host,
                user=command.user,
                port=command.port,
                pinned_host_key=host_key_reference,
                identity_file_reference=identity_reference,
            )
            installation = AmdInstallationSpec(
                installation_id=command.installation_id,
                placement="private_ssh",
                profile_digest=validated.profile.manifest_digest,
                target_id=command.target_id,
            )

            # SQLite is the discoverable command-identity checkpoint.  It
            # deliberately commits before SettingsStore so a crash at either
            # following boundary can continue with the exact same hidden IDs.
            self._deployment.ensure_private_install_intent(
                target=target,
                installation=installation,
            )
            try:
                self._ssh_security.record(
                    target_id=command.target_id,
                    identity_file=validated.identity_file,
                    host_key=validated.host_key,
                )
            except AmdSshSecurityError as exc:
                raise AmdGuidedDeploymentError(exc.error_code) from None
            return self._deployment.reconcile(command.installation_id)

    def _require_available_private_identity(
        self,
        command: AmdPrivateSshInstallCommand,
    ) -> None:
        enrollments = tuple(
            enrollment
            for enrollment in self._deployment.private_installations()
            if enrollment.lifecycle_state != "removed"
        )
        if any(
            _enrollment_matches_command(enrollment, command)
            for enrollment in enrollments
        ):
            return
        if enrollments:
            raise AmdGuidedDeploymentError("amd_installation_already_exists")

    def _validate_private(
        self,
        command: AmdPrivateSshInstallCommand,
        *,
        require_identity_available: bool,
    ) -> _ValidatedPrivateInstall:
        if not isinstance(command, AmdPrivateSshInstallCommand):
            raise AmdGuidedDeploymentError("amd_request_invalid")
        if not isinstance(command.host, str) or not command.host.strip():
            raise AmdGuidedDeploymentError(
                "amd_ssh_host_required",
                field=AmdGuidedInputField.HOST,
            )
        if not isinstance(command.user, str) or not command.user.strip():
            raise AmdGuidedDeploymentError(
                "amd_ssh_user_required",
                field=AmdGuidedInputField.USER,
            )
        if command.identity_file is None:
            raise AmdGuidedDeploymentError(
                "amd_ssh_identity_required",
                field=AmdGuidedInputField.IDENTITY_FILE,
            )
        if not isinstance(command.pinned_host_key, str) or not command.pinned_host_key.strip():
            raise AmdGuidedDeploymentError(
                "amd_ssh_host_key_required",
                field=AmdGuidedInputField.PINNED_HOST_KEY,
            )

        try:
            SshTargetEnrollment(
                target_id=command.target_id,
                host=command.host,
                user=command.user,
                port=command.port,
                pinned_host_key_reference="guided-validation",
                identity_file_reference="guided-validation",
            )
        except SshTargetResolutionError as exc:
            field_by_code = {
                "amd_ssh_host_invalid": AmdGuidedInputField.HOST,
                "amd_ssh_user_invalid": AmdGuidedInputField.USER,
                "amd_ssh_port_invalid": AmdGuidedInputField.PORT,
            }
            raise AmdGuidedDeploymentError(
                exc.error_code,
                field=field_by_code.get(exc.error_code),
            ) from None

        identity_file = _validated_identity_file(
            command.identity_file,
            require_available=require_identity_available,
        )
        try:
            host_key = parse_pinned_host_key(
                command.pinned_host_key,
                expected_host=command.host,
                expected_port=command.port,
            )
        except AmdSshSecurityError as exc:
            raise AmdGuidedDeploymentError(
                exc.error_code,
                field=AmdGuidedInputField.PINNED_HOST_KEY,
            ) from None

        profile = _single_profile(self._catalog)
        try:
            AmdInstallationSpec(
                installation_id=command.installation_id,
                placement="private_ssh",
                profile_digest=profile.manifest_digest,
                target_id=command.target_id,
            )
        except (TypeError, ValueError):
            raise AmdGuidedDeploymentError("amd_request_invalid") from None
        return _ValidatedPrivateInstall(
            command=command,
            identity_file=identity_file,
            host_key=host_key,
            profile=profile,
        )


def _validated_identity_file(
    value: Path,
    *,
    require_available: bool,
) -> Path:
    try:
        path = Path(value)
        rendered = str(path)
    except (OSError, TypeError, ValueError):
        raise AmdGuidedDeploymentError(
            "amd_ssh_identity_invalid",
            field=AmdGuidedInputField.IDENTITY_FILE,
        ) from None
    if (
        not path.is_absolute()
        or not rendered
        or len(rendered) > 2_048
        or rendered.startswith(("\\\\", "//"))
        or "\x00" in rendered
        or "\r" in rendered
        or "\n" in rendered
    ):
        raise AmdGuidedDeploymentError(
            "amd_ssh_identity_invalid",
            field=AmdGuidedInputField.IDENTITY_FILE,
        )
    if require_available:
        try:
            available = path.is_file()
        except OSError:
            available = False
        if not available:
            raise AmdGuidedDeploymentError(
                "amd_ssh_identity_unavailable",
                field=AmdGuidedInputField.IDENTITY_FILE,
            )
    return path


def _enrollment_matches_command(
    enrollment: AmdPrivateInstallationEnrollment,
    command: AmdPrivateSshInstallCommand,
) -> bool:
    return (
        enrollment.installation_id == command.installation_id
        and enrollment.target_id == command.target_id
        and enrollment.host == command.host
        and enrollment.user == command.user
        and enrollment.port == command.port
        and enrollment.desired_presence
        and enrollment.lifecycle_state == "active"
    )


def _single_profile(catalog: ManifestCatalog) -> ExecutionProfileManifest:
    profiles = catalog.profiles
    if len(profiles) != 1:
        raise AmdGuidedDeploymentError("amd_profile_catalog_invalid")
    return profiles[0]


__all__ = [
    "AmdGuidedDeploymentError",
    "AmdGuidedPrivateInstallation",
    "AmdGuidedRetirementInstallation",
    "AmdGuidedDeploymentService",
    "AmdGuidedInputField",
    "AmdPrivateSshInstallCommand",
]
