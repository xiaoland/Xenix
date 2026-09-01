"""Settings tab content widgets and the composition dialog."""

from .contracts import SettingsTab
from .dialog import SettingsDialog
from .embedding import EmbeddingSettings
from .index_status import KnowledgeIndexStatus
from .ml_workers import MLWorkers
from .ocr import OcrSettings
from .provider import ProviderSettingsEditor

__all__ = (
    "EmbeddingSettings",
    "KnowledgeIndexStatus",
    "MLWorkers",
    "OcrSettings",
    "ProviderSettingsEditor",
    "SettingsDialog",
    "SettingsTab",
)
