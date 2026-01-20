"""
ML Backend - FastAPI HTTP Server

Provides HTTP endpoints for ML operations with fire-and-forget execution.
Results are stored in {base_path}/result.json for later retrieval.

Usage:
    uvicorn server:app --host 0.0.0.0 --port 8000
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any
import asyncio

from fastapi import FastAPI, BackgroundTasks, Response
from pydantic import BaseModel, Field

app = FastAPI(title="ML Backend API", version="1.0.0")


class ExecuteRequest(BaseModel):
    """Request model for execute endpoint"""
    operation: str = Field(..., description="Operation type: batch-train, single-train, predict")
    data: Dict[str, Any] = Field(..., description="Operation data including task_id")


def get_task_base_path(task_id: int) -> str:
    """
    Calculate base path for a task

    Args:
        task_id: Task ID

    Returns:
        Base path for task files (e.g., /tmp/ml-backend/tasks/{task_id})
    """
    # Get base directory from config or environment
    base_dir = os.getenv("ML_BASE_PATH", "/tmp/ml-backend")
    return str(Path(base_dir) / "tasks" / str(task_id))


async def execute_task_async(operation: str, data: Dict[str, Any]):
    """
    Execute ML task asynchronously in a separate process

    Spawns a new Python process to run main.py with the operation data.
    This ensures CPU-intensive ML tasks don't block the FastAPI event loop.

    NOTE: main.py will construct the full task path as {ML_BASE_PATH}/tasks/{task_id}

    Args:
        operation: Operation type
        data: Operation data
    """
    task_id = data.get("task_id")

    # Prepare request payload for main.py
    request_payload = {
        "operation": operation,
        "data": data
    }
    input_json = json.dumps(request_payload)

    # Get path to main.py
    server_dir = Path(__file__).parent
    main_py_path = server_dir / "main.py"

    try:
        # Spawn subprocess to execute the task
        # NOTE: Do NOT pass --base-path here - main.py will construct it from task_id
        process = await asyncio.create_subprocess_exec(
            sys.executable,  # Python interpreter
            str(main_py_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Send input data via stdin and wait for completion
        stdout, stderr = await process.communicate(input=input_json.encode())

        # Log subprocess output for debugging
        if stdout:
            print(f"[Task {task_id}] stdout:", stdout.decode(), flush=True)
        if stderr:
            print(f"[Task {task_id}] stderr:", stderr.decode(), flush=True)

        # Check exit code
        if process.returncode != 0:
            print(f"[Task {task_id}] Process exited with code {process.returncode}", flush=True)

    except Exception as e:
        error_msg = f"Failed to spawn task process: {str(e)}"
        print(f"[Task {task_id}] {error_msg}", flush=True)

        # Write error to result.json
        task_base_path = get_task_base_path(task_id)
        result_file = Path(task_base_path) / "result.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)

        error_data = {
            "status": "failed",
            "error": error_msg
        }

        try:
            with open(result_file, 'w') as f:
                json.dump(error_data, f, indent=2)
        except Exception as write_error:
            print(f"Failed to write error result: {write_error}", flush=True)


@app.post("/execute")
async def execute(
    execute_request: ExecuteRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Execute ML operation endpoint

    Returns immediately (202 Accepted) and processes task in background.
    Results are stored in {base_path}/result.json

    Args:
        execute_request: Operation and data
        background_tasks: FastAPI background tasks

    Returns:
        Immediate response with task_id
    """
    task_id = execute_request.data.get("task_id")

    if not task_id:
        return Response(
            content=json.dumps({"error": "task_id is required in data"}),
            status_code=400,
            media_type="application/json"
        )

    # Schedule background task
    background_tasks.add_task(
        execute_task_async,
        execute_request.operation,
        execute_request.data
    )

    # Return immediately
    return {
        "status": "accepted",
        "task_id": task_id,
        "message": f"Task {task_id} accepted for processing"
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/tasks/{task_id}/result")
async def get_result(task_id: int) -> Dict[str, Any]:
    """
    Get task result

    Args:
        task_id: Task ID

    Returns:
        Task result from result.json or status
    """
    base_path = get_task_base_path(task_id)
    result_file = Path(base_path) / "result.json"

    if not result_file.exists():
        return {
            "status": "pending",
            "message": "Result not available yet"
        }

    try:
        with open(result_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to read result: {str(e)}"
        }


@app.get("/tasks/{task_id}/status")
async def get_status(task_id: int) -> Response:
    """
    Get task status from status.txt

    Args:
        task_id: Task ID

    Returns:
        Plain text status (pending/running/completed/failed)
    """
    base_path = get_task_base_path(task_id)
    status_file = Path(base_path) / "status.txt"

    if not status_file.exists():
        # No status file yet - task is pending
        return Response(content="pending", media_type="text/plain")

    try:
        with open(status_file, 'r') as f:
            status = f.read().strip()
            return Response(content=status, media_type="text/plain")
    except Exception as e:
        return Response(
            content="error",
            media_type="text/plain",
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    # Allow connection close without error (fire-and-forget)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        # Allow clients to close connection after receiving response
        timeout_keep_alive=0
    )
