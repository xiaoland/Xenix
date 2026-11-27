from __future__ import annotations

import gc
import logging
import os
import shutil
import time
from pathlib import Path

from .contracts import KnowledgeVectorStoreError

_WINDOWS_SHARING_VIOLATIONS = frozenset({5, 32, 33})
_WINDOWS_REPARSE_POINT = 0x0400
_SHARING_RETRY_DELAYS = (0.02, 0.08)


def assert_within(path: Path, root: Path) -> None:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_root or not resolved_path.is_relative_to(resolved_root):
        raise KnowledgeVectorStoreError()


def is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    if path.is_symlink() or bool(is_junction and is_junction()):
        return True
    if os.name != "nt":
        return False
    try:
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0))
    except FileNotFoundError:
        return False
    return bool(attributes & _WINDOWS_REPARSE_POINT)


def discard_exception_traceback(exc: Exception) -> None:
    """Drop frames that may otherwise retain native Lance/Arrow handles."""
    logging.getLogger(__name__).error(
        "Knowledge vector operation failed",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    exc.__traceback__ = None
    exc.__cause__ = None
    exc.__context__ = None


def is_windows_sharing_violation(exc: OSError) -> bool:
    return (
        getattr(exc, "winerror", None) in _WINDOWS_SHARING_VIOLATIONS
        or isinstance(exc, PermissionError)
    )


def replace_with_retries(source: Path, target: Path) -> bool:
    for attempt in range(len(_SHARING_RETRY_DELAYS) + 1):
        try:
            os.replace(source, target)
            return True
        except FileNotFoundError:
            if not source.exists() and not is_link_like(source):
                return False
            raise KnowledgeVectorStoreError() from None
        except OSError as exc:
            if not is_windows_sharing_violation(exc):
                raise KnowledgeVectorStoreError() from None
            discard_exception_traceback(exc)
            if attempt >= len(_SHARING_RETRY_DELAYS):
                raise KnowledgeVectorStoreError() from None
            gc.collect()
            time.sleep(_SHARING_RETRY_DELAYS[attempt])
    return False


def remove_path_with_retries(path: Path, *, best_effort: bool) -> bool:
    for attempt in range(len(_SHARING_RETRY_DELAYS) + 1):
        try:
            if is_link_like(path):
                return False
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
            else:
                return True
            return True
        except FileNotFoundError:
            return True
        except OSError as exc:
            retryable = is_windows_sharing_violation(exc)
            discard_exception_traceback(exc)
            if not retryable or attempt >= len(_SHARING_RETRY_DELAYS):
                if best_effort:
                    return False
                raise KnowledgeVectorStoreError() from None
            gc.collect()
            time.sleep(_SHARING_RETRY_DELAYS[attempt])
    return False
