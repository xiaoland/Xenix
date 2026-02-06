#!/bin/bash
set -e

echo "Building ML backend layer..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

BUILD_DIR="$ROOT_DIR/.layer-build/ml-backend"
WORK_DIR="$BUILD_DIR/work"

rm -rf "$BUILD_DIR"
mkdir -p "$WORK_DIR"

echo "Building in isolated directory: $BUILD_DIR"

ML_BACKEND_DIR="$ROOT_DIR/packages/ml-backend"
cp "$ML_BACKEND_DIR/pyproject.toml" "$WORK_DIR/"
cp "$ML_BACKEND_DIR/pdm.lock" "$WORK_DIR/"
cp "$ML_BACKEND_DIR/ml-backend.s.yaml" "$BUILD_DIR/"

cd "$WORK_DIR"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found on PATH"
  exit 1
fi
python3 -m pip install --no-cache-dir --upgrade pip
python3 -m pip install --no-cache-dir pdm
pdm export --prod --format requirements --without-hashes --output requirements.txt
mkdir -p "$BUILD_DIR/opt/python"
python3 -m pip install --no-cache-dir -r requirements.txt -t "$BUILD_DIR/opt/python"

echo "ML backend layer built successfully!"
