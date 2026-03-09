import logging
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.logging import setup_logging


def test_setup_logging_creates_log_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    log_path = setup_logging(paths)

    logging.getLogger("xenix.tests").info("log smoke test")

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.exists()
    assert "log smoke test" in log_path.read_text(encoding="utf-8")
