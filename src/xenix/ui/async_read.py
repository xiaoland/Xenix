"""One UI-owned read channel with stale-delivery suppression and explicit cleanup."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

LOGGER = logging.getLogger(__name__)


def _log_stale_failure(error: Exception) -> None:
    LOGGER.error("Discarded background read failed", exc_info=(type(error), error, error.__traceback__))


class _Signals(QObject):
    finished = Signal(int, object)


class _Read(QRunnable):
    def __init__(self, generation: int, read: Callable[[], object]) -> None:
        super().__init__()
        self.generation = generation
        self.read = read
        self.signals = _Signals()
        self.failure: Exception | None = None

    def run(self) -> None:
        try:
            result = self.read()
        except Exception as exc:
            self.failure = exc
            result = exc
        self.signals.finished.emit(self.generation, result)


class AsyncRead(QObject):
    loaded = Signal(object)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._generation = 0
        self._closed = False
        self._running: _Read | None = None
        self._pending: tuple[int, Callable[[], object]] | None = None

    @property
    def busy(self) -> bool:
        return self._running is not None or self._pending is not None

    def submit(self, read: Callable[[], object]) -> None:
        if self._closed:
            return
        self.invalidate()
        if self._running is not None:
            self._pending = (self._generation, read)
        else:
            self._start(self._generation, read)

    def _start(self, generation: int, read: Callable[[], object]) -> None:
        worker = _Read(generation, read)
        self._running = worker
        worker.signals.finished.connect(self._finished)
        self._pool.start(worker)

    def invalidate(self) -> None:
        self._generation += 1
        self._pending = None

    def _finished(self, generation: int, result: object) -> None:
        self._running = None
        if self._closed:
            return
        if generation == self._generation:
            self.loaded.emit(result)
        elif isinstance(result, Exception):
            _log_stale_failure(result)
        if not self._closed and self._pending is not None and self._running is None:
            pending = self._pending
            self._pending = None
            self._start(*pending)

    def shutdown(self) -> None:
        self._closed = True
        self.invalidate()
        self._pool.waitForDone()
        # The queued completion may disappear when the owner is destroyed.
        if self._running is not None and self._running.failure is not None:
            _log_stale_failure(self._running.failure)
        self._running = None
