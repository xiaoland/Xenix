#!/bin/bash
set -e

echo "Building ML backend layer..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

echo "Building in isolated directory: $BUILD_DIR"

ML_BACKEND_DIR="$ROOT_DIR/packages/ml-backend"
mkdir -p "$BUILD_DIR/project"
cp "$ML_BACKEND_DIR/pyproject.toml" "$BUILD_DIR/project/"
cp "$ML_BACKEND_DIR/pdm.lock" "$BUILD_DIR/project/"

cd "$BUILD_DIR/project"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found on PATH"
  exit 1
fi
python3 -m pip install --no-cache-dir --upgrade pip
python3 -m pip install --no-cache-dir pdm
pdm export --prod --format requirements --without-hashes --output requirements.txt
mkdir -p "$BUILD_DIR/project/opt/python"
python3 -m pip install --no-cache-dir -r requirements.txt -t "$BUILD_DIR/project/opt/python"

OUTPUT_DIR="$ROOT_DIR/packages/ml-backend/opt"
rm -rf "$OUTPUT_DIR"
mv "$BUILD_DIR/project/opt" "$OUTPUT_DIR"

echo "ML backend layer built successfully!"
