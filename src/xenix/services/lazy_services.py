from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, cast


def lazy_service[T](factory: Callable[[], T]) -> T:
    """Defer a service's construction until its first attribute access.

    Factories keep constructor references and arguments visible to refactoring
    tools and type checking. Use only for ordinary service method/property
    access; the proxy does not forward Python special methods or identity tests.
    Failed construction is not cached and may be retried on the next access.
    """
    return cast(T, _LazyService(factory))


class _LazyService[T]:
    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._service: T | None = None
        self._lock = threading.Lock()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)

    def _resolve(self) -> T:
        service = self._service
        if service is not None:
            return service
        with self._lock:
            service = self._service
            if service is None:
                service = self._factory()
                self._service = service
            return service
