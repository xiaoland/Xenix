from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from xenix.services.amd.adapters.ocr import AmdOcrDescriptorMismatchError
from xenix.services.amd.compatibility import CompatibilityPlanner, TargetCompatibilityFacts
from xenix.services.amd.composition import _ocr_descriptor_resolver
from xenix.services.amd.deployment import AmdAiDeploymentService, AmdDeploymentError, AmdInstallationSpec
from xenix.services.amd.manifests import ManifestAdmission, ManifestCapability, ManifestCatalog
from xenix.services.amd.participants import AmdProjectionStatus
from xenix.services.amd.placement import AmdRuntimeKey, LoopbackHttpBinding, RuntimeIncarnation
from xenix.services.amd.profile_catalog import load_product_manifest_catalog
from xenix.services.amd.recipes import recipe_for
from xenix.services.amd.reconcile import AmdGenerationMaterialization
from xenix.services.amd.runtime import AmdRuntimeDirectory
from xenix.services.amd.status import AmdInstallationCondition
from xenix.services.ocr.settings import ManagedOcrProviderRef, OcrProviderProjection
from xenix.services.storage.database import create_engine_for_path, create_session_factory
from xenix.services.storage.migrations import bootstrap_current_schema
from xenix.services.storage.models import AmdComponentGenerationRow, AmdInstallationRow
from xenix.services.storage.repositories.amd_installations import AmdInstallationRepository


@dataclass
class _FakeExecutionSession:
    closed: bool = False
    _incarnation: RuntimeIncarnation = field(
        default_factory=lambda: RuntimeIncarnation("test-controller", "test-incarnation")
    )

    @property
    def incarnation(self) -> RuntimeIncarnation:
        return self._incarnation

    def resolve_binding(self, key: AmdRuntimeKey) -> LoopbackHttpBinding:
        assert key.installation_id == "amd-test-installation"
        return LoopbackHttpBinding(
            base_url="http://127.0.0.1:18081",
            bearer_token="test-token-0123456789abcdef",
        )

    def close(self) -> None:
        self.closed = True


@dataclass
class _FakePlacement:
    facts: TargetCompatibilityFacts
    session: _FakeExecutionSession = field(default_factory=_FakeExecutionSession)
    materialized: list[tuple[AmdGenerationMaterialization, ...]] = field(default_factory=list)
    retired: list[str] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)

    @property
    def placement_kind(self) -> str:
        return "local_linux"

    def observe(self, *, profile, target_id: str | None) -> TargetCompatibilityFacts:
        assert target_id is None
        return self.facts

    def materialize(
        self,
        *,
        installation_id: str,
        target_id: str | None,
        profile,
        generations: tuple[AmdGenerationMaterialization, ...],
        cancellation=None,
    ) -> _FakeExecutionSession:
        assert installation_id == "amd-test-installation"
        assert target_id is None
        assert cancellation is not None and not cancellation.is_set()
        self.materialized.append(generations)
        return self.session

    def open_retirement_session(
        self,
        *,
        installation_id: str,
        target_id: str | None,
        profile,
        generations: tuple[AmdGenerationMaterialization, ...],
    ) -> _FakeExecutionSession:
        assert installation_id == "amd-test-installation"
        assert target_id is None
        return self.session

    def self_test(self, *, session: _FakeExecutionSession, generation: AmdGenerationMaterialization) -> str:
        assert session is self.session
        return f"attestation-{generation.generation_id}"

    def cancel_generation_provisioning(
        self,
        *,
        session: _FakeExecutionSession,
        installation_id: str,
        profile,
        generation: AmdGenerationMaterialization,
    ) -> None:
        assert session is self.session
        assert installation_id == "amd-test-installation"
        self.cancelled.append(generation.generation_id)

    def retire_generation(
        self,
        *,
        session: _FakeExecutionSession,
        installation_id: str,
        profile,
        generation: AmdGenerationMaterialization,
    ) -> None:
        assert session is self.session
        assert installation_id == "amd-test-installation"
        self.retired.append(generation.generation_id)


class _BlockedRetirementPlacement(_FakePlacement):
    def open_retirement_session(
        self,
        *,
        installation_id: str,
        target_id: str | None,
        profile,
        generations: tuple[AmdGenerationMaterialization, ...],
    ) -> _FakeExecutionSession:
        del installation_id, target_id, profile, generations
        raise RuntimeError("simulated trusted cleanup-session failure")


@dataclass
class _FakeParticipant:
    capability: ManifestCapability
    projections: dict[tuple[str, str], AmdProjectionStatus] = field(default_factory=dict)

    def ensure(self, *, installation_id: str, component_generation_id: str, manifest) -> AmdProjectionStatus:
        assert manifest.capability is self.capability
        key = (installation_id, component_generation_id)
        self.projections[key] = AmdProjectionStatus(exists=True, retiring=False, selected=False)
        return self.projections[key]

    def mark_retiring(self, *, installation_id: str, component_generation_id: str) -> AmdProjectionStatus:
        key = (installation_id, component_generation_id)
        self.projections[key] = AmdProjectionStatus(exists=True, retiring=True, selected=False)
        return self.projections[key]

    def remove(self, *, installation_id: str, component_generation_id: str) -> AmdProjectionStatus:
        key = (installation_id, component_generation_id)
        self.projections[key] = AmdProjectionStatus(exists=False, retiring=False, selected=False)
        return self.projections[key]

    def status(self, *, installation_id: str, component_generation_id: str) -> AmdProjectionStatus:
        return self.projections.get(
            (installation_id, component_generation_id),
            AmdProjectionStatus(exists=False, retiring=False, selected=False),
        )


def _admitted_facts(catalog: ManifestCatalog) -> TargetCompatibilityFacts:
    profile = catalog.profiles[0]
    components = catalog.profile_components(profile)
    cell = components[0].compatibility_cells[0]
    assert all(component.compatibility_cells == (cell,) for component in components)
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


def _deployment(tmp_path: Path, *, allow_new_installations: bool = True):
    engine = create_engine_for_path(tmp_path / "amd-state.sqlite")
    bootstrap_current_schema(engine)
    catalog = load_product_manifest_catalog()
    placement = _FakePlacement(_admitted_facts(catalog))
    participants = {
        capability: _FakeParticipant(capability)
        for capability in ManifestCapability
    }
    deployment = AmdAiDeploymentService(
        session_factory=create_session_factory(engine),
        catalog=catalog,
        placements={placement.placement_kind: placement},
        participants=participants,
        runtime_directory=AmdRuntimeDirectory(),
        allow_new_installations=allow_new_installations,
    )
    return engine, catalog, deployment, placement


def test_generic_source_has_no_direct_amd_import_edge() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "xenix"
    excluded = {
        Path("ui/amd_setup.py"),
        Path("ui/amd_deployment_tasks.py"),
    }
    violations: list[str] = []

    for source_path in source_root.rglob("*.py"):
        relative_path = source_path.relative_to(source_root)
        if relative_path.parts[:2] == ("services", "amd") or relative_path in excluded:
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.startswith("xenix.services.amd") for alias in node.names):
                    violations.append(str(relative_path))
            elif isinstance(node, ast.ImportFrom):
                if (
                    (node.module or "").startswith("xenix.services.amd")
                    or (
                        node.module == "xenix.services"
                        and any(alias.name == "amd" for alias in node.names)
                    )
                ):
                    violations.append(str(relative_path))

    assert not violations


def test_bundled_profile_is_admitted_and_matches_its_exact_cloud_cell() -> None:
    catalog = load_product_manifest_catalog()
    profile = catalog.profiles[0]

    assert profile.admission is ManifestAdmission.ADMITTED
    assert profile.admission_blockers == ()
    assert {component.capability for component in catalog.profile_components(profile)} == set(ManifestCapability)
    assert all(component.admission is ManifestAdmission.ADMITTED for component in catalog.components)
    assert CompatibilityPlanner(catalog).plan_profile(profile.manifest_digest, _admitted_facts(catalog)).supported


def test_vllm_recipe_uses_the_manifest_wheel_name_and_mirror_safe_snapshot_filter() -> None:
    catalog = load_product_manifest_catalog()
    profile = catalog.profiles[0]

    for manifest in catalog.profile_components(profile):
        if manifest.capability not in {ManifestCapability.CHAT, ManifestCapability.EMBEDDING}:
            continue
        recipe = recipe_for(
            AmdGenerationMaterialization(
                capability=manifest.capability,
                generation_id=f"test-{manifest.capability.value}",
                manifest=manifest,
            )
        )
        wheel_name = next(item.relative_path for item in manifest.artifacts if item.kind.value == "runtime")
        arguments = recipe.provisioning_arguments()
        layout = recipe.launch_layout(
            generation_root=f"/xenix/installations/test/generations/{manifest.capability.value}",
            public_port=18081,
            backend_port=18082,
        )

        assert arguments[2] == wheel_name
        assert "vllm.whl" not in arguments
        assert {"vllm.whl", wheel_name}.issubset(layout.owned_relative_paths)
        assert 'ignore_patterns=[".DS_Store", "**/.DS_Store"]' in recipe.provisioning_script()


def test_deployment_reconciles_admitted_components_then_retires_exact_generations(tmp_path: Path) -> None:
    engine, catalog, deployment, placement = _deployment(tmp_path)
    profile = catalog.profiles[0]
    try:
        operational = deployment.prepare(
            AmdInstallationSpec(
                installation_id="amd-test-installation",
                placement="local_linux",
                profile_digest=profile.manifest_digest,
            )
        )

        assert operational.condition is AmdInstallationCondition.OPERATIONAL
        assert operational.profile_usable
        assert [component.capability for component in operational.components] == list(ManifestCapability)
        assert len(placement.materialized) == 1
        assert len(placement.materialized[0]) == len(ManifestCapability)

        removed = deployment.retire("amd-test-installation")

        assert removed.condition is AmdInstallationCondition.REMOVED
        assert removed.lifecycle_state == "removed"
        assert {component.generation_id for component in removed.components} == set(placement.retired)
        assert placement.session.closed
    finally:
        deployment.close()
        engine.dispose()


def test_retirement_only_deployment_rejects_new_installations(tmp_path: Path) -> None:
    engine, catalog, deployment, _placement = _deployment(tmp_path, allow_new_installations=False)
    try:
        with pytest.raises(AmdDeploymentError) as error:
            deployment.prepare(
                AmdInstallationSpec(
                    installation_id="amd-test-installation",
                    placement="local_linux",
                    profile_digest=catalog.profiles[0].manifest_digest,
                )
            )
        assert error.value.error_code == "amd_retirement_only"
    finally:
        deployment.close()
        engine.dispose()


def test_cleanup_only_local_owner_retires_history_but_rejects_new_local_intent(
    tmp_path: Path,
) -> None:
    engine = create_engine_for_path(tmp_path / "amd-local-history.sqlite")
    bootstrap_current_schema(engine)
    session_factory = create_session_factory(engine)
    catalog = load_product_manifest_catalog()
    profile = catalog.profiles[0]
    initial_placement = _FakePlacement(_admitted_facts(catalog))
    initial = AmdAiDeploymentService(
        session_factory=session_factory,
        catalog=catalog,
        placements={initial_placement.placement_kind: initial_placement},
        participants={
            capability: _FakeParticipant(capability)
            for capability in ManifestCapability
        },
        runtime_directory=AmdRuntimeDirectory(),
    )
    try:
        initial.prepare(
            AmdInstallationSpec(
                installation_id="amd-test-installation",
                placement="local_linux",
                profile_digest=profile.manifest_digest,
            )
        )
    finally:
        initial.close()

    cleanup_placement = _FakePlacement(_admitted_facts(catalog))
    cleanup_only = AmdAiDeploymentService(
        session_factory=session_factory,
        catalog=catalog,
        placements={cleanup_placement.placement_kind: cleanup_placement},
        participants={
            capability: _FakeParticipant(capability)
            for capability in ManifestCapability
        },
        runtime_directory=AmdRuntimeDirectory(),
        new_installation_placements=frozenset(),
    )
    try:
        with pytest.raises(AmdDeploymentError) as error:
            cleanup_only.prepare(
                AmdInstallationSpec(
                    installation_id="amd-new-local-installation",
                    placement="local_linux",
                    profile_digest=profile.manifest_digest,
                )
            )
        assert error.value.error_code == "amd_placement_unavailable"
        for operation in (
            cleanup_only.reconcile,
            cleanup_only.repair,
            cleanup_only.resume,
        ):
            with pytest.raises(AmdDeploymentError) as error:
                operation("amd-test-installation")
            assert error.value.error_code == "amd_placement_unavailable"
        with pytest.raises(AmdDeploymentError) as error:
            cleanup_only.prepare_upgrade(
                "amd-test-installation",
                new_profile_digest=profile.manifest_digest,
            )
        assert error.value.error_code == "amd_placement_unavailable"
        assert cleanup_placement.materialized == []

        removed = cleanup_only.retire(
            "amd-test-installation",
            drain_timeout_seconds=None,
        )

        assert removed.condition is AmdInstallationCondition.REMOVED
        assert cleanup_placement.retired
    finally:
        cleanup_only.close()
        engine.dispose()


def test_restart_retirement_marks_missing_control_session_as_blocked(
    tmp_path: Path,
) -> None:
    engine = create_engine_for_path(tmp_path / "amd-blocked-retirement.sqlite")
    bootstrap_current_schema(engine)
    session_factory = create_session_factory(engine)
    catalog = load_product_manifest_catalog()
    profile = catalog.profiles[0]
    initial_placement = _FakePlacement(_admitted_facts(catalog))
    initial = AmdAiDeploymentService(
        session_factory=session_factory,
        catalog=catalog,
        placements={initial_placement.placement_kind: initial_placement},
        participants={
            capability: _FakeParticipant(capability)
            for capability in ManifestCapability
        },
        runtime_directory=AmdRuntimeDirectory(),
    )
    try:
        initial.prepare(
            AmdInstallationSpec(
                installation_id="amd-test-installation",
                placement="local_linux",
                profile_digest=profile.manifest_digest,
            )
        )
    finally:
        initial.close()

    blocked_placement = _BlockedRetirementPlacement(_admitted_facts(catalog))
    restarted = AmdAiDeploymentService(
        session_factory=session_factory,
        catalog=catalog,
        placements={blocked_placement.placement_kind: blocked_placement},
        participants={
            capability: _FakeParticipant(capability)
            for capability in ManifestCapability
        },
        runtime_directory=AmdRuntimeDirectory(),
    )
    try:
        status = restarted.retire(
            "amd-test-installation",
            drain_timeout_seconds=None,
        )

        assert status.condition is AmdInstallationCondition.REMOVAL_BLOCKED
        assert {
            component.error_code
            for component in status.components
        } == {"physical_cleanup_blocked"}
    finally:
        restarted.close()
        engine.dispose()


def test_ocr_descriptor_requires_the_durable_exact_generation(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "amd-ocr.sqlite")
    bootstrap_current_schema(engine)
    session_factory = create_session_factory(engine)
    catalog = load_product_manifest_catalog()
    repository = AmdInstallationRepository()
    ocr_manifest = next(component for component in catalog.components if component.capability is ManifestCapability.OCR)
    profile = catalog.profiles[0]
    try:
        with session_factory() as session:
            session.add(
                AmdInstallationRow(
                    id="amd-test-installation",
                    placement="local_linux",
                    profile_id=profile.profile_id,
                    profile_digest=profile.manifest_digest,
                )
            )
            session.commit()
            session.add(
                AmdComponentGenerationRow(
                    id="amd-test-ocr-generation",
                    installation_id="amd-test-installation",
                    capability=ManifestCapability.OCR.value,
                    manifest_digest=ocr_manifest.manifest_digest,
                    lifecycle_state="registered",
                    phase="registered",
                )
            )
            session.commit()

        reference = ManagedOcrProviderRef(
            manager_id="amd-rocm",
            installation_id="amd-test-installation",
            component_generation_id="amd-test-ocr-generation",
        )
        projection = OcrProviderProjection(
            id="ocr-managed-test",
            display_name="AMD OCR",
            model=ocr_manifest.launch.served_model_name,
            descriptor_fingerprint=ocr_manifest.manifest_digest,
            target=reference,
            read_only=True,
        )
        resolver = _ocr_descriptor_resolver(
            catalog,
            session_factory=session_factory,
            repository=repository,
        )

        descriptor = resolver(reference, projection)

        assert descriptor.generation_id == reference.component_generation_id
        assert descriptor.manifest_digest == ocr_manifest.manifest_digest
        assert descriptor.model_pack_id == ocr_manifest.launch.served_model_name
        with pytest.raises(AmdOcrDescriptorMismatchError):
            resolver(reference, projection.model_copy(update={"descriptor_fingerprint": "0" * 64}))
    finally:
        engine.dispose()
