"""Backward-compatible entry point for the Settings dialog surface.

The real implementation lives in :mod:`xenix.ui.settings`; this module only
re-exports the names historically imported from ``xenix.ui.settings_dialog``.
"""

from .about_dialog import AboutDialog
from .settings import SettingsDialog, SettingsTab

__all__ = ["AboutDialog", "SettingsDialog", "SettingsTab"]
