"""Logging utilities - collects logs in memory and writes to filesystem in batches"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


_task_id: Optional[int] = None
_logs_buffer: List[Dict[str, Any]] = []
_log_file_path: Optional[Path] = None
_batch_size: int = 10  # Write to file every N logs


def init_logger(task_id: int, base_path: Optional[str] = None):
    """
    Initialize logger with task ID and optional base path for log file

    Args:
        task_id: Task ID for logging context
        base_path: Base path for log file (if provided, logs will be written to {base_path}/logs.jsonl)
    """
    global _task_id, _log_file_path, _logs_buffer
    _task_id = task_id
    _logs_buffer = []

    if base_path:
        _log_file_path = Path(base_path) / "logs.jsonl"
        # Ensure directory exists
        _log_file_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        _log_file_path = None


def log(
    message: str,
    level: str = "INFO",
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Log a structured message

    Collects logs in memory buffer and writes to filesystem in batches.
    Also outputs to stdout for backward compatibility.

    Args:
        message: Log message
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        attributes: Additional attributes to include in log
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

    # Add to buffer
    _logs_buffer.append(log_entry)

    # Write to stdout for backward compatibility
    print(json.dumps(log_entry), file=sys.stdout, flush=True)

    # Check if we should flush to file
    if _log_file_path and len(_logs_buffer) >= _batch_size:
        _flush_logs_to_file()


def _flush_logs_to_file():
    """Write buffered logs to file"""
    global _logs_buffer

    if not _log_file_path or not _logs_buffer:
        return

    try:
        # Append logs to file (JSONL format - one JSON object per line)
        with open(_log_file_path, 'a') as f:
            for log_entry in _logs_buffer:
                f.write(json.dumps(log_entry) + '\n')

        # Clear buffer after successful write
        _logs_buffer = []
    except Exception as e:
        # Don't crash if logging fails
        print(f"Failed to write logs to file: {e}", file=sys.stderr, flush=True)


def flush_logs():
    """Force flush any remaining logs to file"""
    _flush_logs_to_file()


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


def get_logs() -> List[Dict[str, Any]]:
    """
    Get all logs (from buffer and file if exists)

    Returns:
        List of log entries
    """
    logs = []

    # Read from file if exists
    if _log_file_path and _log_file_path.exists():
        try:
            with open(_log_file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
        except Exception as e:
            print(f"Failed to read logs from file: {e}", file=sys.stderr, flush=True)

    # Add buffered logs
    logs.extend(_logs_buffer)

    return logs
