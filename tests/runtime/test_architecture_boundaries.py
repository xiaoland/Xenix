"""Mechanically enforced architecture boundaries and module-size guardrails."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.support.paths import PROJECT_ROOT

_SRC_ROOT = PROJECT_ROOT / "src" / "xenix"
_SERVICES_ROOT = _SRC_ROOT / "services"
_UI_ROOT = _SRC_ROOT / "ui"
_DEPLOYMENT_DOCS_ROOT = PROJECT_ROOT / "docs" / "40-deployment"

_MAX_SOURCE_MODULE_LINES = 1000


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel_parts = path.relative_to(_SRC_ROOT.parent).with_suffix("").parts
    package_parts = rel_parts[:-1] if rel_parts[-1] != "__init__" else rel_parts[:-1]
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                anchor = package_parts[: len(package_parts) - (node.level - 1)]
                base = ".".join(anchor + ((node.module,) if node.module else ()))
                if base:
                    imports.add(base)
                for alias in node.names:
                    if alias.name != "*":
                        imports.add(f"{base}.{alias.name}" if base else alias.name)
            elif node.module:
                imports.add(node.module)
    return imports


def test_services_layer_never_imports_ui_or_qt() -> None:
    violations: list[str] = []
    for path in sorted(_SERVICES_ROOT.rglob("*.py")):
        for module in sorted(_imported_modules(path)):
            if module == "PySide6" or module.startswith("PySide6.") or module == "xenix.ui" or module.startswith("xenix.ui."):
                violations.append(f"{path.relative_to(PROJECT_ROOT)} -> {module}")
    assert not violations, "Services must stay UI/Qt-free:\n" + "\n".join(violations)


def test_ui_layer_never_imports_storage_or_orm_directly() -> None:
    forbidden_roots = ("xenix.services.storage", "sqlalchemy", "sqlmodel", "sqlite3")
    violations: list[str] = []
    for path in sorted(_UI_ROOT.rglob("*.py")):
        for module in sorted(_imported_modules(path)):
            if any(module == root or module.startswith(f"{root}.") for root in forbidden_roots):
                violations.append(f"{path.relative_to(PROJECT_ROOT)} -> {module}")
    assert not violations, "UI must access data through services, not storage/ORM:\n" + "\n".join(violations)


def test_deployment_docs_do_not_reference_volatile_tasks() -> None:
    link_pattern = re.compile(r"\btasks/")
    violations: list[str] = []
    for path in sorted(_DEPLOYMENT_DOCS_ROOT.glob("*.md")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # Ignore runtime data directory paths like artifacts/knowledge/tasks/imports/...
            if "artifacts/knowledge/tasks/" in line:
                continue
            if link_pattern.search(line):
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}: {line.strip()}")
    assert not violations, "Deployment runbooks must not reference volatile tasks/:\n" + "\n".join(violations)


def test_source_modules_stay_under_size_ceiling() -> None:
    oversized: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > _MAX_SOURCE_MODULE_LINES:
            oversized.append(f"{path.relative_to(PROJECT_ROOT)}: {line_count} lines")
    assert not oversized, (
        f"Source modules must stay <= {_MAX_SOURCE_MODULE_LINES} lines:\n" + "\n".join(oversized)
    )


def test_tests_do_not_import_private_agent_tool_modules() -> None:
    forbidden = (
        "xenix.services.agent._model_tools",
        "xenix.services.agent._analysis_tools",
        "xenix.services.agent._data_tools",
    )
    tests_root = PROJECT_ROOT / "tests"
    violations: list[str] = []
    for path in sorted(tests_root.rglob("*.py")):
        if "e2e" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if any(name == root or name.startswith(f"{root}.") for root in forbidden):
                    violations.append(f"{path.relative_to(PROJECT_ROOT)} -> {name}")
    assert not violations, (
        "Tests must invoke agent tools through the public registry/builder instead of private tool modules:\n"
        + "\n".join(violations)
    )
