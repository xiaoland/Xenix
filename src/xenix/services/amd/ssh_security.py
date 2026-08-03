"""AMD-owned enrollment handles for Private SSH placements.

SQLite owns the durable target identity and only stores opaque references to
local security material.  This module owns the small settings document behind
those references: an absolute identity-file *path* and a pinned public host
key.  It never reads private-key bytes, never performs SSH discovery, and never
persists a password, token, or endpoint binding.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from pathlib import Path

from sqlmodel import Session

from ..settings_store import SettingsConflictError, SettingsSnapshot, SettingsStore, SettingsStoreError
from ..storage.models import AmdTargetEnrollmentRow
from ..storage.repositories.amd_installations import AmdInstallationRepository
from .placements.ssh import (
    PinnedHostKey,
    ResolvedSshIdentity,
    SshCredentialResolver,
    SshTargetEnrollment,
    SshTargetResolutionError,
    SshTargetResolver,
    SshTrustResolver,
)


_DOCUMENT_ID = "amd_ssh_security.json"
_SCHEMA_VERSION = 1
_REFERENCE_PREFIX = "amd-private-target:"
_MAX_TARGETS = 128


class AmdSshSecurityError(RuntimeError):
    """A local Private SSH enrollment handle could not be used safely."""


class AmdSshSecurityStore:
    """One app-scoped store for opaque Private SSH enrollment material."""

    def __init__(self, store: SettingsStore) -> None:
        if not isinstance(store, SettingsStore):
            raise TypeError("AMD SSH security requires the app settings store.")
        self._store = store
        self._lock = threading.RLock()
        self._closed = False

    def close(self) -> None:
        """Fence later settings access before the app closes its store."""

        with self._lock:
            self._closed = True

    def record(
        self,
        *,
        target_id: str,
        identity_file: Path,
        host_key: PinnedHostKey,
    ) -> tuple[str, str]:
        """Persist non-secret local handles and return stable opaque refs."""

        normalized_target_id = _require_target_id(target_id)
        path = _require_identity_path(identity_file)
        if not isinstance(host_key, PinnedHostKey):
            raise AmdSshSecurityError("Pinned SSH host key is invalid.")
        reference = _reference_for_target(normalized_target_id)
        record = {
            "identity_file": str(path),
            "host_key_type": host_key.key_type,
            "host_key_data": host_key.key_data,
        }
        with self._lock:
            self._require_open()
            for _attempt in range(8):
                snapshot = self._load()
                current = _payload_from_snapshot(snapshot)
                targets = dict(current["targets"])
                existing = targets.get(normalized_target_id)
                if existing is not None and existing != record:
                    raise AmdSshSecurityError("Private SSH target security material is already enrolled.")
                if existing == record:
                    return reference, reference
                if len(targets) >= _MAX_TARGETS:
                    raise AmdSshSecurityError("Too many Private SSH targets are enrolled.")
                targets[normalized_target_id] = record
                next_payload = {"schema_version": _SCHEMA_VERSION, "targets": targets}
                try:
                    self._store.compare_and_swap(
                        _DOCUMENT_ID,
                        snapshot.revision,
                        lambda _payload, payload=next_payload: payload,
                    )
                    return reference, reference
                except SettingsConflictError:
                    continue
                except SettingsStoreError as exc:
                    raise AmdSshSecurityError("Private SSH security material could not be saved.") from exc
        raise AmdSshSecurityError("Private SSH security material changed repeatedly; retry enrollment.")

    def resolve_identity(self, reference: str) -> ResolvedSshIdentity:
        record = self._record(reference)
        try:
            return ResolvedSshIdentity(identity_file=Path(record["identity_file"]))
        except (KeyError, TypeError, ValueError, SshTargetResolutionError) as exc:
            raise AmdSshSecurityError("Private SSH identity handle is invalid.") from exc

    def resolve_host_key(self, reference: str) -> PinnedHostKey:
        record = self._record(reference)
        try:
            return PinnedHostKey(
                key_type=record["host_key_type"],
                key_data=record["host_key_data"],
            )
        except (KeyError, TypeError, ValueError, SshTargetResolutionError) as exc:
            raise AmdSshSecurityError("Pinned SSH host key is invalid.") from exc

    def _record(self, reference: str) -> Mapping[str, str]:
        target_id = _target_id_from_reference(reference)
        with self._lock:
            self._require_open()
            payload = _payload_from_snapshot(self._load())
        record = payload["targets"].get(target_id)
        if not isinstance(record, Mapping):
            raise AmdSshSecurityError("Private SSH target security material is unavailable.")
        expected_fields = {"identity_file", "host_key_type", "host_key_data"}
        if set(record) != expected_fields or not all(isinstance(record[field], str) for field in expected_fields):
            raise AmdSshSecurityError("Private SSH target security material is invalid.")
        return {field: record[field] for field in expected_fields}

    def _load(self) -> SettingsSnapshot:
        try:
            return self._store.load(_DOCUMENT_ID)
        except SettingsStoreError as exc:
            raise AmdSshSecurityError("Private SSH security material could not be read.") from exc

    def _require_open(self) -> None:
        if self._closed:
            raise AmdSshSecurityError("Private SSH security store is closed.")


class AmdSqliteSshTargetResolver(SshTargetResolver):
    """Resolve a persisted enrollment row into the narrow SSH target port."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        repository: AmdInstallationRepository | None = None,
    ) -> None:
        if not callable(session_factory):
            raise TypeError("AMD SSH target resolver requires a session factory.")
        self._session_factory = session_factory
        self._repository = repository or AmdInstallationRepository()
        self._lock = threading.RLock()
        self._closed = False

    def close(self) -> None:
        """Fence later SQLite access before the app disposes its engine."""

        with self._lock:
            self._closed = True

    def resolve_target(self, target_id: str) -> SshTargetEnrollment:
        _require_target_id(target_id)
        try:
            with self._lock:
                if self._closed:
                    raise SshTargetResolutionError("Private SSH target resolver is closed.")
                with self._session_factory() as session:
                    row = self._repository.get_target(session, target_id)
        except Exception as exc:
            raise SshTargetResolutionError("Private SSH target could not be resolved.") from exc
        if not isinstance(row, AmdTargetEnrollmentRow):
            raise SshTargetResolutionError("Private SSH target is unavailable.")
        try:
            return SshTargetEnrollment(
                target_id=row.id,
                host=row.host,
                user=row.user,
                port=row.port,
                pinned_host_key_reference=row.pinned_host_key,
                identity_file_reference=row.identity_file_reference,
            )
        except (TypeError, ValueError, SshTargetResolutionError) as exc:
            raise SshTargetResolutionError("Private SSH target is invalid.") from exc


class AmdSettingsSshCredentialResolver(SshCredentialResolver):
    """Resolve only a local key-file path; private-key content stays in OpenSSH."""

    def __init__(self, security_store: AmdSshSecurityStore) -> None:
        self._security_store = security_store

    def resolve_identity(self, identity_file_reference: str) -> ResolvedSshIdentity:
        try:
            return self._security_store.resolve_identity(identity_file_reference)
        except AmdSshSecurityError as exc:
            raise SshTargetResolutionError("Private SSH identity is unavailable.") from exc


class AmdSettingsSshTrustResolver(SshTrustResolver):
    """Resolve an enrolled host key without TOFU, DNS, or known-hosts reuse."""

    def __init__(self, security_store: AmdSshSecurityStore) -> None:
        self._security_store = security_store

    def resolve_host_key(self, pinned_host_key_reference: str) -> PinnedHostKey:
        try:
            return self._security_store.resolve_host_key(pinned_host_key_reference)
        except AmdSshSecurityError as exc:
            raise SshTargetResolutionError("Pinned SSH host key is unavailable.") from exc


def parse_pinned_host_key(value: str) -> PinnedHostKey:
    """Parse a copied OpenSSH public key, discarding an optional comment."""

    if not isinstance(value, str) or "\x00" in value or "\r" in value or "\n" in value:
        raise AmdSshSecurityError("Pinned SSH host key is invalid.")
    fields = value.strip().split()
    if len(fields) not in {2, 3}:
        raise AmdSshSecurityError("Pinned SSH host key is invalid.")
    try:
        return PinnedHostKey(key_type=fields[0], key_data=fields[1])
    except SshTargetResolutionError as exc:
        raise AmdSshSecurityError("Pinned SSH host key is invalid.") from exc


def _payload_from_snapshot(snapshot: SettingsSnapshot) -> dict[str, object]:
    payload = snapshot.payload
    if payload == {}:
        return {"schema_version": _SCHEMA_VERSION, "targets": {}}
    if not isinstance(payload, Mapping) or set(payload) != {"schema_version", "targets"}:
        raise AmdSshSecurityError("Private SSH security document is invalid.")
    if payload.get("schema_version") != _SCHEMA_VERSION or not isinstance(payload.get("targets"), Mapping):
        raise AmdSshSecurityError("Private SSH security document is invalid.")
    targets = payload["targets"]
    if len(targets) > _MAX_TARGETS or not all(isinstance(key, str) for key in targets):
        raise AmdSshSecurityError("Private SSH security document is invalid.")
    return {"schema_version": _SCHEMA_VERSION, "targets": dict(targets)}


def _require_target_id(value: str) -> str:
    try:
        # SshTargetEnrollment centralizes the target-id grammar while this
        # store intentionally remains independent from endpoint details.
        return SshTargetEnrollment(
            target_id=value,
            host="127.0.0.1",
            user="xenix",
            port=22,
            pinned_host_key_reference="validation",
            identity_file_reference="validation",
        ).target_id
    except SshTargetResolutionError as exc:
        raise AmdSshSecurityError("Private SSH target ID is invalid.") from exc


def _require_identity_path(value: Path) -> Path:
    path = Path(value)
    rendered = str(path)
    if (
        not path.is_absolute()
        or "\x00" in rendered
        or "\r" in rendered
        or "\n" in rendered
        or len(rendered) > 2_048
    ):
        raise AmdSshSecurityError("Private SSH identity path is invalid.")
    return path


def _reference_for_target(target_id: str) -> str:
    return _REFERENCE_PREFIX + target_id


def _target_id_from_reference(reference: str) -> str:
    if not isinstance(reference, str) or not reference.startswith(_REFERENCE_PREFIX):
        raise AmdSshSecurityError("Private SSH security reference is invalid.")
    return _require_target_id(reference.removeprefix(_REFERENCE_PREFIX))


__all__ = [
    "AmdSettingsSshCredentialResolver",
    "AmdSettingsSshTrustResolver",
    "AmdSqliteSshTargetResolver",
    "AmdSshSecurityError",
    "AmdSshSecurityStore",
    "parse_pinned_host_key",
]
