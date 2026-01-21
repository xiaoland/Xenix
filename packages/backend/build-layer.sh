#!/bin/bash
set -e

echo "Building backend layer with pnpm..."

# Create layer directory structure
mkdir -p opt/nodejs

# Install production dependencies only (no Node.js binary)
cp package.json opt/nodejs/
cd opt/nodejs
pnpm install --prod --no-optional
rm package.json

echo "Backend layer built successfully!"
