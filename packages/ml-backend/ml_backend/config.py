"""Configuration module for ML Backend"""

import os
from typing import Optional


class Config:
    """Global configuration for ML Backend"""

    # Base path for all file operations
    BASE_PATH: str = os.getenv("ML_BASE_PATH", "/tmp/ml-backend")

    # Database connection (optional, for logging)
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

    # Logging level
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Aliyun FC detection
    IS_FC_ENV: bool = os.getenv("FC_FUNC_CODE_PATH") is not None

    @classmethod
    def set_base_path(cls, base_path: str):
        """
        Set base path and recalculate dependent paths

        Args:
            base_path: New base path for file operations
        """
        cls.BASE_PATH = base_path

        # Ensure directories exist with new paths
        cls.ensure_directories()

    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist"""
        os.makedirs(cls.BASE_PATH, exist_ok=True)
