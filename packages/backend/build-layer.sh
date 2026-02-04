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

# Copy only package.json (no workspace files!)
cp "$SCRIPT_DIR/package.json" "$BUILD_DIR/nodejs/"

cd "$BUILD_DIR/nodejs"

# Use npm for isolated install (not pnpm, to avoid workspace detection)
npm install --omit=dev --ignore-scripts --no-optional --no-audit --no-fund

# Clean up package files, keep only node_modules
rm -f package.json package-lock.json

# Move the built layer to the expected location
cd "$SCRIPT_DIR"
rm -rf opt
mkdir -p opt
mv "$BUILD_DIR/nodejs" opt/

echo "Backend layer built successfully!"
