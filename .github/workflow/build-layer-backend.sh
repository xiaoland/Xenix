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

# Install dependencies for the layer build
cd "$BUILD_DIR/nodejs"
npm install --omit=dev --ignore-scripts --no-optional --no-audit --no-fund

# Clean up package files, keep only node_modules
rm -f package.json package-lock.json

# Move the built layer to the expected location
OUTPUT_DIR="$ROOT_DIR/opt"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
mv "$BUILD_DIR/nodejs" "$OUTPUT_DIR/"

echo "Backend layer built successfully!"
