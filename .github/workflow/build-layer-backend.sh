#!/bin/bash
set -e

echo "Preparing backend dependencies for Serverless Devs build..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/packages/backend"

# Generate a minimal package.json with only non-workspace dependencies
BACKEND_PKG="$BACKEND_DIR/package.json"
if [ ! -f "$BACKEND_PKG" ]; then
  echo "ERROR: Backend package.json not found at $BACKEND_PKG"
  exit 1
fi

# Generate clean package.json for Serverless Devs build
node -e '
const fs = require("fs");
const backendPkgPath = process.argv[1];
const outputPkgPath = process.argv[2];
const pkg = JSON.parse(fs.readFileSync(backendPkgPath, "utf8"));
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
fs.writeFileSync(outputPkgPath, JSON.stringify(out, null, 2));
' "$BACKEND_PKG" "$BACKEND_DIR/package.json.build"

# Copy generated package.json for Serverless Devs build (backup original first)
cp "$BACKEND_DIR/package.json" "$BACKEND_DIR/package.json.original"
cp "$BACKEND_DIR/package.json.build" "$BACKEND_DIR/package.json"

echo "Generated clean package.json for Serverless Devs build:"
echo "---"
cat "$BACKEND_DIR/package.json"
echo "---"

echo "Backend dependencies prepared successfully!"
