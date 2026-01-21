#!/bin/bash
# Calculate MD5 hash of dependency definitions for backend layer
set -e

HASH_FILE=".layer-hash-backend"
PACKAGE_JSON="packages/backend/package.json"

# Calculate hash of package.json
CURRENT_HASH=$(md5sum "$PACKAGE_JSON" | cut -d' ' -f1)

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
