from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import NotFoundError, ValidationError
from .artifact_service import (
    ActivatedArtifact,
    ArtifactService,
    RegisterArtifactInput,
    build_artifact_uri,
)
from .dataset_service import DatasetService, ExportDatasetCopyInput
from .storage.models import ArtifactKind, ArtifactRow
from .storage.repositories import ArtifactRepository


def build_dataset_uri(dataset_id: str) -> str:
    dataset_id = dataset_id.strip()
    if not dataset_id:
        raise ValidationError("Dataset id cannot be empty.")
    return f"dataset://{dataset_id}"


class DatasetExportActivation(SQLModel):
    dataset_id: str
    artifact_id: str
    artifact_uri: str
    absolute_path: str
    opened: bool


class DatasetExportService:
    def __init__(
        self,
        *,
        paths: AppPaths,
        session_factory: sessionmaker,
        dataset_service: DatasetService,
        artifact_service: ArtifactService,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._dataset_service = dataset_service
        self._artifact_service = artifact_service
        self._artifacts = ArtifactRepository()

    def activate_uri(self, uri: str, *, thread_id: str | None = None) -> DatasetExportActivation:
        dataset_id = self._dataset_id_from_uri(uri)
        return self.activate_dataset(dataset_id, thread_id=thread_id)

    def activate_dataset(self, dataset_id: str, *, thread_id: str | None = None) -> DatasetExportActivation:
        dataset = self._dataset_service.get_dataset(dataset_id)
        artifact = self._find_reusable_workbook_export(dataset.id)
        if artifact is None or not Path(artifact.absolute_path).exists():
            destination_path = self._default_workbook_path(dataset.id, dataset.name)
            self._dataset_service.export_dataset_copy(
                ExportDatasetCopyInput(
                    dataset_id=dataset.id,
                    destination_path=str(destination_path),
                )
            )
            artifact = self._artifact_service.register_artifact(
                RegisterArtifactInput(
                    thread_id=thread_id,
                    kind=ArtifactKind.DATASET,
                    title=dataset.name,
                    absolute_path=str(destination_path.resolve()),
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    metadata_payload={
                        "dataset_id": dataset.id,
                        "dataset_export": {
                            "dataset_id": dataset.id,
                            "format": "xlsx",
                            "source_path": dataset.source_path,
                        },
                    },
                )
            )
        activated = self._artifact_service.activate_uri(build_artifact_uri(artifact.id))
        return self._activation_from_artifact(dataset.id, activated)

    def _find_reusable_workbook_export(self, dataset_id: str) -> ArtifactRow | None:
        with self._session_factory() as session:
            for artifact in self._artifacts.list_by_kind(session, ArtifactKind.DATASET):
                metadata = dict(artifact.metadata_payload or {})
                export = metadata.get("dataset_export")
                if not isinstance(export, dict):
                    continue
                if export.get("dataset_id") == dataset_id and export.get("format") == "xlsx":
                    return artifact
        return None

    def _default_workbook_path(self, dataset_id: str, name: str) -> Path:
        export_dir = self._paths.artifacts / "datasets" / "exports" / dataset_id
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir / f"{self._slug(name) or dataset_id}.xlsx"

    def _dataset_id_from_uri(self, uri: str) -> str:
        parsed = urlparse(uri)
        if parsed.scheme != "dataset":
            raise ValidationError("Dataset URI must use the dataset scheme.")
        dataset_id = (parsed.netloc or parsed.path.lstrip("/").split("/", 1)[0]).strip()
        if not dataset_id:
            raise ValidationError("Dataset URI is missing a dataset id.")
        try:
            self._dataset_service.get_dataset(dataset_id)
        except NotFoundError:
            raise
        return dataset_id

    def _activation_from_artifact(self, dataset_id: str, artifact: ActivatedArtifact) -> DatasetExportActivation:
        return DatasetExportActivation(
            dataset_id=dataset_id,
            artifact_id=artifact.artifact_id,
            artifact_uri=build_artifact_uri(artifact.artifact_id),
            absolute_path=artifact.absolute_path,
            opened=artifact.opened,
        )

    def _slug(self, value: str) -> str:
        normalized = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value.strip(), flags=re.UNICODE)
        normalized = normalized.strip("-._")
        return normalized[:80]
