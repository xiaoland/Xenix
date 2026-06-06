import logging
import json
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
    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "log smoke test"
    assert payload["logger"] == "xenix.tests"
    assert payload["level"] == "info"


def test_setup_logging_preserves_structured_extra(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    log_path = setup_logging(paths)

    logging.getLogger("xenix.tests").info(
        "structured log smoke test",
        extra={"event_name": "tests.structured_log_smoke", "status": "succeeded"},
    )

    for handler in logging.getLogger().handlers:
        handler.flush()

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "structured log smoke test"
    assert payload["event_name"] == "tests.structured_log_smoke"
    assert payload["status"] == "succeeded"
