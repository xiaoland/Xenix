#!/usr/bin/env python3
"""
PostgreSQL logging handler for OpenTelemetry-compliant logging.
Logs at INFO level and above are automatically sent to the database.
"""
import logging
import os
import time
import json
import psycopg2
from datetime import datetime


# OpenTelemetry severity mapping
SEVERITY_MAPPING = {
    logging.DEBUG: (1, 'DEBUG'),
    logging.INFO: (9, 'INFO'),
    logging.WARNING: (13, 'WARNING'),
    logging.ERROR: (17, 'ERROR'),
    logging.CRITICAL: (21, 'CRITICAL'),
}


class PostgreSQLHandler(logging.Handler):
    """
    Logging handler that writes logs to PostgreSQL following OpenTelemetry standards.
    """
    
    def __init__(self, trace_id, db_url=None):
        super().__init__()
        self.trace_id = trace_id
        self.db_url = db_url or os.environ.get('DATABASE_URL', 
                                                 'postgresql://xenix:xenix_password@localhost:5432/xenix_db')
        self.setLevel(logging.INFO)  # Only handle INFO and above
        
    def emit(self, record):
        """
        Emit a log record to PostgreSQL.
        """
        try:
            # Get severity number and text
            severity_number, severity_text = SEVERITY_MAPPING.get(
                record.levelno, (0, 'UNKNOWN')
            )
            
            # Generate timestamps (OpenTelemetry uses nanoseconds)
            timestamp_ns = int(time.time() * 1e9)
            observed_timestamp_ns = timestamp_ns
            
            # Format message
            message = self.format(record)
            
            # Build resource attributes
            resource = {
                'service.name': 'xenix-ml-pipeline',
                'service.version': '1.0.0',
            }
            
            # Build log attributes
            attributes = {
                'logger.name': record.name,
                'process.pid': record.process,
                'thread.id': record.thread,
            }
            
            # Add exception info if present
            if record.exc_info:
                attributes['exception.type'] = record.exc_info[0].__name__
                attributes['exception.message'] = str(record.exc_info[1])
            
            # Add extra fields if present
            if hasattr(record, 'task_id'):
                attributes['task.id'] = record.task_id
            if hasattr(record, 'model'):
                attributes['model.name'] = record.model
            
            # Insert into database
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO logs 
                   (timestamp, observed_timestamp, trace_id, severity_text, 
                    severity_number, body, resource, attributes, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    timestamp_ns,
                    observed_timestamp_ns,
                    self.trace_id,
                    severity_text,
                    severity_number,
                    message,
                    json.dumps(resource),
                    json.dumps(attributes),
                    datetime.now()
                )
            )
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            # Don't let logging errors break the application
            print(f"Failed to write log to database: {e}")


def setup_logger(name, trace_id, level=logging.INFO):
    """
    Set up a logger with both console and PostgreSQL handlers.
    
    Args:
        name: Logger name
        trace_id: Trace ID (task_id) for OpenTelemetry correlation
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler (all levels)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # PostgreSQL handler (INFO and above)
    pg_handler = PostgreSQLHandler(trace_id)
    pg_formatter = logging.Formatter('%(message)s')
    pg_handler.setFormatter(pg_formatter)
    logger.addHandler(pg_handler)
    
    return logger
