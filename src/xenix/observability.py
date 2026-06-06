from __future__ import annotations

import json
import os
import hashlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

from opentelemetry import metrics, propagate, trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .build_info import BUILD_COMMIT
from .config import AppPaths

INSTALL_ID_FILE_NAME = "telemetry.json"
SERVICE_NAME = "xenix-native"

_configured = False
_logging_instrumented = False
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_counters: dict[str, Any] = {}
_histograms: dict[str, Any] = {}


@dataclass(frozen=True)
class ObservabilityContext:
    install_id: str
    otlp_enabled: bool
    log_export_enabled: bool


def load_or_create_install_id(paths: AppPaths) -> str:
    path = paths.config / INSTALL_ID_FILE_NAME
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        install_id = payload.get("install_id")
        if isinstance(install_id, str) and install_id.strip():
            return install_id.strip()

    install_id = uuid4().hex
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"install_id": install_id}, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return install_id


def setup_observability(paths: AppPaths) -> ObservabilityContext:
    global _configured, _logging_instrumented, _meter_provider, _tracer_provider

    install_id = load_or_create_install_id(paths)
    otlp_enabled = _otlp_enabled()
    log_export_enabled = otlp_enabled and _env_truthy("XENIX_OTEL_EXPORT_LOGS", default=False)

    if _configured or _env_truthy("OTEL_SDK_DISABLED", default=False):
        if not _logging_instrumented:
            LoggingInstrumentor().instrument(set_logging_format=True)
            _logging_instrumented = True
        return ObservabilityContext(
            install_id=install_id,
            otlp_enabled=otlp_enabled,
            log_export_enabled=log_export_enabled,
        )

    resource = Resource.create(_resource_attributes(paths, install_id))

    tracer_provider = TracerProvider(resource=resource)
    if otlp_enabled:
        tracer_provider.add_span_processor(BatchSpanProcessor(_build_span_exporter()))
    trace.set_tracer_provider(tracer_provider)
    _tracer_provider = tracer_provider

    metric_readers = []
    if otlp_enabled:
        metric_readers.append(PeriodicExportingMetricReader(_build_metric_exporter()))
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)
    _meter_provider = meter_provider

    if log_export_enabled:
        _setup_otlp_log_export(resource)

    if not _logging_instrumented:
        LoggingInstrumentor().instrument(set_logging_format=True)
        _logging_instrumented = True

    _configured = True
    return ObservabilityContext(
        install_id=install_id,
        otlp_enabled=otlp_enabled,
        log_export_enabled=log_export_enabled,
    )


def shutdown_observability() -> None:
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
    if _meter_provider is not None:
        _meter_provider.shutdown()


def flush_observability() -> None:
    if _tracer_provider is not None:
        _tracer_provider.force_flush()
    if _meter_provider is not None:
        _meter_provider.force_flush()


def get_tracer(name: str):
    return trace.get_tracer(name)


def get_meter(name: str):
    return metrics.get_meter(name)


@contextmanager
def start_span(name: str, attributes: dict[str, Any] | None = None):
    with trace.get_tracer("xenix").start_as_current_span(
        name,
        attributes=safe_attributes(attributes or {}),
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc, attributes=safe_attributes({"error.type": error_type(exc)}))
            span.set_status(trace.Status(trace.StatusCode.ERROR, error_type(exc)))
            raise


def record_counter(name: str, value: int = 1, attributes: dict[str, Any] | None = None) -> None:
    counter = _counters.get(name)
    if counter is None:
        counter = metrics.get_meter("xenix").create_counter(name)
        _counters[name] = counter
    counter.add(value, safe_attributes(attributes or {}))


def record_histogram(name: str, value: float, attributes: dict[str, Any] | None = None, *, unit: str | None = None) -> None:
    key = f"{name}|{unit or ''}"
    histogram = _histograms.get(key)
    if histogram is None:
        histogram = metrics.get_meter("xenix").create_histogram(name, unit=unit or "")
        _histograms[key] = histogram
    histogram.record(value, safe_attributes(attributes or {}))


def safe_attributes(values: dict[str, Any]) -> dict[str, str | bool | int | float]:
    safe: dict[str, str | bool | int | float] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, Enum):
            safe[key] = str(value.value)
        elif isinstance(value, str | bool | int | float):
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe


def error_type(exc: BaseException) -> str:
    return exc.__class__.__name__


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def inject_context(carrier: dict[str, str]) -> dict[str, str]:
    propagate.inject(carrier)
    return carrier


def extract_context(carrier: dict[str, str]):
    return propagate.extract(carrier)


def _resource_attributes(paths: AppPaths, install_id: str) -> dict[str, str]:
    return {
        "service.name": SERVICE_NAME,
        "service.version": _service_version(),
        "xenix.build.commit": BUILD_COMMIT,
        "xenix.install.id": install_id,
        "xenix.package_mode": "packaged" if getattr(sys, "frozen", False) else "source",
        "xenix.runtime.home_class": "custom" if os.getenv("XENIX_APP_HOME") else "default",
        "os.type": sys.platform,
        "python.version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


def _service_version() -> str:
    try:
        return version("xenix-native")
    except PackageNotFoundError:
        return "1.0.0"


def _otlp_enabled() -> bool:
    return any(
        os.getenv(name)
        for name in (
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        )
    )


def _otlp_protocol() -> str:
    return os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").lower()


def _build_span_exporter():
    if _otlp_protocol() == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    return OTLPSpanExporter()


def _build_metric_exporter():
    if _otlp_protocol() == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    else:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

    return OTLPMetricExporter()


def _setup_otlp_log_export(resource: Resource) -> None:
    import logging

    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    if _otlp_protocol() == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    else:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry._logs import set_logger_provider

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider))


def _env_truthy(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
