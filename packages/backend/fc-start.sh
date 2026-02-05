#!/bin/bash
set -e

# Add Node.js 22 runtime from layer to PATH
export PATH="/opt/nodejs/bin:$PATH"

# Resolve CommonJS dependencies from layer without mutating /code (read-only in FC)
export NODE_PATH="/opt/nodejs/node_modules${NODE_PATH:+:$NODE_PATH}"

# Verify Node.js version
node --version

# Start the application
exec node dist/index.cjs
