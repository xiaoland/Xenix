#!/bin/bash
# Calculate MD5 hash of dependency definitions for ml-backend layer
set -e

HASH_FILE=".layer-hash-ml-backend"
PYPROJECT_TOML="packages/ml-backend/pyproject.toml"
PDM_LOCK="packages/ml-backend/pdm.lock"

# Check if required files exist
if [ ! -f "$PYPROJECT_TOML" ]; then
    echo "Error: $PYPROJECT_TOML not found"
    exit 1
fi

if [ ! -f "$PDM_LOCK" ]; then
    echo "Error: $PDM_LOCK not found"
    exit 1
fi

# Calculate combined hash of pyproject.toml and pdm.lock
CURRENT_HASH=$(cat "$PYPROJECT_TOML" "$PDM_LOCK" | md5sum | cut -d' ' -f1)

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
