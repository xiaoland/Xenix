#!/bin/bash
# Calculate MD5 hash of dependency definitions for backend layer
set -e

BACKEND_DIR="packages/backend"
HASH_FILE="$BACKEND_DIR/.layer-hash-backend"
PACKAGE_JSON="$BACKEND_DIR/package.json"
BUILD_SCRIPT=".github/workflow/build-layer-backend.sh"
WORKFLOW_FILE=".github/workflows/deploy-backend.yml"

if [ ! -f "$PACKAGE_JSON" ]; then
  echo "ERROR: Missing $PACKAGE_JSON"
  exit 1
fi

# Hash package dependencies and layer-build pipeline inputs.
CURRENT_HASH=$(cat "$PACKAGE_JSON" "$BUILD_SCRIPT" "$WORKFLOW_FILE" | md5sum | cut -d' ' -f1)

# Check if hash file exists and compare
if [ -f "$HASH_FILE" ]; then
    PREVIOUS_HASH=$(cat "$HASH_FILE")
    if [ "$CURRENT_HASH" = "$PREVIOUS_HASH" ]; then
        echo "LAYER_CHANGED=false" >> $GITHUB_OUTPUT
        echo "Dependencies unchanged, skipping layer deployment"
        exit 0
    fi
fi

# Hash changed or doesn't exist
echo "LAYER_CHANGED=true" >> $GITHUB_OUTPUT
echo "$CURRENT_HASH" > "$HASH_FILE"
echo "Dependencies changed, layer will be deployed"
