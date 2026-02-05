#!/bin/bash
set -e

echo "Building backend layer..."

# Set CI mode to avoid TTY issues
export CI=true

echo "Node version:"
node -v || true
echo "NPM version:"
npm -v || true

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Build in a temporary directory to completely isolate from workspace
BUILD_DIR=$(mktemp -d)
trap "rm -rf \"$BUILD_DIR\"" EXIT

echo "Building in isolated directory: $BUILD_DIR"

WORK_DIR="$BUILD_DIR/workspace"
mkdir -p "$WORK_DIR"

# Generate a minimal package.json with only non-workspace dependencies
BACKEND_PKG="$ROOT_DIR/packages/backend/package.json"
if [ ! -f "$BACKEND_PKG" ]; then
  echo "Backend package.json not found at $BACKEND_PKG"
  exit 1
fi

node -e '
const fs = require("fs");
const path = process.argv[1];
const pkg = JSON.parse(fs.readFileSync(path, "utf8"));
const deps = pkg.dependencies || {};
const filtered = {};
for (const [name, version] of Object.entries(deps)) {
  if (typeof version === "string" && version.startsWith("workspace:")) continue;
  filtered[name] = version;
}
const out = {
  name: "@xenix/backend-layer",
  private: true,
  version: "0.0.0",
  type: "module",
  dependencies: filtered
};
fs.writeFileSync("package.json", JSON.stringify(out, null, 2));
' "$BACKEND_PKG"

echo "Generated layer package.json (dependencies only):"
cat package.json

mv package.json "$WORK_DIR/package.json"

# Install production deps with npm (no dev dependencies, no scripts)
cd "$WORK_DIR"
npm install --omit=dev --ignore-scripts --no-audit --no-fund

# Prepare layer output structure: ZIP root must be nodejs/
OUTPUT_DIR="$ROOT_DIR/packages/backend/layer"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/nodejs"

# Copy only node_modules into the expected path
if [ -d "$WORK_DIR/node_modules" ]; then
  cp -R "$WORK_DIR/node_modules" "$OUTPUT_DIR/nodejs/"
  # Include manifest files at the layer root to match FC guidance
  if [ -f "$WORK_DIR/package.json" ]; then
    cp "$WORK_DIR/package.json" "$OUTPUT_DIR/nodejs/package.json"
  fi
  if [ -f "$WORK_DIR/package-lock.json" ]; then
    cp "$WORK_DIR/package-lock.json" "$OUTPUT_DIR/nodejs/package-lock.json"
  fi
  echo "Layer node_modules size:"
  du -sh "$OUTPUT_DIR/nodejs/node_modules" || true
  echo "Top-level node_modules (sample):"
  ls -la "$OUTPUT_DIR/nodejs/node_modules" | head -n 40 || true
  echo "Check @hono/node-server:"
  if [ -d "$OUTPUT_DIR/nodejs/node_modules/@hono/node-server" ]; then
    echo "Found @hono/node-server"
    ls -la "$OUTPUT_DIR/nodejs/node_modules/@hono/node-server" || true
    if [ -f "$OUTPUT_DIR/nodejs/node_modules/@hono/node-server/package.json" ]; then
      cat "$OUTPUT_DIR/nodejs/node_modules/@hono/node-server/package.json" | head -n 60 || true
    fi
  else
    echo "Missing @hono/node-server in layer"
  fi
else
  echo "node_modules not found after npm install"
  exit 1
fi

echo "Backend layer built successfully!"
