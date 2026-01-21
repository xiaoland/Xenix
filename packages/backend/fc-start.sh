#!/bin/bash
set -e

# Symlink node_modules from layer
ln -sf /opt/nodejs/node_modules ./node_modules

# Use node from layer if available, otherwise use system node
if [ -f "/opt/nodejs/bin/node" ]; then
    NODE_BIN="/opt/nodejs/bin/node"
else
    NODE_BIN="node"
fi

# Start the application
exec $NODE_BIN dist/index.js