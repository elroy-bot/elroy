#!/bin/bash

# Define the source and destination directories
SRC_DIR="scripts"
HOOKS_DIR=".git/hooks"
PRE_COMMIT_SCRIPT="pre-commit"

# Check if the source pre-commit script exists
if [ ! -f "$SRC_DIR/$PRE_COMMIT_SCRIPT" ]; then
    echo "Pre-commit script not found in $SRC_DIR directory."
    exit 1
fi

# Create the hooks directory if it does not exist
mkdir -p "$HOOKS_DIR"

# Copy the pre-commit script to the hooks directory
cp "$SRC_DIR/$PRE_COMMIT_SCRIPT" "$HOOKS_DIR/pre-commit"

# Make the pre-commit script executable
chmod +x "$HOOKS_DIR/pre-commit"

echo "Pre-commit hook installed successfully."
