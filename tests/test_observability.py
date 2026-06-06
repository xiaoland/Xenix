import json
import logging
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.logging import setup_logging
from xenix.observability import load_or_create_install_id, setup_observability, start_span


def test_install_id_is_random_and_persisted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())

    first = load_or_create_install_id(paths)
    second = load_or_create_install_id(paths)

    assert first == second
    assert len(first) == 32
    payload = json.loads((paths.config / "telemetry.json").read_text(encoding="utf-8"))
    assert payload == {"install_id": first}


def test_logs_include_otel_correlation_inside_span(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    log_path = setup_logging(paths)
    setup_observability(paths)

    with start_span("tests.correlation"):
        logging.getLogger("xenix.tests").info("correlated log")

    for handler in logging.getLogger().handlers:
        handler.flush()

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "correlated log"
    assert payload["otelServiceName"] == "xenix-native"
    assert payload["otelTraceID"] != "0"
    assert payload["otelSpanID"] != "0"
