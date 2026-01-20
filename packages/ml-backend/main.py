#!/usr/bin/env python3
"""
ML Backend - Main entry point for stdio/shell interface

Usage:
    echo '{"operation": "batch-train", "data": {...}}' | python main.py
    cat input.json | python main.py
    echo '{"operation": "batch-train", "data": {...}}' | python main.py --base-path /custom/path

Input: JSON via stdin
Output: JSON lines to stdout (logs + result)

Arguments:
    --base-path PATH    Override base path for file operations (default: from ML_BASE_PATH env var or /tmp/ml-backend)
"""

import sys
import os
import json
import argparse
import traceback

from pathlib import Path

from ml_backend.config import Config
from ml_backend.types import (
    OperationRequest,
    BatchTrainInput,
    SingleTrainInput,
    PredictFileInput,
    PredictInlineInput
)
from ml_backend.controllers import batch_train, single_train, predict_file, predict_inline
from ml_backend.utils.logger import TaskLogger
from ml_backend.utils import StatusManager, TaskStatus


def main():
    """Main entry point - reads from stdin, writes results to result.json"""
    logger = None
    task_id = None
    status_manager = None

    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='ML Backend - stdio interface')
        parser.add_argument('--base-path', type=str, help='Base path for file operations')
        args = parser.parse_args()

        # Read input from stdin first to get task_id
        input_text = sys.stdin.read()

        if not input_text.strip():
            raise ValueError("No input provided via stdin")

        # Parse JSON input
        try:
            request_data = json.loads(input_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON input: {e}")

        # Validate request structure
        request = OperationRequest(**request_data)

        # Extract task_id for setting up task-specific directory
        task_id = request.data.get("task_id")
        if not task_id:
            raise ValueError("Missing task_id in request data")

        # Set BASE_PATH to task-specific directory: {ML_BASE_PATH}/tasks/{task_id}
        default_base = os.getenv("ML_BASE_PATH", "/tmp/ml-backend")
        if args.base_path:
            default_base = args.base_path

        task_base_path = os.path.join(default_base, "tasks", str(task_id))
        Config.set_base_path(task_base_path)

        # Create logger instance for this task
        logger = TaskLogger(task_id, base_path=Config.BASE_PATH)

        # Create status manager for atomic status updates
        status_manager = StatusManager(Config.BASE_PATH)

        # Write initial status: running
        status_manager.write_status(TaskStatus.RUNNING)

        # Ensure directories exist
        Config.ensure_directories()

        logger.log(f"Processing {request.operation} operation", "INFO", {
            "operation": request.operation,
            "task_id": task_id
        })

        # Route to appropriate operation
        result = None

        if request.operation == "batch-train":
            input_data = BatchTrainInput(**request.data)
            result = batch_train(input_data, logger)

        elif request.operation == "single-train":
            input_data = SingleTrainInput(**request.data)
            result = single_train(input_data, logger)

        elif request.operation == "predict-file":
            input_data = PredictFileInput(**request.data)
            result = predict_file(input_data, logger)

        elif request.operation == "predict-inline":
            input_data = PredictInlineInput(**request.data)
            result = predict_inline(input_data, logger)

        else:
            raise ValueError(
                f"Unknown operation: {request.operation}. "
                f"Supported: batch-train, single-train, predict-file, predict-inline"
            )

        # Store successful result in result.json
        result_file = Path(Config.BASE_PATH) / "result.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)

        result_data = result.model_dump() if result else {}

        with open(result_file, 'w') as f:
            json.dump(result_data, f, indent=2)

        # Write completed status
        status_manager.write_status(TaskStatus.COMPLETED)

        logger.log("Operation completed successfully", "INFO")

        # Flush any remaining logs
        logger.flush()

        # Exit successfully
        sys.exit(0)

    except Exception as e:
        # Log error
        error_msg = str(e)
        error_trace = traceback.format_exc()

        # Log using logger if available
        if logger:
            logger.log(f"Operation failed: {error_msg}", "ERROR", {
                "error": error_msg,
                "traceback": error_trace
            })

        # Print to stderr for debugging
        print(f"ERROR: {error_msg}", file=sys.stderr, flush=True)
        print(error_trace, file=sys.stderr, flush=True)

        # Write failed status
        if status_manager:
            status_manager.write_status(TaskStatus.FAILED)

        # Store error result in result.json
        if Config.BASE_PATH:
            result_file = Path(Config.BASE_PATH) / "result.json"
            result_file.parent.mkdir(parents=True, exist_ok=True)

            error_data = {
                "status": "failed",
                "error": error_msg,
                "traceback": error_trace
            }

            try:
                with open(result_file, 'w') as f:
                    json.dump(error_data, f, indent=2)
            except Exception as write_error:
                print(f"Failed to write error result: {write_error}", file=sys.stderr, flush=True)

        # Flush logs if logger exists
        if logger:
            logger.flush()

        # Exit with error
        sys.exit(1)


if __name__ == "__main__":
    main()
