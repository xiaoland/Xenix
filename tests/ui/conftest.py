from __future__ import annotations

import os


# QPA is selected when the first QApplication is created. Keep this scoped to
# direct UI contracts so headed Agent Harness runs can continue to use qwindows.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
