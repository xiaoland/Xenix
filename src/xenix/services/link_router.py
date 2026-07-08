from __future__ import annotations

import webbrowser
from urllib.parse import urlparse

from sqlmodel import SQLModel

from ..exceptions import ValidationError
from .artifact_service import ArtifactService
from .dataset_export_service import DatasetExportService


class LinkActivationResult(SQLModel):
    uri: str
    scheme: str
    opened: bool
    artifact_id: str | None = None
    dataset_id: str | None = None


class LinkRouter:
    def __init__(
        self,
        *,
        artifact_service: ArtifactService,
        dataset_export_service: DatasetExportService,
    ) -> None:
        self._artifact_service = artifact_service
        self._dataset_export_service = dataset_export_service

    def activate(self, uri: str, *, thread_id: str | None = None) -> LinkActivationResult:
        parsed = urlparse(uri)
        scheme = parsed.scheme
        if scheme == "artifact":
            artifact = self._artifact_service.activate_uri(uri)
            return LinkActivationResult(
                uri=uri,
                scheme=scheme,
                opened=artifact.opened,
                artifact_id=artifact.artifact_id,
            )
        if scheme == "dataset":
            export = self._dataset_export_service.activate_uri(uri, thread_id=thread_id)
            return LinkActivationResult(
                uri=uri,
                scheme=scheme,
                opened=export.opened,
                artifact_id=export.artifact_id,
                dataset_id=export.dataset_id,
            )
        if not uri.strip():
            raise ValidationError("Link URI cannot be empty.")
        opened = webbrowser.open(uri)
        if not opened:
            raise ValidationError(f"Could not open link: {uri}")
        return LinkActivationResult(uri=uri, scheme=scheme, opened=True)
