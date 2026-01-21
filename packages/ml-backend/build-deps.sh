#!/bin/bash
set -e

echo "Installing Python dependencies for ML backend..."

# Install Python dependencies directly into function code
pip install pdm
pdm export --prod --format requirements --output requirements.txt
pip install -r requirements.txt -t .

echo "ML backend dependencies installed successfully!"
