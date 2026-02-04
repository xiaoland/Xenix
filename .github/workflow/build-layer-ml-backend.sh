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

DOCKER_IMAGE="${DOCKER_IMAGE:-python:3.12-bullseye}"
echo "Using Docker image: $DOCKER_IMAGE"

docker run --rm \
  -v "$BUILD_DIR/project:/workspace" \
  -w /workspace \
  "$DOCKER_IMAGE" \
  bash -c "pip install --no-cache-dir pdm && pdm export --prod --format requirements --without-hashes --output requirements.txt && mkdir -p /workspace/opt/python && pip install --no-cache-dir -r requirements.txt -t /workspace/opt/python"

OUTPUT_DIR="$ROOT_DIR/opt"
rm -rf "$OUTPUT_DIR"
mv "$BUILD_DIR/project/opt" "$OUTPUT_DIR"

echo "ML backend layer built successfully!"
