#!/bin/bash

# Setup script for Elroy Web API

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found. Please install Python 3 and try again."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is required but not found. Please install pip3 and try again."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install -r "$(dirname "$0")/requirements.txt"

# Make run.py executable
chmod +x "$(dirname "$0")/run.py"

echo "Setup complete!"
echo "You can now run the API server with: ./elroy/web_api/run.py"
echo "Or: python -m elroy.web_api.run"
