#!/bin/bash
# Prune old layer versions, keeping only the latest N versions
set -euo pipefail

LAYER_NAME="${1:-}"
KEEP_VERSIONS="${2:-5}" # Default to keeping 5 versions
REGION="${3:-}"         # Aliyun region (required)
TEMPLATE_PATH="${4:-}"  # Optional s.yaml path, recommended in CI

if [ -z "$LAYER_NAME" ] || [ -z "$REGION" ]; then
    echo "Usage: $0 <layer-name> <keep-versions> <region> [template-path]"
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed"
    exit 1
fi

echo "Pruning old versions of layer: $LAYER_NAME (keeping latest $KEEP_VERSIONS)"

# Build shared CLI args for layer operations.
LAYER_ARGS=(--layer-name "$LAYER_NAME" --region "$REGION")
if [ -n "$TEMPLATE_PATH" ]; then
    LAYER_ARGS+=(-t "$TEMPLATE_PATH")
fi

# List all versions sorted by version number (descending)
LAYER_OUTPUT=$(s layer versions "${LAYER_ARGS[@]}" --output json 2>&1) || {
    echo "Warning: Failed to list layer versions: $LAYER_OUTPUT"
    echo "Skipping pruning step."
    exit 0
}

# Validate JSON output (disable set -e temporarily for this check)
set +e
JSON_VALID=$(echo "$LAYER_OUTPUT" | jq -e . > /dev/null 2>&1; echo $?)
set -e

if [ "$JSON_VALID" -ne 0 ]; then
    echo "Warning: Invalid JSON output from layer list command: $LAYER_OUTPUT"
    echo "Skipping pruning step."
    exit 0
fi

# Support multiple JSON response shapes from Serverless Devs.
VERSIONS=$(
    echo "$LAYER_OUTPUT" \
        | jq -r '.. | .version? // .versionId? // empty' \
        | grep -E '^[0-9]+$' \
        | sort -rn \
        | uniq \
        || true
)

# Count total versions (handle empty case)
TOTAL_VERSIONS=$(echo "$VERSIONS" | sed '/^$/d' | wc -l | tr -d ' ')

if [ -z "$VERSIONS" ] || [ "$TOTAL_VERSIONS" -le "$KEEP_VERSIONS" ]; then
    echo "Total versions ($TOTAL_VERSIONS) <= keep versions ($KEEP_VERSIONS), no pruning needed"
    exit 0
fi

# Calculate how many to delete
DELETE_COUNT=$((TOTAL_VERSIONS - KEEP_VERSIONS))
echo "Deleting $DELETE_COUNT old versions..."

# Get versions to delete (skip the first KEEP_VERSIONS)
VERSIONS_TO_DELETE=$(echo "$VERSIONS" | tail -n "$DELETE_COUNT")

# Delete old versions
for VERSION in $VERSIONS_TO_DELETE; do
    echo "Deleting version $VERSION..."
    s layer remove "${LAYER_ARGS[@]}" --version-id "$VERSION" -y || echo "Failed to delete version $VERSION"
done

echo "Layer pruning completed!"
