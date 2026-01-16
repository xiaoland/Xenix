"""Logging utilities - outputs structured JSON logs to stdout"""

import json
import sys
import time
from typing import Any, Dict, Optional


_task_id: Optional[int] = None


def init_logger(task_id: int):
    """Initialize logger with task ID"""
    global _task_id
    _task_id = task_id


def log(
    message: str,
    level: str = "INFO",
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Log a structured message to stdout

    Outputs JSON line with OpenTelemetry-like format:
    {
        "type": "log",
        "timestamp": <nanoseconds>,
        "severity_text": "INFO",
        "severity_number": 9,
        "body": "message",
        "attributes": {...}
    }
    """
    severity_map = {
        "DEBUG": 5,
        "INFO": 9,
        "WARNING": 13,
        "ERROR": 17,
        "CRITICAL": 21
    }

    log_entry = {
        "type": "log",
        "timestamp": int(time.time() * 1e9),  # nanoseconds
        "observed_timestamp": int(time.time() * 1e9),
        "severity_text": level,
        "severity_number": severity_map.get(level, 9),
        "body": message,
        "resource": {
            "service.name": "ml-backend",
            "service.version": "2.0.0"
        },
        "attributes": attributes or {}
    }

    if _task_id is not None:
        log_entry["attributes"]["task_id"] = _task_id

    # Write to stdout as JSON line
    print(json.dumps(log_entry), file=sys.stdout, flush=True)


def output_result(result: Dict[str, Any]):
    """
    Output the final result to stdout

    Format:
    {
        "type": "result",
        "data": {...}
    }
    """
    result_output = {
        "type": "result",
        "data": result
    }
    print(json.dumps(result_output), file=sys.stdout, flush=True)
