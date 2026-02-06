#!/bin/bash
set -e

echo "Preparing ML backend dependencies for Serverless Devs build..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ML_BACKEND_DIR="$ROOT_DIR/packages/ml-backend"

# Check if required files exist
if [ ! -f "$ML_BACKEND_DIR/pyproject.toml" ]; then
  echo "ERROR: pyproject.toml not found at $ML_BACKEND_DIR/pyproject.toml"
  exit 1
fi

if [ ! -f "$ML_BACKEND_DIR/pdm.lock" ]; then
  echo "ERROR: pdm.lock not found at $ML_BACKEND_DIR/pdm.lock"
  exit 1
fi

# Create temp directory for pdm export
TEMP_DIR=$(mktemp -d)
trap "rm -rf \"$TEMP_DIR\"" EXIT

# Copy pdm files to temp directory
cp "$ML_BACKEND_DIR/pyproject.toml" "$TEMP_DIR/"
cp "$ML_BACKEND_DIR/pdm.lock" "$TEMP_DIR/"

# Install pdm and export requirements.txt
cd "$TEMP_DIR"
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH"
  exit 1
fi

python3 -m pip install --no-cache-dir --upgrade pip
python3 -m pip install --no-cache-dir pdm
pdm export --prod --format requirements --without-hashes --output requirements.txt

# Copy generated requirements.txt to ml-backend directory for Serverless Devs build
cp requirements.txt "$ML_BACKEND_DIR/requirements.txt"

echo "Generated requirements.txt from pdm for Serverless Devs build:"
echo "---"
cat "$ML_BACKEND_DIR/requirements.txt"
echo "---"

echo "ML backend dependencies prepared successfully!"
