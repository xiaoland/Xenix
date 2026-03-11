from __future__ import annotations

from collections.abc import Callable
from multiprocessing import get_context
from pathlib import Path


class MLWorkerRunner:
    def run(self, entrypoint: Callable[[str], None], task_dir: Path) -> int:
        context = get_context("spawn")
        process = context.Process(target=entrypoint, args=(str(task_dir),))
        process.start()
        process.join()
        return process.exitcode or 0
