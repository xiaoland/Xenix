from __future__ import annotations


# Registration is global because pytest 9 forbids pytest_plugins in a nested
# conftest. The plugin is inert unless a test explicitly requests ui_artifacts;
# QPA selection remains scoped to tests/ui/conftest.py.
pytest_plugins = ["pytester", "tests.ui.pytest_plugin"]
