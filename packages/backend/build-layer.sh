#!/bin/bash
set -e

echo "Building backend layer with pnpm..."

# Set CI mode to avoid TTY issues
export CI=true

# Create layer directory structure
mkdir -p opt/nodejs

# Install production dependencies only (no Node.js binary)
cp package.json opt/nodejs/
cd opt/nodejs
pnpm install --production --no-optional
rm package.json

echo "Backend layer built successfully!"
