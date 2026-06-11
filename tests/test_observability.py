import json
import logging
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.logging import setup_logging
from xenix.observability import (
    _log_export_enabled,
    _metric_export_enabled,
    _otlp_enabled,
    _otlp_protocol,
    _trace_export_enabled,
    load_or_create_install_id,
    setup_observability,
    start_span,
)


OTLP_ENV_NAMES = [
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL",
    "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL",
    "XENIX_OTEL_EXPORT_TRACES",
    "XENIX_OTEL_EXPORT_METRICS",
    "XENIX_OTEL_EXPORT_LOGS",
]


def _clear_otlp_env(monkeypatch) -> None:
    for name in OTLP_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


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


def test_otlp_trace_endpoint_enables_traces_only_for_phoenix(monkeypatch) -> None:
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:6006/v1/traces")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")

    assert _trace_export_enabled() is True
    assert _metric_export_enabled() is False
    assert _log_export_enabled() is False
    assert _otlp_enabled() is True
    assert _otlp_protocol("TRACES") == "http/protobuf"


def test_otlp_global_endpoint_enables_traces_and_metrics_not_logs(monkeypatch) -> None:
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4317")

    assert _trace_export_enabled() is True
    assert _metric_export_enabled() is True
    assert _log_export_enabled() is False
    assert _otlp_enabled() is True


def test_otlp_signal_overrides_can_disable_metrics_for_global_endpoint(monkeypatch) -> None:
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4317")
    monkeypatch.setenv("XENIX_OTEL_EXPORT_METRICS", "false")

    assert _trace_export_enabled() is True
    assert _metric_export_enabled() is False
    assert _log_export_enabled() is False
    assert _otlp_enabled() is True


def test_otlp_logs_require_explicit_opt_in_and_endpoint(monkeypatch) -> None:
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://127.0.0.1:4318/v1/logs")

    assert _log_export_enabled() is False
    assert _otlp_enabled() is False

    monkeypatch.setenv("XENIX_OTEL_EXPORT_LOGS", "true")

    assert _trace_export_enabled() is False
    assert _metric_export_enabled() is False
    assert _log_export_enabled() is True
    assert _otlp_enabled() is True


def test_otlp_signal_specific_protocol_overrides_global_protocol(monkeypatch) -> None:
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "http/protobuf")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_PROTOCOL", "http/protobuf")

    assert _otlp_protocol("TRACES") == "http/protobuf"
    assert _otlp_protocol("METRICS") == "grpc"
    assert _otlp_protocol("LOGS") == "http/protobuf"
