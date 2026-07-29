from __future__ import annotations

import base64
import logging
import struct
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QAbstractButton, QApplication

from xenix.services.amd.compatibility import TargetCompatibilityFacts
from xenix.services.amd.deployment import (
    AmdAiDeploymentService,
    AmdDeploymentError,
    AmdInstallationSpec,
    AmdPrivateTargetSpec,
    AmdRetirementRequest,
)
from xenix.services.amd.guided import (
    AmdGuidedDeploymentError,
    AmdGuidedDeploymentService,
    AmdGuidedInputField,
    AmdGuidedPrivateInstallation,
    AmdGuidedRetirementInstallation,
    AmdPrivateSshInstallCommand,
)
from xenix.services.amd.manifests import ManifestCapability, ManifestCatalog
from xenix.services.amd.participants import AmdProjectionStatus
from xenix.services.amd.placement import AmdRuntimeKey, LoopbackHttpBinding, RuntimeIncarnation
from xenix.services.amd.placements.ssh import (
    SshAuthenticationError,
    SshClientUnavailableError,
    SshCommandTimeoutError,
    SshConnectionError,
    SshHostTrustError,
)
from xenix.services.amd.profile_catalog import load_product_manifest_catalog
from xenix.services.amd.reconcile import AmdGenerationMaterialization
from xenix.services.amd.runtime import AmdRuntimeDirectory
from xenix.services.amd.ssh_security import (
    AmdSshSecurityError,
    AmdSshSecurityStore,
    parse_pinned_host_key,
)
from xenix.services.amd.status import AmdInstallationCondition
from xenix.services.settings_store import SettingsStore
from xenix.services.storage.database import create_engine_for_path, create_session_factory
from xenix.services.storage.migrations import bootstrap_current_schema
from xenix.services.storage.repositories.amd_installations import AmdInstallationRepository
from xenix.ui.amd_deployment_tasks import (
    AmdDeploymentTaskRunner,
    AmdGuidedOperation,
    AmdGuidedTaskResult,
    _project_retirement_request,
    _project_retirement_status,
    _project_status,
)
from xenix.ui.amd_setup import AmdGuidedSetupDialog


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _wait_until(
    app: QApplication,
    condition,
    *,
    timeout_seconds: float = 3.0,
) -> bool:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.001)
    app.processEvents()
    return condition()


def _host_key_line(
    key_type: str = "ssh-ed25519",
    *,
    comment: str | None = None,
) -> str:
    encoded_type = key_type.encode("ascii")
    payload = (
        struct.pack(">I", len(encoded_type))
        + encoded_type
        + struct.pack(">I", 32)
        + bytes(range(32))
    )
    rendered = f"{key_type} {base64.b64encode(payload).decode('ascii')}"
    return rendered if comment is None else f"{rendered} {comment}"


def _admitted_facts(catalog: ManifestCatalog) -> TargetCompatibilityFacts:
    profile = catalog.profiles[0]
    components = catalog.profile_components(profile)
    cell = components[0].compatibility_cells[0]
    return TargetCompatibilityFacts(
        os_name=cell.os_name,
        os_version=cell.os_version,
        kernel_version=cell.kernel_version,
        architecture=cell.architecture,
        gpu_architectures=(cell.gpu_architecture,),
        driver_version=cell.driver_version,
        rocm_version=cell.rocm_version,
        hip_version=cell.hip_version,
        python_version=cell.python_version,
        gpu_count=profile.capacity.min_gpu_count,
        free_vram_bytes=profile.capacity.min_free_vram_bytes,
        free_system_memory_bytes=profile.capacity.min_free_system_memory_bytes,
        free_persistent_bytes=profile.capacity.required_persistent_bytes,
    )


@dataclass
class _PrivateExecutionSession:
    incarnation: RuntimeIncarnation = field(
        default_factory=lambda: RuntimeIncarnation(
            "guided-test-controller",
            "guided-test-incarnation",
        )
    )
    closed: bool = False

    def resolve_binding(self, key: AmdRuntimeKey) -> LoopbackHttpBinding:
        return LoopbackHttpBinding(
            base_url="http://127.0.0.1:18081",
            bearer_token=f"guided-test-token-{key.component_generation_id}",
        )

    def close(self) -> None:
        self.closed = True


@dataclass
class _PrivatePlacement:
    facts: TargetCompatibilityFacts
    observe_error: Exception | None = None
    session: _PrivateExecutionSession = field(default_factory=_PrivateExecutionSession)
    materialize_calls: int = 0

    placement_kind = "private_ssh"

    def observe(self, *, profile, target_id: str | None) -> TargetCompatibilityFacts:
        assert target_id is not None
        if self.observe_error is not None:
            raise self.observe_error
        return self.facts

    def materialize(
        self,
        *,
        installation_id: str,
        target_id: str | None,
        profile,
        generations: tuple[AmdGenerationMaterialization, ...],
        cancellation=None,
    ) -> _PrivateExecutionSession:
        assert installation_id
        assert target_id
        assert generations
        assert cancellation is not None and not cancellation.is_set()
        self.materialize_calls += 1
        return self.session

    def self_test(
        self,
        *,
        session: _PrivateExecutionSession,
        generation: AmdGenerationMaterialization,
    ) -> str:
        assert session is self.session
        return f"guided-attestation-{generation.generation_id}"


@dataclass
class _Participant:
    capability: ManifestCapability
    projections: dict[tuple[str, str], AmdProjectionStatus] = field(default_factory=dict)

    def ensure(
        self,
        *,
        installation_id: str,
        component_generation_id: str,
        manifest,
    ) -> AmdProjectionStatus:
        assert manifest.capability is self.capability
        projection = AmdProjectionStatus(
            exists=True,
            retiring=False,
            selected=False,
        )
        self.projections[(installation_id, component_generation_id)] = projection
        return projection

    def status(
        self,
        *,
        installation_id: str,
        component_generation_id: str,
    ) -> AmdProjectionStatus:
        return self.projections.get(
            (installation_id, component_generation_id),
            AmdProjectionStatus(False, False, False),
        )


def _deployment(
    tmp_path: Path,
    *,
    observe_error: Exception | None = None,
):
    engine = create_engine_for_path(tmp_path / "guided-amd.sqlite")
    bootstrap_current_schema(engine)
    session_factory = create_session_factory(engine)
    catalog = load_product_manifest_catalog()
    placement = _PrivatePlacement(
        _admitted_facts(catalog),
        observe_error=observe_error,
    )
    deployment = AmdAiDeploymentService(
        session_factory=session_factory,
        catalog=catalog,
        placements={placement.placement_kind: placement},
        participants={
            capability: _Participant(capability)
            for capability in ManifestCapability
        },
        runtime_directory=AmdRuntimeDirectory(),
    )
    return engine, session_factory, catalog, placement, deployment


def _install_command(
    tmp_path: Path,
    *,
    installation_id: str = "amd-guided-installation",
    target_id: str = "amd-guided-target",
) -> AmdPrivateSshInstallCommand:
    identity_file = tmp_path / "id_ed25519"
    identity_file.write_text("test identity handle only", encoding="utf-8")
    return AmdPrivateSshInstallCommand(
        installation_id=installation_id,
        target_id=target_id,
        host="gpu.example.test",
        user="rocm",
        port=30401,
        identity_file=identity_file,
        pinned_host_key=_host_key_line(comment="verified server host key"),
    )


@pytest.mark.parametrize(
    ("key_type", "comment"),
    (
        ("ssh-ed25519", None),
        ("ecdsa-sha2-nistp256", "Radeon server host key"),
        ("ssh-rsa", "verified comment with spaces"),
    ),
)
def test_host_key_parser_accepts_complete_openssh_server_keys(
    key_type: str,
    comment: str | None,
) -> None:
    parsed = parse_pinned_host_key(_host_key_line(key_type, comment=comment))

    assert parsed.key_type == key_type


def test_host_key_parser_accepts_only_the_exact_known_hosts_endpoint() -> None:
    public_key = _host_key_line()
    exact = f"[gpu.example.test]:30401 {public_key}"

    parsed = parse_pinned_host_key(
        exact,
        expected_host="gpu.example.test",
        expected_port=30401,
    )

    assert parsed.key_type == "ssh-ed25519"
    with pytest.raises(AmdSshSecurityError):
        parse_pinned_host_key(
            exact,
            expected_host="other.example.test",
            expected_port=30401,
        )


@pytest.mark.parametrize(
    "invalid_value",
    (
        "SHA256:server-fingerprint",
        "ssh-ed25519 !!!not-base64!!!",
        _host_key_line("ssh-ed25519").replace("ssh-ed25519", "ssh-rsa", 1),
        _host_key_line() + "\nssh-ed25519 another-key",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
    ),
)
def test_host_key_parser_rejects_ambiguous_or_malformed_material(
    invalid_value: str,
) -> None:
    with pytest.raises(AmdSshSecurityError) as error:
        parse_pinned_host_key(invalid_value)

    assert error.value.error_code == "amd_ssh_host_key_invalid"


@dataclass
class _RecordingSecurity:
    calls: list[object] = field(default_factory=list)

    def record(self, **kwargs):
        self.calls.append(kwargs)
        return ("identity-reference", "host-key-reference")


def _empty_inventory_deployment() -> SimpleNamespace:
    return SimpleNamespace(
        has_installation=lambda _installation_id: False,
        installations=lambda: (),
        private_installations=lambda: (),
    )


@pytest.mark.parametrize(
    ("change", "error_code", "field"),
    (
        ({"host": ""}, "amd_ssh_host_required", AmdGuidedInputField.HOST),
        ({"host": "bad host"}, "amd_ssh_host_invalid", AmdGuidedInputField.HOST),
        ({"user": ""}, "amd_ssh_user_required", AmdGuidedInputField.USER),
        ({"user": "bad user"}, "amd_ssh_user_invalid", AmdGuidedInputField.USER),
        ({"port": 0}, "amd_ssh_port_invalid", AmdGuidedInputField.PORT),
        (
            {"identity_file": None},
            "amd_ssh_identity_required",
            AmdGuidedInputField.IDENTITY_FILE,
        ),
        (
            {"identity_file": Path("relative-key")},
            "amd_ssh_identity_invalid",
            AmdGuidedInputField.IDENTITY_FILE,
        ),
        (
            {"identity_file": Path("C:/missing-guided-key")},
            "amd_ssh_identity_unavailable",
            AmdGuidedInputField.IDENTITY_FILE,
        ),
        (
            {"pinned_host_key": ""},
            "amd_ssh_host_key_required",
            AmdGuidedInputField.PINNED_HOST_KEY,
        ),
        (
            {"pinned_host_key": "SHA256:fingerprint"},
            "amd_ssh_host_key_invalid",
            AmdGuidedInputField.PINNED_HOST_KEY,
        ),
    ),
)
def test_guided_validation_is_field_typed_and_has_no_durable_write(
    tmp_path: Path,
    change: dict[str, object],
    error_code: str,
    field: AmdGuidedInputField,
) -> None:
    security = _RecordingSecurity()
    service = AmdGuidedDeploymentService(
        catalog=load_product_manifest_catalog(),
        deployment=SimpleNamespace(),
        ssh_security=security,
    )
    command = replace(_install_command(tmp_path), **change)

    with pytest.raises(AmdGuidedDeploymentError) as error:
        service.validate_private(command)

    assert error.value.error_code == error_code
    assert error.value.field is field
    assert security.calls == []


def test_guided_install_exact_retry_reconciles_without_duplicate_state(
    tmp_path: Path,
) -> None:
    engine, session_factory, catalog, placement, deployment = _deployment(tmp_path)
    config_root = tmp_path / "config"
    config_root.mkdir()
    settings_store = SettingsStore(config_root)
    ssh_security = AmdSshSecurityStore(settings_store)
    guided = AmdGuidedDeploymentService(
        catalog=catalog,
        deployment=deployment,
        ssh_security=ssh_security,
    )
    command = _install_command(tmp_path)
    repository = AmdInstallationRepository()
    try:
        first = guided.install_private(command)
        second = guided.install_private(command)

        assert first.condition is AmdInstallationCondition.OPERATIONAL
        assert second.condition is AmdInstallationCondition.OPERATIONAL
        assert placement.materialize_calls == 1
        with session_factory() as session:
            targets = repository.get_target(session, command.target_id)
            installations = repository.list_installations(session)
        assert targets is not None
        assert [row.id for row in installations] == [command.installation_id]

        with pytest.raises(AmdGuidedDeploymentError) as conflict:
            guided.install_private(
                replace(command, host="other.example.test")
            )
        assert conflict.value.error_code == "amd_installation_already_exists"
    finally:
        deployment.close()
        ssh_security.close()
        settings_store.close()
        engine.dispose()


@dataclass
class _CheckpointSecurity:
    fail_record: bool = True
    enrolled: bool = False

    def references_for_target(self, target_id: str) -> tuple[str, str]:
        reference = f"amd-private-target:{target_id}"
        return reference, reference

    def record(self, **_kwargs) -> tuple[str, str]:
        if self.fail_record:
            raise AmdSshSecurityError(
                "checkpoint unavailable",
                error_code="amd_ssh_security_unavailable",
            )
        self.enrolled = True
        return ("unused", "unused")

    def contains_target(self, _target_id: str) -> bool:
        return self.enrolled


def test_guided_restart_recovers_sqlite_identity_before_security_checkpoint(
    tmp_path: Path,
) -> None:
    engine, session_factory, catalog, placement, deployment = _deployment(tmp_path)
    security = _CheckpointSecurity()
    guided = AmdGuidedDeploymentService(
        catalog=catalog,
        deployment=deployment,
        ssh_security=security,
    )
    command = _install_command(tmp_path)
    repository = AmdInstallationRepository()
    try:
        with pytest.raises(AmdGuidedDeploymentError) as error:
            guided.install_private(command)
        assert error.value.error_code == "amd_ssh_security_unavailable"

        restored_inventory = guided.private_inventory()
        assert len(restored_inventory) == 1
        restored = restored_inventory[0]
        assert restored.installation_id == command.installation_id
        assert restored.target_id == command.target_id
        assert not restored.security_enrolled
        with session_factory() as session:
            assert repository.get_target(session, command.target_id) is not None
            assert (
                repository.get_installation(session, command.installation_id)
                is not None
            )

        security.fail_record = False
        resumed = guided.install_private(command)

        assert resumed.condition is AmdInstallationCondition.OPERATIONAL
        assert security.enrolled
        assert placement.materialize_calls == 1
    finally:
        deployment.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("error_type", "expected_code"),
    (
        (SshClientUnavailableError, "amd_ssh_client_unavailable"),
        (SshHostTrustError, "amd_ssh_host_trust_failed"),
        (SshAuthenticationError, "amd_ssh_authentication_failed"),
        (SshCommandTimeoutError, "amd_ssh_connection_timeout"),
        (SshConnectionError, "amd_ssh_connection_failed"),
    ),
)
def test_deployment_preserves_typed_ssh_observation_failures(
    tmp_path: Path,
    error_type,
    expected_code: str,
) -> None:
    engine, _session_factory, catalog, _placement, deployment = _deployment(
        tmp_path,
        observe_error=error_type("redacted test failure"),
    )
    try:
        deployment.enroll_private_target(
            AmdPrivateTargetSpec(
                target_id="amd-guided-target",
                host="gpu.example.test",
                user="rocm",
                port=30401,
                pinned_host_key="host-key-reference",
                identity_file_reference="identity-reference",
            )
        )
        status = deployment.prepare(
            AmdInstallationSpec(
                installation_id="amd-guided-installation",
                placement="private_ssh",
                profile_digest=catalog.profiles[0].manifest_digest,
                target_id="amd-guided-target",
            )
        )

        assert status.condition is AmdInstallationCondition.NOT_MATERIALIZED
        assert status.target_observation_error_code == expected_code
        assert status.compatibility_issues == ()
    finally:
        deployment.close()
        engine.dispose()


@pytest.mark.parametrize(
    (
        "condition",
        "profile_usable",
        "component_error",
        "compatibility_issues",
        "expected_success",
        "expected_error",
    ),
    (
        ("operational", True, None, (), True, None),
        (
            "incompatible",
            False,
            None,
            ("amd_compatibility_vram_insufficient",),
            False,
            "amd_compatibility_vram_insufficient",
        ),
        (
            "degraded",
            False,
            "amd_ssh_connection_failed",
            (),
            False,
            "amd_ssh_connection_failed",
        ),
        (
            "installing",
            False,
            None,
            (),
            False,
            "amd_deployment_incomplete",
        ),
    ),
)
def test_task_projection_succeeds_only_for_operational_profile(
    condition: str,
    profile_usable: bool,
    component_error: str | None,
    compatibility_issues: tuple[str, ...],
    expected_success: bool,
    expected_error: str | None,
) -> None:
    status = SimpleNamespace(
        installation_id="amd-guided-installation",
        condition=SimpleNamespace(value=condition),
        profile_usable=profile_usable,
        target_observation_error_code=None,
        compatibility_issues=compatibility_issues,
        components=(
            SimpleNamespace(
                phase="registered" if condition == "operational" else "planned",
                error_code=component_error,
            ),
        ),
    )

    result = _project_status(
        AmdGuidedOperation.INSTALL,
        "amd-guided-installation",
        status,
    )

    assert result.succeeded is expected_success
    assert result.installation_available
    assert result.error_code == expected_error


def test_guided_dialog_focuses_invalid_field_and_has_no_save_or_local_route(
    tmp_path: Path,
    app: QApplication,
) -> None:
    security = _RecordingSecurity()
    deployment = _empty_inventory_deployment()
    guided = AmdGuidedDeploymentService(
        catalog=load_product_manifest_catalog(),
        deployment=deployment,
        ssh_security=security,
    )
    composition = SimpleNamespace(
        retirement_only=False,
        guided=guided,
        deployment=deployment,
    )
    dialog = AmdGuidedSetupDialog(composition)
    try:
        dialog.show()
        app.processEvents()
        dialog._start_install()
        app.processEvents()

        assert dialog._error_code == "amd_ssh_host_required"
        assert dialog.focusWidget() is dialog._host_input
        assert "SSH host" in dialog._details_value.text()
        assert security.calls == []
        button_texts = {
            button.text()
            for button in dialog.findChildren(QAbstractButton)
        }
        assert "Save" not in button_texts
        assert "Local Linux Radeon" not in button_texts
        assert dialog._retirement_installation_id_input.isHidden()
        assert "No separate Save action is required" in dialog._intro_label.text()
    finally:
        dialog.shutdown()
        dialog.close()


def test_guided_dialog_valid_form_schedules_exactly_one_command(
    tmp_path: Path,
    app: QApplication,
    monkeypatch,
) -> None:
    security = _RecordingSecurity()
    deployment = _empty_inventory_deployment()
    guided = AmdGuidedDeploymentService(
        catalog=load_product_manifest_catalog(),
        deployment=deployment,
        ssh_security=security,
    )
    composition = SimpleNamespace(
        retirement_only=False,
        guided=guided,
        deployment=deployment,
    )
    dialog = AmdGuidedSetupDialog(composition)
    commands: list[AmdPrivateSshInstallCommand] = []
    try:
        command = _install_command(tmp_path)
        dialog._host_input.setText(command.host)
        dialog._user_input.setText(command.user)
        dialog._port_input.setValue(command.port)
        dialog._identity_file_input.setText(str(command.identity_file))
        dialog._pinned_host_key_input.setText(command.pinned_host_key)
        monkeypatch.setattr(
            dialog._task_runner,
            "start_install",
            lambda request: commands.append(request) or True,
        )

        dialog._start_install()
        dialog._start_install()

        assert len(commands) == 1
        assert commands[0].host == command.host
        assert dialog._operation_active
        assert dialog._session_installation_id == commands[0].installation_id
        assert security.calls == []
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_background_identity_check_returns_field_error_to_dialog(
    tmp_path: Path,
    app: QApplication,
) -> None:
    security = _RecordingSecurity()
    deployment = _empty_inventory_deployment()
    guided = AmdGuidedDeploymentService(
        catalog=load_product_manifest_catalog(),
        deployment=deployment,
        ssh_security=security,
    )
    composition = SimpleNamespace(
        retirement_only=False,
        guided=guided,
        deployment=deployment,
    )
    dialog = AmdGuidedSetupDialog(composition)
    try:
        dialog.show()
        app.processEvents()
        command = _install_command(tmp_path)
        missing_identity = tmp_path / "missing-id-ed25519"
        dialog._host_input.setText(command.host)
        dialog._user_input.setText(command.user)
        dialog._port_input.setValue(command.port)
        dialog._identity_file_input.setText(str(missing_identity))
        dialog._pinned_host_key_input.setText(command.pinned_host_key)

        dialog._start_install()

        assert _wait_until(app, lambda: not dialog._operation_active)
        assert dialog._condition == "needs_attention"
        assert dialog._phase == "validation"
        assert dialog._error_code == "amd_ssh_identity_unavailable"
        assert dialog.focusWidget() is dialog._identity_file_input
        assert dialog._identity_file_input.isEnabled()
        assert security.calls == []
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_task_runner_logs_redacted_error_metadata_only(
    tmp_path: Path,
    app: QApplication,
    caplog,
) -> None:
    command = _install_command(tmp_path)
    secret_message = (
        f"host={command.host} user={command.user} port={command.port} "
        f"identity={command.identity_file} key={command.pinned_host_key} "
        "stderr=permission denied"
    )

    class SecretFailure(RuntimeError):
        pass

    composition = SimpleNamespace(
        guided=SimpleNamespace(
            install_private=lambda _command: (_ for _ in ()).throw(
                SecretFailure(secret_message)
            )
        ),
        deployment=SimpleNamespace(has_installation=lambda _installation_id: False),
    )
    runner = AmdDeploymentTaskRunner(composition)
    try:
        with caplog.at_level(logging.INFO, logger="xenix.ui.amd_deployment_tasks"):
            assert runner.start_install(command)
            assert _wait_until(
                app,
                lambda: not runner.active
                and any(
                    getattr(record, "exception_type", None) == "SecretFailure"
                    for record in caplog.records
                ),
            )

        safe_fields = (
            "event_name",
            "operation",
            "succeeded",
            "installation_available",
            "condition",
            "phase",
            "error_code",
            "exception_type",
        )
        rendered = "\n".join(
            repr(
                {
                    "message": record.getMessage(),
                    **{
                        name: getattr(record, name)
                        for name in safe_fields
                        if hasattr(record, name)
                    },
                }
            )
            for record in caplog.records
        )
        assert "SecretFailure" in rendered
        assert "amd_operation_failed" in rendered
        assert "amd.guided.operation.raised" in rendered
        assert "amd.guided.operation.completed" in rendered
        for prohibited in (
            command.host,
            command.user,
            str(command.port),
            str(command.identity_file),
            command.pinned_host_key,
            "permission denied",
        ):
            assert prohibited not in rendered
    finally:
        runner.shutdown()


def _restored_dialog_composition(
    *,
    security_enrolled: bool,
) -> SimpleNamespace:
    status = SimpleNamespace(
        installation_id="amd-restored-installation",
        lifecycle_state="active",
        condition=SimpleNamespace(value="not_materialized"),
        profile_usable=False,
        target_observation_error_code=None,
        compatibility_issues=(),
        components=(),
    )
    restored = AmdGuidedPrivateInstallation(
        installation_id="amd-restored-installation",
        target_id="amd-restored-target",
        host="gpu.example.test",
        user="rocm",
        port=30401,
        security_enrolled=security_enrolled,
        status=status,
    )
    guided = SimpleNamespace(
        private_inventory=lambda: (restored,),
        validate_private_fields=lambda _command: None,
        security_enrolled=lambda _installation_id: security_enrolled,
    )
    deployment = SimpleNamespace(
        has_installation=lambda _installation_id: True,
        status=lambda _installation_id: status,
    )
    return SimpleNamespace(
        retirement_only=False,
        guided=guided,
        deployment=deployment,
    )


def test_retirement_only_dialog_discovers_hidden_installation_identity(
    app: QApplication,
) -> None:
    status = SimpleNamespace(
        installation_id="amd-historical-local",
        lifecycle_state="active",
        condition=SimpleNamespace(value="not_materialized"),
        profile_usable=False,
        target_observation_error_code=None,
        compatibility_issues=(),
        components=(),
    )
    restored = AmdGuidedRetirementInstallation(
        installation_id="amd-historical-local",
        placement="local_linux",
        status=status,
    )
    composition = SimpleNamespace(
        retirement_only=True,
        guided=SimpleNamespace(retirement_inventory=lambda: (restored,)),
        deployment=SimpleNamespace(
            has_installation=lambda _installation_id: True,
            status=lambda _installation_id: status,
        ),
    )
    dialog = AmdGuidedSetupDialog(composition)
    try:
        dialog.show()
        app.processEvents()

        assert dialog._session_installation_id == "amd-historical-local"
        assert (
            dialog._retirement_installation_id_input.text()
            == "amd-historical-local"
        )
        assert dialog._retirement_installation_id_input.isReadOnly()
        assert dialog._remove_button.isEnabled()
        assert dialog._install_button.isHidden()
        assert dialog._repair_button.isHidden()
    finally:
        dialog.shutdown()
        dialog.close()


@pytest.mark.parametrize("security_enrolled", (False, True))
def test_guided_dialog_restores_durable_identity_after_restart(
    app: QApplication,
    security_enrolled: bool,
) -> None:
    dialog = AmdGuidedSetupDialog(
        _restored_dialog_composition(security_enrolled=security_enrolled)
    )
    try:
        dialog.show()
        app.processEvents()

        assert dialog._pending_installation_id == "amd-restored-installation"
        assert dialog._pending_target_id == "amd-restored-target"
        assert dialog._session_installation_id == "amd-restored-installation"
        assert dialog._host_input.text() == "gpu.example.test"
        assert dialog._user_input.text() == "rocm"
        assert dialog._port_input.value() == 30401
        assert not dialog._host_input.isEnabled()
        assert dialog._remove_button.isEnabled()
        if security_enrolled:
            assert dialog._repair_button.isEnabled()
            assert not dialog._install_button.isEnabled()
        else:
            assert dialog._error_code == "amd_ssh_enrollment_incomplete"
            assert dialog._identity_file_input.isEnabled()
            assert dialog._install_button.isEnabled()
            assert dialog._install_button.text() == "Continue setup"
    finally:
        dialog.shutdown()
        dialog.close()


def test_already_removed_acknowledgement_projects_removed_truthfully() -> None:
    result = _project_retirement_request(
        "amd-restored-installation",
        AmdRetirementRequest(
            installation_id="amd-restored-installation",
            phase="already_removed",
        ),
    )

    assert result.succeeded
    assert result.condition == "removed"
    assert result.phase == "already_removed"
    assert not result.installation_available


def test_retirement_projection_exposes_physical_cleanup_blocker() -> None:
    result = _project_retirement_status(
        "amd-restored-installation",
        SimpleNamespace(
            installation_id="amd-restored-installation",
            condition=SimpleNamespace(value="removal_blocked"),
            components=(
                SimpleNamespace(
                    lifecycle_state="removal_blocked",
                    phase="removal_blocked",
                    error_code="physical_cleanup_blocked",
                ),
            ),
        ),
    )

    assert not result.succeeded
    assert result.installation_available
    assert result.condition == "removal_blocked"
    assert result.error_code == "physical_cleanup_blocked"


@pytest.mark.parametrize("remove_finishes_first", (False, True))
@pytest.mark.parametrize("installation_available", (False, True))
def test_latest_remove_intent_wins_both_completion_orders(
    app: QApplication,
    monkeypatch,
    remove_finishes_first: bool,
    installation_available: bool,
) -> None:
    dialog = AmdGuidedSetupDialog(
        _restored_dialog_composition(security_enrolled=True)
    )
    install_result = AmdGuidedTaskResult(
        operation=AmdGuidedOperation.REPAIR,
        installation_id="amd-restored-installation",
        succeeded=True,
        installation_available=True,
        condition="operational",
        phase="registered",
        error_code=None,
        security_enrolled=True,
    )
    remove_result = AmdGuidedTaskResult(
        operation=AmdGuidedOperation.REMOVE,
        installation_id="amd-restored-installation",
        succeeded=False,
        installation_available=installation_available,
        condition="removal_blocked" if installation_available else "failed",
        phase="removal_blocked" if installation_available else "failed",
        error_code=(
            "physical_cleanup_blocked"
            if installation_available
            else "amd_installation_not_found"
        ),
        security_enrolled=True,
    )
    try:
        monkeypatch.setattr(dialog._task_runner, "start_repair", lambda _id: True)
        monkeypatch.setattr(dialog._task_runner, "start_remove", lambda _id: True)
        dialog._start_repair()
        dialog._start_remove()

        if remove_finishes_first:
            dialog._finish_retirement_request(remove_result)
            dialog._finish_operation(install_result)
        else:
            dialog._finish_operation(install_result)
            dialog._finish_retirement_request(remove_result)

        assert dialog._condition == (
            "removal_blocked" if installation_available else "failed"
        )
        assert dialog._error_code == (
            "physical_cleanup_blocked"
            if installation_available
            else "amd_installation_not_found"
        )
        assert dialog._remove_button.isEnabled() is installation_available
        assert not dialog._repair_button.isEnabled()
        if not installation_available:
            assert dialog._session_installation_id is None
            assert dialog._install_button.isEnabled()
            assert dialog._pending_installation_id != "amd-restored-installation"
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_guided_dialog_selects_each_durable_private_installation(
    app: QApplication,
    monkeypatch,
) -> None:
    def status(installation_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            installation_id=installation_id,
            lifecycle_state="active",
            condition=SimpleNamespace(value="not_materialized"),
            profile_usable=False,
            target_observation_error_code=None,
            compatibility_issues=(),
            components=(),
        )

    first = AmdGuidedPrivateInstallation(
        installation_id="amd-private-first",
        target_id="amd-target-first",
        host="first.example.test",
        user="rocm",
        port=30401,
        security_enrolled=True,
        status=status("amd-private-first"),
    )
    second = AmdGuidedPrivateInstallation(
        installation_id="amd-private-second",
        target_id="amd-target-second",
        host="second.example.test",
        user="root",
        port=30402,
        security_enrolled=True,
        status=status("amd-private-second"),
    )
    composition = SimpleNamespace(
        retirement_only=False,
        guided=SimpleNamespace(
            private_inventory=lambda: (first, second),
            validate_private_fields=lambda _command: None,
            security_enrolled=lambda _installation_id: True,
        ),
        deployment=SimpleNamespace(
            has_installation=lambda _installation_id: True,
            status=status,
        ),
    )
    dialog = AmdGuidedSetupDialog(composition)
    try:
        dialog.show()
        app.processEvents()

        assert dialog._managed_installation_combo.isVisible()
        assert dialog._managed_installation_combo.count() == 2
        assert dialog._managed_installation_combo.itemText(0).endswith("1")
        assert dialog._session_installation_id == first.installation_id

        monkeypatch.setattr(dialog._task_runner, "start_repair", lambda _id: True)
        dialog._start_repair()
        dialog._finish_operation(
            AmdGuidedTaskResult(
                operation=AmdGuidedOperation.REPAIR,
                installation_id=first.installation_id,
                succeeded=True,
                installation_available=True,
                condition="operational",
                phase="registered",
                error_code=None,
                security_enrolled=True,
            )
        )
        dialog._managed_installation_combo.setCurrentIndex(1)
        dialog._managed_installation_combo.setCurrentIndex(0)
        app.processEvents()
        assert dialog._condition == "operational"

        monkeypatch.setattr(dialog._task_runner, "start_remove", lambda _id: True)
        dialog._start_remove()
        dialog._finish_retirement_request(
            AmdGuidedTaskResult(
                operation=AmdGuidedOperation.REMOVE,
                installation_id=first.installation_id,
                succeeded=False,
                installation_available=True,
                condition="removal_blocked",
                phase="removal_blocked",
                error_code="physical_cleanup_blocked",
                security_enrolled=True,
            )
        )
        dialog._managed_installation_combo.setCurrentIndex(1)
        dialog._managed_installation_combo.setCurrentIndex(0)
        app.processEvents()

        assert dialog._condition == "removal_blocked"
        assert dialog._error_code == "physical_cleanup_blocked"
        assert dialog._retirement_requested
        assert not dialog._repair_button.isEnabled()

        dialog._start_remove()
        dialog._finish_retirement_request(
            AmdGuidedTaskResult(
                operation=AmdGuidedOperation.REMOVE,
                installation_id=first.installation_id,
                succeeded=True,
                installation_available=False,
                condition="removed",
                phase="removed",
                error_code=None,
            )
        )
        app.processEvents()

        assert dialog._managed_installation_combo.count() == 1
        assert dialog._managed_installation_combo.currentIndex() == -1
        assert dialog._managed_installation_combo.isVisible()
        assert dialog._managed_installation_combo.itemText(0).endswith("2")
        assert not dialog._install_button.isEnabled()
        assert dialog._session_installation_id is None

        dialog._managed_installation_combo.setCurrentIndex(0)
        app.processEvents()

        assert dialog._session_installation_id == second.installation_id
        assert dialog._host_input.text() == second.host
        assert dialog._user_input.text() == second.user
        assert dialog._port_input.value() == second.port
        assert dialog._repair_button.isEnabled()
        assert dialog._remove_button.isEnabled()
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_unknown_remove_availability_preserves_identity_for_retry(
    app: QApplication,
    monkeypatch,
) -> None:
    dialog = AmdGuidedSetupDialog(
        _restored_dialog_composition(security_enrolled=True)
    )
    try:
        monkeypatch.setattr(dialog._task_runner, "start_remove", lambda _id: True)
        dialog._start_remove()
        dialog._finish_retirement_request(
            AmdGuidedTaskResult(
                operation=AmdGuidedOperation.REMOVE,
                installation_id="amd-restored-installation",
                succeeded=False,
                installation_available=None,
                condition="failed",
                phase="failed",
                error_code="amd_operation_failed",
                security_enrolled=False,
            )
        )

        assert dialog._session_installation_id == "amd-restored-installation"
        assert dialog._retirement_requested
        assert dialog._remove_button.isEnabled()
        assert not dialog._repair_button.isEnabled()
        assert len(dialog._inventory_entries) == 1
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_retirement_lifecycle_outranks_secondary_security_inventory_error(
    app: QApplication,
) -> None:
    installation_id = "amd-private-retirement-security-error"
    status = SimpleNamespace(
        installation_id=installation_id,
        lifecycle_state="retiring",
        condition=SimpleNamespace(value="removal_blocked"),
        profile_usable=False,
        target_observation_error_code=None,
        compatibility_issues=(),
        components=(
            SimpleNamespace(
                lifecycle_state="removal_blocked",
                phase="removal_blocked",
                error_code="physical_cleanup_blocked",
            ),
        ),
    )
    restored = AmdGuidedPrivateInstallation(
        installation_id=installation_id,
        target_id="amd-target-retirement-security-error",
        host="gpu.example.test",
        user="rocm",
        port=30401,
        security_enrolled=False,
        status=status,
        inventory_error_code="amd_ssh_security_unavailable",
    )
    dialog = AmdGuidedSetupDialog(
        SimpleNamespace(
            retirement_only=False,
            guided=SimpleNamespace(
                private_inventory=lambda: (restored,),
                validate_private_fields=lambda _command: None,
                security_enrolled=lambda _installation_id: False,
            ),
            deployment=SimpleNamespace(
                has_installation=lambda _installation_id: True,
                status=lambda _installation_id: status,
            ),
        )
    )
    try:
        assert dialog._condition == "removal_blocked"
        assert dialog._error_code == "physical_cleanup_blocked"
        assert dialog._retirement_requested
        assert not dialog._install_button.isEnabled()
        assert not dialog._repair_button.isEnabled()
        assert dialog._remove_button.isEnabled()
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_private_security_input_never_crosses_inventory_selection(
    app: QApplication,
) -> None:
    def installation(
        installation_id: str,
        target_id: str,
        host: str,
    ) -> AmdGuidedPrivateInstallation:
        return AmdGuidedPrivateInstallation(
            installation_id=installation_id,
            target_id=target_id,
            host=host,
            user="rocm",
            port=30401,
            security_enrolled=False,
            status=SimpleNamespace(
                installation_id=installation_id,
                lifecycle_state="active",
                condition=SimpleNamespace(value="not_materialized"),
                profile_usable=False,
                target_observation_error_code=None,
                compatibility_issues=(),
                components=(),
            ),
        )

    first = installation(
        "amd-private-unenrolled-first",
        "amd-target-unenrolled-first",
        "first.example.test",
    )
    second = installation(
        "amd-private-unenrolled-second",
        "amd-target-unenrolled-second",
        "second.example.test",
    )
    dialog = AmdGuidedSetupDialog(
        SimpleNamespace(
            retirement_only=False,
            guided=SimpleNamespace(
                private_inventory=lambda: (first, second),
                validate_private_fields=lambda _command: None,
                security_enrolled=lambda _installation_id: False,
            ),
            deployment=SimpleNamespace(
                has_installation=lambda _installation_id: True,
            ),
        )
    )
    try:
        dialog._identity_file_input.setText("C:/private/a-key")
        dialog._pinned_host_key_input.setText("ssh-ed25519 key-for-a")

        dialog._managed_installation_combo.setCurrentIndex(1)
        app.processEvents()

        assert dialog._session_installation_id == second.installation_id
        assert dialog._identity_file_input.text() == ""
        assert dialog._pinned_host_key_input.text() == ""
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_retirement_inventory_preserves_identity_when_profile_is_unavailable(
    app: QApplication,
) -> None:
    installation = SimpleNamespace(
        installation_id="amd-historical-missing-profile",
        placement="local_linux",
        desired_presence=True,
        lifecycle_state="active",
    )

    def unavailable_status(_installation_id: str) -> None:
        raise AmdDeploymentError(
            "profile unavailable",
            error_code="amd_profile_unavailable",
        )

    deployment = SimpleNamespace(
        installations=lambda: (installation,),
        status=unavailable_status,
        has_installation=lambda _installation_id: True,
    )
    guided = AmdGuidedDeploymentService(
        catalog=load_product_manifest_catalog(),
        deployment=deployment,
        ssh_security=SimpleNamespace(),
    )

    inventory = guided.retirement_inventory()
    assert len(inventory) == 1
    assert inventory[0].installation_id == installation.installation_id
    assert inventory[0].status is None
    assert inventory[0].inventory_error_code == "amd_profile_unavailable"

    dialog = AmdGuidedSetupDialog(
        SimpleNamespace(
            retirement_only=True,
            guided=guided,
            deployment=deployment,
        )
    )
    try:
        dialog.show()
        app.processEvents()

        assert dialog._session_installation_id == installation.installation_id
        assert dialog._error_code == "amd_profile_unavailable"
        assert dialog._remove_button.isEnabled()
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


class _UnavailableSecurity:
    def contains_target(self, _target_id: str) -> bool:
        raise AmdSshSecurityError(
            "security unavailable",
            error_code="amd_ssh_security_unavailable",
        )


def test_private_inventory_preserves_identity_when_security_store_is_unavailable(
    app: QApplication,
    caplog,
) -> None:
    installation_id = "amd-private-security-unavailable"
    status = SimpleNamespace(
        installation_id=installation_id,
        lifecycle_state="active",
        condition=SimpleNamespace(value="not_materialized"),
        profile_usable=False,
        target_observation_error_code=None,
        compatibility_issues=(),
        components=(),
    )
    enrollment = SimpleNamespace(
        installation_id=installation_id,
        target_id="amd-target-security-unavailable",
        host="gpu.example.test",
        user="rocm",
        port=30401,
        desired_presence=True,
        lifecycle_state="active",
    )
    deployment = SimpleNamespace(
        private_installations=lambda: (enrollment,),
        status=lambda _installation_id: status,
        has_installation=lambda _installation_id: True,
    )
    guided = AmdGuidedDeploymentService(
        catalog=load_product_manifest_catalog(),
        deployment=deployment,
        ssh_security=_UnavailableSecurity(),
    )

    inventory = guided.private_inventory()
    assert len(inventory) == 1
    assert inventory[0].installation_id == installation_id
    assert not inventory[0].security_enrolled
    assert inventory[0].inventory_error_code == "amd_ssh_security_unavailable"

    with caplog.at_level(
        logging.WARNING,
        logger="xenix.ui.amd_deployment_tasks",
    ):
        dialog = AmdGuidedSetupDialog(
            SimpleNamespace(
                retirement_only=False,
                guided=guided,
                deployment=deployment,
            )
        )
    try:
        dialog.show()
        app.processEvents()

        assert dialog._session_installation_id == installation_id
        assert dialog._error_code == "amd_ssh_security_unavailable"
        assert dialog._remove_button.isEnabled()
        assert dialog._install_button.isEnabled()
        inventory_record = next(
            record
            for record in caplog.records
            if getattr(record, "event_name", None) == "amd.guided.inventory.item"
        )
        assert inventory_record.error_code == "amd_ssh_security_unavailable"
        assert (
            inventory_record.secondary_error_code
            == "amd_ssh_security_unavailable"
        )
        assert "gpu.example.test" not in repr(inventory_record.__dict__)
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_private_retirement_authority_survives_status_and_security_read_failures(
    app: QApplication,
) -> None:
    installation_id = "amd-private-retiring-unreadable"
    enrollment = SimpleNamespace(
        installation_id=installation_id,
        target_id="amd-target-retiring-unreadable",
        host="gpu.example.test",
        user="rocm",
        port=30401,
        desired_presence=False,
        lifecycle_state="retiring",
    )

    def unavailable_status(_installation_id: str) -> None:
        raise AmdDeploymentError(
            "status unavailable",
            error_code="amd_profile_unavailable",
        )

    deployment = SimpleNamespace(
        private_installations=lambda: (enrollment,),
        status=unavailable_status,
        has_installation=lambda _installation_id: True,
    )
    guided = AmdGuidedDeploymentService(
        catalog=load_product_manifest_catalog(),
        deployment=deployment,
        ssh_security=_UnavailableSecurity(),
    )

    inventory = guided.private_inventory()
    assert len(inventory) == 1
    assert not inventory[0].desired_presence
    assert inventory[0].lifecycle_state == "retiring"
    assert inventory[0].status is None

    dialog = AmdGuidedSetupDialog(
        SimpleNamespace(
            retirement_only=False,
            guided=guided,
            deployment=deployment,
        )
    )
    try:
        assert dialog._session_installation_id == installation_id
        assert dialog._condition == "retiring"
        assert dialog._phase == "inventory"
        assert dialog._retirement_requested
        assert not dialog._install_button.isEnabled()
        assert not dialog._repair_button.isEnabled()
        assert dialog._remove_button.isEnabled()
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()


def test_dialog_cannot_hide_an_active_deployment(
    app: QApplication,
    monkeypatch,
) -> None:
    dialog = AmdGuidedSetupDialog(
        _restored_dialog_composition(security_enrolled=True)
    )
    try:
        monkeypatch.setattr(dialog._task_runner, "start_repair", lambda _id: True)
        dialog._start_repair()
        event = QCloseEvent()

        dialog.closeEvent(event)

        assert not event.isAccepted()
        assert not dialog._close_button.isEnabled()
    finally:
        dialog.shutdown()
        dialog.close()
        app.processEvents()
