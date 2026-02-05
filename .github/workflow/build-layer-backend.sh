#!/bin/bash
set -e

echo "Building backend layer..."

# Set CI mode to avoid TTY issues
export CI=true
# Ensure pnpm deploy allows workspace package injection in CI
export PNPM_CONFIG_INJECT_WORKSPACE_PACKAGES=true

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Build in a temporary directory to completely isolate from workspace
BUILD_DIR=$(mktemp -d)
trap "rm -rf \"$BUILD_DIR\"" EXIT

echo "Building in isolated directory: $BUILD_DIR"

WORK_DIR="$BUILD_DIR/workspace"
mkdir -p "$WORK_DIR"

# Copy only what pnpm needs for a workspace install to avoid mutating the repo
FILES=(
  package.json
  pnpm-lock.yaml
  pnpm-workspace.yaml
  packages
)
if [ -f "$ROOT_DIR/.npmrc" ]; then
  FILES+=(".npmrc")
fi
tar -C "$ROOT_DIR" -cf - "${FILES[@]}" | tar -C "$WORK_DIR" -xf -

# Ensure pnpm is available (workflow installed it)
if ! command -v pnpm >/dev/null 2>&1; then
  if command -v corepack >/dev/null 2>&1; then
    echo "pnpm not found; enabling via corepack..."
    corepack enable
    corepack prepare pnpm@10.28.1 --activate
  else
    if command -v npm >/dev/null 2>&1; then
      echo "pnpm not found; installing via npm..."
      npm install -g pnpm@10.28.1
    else
      echo "pnpm not found and corepack/npm are unavailable; installing nodejs/npm via apt..."
      if command -v apt-get >/dev/null 2>&1; then
        apt-get update -y
        apt-get install -y nodejs npm
        npm install -g pnpm@10.28.1
      else
        echo "apt-get unavailable; cannot install nodejs/npm"
        exit 1
      fi
    fi
  fi
fi

# Install production deps for @xenix/backend (pnpm deploy has lockfile issues in CI)
pnpm install --filter @xenix/backend... --prod --ignore-scripts --dir "$WORK_DIR"

# Prepare layer output structure /opt/nodejs/node_modules
OUTPUT_DIR="$ROOT_DIR/packages/backend/opt"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/nodejs"

# Copy only node_modules into the expected path
SOURCE_NODE_MODULES="$WORK_DIR/packages/backend/node_modules"
if [ -L "$SOURCE_NODE_MODULES" ]; then
  # pnpm hoisted linker may make this a symlink to the workspace root
  SOURCE_NODE_MODULES="$(readlink -f "$SOURCE_NODE_MODULES")"
fi
if [ ! -d "$SOURCE_NODE_MODULES" ]; then
  # Fallback to root node_modules (hoisted linker)
  SOURCE_NODE_MODULES="$WORK_DIR/node_modules"
fi
if [ -d "$SOURCE_NODE_MODULES" ]; then
  # -L to dereference symlinks so the layer contains real files
  cp -R -L "$SOURCE_NODE_MODULES" "$OUTPUT_DIR/nodejs/"
else
  echo "node_modules not found after pnpm install"
  exit 1
fi

echo "Backend layer built successfully!"
