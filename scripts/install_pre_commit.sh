#!/bin/bash

# Define the source and destination directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$SCRIPT_DIR"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
PRE_COMMIT_SCRIPT="pre-commit"

# Check if the source pre-commit script exists
if [ ! -f "$SRC_DIR/$PRE_COMMIT_SCRIPT" ]; then
    echo "Pre-commit script not found at $SRC_DIR/$PRE_COMMIT_SCRIPT."
    exit 1
fi

# Create the hooks directory if it does not exist
mkdir -p "$HOOKS_DIR"

# Install the pre-commit script as a symlink so updates are picked up automatically
ln -sf "$SRC_DIR/$PRE_COMMIT_SCRIPT" "$HOOKS_DIR/pre-commit"

# Ensure the pre-commit script is executable
chmod +x "$SRC_DIR/$PRE_COMMIT_SCRIPT"
chmod +x "$HOOKS_DIR/pre-commit"

echo "Pre-commit hook installed successfully."
