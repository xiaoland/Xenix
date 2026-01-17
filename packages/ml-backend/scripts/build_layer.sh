#!/bin/bash
# Build Python layer for Aliyun FC deployment
# This script creates a python/ directory with all dependencies

set -e

echo "Building Python layer for Aliyun FC..."

# Clean previous build
rm -rf python/
mkdir -p python/

tmp_dir=".pdm-export"
req_file="${tmp_dir}/requirements.txt"

echo "Exporting dependencies from pyproject.toml with PDM..."
mkdir -p "${tmp_dir}"
pdm export -f requirements --without-hashes -o "${req_file}"

# Install dependencies to python/ directory
echo "Installing dependencies to python/ directory..."
pip install -r "${req_file}" -t python/ --upgrade

# Cleanup exported requirements
rm -rf "${tmp_dir}"

echo "Python layer built successfully at ./python/"
echo "Layer size:"
du -sh python/

echo ""
echo "Next steps:"
echo "1. Deploy layer: s deploy xenix-ml-python-layer"
echo "2. Deploy functions: s deploy"
