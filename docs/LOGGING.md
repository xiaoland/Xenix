# Logging System Documentation

## Overview

Xenix now includes a comprehensive logging system that stores Python script logs in PostgreSQL following OpenTelemetry standards. Users can view detailed task progress in real-time through the frontend UI.

## Architecture

```
Python Script → PostgreSQLHandler → PostgreSQL logs table
                                           ↓
                                    API: /api/logs/:taskId
                                           ↓
                                    Frontend Log Viewer (3s polling)
```

## OpenTelemetry Compliance

The `logs` table follows OpenTelemetry semantic conventions with trace_id (task_id) for correlation, severity levels, timestamps in nanoseconds, and structured attributes.

## Python Usage

```python
from log_handler import setup_logger

logger = setup_logger(__name__, task_id)
logger.info("Starting data processing")
logger.error("Error occurred", exc_info=True)
```

## Frontend Log Viewer

- **Tabbed Interface**: One tab per task
- **Real-Time Updates**: 3-second polling
- **Color-Coded**: DEBUG (gray), INFO (white), WARNING (yellow), ERROR (red), CRITICAL (dark red)
- **Terminal-Style**: Dark background, monospace font

## API

**GET /api/logs/:taskId** - Returns up to 500 most recent logs for a task

See implementation files for complete details.
