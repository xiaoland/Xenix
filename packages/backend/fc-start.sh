#!/bin/bash
set -e

# Add Node.js 22 runtime from layer to PATH
export PATH="/opt/nodejs/bin:$PATH"

# Symlink node_modules from dependencies layer
ln -sf /opt/nodejs/node_modules ./node_modules

# Verify Node.js version
node --version

# Start the application
exec node dist/index.js