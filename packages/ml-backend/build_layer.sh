#!/bin/bash
# Build Python layer for Aliyun FC deployment
# This script creates a python/ directory with all dependencies

set -e

echo "Building Python layer for Aliyun FC..."

# Clean previous build
rm -rf python/
mkdir -p python/

# Install dependencies to python/ directory
echo "Installing dependencies to python/ directory..."
pip install -r requirements.txt -t python/ --upgrade

echo "Python layer built successfully at ./python/"
echo "Layer size:"
du -sh python/

echo ""
echo "Next steps:"
echo "1. Deploy layer: s deploy xenix-ml-python-layer"
echo "2. Deploy functions: s deploy"
