"""Logging utilities - class-based logger with batch writes to filesystem"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskLogger:
    """Logger instance for a specific task - collects logs in memory and writes in batches"""

    def __init__(self, task_id: int, base_path: Optional[str] = None, batch_size: int = 10):
        """
        Initialize logger for a task

        Args:
            task_id: Task ID for logging context
            base_path: Base path for log file (if provided, logs will be written to {base_path}/logs.jsonl)
            batch_size: Number of logs to buffer before flushing to file
        """
        self.task_id = task_id
        self.logs_buffer: List[Dict[str, Any]] = []
        self.batch_size = batch_size

        if base_path:
            self.log_file_path = Path(base_path) / "logs.jsonl"
            # Ensure directory exists
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.log_file_path = None

    def log(
        self,
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

        log_entry["attributes"]["task_id"] = self.task_id

        # Add to buffer
        self.logs_buffer.append(log_entry)

        # Write to stdout for backward compatibility
        print(json.dumps(log_entry), file=sys.stdout, flush=True)

        # Check if we should flush to file
        if self.log_file_path and len(self.logs_buffer) >= self.batch_size:
            self._flush_to_file()

    def _flush_to_file(self):
        """Write buffered logs to file"""
        if not self.log_file_path or not self.logs_buffer:
            return

        try:
            # Append logs to file (JSONL format - one JSON object per line)
            with open(self.log_file_path, 'a') as f:
                for log_entry in self.logs_buffer:
                    f.write(json.dumps(log_entry) + '\n')

            # Clear buffer after successful write
            self.logs_buffer = []
        except Exception as e:
            # Don't crash if logging fails
            print(f"Failed to write logs to file: {e}", file=sys.stderr, flush=True)

    def flush(self):
        """Force flush any remaining logs to file"""
        self._flush_to_file()

    def get_logs(self) -> List[Dict[str, Any]]:
        """
        Get all logs (from buffer and file if exists)

        Returns:
            List of log entries
        """
        logs = []

        # Read from file if exists
        if self.log_file_path and self.log_file_path.exists():
            try:
                with open(self.log_file_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            logs.append(json.loads(line))
            except Exception as e:
                print(f"Failed to read logs from file: {e}", file=sys.stderr, flush=True)

        # Add buffered logs
        logs.extend(self.logs_buffer)

        return logs


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
