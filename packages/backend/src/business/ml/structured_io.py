#!/usr/bin/env python3
"""
Structured input/output utilities for Python scripts.
Handles JSON communication with the Node.js executor via stdin/stdout.
"""

import json
import sys
import time
import logging


# OpenTelemetry severity mapping
SEVERITY_MAPPING = {
    logging.DEBUG: (1, "DEBUG"),
    logging.INFO: (9, "INFO"),
    logging.WARNING: (13, "WARNING"),
    logging.ERROR: (17, "ERROR"),
    logging.CRITICAL: (21, "CRITICAL"),
}


def read_json_input():
    """
    Read JSON input from stdin.

    Returns:
        dict: Parsed JSON data from stdin

    Raises:
        ValueError: If stdin cannot be parsed as JSON
    """
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            raise ValueError("No input data received from stdin")
        return json.loads(input_data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON input: {e}")


def emit_json_output(data: dict):
    """
    Emit JSON data to stdout.

    Args:
        data: Dictionary to emit as JSON
    """
    print(json.dumps(data), flush=True)


# OpenTelemetry severity mapping
SEVERITY_MAPPING = {
    logging.DEBUG: (1, "DEBUG"),
    logging.INFO: (9, "INFO"),
    logging.WARNING: (13, "WARNING"),
    logging.ERROR: (17, "ERROR"),
    logging.CRITICAL: (21, "CRITICAL"),
}


def emit_log(message: str, level: int = logging.INFO, **kwargs):
    """
    Emit a structured log message as JSON to stdout.

    Args:
        message: Log message
        level: Python logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        **kwargs: Additional attributes
    """
    severity_number, severity_text = SEVERITY_MAPPING.get(level, (0, "UNKNOWN"))

    # Only emit INFO and above
    if severity_number < 9:
        return

    timestamp_ns = int(time.time() * 1e9)

    log_data = {
        "type": "log",
        "data": {
            "timestamp": timestamp_ns,
            "observed_timestamp": timestamp_ns,
            "severity_text": severity_text,
            "severity_number": severity_number,
            "body": message,
            "resource": {
                "service.name": "xenix-ml-pipeline",
                "service.version": "1.0.0",
            },
            "attributes": kwargs,
        },
    }

    emit_json_output(log_data)


def emit_result(*args, **kwargs):
    """
    Emit model training result as JSON to stdout.

    Can be called in two ways:
    1. emit_result(model, params, metrics) - legacy format
    2. emit_result(data_dict) - new format where data_dict contains result data

    Args:
        *args: For legacy format - model, params, metrics
        **kwargs: For new format or additional data
    """
    if args and len(args) == 3:
        # Legacy format: emit_result(model, params, metrics)
        model, params, metrics = args
        result_data = {
            "type": "result",
            "data": {"model": model, "params": params, "metrics": metrics},
        }
    elif args and len(args) == 1 and isinstance(args[0], dict):
        # New format: emit_result(data_dict)
        data_dict = args[0]
        if "error" in data_dict:
            # Error case
            result_data = {"type": "result", "data": data_dict}
        else:
            # Success case
            result_data = {"type": "result", "data": data_dict}
    else:
        raise ValueError(
            "emit_result must be called as emit_result(model, params, metrics) or emit_result(data_dict)"
        )

    emit_json_output(result_data)


def emit_comparison_result(results: list, best_model: str):
    """
    Emit model comparison result as JSON to stdout.

    Args:
        results: List of model comparison results
        best_model: Name of the best performing model
    """
    comparison_data = {
        "type": "comparison_result",
        "data": {"results": results, "best_model": best_model},
    }

    emit_json_output(comparison_data)


def emit_status(status: str, error: str | None = None):
    """
    Emit task status update as JSON to stdout.

    Args:
        status: Task status ('running', 'completed', 'failed')
        error: Error message if status is 'failed'
    """
    status_data = {"type": "status", "data": {"status": status, "error": error}}

    emit_json_output(status_data)


def emit_prediction_result(output_path: str, num_predictions: int, model: str):
    """
    Emit prediction result as JSON to stdout.

    Args:
        output_path: Path to the output file
        num_predictions: Number of predictions made
        model: Model name used for prediction
    """
    # Emit as generic `result` type so TS/JS side handles both training and prediction results
    result_data = {
        "type": "result",
        "data": {
            "output_file": output_path,
            "num_predictions": num_predictions,
            "model": model,
        },
    }

    emit_json_output(result_data)


class StructuredLogger:
    """
    Logger that emits structured JSON logs to stdout.
    """

    def __init__(self, name: str = __name__):
        self.name = name

    def debug(self, message: str, **kwargs):
        """Log debug message (not emitted)"""
        print(f"[DEBUG] {message}", file=sys.stderr)

    def info(self, message: str, **kwargs):
        """Log info message"""
        emit_log(message, logging.INFO, logger_name=self.name, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        emit_log(message, logging.WARNING, logger_name=self.name, **kwargs)

    def error(self, message: str, exc_info=False, **kwargs):
        """Log error message"""
        if exc_info:
            import traceback

            kwargs["exception.traceback"] = traceback.format_exc()
        emit_log(message, logging.ERROR, logger_name=self.name, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        emit_log(message, logging.CRITICAL, logger_name=self.name, **kwargs)


def get_logger(name: str = __name__) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)
