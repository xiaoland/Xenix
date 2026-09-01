"""Settings tab cards and the composition dialog."""

from .contracts import SettingsTab
from .dialog import SettingsDialog
from .embedding import EmbeddingSettingsCard
from .index_status import KnowledgeIndexStatusCard
from .ml_workers import MLWorkersCard
from .ocr import OcrSettingsCard
from .provider import ProviderSettingsEditor

__all__ = (
    "EmbeddingSettingsCard",
    "KnowledgeIndexStatusCard",
    "MLWorkersCard",
    "OcrSettingsCard",
    "ProviderSettingsEditor",
    "SettingsDialog",
    "SettingsTab",
)
