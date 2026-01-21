#!/bin/bash
# Prune old layer versions, keeping only the latest N versions
set -e

LAYER_NAME=$1
KEEP_VERSIONS=${2:-5}  # Default to keeping 5 versions

if [ -z "$LAYER_NAME" ]; then
    echo "Usage: $0 <layer-name> [keep-versions]"
    exit 1
fi

echo "Pruning old versions of layer: $LAYER_NAME (keeping latest $KEEP_VERSIONS)"

# List all versions sorted by version number (descending)
VERSIONS=$(s layer versions list --layer-name "$LAYER_NAME" --output json | jq -r '.[].version' | sort -rn)

# Count total versions
TOTAL_VERSIONS=$(echo "$VERSIONS" | wc -l)

if [ "$TOTAL_VERSIONS" -le "$KEEP_VERSIONS" ]; then
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
    s layer version delete --layer-name "$LAYER_NAME" --version-id "$VERSION" -y || echo "Failed to delete version $VERSION"
done

echo "Layer pruning completed!"
