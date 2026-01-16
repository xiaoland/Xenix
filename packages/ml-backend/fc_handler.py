"""
ML Backend - Aliyun FC entry point

Handler for Aliyun Function Compute (FC) environment.
Follows FC Python event handler convention.

Reference: https://help.aliyun.com/zh/functioncompute/fc/user-guide/event-handlers-1-1
"""

import json
import traceback
from typing import Any, Dict

from ml_backend.config import Config
from ml_backend.types import (
    BatchTrainInput,
    SingleTrainInput,
    PredictInput
)
from ml_backend.controllers import batch_train, single_train, predict
from ml_backend.utils import init_logger, log


def handler(event, context) -> Dict[str, Any]:
    """
    Aliyun FC event handler

    Args:
        event: Event payload (bytes or dict)
        context: FC context object with request info

    Returns:
        Response dict with statusCode, headers, and body
    """
    try:
        # Parse event
        if isinstance(event, bytes):
            event_data = json.loads(event.decode('utf-8'))
        elif isinstance(event, str):
            event_data = json.loads(event)
        else:
            event_data = event

        # Extract operation and data
        operation = event_data.get("operation")
        data = event_data.get("data", {})

        if not operation:
            raise ValueError("Missing 'operation' field in event")

        # Extract task_id for logger initialization
        task_id = data.get("task_id")
        if not task_id:
            raise ValueError("Missing 'task_id' in data")

        # Initialize logger
        init_logger(task_id)

        # Ensure directories exist
        Config.ensure_directories()

        log(f"FC handler: Processing {operation} operation", "INFO", {
            "operation": operation,
            "task_id": task_id,
            "request_id": context.request_id if hasattr(context, 'request_id') else None
        })

        # Route to appropriate operation
        result = None

        if operation == "batch-train":
            input_data = BatchTrainInput(**data)
            result = batch_train(input_data)

        elif operation == "single-train":
            input_data = SingleTrainInput(**data)
            result = single_train(input_data)

        elif operation == "predict":
            input_data = PredictInput(**data)
            result = predict(input_data)

        else:
            raise ValueError(
                f"Unknown operation: {operation}. "
                f"Supported: batch-train, single-train, predict"
            )

        # Return successful response
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "success": True,
                "data": result.model_dump()
            })
        }

    except Exception as e:
        # Log error
        error_msg = str(e)
        error_trace = traceback.format_exc()

        log(f"FC handler failed: {error_msg}", "ERROR", {
            "error": error_msg,
            "traceback": error_trace
        })

        # Return error response
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "success": False,
                "error": error_msg,
                "traceback": error_trace
            })
        }
