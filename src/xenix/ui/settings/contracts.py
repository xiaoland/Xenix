from __future__ import annotations

from enum import StrEnum


class SettingsTab(StrEnum):
    AI = "ai"
    KNOWLEDGE_BASE = "knowledge_base"
    ML_WORKERS = "ml_workers"


__all__ = ["SettingsTab"]
