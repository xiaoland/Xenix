"""Shared path anchors for the Xenix test suite.

Test support only; production code must never import this module.  It gives
nested test modules stable handles on the repository root and the shared
``tests/fixtures/`` tree so physical depth under ``tests/`` never leaks into
fixture or script resolution.
"""

from __future__ import annotations

from pathlib import Path

# tests/support/paths.py -> [0]=support, [1]=tests, [2]=repository root
TESTS_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TESTS_ROOT.parent
FIXTURES_ROOT = TESTS_ROOT / "fixtures"


def project_script(name: str) -> Path:
    """Resolve a repository ``scripts/`` entry by file name."""
    return PROJECT_ROOT / "scripts" / name


def fixture_path(*parts: str) -> Path:
    """Resolve a shared fixture under ``tests/fixtures/``."""
    return FIXTURES_ROOT.joinpath(*parts)
