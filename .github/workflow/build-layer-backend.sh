#!/bin/bash
set -e

echo "Building backend layer..."

# Set CI mode to avoid TTY issues
export CI=true

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Build in a temporary directory to completely isolate from workspace
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

echo "Building in isolated directory: $BUILD_DIR"

# Create layer directory structure
mkdir -p "$BUILD_DIR/nodejs"

PACKAGE_JSON="$ROOT_DIR/packages/backend/package.json"

# Copy only package.json (no workspace files!)
cp "$PACKAGE_JSON" "$BUILD_DIR/nodejs/"

# Build dependencies inside Docker to avoid native build mismatches
DOCKER_IMAGE="${DOCKER_IMAGE:-node:20-bullseye}"
echo "Using Docker image: $DOCKER_IMAGE"

docker run --rm \
  -v "$BUILD_DIR/nodejs:/workspace" \
  -w /workspace \
  "$DOCKER_IMAGE" \
  bash -c "npm install --omit=dev --ignore-scripts --no-optional --no-audit --no-fund"

# Clean up package files, keep only node_modules
rm -f package.json package-lock.json

# Move the built layer to the expected location
OUTPUT_DIR="$ROOT_DIR/opt"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
mv "$BUILD_DIR/nodejs" "$OUTPUT_DIR/"

echo "Backend layer built successfully!"
