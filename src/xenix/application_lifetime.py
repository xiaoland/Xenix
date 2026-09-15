"""Own resources from their acquisition through startup failure or normal close."""

from collections.abc import Callable
from contextlib import ExitStack
import logging


LOGGER = logging.getLogger(__name__)


class ApplicationLifetime:
    """Release in reverse acquisition order, once, continuing after cleanup errors.

    Register resources immediately after acquiring them. Both startup failure and
    window/application close use this same owner; cleanup never hides the startup
    exception or prevents another resource from being released.
    """

    def __init__(self) -> None:
        self._stack = ExitStack()
        self._closed = False

    def add_cleanup(self, label: str, cleanup: Callable[[], object]) -> None:
        if self._closed:
            raise RuntimeError("Cannot add resources to a closed application lifetime.")
        self._stack.callback(self._release, label, cleanup)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stack.close()

    @staticmethod
    def _release(label: str, cleanup: Callable[[], object]) -> None:
        try:
            cleanup()
        except Exception:
            LOGGER.exception("Application resource cleanup failed: %s", label)
