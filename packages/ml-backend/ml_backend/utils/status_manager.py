"""Status file management utilities with atomic writes"""

from enum import Enum
from pathlib import Path
from typing import Optional


class TaskStatus(str, Enum):
    """Task status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StatusManager:
    """Atomic status file writer

    Manages task status file with atomic writes using temp file + rename pattern.
    All status updates are atomic to prevent race conditions.
    """

    def __init__(self, base_path: str):
        """Initialize status manager

        Args:
            base_path: Task directory path (e.g., /tmp/ml-backend/tasks/123)
        """
        self.base_path = Path(base_path)
        self.status_file = self.base_path / "status.txt"

        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def write_status(self, status: TaskStatus) -> None:
        """Atomically write status to file

        Uses temp file + atomic rename to ensure consistency.

        Args:
            status: Task status to write
        """
        # Write to temporary file first
        temp_file = self.status_file.with_suffix('.tmp')
        temp_file.write_text(status.value, encoding='utf-8')

        # Atomic rename (overwrites existing file)
        temp_file.replace(self.status_file)

    def read_status(self) -> Optional[TaskStatus]:
        """Read current status from file

        Returns:
            Current task status or None if file doesn't exist
        """
        if not self.status_file.exists():
            return None

        try:
            status_text = self.status_file.read_text(encoding='utf-8').strip()
            return TaskStatus(status_text)
        except (ValueError, IOError):
            # Invalid status or read error
            return None
