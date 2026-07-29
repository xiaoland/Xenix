"""Placement-neutral reconciliation ports for the AMD control plane.

The deployment facade owns durable lifecycle transitions.  A placement driver
owns observation, target acquisition, process realization, live bindings, and
exact cleanup.  This small contract keeps those concerns independent without a
generic inference gateway or a mutable endpoint registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .compatibility import TargetCompatibilityFacts
from .manifests import ComponentManifest, ExecutionProfileManifest, ManifestCapability
from .placement import AmdExecutionSession


@dataclass(frozen=True, slots=True)
class AmdGenerationMaterialization:
    """Exact durable generation/recipe pair given to one placement realization."""

    capability: ManifestCapability
    generation_id: str
    manifest: ComponentManifest


class AmdCancellationSignal(Protocol):
    """Volatile signal used only to stop a committed retirement race."""

    def is_set(self) -> bool: ...


class AmdPlacementController(Protocol):
    """A Local or Private placement implementation owned by the AMD slice."""

    @property
    def placement_kind(self) -> str: ...

    def observe(
        self,
        *,
        profile: ExecutionProfileManifest,
        target_id: str | None,
    ) -> TargetCompatibilityFacts: ...

    def materialize(
        self,
        *,
        installation_id: str,
        target_id: str | None,
        profile: ExecutionProfileManifest,
        generations: tuple[AmdGenerationMaterialization, ...],
        cancellation: AmdCancellationSignal | None = None,
    ) -> AmdExecutionSession: ...

    def open_retirement_session(
        self,
        *,
        installation_id: str,
        target_id: str | None,
        profile: ExecutionProfileManifest,
        generations: tuple[AmdGenerationMaterialization, ...],
    ) -> AmdExecutionSession: ...

    def self_test(
        self,
        *,
        session: AmdExecutionSession,
        generation: AmdGenerationMaterialization,
    ) -> str: ...

    def cancel_generation_provisioning(
        self,
        *,
        session: AmdExecutionSession,
        installation_id: str,
        profile: ExecutionProfileManifest,
        generation: AmdGenerationMaterialization,
    ) -> None: ...

    def retire_generation(
        self,
        *,
        session: AmdExecutionSession,
        installation_id: str,
        profile: ExecutionProfileManifest,
        generation: AmdGenerationMaterialization,
    ) -> None: ...


__all__ = [
    "AmdGenerationMaterialization",
    "AmdCancellationSignal",
    "AmdPlacementController",
]
