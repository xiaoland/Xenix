from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from ...config import AppPaths
from ...exceptions import ValidationError, report_exception
from ...release_config import ReleaseConfig, load_release_config
from .bundle import (
    PaddleOcrBundleSource,
    ReleasePaddleOcrBundleSource,
    generation_id as build_generation_id,
    load_default_bundle_source,
    matches_catalog_artifact,
    remove_private_tree,
    safe_extract_zip,
    single_bundle_root,
    validate_runtime_manifest,
    verify_runtime_files,
)
from .contracts import (
    ACTIVE_MANIFEST_NAME,
    MAX_STATUS_BYTES,
    NATIVE_OCR_PROTOCOL_VERSION,
    RUNTIME_MANIFEST_NAME,
    VERIFICATION_MAX_AGE_SECONDS,
    VERIFICATION_RECORD_NAME,
    VERIFICATION_SCHEMA_VERSION,
    PaddleOcrBundleCatalog,
    PaddleOcrRuntime,
    PaddleOcrState,
    PaddleOcrStatus,
    bounded_identity,
    bounded_json_file,
    is_sha256,
    resolve_member,
    sha256_file,
    write_json_atomic,
)
from .session import PaddleOcrSession


class PaddleOcrDeploymentService:
    """Activate one immutable, verified native Paddle Inference generation."""

    def __init__(
        self,
        paths: AppPaths,
        *,
        bundle_source: PaddleOcrBundleSource | None = None,
        catalog: PaddleOcrBundleCatalog | None = None,
        release_config: ReleaseConfig | None = None,
    ) -> None:
        if bundle_source is not None and (catalog is not None or release_config is not None):
            raise ValueError("Bundle source cannot be combined with catalog or release configuration.")
        self._paths = paths
        self._root = paths.cache / "knowledge-ocr"
        self._bundles = self._root / "bundles"
        self._downloads = self._root / "downloads"
        self._staging = self._root / "staging"
        self._active_path = self._root / ACTIVE_MANIFEST_NAME
        self._verification_path = self._root / VERIFICATION_RECORD_NAME
        if bundle_source is not None:
            self._bundle_source = bundle_source
        elif catalog is not None:
            # Keep the former catalog/release injection seam as an explicit
            # release-source compatibility path for existing callers.
            self._bundle_source = ReleasePaddleOcrBundleSource(
                catalog,
                release_config or load_release_config(),
            )
        else:
            self._bundle_source = load_default_bundle_source(
                release_config or load_release_config()
            )
        self._state_lock = threading.Lock()
        self._transient_status: PaddleOcrStatus | None = None

    @property
    def catalog(self) -> PaddleOcrBundleCatalog | None:
        source = self._bundle_source
        return source.catalog if source is not None else None

    @property
    def bundle_source(self) -> PaddleOcrBundleSource | None:
        return self._bundle_source

    def status_snapshot(self) -> PaddleOcrStatus:
        with self._state_lock:
            transient = self._transient_status
        if transient is not None:
            return transient
        try:
            runtime = self._resolve_active_runtime()
        except FileNotFoundError:
            return PaddleOcrStatus(PaddleOcrState.NOT_INSTALLED, "runtime_missing")
        except (OSError, TypeError, ValueError):
            return PaddleOcrStatus(PaddleOcrState.REPAIR_REQUIRED, "runtime_manifest_invalid")
        catalog = self.catalog
        if catalog is not None and (
            runtime.runtime_id != catalog.runtime_id
            or runtime.model_pack_id != catalog.model_pack_id
        ):
            return PaddleOcrStatus(
                PaddleOcrState.REPAIR_REQUIRED,
                "runtime_catalog_incompatible",
                runtime.runtime_id,
                runtime.model_pack_id,
                runtime.generation_id,
            )
        verification_reason = self._verification_reason(runtime)
        if verification_reason is not None:
            return PaddleOcrStatus(
                PaddleOcrState.CHECKING,
                verification_reason,
                runtime.runtime_id,
                runtime.model_pack_id,
                runtime.generation_id,
            )
        return PaddleOcrStatus(
            PaddleOcrState.READY,
            runtime_id=runtime.runtime_id,
            model_pack_id=runtime.model_pack_id,
            generation_id=runtime.generation_id,
        )

    def install(self, progress: Callable[[str], None] | None = None) -> PaddleOcrStatus:
        source = self._bundle_source
        if source is None:
            raise ValidationError(
                "Local OCR is unavailable in this build.",
                error_code="knowledge_ocr_catalog_unavailable",
            )
        source.ensure_available()
        catalog = source.catalog
        report = progress or (lambda _phase: None)
        self._set_transient(PaddleOcrStatus(PaddleOcrState.INSTALLING, "starting"))
        staging_root = self._staging / uuid4().hex
        try:
            for directory in (self._root, self._bundles, self._downloads, self._staging):
                directory.mkdir(parents=True, exist_ok=True)
            report("downloading_bundle")
            archive = self._materialize_verified_bundle(source)
            report("extracting_bundle")
            extracted = staging_root / "extracted"
            extracted.mkdir(parents=True)
            safe_extract_zip(archive, extracted)
            candidate = single_bundle_root(extracted)
            report("verifying_bundle")
            runtime = self._runtime_from_generation(
                candidate,
                generation_id=build_generation_id(catalog),
                expected_catalog=catalog,
                verify_all_files=True,
            )
            generation_path = self._bundles / runtime.generation_id
            if generation_path.exists():
                remove_private_tree(generation_path, root=self._bundles)
            os.replace(candidate, generation_path)
            activated = self._runtime_from_generation(
                generation_path,
                generation_id=runtime.generation_id,
                expected_catalog=catalog,
                verify_all_files=False,
            )
            report("self_testing")
            try:
                # Paddle resolves model members from their final filesystem path.
                # A staging-path self-test cannot prove that the activated Windows
                # path remains usable (notably around native path-length limits).
                self._self_test(activated)
            except Exception:
                remove_private_tree(generation_path, root=self._bundles)
                raise
            report("activating_bundle")
            write_json_atomic(
                self._active_path,
                {
                    "schema_version": 1,
                    "generation_id": activated.generation_id,
                    "runtime_id": activated.runtime_id,
                    "model_pack_id": activated.model_pack_id,
                    "manifest_sha256": activated.manifest_sha256,
                    "artifact_sha256": catalog.artifact_sha256,
                },
            )
            self._write_verification_record(activated)
            status = PaddleOcrStatus(
                PaddleOcrState.READY,
                runtime_id=activated.runtime_id,
                model_pack_id=activated.model_pack_id,
                generation_id=activated.generation_id,
            )
            report("ready")
            return status
        except ValidationError:
            self._set_transient(PaddleOcrStatus(PaddleOcrState.FAILED, "setup_failed"))
            raise
        except Exception as exc:
            self._set_transient(PaddleOcrStatus(PaddleOcrState.FAILED, "setup_failed"))
            raise ValidationError(
                "Local OCR setup failed.",
                error_code="knowledge_ocr_setup_failed",
            ) from exc
        finally:
            if staging_root.exists():
                remove_private_tree(staging_root, root=self._staging)
            self._clear_transient_if(PaddleOcrState.INSTALLING)

    def verify_active(self) -> PaddleOcrStatus:
        self._set_transient(PaddleOcrStatus(PaddleOcrState.CHECKING, "verifying"))
        try:
            runtime = self._resolve_active_runtime(verify_all_files=True)
            self._self_test(runtime)
            self._write_verification_record(runtime)
            return PaddleOcrStatus(
                PaddleOcrState.READY,
                runtime_id=runtime.runtime_id,
                model_pack_id=runtime.model_pack_id,
                generation_id=runtime.generation_id,
            )
        except FileNotFoundError:
            return PaddleOcrStatus(PaddleOcrState.NOT_INSTALLED, "runtime_missing")
        except Exception as exc:
            report_exception(exc)
            return PaddleOcrStatus(PaddleOcrState.REPAIR_REQUIRED, "verification_failed")
        finally:
            self._clear_transient_if(PaddleOcrState.CHECKING)

    def open_runtime(self) -> PaddleOcrRuntime:
        try:
            runtime = self._resolve_active_runtime()
        except FileNotFoundError as exc:
            raise ValidationError(
                "Local OCR is not installed.",
                error_code="knowledge_ocr_not_installed",
            ) from exc
        except (OSError, TypeError, ValueError) as exc:
            raise ValidationError(
                "Local OCR requires repair.",
                error_code="knowledge_ocr_repair_required",
            ) from exc
        if self._verification_reason(runtime) is not None:
            raise ValidationError(
                "Local OCR verification is required.",
                error_code="knowledge_ocr_verification_required",
                retryable=True,
            )
        return runtime

    def _verification_reason(self, runtime: PaddleOcrRuntime) -> str | None:
        try:
            payload = bounded_json_file(self._verification_path)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            return "verification_required"
        expected = {
            "schema_version",
            "generation_id",
            "runtime_id",
            "model_pack_id",
            "engine_version",
            "protocol_version",
            "manifest_sha256",
            "verified_at",
        }
        if not isinstance(payload, dict) or payload.keys() != expected:
            return "verification_required"
        verified_at = payload.get("verified_at")
        if type(verified_at) not in {int, float} or float(verified_at) <= 0:
            return "verification_required"
        if time.time() - float(verified_at) > VERIFICATION_MAX_AGE_SECONDS:
            return "verification_stale"
        if (
            payload.get("schema_version") != VERIFICATION_SCHEMA_VERSION
            or payload.get("generation_id") != runtime.generation_id
            or payload.get("runtime_id") != runtime.runtime_id
            or payload.get("model_pack_id") != runtime.model_pack_id
            or payload.get("engine_version") != runtime.engine_version
            or payload.get("protocol_version") != NATIVE_OCR_PROTOCOL_VERSION
            or payload.get("manifest_sha256") != runtime.manifest_sha256
        ):
            return "verification_required"
        return None

    def _write_verification_record(self, runtime: PaddleOcrRuntime) -> None:
        write_json_atomic(
            self._verification_path,
            {
                "schema_version": VERIFICATION_SCHEMA_VERSION,
                "generation_id": runtime.generation_id,
                "runtime_id": runtime.runtime_id,
                "model_pack_id": runtime.model_pack_id,
                "engine_version": runtime.engine_version,
                "protocol_version": NATIVE_OCR_PROTOCOL_VERSION,
                "manifest_sha256": runtime.manifest_sha256,
                "verified_at": time.time(),
            },
        )

    def _set_transient(self, status: PaddleOcrStatus | None) -> None:
        with self._state_lock:
            self._transient_status = status

    def _clear_transient_if(self, state: PaddleOcrState) -> None:
        with self._state_lock:
            if self._transient_status is not None and self._transient_status.state is state:
                self._transient_status = None

    def _materialize_verified_bundle(
        self,
        source: PaddleOcrBundleSource,
    ) -> Path:
        catalog = source.catalog
        source.ensure_available()
        target = self._downloads / catalog.artifact_name
        if matches_catalog_artifact(target, catalog):
            return target
        partial = target.with_suffix(target.suffix + ".part")
        partial.unlink(missing_ok=True)
        try:
            source.materialize(partial)
            if not matches_catalog_artifact(partial, catalog):
                raise ValidationError(
                    "Local OCR bundle failed integrity verification.",
                    error_code="knowledge_ocr_bundle_integrity_failed",
                )
            os.replace(partial, target)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return target

    def _resolve_active_runtime(self, *, verify_all_files: bool = False) -> PaddleOcrRuntime:
        if not self._active_path.is_file():
            raise FileNotFoundError(self._active_path)
        active = bounded_json_file(self._active_path)
        if not isinstance(active, dict) or active.keys() != {
            "schema_version",
            "generation_id",
            "runtime_id",
            "model_pack_id",
            "manifest_sha256",
            "artifact_sha256",
        }:
            raise ValueError("Active native OCR pointer is invalid.")
        if active.get("schema_version") != 1:
            raise ValueError("Active native OCR pointer is incompatible.")
        active_generation_id = bounded_identity(active.get("generation_id"))
        runtime = self._runtime_from_generation(
            self._bundles / active_generation_id,
            generation_id=active_generation_id,
            expected_catalog=None,
            verify_all_files=verify_all_files,
        )
        if (
            runtime.runtime_id != active.get("runtime_id")
            or runtime.model_pack_id != active.get("model_pack_id")
            or runtime.manifest_sha256 != active.get("manifest_sha256")
            or not is_sha256(active.get("artifact_sha256"))
        ):
            raise ValueError("Active native OCR identity is inconsistent.")
        return runtime

    def _runtime_from_generation(
        self,
        generation_path: Path,
        *,
        generation_id: int,
        expected_catalog: PaddleOcrBundleCatalog | None,
        verify_all_files: bool,
    ) -> PaddleOcrRuntime:
        manifest_path = generation_path / RUNTIME_MANIFEST_NAME
        payload = bounded_json_file(manifest_path, max_bytes=MAX_STATUS_BYTES)
        manifest = validate_runtime_manifest(payload)
        manifest_sha256 = sha256_file(manifest_path)
        if expected_catalog is not None and (
            manifest["protocol_version"] != expected_catalog.protocol_version
            or manifest["runtime_id"] != expected_catalog.runtime_id
            or manifest["model_pack_id"] != expected_catalog.model_pack_id
        ):
            raise ValueError("Native OCR bundle identity does not match its catalog.")
        executable = resolve_member(generation_path, manifest["executable"])
        detection = resolve_member(generation_path, manifest["models"]["detection"])
        recognition = resolve_member(generation_path, manifest["models"]["recognition"])
        if not executable.is_file() or not detection.is_dir() or not recognition.is_dir():
            raise ValueError("Native OCR bundle is incomplete.")
        if verify_all_files:
            verify_runtime_files(generation_path, manifest)
        return PaddleOcrRuntime(
            generation_id=generation_id,
            generation_path=generation_path,
            executable_path=executable,
            detection_model_path=detection,
            recognition_model_path=recognition,
            runtime_id=manifest["runtime_id"],
            model_pack_id=manifest["model_pack_id"],
            engine_version=manifest["engine_version"],
            manifest_sha256=manifest_sha256,
        )

    def _self_test(self, runtime: PaddleOcrRuntime) -> None:
        log_path = self._staging / f"self-test-{uuid4().hex}.log"
        succeeded = False
        try:
            with PaddleOcrSession(runtime, allowed_root=runtime.generation_path, log_path=log_path) as session:
                result = session.request("self_test", {}, timeout=120)
            if not isinstance(result, dict) or result.get("success") is not True:
                raise ValidationError(
                    "Local OCR self-test failed.",
                    error_code="knowledge_ocr_self_test_failed",
                )
            succeeded = True
        finally:
            if succeeded:
                log_path.unlink(missing_ok=True)
