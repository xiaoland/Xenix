#!/bin/bash
# Integration test runner for ml-backend

set -e

echo "========================================="
echo "ML-Backend Integration Test Suite"
echo "========================================="
echo ""

# Navigate to ml-backend directory
cd "$(dirname "$0")"

# Check if pytest is installed
if ! python -c "import pytest" 2>/dev/null; then
    echo "❌ pytest not found. Installing..."
    pip install pytest pytest-cov
fi

echo "📦 Python environment:"
python --version
echo ""

echo "📋 Installed packages:"
pip list | grep -E "(pytest|pydantic|scikit-learn|xgboost|lightgbm|pandas|numpy)"
echo ""

echo "🧪 Running integration tests..."
echo ""

# Run pytest with coverage
python -m pytest tests/test_integration.py -v --tb=short

echo ""
echo "========================================="
echo "✅ All integration tests completed!"
echo "========================================="
