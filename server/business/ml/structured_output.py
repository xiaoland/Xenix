#!/usr/bin/env python3
"""
Structured output utilities for Python scripts.
Instead of writing directly to database, scripts emit JSON to stdout.
"""
import json
import sys
import time
import logging


# OpenTelemetry severity mapping
SEVERITY_MAPPING = {
    logging.DEBUG: (1, 'DEBUG'),
    logging.INFO: (9, 'INFO'),
    logging.WARNING: (13, 'WARNING'),
    logging.ERROR: (17, 'ERROR'),
    logging.CRITICAL: (21, 'CRITICAL'),
}


def emit_log(message: str, level: int = logging.INFO, **kwargs):
    """
    Emit a structured log message as JSON to stdout.
    
    Args:
        message: Log message
        level: Python logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        **kwargs: Additional attributes
    """
    severity_number, severity_text = SEVERITY_MAPPING.get(level, (0, 'UNKNOWN'))
    
    # Only emit INFO and above
    if severity_number < 9:
        return
    
    timestamp_ns = int(time.time() * 1e9)
    
    log_data = {
        'type': 'log',
        'data': {
            'timestamp': timestamp_ns,
            'observed_timestamp': timestamp_ns,
            'severity_text': severity_text,
            'severity_number': severity_number,
            'body': message,
            'resource': {
                'service.name': 'xenix-ml-pipeline',
                'service.version': '1.0.0'
            },
            'attributes': kwargs
        }
    }
    
    print(json.dumps(log_data), flush=True)


def emit_result(model: str, params: dict, metrics: dict):
    """
    Emit model training result as JSON to stdout.
    
    Args:
        model: Model name
        params: Best parameters from tuning
        metrics: Performance metrics (mse_train, mae_train, r2_train, etc.)
    """
    result_data = {
        'type': 'result',
        'data': {
            'model': model,
            'params': params,
            'metrics': metrics
        }
    }
    
    print(json.dumps(result_data), flush=True)


def emit_comparison_result(results: list, best_model: str):
    """
    Emit model comparison result as JSON to stdout.
    
    Args:
        results: List of model comparison results
        best_model: Name of the best performing model
    """
    comparison_data = {
        'type': 'comparison_result',
        'data': {
            'results': results,
            'best_model': best_model
        }
    }
    
    print(json.dumps(comparison_data), flush=True)


def emit_status(status: str, error: str = None):
    """
    Emit task status update as JSON to stdout.
    
    Args:
        status: Task status ('running', 'completed', 'failed')
        error: Error message if status is 'failed'
    """
    status_data = {
        'type': 'status',
        'data': {
            'status': status,
            'error': error
        }
    }
    
    print(json.dumps(status_data), flush=True)


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
            kwargs['exception.traceback'] = traceback.format_exc()
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
