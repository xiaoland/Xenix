from __future__ import annotations

from collections.abc import Callable
from multiprocessing import get_context
from pathlib import Path


class MLWorkerRunner:
    def run(
        self,
        entrypoint: Callable[[str], None],
        task_dir: Path,
        *,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> int:
        context = get_context("spawn")
        process = context.Process(target=entrypoint, args=(str(task_dir),))
        process.start()
        while process.is_alive():
            if cancel_requested is not None and cancel_requested():
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join()
                return -15
            process.join(timeout=0.1)
        return process.exitcode or 0
