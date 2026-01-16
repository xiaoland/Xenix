#!/usr/bin/env python
"""
Python-based test runner for ml-backend integration tests

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --fast       # Skip slow tests (batch training)
    python run_tests.py --summary    # Run summary only
"""

import sys
import subprocess
from pathlib import Path


def main():
    """Run integration tests"""
    print("=" * 70)
    print("ML-Backend Integration Test Suite")
    print("=" * 70)
    print()

    # Check if pytest is installed
    try:
        import pytest
    except ImportError:
        print("❌ pytest not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest"], check=True)
        import pytest

    # Build pytest arguments
    args = [
        "tests/test_integration.py",
        "-v",
        "--tb=short",
        "-s",  # Don't capture output
    ]

    # Handle command line arguments
    if "--fast" in sys.argv:
        args.append("-k")
        args.append("not batch_train")
        print("🚀 Running fast tests (skipping batch training)...\n")
    elif "--summary" in sys.argv:
        args.append("-k")
        args.append("test_all_models_summary")
        print("📊 Running summary only...\n")
    else:
        print("🧪 Running all integration tests...\n")

    # Run pytest
    exit_code = pytest.main(args)

    print()
    if exit_code == 0:
        print("=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
    else:
        print("=" * 70)
        print("❌ Some tests failed")
        print("=" * 70)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
