from __future__ import annotations

DEVELOPMENT_BUILD_COMMIT = "development"

try:
    from ._generated_build_info import BUILD_COMMIT as _RAW_BUILD_COMMIT
except ModuleNotFoundError as exc:
    if exc.name != "xenix._generated_build_info":
        raise
    _RAW_BUILD_COMMIT = DEVELOPMENT_BUILD_COMMIT


def _normalize_build_commit(value: object) -> str:
    if not isinstance(value, str):
        return DEVELOPMENT_BUILD_COMMIT
    cleaned = value.strip()
    return cleaned or DEVELOPMENT_BUILD_COMMIT


def _display_build_commit(value: str) -> str:
    if value == DEVELOPMENT_BUILD_COMMIT:
        return value
    return value[:12]


BUILD_COMMIT = _normalize_build_commit(_RAW_BUILD_COMMIT)
BUILD_COMMIT_DISPLAY = _display_build_commit(BUILD_COMMIT)
